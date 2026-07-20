"""Ask ALIE — local client-facing app (Spec §7, §27, §42).

ChatGPT-style shell: sidebar of cases, clean centered content, one primary
action per step. Flow: create a case → upload documents → watch processing
(native text + Tesseract OCR live) → generate the chronology → review/export.
UI chrome is English; extracted chronology content is French (Québec files).
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
:root { --bg:#fff; --side:#f9f9f9; --line:#e7e7e7; --text:#0d0d0d; --muted:#8f8f95;
        --hover:#ececec; --green:#10a37f; --amber:#c07d1f; --red:#c04545; }
* { box-sizing:border-box; }
html,body { height:100%; }
body { font-family:'Segoe UI',system-ui,-apple-system,sans-serif; margin:0; color:var(--text);
       background:var(--bg); font-size:15px; display:flex; }
aside { width:256px; min-width:256px; background:var(--side); border-right:1px solid var(--line);
        height:100vh; position:sticky; top:0; padding:.9rem .7rem; display:flex; flex-direction:column; }
aside .brand { font-weight:700; font-size:1.05rem; padding:.4rem .55rem .9rem; }
aside a.item { display:block; padding:.45rem .6rem; border-radius:9px; color:var(--text);
        text-decoration:none; font-size:.9rem; margin-bottom:2px; white-space:nowrap;
        overflow:hidden; text-overflow:ellipsis; }
aside a.item:hover { background:var(--hover); }
aside a.item.active { background:#e4e4e7; }
aside .label { font-size:.72rem; color:var(--muted); padding:.9rem .6rem .3rem;
        text-transform:uppercase; letter-spacing:.5px; }
aside a.new { border:1px solid var(--line); background:#fff; font-weight:600; }
.content { flex:1; min-height:100vh; overflow-y:auto; }
.wrap { max-width:860px; margin:0 auto; padding:2.2rem 2rem 4rem; }
.hero { text-align:center; margin:14vh auto 0; max-width:640px; }
.hero h1 { font-size:1.9rem; font-weight:600; margin:0 0 .4rem; }
.hero p { color:var(--muted); margin:0 0 2rem; }
.panel { background:#fff; border:1px solid var(--line); border-radius:16px; padding:1.4rem 1.6rem;
         margin-bottom:1.1rem; text-align:left; }
.panel h2 { font-size:.95rem; margin:0 0 .9rem; }
input[type=text], textarea, select { width:100%; border:1px solid var(--line); border-radius:10px;
        padding:.6rem .8rem; font-size:.95rem; font-family:inherit; background:#fff; }
textarea { resize:vertical; }
label { display:block; font-size:.8rem; color:var(--muted); margin:.9rem 0 .3rem; font-weight:600; }
label:first-child { margin-top:0; }
.drop { border:1.5px dashed #c9c9cf; border-radius:12px; padding:1.2rem; text-align:center;
        color:var(--muted); background:#fcfcfc; font-size:.9rem; }
.btn { display:inline-block; background:var(--text); color:#fff; border:none; border-radius:999px;
       padding:.6rem 1.5rem; font-size:.95rem; font-weight:600; cursor:pointer; text-decoration:none; }
.btn:hover { background:#333; }
.btn:disabled { background:#d6d6db; cursor:not-allowed; }
.btn.ghost { background:#fff; color:var(--text); border:1.5px solid var(--line); }
.btn.small { padding:.35rem .9rem; font-size:.82rem; }
.flow { display:flex; align-items:center; gap:.5rem; margin:1.4rem 0 1.8rem; flex-wrap:wrap; }
.flow .s { display:flex; align-items:center; gap:.45rem; font-size:.88rem; color:var(--muted); }
.flow .dot { width:22px; height:22px; border-radius:50%; border:1.5px solid #cfcfd6; display:flex;
       align-items:center; justify-content:center; font-size:.72rem; color:var(--muted); background:#fff; }
.flow .s.done .dot { background:var(--green); border-color:var(--green); color:#fff; }
.flow .s.done { color:var(--text); }
.flow .s.active { color:var(--text); font-weight:600; }
.flow .s.active .dot { border-color:var(--text); color:var(--text); }
.flow .sep { flex:0 0 26px; height:1.5px; background:var(--line); }
table { border-collapse:collapse; width:100%; }
th,td { border-bottom:1px solid #f95; border-bottom:1px solid var(--line); padding:8px 10px;
        text-align:left; vertical-align:top; font-size:.9rem; }
th { color:var(--muted); font-weight:600; font-size:.75rem; text-transform:uppercase; letter-spacing:.4px; }
a { color:inherit; }
.kpis { display:flex; gap:1.6rem; flex-wrap:wrap; }
.kpi b { font-size:1.35rem; display:block; font-weight:650; }
.kpi span { font-size:.73rem; color:var(--muted); text-transform:uppercase; letter-spacing:.4px; }
.bar { background:#efeff2; border-radius:6px; height:7px; overflow:hidden; margin-top:5px; min-width:120px; }
.bar>i { display:block; height:100%; background:var(--text); transition:width .6s; }
.badge { display:inline-block; border-radius:6px; padding:1px 7px; font-size:.73rem; margin:1px 2px 1px 0; }
.badge.native { background:#e6f4ef; color:var(--green); }
.badge.ocr { background:#f8efe0; color:var(--amber); }
.badge.none { background:#f8e7e7; color:var(--red); }
ul.feed { list-style:none; margin:0; padding:0; max-height:250px; overflow-y:auto; font-size:.85rem; }
ul.feed li { padding:.32rem 0; border-bottom:1px solid #f2f2f4; color:#3f3f46; }
.pill { background:#f0f0f3; color:#52525b; border-radius:7px; padding:1px 8px; font-size:.73rem; margin-right:.4rem; }
.err { background:#fdecec; border:1px solid #eeb8b8; color:#8c2f2f; border-radius:10px;
       padding:.7rem 1rem; margin-bottom:1rem; }
.topline { display:flex; align-items:baseline; justify-content:space-between; gap:1rem; }
.topline h1 { font-size:1.25rem; margin:0; }
.status-chip { font-size:.78rem; color:var(--muted); }
blockquote { margin:4px 0; padding-left:8px; border-left:3px solid var(--line); color:#52525b; }
form.inline { display:inline; }
details summary { cursor:pointer; color:var(--muted); font-size:.83rem; }
.primary-zone { display:flex; align-items:center; gap:.9rem; flex-wrap:wrap; }
"""


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "case"


