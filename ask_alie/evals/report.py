"""Human-readable run summary (Spec §33: a generated run_summary.md is enough)."""

from __future__ import annotations

from ask_alie.evals.metrics import MetricsReport


def _fmt(value: object) -> str:
    return "n/a" if value is None else str(value)


def render_run_summary(report: MetricsReport) -> str:
    lines = [
        "# Run summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Gold captured | {report.gold_captured} / {report.gold_total} |",
        f"| Total candidate events | {report.total_candidates} |",
        f"| Default queue | {_fmt(report.default_queue_count)} |",
        f"| Secondary queue | {_fmt(report.secondary_queue_count)} |",
        f"| Wrong-date events | {report.wrong_date_events} |",
        f"| Uncertain matches (adjudicate) | {report.uncertain_matches} |",
        f"| Unmatched gold | {report.unmatched_gold} |",
        f"| Unmatched candidates | {report.unmatched_candidates} |",
        f"| Defensible extras | {_fmt(report.defensible_extras)} |",
        f"| Unsupported extras | {_fmt(report.unsupported_extras)} |",
        f"| Gold recovered by agentic loop | {report.recovered_gold_by_loop} |",
        f"| Loop-added candidates | {report.loop_added_candidates} |",
        f"| Review time (min) | {_fmt(report.review_time_minutes)} |",
        f"| Run cost (USD) | {_fmt(report.run_cost_usd)} |",
        f"| Run duration (s) | {_fmt(report.run_duration_seconds)} |",
        "",
        "Reference (prior Case 1 result): 50 / 74 gold captured, 187 rows emitted.",
        "",
    ]
    return "\n".join(lines)
