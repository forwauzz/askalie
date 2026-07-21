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
- [x] P5.1 Gold format + matching — done
- [x] P5.2 Metrics + run summary — done

## Phase 6 — Tools, agents, orchestrator
- [x] P6.1 Tool layer (provider-neutral) — done (includes curator service from P6.4, needed by run_curator)
- [x] P6.2 SDK adapters + agent specs — done
- [x] P6.3 Scout pipeline (mock-first) — done
- [x] P6.4 Gap + Curator services (mock-first) — done
- [x] P6.5 Orchestrator runner — done (mock runtime + run CLI; Claude live path BLOCKED-ON-USER for execution)

## Phase 7 — Curation output, export, review UI
- [x] P7.1 Exports — done
- [x] P7.2 Review UI — done
- [x] P7.3 Progress view — done

## Phase L — Live (needs user-provided env/data)
- [x] PL.1 doctor command — done
- [x] PL.2 Experiment 0: Case 1 ingest inventory — done (2026-07-20: 363 pages / 13 docs; 115 native, 228 OCR fra+eng, 20 empty/unreadable; 280.8s. Tokenize: 174 unique dates, 123 unique entities)
- [x] PL.3+PL.4 Experiments 1&2 combined (Scout units + reader baseline) — done 2026-07-20. Prior units were document-level (unusable), so baseline ran on Scout segmentation: 230 units + 12 uncertain ranges. 230/230 readers succeeded, 837 candidates, 595 with restored dates. **Machine-scored: 39/74 gold full-captured + 18 partial (awaiting human adjudication) + 11 wrong-date; only 6 gold entirely missed.** Prior system reference: 50/74 human-adjudicated, 187 rows. Live-path fixes en route: schema-in-prompt, max_turns, bracket-tolerant date restoration, containment-based matcher.
- [x] PL.5 Experiment 3 (gap loop) — done 2026-07-20. Gap Agent produced 19 intelligent targeted tasks over 2 iterations (zero-event rereads, uncited-token clusters, missing operative report search, resegmentation); rereads added 60 candidates but 0 converted new gold (search/resegment tasks that target the 6 true misses were left pending — executor only automates rereads/inspects). Verdict: mechanism validated, value unproven. Pipeline lesson: added 10-min call timeout after a hung session stalled 2.5h.
- [x] PL.6 Experiment 4 (curator) — done 2026-07-20. Batched curation (100-event chunks): 430 default / 467 secondary, 129 duplicates linked, 33 baseline forced-default, 0 dropped. 31/39 captured gold in default, 8 in secondary (review burden halved vs 897 raw; gold-in-secondary needs threshold review).
- [x] PL.7b Experiment 6 (blind validation) — done 2026-07-21 under freeze-blind-v1. **Case 2 SAAQ: 19/36 (53%) strict-captured**, 6 wrong-date, 154 rows, 83 min, 0 reader failures, loop recovered 2 gold. Prior system v10 (after ≥4 tuning rounds on this case): 31/36 (86%). **Case 3 IVAC: 9/61 (15%)**, 13 wrong-date, 39 unmatched (only 5 recoverable among undated), 144 rows, 114 min, 0 failures, **loop recovered 7 gold**. Prior system v5 (also multi-round): 23/61 (38%). Diagnosis: date-sparse files (41 tokens/216p on IVAC; 50% undated events) break date-anchored capture, and the materiality rules over-suppress form-heavy IVAC reports (2/3 zero-event units). Loop-recovery metric rose with file difficulty (0 → 2 → 7): the adaptive loop earns its place exactly where first passes fail. Verdict: REVISE — architecture sound, date representation (Variant B) + per-régime materiality profiles are the required revisions before re-validation.
- [~] PL.7a Experiment 5 (personalization): Cabinet master prompt A/B done 2026-07-20 on identical Scout units. v1 generic: 897 rows, 39 machine-full + 18 partial, 6 unmatched. v2 master prompt: **322 rows (−64%)**, 30 machine-full + 19 partial, 14 unmatched, wrong-dates unchanged (11). Curated v2: 262 default / 60 secondary, 20 dups linked. Awaiting human adjudication of v2's 19 partials to settle capture (terse Cabinet-style summaries bias the containment matcher low). Human-adjudicated v1: 47/74 (prior system: 50/74). Also: skill machinery live (read-cnesst-decision, observable in UI); adjudication tab shipped; privacy leak (patient surname) found + sealed with dictionary variants. Remaining: skill pilot on decisions, wrong-date fix, stability runs, blind Cases 2–3 (go/no-go).

## Iteration notes
(append newest first: date, packet, what was done, test status, blockers)

- 2026-07-20 — PL.2 (Experiment 0) done on real Case 1. Tesseract wired (user install found off-PATH; fra.traineddata added to user tessdata via TESSDATA_PREFIX). Ingest: 363 pages / 13 documents → 115 native-usable (32%), 228 OCR-required (63%), 20 empty/unreadable (5%), 280.8s. Tokenize: 363 pages → 174 unique date tokens, 123 unique entity tokens (pattern recognizers only — no known_entities.json yet, so names are NOT tokenized; needed before any live reader run). Gold answer_key.pdf deliberately excluded from ingest (Spec §28.2). Review UI verified live against the real case. Remaining: PL.3+ need ANTHROPIC_API_KEY.

