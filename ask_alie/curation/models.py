"""Curation assignment model (Spec §11.6, §19.2)."""

from __future__ import annotations

from ask_alie.serialization import AlieModel


class CurationAssignment(AlieModel):
    event_id: str
    queue: str  # "default" | "secondary"
    reason: str = ""
    curator_run_id: str = ""
    duplicate_of: str | None = None
    needs_review: bool = False
