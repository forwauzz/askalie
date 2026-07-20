from ask_alie.ingest.quality import score_text
from tests.fixtures.make_fixtures import CONSULTATION_P1, DECISION_P2, GARBAGE_TEXT, IMAGING_P1


def test_french_clinical_text_is_usable() -> None:
    for text in (CONSULTATION_P1, IMAGING_P1, DECISION_P2):
        result = score_text(text)
        assert result.usable, result.signals
        assert result.score > 0.5


def test_blank_and_short_text_fail() -> None:
    assert not score_text("").usable
    assert not score_text("Page 3\n").usable
    assert score_text("").signals["reason"] == "too_short"


def test_garbage_text_fails_on_alphabetic_ratio() -> None:
    result = score_text(GARBAGE_TEXT)
    assert not result.usable
    assert "alphabetic" in result.signals["failed_checks"]
