"""Candidate event models (Spec §11.4)."""

from __future__ import annotations

from ask_alie.serialization import AlieModel


class CrossReference(AlieModel):
    description: str
    date_token: str | None = None


class EventOrigin(AlieModel):
    reader_run_id: str
    pass_number: int = 1
    reason_for_pass: str = "initial"
    skills: list[str] = []  # skills active during the reader pass that produced this event


class CandidateEvent(AlieModel):
    event_id: str
    report_id: str
    event_date_token: str
    event_type: str = "unknown"
    summary_fr: str = ""
    author_token: str | None = None
    facility_token: str | None = None
    source_pages: list[int] = []
    quote: str = ""
    quote_page: int | None = None
    reader_confidence: str = "medium"
    uncertainty: str | None = None
    cross_references: list[CrossReference] = []
    origin: EventOrigin | None = None
    flags: list[str] = []
    # filled by local restoration (Spec §13.4)
    event_date: str | None = None
