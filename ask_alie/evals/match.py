"""Gold-to-candidate matching (Spec §28.3).

Deterministic first pass: date match + word-overlap similarity + key-fact
overlap. Borderline similarity is flagged for manual adjudication rather than
silently decided.
"""

from __future__ import annotations

import re

from ask_alie.evals.gold import GoldEvent
from ask_alie.events.models import CandidateEvent
from ask_alie.serialization import AlieModel

_WORD = re.compile(r"[a-zà-ÿ]{3,}", re.IGNORECASE)
_FULL_THRESHOLD = 0.45
_PARTIAL_THRESHOLD = 0.2

_STOPWORDS = frozenset(
    (
        "les des une pour avec dans sur est sont aux par elle nous vous pas cette son ses "
        "que qui été plus depuis suite date entre vers chez sous ainsi comme lors fait "
        "faire être avoir aussi sans mais donc car tout tous toute toutes autre autres "
        "the and for with was this that from"
    ).split()
)


class MatchRecord(AlieModel):
    gold_event_id: str
    candidate_event_id: str | None
    date_match: bool = False
    meaning_match: str = "none"  # full | partial | none
    needs_adjudication: bool = False
    reviewer: str | None = None
    notes: str | None = None


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if w.lower() not in _STOPWORDS}


def _similarity(gold: GoldEvent, candidate: CandidateEvent) -> float:
    """Containment score: shared meaningful words over the shorter text.

    Gold descriptions are long paragraphs while candidate summaries are short,
    so symmetric Jaccard under-scores true matches badly.
    """
    gold_words = _words(gold.description)
    candidate_words = _words(candidate.summary_fr)
    if not gold_words or not candidate_words:
        return 0.0
    containment = len(gold_words & candidate_words) / min(len(gold_words), len(candidate_words))
    if gold.key_facts:
        summary = candidate.summary_fr.casefold()
        fact_hits = sum(1 for fact in gold.key_facts if fact.casefold() in summary)
        return max(containment, fact_hits / len(gold.key_facts))
    return containment


def _classify(score: float) -> tuple[str, bool]:
    if score >= _FULL_THRESHOLD:
        return "full", False
    if score >= _PARTIAL_THRESHOLD:
        return "partial", True  # uncertain: manual adjudication
    return "none", False


def match_events(
    gold_events: list[GoldEvent], candidates: list[CandidateEvent]
) -> list[MatchRecord]:
    records: list[MatchRecord] = []
    used_candidates: set[str] = set()

    def best_match(
        gold: GoldEvent, pool: list[CandidateEvent]
    ) -> tuple[CandidateEvent | None, float]:
        best: CandidateEvent | None = None
        best_score = 0.0
        for candidate in pool:
            if candidate.event_id in used_candidates:
                continue
            score = _similarity(gold, candidate)
            if score > best_score:
                best, best_score = candidate, score
        return best, best_score

    for gold in gold_events:
        same_date = [c for c in candidates if c.event_date == gold.date]
        candidate, score = best_match(gold, same_date)
        meaning, uncertain = _classify(score)
        if candidate is not None and meaning != "none":
            used_candidates.add(candidate.event_id)
            records.append(
                MatchRecord(
                    gold_event_id=gold.gold_event_id,
                    candidate_event_id=candidate.event_id,
                    date_match=True,
                    meaning_match=meaning,
                    needs_adjudication=uncertain,
                )
            )
            continue

        # no same-date match: look for the event under a wrong date
        other_date = [c for c in candidates if c.event_date != gold.date]
        candidate, score = best_match(gold, other_date)
        meaning, uncertain = _classify(score)
        if candidate is not None and meaning == "full":
            used_candidates.add(candidate.event_id)
            records.append(
                MatchRecord(
                    gold_event_id=gold.gold_event_id,
                    candidate_event_id=candidate.event_id,
                    date_match=False,
                    meaning_match=meaning,
                    needs_adjudication=uncertain,
                    notes="wrong date",
                )
            )
        else:
            records.append(
                MatchRecord(gold_event_id=gold.gold_event_id, candidate_event_id=None)
            )

    return records