- 2026-07-20 — P7.1–P7.3 done; AUTONOMOUS PORTION COMPLETE. Reviewer decision service (append-only replay: accept/edit/move/reject/merge/duplicate), default/secondary/unresolved queue splitting, JSON + Excel-friendly CSV + self-contained HTML exports with quotes and page refs, FastAPI review UI (case list, run screen with activity feed, chronology with per-row action forms, progress JSON endpoint), serve CLI. HANDOFF.md written. 92 tests green, ruff clean. Remaining packets are all BLOCKED-ON-USER (Phase L live experiments).

- 2026-07-20 — P6.5 + PL.1 done. ScriptedCaseMock covering all four agent schemas deterministically; MockRuntime running the full phase sequence (scout → readers → gap ×N → curator → finish) through the real tool layer; `run` CLI with runtime selection (mock / claude / openai-stub); `doctor` CLI reporting live prerequisites. Integration test proves the whole case runs offline: scout units, zero reader failures, pass-2 recovery via the gap loop, full curation, chronology.json, finished manifest. 86 tests green, ruff clean.

- 2026-07-20 — P6.2–P6.4 done. Neutral AgentSpecs (scout/gap-reviewer/curator) + prompt files (orchestrator/scout/gap per Spec §15.5/§16/§18); Claude adapter generating the MCP server and AgentDefinitions from the registries, allowed-tools list matching Spec §22.4, ClaudeRuntime live-session path (Phase L); Scout pipeline with 1500/500-char packets and uncertain-range → overlapping low-confidence fallback units; Gap service computing local facts (zero-event reports, uncited date tokens, reader flags) with task creation + executor (reread dispatches pass N+1 with origin tracked, pass limit 3 enforced, judgment tasks left pending). 82 tests green, ruff clean.

- 2026-07-20 — P6.1 done. All 13 Spec §21 tools as plain async functions + ToolSpec registry (no SDK imports): case state, inspect/read/search, report map save/replace, update_report_units (split/merge/resize/relabel/mark_uncertain with reader-result invalidation + stale flagging, never deletion), task lifecycle, dispatch_readers wrapper, run_curator, finish_case writing chronology.json. Curator service with baseline mandatory-default post-check that forces default + flags disagreement, and defaults unassigned events. 75 tests green, ruff clean. Note: baseline config is a Python constant (curation/baseline.py) instead of YAML to avoid a pyyaml dep.

- 2026-07-20 — P5.1–P5.2 done. Gold loader (eval-layer-only, guarded by import test per Spec §28.2), date+similarity+key-fact matcher with wrong-date detection and adjudication flags, all Spec §4 metrics (manual/live ones report null honestly), matches.jsonl + metrics.json + run_summary.md artifacts, `evaluate` CLI. Hand-computed metric assertions on synthetic full/wrong-date/partial/miss/extra cases. 68 tests green, ruff clean.

- 2026-07-20 — P4.1–P4.5 done. Report map + manual unit import with page-marker text assembly; ModelClient seam (Mock / Claude, lazy SDK import, import-boundary test enforcing PLAN §2); reader runner with Spec §34 retry ladder (retry → simplified prompt → fail surfaced); bounded async dispatcher writing results, assigning event IDs/origins, restoring dates, recording failures; candidate store; duplicate linking (never deleting); HeuristicReaderMock enabling offline end-to-end; `reports` + `readers` CLI. Mock e2e on fixtures: 3 reports → candidates with restored dates. 64 tests green, ruff clean.

- 2026-07-20 — P3.1–P3.3 done. Date detection (fr/en textual, ISO, dmy with ambiguity confidence; 25 positive + 6 negative table cases incl. OCR-mangled never-mis-normalize), deterministic opaque date tokens + sequential entity tokens with save/load registries, regex recognizers (RAMQ/phone/email/postal/labeled claim) + per-case known-entities dictionary, safe-text builder with overlap resolution, tokenize CLI, date restoration with date_unresolved flag. Leak test proves no raw identifiers/dates survive in safe text. 56 tests green, ruff clean.

- 2026-07-20 — P2.1–P2.3 done. Multi-signal quality scorer (Spec §12.3), PyMuPDF native extraction, page PNG rendering, OcrEngine seam (Tesseract subprocess / Null fallback), full ingest pipeline writing page records + raw text, `ingest` CLI with Step-1 summary. Fixture case: 8 pages → 5 native, 3 OCR-needed correctly flagged. 16 tests green + 1 skip (live Tesseract), ruff clean. Created NEEDS_FROM_USER.md (Tesseract, API key, Case 1 paths).

- 2026-07-20 — P1.1–P1.3 done. All Spec §11 Pydantic models (manifest, page, report unit, candidate event, task, curation, decision) with unknown-field tolerance; CasePaths tree per Spec §10; sha256-idempotent create_case_workspace; JsonlStore; log_action run log. 10 tests green, ruff clean.

- 2026-07-20 — P0.1 + P0.2 done. Repo skeleton (pyproject, package layout per Spec §31 + llm/ and agents/runtime/ seams, CLI stubs, CLAUDE.md, .env.example), venv with dev deps, and synthetic French fixture PDFs (consultation, IRM, CNESST decision, blank/image-only/garbage pages). 4 tests green, ruff clean.
