from ask_alie.privacy.entities import find_entities
from ask_alie.privacy.registry import DateRegistry, EntityRegistry

KNOWN = {
    "persons": ["Jean Tremblay"],
    "providers": ["Marie Gagnon"],
    "employers": ["Entrepôt Fictif inc."],
}


def test_pattern_recognizers() -> None:
    text = (
        "Patient : Jean Tremblay, NAM : TREJ 8001 0512, tél. 514 555-0182, "
        "courriel jean@example.com, code postal H2X 1Y4. Dossier CNESST : 123456789."
    )
    matches = find_entities(text, KNOWN)
    categories = {m.category for m in matches}
    assert {"PERSON", "RAMQ", "PHONE", "EMAIL", "POSTAL", "CLAIM"} <= categories
    claim = next(m for m in matches if m.category == "CLAIM")
    assert claim.value == "123456789"


def test_dictionary_names_case_insensitive() -> None:
    matches = find_entities("vu par la Dre MARIE GAGNON aujourd'hui", KNOWN)
    assert any(m.category == "PROVIDER" for m in matches)


def test_entity_tokens_stable_across_pages() -> None:
    registry = EntityRegistry()
    token_page1 = registry.token_for("PERSON", "Jean Tremblay")
    registry.token_for("PROVIDER", "Marie Gagnon")
    token_page2 = registry.token_for("PERSON", "jean tremblay")  # casefold-stable
    assert token_page1 == token_page2 == "[[PERSON_01]]"
    assert registry.resolve("[[PERSON_01]]") == "Jean Tremblay"


def test_registry_save_load_round_trip(tmp_path) -> None:
    registry = EntityRegistry()
    registry.token_for("PERSON", "Jean Tremblay")
    registry.save(tmp_path / "e.json")
    loaded = EntityRegistry.load(tmp_path / "e.json")
    assert loaded.token_for("PERSON", "Jean Tremblay") == "[[PERSON_01]]"
    assert loaded.token_for("PERSON", "Autre Personne") == "[[PERSON_02]]"

    dates = DateRegistry()
    token = dates.token_for("2025-07-16")
    dates.save(tmp_path / "d.json")
    reloaded = DateRegistry.load(tmp_path / "d.json")
    assert reloaded.token_for("2025-07-16") == token
    assert reloaded.resolve(token) == "2025-07-16"


def test_date_tokens_deterministic_and_opaque() -> None:
    a, b = DateRegistry(), DateRegistry()
    assert a.token_for("2025-07-16") == b.token_for("2025-07-16")
    assert a.token_for("2025-07-16") != a.token_for("2025-07-17")
