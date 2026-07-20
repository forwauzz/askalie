import json
from pathlib import Path

from ask_alie.cli import main
from ask_alie.events.models import CandidateEvent
from ask_alie.events.restore import restore_event_dates
from ask_alie.ingest.ocr import NullOcrEngine
from ask_alie.ingest.service import ingest_case
from ask_alie.privacy.tokenize import load_date_registry, tokenize_case
from ask_alie.workspace.paths import CasePaths

KNOWN_ENTITIES = {
    "persons": ["Jean Tremblay"],
    "providers": ["Marie Gagnon", "Paul Lefebvre"],
    "facilities": ["Clinique Médicale Saint-Laurent", "Centre d'Imagerie Fictif de Montréal"],
    "employers": ["Entrepôt Fictif inc."],
    "addresses": ["1234, boulevard Fictif"],
}


def _prepare_case(fixture_pdf_dir: Path, tmp_path: Path, case_id: str) -> CasePaths:
    ingest_case(fixture_pdf_dir, case_id, tmp_path, ocr_engine=NullOcrEngine())
    paths = CasePaths.for_case(tmp_path, case_id)
    (paths.root / "known_entities.json").write_text(
        json.dumps(KNOWN_ENTITIES, ensure_ascii=False), encoding="utf-8"
    )
    return paths


def test_tokenize_case_end_to_end(fixture_pdf_dir: Path, tmp_path: Path) -> None:
    paths = _prepare_case(fixture_pdf_dir, tmp_path, "case_tok")
    summary = tokenize_case(paths.root)
    assert summary.pages_tokenized == 8
    assert summary.date_tokens >= 5  # accident, consult, IRM, decision, RRA, arrêt...

    safe_texts = "\n".join(
        p.read_text(encoding="utf-8") for p in paths.pages_dir.rglob("*.safe.txt")
    )
    # no raw identifiers survive
    for leaked in ("Tremblay", "TREJ", "555-0182", "123456789", "Gagnon", "H2X"):
        assert leaked not in safe_texts, f"identifier leaked: {leaked}"
    # no raw dates survive
    for leaked in ("16 juillet 2025", "3 mars 2025", "5 août 2025"):
        assert leaked not in safe_texts, f"date leaked: {leaked}"
    assert "[[DATE_" in safe_texts and "[[PERSON_01]]" in safe_texts

    # same date on different pages → same token
    registry = load_date_registry(paths)
    accident_tokens = {
        token for token, entry in registry.entries.items() if entry.normalized == "2025-03-03"
    }
    assert len(accident_tokens) == 1
    (accident_token,) = accident_tokens
    pages_seen = {occ.page for occ in registry.entries[accident_token].occurrences}
    assert len(pages_seen) >= 2  # consultation and decision both mention the accident


def test_restoration_round_trip(fixture_pdf_dir: Path, tmp_path: Path) -> None:
    paths = _prepare_case(fixture_pdf_dir, tmp_path, "case_restore")
    tokenize_case(paths.root)
    registry = load_date_registry(paths)
    token = registry.token_for("2025-07-16")

    bare = token.strip("[]")  # model sometimes drops the brackets
    events = [
        CandidateEvent(event_id="e1", report_id="r1", event_date_token=token),
        CandidateEvent(event_id="e2", report_id="r1", event_date_token="[[DATE_ZZZZ]]"),
        CandidateEvent(event_id="e3", report_id="r1", event_date_token=bare),
        CandidateEvent(event_id="e4", report_id="r1", event_date_token="2024-03-01"),
        CandidateEvent(event_id="e5", report_id="r1", event_date_token="3 mars 2024"),
        CandidateEvent(event_id="e6", report_id="r1", event_date_token="19 septembre"),  # no year
    ]
    restored = restore_event_dates(events, registry)
    assert restored[0].event_date == "2025-07-16" and restored[0].flags == []
    assert restored[1].event_date is None and "date_unresolved" in restored[1].flags
    assert restored[2].event_date == "2025-07-16"
    assert restored[3].event_date == "2024-03-01" and "date_literal" in restored[3].flags
    assert restored[4].event_date == "2024-03-03" and "date_literal" in restored[4].flags
    assert restored[5].event_date is None and "date_unresolved" in restored[5].flags


def test_tokenize_cli(fixture_pdf_dir: Path, tmp_path: Path, capsys) -> None:
    paths = _prepare_case(fixture_pdf_dir, tmp_path, "case_tok_cli")
    assert main(["tokenize", "--case", str(paths.root)]) == 0
    assert "pages tokenized  8" in capsys.readouterr().out
