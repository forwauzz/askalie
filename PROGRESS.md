# Ask ALIE build progress

Status values: `todo` | `in-progress` | `done` | `BLOCKED-ON-USER`.
The loop updates this file every iteration. A packet is `done` only when its PLAN.md exit criteria pass.

## Phase 0 — Bootstrap
- [x] P0.1 Repo skeleton — done
- [x] P0.2 Fixture generator — done

## Phase 1 — Workspace & models
- [x] P1.1 Core data models — done
- [x] P1.2 Workspace layout — done
- [x] P1.3 Run log — done

## Phase 2 — Ingest
- [x] P2.1 Native extraction + quality — done
- [x] P2.2 OCR fallback — done (Tesseract absent on this machine; NullOcrEngine path verified, live test auto-skips — see NEEDS_FROM_USER.md)
- [x] P2.3 ingest CLI — done

## Phase 3 — Tokenization & privacy
- [x] P3.1 Date detection — done
- [x] P3.2 Entity tokenization — done
- [x] P3.3 Safe text + restoration — done

## Phase 4 — Reader baseline (mock-first)
- [x] P4.1 Report map import — done
- [x] P4.2 Model client seam — done
- [x] P4.3 Reader worker + dispatcher — done
- [x] P4.4 Candidate store + duplicates — done
- [x] P4.5 readers CLI — done

## Phase 5 — Evaluation harness
- [ ] P5.1 Gold format + matching — todo
- [ ] P5.2 Metrics + run summary — todo

## Phase 6 — Tools, agents, orchestrator
- [ ] P6.1 MCP tool layer — todo
- [ ] P6.2 SDK server + agent definitions — todo
- [ ] P6.3 Scout pipeline (mock-first) — todo
- [ ] P6.4 Gap + Curator services (mock-first) — todo
- [ ] P6.5 Orchestrator runner — todo

## Phase 7 — Curation output, export, review UI
- [ ] P7.1 Exports — todo
- [ ] P7.2 Review UI — todo
- [ ] P7.3 Progress view — todo

## Phase L — Live (needs user-provided env/data)
- [ ] PL.1 doctor command — todo
- [ ] PL.2 Experiment 0: Case 1 ingest inventory — BLOCKED-ON-USER (Case 1 bundle, Tesseract)
- [ ] PL.3 Experiment 1: reader baseline on Case 1 — BLOCKED-ON-USER (API key)
- [ ] PL.4 Experiment 2: Scout comparison — BLOCKED-ON-USER
- [ ] PL.5 Experiment 3: adaptive orchestrator — BLOCKED-ON-USER
- [ ] PL.6 Experiment 4: curator metrics — BLOCKED-ON-USER
- [ ] PL.7 Stability + Experiments 5–6 — BLOCKED-ON-USER (go/no-go review first)

## Iteration notes
(append newest first: date, packet, what was done, test status, blockers)

- 2026-07-20 — P4.1–P4.5 done. Report map + manual unit import with page-marker text assembly; ModelClient seam (Mock / Claude, lazy SDK import, import-boundary test enforcing PLAN §2); reader runner with Spec §34 retry ladder (retry → simplified prompt → fail surfaced); bounded async dispatcher writing results, assigning event IDs/origins, restoring dates, recording failures; candidate store; duplicate linking (never deleting); HeuristicReaderMock enabling offline end-to-end; `reports` + `readers` CLI. Mock e2e on fixtures: 3 reports → candidates with restored dates. 64 tests green, ruff clean.

- 2026-07-20 — P3.1–P3.3 done. Date detection (fr/en textual, ISO, dmy with ambiguity confidence; 25 positive + 6 negative table cases incl. OCR-mangled never-mis-normalize), deterministic opaque date tokens + sequential entity tokens with save/load registries, regex recognizers (RAMQ/phone/email/postal/labeled claim) + per-case known-entities dictionary, safe-text builder with overlap resolution, tokenize CLI, date restoration with date_unresolved flag. Leak test proves no raw identifiers/dates survive in safe text. 56 tests green, ruff clean.

- 2026-07-20 — P2.1–P2.3 done. Multi-signal quality scorer (Spec §12.3), PyMuPDF native extraction, page PNG rendering, OcrEngine seam (Tesseract subprocess / Null fallback), full ingest pipeline writing page records + raw text, `ingest` CLI with Step-1 summary. Fixture case: 8 pages → 5 native, 3 OCR-needed correctly flagged. 16 tests green + 1 skip (live Tesseract), ruff clean. Created NEEDS_FROM_USER.md (Tesseract, API key, Case 1 paths).

- 2026-07-20 — P1.1–P1.3 done. All Spec §11 Pydantic models (manifest, page, report unit, candidate event, task, curation, decision) with unknown-field tolerance; CasePaths tree per Spec §10; sha256-idempotent create_case_workspace; JsonlStore; log_action run log. 10 tests green, ruff clean.

- 2026-07-20 — P0.1 + P0.2 done. Repo skeleton (pyproject, package layout per Spec §31 + llm/ and agents/runtime/ seams, CLI stubs, CLAUDE.md, .env.example), venv with dev deps, and synthetic French fixture PDFs (consultation, IRM, CNESST decision, blank/image-only/garbage pages). 4 tests green, ruff clean.
