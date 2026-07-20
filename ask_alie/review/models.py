"""Reviewer decision model (Spec §11.7)."""

from __future__ import annotations

from ask_alie.serialization import AlieModel


class ReviewerDecision(AlieModel):
    event_id: str
    action: str  # accept | edit | move_default | move_secondary | reject | merge | duplicate
    before: dict = {}
    after: dict = {}
    reason: str = ""
    created_at: str = ""
