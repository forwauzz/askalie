"""Provider-neutral tool registry (PLAN §3).

Every case tool is a plain async function taking a ToolContext plus keyword
arguments and returning a concise JSON-serializable dict. SDK adapters (Claude
MCP server, later OpenAI function tools) are GENERATED from these specs; no
tool implementation imports an SDK.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ask_alie.llm.client import ModelClient
from ask_alie.workspace.paths import CasePaths

ToolFn = Callable[..., Awaitable[dict[str, Any]]]


@dataclass
class ToolContext:
    paths: CasePaths
    client: ModelClient | None = None  # required by dispatch_readers / run_curator


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    params_schema: dict[str, Any] = field(default_factory=dict)
    fn: ToolFn = None  # type: ignore[assignment]


TOOLS: dict[str, ToolSpec] = {}


def tool(name: str, description: str, params_schema: dict[str, Any] | None = None):
    def decorator(fn: ToolFn) -> ToolFn:
        TOOLS[name] = ToolSpec(
            name=name,
            description=description,
            params_schema=params_schema or {"type": "object", "properties": {}},
            fn=fn,
        )
        return fn

    return decorator


def get_tool(name: str) -> ToolSpec:
    _ensure_loaded()
    return TOOLS[name]


def all_tools() -> dict[str, ToolSpec]:
    _ensure_loaded()
    return dict(TOOLS)


def _ensure_loaded() -> None:
    """Import tool modules so their @tool decorators register."""
    from ask_alie.tools import (  # noqa: F401
        case_state,
        curation,
        documents,
        readers,
        reports,
        search,
        tasks,
    )
