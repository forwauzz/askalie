"""Structured-output schemas for Scout and Gap agents (Spec §16.3, §18.3)."""

from __future__ import annotations

from ask_alie.serialization import AlieModel


class ScoutUnit(AlieModel):
    page_start: int
    page_end: int
    document_type: str = "unknown"
    title: str = ""
    confidence: str = "medium"
    reason: str = ""


class UncertainRange(AlieModel):
    page_start: int
    page_end: int
    reason: str = ""


class ScoutResult(AlieModel):
    document_id: str
    proposed_units: list[ScoutUnit] = []
    uncertain_ranges: list[UncertainRange] = []


class GapTaskDraft(AlieModel):
    action: str  # reread_report | inspect_pages | resegment | search
    target_ids: list[str] = []
    priority: str = "medium"
    reason: str = ""
    instructions: str | None = None


class GapResult(AlieModel):
    tasks: list[GapTaskDraft] = []
    assessment: str = ""
