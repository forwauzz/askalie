"""Ask ALIE — local client-facing app (Spec §7, §27, §42).

Legal-workspace product shell (Legora-style): refined sidebar, matter pages
with tabs (Overview / Documents / Chronology), and the chronology as a rich,
filterable, year-grouped table with source excerpts and original document
names. UI chrome is English; extracted chronology content is French.
"""

from __future__ import annotations

import asyncio
import html
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

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
:root { --bg:#fafafa; --panel:#fff; --line:#e9e9ec; --text:#141417; --muted:#8a8a93;
        --soft:#f4f4f6; --green:#0e7a5f; --green-bg:#e7f3ef; --amber:#a3691a; --amber-bg:#faf1e2;
        --red:#b04343; --red-bg:#f9e9e9; --blue:#3556a8; --blue-bg:#e9eefb; }
* { box-sizing:border-box; }
body { font-family:Inter,'Segoe UI',system-ui,-apple-system,sans-serif; margin:0; display:flex;
       color:var(--text); background:var(--bg); font-size:14.5px; -webkit-font-smoothing:antialiased; }
aside { width:248px; min-width:248px; background:var(--panel); border-right:1px solid var(--line);
        height:100vh; position:sticky; top:0; padding:1rem .75rem; display:flex; flex-direction:column; }
aside .brand { display:flex; align-items:center; gap:.5rem; font-weight:700; font-size:1rem;
        padding:.2rem .5rem 1.1rem; letter-spacing:.2px; }
aside .brand i { width:22px; height:22px; border-radius:7px; background:var(--text); color:#fff;
        font-style:normal; display:flex; align-items:center; justify-content:center; font-size:.75rem; }
aside a.item { display:block; padding:.48rem .6rem; border-radius:8px; color:var(--text);
        text-decoration:none; font-size:.88rem; margin-bottom:2px; white-space:nowrap;
        overflow:hidden; text-overflow:ellipsis; }
aside a.item:hover { background:var(--soft); }
aside a.item.active { background:#ededf0; font-weight:600; }
aside .label { font-size:.68rem; color:var(--muted); padding:1rem .6rem .35rem;
        text-transform:uppercase; letter-spacing:.7px; font-weight:600; }
aside a.new { border:1px solid var(--line); font-weight:600; text-align:center; }
.content { flex:1; min-height:100vh; overflow-y:auto; }
.pagehead { background:var(--panel); border-bottom:1px solid var(--line); padding:1.1rem 2.2rem .0; }
.pagehead .row1 { display:flex; align-items:center; justify-content:space-between; gap:1rem; }
.pagehead h1 { font-size:1.15rem; margin:0; font-weight:650; }
.pagehead .sub { color:var(--muted); font-size:.82rem; margin-top:.15rem; }
.tabs { display:flex; gap:1.4rem; margin-top:.9rem; }
.tabs a { text-decoration:none; color:var(--muted); font-size:.88rem; font-weight:550;
        padding:.45rem 2px .55rem; border-bottom:2px solid transparent; }
.tabs a.on { color:var(--text); border-bottom-color:var(--text); }
.wrap { max-width:1080px; margin:0 auto; padding:1.6rem 2.2rem 4rem; }
.wrap.narrow { max-width:720px; }
.hero { text-align:center; margin:11vh auto 0; }
.hero h1 { font-size:1.75rem; font-weight:650; margin:0 0 .45rem; }
.hero p { color:var(--muted); margin:0 0 1.8rem; }
.panel { background:var(--panel); border:1px solid var(--line); border-radius:14px;
         padding:1.25rem 1.5rem; margin-bottom:1rem; text-align:left; }
.panel h2 { font-size:.8rem; margin:0 0 .9rem; text-transform:uppercase; letter-spacing:.6px;
         color:var(--muted); font-weight:650; }
input[type=text], textarea, select { width:100%; border:1px solid var(--line); border-radius:9px;
        padding:.55rem .75rem; font-size:.92rem; font-family:inherit; background:#fff; }
label { display:block; font-size:.78rem; color:var(--muted); margin:1rem 0 .3rem; font-weight:600; }
label:first-child { margin-top:0; }
.drop { border:1.5px dashed #cfcfd6; border-radius:11px; padding:1.1rem; text-align:center;
        color:var(--muted); background:#fcfcfd; font-size:.88rem; }
.btn { display:inline-block; background:var(--text); color:#fff; border:none; border-radius:9px;
       padding:.58rem 1.35rem; font-size:.92rem; font-weight:600; cursor:pointer; text-decoration:none; }
.btn:hover { background:#2c2c31; }
.btn:disabled { background:#d8d8dd; cursor:not-allowed; }
.btn.ghost { background:#fff; color:var(--text); border:1px solid var(--line); }
.btn.small { padding:.34rem .8rem; font-size:.8rem; }
.flow { display:flex; align-items:center; gap:.55rem; margin:.2rem 0 1.2rem; flex-wrap:wrap; }
.flow .s { display:flex; align-items:center; gap:.45rem; font-size:.85rem; color:var(--muted); }
.flow .dot { width:20px; height:20px; border-radius:50%; border:1.5px solid #cfcfd6; display:flex;
       align-items:center; justify-content:center; font-size:.68rem; background:#fff; }
.flow .s.done .dot { background:var(--green); border-color:var(--green); color:#fff; }
.flow .s.done, .flow .s.active { color:var(--text); }
.flow .s.active { font-weight:650; }
.flow .s.active .dot { border-color:var(--text); }
.flow .sep { width:22px; height:1.5px; background:var(--line); }
table { border-collapse:collapse; width:100%; background:var(--panel); }
th,td { border-bottom:1px solid var(--line); padding:10px 12px; text-align:left; vertical-align:top; }
th { color:var(--muted); font-weight:600; font-size:.72rem; text-transform:uppercase;
     letter-spacing:.6px; position:sticky; top:0; background:var(--panel); z-index:2; }
tr:hover td { background:#fcfcfd; }
tr.group td { background:var(--soft); font-weight:700; font-size:.8rem; letter-spacing:.5px;
     color:#5a5a63; padding:6px 12px; position:sticky; top:37px; z-index:1; }
.chip { display:inline-block; border-radius:999px; padding:2px 10px; font-size:.72rem; font-weight:600; }
.chip.type { background:var(--blue-bg); color:var(--blue); }
.chip.default { background:var(--green-bg); color:var(--green); }
.chip.secondary { background:var(--soft); color:#5a5a63; }
.chip.review { background:var(--amber-bg); color:var(--amber); }
.chip.rejected { background:var(--red-bg); color:var(--red); text-decoration:line-through; }
.chip.ok { background:var(--green-bg); color:var(--green); }
.chip.warn { background:var(--amber-bg); color:var(--amber); }
.chip.bad { background:var(--red-bg); color:var(--red); }
td.date { white-space:nowrap; font-weight:650; width:110px; }
td.date span { display:block; color:var(--muted); font-weight:400; font-size:.75rem; }
td.ev p { margin:.35rem 0 .2rem; line-height:1.5; font-size:.93rem; max-width:520px; }
td.ev blockquote { margin:6px 0 2px; padding:.55rem .8rem; background:var(--soft);
     border-left:3px solid #d4d4da; border-radius:6px; color:#4c4c55; font-size:.86rem;
     line-height:1.5; font-style:italic; }
td.src { font-size:.83rem; color:#4c4c55; max-width:190px; }
td.src b { display:block; font-weight:600; color:var(--text); overflow:hidden;
     text-overflow:ellipsis; white-space:nowrap; max-width:180px; }
.kpis { display:flex; gap:1.8rem; flex-wrap:wrap; }
.kpi b { font-size:1.4rem; display:block; font-weight:650; }
.kpi span { font-size:.7rem; color:var(--muted); text-transform:uppercase; letter-spacing:.5px; }
.bar { background:#ededf0; border-radius:6px; height:6px; overflow:hidden; margin-top:5px; min-width:120px; }
.bar>i { display:block; height:100%; background:var(--text); transition:width .6s; }
.badge { display:inline-block; border-radius:6px; padding:1px 7px; font-size:.72rem; margin:1px 2px 1px 0; }
.badge.native { background:var(--green-bg); color:var(--green); }
.badge.ocr { background:var(--amber-bg); color:var(--amber); }
.badge.none { background:var(--red-bg); color:var(--red); }
ul.feed { list-style:none; margin:0; padding:0; max-height:250px; overflow-y:auto; font-size:.84rem; }
ul.feed li { padding:.32rem 0; border-bottom:1px solid var(--soft); color:#4c4c55; }
.pill { background:var(--soft); color:#5a5a63; border-radius:7px; padding:1px 8px; font-size:.72rem; margin-right:.4rem; }
.err { background:var(--red-bg); border:1px solid #e5bcbc; color:#8c2f2f; border-radius:10px;
       padding:.7rem 1rem; margin-bottom:1rem; }
.toolbar { display:flex; align-items:center; gap:.6rem; margin-bottom:1rem; flex-wrap:wrap; }
.toolbar input[type=text] { max-width:280px; }
.fchip { border:1px solid var(--line); background:#fff; border-radius:999px; padding:.35rem .95rem;
       font-size:.82rem; cursor:pointer; font-weight:550; color:#5a5a63; }
.fchip.on { background:var(--text); color:#fff; border-color:var(--text); }
details.menu { position:relative; }
details.menu summary { list-style:none; cursor:pointer; color:var(--muted); font-size:1.05rem;
       padding:0 .4rem; border-radius:6px; }
details.menu summary:hover { background:var(--soft); }
details.menu .sheet { position:absolute; right:0; z-index:5; background:#fff; border:1px solid var(--line);
       border-radius:10px; box-shadow:0 8px 22px rgba(15,15,25,.1); padding:.8rem; width:250px; }
details.menu .sheet input, details.menu .sheet select { margin-bottom:.5rem; font-size:.84rem; }
blockquote { margin:4px 0; }
.rowamber td:first-child { box-shadow:inset 3px 0 0 var(--amber); }
form.inline { display:inline; }
.primary-zone { display:flex; align-items:center; gap:.9rem; flex-wrap:wrap; }
.empty { color:var(--muted); text-align:center; padding:2.5rem 1rem; }
"""

_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _fmt_date(iso: str | None) -> tuple[str, str]:
    if not iso:
        return "Unresolved", ""
    try:
        d = date.fromisoformat(iso)
        return f"{_MONTHS[d.month - 1]} {d.day}, {d.year}", iso
    except ValueError:
        return iso, ""


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

    def list_cases() -> list[str]:
        if not cases_dir.is_dir():
            return []
        return [
            d.name for d in sorted(cases_dir.iterdir()) if (d / "manifest.json").is_file()
        ]

    def _shell(
        title: str, body: str, active_case: str | None = None, active_nav: str = ""
    ) -> HTMLResponse:
        items = "".join(
            f"<a class='item{' active' if cid == active_case else ''}' "
            f"href='/case/{cid}'>{_esc(cid)}</a>"
            for cid in list_cases()
        )
        sidebar = (
            "<aside><div class='brand'><i>A</i>Ask ALIE</div>"
            "<a class='item new' href='/'>+ New case</a>"
            "<div class='label'>Cases</div>"
            + (items or "<span class='item' style='color:var(--muted)'>No cases yet</span>")
            + "<div style='flex:1'></div>"
            "<div class='label'>Workspace</div>"
            f"<a class='item{' active' if active_nav == 'skills' else ''}' href='/skills'>Skills</a>"
            f"<a class='item{' active' if active_nav == 'settings' else ''}' href='/settings'>Settings</a>"
            "</aside>"
        )
        return HTMLResponse(
            f"<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{_esc(title)}</title><style>{_STYLE}</style></head><body>"
            f"{sidebar}<div class='content'>{body}</div></body></html>"
        )

    def _case_head(case_id: str, tab: str, subtitle: str = "") -> str:
        tabs = [("overview", "Overview", f"/case/{case_id}"),
                ("documents", "Documents", f"/case/{case_id}/documents"),
                ("chronology", "Chronology", f"/case/{case_id}/chronology")]
        tab_html = "".join(
            f"<a class='{'on' if key == tab else ''}' href='{href}'>{label}</a>"
            for key, label, href in tabs
        )
        return (
            f"<div class='pagehead'><div class='row1'><div><h1>{_esc(case_id)}</h1>"
            f"<div class='sub'>{_esc(subtitle) or 'CNESST · SAAQ · IVAC medical-legal chronology'}</div></div>"
            f"<span class='status-chip' id='status-chip' style='color:var(--muted);font-size:.82rem'></span></div>"
            f"<div class='tabs'>{tab_html}</div></div>"
        )

    def _skills_note() -> str:
        from ask_alie import config
        from ask_alie.agents.skills import load_skills

        skills = load_skills()
        if not skills or not config.skills_enabled():
            return ""
        names = ", ".join(s.name for s in skills)
        return (
            f"Applies {len(skills)} specialized <a href='/skills'>skill"
            f"{'s' if len(skills) != 1 else ''}</a> automatically ({_esc(names)})."
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

    # ---------- skills & settings ----------

    def _md_lite(body: str) -> str:
        """Tiny renderer for skill bodies: # headers, - lists, paragraphs."""
        out: list[str] = []
        in_list = False
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if line.startswith("#"):
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append(f"<h3>{_esc(line.lstrip('# '))}</h3>")
            elif line.startswith("- "):
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append(f"<li>{_esc(line[2:])}</li>")
            elif not line:
                if in_list:
                    out.append("</ul>")
                    in_list = False
            else:
                out.append(f"<p>{_esc(line)}</p>")
        if in_list:
            out.append("</ul>")
        return "".join(out)

    @app.get("/skills", response_class=HTMLResponse)
    async def skills_page() -> HTMLResponse:
        from ask_alie import config
        from ask_alie.agents.skills import load_skills

        skills = load_skills()
        enabled = config.skills_enabled()
        cards = []
        for skill in skills:
            chips = "".join(
                f"<span class='chip type'>{_esc(t)}</span> " for t in skill.applies_to
            )
            cards.append(
                f"<div class='panel'><h2>{_esc(skill.name)}</h2>"
                f"<p style='margin:.2rem 0 .7rem'>{_esc(skill.description)}</p>"
                f"<div style='margin-bottom:.8rem'>{chips}</div>"
                f"<details><summary>Method details</summary>"
                f"<div style='font-size:.9rem;color:#3f3f46'>{_md_lite(skill.body)}</div></details></div>"
            )
        status = (
            "<span class='chip ok'>active</span> Skills are applied automatically when a "
            "document of a matching type is read."
            if enabled
            else "<span class='chip warn'>disabled</span> Set ASK_ALIE_SKILLS=on to re-enable."
        )
        body = (
            "<div class='pagehead'><div class='row1'><div><h1>Skills</h1>"
            "<div class='sub'>Specialized extraction methods ALIE applies to matching documents</div>"
            "</div></div><div class='tabs'></div></div>"
            f"<div class='wrap'><p style='color:var(--muted)'>{status}</p>"
            + ("".join(cards) or "<div class='panel'><div class='empty'>No skills installed yet.</div></div>")
            + "</div>"
        )
        return _shell("Skills — Ask ALIE", body, active_nav="skills")

    @app.get("/settings", response_class=HTMLResponse)
    async def settings_page() -> HTMLResponse:
        from ask_alie.doctor import run_checks

        rows = []
        for name, ok, detail in run_checks():
            chip = "<span class='chip ok'>ok</span>" if ok else "<span class='chip warn'>attention</span>"
            rows.append(f"<tr><td>{_esc(name)}</td><td>{chip}</td><td>{_esc(detail)}</td></tr>")
        body = (
            "<div class='pagehead'><div class='row1'><div><h1>Settings</h1>"
            "<div class='sub'>Engine, authentication and system health</div></div></div>"
            "<div class='tabs'></div></div>"
            "<div class='wrap'><div class='panel' style='padding:0'>"
            "<table><thead><tr><th>Component</th><th>Status</th><th>Detail</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table></div></div>"
        )
        return _shell("Settings — Ask ALIE", body, active_nav="settings")

    # ---------- landing ----------

    @app.get("/", response_class=HTMLResponse)
    async def home() -> HTMLResponse:
        body = """
<div class='wrap narrow'><div class='hero'>
  <h1>Ready to build a chronology?</h1>
  <p>Upload the case file, tell ALIE what matters, and get a sourced medical-legal chronology.</p>
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
    <button class='btn' type='submit' style='font-size:1rem;padding:.68rem 1.9rem'>
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

    # ---------- progress JSON ----------

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
        last_activity_age = None
        if paths.run_log.exists():
            import time as _time

            last_activity_age = round(_time.time() - paths.run_log.stat().st_mtime)
            for line in paths.run_log.read_text(encoding="utf-8").splitlines()[-15:]:
                entry = json.loads(line)
                text = entry.get("reason") or json.dumps(entry.get("result") or {}, ensure_ascii=False)
                activity.append(f"{entry['actor']} · {entry['action']} — {text[:160]}")
        state["activity"] = list(reversed(activity))
        state["last_activity_seconds"] = last_activity_age
        return state

    # ---------- overview tab ----------

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

        body = _case_head(case_id, "overview") + f"""
<div class='wrap'>
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
         href='/case/{_esc(case_id)}/chronology'>Open chronology</a>
      <span id='primary-note' style='color:var(--muted);font-size:.86rem'></span>
    </div>
    <div style='margin-top:.7rem;font-size:.82rem;color:var(--muted)'>{_skills_note()}</div>
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
    <div style='margin-top:.8rem' id='recent'></div>
  </div>

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
  el('recent').innerHTML = (s.recent_pages||[]).map(p => badge(p.method, p.flags) + ' ' + p.page_id).join(' &nbsp; ');
  el('feed').innerHTML = (s.activity||[]).map(a => {{
    const i = a.indexOf(' · ');
    return "<li><span class='pill'>" + a.slice(0, i) + '</span>' + a.slice(i+3) + '</li>';
  }}).join('') || '<li>Waiting…</li>';

  const ingRun = s.job && s.job.status === 'running' && s.job.stage === 'ingestion';
  // agents may also run outside this server (CLI/scripts): recent activity counts
  const external = !s.job && !s.run_finished && s.last_activity_seconds !== null
      && s.last_activity_seconds < 180 && (s.reports_read || 0) > 0;
  const chrRun = (s.job && s.job.status === 'running' && s.job.stage === 'chronology') || external;
  const ready = s.ingest_done && s.tokenized;
  el('f-process').className = 's ' + (ready ? 'done' : (ingRun ? 'active' : ''));
  el('f-generate').className = 's ' + (s.run_finished ? 'done' : ((chrRun || ready) ? 'active' : ''));
  el('f-review').className = 's ' + (s.run_finished ? 'active' : '');
  el('status-chip').textContent = ingRun ? 'Processing documents — extracting text, running OCR…'
      : chrRun ? 'Agents at work — segmenting, reading, checking gaps…'
      : s.run_finished ? 'Chronology ready for review'
      : ready ? 'Documents processed — ready to generate' : '';
  el('build-btn').disabled = !ready || chrRun || ingRun || s.run_finished;
  el('build-btn').textContent = chrRun ? 'Generating…' : 'Generate chronology';
  el('primary-note').textContent = ingRun ? 'You can generate the chronology once processing completes.'
      : chrRun ? 'This can take a while on large files — progress appears in Activity below.'
      : s.run_finished ? 'Done — open the chronology tab.' : '';
  el('review-link').style.display = s.run_finished ? 'inline-block' : 'none';
}}
tick(); setInterval(tick, 1500);
</script>"""
        return _shell(f"{case_id} — Ask ALIE", body, active_case=case_id)

    # ---------- documents tab ----------

    @app.get("/case/{case_id}/documents", response_class=HTMLResponse)
    async def documents_tab(case_id: str) -> HTMLResponse:
        paths = paths_for(case_id)
        rows = []
        if paths.manifest.exists():
            for doc in load_manifest(paths).documents:
                records = load_page_records(paths, doc.document_id)
                native = sum(1 for r in records if not r.flags and r.extraction_method == "native")
                unreadable = sum(1 for r in records if r.flags)
                ocr = len(records) - native - unreadable
                pct = round(100 * len(records) / max(doc.page_count, 1))
                rows.append(
                    f"<tr><td><b>{_esc(doc.filename)}</b></td>"
                    f"<td>{len(records)} / {doc.page_count}</td>"
                    f"<td><div class='bar'><i style='width:{pct}%'></i></div>"
                    f"<span class='badge native'>{native} native</span>"
                    f"<span class='badge ocr'>{ocr} OCR</span>"
                    + (f"<span class='badge none'>{unreadable} unreadable</span>" if unreadable else "")
                    + "</td></tr>"
                )
        body = _case_head(case_id, "documents") + (
            "<div class='wrap'><div class='panel' style='padding:0'>"
            "<table><thead><tr><th>Document</th><th>Pages</th><th>Extraction</th></tr></thead><tbody>"
            + ("".join(rows) or "<tr><td colspan='3' class='empty'>No documents.</td></tr>")
            + "</tbody></table></div></div>"
        )
        return _shell(f"Documents — {case_id}", body, active_case=case_id)

    @app.post("/case/{case_id}/build")
    async def build(case_id: str, runtime: str = Form("claude")) -> RedirectResponse:
        runtime_name = runtime if runtime in ("claude", "mock") else "claude"
        jobs.start(case_id, "chronology", lambda: chronology_pipeline(case_id, runtime_name))
        return RedirectResponse(url=f"/case/{case_id}", status_code=303)

    # ---------- chronology tab: the rich table ----------

    def _actions_menu(case_id: str, event_id: str) -> str:
        options = "".join(f"<option value='{a}'>{a}</option>" for a in REVIEW_ACTIONS)
        return (
            "<details class='menu'><summary>⋯</summary><div class='sheet'>"
            f"<form method='post' action='/case/{case_id}/decision'>"
            f"<input type='hidden' name='event_id' value='{event_id}'>"
            f"<select name='action'>{options}</select>"
            f"<input type='text' name='new_summary' placeholder='new summary (for edit)'>"
            f"<input type='text' name='reason' placeholder='reason'>"
            f"<button class='btn small' type='submit'>Apply</button>"
            "</form></div></details>"
        )

    def _status_chip(row: dict[str, Any]) -> str:
        if row["status"] == "rejected":
            return "<span class='chip rejected'>rejected</span>"
        queue_class = "default" if row["queue"] == "default" else "secondary"
        queue_label = "main" if row["queue"] == "default" else row["queue"]
        chips = f"<span class='chip {queue_class}'>{_esc(queue_label)}</span>"
        if row["needs_review"]:
            chips += " <span class='chip review'>needs review</span>"
        if row["status"] not in ("candidate",):
            chips += f" <span class='chip secondary'>{_esc(row['status'])}</span>"
        return chips

    @app.get("/case/{case_id}/chronology", response_class=HTMLResponse)
    async def chronology(case_id: str) -> HTMLResponse:
        rows = build_rows(paths_for(case_id))
        queues = split_queues(rows)
        review_ids = {r["event_id"] for r in queues["unresolved"]}

        body_rows: list[str] = []
        current_year = None
        for row in rows:
            year = (row["date"] or "")[:4] or "Undated"
            if year != current_year:
                current_year = year
                body_rows.append(f"<tr class='group'><td colspan='6'>{_esc(year)}</td></tr>")
            nice, iso = _fmt_date(row["date"])
            provenance = f"pass {row['pass_number']}"
            if row.get("skills"):
                provenance += f" · skill: {', '.join(row['skills'])}"
            if row["flags"]:
                provenance += f" · flags: {', '.join(row['flags'])}"
            quote = (
                f"<details><summary>Source excerpt · p. {_esc(row['quote_page'])}</summary>"
                f"<blockquote>{_esc(row['quote'])}</blockquote>"
                f"<p style='color:var(--muted);font-size:.78rem'>{_esc(provenance)}</p></details>"
                if row["quote"]
                else f"<p style='color:var(--muted);font-size:.78rem'>{_esc(provenance)}</p>"
            )
            pages = ", ".join(str(p) for p in row["source_pages"])
            filters = " ".join(
                [row["queue"], "review" if row["event_id"] in review_ids else "", row["status"]]
            )
            search_text = _esc(
                f"{row['date']} {row['event_type']} {row['summary']} {row['author']} "
                f"{row['source_document']}".lower()
            )
            amber = " rowamber" if row["needs_review"] and row["status"] != "rejected" else ""
            skill_chip = (
                " <span class='chip ok' title='extracted with a specialized skill'>skill</span>"
                if row.get("skills")
                else ""
            )
            body_rows.append(
                f"<tr class='evrow{amber}' data-f='{filters}' data-s=\"{search_text}\">"
                f"<td class='date'>{_esc(nice)}<span>{_esc(iso)}</span></td>"
                f"<td class='ev'><span class='chip type'>{_esc(row['event_type'])}</span>{skill_chip}"
                f"<p>{_esc(row['summary'])}</p>{quote}</td>"
                f"<td>{_esc(row['author'] or '—')}</td>"
                f"<td class='src'><b title=\"{_esc(row['source_document'])}\">{_esc(row['source_document'])}</b>"
                f"p. {_esc(pages or '—')}</td>"
                f"<td>{_status_chip(row)}</td>"
                f"<td>{_actions_menu(case_id, row['event_id'])}</td></tr>"
            )

        table = (
            "<div class='panel' style='padding:0;overflow:visible'>"
            "<table id='chrono'><thead><tr><th>Date</th><th>Event</th><th>Author</th>"
            "<th>Source</th><th>Status</th><th></th></tr></thead><tbody>"
            + "".join(body_rows)
            + "</tbody></table></div>"
            if rows
            else "<div class='panel'><div class='empty'>No chronology yet — generate it from the Overview tab.</div></div>"
        )

        body = _case_head(
            case_id, "chronology",
            f"{len(queues['default'])} main · {len(queues['secondary'])} secondary · "
            f"{len(queues['unresolved'])} to review",
        ) + f"""
<div class='wrap'>
  <div class='toolbar'>
    <button class='fchip on' data-q='all'>All ({len(rows)})</button>
    <button class='fchip' data-q='default'>Main timeline ({len(queues["default"])})</button>
    <button class='fchip' data-q='secondary'>Secondary ({len(queues["secondary"])})</button>
    <button class='fchip' data-q='review'>Needs review ({len(queues["unresolved"])})</button>
    <input type='text' id='search' placeholder='Search events, sources, authors…'>
    <span style='flex:1'></span>
    <span style='font-size:.85rem;color:var(--muted)'>Download:</span>
    <a class='btn ghost small' href='/case/{_esc(case_id)}/download/csv'>CSV</a>
    <a class='btn ghost small' href='/case/{_esc(case_id)}/download/html'>HTML</a>
    <a class='btn ghost small' href='/case/{_esc(case_id)}/download/json'>JSON</a>
  </div>
  {table}
</div>
<script>
let q = 'all';
function apply() {{
  const s = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('tr.evrow').forEach(tr => {{
    const okQ = q === 'all' || tr.dataset.f.split(' ').includes(q);
    const okS = !s || tr.dataset.s.includes(s);
    tr.style.display = okQ && okS ? '' : 'none';
  }});
}}
document.querySelectorAll('.fchip').forEach(b => b.addEventListener('click', () => {{
  document.querySelectorAll('.fchip').forEach(x => x.classList.remove('on'));
  b.classList.add('on'); q = b.dataset.q; apply();
}}));
document.getElementById('search')?.addEventListener('input', apply);
</script>"""
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

    _DOWNLOAD_TYPES = {
        "csv": ("chronology.csv", "text/csv"),
        "html": ("chronology.html", "text/html"),
        "json": ("chronology.json", "application/json"),
    }

    @app.get("/case/{case_id}/download/{kind}")
    async def download(case_id: str, kind: str):
        if kind not in _DOWNLOAD_TYPES:
            return JSONResponse({"error": f"unknown format: {kind}"}, status_code=404)
        filename, media_type = _DOWNLOAD_TYPES[kind]
        path = paths_for(case_id).output_dir / filename
        if not path.exists():
            export_all(paths_for(case_id))  # generate on first download
        return FileResponse(
            path, media_type=media_type, filename=f"{case_id}-{filename}"
        )

    return app
