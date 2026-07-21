"""Human adjudication of uncertain gold matches (Spec §28.3).

Verdicts are stored separately from machine matches so re-running the
evaluation never clobbers human decisions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ask_alie.evals.gold import load_gold
from ask_alie.evals.match import MatchRecord
from ask_alie.events.store import CandidateStore
from ask_alie.serialization import AlieModel
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.paths import CasePaths

VERDICTS = ("match", "no_match")


class Adjudication(AlieModel):
    gold_event_id: str
    verdict: str  # match | no_match
    reviewer: str = "reviewer"
    created_at: str = ""


def _store(paths: CasePaths) -> JsonlStore[Adjudication]:
    return JsonlStore(paths.eval_dir / "adjudications.jsonl", Adjudication)


def load_adjudications(paths: CasePaths) -> dict[str, Adjudication]:
    latest: dict[str, Adjudication] = {}
    for entry in _store(paths).read_all():
        latest[entry.gold_event_id] = entry  # later entries win
    return latest


def record_adjudication(
    paths: CasePaths, gold_event_id: str, verdict: str, reviewer: str = "reviewer"
) -> Adjudication:
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")
    entry = Adjudication(
        gold_event_id=gold_event_id,
        verdict=verdict,
        reviewer=reviewer,
        created_at=datetime.now(UTC).isoformat(),
    )
    _store(paths).append(entry)
    return entry


def stored_gold_path(paths: CasePaths) -> Path | None:
    marker = paths.eval_dir / "gold_path.txt"
    if marker.exists():
        candidate = Path(marker.read_text(encoding="utf-8").strip())
        if candidate.exists():
            return candidate
    return None


def pending_adjudications(paths: CasePaths) -> list[dict[str, Any]]:
    """Uncertain matches awaiting a human verdict, with both sides joined."""
    matches_path = paths.eval_dir / "matches.jsonl"
    gold_path = stored_gold_path(paths)
    if not matches_path.exists() or gold_path is None:
        return []
    matches = JsonlStore(matches_path, MatchRecord).read_all()
    decided = load_adjudications(paths)
    gold_by_id = {g.gold_event_id: g for g in load_gold(gold_path)}
    candidates = {c.event_id: c for c in CandidateStore(paths).read_all()}

    # source document names for display
    from ask_alie.reports.map import load_report_map
    from ask_alie.workspace.manifest import load_manifest

    doc_names = {}
    if paths.manifest.exists():
        doc_names = {d.document_id: d.filename for d in load_manifest(paths).documents}
    report_docs = {
        u.report_id: doc_names.get(u.document_id, u.document_id)
        for u in load_report_map(paths)
    }

    pending: list[dict[str, Any]] = []
    for match in matches:
        if not match.needs_adjudication or match.gold_event_id in decided:
            continue
        gold = gold_by_id.get(match.gold_event_id)
        candidate = candidates.get(match.candidate_event_id or "")
        if gold is None or candidate is None:
            continue
        pending.append(
            {
                "gold_event_id": gold.gold_event_id,
                "date": gold.date,
                "gold_description": gold.description,
                "candidate_event_id": candidate.event_id,
                "candidate_summary": candidate.summary_fr,
                "candidate_quote": candidate.quote,
                "candidate_source": report_docs.get(candidate.report_id, candidate.report_id),
                "candidate_pages": candidate.source_pages,
            }
        )
    return pending
