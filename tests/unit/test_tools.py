"""Tool-layer tests against the fixture workspace (PLAN P6.1)."""

import asyncio
import json
from pathlib import Path

import pytest

from ask_alie.curation.models import CurationAssignment
from ask_alie.curation.service import CuratorAssignmentDraft, CuratorResult
from ask_alie.events.store import CandidateStore
from ask_alie.ingest.ocr import NullOcrEngine
from ask_alie.ingest.service import ingest_case
from ask_alie.llm.client import MockModelClient
from ask_alie.llm.mock import HeuristicReaderMock
from ask_alie.privacy.tokenize import tokenize_case
from ask_alie.reports.map import load_report_map
from ask_alie.reports.service import create_units_from_specs
from ask_alie.tools.registry import ToolContext, all_tools, get_tool
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.paths import CasePaths

from tests.unit.test_reader_dispatch import UNIT_SPECS
from tests.unit.test_tokenize_service import KNOWN_ENTITIES

EXPECTED_TOOLS = {
    "get_case_state", "inspect_document", "read_pages", "inspect_report",
    "search_case", "list_candidates", "save_report_map", "update_report_units",
    "dispatch_readers", "create_tasks", "resolve_tasks", "run_curator", "finish_case",
}


def _call(name: str, ctx: ToolContext, **kwargs):
    return asyncio.run(get_tool(name).fn(ctx, **kwargs))


@pytest.fixture()
def ctx(fixture_pdf_dir: Path, tmp_path: Path) -> ToolContext:
    ingest_case(fixture_pdf_dir, "case_tools", tmp_path, ocr_engine=NullOcrEngine())
    paths = CasePaths.for_case(tmp_path, "case_tools")
    (paths.root / "known_entities.json").write_text(
        json.dumps(KNOWN_ENTITIES, ensure_ascii=False), encoding="utf-8"
    )
    tokenize_case(paths.root)
    create_units_from_specs(paths, UNIT_SPECS)
    return ToolContext(paths=paths, client=HeuristicReaderMock())


def test_registry_exposes_all_spec_tools() -> None:
    assert set(all_tools()) == EXPECTED_TOOLS


def test_case_state_and_dispatch_flow(ctx: ToolContext) -> None:
    state = _call("get_case_state", ctx)
    assert state["document_count"] == 2 and state["page_count"] == 8
    assert state["report_count"] == 3 and state["reports_read"] == 0
    assert set(state["reports_unread"]) == {"report_0001", "report_0002", "report_0003"}

    result = _call("dispatch_readers", ctx, report_ids=["report_0001", "report_0002"])
    assert result["completed"] == 2 and result["failed"] == 0

    state = _call("get_case_state", ctx)
    assert state["reports_read"] == 2 and state["reports_unread"] == ["report_0003"]
    assert state["candidate_count"] == result["new_candidate_events"]


def test_inspect_and_read_and_search(ctx: ToolContext) -> None:
    doc = _call("inspect_document", ctx, document_id="doc_001", page_end=2)
    assert len(doc["pages"]) == 2
    assert doc["pages"][0]["date_tokens"]

    pages = _call("read_pages", ctx, page_ids=["doc_001:p_0001"])
    assert "[[PERSON_01]]" in pages["pages"][0]["text"]
    assert "error" in _call("read_pages", ctx, page_ids=["bogus"])

    report = _call("inspect_report", ctx, report_id="report_0001", include_text=True)
    assert report["unit"]["document_type"] == "medical_consultation"
    assert "=== doc_001 page 1 ===" in report["text"]

    found = _call("search_case", ctx, query="lombalgie")
    assert found["results"] and found["results"][0]["page_id"].startswith("doc_001")


