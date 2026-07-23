"""Flagged Reducto pipeline tests — fully offline via httpx.MockTransport."""

import json
from pathlib import Path

import httpx
import pytest

from ask_alie.ingest.ocr import NullOcrEngine
from ask_alie.ingest.reducto import ReductoEngine, ReductoError, ReductoPage
from ask_alie.ingest.service import ingest_case, load_page_records
from ask_alie.workspace.paths import CasePaths

from tests.fixtures.make_fixtures import CONSULTATION_P1, DECISION_P2


def _engine(handler) -> ReductoEngine:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://platform.reducto.ai")
    return ReductoEngine(api_key="test", client=client, poll_interval=0.01)


def test_parse_pdf_sync_result(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-fake")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            return httpx.Response(200, json={"file_id": "abc123"})
        if request.url.path == "/parse":
            body = json.loads(request.content)
            assert body["document_url"] == "reducto://abc123"
            return httpx.Response(200, json={
                "result": {
                    "type": "full",
                    "chunks": [
                        {"blocks": [
                            {"content": "Page un contenu.", "bbox": {"page": 1}},
                            {"content": "Suite page un.", "bbox": {"page": 1}},
                            {"content": "Page deux contenu.", "bbox": {"page": 2}},
                        ]},
                    ],
                }
            })
        raise AssertionError(f"unexpected call {request.url.path}")

    pages = _engine(handler).parse_pdf(pdf)
    assert [p.page_number for p in pages] == [1, 2]
    assert pages[0].text == "Page un contenu.\nSuite page un."


def test_parse_pdf_polls_async_job(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-fake")
    calls = {"job": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload":
            return httpx.Response(200, json={"document_url": "https://signed.example/x"})
        if request.url.path == "/parse":
            return httpx.Response(200, json={"job_id": "job-1", "status": "pending"})
        if request.url.path == "/job/job-1":
            calls["job"] += 1
            if calls["job"] < 2:
                return httpx.Response(200, json={"job_id": "job-1", "status": "running"})
            return httpx.Response(200, json={
                "status": "completed",
                "result": {"chunks": [{"blocks": [{"content": "Texte.", "bbox": {"page": 1}}]}]},
            })
        raise AssertionError(f"unexpected call {request.url.path}")

    pages = _engine(handler).parse_pdf(pdf)
    assert pages == [ReductoPage(page_number=1, text="Texte.")]
    assert calls["job"] == 2


def test_parse_errors_are_clear(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-fake")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")

    with pytest.raises(ReductoError, match="401"):
        _engine(handler).parse_pdf(pdf)


def test_from_config_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDUCTO_API_KEY", raising=False)
    with pytest.raises(ReductoError, match="REDUCTO_API_KEY"):
        ReductoEngine.from_config()


class StubReducto:
    """Returns usable text for bundle_01 pages 1-2 only; rest falls back locally."""

    def parse_pdf(self, pdf_path: Path):
        if "doc_001" not in pdf_path.name:
            raise ReductoError("stub: parse unavailable for this document")
        return [
            ReductoPage(page_number=1, text=CONSULTATION_P1),
            ReductoPage(page_number=2, text=DECISION_P2),
        ]


def test_ingest_with_reducto_flag(fixture_pdf_dir: Path, tmp_path: Path) -> None:
    _, summary = ingest_case(
        fixture_pdf_dir, "case_reducto", tmp_path,
        ocr_engine=NullOcrEngine(), pdf_engine="reducto", reducto_engine=StubReducto(),
    )
    assert summary.reducto_pages == 2
    # everything else fell back to the local pipeline
    assert summary.native_pages == 3 and summary.total_pages == 8
    assert "reducto parsed   2" in summary.render()

    paths = CasePaths.for_case(tmp_path, "case_reducto")
    records = load_page_records(paths, "doc_001") + load_page_records(paths, "doc_002")
    methods = {r.page_id: r.extraction_method for r in records}
    assert methods["doc_001:p_0001"] == "reducto"
    assert methods["doc_001:p_0002"] == "reducto"
    assert methods["doc_001:p_0003"] == "native"
    fallback_flagged = [r for r in records if "reducto_fallback" in r.flags]
    assert fallback_flagged  # local pages are marked as fallbacks under the flag
    # doc_002 whole-document failure was logged, pages still processed
    log_text = paths.run_log.read_text(encoding="utf-8")
    assert "reducto_failed" in log_text


def test_ingest_reducto_flag_without_key_fails_fast(
    fixture_pdf_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("REDUCTO_API_KEY", raising=False)
    with pytest.raises(ReductoError, match="REDUCTO_API_KEY"):
        ingest_case(
            fixture_pdf_dir, "case_reducto_nokey", tmp_path,
            ocr_engine=NullOcrEngine(), pdf_engine="reducto",
        )