def create_app(workspace_root: Path) -> FastAPI:
    app = FastAPI(title="Ask ALIE")
    jobs = JobRegistry()
    cases_dir = workspace_root / "cases"
    uploads_dir = workspace_root / "uploads"

    def paths_for(case_id: str) -> CasePaths:
        return CasePaths.for_case(workspace_root, case_id)

    def list_cases() -> list[dict[str, Any]]:
        cases: list[dict[str, Any]] = []
        for case_dir in sorted(cases_dir.iterdir()) if cases_dir.is_dir() else []:
            if (case_dir / "manifest.json").is_file():
                manifest = load_manifest(CasePaths(root=case_dir))
                cases.append(
                    {
                        "case_id": manifest.case_id,
                        "status": manifest.run_status,
                        "documents": len(manifest.documents),
                        "pages": sum(d.page_count for d in manifest.documents),
                        "created": manifest.created_at[:16].replace("T", " "),
                    }
                )
        return cases

    def _shell(title: str, body: str, active_case: str | None = None) -> HTMLResponse:
        items = "".join(
            f"<a class='item{' active' if c['case_id'] == active_case else ''}' "
            f"href='/case/{c['case_id']}'>{_esc(c['case_id'])}</a>"
            for c in list_cases()
        )
        sidebar = (
            "<aside><div class='brand'>Ask ALIE</div>"
            "<a class='item new' href='/'>+ New case</a>"
            "<div class='label'>Cases</div>"
            + (items or "<span class='item' style='color:var(--muted)'>No cases yet</span>")
            + "</aside>"
        )
        return HTMLResponse(
            f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{_esc(title)}</title><style>{_STYLE}</style></head><body>"
            f"{sidebar}<div class='content'>{body}</div></body></html>"
        )

    # ---------- pipelines (background threads) ----------

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

    # ---------- landing: new case ----------

    @app.get("/", response_class=HTMLResponse)
    async def home() -> HTMLResponse:
        body = """
<div class='wrap'><div class='hero'>
  <h1>Ready to build a chronology?</h1>
  <p>Upload the case file, tell ALIE what matters, and get a sourced medical-legal
     chronology — CNESST · SAAQ · IVAC.</p>
  <form method='post' action='/cases' enctype='multipart/form-data'>
    <div class='panel'>
      <label>Case name</label>
      <input type='text' name='name' required placeholder='e.g. CNESST — Tremblay 2025'>
      <label>Case documents (PDF)</label>
      <div class='drop'><input type='file' name='files' multiple accept='application/pdf' required>
        <p>Drop the case PDFs — clinical notes, imaging, decisions, expert reports…</p></div>
      <label>What matters in this file? <span style='font-weight:400'>(optional)</span></label>
      <textarea name='instructions' rows='3'
        placeholder='e.g. Focus on work capacity, the evolution of the lumbar condition, imaging findings and the alleged relapse.'></textarea>
    </div>
    <button class='btn' type='submit' style='font-size:1.02rem;padding:.7rem 2rem'>
      Create case &amp; process documents</button>
  </form>
</div></div>"""
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

    # ---------- progress JSON (polled by the case screen) ----------

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
<div class='wrap'>
  <div class='topline'><h1>{_esc(case_id)}</h1>
    <span class='status-chip' id='status-chip'></span></div>

  <div class='flow'>
    <div class='s done' id='f-upload'><div class='dot'>✓</div>Upload</div><div class='sep'></div>
    <div class='s' id='f-process'><div class='dot'>2</div>Process documents</div><div class='sep'></div>
    <div class='s' id='f-generate'><div class='dot'>3</div>Generate chronology</div><div class='sep'></div>
    <div class='s' id='f-review'><div class='dot'>4</div>Review &amp; export</div>
  </div>

  <div id='error' class='err' style='display:none'></div>

  <div class='panel'>
    <div class='primary-zone'>
      <form method='post' action='/case/{_esc(case_id)}/build' class='inline' id='build-form'>
        <select name='runtime' style='width:auto;display:inline-block;margin-right:.6rem'>
          <option value='claude'>Claude — real AI analysis</option>
          <option value='mock'>Local simulation (demo, no AI)</option>
        </select>
        <button class='btn' type='submit' id='build-btn' disabled>Generate chronology</button>
      </form>
      <a class='btn ghost' id='review-link' style='display:none'
         href='/case/{_esc(case_id)}/chronology'>Review chronology</a>
      <span id='primary-note' style='color:var(--muted);font-size:.88rem'></span>
    </div>
  </div>

  <div class='panel'><h2>Overview</h2>
    <div class='kpis'>
      <div class='kpi'><b id='k-pages'>–</b><span>pages processed</span></div>
      <div class='kpi'><b id='k-native'>–</b><span>native text</span></div>
      <div class='kpi'><b id='k-ocr'>–</b><span>OCR (Tesseract)</span></div>
      <div class='kpi'><b id='k-unread'>–</b><span>unreadable</span></div>
      <div class='kpi'><b id='k-reports'>–</b><span>reports read</span></div>
      <div class='kpi'><b id='k-events'>–</b><span>events found</span></div>
    </div>
  </div>

  <div class='panel'><h2>Documents</h2><div id='docs'>Loading…</div>
    <div style='margin-top:.7rem' id='recent'></div></div>

  <div class='panel'><h2>Activity</h2>
    <ul class='feed' id='feed'>{server_activity or "<li>Waiting…</li>"}</ul></div>
