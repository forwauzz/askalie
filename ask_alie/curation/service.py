"""Curator service (Spec §19): assign every candidate to a queue.

Model judgment first; the baseline mandatory-default rule is applied as a
local post-check that flags disagreement instead of silently overriding
context (queue is forced to default, needs_review is set). Candidates the
model skipped are defaulted and flagged — nothing is dropped.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ask_alie.curation.baseline import MANDATORY_DEFAULT
from ask_alie.curation.models import CurationAssignment
from ask_alie.events.duplicates import link_duplicates
from ask_alie.events.store import CandidateStore
from ask_alie.llm.client import ModelClient
from ask_alie.serialization import AlieModel
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.paths import CasePaths
from ask_alie.workspace.runlog import log_action

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "agents" / "prompts"


class CuratorAssignmentDraft(AlieModel):
    event_id: str
    queue: str = "default"
    reason: str = ""
    duplicate_of: str | None = None
    needs_review: bool = False


class CuratorResult(AlieModel):
    assignments: list[CuratorAssignmentDraft] = []


def curator_system_prompt() -> str:
    return (_PROMPTS_DIR / "curator.md").read_text(encoding="utf-8")


async def run_curator(
    paths: CasePaths, client: ModelClient, curator_run_id: str = "curator_0001"
) -> dict[str, Any]:
    store = CandidateStore(paths)
    events = store.read_all()
    if not events:
        return {"error": "no candidate events to curate"}
    duplicate_links = link_duplicates(events)

    summaries = [
        {
            "event_id": e.event_id,
            "event_date": e.event_date,
            "event_type": e.event_type,
            "summary_fr": e.summary_fr[:250],
            "flags": e.flags,
        }
        for e in events
    ]
    prompt = (
        "Assign each candidate event to the 'default' or 'secondary' queue.\n"
        "Candidates (JSON):\n" + json.dumps(summaries, ensure_ascii=False, indent=1)
    )
    result = await client.structured(prompt, CuratorResult, system=curator_system_prompt())

    drafts = {d.event_id: d for d in result.assignments}
    by_id = {e.event_id: e for e in events}
    assignments: list[CurationAssignment] = []
    forced_default = 0
    unassigned = 0

    for event in events:
        draft = drafts.get(event.event_id)
        if draft is None:
            unassigned += 1
            draft = CuratorAssignmentDraft(
                event_id=event.event_id,
                queue="default",
                reason="not assigned by curator",
                needs_review=True,
            )
        queue, reason, needs_review = draft.queue, draft.reason, draft.needs_review
        if event.event_type in MANDATORY_DEFAULT and queue != "default":
            queue = "default"
            reason = (reason + " [baseline: mandatory default]").strip()
            needs_review = True
            forced_default += 1
        assignments.append(
            CurationAssignment(
                event_id=event.event_id,
                queue=queue if queue in ("default", "secondary") else "default",
                reason=reason,
                curator_run_id=curator_run_id,
                duplicate_of=draft.duplicate_of or duplicate_links.get(event.event_id),
                needs_review=needs_review,
            )
        )

    # drafts for unknown event ids are ignored, but surfaced
    unknown = [event_id for event_id in drafts if event_id not in by_id]

    JsonlStore(paths.curation_file, CurationAssignment).rewrite(assignments)
    counts = {
        "default": sum(1 for a in assignments if a.queue == "default"),
        "secondary": sum(1 for a in assignments if a.queue == "secondary"),
    }
    log_action(
        paths,
        actor="curator",
        action="run_curator",
        result={**counts, "forced_default": forced_default, "unassigned": unassigned},
    )
    return {
        **counts,
        "total": len(assignments),
        "forced_default": forced_default,
        "unassigned_defaulted": unassigned,
        "unknown_event_ids": unknown,
        "duplicates_linked": len(duplicate_links),
    }
