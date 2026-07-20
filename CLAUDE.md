# Ask ALIE agent runtime

## Objective

Build a sourced chronology from the active case workspace.

## Persistent rules

- Never read files outside the active case directory.
- Use safe page and report text, not raw source text.
- Do not create events from unsupported assumptions.
- Preserve source page references.
- Do not silently delete candidate events.
- Use specialist agents for scouting, gap review and curation.
- Use the reader dispatcher for report extraction.
- Prefer targeted follow-up work to repeating the whole case.

## State

The authoritative state is stored in case JSON and JSONL files.
Do not rely only on conversation memory.

## Completion

Before finishing, inspect:
- report coverage;
- reader failures;
- pending high-priority tasks;
- Gap Agent output;
- curation status.
