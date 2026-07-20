# Ask ALIE — Handoff

**State (2026-07-20):** every offline packet in [PLAN.md](PLAN.md) is done. 92 tests green, ruff clean,
zero network/API/Tesseract required for the suite. What remains is exclusively the live Phase L
experiments, each blocked on something only you can provide (see [NEEDS_FROM_USER.md](NEEDS_FROM_USER.md)).

## What exists

The full Spec pipeline, end to end, verifiable offline with synthetic French CNESST-style fixtures:

- **Ingest** — PyMuPDF native extraction, multi-signal quality scoring, PNG rendering, Tesseract OCR
  seam with graceful fallback (pages flagged `ocr_unavailable`, never dropped).
- **Privacy** — fr/en date detection (25+ formats, never mis-normalizes), stable opaque date tokens,
  entity tokenization (RAMQ/phone/email/postal/claim + per-case `known_entities.json` dictionary),
  safe text with a leak test, restoration with `date_unresolved` flagging.
- **Readers** — report units with page-marker safe text, async dispatcher (bounded concurrency,
  retry → simplified-prompt → surfaced-failure ladder), event IDs/origins/restored dates,
  duplicate linking (nothing deleted).
- **Agentic loop** — 13 provider-neutral tools (ToolSpec registry), Scout (uncertain seams become
  overlapping fallback units), Gap Agent (local facts → targeted tasks; executor runs re-reads as
  pass N+1, 3-pass limit), Curator (baseline mandatory-default enforced as a flagging post-check),
  orchestrator runtimes: **mock** (scripted, fully tested) and **claude** (Agent SDK session, needs
  API key). OpenAI runtime is a documented stub; an import-boundary test keeps SDKs behind the seams.
- **Evaluation** — gold loader isolated to the eval layer (guard test), matcher with wrong-date
  detection and adjudication flags, all 11 Spec §4 metrics, `matches.jsonl`/`metrics.json`/`run_summary.md`.
- **Review** — FastAPI UI (case list, run screen with activity feed, chronology with
  default/secondary/unresolved queues, reviewer actions appended to `decisions.jsonl`), exports
  (JSON / Excel-friendly CSV / self-contained HTML).

## Try it right now (no credentials needed)

```powershell
.\.venv\Scripts\python -m pytest -q                       # 92 green
.\.venv\Scripts\python tests\fixtures\make_fixtures.py demo_pdfs
.\.venv\Scripts\python -m ask_alie ingest --input demo_pdfs --case-id demo --workspace workspace
.\.venv\Scripts\python -m ask_alie tokenize --case workspace\cases\demo
# optional: put a known_entities.json in the case dir for name tokenization
.\.venv\Scripts\python -m ask_alie run --case workspace\cases\demo --mock
.\.venv\Scripts\python -m ask_alie serve --workspace workspace   # http://127.0.0.1:8321
```

`ask_alie doctor` reports which live prerequisites are still missing.

## Command reference

| Command | Purpose |
| --- | --- |
| `ingest --input <dir> --case-id <id> [--workspace <dir>]` | PDFs → workspace, native/OCR routing summary |
| `tokenize --case <dir>` | safe text + date/entity registries |
| `reports --case <dir> --import-file <units.json>` | manual report units (Spec §38 step 3) |
| `readers --case <dir> [--mock] [--concurrency N] [--reports ids]` | reader pass |
| `run --case <dir> [--mock \| --runtime claude]` | full orchestration |
| `evaluate --case <dir> --gold <gold.jsonl>` | metrics vs gold |
| `serve [--workspace <dir>] [--port 8321]` | review UI |
| `doctor` | live-prerequisite check |

## Blocked live steps (Phase L) and what unblocks each

1. **PL.2 Experiment 0** (Case 1 ingest inventory) — needs the Case 1 bundle path + Tesseract.
2. **PL.3 Experiment 1** (reader baseline vs gold; reference: 50/74, 187 rows) — needs `ANTHROPIC_API_KEY`
   + Case 1 + gold JSONL (format: one `{gold_event_id, date, description, key_facts[]}` per line).
3. **PL.4 Experiment 2** (Scout vs manual segmentation) — same.
4. **PL.5 Experiment 3** (adaptive orchestrator; the headline metric `recovered_gold_by_loop`) — same.
5. **PL.6 Experiment 4** (curator queue metrics) — same.
6. **PL.7** stability ×2 runs + Experiments 5–6 — after your go/no-go on Experiment 3 results.

Two knowingly-simplified spots to revisit before live runs: real-case entity tokenization relies on
the per-case dictionary (a Scout-assisted or Presidio pass is the upgrade path), and
`ClaudeModelClient`/`ClaudeRuntime` request assembly is unit-tested but the live session itself has
never executed — expect a short shakedown on first real run.
