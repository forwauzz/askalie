"""Scout, Gap and SDK-adapter tests (PLAN P6.2/P6.3/P6.4-gap)."""

import asyncio
import json
from pathlib import Path

import pytest

from ask_alie.agents.gap import build_gap_input, execute_tasks, run_gap_review
from ask_alie.agents.runtime.claude import (
    allowed_tool_names,
    build_agent_definitions,
    build_mcp_server,
    mcp_tool_name,
)
from ask_alie.agents.schemas import GapResult, GapTaskDraft, ScoutResult, ScoutUnit, UncertainRange
from ask_alie.agents.scout import run_scout
from ask_alie.agents.specs import AGENT_SPECS, load_prompt
from ask_alie.events.store import CandidateStore
from ask_alie.ingest.ocr import NullOcrEngine
from ask_alie.ingest.service import ingest_case
from ask_alie.llm.client import MockModelClient
from ask_alie.llm.mock import HeuristicReaderMock
from ask_alie.privacy.tokenize import tokenize_case
from ask_alie.reports.map import load_report_map
from ask_alie.reports.packet import build_scout_packet
from ask_alie.tools.registry import ToolContext, all_tools, get_tool
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.paths import CasePaths
from ask_alie.workspace.tasks import AgentTask

from tests.unit.test_tokenize_service import KNOWN_ENTITIES


@pytest.fixture()
def ctx(fixture_pdf_dir: Path, tmp_path: Path) -> ToolContext:
    ingest_case(fixture_pdf_dir, "case_agents", tmp_path, ocr_engine=NullOcrEngine())
    paths = CasePaths.for_case(tmp_path, "case_agents")
    (paths.root / "known_entities.json").write_text(
        json.dumps(KNOWN_ENTITIES, ensure_ascii=False), encoding="utf-8"
    )
    tokenize_case(paths.root)
    return ToolContext(paths=paths, client=HeuristicReaderMock())


def test_scout_packet_shape(ctx: ToolContext) -> None:
    packet = build_scout_packet(ctx.paths, "doc_001")
    assert [p["page"] for p in packet] == [1, 2, 3, 4]
    assert "[[PERSON_01]]" in packet[0]["head"]


def test_scout_saves_map_with_uncertain_fallback(ctx: ToolContext) -> None:
    def scout_handler(prompt: str, schema: type) -> ScoutResult:
        document_id = "doc_001" if "doc_001" in prompt else "doc_002"
        if document_id == "doc_001":
            return ScoutResult(
                document_id=document_id,
                proposed_units=[
                    ScoutUnit(page_start=1, page_end=2, document_type="medical_consultation",
                              title="Consultation", confidence="high", reason="header+signature"),
                    ScoutUnit(page_start=3, page_end=3, document_type="imaging",
                              title="IRM", confidence="high", reason="imaging header"),
                    ScoutUnit(page_start=4, page_end=4, document_type="empty",
                              title="Page vide", confidence="high", reason="blank"),
                ],
            )
        return ScoutResult(
            document_id=document_id,
            proposed_units=[
                ScoutUnit(page_start=1, page_end=2, document_type="administrative_decision",
                          title="Décision CNESST", confidence="high", reason="CNESST letterhead"),
            ],
            uncertain_ranges=[UncertainRange(page_start=3, page_end=4, reason="scan + garbage seam")],
        )

    result = asyncio.run(run_scout(ctx, MockModelClient(scout_handler)))
    assert result["proposed_units"] == 5  # 4 proposed + 1 fallback
    assert result["uncertain_ranges"] == 1
    units = load_report_map(ctx.paths)
    fallback = [u for u in units if u.document_type == "uncertain"]
    assert len(fallback) == 1
    assert fallback[0].boundary_confidence == "low"
    # every unit's text was assembled
    for unit in units:
        assert (ctx.paths.report_units_dir / f"{unit.report_id}.safe.txt").exists()


def _prepare_read_case(ctx: ToolContext) -> None:
    from ask_alie.reports.service import create_units_from_specs
    from tests.unit.test_reader_dispatch import UNIT_SPECS

    create_units_from_specs(ctx.paths, UNIT_SPECS)
    asyncio.run(get_tool("dispatch_readers").fn(
        ctx, report_ids=["report_0001", "report_0002", "report_0003"]
    ))


