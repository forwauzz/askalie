"""Round-trip tests for the Spec §11 data models."""

from ask_alie.curation.models import CurationAssignment
from ask_alie.events.models import CandidateEvent, CrossReference, EventOrigin
from ask_alie.reports.models import ReportUnit
from ask_alie.review.models import ReviewerDecision
from ask_alie.workspace.manifest import CaseManifest, DocumentEntry
from ask_alie.workspace.pages import PageRecord
from ask_alie.workspace.tasks import AgentTask

MODELS = [
    (
        CaseManifest,
        {
            "case_id": "case_001",
            "created_at": "2026-07-20T12:00:00-04:00",
            "documents": [
                {"document_id": "doc_001", "filename": "b.pdf", "sha256": "ab", "page_count": 4}
            ],
        },
    ),
    (
        PageRecord,
        {
            "page_id": "doc_001:p_0012",
            "document_id": "doc_001",
            "page_number": 12,
            "extraction_method": "tesseract",
            "text_quality": 0.76,
            "date_tokens": ["[[DATE_K7M2]]"],
            "entity_tokens": ["[[PERSON_01]]"],
        },
    ),
    (
        ReportUnit,
        {
            "report_id": "report_0042",
            "document_id": "doc_001",
            "page_start": 12,
            "page_end": 15,
            "page_ids": ["doc_001:p_0012"],
            "document_type": "medical_consultation",
            "boundary_confidence": "medium",
        },
    ),
    (
        CandidateEvent,
        {
            "event_id": "event_0104",
            "report_id": "report_0042",
            "event_date_token": "[[DATE_K7M2]]",
            "summary_fr": "Le travailleur consulte...",
            "source_pages": [13],
            "quote": "Le patient rapporte...",
            "quote_page": 13,
            "cross_references": [{"description": "IRM antérieure", "date_token": "[[DATE_A91Q]]"}],
            "origin": {"reader_run_id": "reader_run_0051", "pass_number": 1},
        },
    ),
    (
        AgentTask,
        {
            "task_id": "task_0087",
            "action": "reread_report",
            "target_ids": ["report_0042"],
            "requested_by": "gap_agent",
            "priority": "high",
        },
    ),
    (
        CurationAssignment,
        {"event_id": "event_0104", "queue": "default", "reason": "Material change"},
    ),
    (
        ReviewerDecision,
        {
            "event_id": "event_0104",
            "action": "edit",
            "before": {"summary_fr": "a"},
            "after": {"summary_fr": "b"},
        },
    ),
]


def test_round_trip_serialization() -> None:
    for model_cls, payload in MODELS:
        instance = model_cls.model_validate(payload)
        again = model_cls.model_validate_json(instance.model_dump_json())
        assert again == instance


def test_unknown_fields_are_tolerated() -> None:
    for model_cls, payload in MODELS:
        assert model_cls.model_validate({**payload, "future_field": 123})


def test_nested_models_parse() -> None:
    event = CandidateEvent.model_validate(MODELS[3][1])
    assert isinstance(event.cross_references[0], CrossReference)
    assert isinstance(event.origin, EventOrigin)
    assert isinstance(
        CaseManifest.model_validate(MODELS[0][1]).documents[0], DocumentEntry
    )
