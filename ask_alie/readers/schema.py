"""Reader structured-output schema (Spec §17.3)."""

from __future__ import annotations

from ask_alie.events.models import CrossReference
from ask_alie.serialization import AlieModel


class ReaderEventDraft(AlieModel):
    """An event as returned by a reader; IDs and origin are assigned locally."""

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


class ReaderAssessment(AlieModel):
    report_type: str = "unknown"
    readability: str = "good"
    possible_boundary_problem: bool = False
    possible_missing_pages: bool = False


class ReaderResult(AlieModel):
    report_id: str
    events: list[ReaderEventDraft] = []
    report_summary: str = ""
    cross_references: list[CrossReference] = []
    recommended_followups: list[str] = []
    reader_assessment: ReaderAssessment = ReaderAssessment()
