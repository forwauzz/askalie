"""Restore real dates from tokens after extraction (Spec §13.4).

Unresolvable tokens preserve the event and flag it — never drop it.
"""

from __future__ import annotations

from ask_alie.events.models import CandidateEvent
from ask_alie.privacy.registry import DateRegistry

DATE_UNRESOLVED_FLAG = "date_unresolved"


def restore_event_dates(events: list[CandidateEvent], registry: DateRegistry) -> list[CandidateEvent]:
    for event in events:
        normalized = registry.resolve(event.event_date_token)
        if normalized:
            event.event_date = normalized
        elif DATE_UNRESOLVED_FLAG not in event.flags:
            event.flags.append(DATE_UNRESOLVED_FLAG)
    return events
