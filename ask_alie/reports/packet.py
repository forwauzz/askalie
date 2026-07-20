"""Scout document packet: first 1500 + last 500 chars of each page (Spec §16.5)."""

from __future__ import annotations

from typing import Any

from ask_alie.ingest.service import load_page_records
from ask_alie.workspace.paths import CasePaths

_HEAD_CHARS = 1500
_TAIL_CHARS = 500


def build_scout_packet(paths: CasePaths, document_id: str) -> list[dict[str, Any]]:
    packet: list[dict[str, Any]] = []
    for record in load_page_records(paths, document_id):
        safe_path = paths.page_dir(document_id) / f"page_{record.page_number:04d}.safe.txt"
        text = safe_path.read_text(encoding="utf-8") if safe_path.exists() else ""
        entry: dict[str, Any] = {
            "page": record.page_number,
            "extraction_method": record.extraction_method,
            "text_quality": record.text_quality,
            "flags": record.flags,
            "head": text[:_HEAD_CHARS],
        }
        if len(text) > _HEAD_CHARS + _TAIL_CHARS:
            entry["tail"] = text[-_TAIL_CHARS:]
        packet.append(entry)
    return packet
