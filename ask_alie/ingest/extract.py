"""Native text extraction with PyMuPDF (Spec §12.2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass(frozen=True)
class NativePage:
    page_number: int  # 1-based
    text: str


def extract_native_text(pdf_path: Path) -> list[NativePage]:
    pages: list[NativePage] = []
    with fitz.open(pdf_path) as doc:
        for index, page in enumerate(doc, start=1):
            pages.append(NativePage(page_number=index, text=page.get_text()))
    return pages
