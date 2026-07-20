"""Scout pipeline: propose report units per document, honoring uncertainty (Spec §16, §34)."""

from __future__ import annotations

import json
from typing import Any

from ask_alie.agents.schemas import ScoutResult
from ask_alie.agents.specs import load_prompt
from ask_alie.llm.client import ModelClient
from ask_alie.reports.packet import build_scout_packet
from ask_alie.tools.registry import ToolContext
from ask_alie.tools.reports import save_report_map
from ask_alie.workspace.manifest import load_manifest
from ask_alie.workspace.runlog import log_action


async def run_scout(ctx: ToolContext, client: ModelClient) -> dict[str, Any]:
    manifest = load_manifest(ctx.paths)
    system = load_prompt("scout.md")
    unit_specs: list[dict[str, Any]] = []
    uncertain_count = 0

    for doc in manifest.documents:
        packet = build_scout_packet(ctx.paths, doc.document_id)
        prompt = (
            f"Document: {doc.document_id} ({doc.page_count} pages).\n"
            "Propose report units for this page packet (JSON):\n"
            + json.dumps(packet, ensure_ascii=False)
        )
        from ask_alie import config

        result = await client.structured(
            prompt, ScoutResult, system=system, model=config.agent_model()
        )
        for unit in result.proposed_units:
            unit_specs.append(
                {
                    "document_id": doc.document_id,
                    "page_start": unit.page_start,
                    "page_end": unit.page_end,
                    "document_type": unit.document_type,
                    "title": unit.title,
                    "confidence": unit.confidence,
                    "reason": unit.reason,
                }
            )
        # uncertain seams become overlapping low-confidence fallback units (Spec §34)
        for uncertain in result.uncertain_ranges:
            uncertain_count += 1
            unit_specs.append(
                {
                    "document_id": doc.document_id,
                    "page_start": uncertain.page_start,
                    "page_end": uncertain.page_end,
                    "document_type": "uncertain",
                    "title": "Plage incertaine",
                    "confidence": "low",
                    "reason": uncertain.reason or "uncertain range (fallback unit)",
                }
            )

    saved = await save_report_map(ctx, units=unit_specs)
    log_action(
        ctx.paths,
        actor="scout",
        action="run_scout",
        result={"units": saved.get("saved_units", 0), "uncertain_ranges": uncertain_count},
    )
    return {"proposed_units": saved.get("saved_units", 0), "uncertain_ranges": uncertain_count}
