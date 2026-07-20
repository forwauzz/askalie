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
- [ ] P2.1 Native extraction + quality — todo
- [ ] P2.2 OCR fallback — todo
- [ ] P2.3 ingest CLI — todo

## Phase 3 — Tokenization & privacy
- [ ] P3.1 Date detection — todo
- [ ] P3.2 Entity tokenization — todo
- [ ] P3.3 Safe text + restoration — todo

## Phase 4 — Reader baseline (mock-first)
- [ ] P4.1 Report map import — todo
- [ ] P4.2 Model client seam — todo
- [ ] P4.3 Reader worker + dispatcher — todo
- [ ] P4.4 Candidate store + duplicates — todo
- [ ] P4.5 readers CLI — todo

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

- 2026-07-20 — P1.1–P1.3 done. All Spec §11 Pydantic models (manifest, page, report unit, candidate event, task, curation, decision) with unknown-field tolerance; CasePaths tree per Spec §10; sha256-idempotent create_case_workspace; JsonlStore; log_action run log. 10 tests green, ruff clean.

- 2026-07-20 — P0.1 + P0.2 done. Repo skeleton (pyproject, package layout per Spec §31 + llm/ and agents/runtime/ seams, CLI stubs, CLAUDE.md, .env.example), venv with dev deps, and synthetic French fixture PDFs (consultation, IRM, CNESST decision, blank/image-only/garbage pages). 4 tests green, ruff clean.
