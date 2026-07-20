"""inspect_document and read_pages tools (Spec §21.1)."""

from __future__ import annotations

from typing import Any

from ask_alie.ingest.service import load_page_records
from ask_alie.tools.registry import ToolContext, tool

_MAX_PAGES_PER_READ = 20


def _safe_text(ctx: ToolContext, document_id: str, page_number: int) -> str:
    path = ctx.paths.page_dir(document_id) / f"page_{page_number:04d}.safe.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@tool(
    "inspect_document",
    "Summarize a page range of one document: extraction method, quality, header preview.",
    {
        "type": "object",
        "properties": {
            "document_id": {"type": "string"},
            "page_start": {"type": "integer"},
            "page_end": {"type": "integer"},
            "mode": {"type": "string", "enum": ["headers", "full"]},
        },
        "required": ["document_id"],
    },
)
async def inspect_document(
    ctx: ToolContext,
    document_id: str,
    page_start: int = 1,
    page_end: int | None = None,
    mode: str = "headers",
) -> dict[str, Any]:
    records = load_page_records(ctx.paths, document_id)
    if not records:
        return {"error": f"unknown document or no pages: {document_id}"}
    page_end = page_end or records[-1].page_number
    selected = [r for r in records if page_start <= r.page_number <= page_end]
    pages = []
    for record in selected:
        text = _safe_text(ctx, document_id, record.page_number)
        preview = text.strip()[:150] if mode == "headers" else text.strip()[:1500]
        pages.append(
            {
                "page_id": record.page_id,
                "extraction_method": record.extraction_method,
                "text_quality": record.text_quality,
                "flags": record.flags,
                "date_tokens": record.date_tokens,
                "preview": preview,
            }
        )
    return {"document_id": document_id, "pages": pages}


@tool(
    "read_pages",
    "Return the safe text of specific pages (max 20 per call).",
    {
        "type": "object",
        "properties": {
            "page_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["page_ids"],
    },
)
async def read_pages(ctx: ToolContext, page_ids: list[str]) -> dict[str, Any]:
    if len(page_ids) > _MAX_PAGES_PER_READ:
        return {"error": f"too many pages requested ({len(page_ids)} > {_MAX_PAGES_PER_READ})"}
    pages = []
    for page_id in page_ids:
        try:
            document_id, page_part = page_id.split(":p_")
            page_number = int(page_part)
        except ValueError:
            return {"error": f"invalid page_id: {page_id}"}
        pages.append({"page_id": page_id, "text": _safe_text(ctx, document_id, page_number)})
    return {"pages": pages}
