"""run_curator and finish_case tools (Spec §21.2)."""

from __future__ import annotations

from typing import Any

from ask_alie.curation.models import CurationAssignment
from ask_alie.curation.service import run_curator as run_curator_service
from ask_alie.events.store import CandidateStore
from ask_alie.tools.registry import ToolContext, tool
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.manifest import load_manifest, save_manifest
from ask_alie.workspace.runlog import log_action
from ask_alie.workspace.tasks import AgentTask


@tool(
    "run_curator",
    "Run curation over all current candidates, assigning default/secondary queues.",
    {
        "type": "object",
        "properties": {"curator_run_id": {"type": "string"}},
    },
)
async def run_curator(ctx: ToolContext, curator_run_id: str = "curator_0001") -> dict[str, Any]:
    if ctx.client is None:
        return {"error": "no model client configured for curation"}
    return await run_curator_service(ctx.paths, ctx.client, curator_run_id)


@tool(
    "finish_case",
    "Finalize the case: completeness checks, chronology.json output, manifest status.",
)
async def finish_case(ctx: ToolContext) -> dict[str, Any]:
    events = CandidateStore(ctx.paths).read_all()
    assignments = JsonlStore(ctx.paths.curation_file, CurationAssignment).read_all()
    tasks = JsonlStore(ctx.paths.tasks_file, AgentTask).read_all()
    pending_high = [t.task_id for t in tasks if t.status == "pending" and t.priority == "high"]

    warnings: list[str] = []
    if not assignments:
        warnings.append("curation has not run")
    if pending_high:
        warnings.append(f"pending high-priority tasks: {pending_high}")
    unresolved_dates = sum(1 for e in events if "date_unresolved" in e.flags)

    queue_by_event = {a.event_id: a for a in assignments}
    rows = []
    for event in sorted(events, key=lambda e: (e.event_date or "9999-99-99")):
        assignment = queue_by_event.get(event.event_id)
        rows.append(
            {
                "event": event.model_dump(),
                "queue": assignment.queue if assignment else "unassigned",
                "curation_reason": assignment.reason if assignment else None,
                "duplicate_of": assignment.duplicate_of if assignment else None,
                "needs_review": assignment.needs_review if assignment else True,
            }
        )
    import json as _json

    ctx.paths.output_dir.mkdir(parents=True, exist_ok=True)
    (ctx.paths.output_dir / "chronology.json").write_text(
        _json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    manifest = load_manifest(ctx.paths)
    manifest.run_status = "finished"
    save_manifest(ctx.paths, manifest)
    log_action(ctx.paths, actor="tools", action="finish_case",
               result={"events": len(events), "warnings": warnings})
    return {
        "events": len(events),
        "default": sum(1 for r in rows if r["queue"] == "default"),
        "secondary": sum(1 for r in rows if r["queue"] == "secondary"),
        "unresolved_dates": unresolved_dates,
        "warnings": warnings,
        "output": "output/chronology.json",
    }
