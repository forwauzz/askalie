# Configuration freeze — blind validation (Spec Experiment 6)

**Frozen: 2026-07-21.** No prompt, skill, model, threshold or tool-behavior changes
until both blind runs (Case 2 SAAQ, Case 3 IVAC) are complete and reported.
Git tag: `freeze-blind-v1`.

## Frozen configuration

- **Reader prompt:** the Cabinet master prompt (`agents/prompts/reader.md`) —
  materiality rule, always-extract floor, Dx/Px/AT/RAT/LF conventions, four
  corrections, French event taxonomy.
- **Skills:** `read-cnesst-decision` (auto-applies to decision-typed units);
  ASK_ALIE_SKILLS=on.
- **Models:** readers = haiku; scout/gap/curator/judge = sonnet; subscription-seat auth.
- **Pipeline:** ingest (fra+eng OCR) → heuristic entity draft + tokenize → Scout
  (taxonomy prompt) → readers (concurrency 4, 3-attempt ladder, 10-min timeout) →
  gap loop ×2 (reread/inspect auto-executed; search/resegment surfaced) → batched
  curator (100/chunk, mandatory-default post-check) → finish → exports.
- **Evaluation:** containment matcher (full ≥ 0.45, partial ≥ 0.2), LLM judge on
  partials (reviewer=llm-judge, human override allowed), gold read only by the
  eval layer.

## Known limitations accepted into the freeze (measured, not patched)

- Wrong-date events (11 on Case 1) — date-token selection; Variant B experiment
  is post-blind backlog.
- ~36% undated events (no-guess policy on partial dates).
- Entity masking is heuristic-draft only on blind cases (no human dictionary review).
- The decision skill's taxonomy is CNESST-flavored; SAAQ/IVAC decision handling
  rides on the generic prompt floor.
- Gap-loop search/resegment tasks are surfaced, not auto-executed.

## Reference results at freeze

- Case 1 v1 (generic prompt): 47/74 human-adjudicated, 897 rows.
- Case 1 v2 (frozen config): 46/74 LLM-judged, 322 rows, 262 main / 60 secondary.
- Prior deterministic system: 50/74, 187 rows (Case 1).
