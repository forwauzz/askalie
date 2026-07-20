"""Append-only candidate event store (Spec §10: candidates/events.jsonl)."""

from __future__ import annotations

from ask_alie.events.models import CandidateEvent
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.paths import CasePaths


class CandidateStore:
    def __init__(self, paths: CasePaths):
        self._store = JsonlStore(paths.candidates_file, CandidateEvent)

    def read_all(self) -> list[CandidateEvent]:
        return self._store.read_all()

    def append_events(self, events: list[CandidateEvent]) -> None:
        self._store.append_many(events)

    def rewrite(self, events: list[CandidateEvent]) -> None:
        self._store.rewrite(events)
