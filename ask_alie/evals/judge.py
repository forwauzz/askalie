"""LLM judge for uncertain gold matches.

An isolated evaluation call (never part of extraction, never in the
prompt-authoring loop) that renders match verdicts on the pairs a human
would otherwise click through. Verdicts are recorded with
reviewer="llm-judge" so they remain distinguishable from human decisions,
which always override (later adjudications win).
"""

from __future__ import annotations

import asyncio
from typing import Any

from ask_alie.evals.adjudicate import (
    pending_adjudications,
    record_adjudication,
    stored_gold_path,
)
from ask_alie.llm.client import ModelClient
from ask_alie.serialization import AlieModel
from ask_alie.workspace.paths import CasePaths

JUDGE_REVIEWER = "llm-judge"

JUDGE_SYSTEM = """You are an impartial evaluation judge for medical-legal
chronologies (Québec CNESST files). You compare two chronology entries that
already share the same date and decide whether they describe the SAME
real-world event (the same act: the same consultation, examination, decision,
report or session).

Differences in wording, language (French/English), level of detail or
abbreviation style do NOT matter. Different acts on the same date DO matter:
a consultation and an imaging exam on the same day are different events; a
decision and the medical report it relies on are different events.

Judge strictly on what the two entries state."""


class JudgeVerdict(AlieModel):
    same_event: bool
    confidence: str = "medium"  # high | medium | low
    reason: str = ""


async def judge_pending(
    paths: CasePaths,
    client: ModelClient,
    max_concurrency: int = 3,
) -> dict[str, Any]:
    pending = pending_adjudications(paths)
    if not pending:
        return {"judged": 0, "match": 0, "no_match": 0}

    from ask_alie import config

    semaphore = asyncio.Semaphore(max_concurrency)

    async def judge_one(item: dict[str, Any]) -> bool:
        async with semaphore:
            prompt = (
                f"Shared date: {item['date']}\n\n"
                f"Entry A (reference chronology):\n{item['gold_description']}\n\n"
                f"Entry B (extracted candidate):\n{item['candidate_summary']}\n"
                f"Supporting quote from the source document:\n"
                f"{(item['candidate_quote'] or '')[:400]}\n\n"
                "Do Entry A and Entry B describe the same real-world event?"
            )
            verdict = await client.structured(
                prompt, JudgeVerdict, system=JUDGE_SYSTEM, model=config.agent_model()
            )
            record_adjudication(
                paths,
                item["gold_event_id"],
                "match" if verdict.same_event else "no_match",
                reviewer=JUDGE_REVIEWER,
            )
            return verdict.same_event

    results = await asyncio.gather(*(judge_one(item) for item in pending))
    matches = sum(results)

    gold_path = stored_gold_path(paths)
    if gold_path:
        from ask_alie.evals.metrics import evaluate_case

        evaluate_case(paths, gold_path)
    return {"judged": len(pending), "match": matches, "no_match": len(pending) - matches}
