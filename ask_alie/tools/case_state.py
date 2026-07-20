"""get_case_state and list_candidates tools (Spec §21.1)."""

from __future__ import annotations

import json
from typing import Any

from ask_alie.events.store import CandidateStore
from ask_alie.reports.map import load_report_map
from ask_alie.tools.registry import ToolContext, tool
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.manifest import load_manifest
from ask_alie.workspace.tasks import AgentTask


@tool(
    "get_case_state",
    "Return a concise summary of the current Ask ALIE case state.",
)
async def get_case_state(ctx: ToolContext) -> dict[str, Any]:
    manifest = load_manifest(ctx.paths)
    units = load_report_map(ctx.paths)
    page_records = list(ctx.paths.pages_dir.rglob("page_*.json"))
    reports_read = {p.stem.removesuffix(".result") for p in ctx.paths.readers_dir.glob("*.result.json")}
    tasks = JsonlStore(ctx.paths.tasks_file, AgentTask).read_all()
    candidates = CandidateStore(ctx.paths).read_all()

    failures_path = ctx.paths.readers_dir / "failures.jsonl"
    failure_count = (
        len(failures_path.read_text(encoding="utf-8").splitlines()) if failures_path.exists() else 0
    )
    flags = sorted(
        {flag for record_path in page_records for flag in json.loads(record_path.read_text(encoding="utf-8")).get("flags", [])}
    )
    return {
        "case_id": manifest.case_id,
        "run_status": manifest.run_status,
        "document_count": len(manifest.documents),
        "page_count": len(page_records),
        "report_count": len([u for u in units if u.status != "superseded"]),
        "reports_read": len(reports_read),
        "reports_unread": [
            u.report_id for u in units if u.status != "superseded" and u.report_id not in reports_read
        ],
        "candidate_count": len(candidates),
        "pending_tasks": sum(1 for t in tasks if t.status == "pending"),
        "reader_failures": failure_count,
        "page_flags": flags,
    }


@tool(
    "list_candidates",
    "List candidate events, optionally filtered by report ids or flags.",
    {
        "type": "object",
        "properties": {
            "report_ids": {"type": "array", "items": {"type": "string"}},
            "flags": {"type": "array", "items": {"type": "string"}},
            "limit": {"type": "integer"},
        },
    },
)
async def list_candidates(
    ctx: ToolContext,
    report_ids: list[str] | None = None,
    flags: list[str] | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    events = CandidateStore(ctx.paths).read_all()
    if report_ids:
        events = [e for e in events if e.report_id in report_ids]
    if flags:
        events = [e for e in events if any(f in e.flags for f in flags)]
    total = len(events)
    return {
        "total": total,
        "returned": min(total, limit),
        "events": [
            {
                "event_id": e.event_id,
                "report_id": e.report_id,
                "event_date": e.event_date,
                "event_type": e.event_type,
                "summary_fr": e.summary_fr[:200],
                "flags": e.flags,
                "pass": e.origin.pass_number if e.origin else 1,
            }
            for e in events[:limit]
        ],
    }