def test_gap_input_facts(ctx: ToolContext) -> None:
    _prepare_read_case(ctx)
    # add a zero-event unit over the blank page
    from ask_alie.reports.service import create_units_from_specs

    create_units_from_specs(ctx.paths, [
        {"document_id": "doc_001", "page_start": 4, "page_end": 4, "document_type": "empty"},
    ])
    asyncio.run(get_tool("dispatch_readers").fn(ctx, report_ids=["report_0004"]))

    facts = build_gap_input(ctx)
    by_id = {r["report_id"]: r for r in facts["reports"]}
    assert by_id["report_0004"]["read"] and by_id["report_0004"]["event_count"] == 0
    assert by_id["report_0001"]["date_tokens_in_text"] > 0
    assert by_id["report_0001"]["uncited_date_tokens"] == []  # heuristic mock cites every token


def test_gap_review_creates_and_executes_reread(ctx: ToolContext) -> None:
    _prepare_read_case(ctx)
    before = len(CandidateStore(ctx.paths).read_all())

    def gap_handler(prompt: str, schema: type) -> GapResult:
        return GapResult(
            tasks=[
                GapTaskDraft(action="reread_report", target_ids=["report_0001"], priority="high",
                             reason="uncited work-status change",
                             instructions="Extract work-stoppage periods"),
                GapTaskDraft(action="resegment", target_ids=["report_0003"], priority="medium",
                             reason="two signature blocks"),
            ],
            assessment="First pass likely incomplete for work status.",
        )

    review = asyncio.run(run_gap_review(ctx, MockModelClient(gap_handler)))
    assert len(review["tasks_created"]) == 2

    executed = asyncio.run(execute_tasks(ctx))
    assert len(executed["executed"]) == 1
    assert executed["pending"]  # resegment left for the orchestrator

    events = CandidateStore(ctx.paths).read_all()
    recovered = [e for e in events if e.origin and e.origin.pass_number == 2]
    assert len(events) > before and recovered
    assert all(e.origin.reason_for_pass == "gap_reread" for e in recovered)

    tasks = {t.task_id: t for t in JsonlStore(ctx.paths.tasks_file, AgentTask).read_all()}
    assert tasks["task_0001"].status == "done"
    assert tasks["task_0002"].status == "pending"


def test_reread_pass_limit_enforced(ctx: ToolContext) -> None:
    _prepare_read_case(ctx)
    store = CandidateStore(ctx.paths)
    events = store.read_all()
    for event in events:
        if event.report_id == "report_0001" and event.origin:
            event.origin.pass_number = 3  # already at the Spec §15.4 limit
    store.rewrite(events)

    asyncio.run(get_tool("create_tasks").fn(ctx, tasks=[
        {"action": "reread_report", "target_ids": ["report_0001"], "priority": "high"},
    ], requested_by="gap_agent"))
    executed = asyncio.run(execute_tasks(ctx))
    assert executed["skipped"]
    tasks = JsonlStore(ctx.paths.tasks_file, AgentTask).read_all()
    assert tasks[-1].status == "skipped"


def test_claude_adapter_generation(ctx: ToolContext) -> None:
    server = build_mcp_server(ctx)
    assert server is not None

    definitions = build_agent_definitions()
    assert set(definitions) == set(AGENT_SPECS) == {"scout", "gap-reviewer", "curator"}
    scout_def = definitions["scout"]
    assert scout_def.tools == [
        mcp_tool_name(n) for n in ("inspect_document", "read_pages", "save_report_map")
    ]
    assert "Scout" in scout_def.prompt

    allowed = allowed_tool_names()
    assert "Agent" in allowed
    assert set(allowed) == {"Agent"} | {mcp_tool_name(n) for n in all_tools()}


def test_all_prompts_load() -> None:
    for filename in ("orchestrator.md", "scout.md", "gap.md", "curator.md", "reader.md"):
        assert load_prompt(filename).strip()
