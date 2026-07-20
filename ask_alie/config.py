"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def workspace_root() -> Path:
    return Path(os.environ.get("ASK_ALIE_WORKSPACE", "workspace"))


def tesseract_cmd() -> str | None:
    return os.environ.get("TESSERACT_CMD") or None


def anthropic_api_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY") or None
