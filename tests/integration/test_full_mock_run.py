"""Full mock orchestration end-to-end (PLAN P6.5 exit criterion)."""

import asyncio
import json
from pathlib import Path

import pytest

from ask_alie.agents.runtime.mock import MockRuntime
from ask_alie.cli import main
from ask_alie.curation.models import CurationAssignment
from ask_alie.events.store import CandidateStore
from ask_alie.ingest.ocr import NullOcrEngine
from ask_alie.ingest.service import ingest_case
from ask_alie.privacy.tokenize import tokenize_case
from ask_alie.tools.registry import ToolContext
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.manifest import load_manifest
from ask_alie.workspace.paths import CasePaths

from tests.unit.test_tokenize_service import KNOWN_ENTITIES


@pytest.fixture()
def prepared_case(fixture_pdf_dir: Path, tmp_path: Path) -> CasePaths:
    ingest_case(fixture_pdf_dir, "case_full", tmp_path, ocr_engine=NullOcrEngine())
    paths = CasePaths.for_case(tmp_path, "case_full")
    (paths.root / "known_entities.json").write_text(
        json.dumps(KNOWN_ENTITIES, ensure_ascii=False), encoding="utf-8"
    )
    tokenize_case(paths.root)
    return paths


def test_mock_runtime_full_case(prepared_case: CasePaths) -> None:
    progress_lines: list[str] = []
    result = asyncio.run(
        MockRuntime().run_orchestration(
            ToolContext(paths=prepared_case), progress=progress_lines.append
        )
    )
    assert result.status == "finished" and result.runtime == "mock"
    assert any("Scout" in line for line in progress_lines)

    detail = result.detail
    assert detail["scout"]["proposed_units"] >= 3
    assert detail["dispatch"]["failed"] == 0
    # the gap loop ran and recovered something on a second pass
    assert detail["gap_iterations"][0]["tasks_created"] == 1
    events = CandidateStore(prepared_case).read_all()
    assert any(e.origin and e.origin.pass_number == 2 for e in events)

    # every event curated, chronology written, case finished
    assignments = JsonlStore(prepared_case.curation_file, CurationAssignment).read_all()
    assert len(assignments) == len(events) > 0
    chronology = json.loads(
        (prepared_case.output_dir / "chronology.json").read_text(encoding="utf-8")
    )
    assert len(chronology) == len(events)
    assert not detail["finish"]["warnings"]
    assert load_manifest(prepared_case).run_status == "finished"


def test_run_cli_mock(prepared_case: CasePaths, capsys: pytest.CaptureFixture) -> None:
    assert main(["run", "--case", str(prepared_case.root), "--mock"]) == 0
    out = capsys.readouterr().out
    assert "run finished (mock runtime)" in out


def test_run_cli_openai_stub(prepared_case: CasePaths, capsys: pytest.CaptureFixture) -> None:
    assert main(["run", "--case", str(prepared_case.root), "--runtime", "openai"]) == 1
    assert "stub" in capsys.readouterr().out


def test_doctor_cli(capsys: pytest.CaptureFixture) -> None:
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "claude-agent-sdk importable" in out
    assert "Tesseract" in out
