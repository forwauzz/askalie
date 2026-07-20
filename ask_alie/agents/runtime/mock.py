"""MockRuntime: scripted deterministic orchestration through the real tool layer.

Same phases the live orchestrator performs (scout → readers → gap → follow-ups
→ curator → finish), with control flow in code instead of a model. Used by
tests and `run --mock`.
"""

from __future__ import annotations

from typing import Any

from ask_alie.agents.gap import execute_tasks, run_gap_review
from ask_alie.agents.runtime.base import DEFAULT_LIMITS, ProgressFn, RunResult
from ask_alie.agents.scout import run_scout
from ask_alie.reports.map import load_report_map
from ask_alie.tools.registry import ToolContext, get_tool


class MockRuntime:
    name = "mock"

    async def run_orchestration(
        self,
        ctx: ToolContext,
        limits: dict[str, Any] | None = None,
        progress: ProgressFn = lambda _line: None,
    ) -> RunResult:
        from ask_alie.llm.mock import ScriptedCaseMock

        limits = {**DEFAULT_LIMITS, **(limits or {})}
        if ctx.client is None:
            ctx.client = ScriptedCaseMock()
        client = ctx.client
        detail: dict[str, Any] = {}

        progress("Scout: proposing report units")
        detail["scout"] = await run_scout(ctx, client)

        report_ids = [
            u.report_id for u in load_report_map(ctx.paths) if u.status != "superseded"
        ]
        progress(f"Dispatching {len(report_ids)} readers")
        detail["dispatch"] = await get_tool("dispatch_readers").fn(
            ctx, report_ids=report_ids, max_concurrency=limits["max_concurrency"]
        )

        detail["gap_iterations"] = []
        for iteration in range(int(limits["max_gap_iterations"])):
            progress(f"Gap review (iteration {iteration + 1})")
            review = await run_gap_review(ctx, client)
            if not review["tasks_created"]:
                detail["gap_iterations"].append({"tasks_created": 0})
                break
            executed = await execute_tasks(ctx, int(limits["max_reader_passes"]))
            detail["gap_iterations"].append(
                {"tasks_created": len(review["tasks_created"]), **executed}
            )

        progress("Curation")
        detail["curation"] = await get_tool("run_curator").fn(ctx)

        progress("Finishing case")
        detail["finish"] = await get_tool("finish_case").fn(ctx)
        return RunResult(status="finished", runtime=self.name, detail=detail)
