"""Provider-neutral agent specifications (PLAN §3).

Claude AgentDefinitions (and later OpenAI Agents) are generated from these.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class AgentSpec:
    name: str
    description: str
    prompt_file: str
    tool_names: tuple[str, ...]
    model: str = "sonnet"


AGENT_SPECS: dict[str, AgentSpec] = {
    "scout": AgentSpec(
        name="scout",
        description="Use when the case needs report boundaries proposed, reviewed or corrected.",
        prompt_file="scout.md",
        tool_names=("inspect_document", "read_pages", "save_report_map"),
    ),
    "gap-reviewer": AgentSpec(
        name="gap-reviewer",
        description=(
            "Use after initial report reading to identify probable missing reports "
            "or events and propose targeted follow-up tasks."
        ),
        prompt_file="gap.md",
        tool_names=("get_case_state", "inspect_report", "search_case", "create_tasks"),
    ),
    "curator": AgentSpec(
        name="curator",
        description=(
            "Use when candidate extraction and gap review are complete to assign "
            "default and secondary chronology queues."
        ),
        prompt_file="curator.md",
        tool_names=("list_candidates", "run_curator"),
    ),
}


def load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")