def test_update_report_units_split_invalidates(ctx: ToolContext) -> None:
    _call("dispatch_readers", ctx, report_ids=["report_0001"])
    assert (ctx.paths.readers_dir / "report_0001.result.json").exists()
    before = len(CandidateStore(ctx.paths).read_all())
    assert before > 0

    result = _call("update_report_units", ctx, operation="split",
                   report_ids=["report_0001"], split_at_page=2)
    assert result["created"] == ["report_0004", "report_0005"]

    # reader result invalidated, events flagged stale but retained
    assert not (ctx.paths.readers_dir / "report_0001.result.json").exists()
    events = CandidateStore(ctx.paths).read_all()
    assert len(events) == before
    assert all("stale_unit" in e.flags for e in events if e.report_id == "report_0001")

    units = {u.report_id: u for u in load_report_map(ctx.paths)}
    assert units["report_0001"].status == "superseded"
    assert units["report_0004"].page_ids == ["doc_001:p_0001"]
    assert units["report_0005"].page_ids == ["doc_001:p_0002"]

    merged = _call("update_report_units", ctx, operation="merge",
                   report_ids=["report_0004", "report_0005"])
    assert merged["created"] == ["report_0006"]
    units = {u.report_id: u for u in load_report_map(ctx.paths)}
    assert units["report_0006"].page_start == 1 and units["report_0006"].page_end == 2


def test_save_report_map_replaces(ctx: ToolContext) -> None:
    result = _call("save_report_map", ctx, units=[
        {"document_id": "doc_001", "page_start": 1, "page_end": 3, "document_type": "medical_consultation"},
        {"document_id": "doc_002", "page_start": 1, "page_end": 2, "document_type": "administrative_decision"},
    ])
    assert result["saved_units"] == 2
    units = load_report_map(ctx.paths)
    assert [u.report_id for u in units] == ["report_0001", "report_0002"]


def test_tasks_lifecycle(ctx: ToolContext) -> None:
    created = _call("create_tasks", ctx, requested_by="gap_agent", tasks=[
        {"action": "reread_report", "target_ids": ["report_0001"], "priority": "high",
         "reason": "six date tokens, one event"},
    ])
    assert created["created"] == ["task_0001"]
    resolved = _call("resolve_tasks", ctx, task_ids=["task_0001"], result_summary="re-read done")
    assert resolved["status"] == "done"
    assert "error" in _call("resolve_tasks", ctx, task_ids=["task_9999"])


def test_curator_and_finish(ctx: ToolContext) -> None:
    _call("dispatch_readers", ctx, report_ids=["report_0001", "report_0002", "report_0003"])
    events = CandidateStore(ctx.paths).read_all()
    # make one event a mandatory-default type the mock will try to demote
    events[0].event_type = "administrative_decision"
    CandidateStore(ctx.paths).rewrite(events)

    def curator_handler(prompt: str, schema: type) -> CuratorResult:
        payload = json.loads(prompt.split("Candidates (JSON):\n")[1])
        drafts = []
        for i, item in enumerate(payload):
            drafts.append(CuratorAssignmentDraft(
                event_id=item["event_id"],
                queue="secondary" if i % 2 == 0 else "default",
                reason="mock assignment",
            ))
        return CuratorResult(assignments=drafts[:-1])  # leave the last unassigned

    ctx.client = MockModelClient(curator_handler)
    result = _call("run_curator", ctx)
    assert result["total"] == len(events)
    assert result["forced_default"] >= 1  # the administrative_decision demotion was overridden
    assert result["unassigned_defaulted"] == 1

    assignments = JsonlStore(ctx.paths.curation_file, CurationAssignment).read_all()
    assert len(assignments) == len(events)
    forced = next(a for a in assignments if a.event_id == events[0].event_id)
    assert forced.queue == "default" and forced.needs_review

    finish = _call("finish_case", ctx)
    assert finish["events"] == len(events)
    assert not finish["warnings"]
    chronology = json.loads((ctx.paths.output_dir / "chronology.json").read_text(encoding="utf-8"))
    assert len(chronology) == len(events)
