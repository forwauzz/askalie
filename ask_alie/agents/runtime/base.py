"""AgentRuntime protocol (PLAN §3): the only SDK-shaped seam."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from ask_alie.serialization import AlieModel
from ask_alie.tools.registry import ToolContext

ProgressFn = Callable[[str], None]

DEFAULT_LIMITS: dict[str, Any] = {
    "max_turns": 60,  # Spec §15.4
    "max_gap_iterations": 2,
    "max_reader_passes": 3,
    "max_concurrency": 5,
}


class RunResult(AlieModel):
    status: str  # finished | failed | stopped
    runtime: str = ""
    detail: dict = {}


class AgentRuntime(Protocol):
    name: str

    async def run_orchestration(
        self,
        ctx: ToolContext,
        limits: dict[str, Any],
        progress: ProgressFn,
    ) -> RunResult: ...
