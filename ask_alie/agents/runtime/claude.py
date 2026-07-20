"""Claude Agent SDK adapter: MCP server + AgentDefinitions generated from the
neutral registries, and the live orchestrator session (Spec §22).

Everything here is generated from ToolSpec/AgentSpec — the business logic
never touches the SDK. The live session path is exercised in Phase L.
"""

from __future__ import annotations

import json
from typing import Any

from ask_alie.agents.runtime.base import DEFAULT_LIMITS, ProgressFn, RunResult
from ask_alie.agents.specs import AGENT_SPECS, load_prompt
from ask_alie.tools.registry import ToolContext, ToolSpec, all_tools
from ask_alie.workspace.runlog import log_action

MCP_SERVER_NAME = "ask_alie"

ORCHESTRATOR_KICKOFF = """
Build the chronology for the case in this working directory.

Start by inspecting the case state. Use the Scout when report units do not
exist. Dispatch readers after the report map is usable. Review the results,
run a gap review, perform targeted follow-up work, curate the candidates and
finish the case.
"""


def mcp_tool_name(name: str) -> str:
    return f"mcp__{MCP_SERVER_NAME}__{name}"


def allowed_tool_names() -> list[str]:
    return ["Agent"] + [mcp_tool_name(name) for name in sorted(all_tools())]


def _wrap_tool(spec: ToolSpec, ctx: ToolContext, sdk_tool: Any) -> Any:
    @sdk_tool(spec.name, spec.description, spec.params_schema)
    async def handler(args: dict[str, Any], _spec: ToolSpec = spec) -> dict[str, Any]:
        result = await _spec.fn(ctx, **(args or {}))
        return {
            "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            "structuredContent": result,
        }

    return handler


def build_mcp_server(ctx: ToolContext) -> Any:
    from claude_agent_sdk import create_sdk_mcp_server, tool as sdk_tool

    wrapped = [_wrap_tool(spec, ctx, sdk_tool) for spec in all_tools().values()]
    return create_sdk_mcp_server(name=MCP_SERVER_NAME, version="0.1.0", tools=wrapped)


def build_agent_definitions() -> dict[str, Any]:
    from claude_agent_sdk import AgentDefinition

    return {
        spec.name: AgentDefinition(
            description=spec.description,
            prompt=load_prompt(spec.prompt_file),
            tools=[mcp_tool_name(name) for name in spec.tool_names],
            model=spec.model,
        )
        for spec in AGENT_SPECS.values()
    }


class ClaudeRuntime:
    name = "claude"

    async def run_orchestration(
        self,
        ctx: ToolContext,
        limits: dict[str, Any] | None = None,
        progress: ProgressFn = lambda _line: None,
    ) -> RunResult:
        # Auth: API key when set, otherwise the user's Claude subscription login.
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

        limits = {**DEFAULT_LIMITS, **(limits or {})}
        options = ClaudeAgentOptions(
            cwd=str(ctx.paths.root),
            system_prompt=load_prompt("orchestrator.md"),
            allowed_tools=allowed_tool_names(),
            mcp_servers={MCP_SERVER_NAME: build_mcp_server(ctx)},
            agents=build_agent_definitions(),
            max_turns=int(limits["max_turns"]),
        )

        detail: dict[str, Any] = {"messages": 0}
        result_text = None
        session_id = None
        async for message in query(prompt=ORCHESTRATOR_KICKOFF, options=options):
            detail["messages"] += 1
            session_id = getattr(message, "session_id", session_id)
            progress(type(message).__name__)
            if isinstance(message, ResultMessage):
                result_text = message.result
                detail["total_cost_usd"] = getattr(message, "total_cost_usd", None)

        detail["session_id"] = session_id
        detail["result"] = (result_text or "")[:2000]
        (ctx.paths.logs_dir / "session.json").write_text(
            json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log_action(ctx.paths, actor="orchestrator", action="run_orchestration",
                   result={"runtime": self.name, "messages": detail["messages"]})
        return RunResult(status="finished", runtime=self.name, detail=detail)
