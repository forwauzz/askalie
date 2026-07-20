"""Ask ALIE — local client-facing app (Spec §7, §27, §42).

Full flow: upload PDFs → watch ingestion and OCR live → generate the
chronology with live agent feedback → review and export. Server-rendered
pages + a small polling script; no build step, no external assets.
"""

from __future__ import annotations

import asyncio
import html
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from ask_alie.ingest.service import ingest_case, load_page_records
from ask_alie.privacy.tokenize import tokenize_case
from ask_alie.review.export import export_all
from ask_alie.review.jobs import JobRegistry
from ask_alie.review.service import REVIEW_ACTIONS, build_rows, record_decision, split_queues
from ask_alie.tools.registry import ToolContext, get_tool
from ask_alie.workspace.manifest import load_manifest
from ask_alie.workspace.paths import CasePaths
from ask_alie.workspace.runlog import log_action

_STYLE = """
:root { --brand:#1d3d6b; --brand2:#2e6fb7; --ok:#1d7a4f; --warn:#b3701c; --bad:#a33; --bg:#f4f6fa; }
* { box-sizing: border-box; }
body { font-family:'Segoe UI',system-ui,sans-serif; margin:0; background:var(--bg); color:#182233; }
header.app { background:linear-gradient(100deg,var(--brand),var(--brand2)); color:#fff; padding:1.1rem 2rem; }
header.app h1 { margin:0; font-size:1.35rem; letter-spacing:.3px; }
header.app p { margin:.15rem 0 0; opacity:.85; font-size:.85rem; }
main { max-width:1180px; margin:1.5rem auto; padding:0 1.5rem; }
.card { background:#fff; border-radius:12px; box-shadow:0 1px 4px rgba(20,40,80,.08); padding:1.2rem 1.4rem; margin-bottom:1.2rem; }
.card h2 { margin:0 0 .8rem; font-size:1.05rem; color:var(--brand); }
table { border-collapse:collapse; width:100%; }
th,td { border-bottom:1px solid #e3e8f0; padding:7px 9px; text-align:left; vertical-align:top; font-size:.92rem; }
th { color:#5a6a85; font-weight:600; font-size:.8rem; text-transform:uppercase; letter-spacing:.4px; }
a { color:var(--brand2); text-decoration:none; } a:hover { text-decoration:underline; }
.btn { display:inline-block; background:var(--brand2); color:#fff; border:none; border-radius:8px;
       padding:.55rem 1.2rem; font-size:.95rem; cursor:pointer; }
.btn:disabled { background:#9fb2cc; cursor:not-allowed; }
.btn.big { font-size:1.05rem; padding:.7rem 1.6rem; }
.btn.ghost { background:#fff; color:var(--brand2); border:1px solid var(--brand2); }
.steps { display:flex; gap:.6rem; flex-wrap:wrap; margin-bottom:1.2rem; }
.step { flex:1; min-width:150px; background:#fff; border-radius:10px; padding:.7rem 1rem;
        border:2px solid #dfe6f0; font-size:.9rem; }
.step .n { font-size:.72rem; color:#7285a3; text-transform:uppercase; letter-spacing:.5px; }
.step.done { border-color:var(--ok); } .step.active { border-color:var(--brand2); box-shadow:0 0 0 3px rgba(46,111,183,.12); }
.step.failed { border-color:var(--bad); }
.bar { background:#e6ebf3; border-radius:6px; height:10px; overflow:hidden; margin-top:4px; }
.bar>i { display:block; height:100%; background:var(--brand2); transition:width .6s; }
.badge { display:inline-block; border-radius:6px; padding:1px 7px; font-size:.75rem; margin:1px; }
.badge.native { background:#e2f2e8; color:var(--ok); }
.badge.ocr { background:#fdeeda; color:var(--warn); }
.badge.none { background:#f6e0e0; color:var(--bad); }
.kpis { display:flex; gap:1.2rem; flex-wrap:wrap; }
.kpi { min-width:110px; } .kpi b { font-size:1.5rem; color:var(--brand); display:block; }
.kpi span { font-size:.78rem; color:#68789a; text-transform:uppercase; letter-spacing:.4px; }
ul.feed { list-style:none; margin:0; padding:0; max-height:260px; overflow-y:auto; font-size:.87rem; }
ul.feed li { padding:.3rem 0; border-bottom:1px dashed #e6ebf3; }
.pill { background:#eef2f8; color:var(--brand); border-radius:8px; padding:1px 8px; font-size:.78rem; margin-right:.4rem; }
form.inline { display:inline; }
input[type=text], textarea, select { border:1px solid #c9d4e4; border-radius:8px; padding:.45rem .6rem;
        font-size:.92rem; font-family:inherit; width:100%; }
form .row { margin-bottom:.8rem; }
label { display:block; font-size:.82rem; color:#5a6a85; margin-bottom:.25rem; font-weight:600; }
.drop { border:2px dashed #b9c8dd; border-radius:10px; padding:1.1rem; text-align:center; color:#5a6a85; background:#fafcff; }
blockquote { margin:4px 0; padding-left:8px; border-left:3px solid #b9c8dd; color:#4c5a72; }
.err { background:#fbe9e9; border:1px solid #e0b4b4; color:#8c2f2f; border-radius:8px; padding:.6rem .9rem; }
nav.crumbs { margin-bottom:1rem; font-size:.9rem; }
"""


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _shell(title: str, body: str, head_extra: str = "") -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{_esc(title)}</title><style>{_STYLE}</style>{head_extra}</head><body>"
        f"<header class='app'><h1>Ask ALIE</h1>"
        f"<p>Chronologies médico-légales · CNESST · SAAQ · IVAC</p></header>"
        f"<main>{body}</main></body></html>"
    )


