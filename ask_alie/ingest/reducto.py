"""Flagged Reducto AI extraction engine (ASK_ALIE_PDF_ENGINE=reducto).

Uploads a PDF to Reducto's parse API and returns per-page text. Used as an
alternative to the local native+Tesseract path — page records keep the same
shape (extraction_method="reducto"), and any page Reducto can't produce
usable text for falls back to the local pipeline.

The response parser is deliberately tolerant of schema variants (sync result,
async job polling, url-typed results); the live shakedown happens once a real
REDUCTO_API_KEY is configured.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ask_alie import config


class ReductoError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReductoPage:
    page_number: int
    text: str


class ReductoEngine:
    name = "reducto"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        client: httpx.Client | None = None,
        poll_interval: float = 2.0,
        timeout: float = 600.0,
    ):
        self.base_url = (base_url or config.reducto_base_url()).rstrip("/")
        self.poll_interval = poll_interval
        self.timeout = timeout
        self._client = client or httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"}, timeout=120.0
        )

    @classmethod
    def from_config(cls) -> ReductoEngine:
        api_key = config.reducto_api_key()
        if not api_key:
            raise ReductoError(
                "ASK_ALIE_PDF_ENGINE=reducto but REDUCTO_API_KEY is not set - "
                "add it to .env (see .env.example)"
            )
        return cls(api_key)

    # ---------- API calls ----------

    def _post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self._client.post(f"{self.base_url}{path}", **kwargs)
        if response.status_code >= 400:
            raise ReductoError(
                f"Reducto {path} failed ({response.status_code}): {response.text[:300]}"
            )
        return response.json()

    def _get(self, path_or_url: str) -> dict[str, Any]:
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        response = self._client.get(url)
        if response.status_code >= 400:
            raise ReductoError(
                f"Reducto GET failed ({response.status_code}): {response.text[:300]}"
            )
        return response.json()

    def parse_pdf(self, pdf_path: Path) -> list[ReductoPage]:
        with pdf_path.open("rb") as fh:
            uploaded = self._post("/upload", files={"file": (pdf_path.name, fh, "application/pdf")})
        document_ref = (
            uploaded.get("document_url")
            or uploaded.get("presigned_url")
            or (f"reducto://{uploaded['file_id']}" if uploaded.get("file_id") else None)
        )
        if not document_ref:
            raise ReductoError(f"Reducto upload returned no document reference: {list(uploaded)}")

        payload = self._post("/parse", json={"document_url": document_ref})
        result = self._resolve_result(payload)
        pages = self._pages_from_result(result)
        if not pages:
            raise ReductoError(f"Reducto parse returned no page content: {list(result)}")
        return pages

    def _resolve_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        # async job → poll until complete
        job_id = payload.get("job_id")
        deadline = time.monotonic() + self.timeout
        while job_id and "result" not in payload:
            if time.monotonic() > deadline:
                raise ReductoError(f"Reducto job {job_id} timed out")
            time.sleep(self.poll_interval)
            payload = self._get(f"/job/{job_id}")
            status = str(payload.get("status", "")).lower()
            if status in ("failed", "error"):
                raise ReductoError(f"Reducto job {job_id} failed: {payload}")
        result = payload.get("result", payload)
        # url-typed result → fetch the actual content
        if isinstance(result, dict) and result.get("type") == "url" and result.get("url"):
            fetched = self._get(result["url"])
            result = fetched.get("result", fetched)
        if not isinstance(result, dict):
            raise ReductoError(f"Unexpected Reducto result shape: {type(result)}")
        return result

    @staticmethod
    def _pages_from_result(result: dict[str, Any]) -> list[ReductoPage]:
        by_page: dict[int, list[str]] = {}
        chunks = result.get("chunks") or []
        for chunk in chunks:
            blocks = chunk.get("blocks") or []
            if blocks:
                for block in blocks:
                    content = (block.get("content") or "").strip()
                    if not content:
                        continue
                    bbox = block.get("bbox") or {}
                    page = int(bbox.get("page") or block.get("page") or 1)
                    by_page.setdefault(page, []).append(content)
            else:
                content = (chunk.get("content") or chunk.get("embed") or "").strip()
                if content:
                    by_page.setdefault(1, []).append(content)
        return [
            ReductoPage(page_number=page, text="\n".join(parts))
            for page, parts in sorted(by_page.items())
        ]
