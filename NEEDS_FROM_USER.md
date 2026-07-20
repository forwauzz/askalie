# Needs from user

Things the autonomous build cannot supply itself. Nothing here blocks the offline build —
each item unblocks a live capability.

## 1. ~~Tesseract OCR~~ — RESOLVED, except the French pack

Tesseract 5.4.0 found at `C:\Program Files\Tesseract-OCR\tesseract.exe` (was off PATH;
now wired via `TESSERACT_CMD` in `.env`). Live OCR test passes.

**Still missing: the `fra` language pack** (only `eng` + `osd` installed). The engine now
degrades gracefully to `eng`, but French accents will be mangled on real scans. Fix: place
`fra.traineddata` from https://github.com/tesseract-ocr/tessdata (or tessdata_best) into
`C:\Program Files\Tesseract-OCR\tessdata\`. `ask_alie doctor` verifies it.

## 2. ANTHROPIC_API_KEY (unblocks live readers/orchestrator, Experiments 1–4)

Copy `.env.example` to `.env` and fill `ANTHROPIC_API_KEY`.

## 3. ~~Case 1 bundle + gold chronology~~ — RESOLVED

Both found at the spec paths (verified by `ask_alie doctor` 2026-07-20):
`C:\Dev\ALIE\chrono-lab\bundles\case1_cnesst\inputs` and
`...\normalized\gold_events.jsonl`. The gold file stays outside any prompt/context per
Spec §28.2 — only the eval layer may read it (enforced by test).
