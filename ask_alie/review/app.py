"""Local review UI (Spec §27): FastAPI, server-rendered, no build step.

Pages are rendered with small helper functions instead of template files to
keep packaging trivial. POC quality by design (Spec §3.3).
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from ask_alie.review.export import export_all
from ask_alie.review.service import REVIEW_ACTIONS, build_rows, record_decision, split_queues
from ask_alie.tools.registry import ToolContext, get_tool
from ask_alie.workspace.manifest import load_manifest
from ask_alie.workspace.paths import CasePaths

_STYLE = """
body { font-family: system-ui, sans-serif; margin: 1.5rem; color: #1a1a1a; max-width: 1200px; }
table { border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }
th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left; vertical-align: top; }
th { background: #f0f0f0; }
nav a { margin-right: 1rem; }
form.inline { display: inline; }
select, input[type=text] { max-width: 220px; }
blockquote { margin: 4px 0; padding-left: 8px; border-left: 3px solid #999; color: #444; }
.pill { background: #eee; border-radius: 8px; padding: 1px 8px; font-size: 0.85em; }
"""


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body><h1>{html.escape(title)}</h1>{body}</body></html>"
    )


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def create_app(workspace_root: Path) -> FastAPI:
    app = FastAPI(title="Ask ALIE review")
    cases_dir = workspace_root / "cases"

    def paths_for(case_id: str) -> CasePaths:
        return CasePaths.for_case(workspace_root, case_id)

    @app.get("/", response_class=HTMLResponse)
    async def case_list() -> HTMLResponse:
        rows = []
        for case_dir in sorted(cases_dir.iterdir()) if cases_dir.is_dir() else []:
            manifest_path = case_dir / "manifest.json"
            if not manifest_path.is_file():
                continue
            manifest = load_manifest(CasePaths(root=case_dir))
            pages = sum(d.page_count for d in manifest.documents)
            rows.append(
                f"<tr><td><a href='/case/{manifest.case_id}'>{_esc(manifest.case_id)}</a></td>"
                f"<td>{_esc(manifest.run_status)}</td><td>{len(manifest.documents)}</td>"
                f"<td>{pages}</td><td>{_esc(manifest.configuration)}</td>"
                f"<td>{_esc(manifest.created_at[:19])}</td></tr>"
            )
        body = (
            "<table><thead><tr><th>Cas</th><th>Statut</th><th>Documents</th><th>Pages</th>"
            "<th>Configuration</th><th>Créé</th></tr></thead><tbody>"
            + ("".join(rows) or "<tr><td colspan='6'>Aucun cas.</td></tr>")
            + "</tbody></table>"
        )
        return _page("Ask ALIE — cas", body)

    @app.get("/case/{case_id}/progress")
    async def progress(case_id: str) -> dict[str, Any]:
        return await get_tool("get_case_state").fn(ToolContext(paths=paths_for(case_id)))

    @app.get("/case/{case_id}", response_class=HTMLResponse)
    async def run_screen(case_id: str) -> HTMLResponse:
        paths = paths_for(case_id)
        state = await get_tool("get_case_state").fn(ToolContext(paths=paths))
        activity = []
        if paths.run_log.exists():
            for line in paths.run_log.read_text(encoding="utf-8").splitlines()[-25:]:
                entry = json.loads(line)
                activity.append(
                    f"<li><span class='pill'>{_esc(entry['actor'])}</span> "
                    f"{_esc(entry['action'])} — {_esc(entry.get('result'))}</li>"
                )
        counters = "".join(
            f"<tr><th>{_esc(key)}</th><td>{_esc(value)}</td></tr>"
            for key, value in state.items()
        )
        body = (
            f"<nav><a href='/'>← cas</a>"
            f"<a href='/case/{case_id}/chronology'>chronologie</a>"
            f"<a href='/case/{case_id}/progress'>progress (JSON)</a></nav>"
            f"<h2>État</h2><table>{counters}</table>"
            f"<h2>Activité</h2><ul>{''.join(activity) or '<li>Aucune activité.</li>'}</ul>"
        )
        return _page(f"Cas {case_id}", body)

    def _actions_form(case_id: str, event_id: str) -> str:
        options = "".join(f"<option value='{a}'>{a}</option>" for a in REVIEW_ACTIONS)
        return (
            f"<form class='inline' method='post' action='/case/{case_id}/decision'>"
            f"<input type='hidden' name='event_id' value='{event_id}'>"
            f"<select name='action'>{options}</select> "
            f"<input type='text' name='new_summary' placeholder='nouveau résumé (edit)'> "
            f"<input type='text' name='reason' placeholder='raison'> "
            f"<button type='submit'>appliquer</button></form>"
        )

    def _rows_table(case_id: str, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "<p>Aucun événement.</p>"
        parts = []
        for row in rows:
            quote = (
                f"<details><summary>citation (p. {_esc(row['quote_page'])})</summary>"
                f"<blockquote>{_esc(row['quote'])}</blockquote>"
                f"<p>passe {row['pass_number']} · flags: {_esc(', '.join(row['flags']))}</p></details>"
                if row["quote"]
                else ""
            )
            parts.append(
                "<tr>"
                f"<td>{_esc(row['date'] or 'non résolue')}</td>"
                f"<td>{_esc(row['event_type'])}</td>"
                f"<td>{_esc(row['summary'])}{quote}</td>"
                f"<td>{_esc(row['author'])}</td>"
                f"<td>{_esc(row['report_id'])} p. {_esc(', '.join(str(p) for p in row['source_pages']))}</td>"
                f"<td>{_esc(row['status'])}</td>"
                f"<td>{_actions_form(case_id, row['event_id'])}</td>"
                "</tr>"
            )
        return (
            "<table><thead><tr><th>Date</th><th>Type</th><th>Description</th><th>Auteur</th>"
            "<th>Source</th><th>Statut</th><th>Actions</th></tr></thead><tbody>"
            + "".join(parts)
            + "</tbody></table>"
        )

    @app.get("/case/{case_id}/chronology", response_class=HTMLResponse)
    async def chronology(case_id: str) -> HTMLResponse:
        queues = split_queues(build_rows(paths_for(case_id)))
        body = (
            f"<nav><a href='/case/{case_id}'>← cas</a></nav>"
            f"<form method='post' action='/case/{case_id}/export'>"
            f"<button type='submit'>exporter (JSON / CSV / HTML)</button></form>"
            f"<h2>File principale ({len(queues['default'])})</h2>"
            + _rows_table(case_id, queues["default"])
            + f"<h2>File secondaire ({len(queues['secondary'])})</h2>"
            + _rows_table(case_id, queues["secondary"])
            + f"<h2>Non résolu / à réviser ({len(queues['unresolved'])})</h2>"
            + _rows_table(case_id, queues["unresolved"])
        )
        return _page(f"Chronologie — {case_id}", body)

    @app.post("/case/{case_id}/decision")
    async def decision(
        case_id: str,
        event_id: str = Form(...),
        action: str = Form(...),
        new_summary: str = Form(""),
        reason: str = Form(""),
    ) -> RedirectResponse:
        after = {"summary_fr": new_summary} if action == "edit" and new_summary else {}
        record_decision(paths_for(case_id), event_id, action, after=after, reason=reason)
        return RedirectResponse(url=f"/case/{case_id}/chronology", status_code=303)

    @app.post("/case/{case_id}/export")
    async def export(case_id: str) -> RedirectResponse:
        export_all(paths_for(case_id))
        return RedirectResponse(url=f"/case/{case_id}/chronology", status_code=303)

    return app
