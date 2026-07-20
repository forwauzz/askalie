# Loop prompt — Ask ALIE build

You are building the Ask ALIE POC in this repository, end to end, autonomously.

Each iteration:

1. Read `PROGRESS.md`. Pick the first packet that is `todo` or `in-progress` (skip `BLOCKED-ON-USER`).
2. Re-read that packet's section in `PLAN.md`, and the relevant Spec sections it cites in `ASK_ALIE_AGENTIC_POC_FULL_SPEC.md`.
3. Implement the packet completely, including its tests. Obey PLAN.md §1 operating rules and §2 pre-made decisions.
4. Run `pytest` (full suite) and `ruff check`. Fix anything red before proceeding.
5. Update `PROGRESS.md`: mark the packet `done` (or `in-progress`/`BLOCKED-ON-USER` with a note) and append an iteration note.
6. If anything requires the user (env var, install, data path), record exact instructions in `NEEDS_FROM_USER.md` and continue with the next packet.
7. Commit: `packet <id>: <summary>`.

Never make the test suite depend on network access, ANTHROPIC_API_KEY, Tesseract, or real case files — use the mock/fixture seams defined in PLAN.md §3.

Stop condition: every packet is `done` or `BLOCKED-ON-USER`. Then write `HANDOFF.md` (state of the system, how to run each command, list of blocked live steps and exactly what unblocks each) and end the loop.
