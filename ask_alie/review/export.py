"""Chronology exports: JSON, CSV and a self-contained HTML file (Spec §27)."""

from __future__ import annotations

import csv
import html
import json
from typing import Any

from ask_alie.review.service import build_rows, split_queues
from ask_alie.workspace.paths import CasePaths

_CSV_COLUMNS = ["Date", "Type", "Description", "Auteur", "Source", "Page", "File", "Statut"]


def export_all(paths: CasePaths) -> dict[str, str]:
    rows = build_rows(paths)
    queues = split_queues(rows)
    paths.output_dir.mkdir(parents=True, exist_ok=True)

    json_path = paths.output_dir / "chronology.json"
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = paths.output_dir / "chronology.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(_CSV_COLUMNS)
        for row in queues["default"] + queues["secondary"]:
            writer.writerow(
                [
                    row["date"] or "date non résolue",
                    row["event_type"],
                    row["summary"],
                    row["author"] or "",
                    row["report_id"],
                    ", ".join(str(p) for p in row["source_pages"]),
                    row["queue"],
                    row["status"],
                ]
            )

    html_path = paths.output_dir / "chronology.html"
    html_path.write_text(_render_html(queues), encoding="utf-8")
    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "html": str(html_path),
    }


def _table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>Aucun événement.</p>"
    cells = []
    for row in rows:
        quote = html.escape(row["quote"] or "")
        pages = ", ".join(str(p) for p in row["source_pages"])
        cells.append(
            "<tr>"
            f"<td>{html.escape(row['date'] or 'date non résolue')}</td>"
            f"<td>{html.escape(row['event_type'])}</td>"
            f"<td>{html.escape(row['summary'])}"
            + (
                f"<details><summary>citation (p. {row['quote_page']})</summary>"
                f"<blockquote>{quote}</blockquote></details>"
                if quote
                else ""
            )
            + "</td>"
            f"<td>{html.escape(row['author'] or '')}</td>"
            f"<td>{html.escape(row['report_id'])} p. {pages}</td>"
            f"<td>{html.escape(row['status'])}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Date</th><th>Type</th><th>Description</th>"
        "<th>Auteur</th><th>Source</th><th>Statut</th></tr></thead><tbody>"
        + "".join(cells)
        + "</tbody></table>"
    )


def _render_html(queues: dict[str, list[dict[str, Any]]]) -> str:
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Chronologie Ask ALIE</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ background: #f0f0f0; }}
blockquote {{ margin: 4px 0; padding-left: 8px; border-left: 3px solid #999; color: #444; }}
h2 {{ margin-top: 2rem; }}
</style></head><body>
<h1>Chronologie — Ask ALIE (POC)</h1>
<h2>File principale ({len(queues["default"])})</h2>
{_table(queues["default"])}
<h2>File secondaire ({len(queues["secondary"])})</h2>
{_table(queues["secondary"])}
<h2>Non résolu / à réviser ({len(queues["unresolved"])})</h2>
{_table(queues["unresolved"])}
</body></html>
"""
