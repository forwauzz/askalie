import shutil
from pathlib import Path

import pytest

from ask_alie.cli import main
from ask_alie.ingest.ocr import NullOcrEngine, TesseractEngine, default_engine
from ask_alie.ingest.service import ingest_case, load_page_records
from ask_alie.workspace.paths import CasePaths


class FakeOcrEngine:
    name = "fake"
    available = True

    def ocr_image(self, png_path: Path) -> str:
        return (
            "PHYSIOTHÉRAPIE FICTIVE — note de traitement du 10 juillet 2025 pour le patient. "
            "Le traitement de physiothérapie est poursuivi avec des exercices pour la région "
            "lombaire et une amélioration est notée depuis la dernière visite du patient."
        )


def test_ingest_with_null_ocr(fixture_pdf_dir: Path, tmp_path: Path) -> None:
    manifest, summary = ingest_case(
        fixture_pdf_dir, "case_null", tmp_path, ocr_engine=NullOcrEngine()
    )
    # 8 fixture pages: 5 native-usable, 3 needing OCR (blank, image-only, garbage)
    assert summary.total_pages == 8
    assert summary.native_pages == 5
    assert summary.ocr_pages == 0
    assert summary.unreadable_pages == 3

    paths = CasePaths.for_case(tmp_path, "case_null")
    records = load_page_records(paths, "doc_001") + load_page_records(paths, "doc_002")
    assert len(records) == 8
    flagged = [r for r in records if "ocr_unavailable" in r.flags]
    assert len(flagged) == 3
    for record in flagged:
        assert record.extraction_method == "none"
        # page image preserved for review (Spec §34)
        stem = f"page_{record.page_number:04d}"
        assert (paths.page_dir(record.document_id) / f"{stem}.png").exists()
    for record in records:
        assert (paths.root / record.raw_text_path).exists()


def test_ingest_with_fake_ocr_engine(fixture_pdf_dir: Path, tmp_path: Path) -> None:
    _, summary = ingest_case(fixture_pdf_dir, "case_fake", tmp_path, ocr_engine=FakeOcrEngine())
    assert summary.ocr_pages == 3
    assert summary.unreadable_pages == 0
    paths = CasePaths.for_case(tmp_path, "case_fake")
    ocr_records = [
        r
        for r in load_page_records(paths, "doc_001") + load_page_records(paths, "doc_002")
        if r.extraction_method == "fake"
    ]
    assert len(ocr_records) == 3


def test_ingest_cli(fixture_pdf_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    exit_code = main(
        ["ingest", "--input", str(fixture_pdf_dir), "--case-id", "case_cli", "--workspace", str(tmp_path)]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "total pages      8" in out
    assert "case case_cli: 2 document(s)" in out


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract not installed")
def test_live_tesseract_on_image_only_page(fixture_pdf_dir: Path, tmp_path: Path) -> None:
    engine = default_engine()
    assert isinstance(engine, TesseractEngine)
    _, summary = ingest_case(fixture_pdf_dir, "case_live", tmp_path, ocr_engine=engine)
    # the image-only physio page should come back as readable text
    assert summary.ocr_pages >= 1
