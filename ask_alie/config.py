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


def reader_model() -> str:
    """High-volume reader calls: cheap tier by default (Spec §23.4)."""
    return os.environ.get("ASK_ALIE_READER_MODEL", "haiku")


def agent_model() -> str:
    """Scout / Gap / Curator judgment calls: capable tier."""
    return os.environ.get("ASK_ALIE_AGENT_MODEL", "sonnet")


def skills_enabled() -> bool:
    """Agent Skills toggle (Spec §25); set ASK_ALIE_SKILLS=off for A/B pilots."""
    return os.environ.get("ASK_ALIE_SKILLS", "on").lower() != "off"
