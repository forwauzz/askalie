"""Duplicate linking: candidates are linked, never deleted (Spec §5.3, §34)."""

from __future__ import annotations

import re

from ask_alie.events.models import CandidateEvent

_WORD = re.compile(r"[a-zà-ÿ]{3,}", re.IGNORECASE)
_SIMILARITY_THRESHOLD = 0.6


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)}


def _similar(a: CandidateEvent, b: CandidateEvent) -> bool:
    wa, wb = _words(a.summary_fr), _words(b.summary_fr)
    if not wa or not wb:
        return False
    jaccard = len(wa & wb) / len(wa | wb)
    return jaccard >= _SIMILARITY_THRESHOLD


def link_duplicates(events: list[CandidateEvent]) -> dict[str, str]:
    """Return {duplicate_event_id: original_event_id} for same-date similar events.

    Marks duplicates with a flag; nothing is removed.
    """
    links: dict[str, str] = {}
    by_date: dict[str, list[CandidateEvent]] = {}
    for event in events:
        by_date.setdefault(event.event_date_token, []).append(event)

    for group in by_date.values():
        for i, later in enumerate(group):
            if later.event_id in links:
                continue
            for earlier in group[:i]:
                if earlier.event_id in links:
                    continue
                if _similar(earlier, later):
                    links[later.event_id] = earlier.event_id
                    flag = f"duplicate_of:{earlier.event_id}"
                    if flag not in later.flags:
                        later.flags.append(flag)
                    break
    return links
