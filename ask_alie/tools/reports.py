"""Report tools: inspect_report, save_report_map, update_report_units (Spec §21).

Boundary changes invalidate only the affected reader results (Spec §34):
result files are removed and related candidate events are flagged stale —
never deleted.
"""

from __future__ import annotations

from typing import Any

from ask_alie.events.store import CandidateStore
from ask_alie.reports.map import load_report_map, save_report_map as write_map
from ask_alie.reports.models import ReportUnit
from ask_alie.reports.service import assemble_report_text, load_report_text
from ask_alie.tools.registry import ToolContext, tool
from ask_alie.workspace.runlog import log_action

STALE_FLAG = "stale_unit"


def _invalidate_reader_results(ctx: ToolContext, report_ids: list[str]) -> None:
    for report_id in report_ids:
        result_path = ctx.paths.readers_dir / f"{report_id}.result.json"
        result_path.unlink(missing_ok=True)
    store = CandidateStore(ctx.paths)
    events = store.read_all()
    changed = False
    for event in events:
        if event.report_id in report_ids and STALE_FLAG not in event.flags:
            event.flags.append(STALE_FLAG)
            changed = True
    if changed:
        store.rewrite(events)


def _next_number(units: list[ReportUnit]) -> int:
    return 1 + max((int(u.report_id.split("_")[1]) for u in units), default=0)


def _new_unit(number: int, document_id: str, start: int, end: int, template: ReportUnit,
              reason: str) -> ReportUnit:
    return ReportUnit(
        report_id=f"report_{number:04d}",
        document_id=document_id,
        page_start=start,
        page_end=end,
        page_ids=[f"{document_id}:p_{n:04d}" for n in range(start, end + 1)],
        document_type=template.document_type,
        title=template.title,
        boundary_confidence="medium",
        boundary_reason=reason,
    )


@tool(
    "inspect_report",
    "Return one report unit's metadata, text preview and reader-result summary.",
    {
        "type": "object",
        "properties": {
            "report_id": {"type": "string"},
            "include_text": {"type": "boolean"},
        },
        "required": ["report_id"],
    },
)
async def inspect_report(ctx: ToolContext, report_id: str, include_text: bool = False) -> dict[str, Any]:
    units = {u.report_id: u for u in load_report_map(ctx.paths)}
    unit = units.get(report_id)
    if unit is None:
        return {"error": f"unknown report: {report_id}"}
    payload: dict[str, Any] = {"unit": unit.model_dump()}
    result_path = ctx.paths.readers_dir / f"{report_id}.result.json"
    payload["reader_result_path"] = (
        str(result_path.relative_to(ctx.paths.root)) if result_path.exists() else None
    )
    try:
        text = load_report_text(ctx.paths, report_id)
        payload["text_characters"] = len(text)
        if include_text:
            payload["text"] = text[:8000]
    except FileNotFoundError:
        payload["text_characters"] = 0
    return payload


@tool(
    "save_report_map",
    "Replace the report map with proposed units (Scout output). Invalidates all reader results.",
    {
        "type": "object",
        "properties": {
            "units": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "document_id": {"type": "string"},
                        "page_start": {"type": "integer"},
                        "page_end": {"type": "integer"},
                        "document_type": {"type": "string"},
                        "title": {"type": "string"},
                        "confidence": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["document_id", "page_start", "page_end"],
                },
            }
        },
        "required": ["units"],
    },
)
async def save_report_map(ctx: ToolContext, units: list[dict]) -> dict[str, Any]:
    existing = load_report_map(ctx.paths)
    if existing:
        _invalidate_reader_results(ctx, [u.report_id for u in existing])
    new_units: list[ReportUnit] = []
    for index, spec in enumerate(units, start=1):
        unit = ReportUnit(
            report_id=f"report_{index:04d}",
            document_id=spec["document_id"],
            page_start=int(spec["page_start"]),
            page_end=int(spec["page_end"]),
            page_ids=[
                f"{spec['document_id']}:p_{n:04d}"
                for n in range(int(spec["page_start"]), int(spec["page_end"]) + 1)
            ],
            document_type=spec.get("document_type", "unknown"),
            title=spec.get("title", ""),
            boundary_confidence=spec.get("confidence", "medium"),
            boundary_reason=spec.get("reason", ""),
        )
        assemble_report_text(ctx.paths, unit)
        new_units.append(unit)
    write_map(ctx.paths, new_units)
    log_action(ctx.paths, actor="tools", action="save_report_map",
               result={"units": len(new_units)})
    return {"saved_units": len(new_units)}


