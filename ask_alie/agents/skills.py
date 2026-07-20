"""Filesystem Agent Skills (Spec §25): reusable extraction methods.

Skills live in .claude/skills/<name>/SKILL.md with simple frontmatter
(name, description, applies_to). A skill whose applies_to matches the
report unit's document type is appended to the reader's system prompt.
Toggle globally with ASK_ALIE_SKILLS=off (used for A/B pilots).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "skills"


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    applies_to: tuple[str, ...] = field(default_factory=tuple)
    body: str = ""


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: dict[str, object] = {}
    body_start = len(lines)
    key: str | None = None
    for index, line in enumerate(lines[1:], start=1):
        stripped = line.strip()
        if stripped == "---":
            body_start = index + 1
            break
        if stripped.startswith("- ") and key:
            meta.setdefault(key, [])
            if isinstance(meta[key], list):
                meta[key].append(stripped[2:].strip())
        elif ":" in stripped and not line.startswith(" "):
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            meta[key] = [] if value in ("", ">", "|") else value
        elif key and isinstance(meta.get(key), str):
            meta[key] = f"{meta[key]} {stripped}".strip()
        elif key and isinstance(meta.get(key), list) and stripped and not stripped.startswith("- "):
            # folded multiline scalar (">"): accumulate into a string
            meta[key] = stripped if not meta[key] else meta[key]
    return meta, "\n".join(lines[body_start:])


def load_skills(skills_dir: Path | None = None) -> list[Skill]:
    directory = skills_dir or SKILLS_DIR
    skills: list[Skill] = []
    if not directory.is_dir():
        return skills
    for skill_file in sorted(directory.glob("*/SKILL.md")):
        meta, body = _parse_frontmatter(skill_file.read_text(encoding="utf-8"))
        applies = meta.get("applies_to") or []
        skills.append(
            Skill(
                name=str(meta.get("name") or skill_file.parent.name),
                description=str(meta.get("description") or ""),
                applies_to=tuple(applies) if isinstance(applies, list) else (str(applies),),
                body=body.strip(),
            )
        )
    return skills


def skills_for(document_type: str | None, skills_dir: Path | None = None) -> list[Skill]:
    if not document_type:
        return []
    normalized = document_type.strip().lower()
    return [s for s in load_skills(skills_dir) if normalized in s.applies_to]
