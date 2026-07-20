"""Gold chronology loading (Spec §28).

IMPORTANT (Spec §28.2): gold data is read ONLY by the eval layer. An import
guard test enforces that no other module touches this file's loader.
"""

from __future__ import annotations

from pathlib import Path

from ask_alie.serialization import AlieModel
from ask_alie.workspace.jsonl import JsonlStore


class GoldEvent(AlieModel):
    gold_event_id: str
    date: str  # ISO yyyy-mm-dd
    description: str
    event_type: str = "unknown"
    key_facts: list[str] = []


def load_gold(path: Path) -> list[GoldEvent]:
    return JsonlStore(path, GoldEvent).read_all()
