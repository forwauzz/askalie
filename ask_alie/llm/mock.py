"""Deterministic heuristic reader mock for offline end-to-end runs (PLAN §3).

Builds a plausible ReaderResult from the report safe text itself: one event per
unique date token, quoting the line it appears on. No model, no network.
"""

from __future__ import annotations

import re

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
