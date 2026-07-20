"""Exports and review UI tests (PLAN P7.1–P7.3)."""

import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ask_alie.agents.runtime.mock import MockRuntime
from ask_alie.ingest.ocr import NullOcrEngine
from ask_alie.ingest.service import ingest_case
from ask_alie.privacy.tokenize import tokenize_case
from ask_alie.review.app import create_app
from ask_alie.review.export import export_all
from ask_alie.review.service import build_rows, record_decision, split_queues
from ask_alie.tools.registry import ToolContext
from ask_alie.workspace.paths import CasePaths

from tests.unit.test_tokenize_service import KNOWN_ENTITIES


@pytest.fixture(scope="module")
def finished_workspace(fixture_pdf_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One fully mock-orchestrated case, shared by the module's tests."""
    workspace = tmp_path_factory.mktemp("review_ws")
    ingest_case(fixture_pdf_dir, "case_ui", workspace, ocr_engine=NullOcrEngine())
    paths = CasePaths.for_case(workspace, "case_ui")
    (paths.root / "known_entities.json").write_text(
        json.dumps(KNOWN_ENTITIES, ensure_ascii=False), encoding="utf-8"
    )
    tokenize_case(paths.root)
    asyncio.run(MockRuntime().run_orchestration(ToolContext(paths=paths)))
    return workspace


@pytest.fixture()
def paths(finished_workspace: Path) -> CasePaths:
    return CasePaths.for_case(finished_workspace, "case_ui")


@pytest.fixture()
def client(finished_workspace: Path) -> TestClient:
    return TestClient(create_app(finished_workspace))


def test_export_all_files(paths: CasePaths) -> None:
    outputs = export_all(paths)
    csv_text = Path(outputs["csv"]).read_text(encoding="utf-8-sig")
    assert csv_text.splitlines()[0] == "Date,Type,Description,Auteur,Source,Page,File,Statut"
    assert "Événement daté" in csv_text

    html_text = Path(outputs["html"]).read_text(encoding="utf-8")
    assert "File principale" in html_text and "citation" in html_text

    rows = json.loads(Path(outputs["json"]).read_text(encoding="utf-8"))
    assert rows and rows[0]["event_id"]
    # sorted by restored date
    dates = [r["date"] for r in rows if r["date"]]
    assert dates == sorted(dates)


def test_case_list_and_run_screen(client: TestClient) -> None:
    home = client.get("/")
    assert home.status_code == 200 and "case_ui" in home.text

    run_screen = client.get("/case/case_ui")
    assert run_screen.status_code == 200
    assert "Activité" in run_screen.text and "run_curator" in run_screen.text


def test_progress_json(client: TestClient) -> None:
    state = client.get("/case/case_ui/progress").json()
    assert state["case_id"] == "case_ui"
    assert state["reports_read"] == state["report_count"] > 0
    assert state["candidate_count"] > 0


def test_chronology_and_reviewer_actions(client: TestClient, paths: CasePaths) -> None:
    page = client.get("/case/case_ui/chronology")
    assert page.status_code == 200 and "File principale" in page.text

    rows = build_rows(paths)
    target = rows[0]["event_id"]

    # move to secondary
    response = client.post(
        "/case/case_ui/decision",
        data={"event_id": target, "action": "move_secondary", "reason": "routine"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    moved = next(r for r in build_rows(paths) if r["event_id"] == target)
    assert moved["queue"] == "secondary"

    # edit the summary
    client.post(
        "/case/case_ui/decision",
        data={
            "event_id": target,
            "action": "edit",
            "new_summary": "Résumé corrigé par la réviseure",
            "reason": "clarté",
        },
    )
    edited = next(r for r in build_rows(paths) if r["event_id"] == target)
    assert edited["summary"] == "Résumé corrigé par la réviseure"
    assert edited["status"] == "edited"

    # reject: leaves the active queues but stays inspectable in unresolved
    client.post(
        "/case/case_ui/decision",
        data={"event_id": target, "action": "reject", "reason": "non pertinent"},
    )
    queues = split_queues(build_rows(paths))
    assert all(r["event_id"] != target for r in queues["default"] + queues["secondary"])
    assert any(r["event_id"] == target for r in queues["unresolved"])

    # decisions were appended, never overwritten
    decisions = paths.decisions_file.read_text(encoding="utf-8").splitlines()
    assert len(decisions) == 3


def test_export_via_ui(client: TestClient, paths: CasePaths) -> None:
    response = client.post("/case/case_ui/export", follow_redirects=False)
    assert response.status_code == 303
    assert (paths.output_dir / "chronology.csv").exists()


def test_record_decision_validates_action(paths: CasePaths) -> None:
    with pytest.raises(ValueError):
        record_decision(paths, "event_0001", "obliterate")
