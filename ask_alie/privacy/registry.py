"""Stable token registries for dates and identifiers (Spec §13).

Date tokens are deterministic hashes of the normalized date, so the same date
always yields the same opaque token within and across runs, with no
chronological ordering leaked (Spec §13.3). Entity tokens are sequential per
category ([[PERSON_01]]).

POC note: files are plain JSON despite the .enc.json names from the Spec tree.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ask_alie.serialization import AlieModel


class DateOccurrence(AlieModel):
    document_id: str
    page: int
    raw_text: str
    start_char: int
    end_char: int
    confidence: str = "high"


class DateEntry(AlieModel):
    token: str
    normalized: str
    occurrences: list[DateOccurrence] = []


def _date_code(normalized: str, length: int = 4) -> str:
    return hashlib.sha256(normalized.encode()).hexdigest()[:length].upper()


class DateRegistry:
    def __init__(self) -> None:
        self.entries: dict[str, DateEntry] = {}
        self._by_normalized: dict[str, str] = {}

    def token_for(self, normalized: str) -> str:
        token = self._by_normalized.get(normalized)
        if token:
            return token
        length = 4
        code = _date_code(normalized, length)
        while f"[[DATE_{code}]]" in self.entries:
            length += 2
            code = _date_code(normalized, length)
        token = f"[[DATE_{code}]]"
        self.entries[token] = DateEntry(token=token, normalized=normalized)
        self._by_normalized[normalized] = token
        return token

    def record(self, normalized: str, occurrence: DateOccurrence) -> str:
        token = self.token_for(normalized)
        self.entries[token].occurrences.append(occurrence)
        return token

    def resolve(self, token: str) -> str | None:
        entry = self.entries.get(token)
        return entry.normalized if entry else None

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {t: e.model_dump() for t, e in self.entries.items()}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> DateRegistry:
        registry = cls()
        if path.exists():
            for token, raw in json.loads(path.read_text(encoding="utf-8")).items():
                entry = DateEntry.model_validate(raw)
                registry.entries[token] = entry
                registry._by_normalized[entry.normalized] = token
        return registry


class EntityEntry(AlieModel):
    token: str
    category: str
    value: str


class EntityRegistry:
    def __init__(self) -> None:
        self.entries: dict[str, EntityEntry] = {}
        self._by_value: dict[tuple[str, str], str] = {}
        self._counters: dict[str, int] = {}

    def token_for(self, category: str, value: str) -> str:
        key = (category, value.casefold())
        token = self._by_value.get(key)
        if token:
            return token
        self._counters[category] = self._counters.get(category, 0) + 1
        token = f"[[{category}_{self._counters[category]:02d}]]"
        self.entries[token] = EntityEntry(token=token, category=category, value=value)
        self._by_value[key] = token
        return token

    def resolve(self, token: str) -> str | None:
        entry = self.entries.get(token)
        return entry.value if entry else None

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "entries": {t: e.model_dump() for t, e in self.entries.items()},
            "counters": self._counters,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> EntityRegistry:
        registry = cls()
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            for token, raw in payload["entries"].items():
                entry = EntityEntry.model_validate(raw)
                registry.entries[token] = entry
                registry._by_value[(entry.category, entry.value.casefold())] = token
            registry._counters = dict(payload.get("counters", {}))
        return registry
