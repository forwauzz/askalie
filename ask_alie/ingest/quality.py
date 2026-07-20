"""Page-text quality scoring (Spec §12.3).

Decides whether native-extracted text is usable or the page must be OCR'd.
Combines several signals rather than a bare character-count threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_COMMON_WORDS = frozenset(
    (
        # French
        "le la les de des du et un une pour avec dans sur est sont au aux par il elle "
        "nous vous ne pas ce cette son sa ses que qui a été plus depuis suite date "
        # English
        "the and of to in for with on is are was were this that from by at as it"
    ).split()
)

_MIN_CHARACTERS = 80
_MIN_WORDS = 12
_MIN_PRINTABLE_RATIO = 0.95
_MIN_ALPHABETIC_RATIO = 0.35
_MIN_KNOWN_WORD_RATIO = 0.05


@dataclass(frozen=True)
class QualityScore:
    score: float
    usable: bool
    signals: dict = field(default_factory=dict)


def score_text(text: str) -> QualityScore:
    stripped = text.strip()
    characters = len(stripped)
    if characters < _MIN_CHARACTERS:
        return QualityScore(0.0, False, {"reason": "too_short", "characters": characters})

    printable = sum(ch.isprintable() or ch in "\n\r\t" for ch in stripped)
    printable_ratio = printable / characters
    alphabetic_ratio = sum(ch.isalpha() for ch in stripped) / characters

    words = stripped.split()
    word_count = len(words)
    known_hits = sum(1 for w in words if w.lower().strip(".,;:()'\"«»") in _COMMON_WORDS)
    known_ratio = known_hits / max(word_count, 1)

    checks = {
        "printable": printable_ratio >= _MIN_PRINTABLE_RATIO,
        "alphabetic": alphabetic_ratio >= _MIN_ALPHABETIC_RATIO,
        "word_count": word_count >= _MIN_WORDS,
        "known_words": known_ratio >= _MIN_KNOWN_WORD_RATIO,
    }
    score = round(
        (
            min(printable_ratio, 1.0)
            + min(alphabetic_ratio / 0.5, 1.0)
            + min(word_count / 50, 1.0)
            + min(known_ratio / 0.15, 1.0)
        )
        / 4,
        3,
    )
    return QualityScore(
        score=score,
        usable=all(checks.values()),
        signals={
            "characters": characters,
            "printable_ratio": round(printable_ratio, 3),
            "alphabetic_ratio": round(alphabetic_ratio, 3),
            "word_count": word_count,
            "known_word_ratio": round(known_ratio, 3),
            "failed_checks": [name for name, ok in checks.items() if not ok],
        },
    )