@tool(
    "update_report_units",
    "Split, merge, resize, relabel or mark a report unit uncertain. Invalidates affected reader results.",
    {
        "type": "object",
        "properties": {
            "operation": {"type": "string", "enum": ["split", "merge", "resize", "relabel", "mark_uncertain"]},
            "report_ids": {"type": "array", "items": {"type": "string"}},
            "split_at_page": {"type": "integer"},
            "page_start": {"type": "integer"},
            "page_end": {"type": "integer"},
            "document_type": {"type": "string"},
            "title": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["operation", "report_ids"],
    },
)
async def update_report_units(
    ctx: ToolContext,
    operation: str,
    report_ids: list[str],
    split_at_page: int | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    document_type: str | None = None,
    title: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    units = load_report_map(ctx.paths)
    by_id = {u.report_id: u for u in units}
    missing = [rid for rid in report_ids if rid not in by_id]
    if missing:
        return {"error": f"unknown reports: {missing}"}

    created: list[str] = []
    if operation == "split":
        unit = by_id[report_ids[0]]
        if split_at_page is None or not (unit.page_start < split_at_page <= unit.page_end):
            return {"error": f"split_at_page must be within ({unit.page_start}, {unit.page_end}]"}
        number = _next_number(units)
        first = _new_unit(number, unit.document_id, unit.page_start, split_at_page - 1, unit,
                          reason or f"split from {unit.report_id}")
        second = _new_unit(number + 1, unit.document_id, split_at_page, unit.page_end, unit,
                           reason or f"split from {unit.report_id}")
        unit.status = "superseded"
        assemble_report_text(ctx.paths, first)
        assemble_report_text(ctx.paths, second)
        units.extend([first, second])
        created = [first.report_id, second.report_id]
        _invalidate_reader_results(ctx, [unit.report_id])
    elif operation == "merge":
        targets = [by_id[rid] for rid in report_ids]
        documents = {u.document_id for u in targets}
        if len(documents) != 1:
            return {"error": "merge requires units from one document"}
        targets.sort(key=lambda u: u.page_start)
        merged = _new_unit(
            _next_number(units), targets[0].document_id,
            targets[0].page_start, targets[-1].page_end, targets[0],
            reason or f"merged {', '.join(report_ids)}",
        )
        for unit in targets:
            unit.status = "superseded"
        assemble_report_text(ctx.paths, merged)
        units.append(merged)
        created = [merged.report_id]
        _invalidate_reader_results(ctx, report_ids)
    elif operation == "resize":
        unit = by_id[report_ids[0]]
        if page_start is None or page_end is None or page_start > page_end:
            return {"error": "resize requires valid page_start and page_end"}
        unit.page_start, unit.page_end = page_start, page_end
        unit.page_ids = [f"{unit.document_id}:p_{n:04d}" for n in range(page_start, page_end + 1)]
        unit.boundary_reason = reason or unit.boundary_reason
        assemble_report_text(ctx.paths, unit)
        _invalidate_reader_results(ctx, [unit.report_id])
    elif operation == "relabel":
        unit = by_id[report_ids[0]]
        if document_type:
            unit.document_type = document_type
        if title is not None:
            unit.title = title
    elif operation == "mark_uncertain":
        for rid in report_ids:
            by_id[rid].boundary_confidence = "low"
            if "uncertain_boundary" not in by_id[rid].flags:
                by_id[rid].flags.append("uncertain_boundary")
    else:
        return {"error": f"unknown operation: {operation}"}

    write_map(ctx.paths, units)
    log_action(ctx.paths, actor="tools", action="update_report_units",
               targets=report_ids, reason=reason or operation,
               result={"operation": operation, "created": created})
    return {"operation": operation, "created": created, "superseded": report_ids if created else []}
