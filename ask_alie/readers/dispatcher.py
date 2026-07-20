"""Bounded parallel reader dispatcher (Spec §23)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from ask_alie.events.models import CandidateEvent, EventOrigin
from ask_alie.events.restore import restore_event_dates
from ask_alie.events.store import CandidateStore
from ask_alie.llm.client import ModelClient
from ask_alie.privacy.tokenize import load_date_registry
from ask_alie.readers.runner import ReaderFailure, run_reader
from ask_alie.readers.schema import ReaderResult
from ask_alie.reports.map import load_report_map
from ask_alie.reports.service import load_report_text
from ask_alie.workspace.paths import CasePaths
from ask_alie.workspace.runlog import log_action


@dataclass
class DispatchSummary:
    submitted: int = 0
    completed: int = 0
    failed: int = 0
    new_candidate_events: int = 0
    result_paths: list[str] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)

    def render(self) -> str:
        return (
            f"readers submitted {self.submitted}, completed {self.completed}, "
            f"failed {self.failed}, new candidate events {self.new_candidate_events}"
        )


def _record_failure(paths: CasePaths, failure: ReaderFailure) -> dict:
    entry = {"report_id": failure.report_id, "error": str(failure), "attempts": failure.attempts}
    failures_path = paths.readers_dir / "failures.jsonl"
    failures_path.parent.mkdir(parents=True, exist_ok=True)
    with failures_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


async def dispatch_readers(
    paths: CasePaths,
    client: ModelClient,
    report_ids: list[str],
    reason: str = "initial",
    instructions: str | None = None,
    max_concurrency: int = 5,
    pass_number: int = 1,
) -> DispatchSummary:
    units = {u.report_id: u for u in load_report_map(paths)}
    unknown = [rid for rid in report_ids if rid not in units]
    if unknown:
        raise ValueError(f"Unknown report ids: {unknown}")

    semaphore = asyncio.Semaphore(max_concurrency)

    async def run_one(report_id: str) -> ReaderResult | ReaderFailure:
        async with semaphore:
            unit = units[report_id]
            text = load_report_text(paths, report_id)
            try:
                result, _attempts = await run_reader(client, unit, text, instructions)
                # save immediately so progress views count completed reports live
                paths.readers_dir.mkdir(parents=True, exist_ok=True)
                (paths.readers_dir / f"{report_id}.result.json").write_text(
                    result.model_dump_json(indent=2), encoding="utf-8"
                )
                return result
            except ReaderFailure as failure:
                return failure

    outcomes = await asyncio.gather(*(run_one(rid) for rid in report_ids))

    summary = DispatchSummary(submitted=len(report_ids))
    store = CandidateStore(paths)
    date_registry = load_date_registry(paths)
    event_count = len(store.read_all())

    for report_id, outcome in zip(report_ids, outcomes):
        if isinstance(outcome, ReaderFailure):
            summary.failed += 1
            summary.failures.append(_record_failure(paths, outcome))
            continue

        result_path = paths.readers_dir / f"{report_id}.result.json"
        result_path.write_text(outcome.model_dump_json(indent=2), encoding="utf-8")
        summary.result_paths.append(str(result_path.relative_to(paths.root)))
        summary.completed += 1

        events: list[CandidateEvent] = []
        for draft in outcome.events:
            event_count += 1
            events.append(
                CandidateEvent(
                    event_id=f"event_{event_count:04d}",
                    report_id=report_id,
                    origin=EventOrigin(
                        reader_run_id=f"reader_{report_id}_p{pass_number}",
                        pass_number=pass_number,
                        reason_for_pass=reason,
                    ),
                    **draft.model_dump(),
                )
            )
        restore_event_dates(events, date_registry)
        store.append_events(events)
        summary.new_candidate_events += len(events)

    log_action(
        paths,
        actor="dispatcher",
        action="dispatch_readers",
        targets=report_ids,
        reason=reason,
        result={
            "completed": summary.completed,
            "failed": summary.failed,
            "candidate_events": summary.new_candidate_events,
        },
    )
    return summary
