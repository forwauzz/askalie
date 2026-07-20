"""Provider portability guard (PLAN §2): SDK imports stay behind the seams."""

import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2] / "ask_alie"
ALLOWED = {PACKAGE / "llm", PACKAGE / "agents" / "runtime"}
SDK_IMPORT = re.compile(r"^\s*(?:from|import)\s+(claude_agent_sdk|openai)\b", re.MULTILINE)


def test_no_sdk_imports_outside_seams() -> None:
    offenders: list[str] = []
    for path in PACKAGE.rglob("*.py"):
        if any(allowed in path.parents for allowed in ALLOWED):
            continue
        if SDK_IMPORT.search(path.read_text(encoding="utf-8")):
            offenders.append(str(path.relative_to(PACKAGE)))
    assert not offenders, f"SDK imports outside ask_alie/llm and ask_alie/agents/runtime: {offenders}"
