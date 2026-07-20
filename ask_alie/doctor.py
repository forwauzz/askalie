"""Environment prerequisite checks for live runs (PLAN PL.1)."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from ask_alie import config

CASE1_INPUTS = Path(r"C:\Dev\ALIE\chrono-lab\bundles\case1_cnesst\inputs")
CASE1_GOLD = Path(r"C:\Dev\ALIE\chrono-lab\bundles\case1_cnesst\normalized\gold_events.jsonl")


def run_checks() -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    checks.append(
        (
            "Python >= 3.12",
            sys.version_info >= (3, 12),
            f"found {sys.version_info.major}.{sys.version_info.minor}",
        )
    )

    from ask_alie.llm.client import sdk_available

    ok, detail = sdk_available()
    checks.append(("claude-agent-sdk importable", ok, detail))

    checks.append(
        (
            "ANTHROPIC_API_KEY",
            bool(config.anthropic_api_key()),
            "set" if config.anthropic_api_key() else "missing - copy .env.example to .env",
        )
    )

    tesseract = config.tesseract_cmd() or shutil.which("tesseract")
    checks.append(
        (
            "Tesseract OCR",
            bool(tesseract),
            tesseract or "not found - winget install UB-Mannheim.TesseractOCR (fra+eng packs)",
        )
    )
    if tesseract:
        from ask_alie.ingest.ocr import installed_langs

        langs = installed_langs(tesseract)
        checks.append(
            (
                "Tesseract 'fra' language pack",
                "fra" in langs,
                f"installed langs: {', '.join(sorted(langs)) or 'none'}"
                + (
                    ""
                    if "fra" in langs
                    else " - French OCR degraded; add fra.traineddata to the tessdata folder"
                ),
            )
        )

    checks.append(
        (
            "Case 1 bundle",
            CASE1_INPUTS.is_dir(),
            str(CASE1_INPUTS) if CASE1_INPUTS.is_dir() else f"not found at {CASE1_INPUTS}",
        )
    )
    checks.append(
        (
            "Case 1 gold file",
            CASE1_GOLD.is_file(),
            str(CASE1_GOLD) if CASE1_GOLD.is_file() else f"not found at {CASE1_GOLD}",
        )
    )
    return checks


def render_checks(checks: list[tuple[str, bool, str]]) -> str:
    lines = []
    for name, ok, detail in checks:
        status = "OK     " if ok else "MISSING"
        lines.append(f"[{status}] {name}: {detail}")
    missing = sum(1 for _, ok, _ in checks if not ok)
    lines.append(
        "All live prerequisites satisfied."
        if missing == 0
        else f"{missing} prerequisite(s) missing - offline build and --mock runs are unaffected."
    )
    return "\n".join(lines)
