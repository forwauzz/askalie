"""Render PDF pages to PNG images for OCR and review (Spec §12.2)."""

from __future__ import annotations

from pathlib import Path

import fitz


def render_page_png(pdf_path: Path, page_number: int, out_path: Path, dpi: int = 150) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf_path) as doc:
        pix = doc[page_number - 1].get_pixmap(dpi=dpi)
        pix.save(out_path)
    return out_path
