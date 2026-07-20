"""Absolute-date detection for French and English page text (Spec §13.2).

Only absolute calendar dates are matched. OCR-mangled dates are allowed to
miss; they must never normalize to a wrong value.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_MONTHS: dict[str, int] = {}
for i, names in enumerate(
    [
        ("janvier", "janv", "january", "jan"),
        ("février", "fevrier", "févr", "fevr", "february", "feb"),
        ("mars", "march", "mar"),
        ("avril", "avr", "april", "apr"),
        ("mai", "may"),
        ("juin", "june", "jun"),
        ("juillet", "juil", "july", "jul"),
        ("août", "aout", "august", "aug"),
        ("septembre", "sept", "september", "sep"),
        ("octobre", "oct", "october"),
        ("novembre", "nov", "november"),
        ("décembre", "decembre", "déc", "dec", "december"),
    ],
    start=1,
):
    for name in names:
        _MONTHS[name] = i

_TEXTUAL = re.compile(r"\b(\d{1,2}|1er|premier)\s+([A-Za-zÀ-ÿ]+)\.?\s+(\d{4})\b", re.IGNORECASE)
_ENGLISH = re.compile(r"\b([A-Za-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.IGNORECASE)
_YMD = re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b")
_DMY = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b")


@dataclass(frozen=True)
class DateMatch:
    raw_text: str
    normalized: str  # ISO yyyy-mm-dd
    start_char: int
    end_char: int
    confidence: str  # high | medium


def _valid(year: int, month: int, day: int) -> str | None:
    if not (1900 <= year <= 2100):
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _day_number(raw: str) -> int | None:
    lowered = raw.lower()
    if lowered in ("1er", "premier"):
        return 1
    return int(raw) if raw.isdigit() else None


def find_dates(text: str) -> list[DateMatch]:
    candidates: list[DateMatch] = []

    for match in _TEXTUAL.finditer(text):
        day = _day_number(match.group(1))
        month = _MONTHS.get(match.group(2).lower().rstrip("."))
        if day is None or month is None:
            continue
        normalized = _valid(int(match.group(3)), month, day)
        if normalized:
            candidates.append(
                DateMatch(match.group(0), normalized, match.start(), match.end(), "high")
            )

    for match in _ENGLISH.finditer(text):
        month = _MONTHS.get(match.group(1).lower().rstrip("."))
        if month is None:
            continue
        normalized = _valid(int(match.group(3)), month, int(match.group(2)))
        if normalized:
            candidates.append(
                DateMatch(match.group(0), normalized, match.start(), match.end(), "high")
            )

    for match in _YMD.finditer(text):
        normalized = _valid(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if normalized:
            candidates.append(
                DateMatch(match.group(0), normalized, match.start(), match.end(), "high")
            )

    for match in _DMY.finditer(text):
        first, second, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if first > 12:  # unambiguous dd/mm
            day, month, confidence = first, second, "high"
        elif second > 12:  # mm/dd style
            day, month, confidence = second, first, "medium"
        else:  # ambiguous: assume dd/mm (Québec convention)
            day, month, confidence = first, second, "medium"
        normalized = _valid(year, month, day)
        if normalized:
            candidates.append(
                DateMatch(match.group(0), normalized, match.start(), match.end(), confidence)
            )

    # drop overlapping matches, earliest-longest wins
    candidates.sort(key=lambda m: (m.start_char, -(m.end_char - m.start_char)))
    result: list[DateMatch] = []
    consumed = -1
    for candidate in candidates:
        if candidate.start_char > consumed:
            result.append(candidate)
            consumed = candidate.end_char - 1
    return result
