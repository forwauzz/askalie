"""Table-driven date detection tests (PLAN P3.1: ≥25 formats)."""

import pytest

from ask_alie.privacy.dates import find_dates

CASES = [
    # French textual
    ("Consultation du 16 juillet 2025 à la clinique.", "2025-07-16", "high"),
    ("le 1er mars 2024", "2024-03-01", "high"),
    ("le premier mars 2024", "2024-03-01", "high"),
    ("le 3 février 2025", "2025-02-03", "high"),
    ("le 3 fevrier 2025 (sans accent)", "2025-02-03", "high"),
    ("le 12 août 2023", "2023-08-12", "high"),
    ("le 12 aout 2023", "2023-08-12", "high"),
    ("le 28 décembre 2022", "2022-12-28", "high"),
    ("examen du 5 janv. 2025", "2025-01-05", "high"),
    ("visite du 9 sept. 2024", "2024-09-09", "high"),
    ("le 30 juil. 2025", "2025-07-30", "high"),
    # English textual
    ("seen on July 16, 2025 by the physician", "2025-07-16", "high"),
    ("on 16 July 2025 the worker", "2025-07-16", "high"),
    ("March 3rd, 2025 initial injury", "2025-03-03", "high"),
    ("assessment of Feb 2, 2024", "2024-02-02", "high"),
    # ISO / ymd
    ("2025-07-16", "2025-07-16", "high"),
    ("2025/07/16", "2025-07-16", "high"),
    ("2024-01-05 08:30", "2024-01-05", "high"),
    # dmy numeric
    ("le 16/07/2025", "2025-07-16", "high"),
    ("le 16-07-2025", "2025-07-16", "high"),
    ("le 16.07.2025", "2025-07-16", "high"),
    ("reçu le 28/02/2023", "2023-02-28", "high"),
    # ambiguous numeric → dd/mm assumption, medium confidence
    ("le 03/04/2025", "2025-04-03", "medium"),
    ("le 05/01/2024", "2024-01-05", "medium"),
    # mm/dd style (second > 12)
    ("on 07/16/2025", "2025-07-16", "medium"),
]


@pytest.mark.parametrize(("text", "expected", "confidence"), CASES)
def test_detects_and_normalizes(text: str, expected: str, confidence: str) -> None:
    matches = find_dates(text)
    assert len(matches) == 1, f"expected 1 match in {text!r}, got {matches}"
    assert matches[0].normalized == expected
    assert matches[0].confidence == confidence


NEGATIVE = [
    "le 32 juillet 2025",  # invalid day
    "le 30 février 2025",  # invalid date
    "l6 juillet 2O25",  # OCR-mangled: must miss, never mis-normalize
    "version 2.10.3 du logiciel",  # not a date
    "NAM TREJ 8001 0512",  # RAMQ digits
    "réclamation numéro 123456789",
]


@pytest.mark.parametrize("text", NEGATIVE)
def test_never_wrongly_normalizes(text: str) -> None:
    assert find_dates(text) == []


def test_multiple_dates_with_offsets() -> None:
    text = "Accident du 3 mars 2025. Consultation le 16 juillet 2025."
    matches = find_dates(text)
    assert [m.normalized for m in matches] == ["2025-03-03", "2025-07-16"]
    for match in matches:
        assert text[match.start_char : match.end_char] == match.raw_text
