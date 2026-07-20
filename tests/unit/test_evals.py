"""Evaluation harness tests with hand-computed expectations (PLAN P5.1/P5.2)."""

import re
from pathlib import Path

from ask_alie.cli import main
from ask_alie.evals.gold import GoldEvent
from ask_alie.evals.match import match_events
from ask_alie.evals.metrics import compute_metrics, evaluate_case
from ask_alie.events.models import CandidateEvent, EventOrigin
from ask_alie.events.store import CandidateStore
from ask_alie.workspace.jsonl import JsonlStore
from ask_alie.workspace.paths import CasePaths

GOLD = [
    GoldEvent(
        gold_event_id="g1",
        date="2025-07-16",
        description="Consultation médicale pour recrudescence de lombalgie avec arrêt de travail",
        key_facts=["lombalgie", "arrêt de travail"],
    ),
    GoldEvent(
        gold_event_id="g2",
        date="2025-07-22",
        description="IRM lombaire montrant une protrusion discale L4-L5 droite",
        key_facts=["protrusion discale", "L4-L5"],
    ),
    GoldEvent(
        gold_event_id="g3",
        date="2025-08-05",
        description="Décision CNESST acceptant la récidive rechute aggravation",
        key_facts=["CNESST", "récidive", "aggravation"],
    ),
    GoldEvent(
        gold_event_id="g4",
        date="2025-09-01",
        description="Chirurgie de discectomie L4-L5",
        key_facts=["discectomie"],
    ),
]


def _candidate(event_id: str, date: str | None, summary: str, pass_number: int = 1) -> CandidateEvent:
    return CandidateEvent(
        event_id=event_id,
        report_id="report_0001",
        event_date_token="[[DATE_XXXX]]",
        event_date=date,
        summary_fr=summary,
        origin=EventOrigin(reader_run_id="r", pass_number=pass_number),
    )


CANDIDATES = [
    # full match for g1
    _candidate("e1", "2025-07-16", "Consultation médicale pour recrudescence de lombalgie, arrêt de travail prescrit"),
    # wrong-date full match for g2 (right meaning, wrong day)
    _candidate("e2", "2025-07-23", "IRM lombaire : protrusion discale L4-L5 droite avec conflit radiculaire"),
    # partial/uncertain same-date match for g3, recovered by the loop (pass 2)
    _candidate("e3", "2025-08-05", "Décision de la CNESST concernant la réclamation du travailleur", pass_number=2),
    # unmatched extra
    _candidate("e4", "2025-10-01", "Renouvellement de prescription sans changement"),
]


def test_matching_classifications() -> None:
    matches = match_events(GOLD, CANDIDATES)
    by_gold = {m.gold_event_id: m for m in matches}

    assert by_gold["g1"].date_match and by_gold["g1"].meaning_match == "full"
    assert by_gold["g1"].candidate_event_id == "e1"

    assert not by_gold["g2"].date_match and by_gold["g2"].meaning_match == "full"
    assert by_gold["g2"].notes == "wrong date"

    assert by_gold["g3"].date_match and by_gold["g3"].meaning_match == "partial"
    assert by_gold["g3"].needs_adjudication

    assert by_gold["g4"].candidate_event_id is None  # miss


def test_metrics_hand_computed() -> None:
    matches = match_events(GOLD, CANDIDATES)
    report = compute_metrics(GOLD, CANDIDATES, matches, assignments=[])

    assert report.gold_total == 4
    assert report.gold_captured == 1  # only g1 is date+meaning full
    assert report.total_candidates == 4
    assert report.wrong_date_events == 1  # g2
    assert report.uncertain_matches == 1  # g3
    assert report.unmatched_gold == 1  # g4
    assert report.unmatched_candidates == 1  # e4
    assert report.recovered_gold_by_loop == 0  # e3 is partial, not captured
    assert report.loop_added_candidates == 1  # e3 has pass_number 2
    assert report.default_queue_count is None  # no curation yet → n/a
    assert report.defensible_extras is None  # manual adjudication


def test_evaluate_case_writes_artifacts(tmp_path: Path, capsys) -> None:
    paths = CasePaths.for_case(tmp_path, "case_eval")
    paths.create_tree()
    CandidateStore(paths).append_events(CANDIDATES)
    gold_path = tmp_path / "gold_events.jsonl"
    JsonlStore(gold_path, GoldEvent).append_many(GOLD)

    exit_code = main(["evaluate", "--case", str(paths.root), "--gold", str(gold_path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "| Gold captured | 1 / 4 |" in out

    assert (paths.eval_dir / "metrics.json").exists()
    assert (paths.eval_dir / "run_summary.md").exists()
    matches_lines = (paths.eval_dir / "matches.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(matches_lines) == 4

    # re-running does not duplicate matches (file is rewritten)
    evaluate_case(paths, gold_path)
    assert len((paths.eval_dir / "matches.jsonl").read_text(encoding="utf-8").splitlines()) == 4


def test_gold_isolation_guard() -> None:
    """Spec §28.2: only the eval layer may import the gold loader."""
    package = Path(__file__).resolve().parents[2] / "ask_alie"
    pattern = re.compile(r"evals\.gold|from ask_alie\.evals import gold")
    offenders = [
        str(path.relative_to(package))
        for path in package.rglob("*.py")
        if package / "evals" not in path.parents and pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"gold loader imported outside evals/: {offenders}"