</div>

<script>
const CID = {json.dumps(case_id)};
function badge(m, f) {{
  if (f && f.length) return "<span class='badge none'>" + (f[0]==='ocr_unavailable'?'OCR unavailable':'unreadable') + "</span>";
  if (m === 'native') return "<span class='badge native'>native text</span>";
  if (m === 'none') return "<span class='badge none'>empty</span>";
  return "<span class='badge ocr'>OCR</span>";
}}
async function tick() {{
  let s;
  try {{ s = await (await fetch('/case/' + CID + '/progress')).json(); }} catch (e) {{ return; }}
  const el = id => document.getElementById(id);
  if (s.job && s.job.status === 'failed') {{
    el('error').style.display = 'block';
    el('error').textContent = 'The ' + s.job.stage + ' step failed: ' + (s.job.error || 'unknown error');
  }}
  if (!s.exists) {{ el('status-chip').textContent = 'Creating case…'; return; }}
  el('k-pages').textContent = (s.pages_done||0) + ' / ' + (s.total_pages||0);
  el('k-native').textContent = s.native_done ?? '–';
  el('k-ocr').textContent = s.ocr_done ?? '–';
  el('k-unread').textContent = s.unreadable_done ?? '–';
  el('k-reports').textContent = (s.reports_read||0) + ' / ' + (s.report_count||0);
  el('k-events').textContent = s.candidate_count ?? '–';
  el('docs').innerHTML = '<table><thead><tr><th>Document</th><th>Pages</th><th>Progress</th></tr></thead><tbody>' +
    (s.documents||[]).map(d =>
      '<tr><td>' + d.filename + '</td><td>' + d.pages_done + ' / ' + d.page_count + '</td>' +
      "<td><div class='bar'><i style='width:" +
      Math.round(100*d.pages_done/Math.max(d.page_count,1)) + "%'></i></div>" +
      "<span class='badge native'>" + d.native + " native</span>" +
      "<span class='badge ocr'>" + d.ocr + " OCR</span>" +
      (d.unreadable ? "<span class='badge none'>" + d.unreadable + " unreadable</span>" : '') +
      '</td></tr>').join('') + '</tbody></table>';
  el('recent').innerHTML = (s.recent_pages||[]).map(p => badge(p.method, p.flags) + ' ' + p.page_id).join(' &nbsp; ');
  el('feed').innerHTML = (s.activity||[]).map(a => {{
    const i = a.indexOf(' · ');
    return "<li><span class='pill'>" + a.slice(0, i) + '</span>' + a.slice(i+3) + '</li>';
  }}).join('') || '<li>Waiting…</li>';

  const ingRun = s.job && s.job.status === 'running' && s.job.stage === 'ingestion';
  const chrRun = s.job && s.job.status === 'running' && s.job.stage === 'chronology';
  const ready = s.ingest_done && s.tokenized;
  el('f-process').className = 's ' + (ready ? 'done' : (ingRun ? 'active' : ''));
  el('f-generate').className = 's ' + (s.run_finished ? 'done' : (chrRun ? 'active' : (ready ? 'active' : '')));
  el('f-review').className = 's ' + (s.run_finished ? 'active' : '');
  el('status-chip').textContent = ingRun ? 'Processing documents — extracting text and running OCR…'
      : chrRun ? 'Agents at work — segmenting, reading, checking gaps…'
      : s.run_finished ? 'Chronology ready for review'
      : ready ? 'Documents processed — ready to generate' : '';
  el('build-btn').disabled = !ready || chrRun || ingRun || s.run_finished;
  el('build-btn').textContent = chrRun ? 'Generating…' : 'Generate chronology';
  el('primary-note').textContent = ingRun ? 'You can generate the chronology once processing completes.'
      : chrRun ? 'This can take a while on large files — progress appears in Activity below.'
      : s.run_finished ? 'Done — open the review screen.' : '';
  el('review-link').style.display = s.run_finished ? 'inline-block' : 'none';
}}
tick(); setInterval(tick, 1500);
</script>"""
        return _shell(f"{case_id} — Ask ALIE", body, active_case=case_id)

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
            f"<input type='text' name='new_summary' placeholder='new summary (edit)' style='width:170px'> "
            f"<input type='text' name='reason' placeholder='reason' style='width:110px'> "
            f"<button class='btn small' type='submit'>apply</button></form>"
        )

    def _rows_table(case_id: str, rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "<p style='color:var(--muted)'>No events.</p>"
        parts = []
        for row in rows:
            quote = (
                f"<details><summary>quote (p. {_esc(row['quote_page'])})</summary>"
                f"<blockquote>{_esc(row['quote'])}</blockquote>"
                f"<p>pass {row['pass_number']} · flags: {_esc(', '.join(row['flags']))}</p></details>"
                if row["quote"]
                else ""
            )
            parts.append(
                "<tr>"
                f"<td>{_esc(row['date'] or 'unresolved')}</td>"
                f"<td>{_esc(row['event_type'])}</td>"
                f"<td>{_esc(row['summary'])}{quote}</td>"
                f"<td>{_esc(row['author'])}</td>"
                f"<td>{_esc(row['report_id'])} p. {_esc(', '.join(str(p) for p in row['source_pages']))}</td>"
                f"<td>{_esc(row['status'])}</td>"
                f"<td>{_actions_form(case_id, row['event_id'])}</td>"
                "</tr>"
            )
        return (
            "<table><thead><tr><th>Date</th><th>Type</th><th>Description</th><th>Author</th>"
            "<th>Source</th><th>Status</th><th>Actions</th></tr></thead><tbody>"
            + "".join(parts)
            + "</tbody></table>"
        )

    @app.get("/case/{case_id}/chronology", response_class=HTMLResponse)
    async def chronology(case_id: str) -> HTMLResponse:
        queues = split_queues(build_rows(paths_for(case_id)))
        body = (
            f"<div class='wrap'>"
            f"<div class='topline'><h1>Chronology — {_esc(case_id)}</h1>"
            f"<form method='post' action='/case/{case_id}/export' class='inline'>"
            f"<button class='btn ghost small' type='submit'>Export (JSON / CSV / HTML)</button></form></div>"
            f"<div class='panel'><h2>Main timeline ({len(queues['default'])})</h2>"
            + _rows_table(case_id, queues["default"])
            + f"</div><div class='panel'><h2>Secondary queue ({len(queues['secondary'])})</h2>"
            + _rows_table(case_id, queues["secondary"])
            + f"</div><div class='panel'><h2>Unresolved / needs review ({len(queues['unresolved'])})</h2>"
            + _rows_table(case_id, queues["unresolved"])
            + "</div></div>"
        )
        return _shell(f"Chronology — {case_id}", body, active_case=case_id)

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
