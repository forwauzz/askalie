"""Gold chronology loading (Spec §28).

IMPORTANT (Spec §28.2): gold data is read ONLY by the eval layer. An import
guard test enforces that no other module touches this file's loader.
"""

from __future__ import annotations

from pathlib import Path

from ask_alie.serialization import AlieModel


class GoldEvent(AlieModel):
    gold_event_id: str
    date: str  # ISO yyyy-mm-dd
    description: str
    event_type: str = "unknown"
    key_facts: list[str] = []


def _normalize_gold_record(raw: dict) -> dict:
    """Accept the chrono-lab gold format (gold_event_id, date_iso, title, text)."""
    record = dict(raw)
    if "date" not in record and "date_iso" in record:
        record["date"] = record["date_iso"]
    if "description" not in record:
        parts = [record.get("title"), record.get("text")]
        record["description"] = " — ".join(p for p in parts if p)
    return record


def load_gold(path: Path) -> list[GoldEvent]:
    import json

    return [
        GoldEvent.model_validate(_normalize_gold_record(json.loads(line)))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