def _slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "dossier"


def create_app(workspace_root: Path) -> FastAPI:
    app = FastAPI(title="Ask ALIE")
    jobs = JobRegistry()
    cases_dir = workspace_root / "cases"
    uploads_dir = workspace_root / "uploads"

    def paths_for(case_id: str) -> CasePaths:
        return CasePaths.for_case(workspace_root, case_id)

    # ---------- pipelines (run in background threads) ----------

    def ingestion_pipeline(input_dir: Path, case_id: str, instructions: str) -> None:
        ingest_case(input_dir, case_id, workspace_root)
        paths = paths_for(case_id)
        if instructions.strip():
            paths.instructions.write_text(instructions.strip(), encoding="utf-8")
        tokenize_case(paths.root)

    def chronology_pipeline(case_id: str, runtime_name: str) -> None:
        paths = paths_for(case_id)

        def progress(line: str) -> None:
            log_action(paths, actor="alie", action="phase", reason=line)

        if runtime_name == "mock":
            from ask_alie.agents.runtime.mock import MockRuntime

            runtime, ctx = MockRuntime(), ToolContext(paths=paths)
        else:
            from ask_alie.agents.runtime.claude import ClaudeRuntime
            from ask_alie.llm.client import ClaudeModelClient

            runtime, ctx = ClaudeRuntime(), ToolContext(paths=paths, client=ClaudeModelClient())
        asyncio.run(runtime.run_orchestration(ctx, {}, progress=progress))
        export_all(paths)

    # ---------- landing: case list + upload ----------

    @app.get("/", response_class=HTMLResponse)
    async def home() -> HTMLResponse:
        rows = []
        for case_dir in sorted(cases_dir.iterdir()) if cases_dir.is_dir() else []:
            if not (case_dir / "manifest.json").is_file():
                continue
            manifest = load_manifest(CasePaths(root=case_dir))
            pages = sum(d.page_count for d in manifest.documents)
            rows.append(
                f"<tr><td><a href='/case/{manifest.case_id}'><b>{_esc(manifest.case_id)}</b></a></td>"
                f"<td>{_esc(manifest.run_status)}</td><td>{len(manifest.documents)}</td>"
                f"<td>{pages}</td><td>{_esc(manifest.created_at[:16].replace('T', ' '))}</td>"
                f"<td><a href='/case/{manifest.case_id}/chronology'>chronologie</a></td></tr>"
            )
        upload_card = """
<div class='card'><h2>Nouveau dossier</h2>
<form method='post' action='/cases' enctype='multipart/form-data'>
  <div class='row'><label>Nom du dossier</label>
    <input type='text' name='name' required placeholder='ex. Dossier CNESST — Tremblay 2025'></div>
  <div class='row'><label>Documents PDF</label>
    <div class='drop'><input type='file' name='files' multiple accept='application/pdf' required>
    <p>Déposez les PDF du dossier (notes cliniques, imagerie, décisions, expertises…)</p></div></div>
  <div class='row'><label>Qu'est-ce qui compte dans ce dossier ? (optionnel)</label>
    <textarea name='instructions' rows='3'
      placeholder='ex. Se concentrer sur la capacité de travail, l’évolution de la condition lombaire, l’imagerie et la rechute alléguée.'></textarea></div>
  <button class='btn big' type='submit'>Créer le dossier et lancer l'analyse</button>
</form></div>"""
        body = upload_card + (
            "<div class='card'><h2>Dossiers</h2><table><thead><tr><th>Dossier</th><th>Statut</th>"
            "<th>Documents</th><th>Pages</th><th>Créé</th><th></th></tr></thead><tbody>"
            + ("".join(rows) or "<tr><td colspan='6'>Aucun dossier pour l'instant.</td></tr>")
            + "</tbody></table></div>"
        )
        return _shell("Ask ALIE", body)

    @app.post("/cases")
    async def create_case(
        name: str = Form(...),
        instructions: str = Form(""),
        files: list[UploadFile] = File(...),
    ) -> RedirectResponse:
        case_id = _slugify(name)
        suffix = 2
        while (cases_dir / case_id).exists():
            case_id = f"{_slugify(name)}-{suffix}"
            suffix += 1
        input_dir = uploads_dir / case_id
        input_dir.mkdir(parents=True, exist_ok=True)
        for upload in files:
            safe_name = Path(upload.filename or "document.pdf").name
            (input_dir / safe_name).write_bytes(await upload.read())
        jobs.start(case_id, "ingestion", lambda: ingestion_pipeline(input_dir, case_id, instructions))
        return RedirectResponse(url=f"/case/{case_id}", status_code=303)

    # ---------- progress JSON (P7.3, polled by the case screen) ----------

    @app.get("/case/{case_id}/progress")
    async def progress(case_id: str) -> dict[str, Any]:
        paths = paths_for(case_id)
        state: dict[str, Any] = {"case_id": case_id, "exists": paths.manifest.exists()}
        job = jobs.get(case_id)
        state["job"] = (
            {"stage": job.stage, "status": job.status, "error": job.error} if job else None
        )
        if not state["exists"]:
            return state

        state.update(await get_tool("get_case_state").fn(ToolContext(paths=paths)))
        manifest = load_manifest(paths)

        documents, pages_done, ocr_done, native_done, unreadable = [], 0, 0, 0, 0
        recent: list[tuple[float, dict[str, Any]]] = []
        for doc in manifest.documents:
            records = load_page_records(paths, doc.document_id)
            done = len(records)
            pages_done += done
            counts = {"native": 0, "ocr": 0, "unreadable": 0}
            for record in records:
                if record.flags:
                    counts["unreadable"] += 1
                elif record.extraction_method == "native":
                    counts["native"] += 1
                else:
                    counts["ocr"] += 1
            native_done += counts["native"]
            ocr_done += counts["ocr"]
            unreadable += counts["unreadable"]
            documents.append(
                {
                    "document_id": doc.document_id,
                    "filename": doc.filename,
                    "page_count": doc.page_count,
                    "pages_done": done,
                    **counts,
                }
            )
            for record in records[-3:]:
                page_json = paths.page_dir(doc.document_id) / f"page_{record.page_number:04d}.json"
                if page_json.exists():
                    recent.append(
                        (
                            page_json.stat().st_mtime,
                            {
                                "page_id": record.page_id,
                                "method": record.extraction_method,
                                "flags": record.flags,
                            },
                        )
                    )
        recent.sort(key=lambda pair: pair[0], reverse=True)

        total_pages = sum(d.page_count for d in manifest.documents)
        safe_count = len(list(paths.pages_dir.rglob("*.safe.txt")))
        state.update(
            {
                "documents": documents,
                "total_pages": total_pages,
                "pages_done": pages_done,
                "native_done": native_done,
                "ocr_done": ocr_done,
                "unreadable_done": unreadable,
                "ingest_done": total_pages > 0 and pages_done >= total_pages,
                "tokenized": safe_count >= total_pages and total_pages > 0,
                "recent_pages": [entry for _, entry in recent[:8]],
                "run_finished": manifest.run_status == "finished",
            }
        )

        activity = []
        if paths.run_log.exists():
            for line in paths.run_log.read_text(encoding="utf-8").splitlines()[-15:]:
                entry = json.loads(line)
                text = entry.get("reason") or json.dumps(entry.get("result") or {}, ensure_ascii=False)
                activity.append(f"{entry['actor']} · {entry['action']} — {text[:160]}")
        state["activity"] = list(reversed(activity))
        return state

    # ---------- case screen ----------

    @app.get("/case/{case_id}", response_class=HTMLResponse)
    async def case_screen(case_id: str) -> HTMLResponse:
        paths = paths_for(case_id)
        server_activity = ""
        if paths.run_log.exists():
            items = []
            for line in paths.run_log.read_text(encoding="utf-8").splitlines()[-15:]:
                entry = json.loads(line)
                detail = entry.get("reason") or json.dumps(entry.get("result") or {}, ensure_ascii=False)
                items.append(
                    f"<li><span class='pill'>{_esc(entry['actor'])}</span>"
                    f"{_esc(entry['action'])} — {_esc(detail[:160])}</li>"
                )
            server_activity = "".join(reversed(items))

        body = f"""
<nav class='crumbs'><a href='/'>← dossiers</a></nav>
<div id='error' class='err' style='display:none'></div>
<div class='steps'>
  <div class='step done' id='step-upload'><div class='n'>Étape 1</div>Téléversement</div>
  <div class='step' id='step-ingest'><div class='n'>Étape 2</div>Ingestion &amp; OCR
    <div class='bar'><i id='ingest-bar' style='width:0%'></i></div>
    <div id='ingest-note' style='font-size:.8rem;color:#68789a;margin-top:3px'></div></div>
  <div class='step' id='step-chrono'><div class='n'>Étape 3</div>Chronologie
    <div id='chrono-note' style='font-size:.8rem;color:#68789a;margin-top:3px'></div></div>
  <div class='step' id='step-review'><div class='n'>Étape 4</div>Révision &amp; export</div>
</div>

<div class='card'><h2>Vue d'ensemble</h2>
  <div class='kpis'>
    <div class='kpi'><b id='k-pages'>–</b><span>pages traitées</span></div>
    <div class='kpi'><b id='k-native'>–</b><span>texte natif</span></div>
    <div class='kpi'><b id='k-ocr'>–</b><span>OCR (Tesseract)</span></div>
    <div class='kpi'><b id='k-unread'>–</b><span>illisibles</span></div>
    <div class='kpi'><b id='k-reports'>–</b><span>rapports</span></div>
    <div class='kpi'><b id='k-events'>–</b><span>événements</span></div>
  </div>
</div>

<div class='card'><h2>Documents</h2><div id='docs'>Chargement…</div>
  <div style='margin-top:.6rem' id='recent'></div></div>

<div class='card'><h2>Générer la chronologie</h2>
  <form method='post' action='/case/{_esc(case_id)}/build' id='build-form'>
    <div class='row'><label>Moteur</label>
      <select name='runtime' style='max-width:340px'>
        <option value='claude'>Claude (analyse réelle par IA)</option>
        <option value='mock'>Simulation locale (démonstration, sans IA)</option>
      </select></div>
    <button class='btn big' type='submit' id='build-btn' disabled>Générer la chronologie</button>
    <a class='btn ghost big' id='review-link' style='display:none;margin-left:.6rem'
       href='/case/{_esc(case_id)}/chronology'>Réviser la chronologie</a>
  </form>
</div>

<div class='card'><h2>Activité</h2><ul class='feed' id='feed'>{server_activity or "<li>En attente…</li>"}</ul></div>

<script>
const CID = {json.dumps(case_id)};
function badge(m, f) {{
  if (f && f.length) return "<span class='badge none'>" + (f[0]==='ocr_unavailable'?'OCR indispo':'illisible') + "</span>";
  if (m === 'native') return "<span class='badge native'>texte natif</span>";
  if (m === 'none') return "<span class='badge none'>vide</span>";
  return "<span class='badge ocr'>OCR " + m + "</span>";
}}
async function tick() {{
  let s;
  try {{ s = await (await fetch('/case/' + CID + '/progress')).json(); }} catch (e) {{ return; }}
  const el = id => document.getElementById(id);
  if (s.job && s.job.status === 'failed') {{
    el('error').style.display = 'block';
    el('error').textContent = 'Échec (' + s.job.stage + ') : ' + (s.job.error || 'erreur inconnue');
  }}
  if (!s.exists) {{ el('ingest-note').textContent = 'Création du dossier…'; return; }}
  el('k-pages').textContent = (s.pages_done||0) + ' / ' + (s.total_pages||0);
  el('k-native').textContent = s.native_done ?? '–';
  el('k-ocr').textContent = s.ocr_done ?? '–';
  el('k-unread').textContent = s.unreadable_done ?? '–';
  el('k-reports').textContent = (s.reports_read||0) + ' / ' + (s.report_count||0);
  el('k-events').textContent = s.candidate_count ?? '–';
  const pct = s.total_pages ? Math.round(100*s.pages_done/s.total_pages) : 0;
  el('ingest-bar').style.width = pct + '%';
  el('docs').innerHTML = '<table><thead><tr><th>Document</th><th>Pages</th><th>Progression</th></tr></thead><tbody>' +
    (s.documents||[]).map(d =>
      '<tr><td>' + d.filename + '</td><td>' + d.pages_done + ' / ' + d.page_count + '</td>' +
      "<td><div class='bar' style='min-width:120px'><i style='width:" +
      Math.round(100*d.pages_done/Math.max(d.page_count,1)) + "%'></i></div>" +
      "<span class='badge native'>" + d.native + " natif</span>" +
      "<span class='badge ocr'>" + d.ocr + " OCR</span>" +
      (d.unreadable ? "<span class='badge none'>" + d.unreadable + " illisible</span>" : '') +
      '</td></tr>').join('') + '</tbody></table>';
  el('recent').innerHTML = (s.recent_pages||[]).map(p => badge(p.method, p.flags) + ' ' + p.page_id).join(' &nbsp; ');
  el('feed').innerHTML = (s.activity||[]).map(a => {{
    const i = a.indexOf(' · ');
    return "<li><span class='pill'>" + a.slice(0, i) + '</span>' + a.slice(i+3) + '</li>';
  }}).join('') || '<li>En attente…</li>';

  const ingestRunning = s.job && s.job.status === 'running' && s.job.stage === 'ingestion';
  const chronoRunning = s.job && s.job.status === 'running' && s.job.stage === 'chronology';
  el('step-ingest').className = 'step ' + (s.ingest_done && s.tokenized ? 'done' : (ingestRunning ? 'active' : ''));
  el('ingest-note').textContent = ingestRunning ? 'Extraction du texte et OCR en cours…'
      : (s.ingest_done && s.tokenized ? 'Terminé — texte anonymisé prêt' : '');
  el('step-chrono').className = 'step ' + (s.run_finished ? 'done' : (chronoRunning ? 'active' : ''));
  el('chrono-note').textContent = chronoRunning
      ? 'Agents au travail : segmentation, lecture, révision des écarts…'
      : (s.run_finished ? 'Chronologie générée' : '');
  el('step-review').className = 'step ' + (s.run_finished ? 'active' : '');
  el('build-btn').disabled = !(s.ingest_done && s.tokenized) || chronoRunning || ingestRunning;
  el('build-btn').textContent = chronoRunning ? 'Génération en cours…' : 'Générer la chronologie';
  el('review-link').style.display = s.run_finished ? 'inline-block' : 'none';
}}
tick(); setInterval(tick, 1500);
</script>"""
        return _shell(f"Dossier {case_id} — Ask ALIE", body)

    @app.post("/case/{case_id}/build")
    async def build(case_id: str, runtime: str = Form("claude")) -> RedirectResponse:
        runtime_name = runtime if runtime in ("claude", "mock") else "claude"
        jobs.start(case_id, "chronology", lambda: chronology_pipeline(case_id, runtime_name))
        return RedirectResponse(url=f"/case/{case_id}", status_code=303)

    # ---------- chronology review ----------

    def _actions_form(case_id: str, event_id: str) -> str:
        options = "".join(f"<option value='{a}'>{a}</option>" for a in REVIEW_ACTIONS)
        return (
            f"<form class='inline' method='post' action='/case/{case_id}/decision'>"
            f"<input type='hidden' name='event_id' value='{event_id}'>"
            f"<select name='action' style='width:auto'>{options}</select> "
            f"<input type='text' name='new_summary' placeholder='nouveau résumé (edit)' style='width:180px'> "
            f"<input type='text' name='reason' placeholder='raison' style='width:120px'> "
            f"<button class='btn' type='submit'>appliquer</button></form>"
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
            f"<nav class='crumbs'><a href='/case/{case_id}'>← dossier</a></nav>"
            f"<div class='card'><form method='post' action='/case/{case_id}/export' class='inline'>"
            f"<button class='btn' type='submit'>Exporter (JSON / CSV / HTML)</button></form></div>"
            f"<div class='card'><h2>File principale ({len(queues['default'])})</h2>"
            + _rows_table(case_id, queues["default"])
            + f"</div><div class='card'><h2>File secondaire ({len(queues['secondary'])})</h2>"
            + _rows_table(case_id, queues["secondary"])
            + f"</div><div class='card'><h2>Non résolu / à réviser ({len(queues['unresolved'])})</h2>"
            + _rows_table(case_id, queues["unresolved"])
            + "</div>"
        )
        return _shell(f"Chronologie — {case_id}", body)

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
