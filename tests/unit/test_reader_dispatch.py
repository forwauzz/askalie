import asyncio
import json
from pathlib import Path

import pytest

from ask_alie.cli import main
from ask_alie.events.duplicates import link_duplicates
from ask_alie.events.models import CandidateEvent
from ask_alie.events.store import CandidateStore
from ask_alie.ingest.ocr import NullOcrEngine
from ask_alie.ingest.service import ingest_case
from ask_alie.llm.client import ClaudeModelClient, MockModelClient
from ask_alie.llm.mock import HeuristicReaderMock
from ask_alie.privacy.tokenize import tokenize_case
from ask_alie.readers.dispatcher import dispatch_readers
from ask_alie.readers.schema import ReaderResult
from ask_alie.reports.map import load_report_map
from ask_alie.reports.service import create_units_from_specs, load_report_text
from ask_alie.workspace.paths import CasePaths

from tests.unit.test_tokenize_service import KNOWN_ENTITIES

UNIT_SPECS = [
    {"document_id": "doc_001", "page_start": 1, "page_end": 2, "document_type": "medical_consultation"},
    {"document_id": "doc_001", "page_start": 3, "page_end": 3, "document_type": "imaging"},
    {"document_id": "doc_002", "page_start": 1, "page_end": 2, "document_type": "administrative_decision"},
]


@pytest.fixture()
def case_paths(fixture_pdf_dir: Path, tmp_path: Path) -> CasePaths:
    ingest_case(fixture_pdf_dir, "case_read", tmp_path, ocr_engine=NullOcrEngine())
    paths = CasePaths.for_case(tmp_path, "case_read")
    (paths.root / "known_entities.json").write_text(
        json.dumps(KNOWN_ENTITIES, ensure_ascii=False), encoding="utf-8"
    )
    tokenize_case(paths.root)
    create_units_from_specs(paths, UNIT_SPECS)
    return paths


def test_report_units_and_text_assembly(case_paths: CasePaths) -> None:
    units = load_report_map(case_paths)
    assert [u.report_id for u in units] == ["report_0001", "report_0002", "report_0003"]
    text = load_report_text(case_paths, "report_0001")
    assert "=== doc_001 page 1 ===" in text and "=== doc_001 page 2 ===" in text
    assert "[[DATE_" in text


def test_dispatch_with_heuristic_mock(case_paths: CasePaths) -> None:
    summary = asyncio.run(
        dispatch_readers(case_paths, HeuristicReaderMock(),
                         ["report_0001", "report_0002", "report_0003"])
    )
    assert summary.completed == 3 and summary.failed == 0
    assert summary.new_candidate_events > 0

    events = CandidateStore(case_paths).read_all()
    assert len(events) == summary.new_candidate_events
    for event in events:
        assert event.origin and event.origin.pass_number == 1
        assert event.origin.reason_for_pass == "initial"
        assert event.event_date or "date_unresolved" in event.flags
    # dates restored from the registry
    assert any(e.event_date == "2025-07-16" for e in events)
    assert (case_paths.readers_dir / "report_0001.result.json").exists()


def test_dispatch_retry_and_failure_surfacing(case_paths: CasePaths) -> None:
    attempts: dict[str, int] = {}

    def handler(prompt: str, schema: type) -> ReaderResult:
        report_id = next(
            rid for rid in ("report_0001", "report_0002", "report_0003") if rid in prompt
        )
        attempts[report_id] = attempts.get(report_id, 0) + 1
        if report_id == "report_0002" and attempts[report_id] < 3:
            raise ValueError("flaky schema failure")
        if report_id == "report_0003":
            raise ValueError("permanent failure")
        return ReaderResult(report_id=report_id)

    summary = asyncio.run(
        dispatch_readers(case_paths, MockModelClient(handler),
                         ["report_0001", "report_0002", "report_0003"])
    )
    # report_0002 succeeded on the simplified third attempt; report_0003 failed after 3
    assert summary.completed == 2 and summary.failed == 1
    assert attempts["report_0002"] == 3 and attempts["report_0003"] == 3
    assert summary.failures[0]["report_id"] == "report_0003"
    failures_file = case_paths.readers_dir / "failures.jsonl"
    assert "permanent failure" in failures_file.read_text(encoding="utf-8")


def test_dispatch_respects_concurrency(case_paths: CasePaths) -> None:
    active = 0
    peak = 0

    async def handler(prompt: str, schema: type) -> ReaderResult:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return ReaderResult(report_id="report_0001")

    asyncio.run(
        dispatch_readers(
            case_paths,
            MockModelClient(handler),
            ["report_0001", "report_0002", "report_0003"],
            max_concurrency=2,
        )
    )
    assert peak <= 2


def test_skill_application_is_recorded(case_paths: CasePaths) -> None:
    """report_0003 is administrative_decision → the CNESST skill applies and is logged."""
    asyncio.run(dispatch_readers(case_paths, HeuristicReaderMock(), ["report_0003"]))

    log_text = case_paths.run_log.read_text(encoding="utf-8")
    read_lines = [
        json.loads(line) for line in log_text.splitlines() if '"report_read"' in line
    ]
    assert read_lines and read_lines[-1]["result"]["skills"] == ["read-cnesst-decision"]
    assert "skill: read-cnesst-decision" in read_lines[-1]["reason"]

    events = [e for e in CandidateStore(case_paths).read_all() if e.report_id == "report_0003"]
    assert events and all(e.origin.skills == ["read-cnesst-decision"] for e in events)


def test_duplicate_linking_retains_both() -> None:
    a = CandidateEvent(
        event_id="e1", report_id="r1", event_date_token="[[DATE_AAAA]]",
        summary_fr="Consultation médicale pour lombalgie aiguë avec arrêt de travail",
    )
    b = CandidateEvent(
        event_id="e2", report_id="r2", event_date_token="[[DATE_AAAA]]",
        summary_fr="Consultation médicale pour lombalgie aiguë et arrêt de travail",
    )
    c = CandidateEvent(
        event_id="e3", report_id="r3", event_date_token="[[DATE_BBBB]]",
        summary_fr="Décision administrative de la CNESST",
    )
    links = link_duplicates([a, b, c])
    assert links == {"e2": "e1"}
    assert "duplicate_of:e1" in b.flags
    assert not a.flags and not c.flags


def test_readers_cli_mock_end_to_end(case_paths: CasePaths, capsys) -> None:
    exit_code = main(["readers", "--case", str(case_paths.root), "--mock", "--concurrency", "2"])
    assert exit_code == 0
    assert "completed 3" in capsys.readouterr().out


def test_claude_client_request_assembly() -> None:
    request = ClaudeModelClient.build_structured_request("hello", ReaderResult, system="sys")
    assert request["prompt"] == "hello"
    assert request["system_prompt"] == "sys"
    assert request["output_format"]["schema"]["title"] == "ReaderResult"
