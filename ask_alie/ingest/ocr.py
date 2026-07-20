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


PREFERRED_LANGS = ("fra", "eng")  # Spec §12.2


class TesseractEngine:
    """Shells out to the tesseract binary with the preferred installed languages."""

    name = "tesseract"

    def __init__(self, cmd: str, langs: str = "fra+eng"):
        self.cmd = cmd
        self.langs = langs
        self.available = True

    def ocr_image(self, png_path: Path) -> str:
        proc = subprocess.run(
            [self.cmd, str(png_path), "stdout", "-l", self.langs],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if proc.returncode != 0:
            raise OcrError(f"tesseract failed on {png_path.name}: {proc.stderr.strip()[:500]}")
        return proc.stdout


def installed_langs(cmd: str) -> set[str]:
    try:
        proc = subprocess.run(
            [cmd, "--list-langs"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except OSError:
        return set()
    lines = (proc.stdout + proc.stderr).splitlines()
    return {line.strip() for line in lines if line.strip() and ":" not in line}


def pick_langs(available: set[str]) -> str:
    """Preferred languages that are actually installed; eng as the last resort."""
    usable = [lang for lang in PREFERRED_LANGS if lang in available]
    return "+".join(usable) if usable else "eng"


class NullOcrEngine:
    """Used when Tesseract is not installed: pages are flagged, never dropped (Spec §34)."""

    name = "none"
    available = False

    def ocr_image(self, png_path: Path) -> str:
        raise OcrError("No OCR engine available; install Tesseract or set TESSERACT_CMD")


def default_engine() -> OcrEngine:
    cmd = config.tesseract_cmd() or shutil.which("tesseract")
    if not cmd:
        return NullOcrEngine()
    return TesseractEngine(cmd, langs=pick_langs(installed_langs(cmd)))
