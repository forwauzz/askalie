"""OCR engine seam (PLAN §3): Tesseract when present, graceful null fallback."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from ask_alie import config


class OcrError(RuntimeError):
    pass


class OcrEngine(Protocol):
    name: str
    available: bool

    def ocr_image(self, png_path: Path) -> str: ...


class TesseractEngine:
    """Shells out to the tesseract binary with fra+eng (Spec §12.2)."""

    name = "tesseract"

    def __init__(self, cmd: str):
        self.cmd = cmd
        self.available = True

    def ocr_image(self, png_path: Path) -> str:
        proc = subprocess.run(
            [self.cmd, str(png_path), "stdout", "-l", "fra+eng"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if proc.returncode != 0:
            raise OcrError(f"tesseract failed on {png_path.name}: {proc.stderr.strip()[:500]}")
        return proc.stdout


class NullOcrEngine:
    """Used when Tesseract is not installed: pages are flagged, never dropped (Spec §34)."""

    name = "none"
    available = False

    def ocr_image(self, png_path: Path) -> str:
        raise OcrError("No OCR engine available; install Tesseract or set TESSERACT_CMD")


def default_engine() -> OcrEngine:
    cmd = config.tesseract_cmd() or shutil.which("tesseract")
    return TesseractEngine(cmd) if cmd else NullOcrEngine()
