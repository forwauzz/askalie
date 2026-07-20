from pathlib import Path

import fitz


def test_fixture_bundles_have_expected_pages(fixture_pdf_dir: Path) -> None:
    b1 = fitz.open(fixture_pdf_dir / "bundle_01.pdf")
    b2 = fitz.open(fixture_pdf_dir / "bundle_02.pdf")
    assert b1.page_count == 4
    assert b2.page_count == 4

    # native text present where expected
    assert "Consultation" in b1[0].get_text() or "consultation" in b1[0].get_text()
    assert "IRM" in b1[2].get_text()
    assert b1[3].get_text().strip() == ""  # blank page

    assert "CNESST" in b2[0].get_text()
    assert "entorse lombaire" in b2[1].get_text()
    assert b2[2].get_text().strip() == ""  # image-only page has no text layer
    assert len(b2[3].get_text()) > 100  # garbage page has text, just unusable
