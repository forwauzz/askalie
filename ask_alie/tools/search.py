"""search_case tool: plain-text/regex search over safe page text (Spec §21.1)."""

from __future__ import annotations

import re
from typing import Any

from ask_alie.tools.registry import ToolContext, tool


@tool(
    "search_case",
    "Search the case's safe page text for a phrase or regex; returns matching lines with page ids.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "regex": {"type": "boolean"},
            "max_results": {"type": "integer"},
        },
        "required": ["query"],
    },
)
async def search_case(
    ctx: ToolContext, query: str, regex: bool = False, max_results: int = 20
) -> dict[str, Any]:
    try:
        pattern = re.compile(query if regex else re.escape(query), re.IGNORECASE)
    except re.error as exc:
        return {"error": f"invalid regex: {exc}"}

    results: list[dict[str, Any]] = []
    for safe_path in sorted(ctx.paths.pages_dir.rglob("*.safe.txt")):
        document_id = safe_path.parent.name
        page_number = int(safe_path.stem.split("_")[1].split(".")[0])
        for line_number, line in enumerate(
            safe_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if pattern.search(line):
                results.append(
                    {
                        "page_id": f"{document_id}:p_{page_number:04d}",
                        "line": line_number,
                        "text": line.strip()[:200],
                    }
                )
                if len(results) >= max_results:
                    return {"query": query, "truncated": True, "results": results}
    return {"query": query, "truncated": False, "results": results}
