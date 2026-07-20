from pathlib import Path

from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.manifest import create_case_workspace, load_manifest
from ask_alie.workspace.paths import CasePaths
from ask_alie.workspace.runlog import log_action
from ask_alie.workspace.tasks import AgentTask


def test_create_and_reopen_workspace(fixture_pdf_dir: Path, tmp_path: Path) -> None:
    manifest = create_case_workspace(fixture_pdf_dir, "case_test", tmp_path)

    paths = CasePaths.for_case(tmp_path, "case_test")
    assert paths.manifest.exists()
    assert (paths.source_original / "doc_001.pdf").exists()
    assert paths.report_units_dir.is_dir()
    assert paths.logs_dir.is_dir()

    assert [d.document_id for d in manifest.documents] == ["doc_001", "doc_002"]
    assert [d.page_count for d in manifest.documents] == [4, 4]
    assert manifest.documents[0].filename == "bundle_01.pdf"

    # idempotent: identical inputs return the stored manifest unchanged
    again = create_case_workspace(fixture_pdf_dir, "case_test", tmp_path)
    assert again == manifest
    assert load_manifest(paths) == manifest


def test_jsonl_store_round_trip(tmp_path: Path) -> None:
    store = JsonlStore(tmp_path / "tasks.jsonl", AgentTask)
    assert store.read_all() == []
    store.append(AgentTask(task_id="task_0001", action="reread_report"))
    store.append_many([AgentTask(task_id="task_0002", action="inspect_pages")])
    items = store.read_all()
    assert [t.task_id for t in items] == ["task_0001", "task_0002"]


def test_run_log_entry_shape(tmp_path: Path) -> None:
    paths = CasePaths.for_case(tmp_path, "case_log")
    entry = log_action(
        paths,
        actor="orchestrator",
        action="dispatch_readers",
        targets=["report_0042"],
        reason="Initial report pass",
        result={"completed": 1, "failed": 0},
    )
    assert set(entry) == {"timestamp", "actor", "action", "targets", "reason", "result"}
    assert paths.run_log.read_text(encoding="utf-8").count("\n") == 1
