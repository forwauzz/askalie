"""Single reader execution with the Spec §34 retry ladder."""

from __future__ import annotations

from pathlib import Path

from ask_alie.llm.client import ModelClient
from ask_alie.readers.schema import ReaderResult
from ask_alie.reports.models import ReportUnit

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "agents" / "prompts"


class ReaderFailure(RuntimeError):
    def __init__(self, report_id: str, message: str, attempts: int):
        super().__init__(message)
        self.report_id = report_id
        self.attempts = attempts


def reader_system_prompt(document_type: str | None = None) -> str:
    base = (_PROMPTS_DIR / "reader.md").read_text(encoding="utf-8")
    from ask_alie import config
    from ask_alie.agents.skills import skills_for

    if config.skills_enabled():
        for skill in skills_for(document_type):
            base += f"\n\n## Skill: {skill.name}\n\n{skill.body}\n"
    return base


def build_reader_prompt(
    unit: ReportUnit, report_text: str, instructions: str | None, simplified: bool = False
) -> str:
    parts = [f"Report ID: {unit.report_id}"]
    if simplified:
        parts.append(
            "Extract the dated chronology events from this report as JSON matching "
            "the schema. Keep summaries short. Use only date tokens present in the text."
        )
    else:
        parts.append(f"Document type hint: {unit.document_type or 'unknown'}")
        if instructions:
            parts.append(f"Targeted instructions:\n{instructions}")
    parts.append("Report text:\n" + report_text)
    return "\n\n".join(parts)


async def run_reader(
    client: ModelClient,
    unit: ReportUnit,
    report_text: str,
    instructions: str | None = None,
) -> tuple[ReaderResult, int]:
    """Run one reader. Retry once, then once more with a simpler prompt (Spec §34).

    Returns (result, attempts). Raises ReaderFailure after three failed attempts.
    """
    system = reader_system_prompt(unit.document_type)
    last_error: Exception | None = None
    for attempt in range(1, 4):
        simplified = attempt == 3
        prompt = build_reader_prompt(unit, report_text, instructions, simplified=simplified)
        try:
            from ask_alie import config

            result = await client.structured(
                prompt, ReaderResult, system=system, model=config.reader_model()
            )
            result.report_id = unit.report_id  # authoritative, never model-chosen
            return result, attempt
        except Exception as exc:  # noqa: BLE001 - every failure enters the retry ladder
            last_error = exc
    raise ReaderFailure(unit.report_id, str(last_error), attempts=3)
