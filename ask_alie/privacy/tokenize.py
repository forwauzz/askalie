"""Case tokenization pipeline: raw page text → safe text + token registries (Spec §13)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ask_alie.privacy.dates import find_dates
from ask_alie.privacy.entities import find_entities
from ask_alie.privacy.registry import DateOccurrence, DateRegistry, EntityRegistry
from ask_alie.workspace.manifest import load_manifest
from ask_alie.workspace.pages import PageRecord
from ask_alie.workspace.paths import CasePaths
from ask_alie.workspace.runlog import log_action


@dataclass
class TokenizeSummary:
    pages_tokenized: int = 0
    date_tokens: int = 0
    entity_tokens: int = 0

    def render(self) -> str:
        return (
            f"pages tokenized  {self.pages_tokenized}\n"
            f"unique dates     {self.date_tokens}\n"
            f"unique entities  {self.entity_tokens}"
        )


def _date_map_path(paths: CasePaths) -> Path:
    return paths.privacy_dir / "date_map.enc.json"


def _entity_map_path(paths: CasePaths) -> Path:
    return paths.privacy_dir / "entity_map.enc.json"


def load_date_registry(paths: CasePaths) -> DateRegistry:
    return DateRegistry.load(_date_map_path(paths))


def load_entity_registry(paths: CasePaths) -> EntityRegistry:
    return EntityRegistry.load(_entity_map_path(paths))


def _load_known_entities(paths: CasePaths) -> dict[str, list[str]]:
    known_path = paths.root / "known_entities.json"
    if known_path.exists():
        return json.loads(known_path.read_text(encoding="utf-8"))
    return {}


def _build_safe_text(
    text: str,
    document_id: str,
    page_number: int,
    date_registry: DateRegistry,
    entity_registry: EntityRegistry,
    known_entities: dict[str, list[str]],
) -> tuple[str, list[str], list[str]]:
    replacements: list[tuple[int, int, str]] = []
    date_tokens: list[str] = []
    entity_tokens: list[str] = []

    for match in find_dates(text):
        token = date_registry.record(
            match.normalized,
            DateOccurrence(
                document_id=document_id,
                page=page_number,
                raw_text=match.raw_text,
                start_char=match.start_char,
                end_char=match.end_char,
                confidence=match.confidence,
            ),
        )
        replacements.append((match.start_char, match.end_char, token))
        if token not in date_tokens:
            date_tokens.append(token)

    for match in find_entities(text, known_entities):
        token = entity_registry.token_for(match.category, match.value)
        replacements.append((match.start_char, match.end_char, token))
        if token not in entity_tokens:
            entity_tokens.append(token)

    # overlapping date/entity spans: earliest-longest wins
    replacements.sort(key=lambda r: (r[0], -(r[1] - r[0])))
    pieces: list[str] = []
    cursor = 0
    for start, end, token in replacements:
        if start < cursor:
            continue
        pieces.append(text[cursor:start])
        pieces.append(token)
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), date_tokens, entity_tokens


def tokenize_case(case_root: Path) -> TokenizeSummary:
    paths = CasePaths(root=Path(case_root))
    manifest = load_manifest(paths)
    date_registry = load_date_registry(paths)
    entity_registry = load_entity_registry(paths)
    known_entities = _load_known_entities(paths)
    summary = TokenizeSummary()

    for doc in manifest.documents:
        page_dir = paths.page_dir(doc.document_id)
        for record_path in sorted(page_dir.glob("page_*.json")):
            record = PageRecord.model_validate_json(record_path.read_text(encoding="utf-8"))
            raw_path = paths.root / record.raw_text_path
            text = raw_path.read_text(encoding="utf-8") if raw_path.exists() else ""

            safe_text, date_tokens, entity_tokens = _build_safe_text(
                text, doc.document_id, record.page_number,
                date_registry, entity_registry, known_entities,
            )
            safe_path = page_dir / f"page_{record.page_number:04d}.safe.txt"
            safe_path.write_text(safe_text, encoding="utf-8")

            record.safe_text_path = str(safe_path.relative_to(paths.root))
            record.date_tokens = date_tokens
            record.entity_tokens = entity_tokens
            record_path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
            summary.pages_tokenized += 1

    date_registry.save(_date_map_path(paths))
    entity_registry.save(_entity_map_path(paths))
    summary.date_tokens = len(date_registry.entries)
    summary.entity_tokens = len(entity_registry.entries)

    log_action(
        paths,
        actor="tokenize",
        action="tokenize_case",
        result={
            "pages": summary.pages_tokenized,
            "unique_dates": summary.date_tokens,
            "unique_entities": summary.entity_tokens,
        },
    )
    return summary
