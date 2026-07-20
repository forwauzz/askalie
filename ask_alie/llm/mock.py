"""Deterministic heuristic mocks for offline end-to-end runs (PLAN §3).

HeuristicReaderMock builds a plausible ReaderResult from the report safe text
itself: one event per unique date token, quoting the line it appears on.
ScriptedCaseMock extends that to Scout, Gap and Curator schemas so the full
orchestration can run without a model or network.
"""

from __future__ import annotations

import json
import re

from ask_alie.agents.schemas import GapResult, GapTaskDraft, ScoutResult, ScoutUnit
from ask_alie.curation.service import CuratorAssignmentDraft, CuratorResult
from ask_alie.readers.schema import ReaderEventDraft, ReaderResult
from ask_alie.serialization import AlieModel

_REPORT_ID = re.compile(r"Report ID: (report_\d+)")
_PAGE_MARKER = re.compile(r"=== (\w+) page (\d+) ===")
_DATE_TOKEN = re.compile(r"\[\[DATE_[A-Z0-9]+\]\]")


class HeuristicReaderMock:
    name = "heuristic-mock"

    async def structured(
        self,
        prompt: str,
        schema: type[AlieModel],
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> AlieModel:
        if schema is not ReaderResult:
            raise TypeError(f"HeuristicReaderMock only supports ReaderResult, got {schema}")

        match = _REPORT_ID.search(prompt)
        report_id = match.group(1) if match else "report_0000"

        events: list[ReaderEventDraft] = []
        seen_tokens: set[str] = set()
        current_page = 1
        for line in prompt.splitlines():
            marker = _PAGE_MARKER.match(line.strip())
            if marker:
                current_page = int(marker.group(2))
                continue
            for token in _DATE_TOKEN.findall(line):
                if token in seen_tokens:
                    continue
                seen_tokens.add(token)
                events.append(
                    ReaderEventDraft(
                        event_date_token=token,
                        event_type="unknown",
                        summary_fr=f"Événement daté {token} extrait du rapport (mock).",
                        source_pages=[current_page],
                        quote=line.strip()[:160],
                        quote_page=current_page,
                        reader_confidence="medium",
                    )
                )

        return ReaderResult(
            report_id=report_id,
            events=events,
            report_summary=f"Résumé mock du rapport {report_id} ({len(events)} événement(s)).",
        )


def _payload_after(prompt: str, marker: str) -> list | dict:
    return json.loads(prompt.split(marker, 1)[1])


class ScriptedCaseMock:
    """Deterministic full-case mock: routes by schema, no model involved."""

    name = "scripted-mock"

    def __init__(self) -> None:
        self._reader = HeuristicReaderMock()
        self._gap_rounds = 0

    async def structured(
        self,
        prompt: str,
        schema: type[AlieModel],
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> AlieModel:
        if schema is ReaderResult:
            return await self._reader.structured(prompt, schema)
        if schema is ScoutResult:
            return self._scout(prompt)
        if schema is GapResult:
            return self._gap(prompt)
        if schema is CuratorResult:
            return self._curate(prompt)
        raise TypeError(f"ScriptedCaseMock does not support schema {schema}")

    def _scout(self, prompt: str) -> ScoutResult:
        document_id = re.search(r"Document: (\w+)", prompt).group(1)
        packet = _payload_after(prompt, "(JSON):\n")
        units: list[ScoutUnit] = []
        run_start: int | None = None
        run_empty = False

        def close_run(end_page: int) -> None:
            nonlocal run_start
            if run_start is None:
                return
            units.append(
                ScoutUnit(
                    page_start=run_start,
                    page_end=end_page,
                    document_type="empty" if run_empty else "report",
                    title="Pages vides" if run_empty else "Rapport",
                    confidence="medium",
                    reason="scripted mock grouping",
                )
            )
            run_start = None

        previous_page = 0
        for entry in packet:
            page, empty = entry["page"], not entry.get("head", "").strip()
            if run_start is None:
                run_start, run_empty = page, empty
            elif empty != run_empty:
                close_run(previous_page)
                run_start, run_empty = page, empty
            previous_page = page
        close_run(previous_page)
        return ScoutResult(document_id=document_id, proposed_units=units)

    def _gap(self, prompt: str) -> GapResult:
        self._gap_rounds += 1
        if self._gap_rounds > 1:
            return GapResult(assessment="No further gaps identified (scripted mock).")
        facts = _payload_after(prompt, "(JSON facts):\n")
        readable = [
            r for r in facts["reports"] if r["read"] and r["date_tokens_in_text"] > 0
        ]
        if not readable:
            return GapResult(assessment="Nothing readable to re-check (scripted mock).")
        richest = max(readable, key=lambda r: r["date_tokens_in_text"])
        return GapResult(
            tasks=[
                GapTaskDraft(
                    action="reread_report",
                    target_ids=[richest["report_id"]],
                    priority="high",
                    reason="scripted mock: densest report re-checked once",
                    instructions="Re-read for work-status changes and treatment dates.",
                )
            ],
            assessment="One targeted re-read proposed (scripted mock).",
        )

    def _curate(self, prompt: str) -> CuratorResult:
        candidates = _payload_after(prompt, "Candidates (JSON):\n")
        assignments = [
            CuratorAssignmentDraft(
                event_id=item["event_id"],
                queue="secondary"
                if any(str(f).startswith("duplicate_of:") for f in item.get("flags", []))
                else "default",
                reason="scripted mock assignment",
            )
            for item in candidates
        ]
        return CuratorResult(assignments=assignments)
