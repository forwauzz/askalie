"""Agent Skills tests (Spec §25, PLAN Experiment 5 machinery)."""

import pytest

from ask_alie.agents.skills import load_skills, skills_for
from ask_alie.readers.runner import reader_system_prompt


def test_load_first_skill() -> None:
    skills = {s.name: s for s in load_skills()}
    assert "read-cnesst-decision" in skills
    skill = skills["read-cnesst-decision"]
    assert "administrative_decision" in skill.applies_to
    assert "Never use the accident date as the decision date." in skill.body
    assert "CNESST" in skill.description


def test_skills_match_by_document_type() -> None:
    assert [s.name for s in skills_for("administrative_decision")] == ["read-cnesst-decision"]
    assert skills_for("imaging") == []
    assert skills_for(None) == []


def test_reader_system_prompt_includes_matching_skill() -> None:
    with_skill = reader_system_prompt("administrative_decision")
    assert "## Skill: read-cnesst-decision" in with_skill
    assert "accepted and rejected diagnoses" in with_skill
    without = reader_system_prompt("imaging")
    assert "## Skill:" not in without


def test_skills_global_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASK_ALIE_SKILLS", "off")
    assert "## Skill:" not in reader_system_prompt("administrative_decision")
    monkeypatch.setenv("ASK_ALIE_SKILLS", "on")
    assert "## Skill:" in reader_system_prompt("administrative_decision")
