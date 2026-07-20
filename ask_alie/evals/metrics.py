"""Run metrics per Spec §4. Metrics that need live runs or human adjudication
report null rather than fake numbers."""

from __future__ import annotations

from pathlib import Path

from ask_alie.curation.models import CurationAssignment
from ask_alie.evals.gold import GoldEvent, load_gold
from ask_alie.evals.match import MatchRecord, match_events
from ask_alie.events.models import CandidateEvent
from ask_alie.events.store import CandidateStore
from ask_alie.serialization import AlieModel
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.paths import CasePaths
from ask_alie.workspace.runlog import log_action


class MetricsReport(AlieModel):
    gold_total: int
    gold_captured: int
    total_candidates: int
    default_queue_count: int | None = None
    secondary_queue_count: int | None = None
    wrong_date_events: int
    uncertain_matches: int
    unmatched_gold: int
    unmatched_candidates: int
    defensible_extras: int | None = None  # manual adjudication (Spec §28.4)
    unsupported_extras: int | None = None  # manual adjudication
    recovered_gold_by_loop: int
    loop_added_candidates: int
    review_time_minutes: float | None = None
    run_cost_usd: float | None = None
    run_duration_seconds: float | None = None
    stability: dict | None = None  # filled by cross-run comparison (Spec §28.5)


def compute_metrics(
    gold_events: list[GoldEvent],
    candidates: list[CandidateEvent],
    matches: list[MatchRecord],
    assignments: list[CurationAssignment],
) -> MetricsReport:
    matched_candidate_ids = {m.candidate_event_id for m in matches if m.candidate_event_id}
    captured = [m for m in matches if m.date_match and m.meaning_match == "full"]
    by_id = {c.event_id: c for c in candidates}

    def pass_number(event_id: str | None) -> int:
        event = by_id.get(event_id or "")
        return event.origin.pass_number if event and event.origin else 1

    queues: dict[str, int] = {}
    for assignment in assignments:
        queues[assignment.queue] = queues.get(assignment.queue, 0) + 1

    return MetricsReport(
        gold_total=len(gold_events),
        gold_captured=len(captured),
        total_candidates=len(candidates),
        default_queue_count=queues.get("default") if assignments else None,
        secondary_queue_count=queues.get("secondary") if assignments else None,
        wrong_date_events=sum(
            1 for m in matches if not m.date_match and m.meaning_match == "full"
        ),
        uncertain_matches=sum(1 for m in matches if m.needs_adjudication),
        unmatched_gold=sum(1 for m in matches if m.candidate_event_id is None),
        unmatched_candidates=len(candidates) - len(matched_candidate_ids),
        recovered_gold_by_loop=sum(1 for m in captured if pass_number(m.candidate_event_id) > 1),
        loop_added_candidates=sum(
            1 for c in candidates if c.origin and c.origin.pass_number > 1
        ),
    )


def evaluate_case(paths: CasePaths, gold_path: Path) -> MetricsReport:
    gold_events = load_gold(gold_path)
    candidates = CandidateStore(paths).read_all()
    matches = match_events(gold_events, candidates)
    assignments = JsonlStore(paths.curation_file, CurationAssignment).read_all()
    report = compute_metrics(gold_events, candidates, matches, assignments)

    paths.eval_dir.mkdir(parents=True, exist_ok=True)
    matches_store: JsonlStore[MatchRecord] = JsonlStore(
        paths.eval_dir / "matches.jsonl", MatchRecord
    )
    (paths.eval_dir / "matches.jsonl").unlink(missing_ok=True)
    matches_store.append_many(matches)
    (paths.eval_dir / "metrics.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    from ask_alie.evals.report import render_run_summary

    (paths.eval_dir / "run_summary.md").write_text(
        render_run_summary(report), encoding="utf-8"
    )
    log_action(
        paths,
        actor="evaluate",
        action="evaluate_case",
        result={"gold_captured": report.gold_captured, "gold_total": report.gold_total},
    )
    return report
