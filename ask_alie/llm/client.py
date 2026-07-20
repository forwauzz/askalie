"""Provider-neutral model access seam (PLAN §3).

Everything outside ask_alie/llm/ and ask_alie/agents/runtime/ talks to models
exclusively through ModelClient. Implementations may import SDKs; callers may not.
"""

from __future__ import annotations

import inspect
import json
from typing import Any, Protocol, TypeVar

from ask_alie.serialization import AlieModel

T = TypeVar("T", bound=AlieModel)


class ModelClient(Protocol):
    name: str

    async def structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> T: ...


class MockModelClient:
    """Deterministic test client: a handler produces (or raises) per call."""

    name = "mock"

    def __init__(self, handler: Any):
        self.handler = handler
        self.calls: list[str] = []

    async def structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> T:
        self.calls.append(prompt)
        result = self.handler(prompt, schema)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)


class ClaudeModelClient:
    """Live single-shot structured call via claude-agent-sdk.

    Only request assembly is unit-tested; the network path runs in Phase L.
    """

    name = "claude"

    def __init__(self, model: str | None = None):
        self.model = model

    @staticmethod
    def build_structured_request(
        prompt: str, schema: type[AlieModel], system: str | None = None
    ) -> dict[str, Any]:
        return {
            "prompt": prompt,
            "system_prompt": system,
            "output_format": {"type": "json_schema", "schema": schema.model_json_schema()},
        }

    async def structured(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> T:
        from ask_alie import config

        if not config.anthropic_api_key():
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set - copy .env.example to .env "
                "(see NEEDS_FROM_USER.md)"
            )
        from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query  # lazy

        request = self.build_structured_request(prompt, schema, system)
        options = ClaudeAgentOptions(
            system_prompt=request["system_prompt"],
            model=model or self.model,
            max_turns=1,
            allowed_tools=[],
        )
        result_text: str | None = None
        async for message in query(prompt=request["prompt"], options=options):
            if isinstance(message, ResultMessage):
                result_text = message.result
        if result_text is None:
            raise RuntimeError("Model returned no result message")
        payload = _extract_json(result_text)
        return schema.model_validate(payload)


def sdk_available() -> tuple[bool, str]:
    """Report whether claude-agent-sdk imports (used by doctor)."""
    try:
        import claude_agent_sdk  # noqa: F401

        return True, "ok"
    except ImportError as exc:
        return False, str(exc)


def _extract_json(text: str) -> Any:
    """Parse a JSON object from model output, tolerating code fences."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```")[1]
        if stripped.startswith("json"):
            stripped = stripped[4:]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in model output: {text[:200]!r}")
    return json.loads(stripped[start : end + 1])
