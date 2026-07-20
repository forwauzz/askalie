"""Rule-based identifier recognition (PLAN §2: regex-first, no spaCy/Presidio).

Pattern recognizers cover structured identifiers (RAMQ, phone, email, postal
code, labeled claim numbers). Names, facilities and employers come from a
per-case known-entities dictionary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_RAMQ = re.compile(r"\b[A-Z]{4}\s?\d{4}\s?\d{4}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_PHONE = re.compile(r"(?:\(\d{3}\)\s?|\b\d{3}[\s.-])\d{3}[\s.-]\d{4}\b")
_POSTAL = re.compile(r"\b[A-Za-z]\d[A-Za-z]\s?\d[A-Za-z]\d\b")
_CLAIM = re.compile(r"(?i)\b(?:dossier|réclamation|reclamation|claim)\b[^\n\d]{0,25}(\d{6,10})\b")

_DICTIONARY_CATEGORIES = {
    "persons": "PERSON",
    "providers": "PROVIDER",
    "facilities": "FACILITY",
    "employers": "EMPLOYER",
    "addresses": "ADDRESS",
}


@dataclass(frozen=True)
class EntityMatch:
    category: str
    value: str
    start_char: int
    end_char: int


def find_entities(text: str, known_entities: dict[str, list[str]] | None = None) -> list[EntityMatch]:
    matches: list[EntityMatch] = []

    for pattern, category in ((_EMAIL, "EMAIL"), (_RAMQ, "RAMQ"), (_PHONE, "PHONE"), (_POSTAL, "POSTAL")):
        for match in pattern.finditer(text):
            matches.append(EntityMatch(category, match.group(0), match.start(), match.end()))

    for match in _CLAIM.finditer(text):
        matches.append(EntityMatch("CLAIM", match.group(1), match.start(1), match.end(1)))

    for key, category in _DICTIONARY_CATEGORIES.items():
        for value in (known_entities or {}).get(key, []):
            for match in re.finditer(re.escape(value), text, re.IGNORECASE):
                matches.append(EntityMatch(category, value, match.start(), match.end()))

    # drop overlaps, earliest-longest wins
    matches.sort(key=lambda m: (m.start_char, -(m.end_char - m.start_char)))
    result: list[EntityMatch] = []
    consumed = -1
    for match in matches:
        if match.start_char > consumed:
            result.append(match)
            consumed = match.end_char - 1
    return result
