"""dispatch_readers tool wrapping the bounded dispatcher (Spec §21.2)."""

from __future__ import annotations

from typing import Any

from ask_alie.readers.dispatcher import dispatch_readers as run_dispatch
from ask_alie.tools.registry import ToolContext, tool


@tool(
    "dispatch_readers",
    "Run report readers in bounded parallel sessions; returns a concise batch summary.",
    {
        "type": "object",
        "properties": {
            "report_ids": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"},
            "instructions": {"type": "string"},
            "max_concurrency": {"type": "integer"},
            "pass_number": {"type": "integer"},
        },
        "required": ["report_ids"],
    },
)
async def dispatch_readers(
    ctx: ToolContext,
    report_ids: list[str],
    reason: str = "initial",
    instructions: str | None = None,
    max_concurrency: int = 5,
    pass_number: int = 1,
) -> dict[str, Any]:
    if ctx.client is None:
        return {"error": "no model client configured for reader dispatch"}
    summary = await run_dispatch(
        ctx.paths,
        ctx.client,
        report_ids,
        reason=reason,
        instructions=instructions,
        max_concurrency=max_concurrency,
        pass_number=pass_number,
    )
    return {
        "submitted": summary.submitted,
        "completed": summary.completed,
        "failed": summary.failed,
        "new_candidate_events": summary.new_candidate_events,
        "result_paths": summary.result_paths,
        "failures": summary.failures,
    }
