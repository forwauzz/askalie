"""Report unit model (Spec §11.3)."""

from __future__ import annotations

from ask_alie.serialization import AlieModel


class ReportUnit(AlieModel):
    report_id: str
    document_id: str
    page_start: int
    page_end: int
    page_ids: list[str] = []
    document_type: str = "unknown"
    title: str = ""
    boundary_confidence: str = "medium"
    boundary_reason: str = ""
    status: str = "proposed"
    flags: list[str] = []
