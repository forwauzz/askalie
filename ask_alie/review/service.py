"""Reviewer decisions and the effective chronology state (Spec §7.3, §11.7).

Decisions are append-only; the effective row state is derived by replaying
them in order. Nothing is ever deleted — rejected rows stay inspectable.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ask_alie.curation.models import CurationAssignment
from ask_alie.events.store import CandidateStore
from ask_alie.privacy.tokenize import load_entity_registry
from ask_alie.review.models import ReviewerDecision
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.paths import CasePaths

REVIEW_ACTIONS = (
    "accept",
    "edit",
    "move_default",
    "move_secondary",
    "reject",
    "merge",
    "duplicate",
)


def _decisions_store(paths: CasePaths) -> JsonlStore[ReviewerDecision]:
    return JsonlStore(paths.decisions_file, ReviewerDecision)


def record_decision(
    paths: CasePaths,
    event_id: str,
    action: str,
    after: dict[str, Any] | None = None,
    before: dict[str, Any] | None = None,
    reason: str = "",
) -> ReviewerDecision:
    if action not in REVIEW_ACTIONS:
        raise ValueError(f"unknown reviewer action: {action}")
    decision = ReviewerDecision(
        event_id=event_id,
        action=action,
        before=before or {},
        after=after or {},
        reason=reason,
        created_at=datetime.now(UTC).isoformat(),
    )
    _decisions_store(paths).append(decision)
    return decision


def build_rows(paths: CasePaths) -> list[dict[str, Any]]:
    """Candidate events + curation + replayed reviewer decisions → display rows."""
    events = CandidateStore(paths).read_all()
    assignments = {
        a.event_id: a for a in JsonlStore(paths.curation_file, CurationAssignment).read_all()
    }
    decisions: dict[str, list[ReviewerDecision]] = {}
    for decision in _decisions_store(paths).read_all():
        decisions.setdefault(decision.event_id, []).append(decision)
    entities = load_entity_registry(paths)

    # map report -> source document filename for client-facing display
    from ask_alie.reports.map import load_report_map
    from ask_alie.workspace.manifest import load_manifest

    doc_names: dict[str, str] = {}
    report_docs: dict[str, str] = {}
    if paths.manifest.exists():
        doc_names = {d.document_id: d.filename for d in load_manifest(paths).documents}
    for unit in load_report_map(paths):
        report_docs[unit.report_id] = doc_names.get(unit.document_id, unit.document_id)

    rows: list[dict[str, Any]] = []
    for event in events:
        assignment = assignments.get(event.event_id)
        queue = assignment.queue if assignment else "unassigned"
        status = "candidate"
        summary = event.summary_fr
        review_reasons: list[str] = []

        for decision in decisions.get(event.event_id, []):
            if decision.action == "accept":
                status = "accepted"
            elif decision.action == "edit":
                summary = decision.after.get("summary_fr", summary)
                status = "edited"
            elif decision.action == "move_default":
                queue = "default"
            elif decision.action == "move_secondary":
                queue = "secondary"
            elif decision.action == "reject":
                status = "rejected"
            elif decision.action in ("merge", "duplicate"):
                status = decision.action
            if decision.reason:
                review_reasons.append(decision.reason)

        author = None
        if event.author_token:
            author = entities.resolve(event.author_token) or event.author_token
        rows.append(
            {
                "event_id": event.event_id,
                "date": event.event_date,
                "event_type": event.event_type,
                "summary": summary,
                "author": author,
                "report_id": event.report_id,
                "source_document": report_docs.get(event.report_id, event.report_id),
                "source_pages": event.source_pages,
                "quote": event.quote,
                "quote_page": event.quote_page,
                "queue": queue,
                "status": status,
                "needs_review": assignment.needs_review if assignment else True,
                "duplicate_of": assignment.duplicate_of if assignment else None,
                "flags": event.flags,
                "pass_number": event.origin.pass_number if event.origin else 1,
                "review_reasons": review_reasons,
            }
        )
    rows.sort(key=lambda r: (r["date"] is None, r["date"] or "", r["event_id"]))
    return rows


def split_queues(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Default / secondary (excluding rejected) plus the unresolved queue (Spec §27.5)."""
    active = [r for r in rows if r["status"] != "rejected"]
    return {
        "default": [r for r in active if r["queue"] == "default"],
        "secondary": [r for r in active if r["queue"] == "secondary"],
        "unresolved": [
            r
            for r in rows
            if r["status"] == "rejected"
            or r["queue"] == "unassigned"
            or r["needs_review"]
            or "date_unresolved" in r["flags"]
            or "stale_unit" in r["flags"]
        ],
    }
