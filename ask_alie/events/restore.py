"""Restore real dates from tokens after extraction (Spec §13.4).

Readers occasionally return the token without brackets, or a literal date
string they saw in the text. Restoration is forgiving about format but never
guesses: partial dates (no year, no day) stay unresolved and flagged.
"""

from __future__ import annotations

import re

from ask_alie.events.models import CandidateEvent
from ask_alie.privacy.dates import find_dates
from ask_alie.privacy.registry import DateRegistry

DATE_UNRESOLVED_FLAG = "date_unresolved"
DATE_DIRECT_FLAG = "date_literal"

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_BARE_TOKEN = re.compile(r"^DATE_[0-9A-F]{4,10}$")


def _resolve_token(token: str, registry: DateRegistry) -> tuple[str | None, str | None]:
    """Return (normalized_date, extra_flag) for a reader-provided token."""
    candidate = token.strip()
    normalized = registry.resolve(candidate)
    if normalized:
        return normalized, None
    if _BARE_TOKEN.fullmatch(candidate):
        normalized = registry.resolve(f"[[{candidate}]]")
        if normalized:
            return normalized, None
    if _ISO.fullmatch(candidate):
        return candidate, DATE_DIRECT_FLAG
    # a literal absolute date string ("16 juillet 2025") parses unambiguously
    matches = find_dates(candidate)
    if len(matches) == 1 and matches[0].raw_text.strip() == candidate:
        return matches[0].normalized, DATE_DIRECT_FLAG
    return None, None


def restore_event_dates(events: list[CandidateEvent], registry: DateRegistry) -> list[CandidateEvent]:
    for event in events:
        normalized, extra_flag = _resolve_token(event.event_date_token, registry)
        if normalized:
            event.event_date = normalized
            if extra_flag and extra_flag not in event.flags:
                event.flags.append(extra_flag)
            if DATE_UNRESOLVED_FLAG in event.flags:
                event.flags.remove(DATE_UNRESOLVED_FLAG)
        elif DATE_UNRESOLVED_FLAG not in event.flags:
            event.flags.append(DATE_UNRESOLVED_FLAG)
    return events
