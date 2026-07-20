"""Gap Agent service: local facts in, targeted tasks out, executor for follow-ups (Spec §18).

Local code computes FACTS (zero-event reports, uncited date tokens, reader
flags); the model judges which gaps matter. The executor performs reread and
inspection tasks and enforces the Spec §15.4 pass limit.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ask_alie.agents.schemas import GapResult
from ask_alie.agents.specs import load_prompt
from ask_alie.events.store import CandidateStore
from ask_alie.llm.client import ModelClient
from ask_alie.readers.schema import ReaderResult
from ask_alie.reports.map import load_report_map
from ask_alie.reports.service import load_report_text
from ask_alie.tools.registry import ToolContext
from ask_alie.tools.readers import dispatch_readers
from ask_alie.tools.tasks import create_tasks, resolve_tasks
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.runlog import log_action
from ask_alie.workspace.tasks import AgentTask

_DATE_TOKEN = re.compile(r"\[\[DATE_[A-Z0-9]+\]\]")
MAX_READER_PASSES = 3


def build_gap_input(ctx: ToolContext) -> dict[str, Any]:
    units = [u for u in load_report_map(ctx.paths) if u.status != "superseded"]
    events = CandidateStore(ctx.paths).read_all()
    events_by_report: dict[str, list] = {}
    for event in events:
        events_by_report.setdefault(event.report_id, []).append(event)

    reports: list[dict[str, Any]] = []
    for unit in units:
        result_path = ctx.paths.readers_dir / f"{unit.report_id}.result.json"
        read = result_path.exists()
        report_events = events_by_report.get(unit.report_id, [])
        try:
            text = load_report_text(ctx.paths, unit.report_id)
        except FileNotFoundError:
            text = ""
        tokens = set(_DATE_TOKEN.findall(text))
        cited = {e.event_date_token for e in report_events}
        entry: dict[str, Any] = {
            "report_id": unit.report_id,
            "document_type": unit.document_type,
            "pages": [unit.page_start, unit.page_end],
            "boundary_confidence": unit.boundary_confidence,
            "flags": unit.flags,
            "read": read,
            "event_count": len(report_events),
            "date_tokens_in_text": len(tokens),
            "uncited_date_tokens": sorted(tokens - cited),
        }
        if read:
            result = ReaderResult.model_validate_json(result_path.read_text(encoding="utf-8"))
            assessment = result.reader_assessment
            entry["reader_flags"] = {
                "possible_boundary_problem": assessment.possible_boundary_problem,
                "possible_missing_pages": assessment.possible_missing_pages,
            }
            if result.cross_references:
                entry["cross_references"] = [c.description for c in result.cross_references][:5]
        reports.append(entry)

    tasks = JsonlStore(ctx.paths.tasks_file, AgentTask).read_all()
    return {
        "reports": reports,
        "total_candidates": len(events),
        "pending_tasks": [t.model_dump() for t in tasks if t.status == "pending"],
    }


async def run_gap_review(ctx: ToolContext, client: ModelClient) -> dict[str, Any]:
    facts = build_gap_input(ctx)
    prompt = (
        "Review this case state and propose targeted follow-up tasks (JSON facts):\n"
        + json.dumps(facts, ensure_ascii=False, indent=1)
    )
    result = await client.structured(prompt, GapResult, system=load_prompt("gap.md"))
    created: dict[str, Any] = {"created": []}
    if result.tasks:
        created = await create_tasks(
            ctx,
            tasks=[t.model_dump(exclude_none=True) for t in result.tasks],
            requested_by="gap_agent",
        )
    log_action(
        ctx.paths,
        actor="gap_agent",
        action="run_gap_review",
        result={"tasks_created": len(created["created"]), "assessment": result.assessment[:300]},
    )
    return {
        "tasks_created": created["created"],
        "assessment": result.assessment,
    }


def _next_pass(ctx: ToolContext, report_id: str) -> int:
    events = [e for e in CandidateStore(ctx.paths).read_all() if e.report_id == report_id]
    highest = max((e.origin.pass_number for e in events if e.origin), default=1)
    return highest + 1


async def execute_tasks(ctx: ToolContext, max_reader_passes: int = MAX_READER_PASSES) -> dict[str, Any]:
    """Execute pending reread/inspect tasks; leave judgment-heavy ones for the orchestrator."""
    tasks = JsonlStore(ctx.paths.tasks_file, AgentTask).read_all()
    pending = sorted(
        (t for t in tasks if t.status == "pending"),
        key=lambda t: {"high": 0, "medium": 1, "low": 2}.get(t.priority, 1),
    )
    executed, skipped, left_pending = [], [], []

    for task in pending:
        if task.action == "reread_report":
            for report_id in task.target_ids:
                next_pass = _next_pass(ctx, report_id)
                if next_pass > max_reader_passes:
                    skipped.append(task.task_id)
                    await resolve_tasks(
                        ctx, task_ids=[task.task_id], status="skipped",
                        result_summary=f"pass limit reached ({max_reader_passes})",
                    )
                    break
                summary = await dispatch_readers(
                    ctx,
                    report_ids=[report_id],
                    reason="gap_reread",
                    instructions=task.instructions,
                    pass_number=next_pass,
                )
                executed.append(task.task_id)
                await resolve_tasks(
                    ctx, task_ids=[task.task_id],
                    result_summary=f"reread pass {next_pass}: "
                    f"{summary.get('new_candidate_events', 0)} new events",
                )
        elif task.action == "inspect_pages":
            executed.append(task.task_id)
            await resolve_tasks(
                ctx, task_ids=[task.task_id],
                result_summary=f"pages surfaced for review: {task.target_ids}",
            )
        else:
            left_pending.append(task.task_id)  # resegment/search need orchestrator judgment

    return {"executed": executed, "skipped": skipped, "pending": left_pending}
