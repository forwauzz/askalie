"""Hybrid ingest pipeline: native extraction, quality check, OCR fallback (Spec §12)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ask_alie.ingest.extract import extract_native_text
from ask_alie.ingest.ocr import OcrEngine, OcrError, default_engine
from ask_alie.ingest.quality import score_text
from ask_alie.ingest.render import render_page_png
from ask_alie.workspace.manifest import CaseManifest, create_case_workspace
from ask_alie.workspace.pages import PageRecord
from ask_alie.workspace.paths import CasePaths
from ask_alie.workspace.runlog import log_action


@dataclass
class IngestSummary:
    total_pages: int = 0
    native_pages: int = 0
    ocr_pages: int = 0
    unreadable_pages: int = 0
    duration_seconds: float = 0.0

    def render(self) -> str:
        return (
            f"total pages      {self.total_pages}\n"
            f"native usable    {self.native_pages}\n"
            f"OCR required     {self.ocr_pages}\n"
            f"empty/unreadable {self.unreadable_pages}\n"
            f"ingest duration  {self.duration_seconds:.1f}s"
        )


def ingest_case(
    input_dir: Path,
    case_id: str,
    workspace_root: Path,
    ocr_engine: OcrEngine | None = None,
) -> tuple[CaseManifest, IngestSummary]:
    started = time.monotonic()
    engine = ocr_engine or default_engine()
    manifest = create_case_workspace(input_dir, case_id, workspace_root)
    paths = CasePaths.for_case(workspace_root, case_id)
    summary = IngestSummary()

    for doc in manifest.documents:
        pdf_path = paths.source_original / f"{doc.document_id}.pdf"
        page_dir = paths.page_dir(doc.document_id)
        page_dir.mkdir(parents=True, exist_ok=True)

        for native in extract_native_text(pdf_path):
            summary.total_pages += 1
            number = native.page_number
            stem = f"page_{number:04d}"
            flags: list[str] = []
            quality = score_text(native.text)

            if quality.usable:
                text, method = native.text, "native"
                summary.native_pages += 1
            else:
                png_path = render_page_png(pdf_path, number, page_dir / f"{stem}.png")
                if engine.available:
                    try:
                        text, method = engine.ocr_image(png_path), engine.name
                        quality = score_text(text)
                        if not quality.usable:
                            flags.append("low_quality_ocr")
                            summary.unreadable_pages += 1
                        else:
                            summary.ocr_pages += 1
                    except OcrError:
                        text, method = "", "none"
                        flags.append("ocr_failed")
                        summary.unreadable_pages += 1
                else:
                    text, method = "", "none"
                    flags.append("ocr_unavailable")
                    summary.unreadable_pages += 1

            raw_path = page_dir / f"{stem}.raw.txt"
            raw_path.write_text(text, encoding="utf-8")
            record = PageRecord(
                page_id=f"{doc.document_id}:p_{number:04d}",
                document_id=doc.document_id,
                page_number=number,
                native_character_count=len(native.text.strip()),
                extraction_method=method,
                text_quality=quality.score,
                raw_text_path=str(raw_path.relative_to(paths.root)),
                flags=flags,
            )
            (page_dir / f"{stem}.json").write_text(record.model_dump_json(indent=2), encoding="utf-8")

    summary.duration_seconds = time.monotonic() - started
    log_action(
        paths,
        actor="ingest",
        action="ingest_case",
        targets=[d.document_id for d in manifest.documents],
        result={
            "total_pages": summary.total_pages,
            "native_pages": summary.native_pages,
            "ocr_pages": summary.ocr_pages,
            "unreadable_pages": summary.unreadable_pages,
            "ocr_engine": engine.name,
        },
    )
    return manifest, summary


def load_page_records(paths: CasePaths, document_id: str) -> list[PageRecord]:
    page_dir = paths.page_dir(document_id)
    records = [
        PageRecord.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(page_dir.glob("page_*.json"))
    ]
    return records
