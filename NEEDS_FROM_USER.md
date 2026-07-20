# Needs from user

Things the autonomous build cannot supply itself. Nothing here blocks the offline build —
each item unblocks a live capability.

## 1. Tesseract OCR (unblocks real OCR + Experiment 0)

Not found on PATH (checked 2026-07-20). The pipeline runs without it — image-only pages are
flagged `ocr_unavailable` and preserved — but real scans need it.

Install: `winget install UB-Mannheim.TesseractOCR`
Then ensure the `fra` and `eng` language packs are included (the UB-Mannheim installer has a
component checkbox for French), and either add tesseract.exe to PATH or set `TESSERACT_CMD`
in `.env`. Verify with: `tesseract --version` and `tesseract --list-langs`.

## 2. ANTHROPIC_API_KEY (unblocks live readers/orchestrator, Experiments 1–4)

Copy `.env.example` to `.env` and fill `ANTHROPIC_API_KEY`.

## 3. Case 1 bundle + gold chronology (unblocks Experiments 0–4 on real data)

The spec references `C:\Dev\ALIE\chrono-lab\bundles\case1_cnesst\inputs` and
`...\normalized\gold_events.jsonl`. Confirm these paths exist on this machine (or provide
the correct ones). The gold file must stay outside any prompt/context per Spec §28.2.
