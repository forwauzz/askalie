"""Command-line entry points for Ask ALIE."""

from __future__ import annotations

import argparse

COMMANDS: dict[str, str] = {
    "ingest": "Ingest case PDFs into a local case workspace",
    "tokenize": "Replace identifiers and dates with stable tokens",
    "reports": "Import manual report units from a JSON spec file",
    "readers": "Run the reader pass over report units",
    "run": "Run the adaptive orchestrator on a case",
    "evaluate": "Score a case against a gold chronology",
    "serve": "Serve the local review UI",
    "doctor": "Check environment prerequisites for live runs",
}

IMPLEMENTED: frozenset[str] = frozenset({"ingest", "tokenize", "reports", "readers", "evaluate"})

# Packet that will replace each stub, per PLAN.md.
_PENDING_PACKET = {
    "ingest": "P2.3",
    "tokenize": "P3.3",
    "readers": "P4.5",
    "run": "P6.5",
    "evaluate": "P5.2",
    "serve": "P7.2",
    "doctor": "PL.1",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ask_alie",
        description="Ask ALIE - local agentic medical-legal chronology POC",
    )
    subparsers = parser.add_subparsers(dest="command")
    for name, help_text in COMMANDS.items():
        sub = subparsers.add_parser(name, help=help_text)
        if name == "ingest":
            sub.add_argument("--input", required=True, help="Directory containing case PDFs")
            sub.add_argument("--case-id", required=True)
            sub.add_argument("--workspace", default=None, help="Workspace root (default: env/workspace)")
        elif name == "tokenize":
            sub.add_argument("--case", required=True, help="Case directory (workspace/cases/<id>)")
        elif name == "reports":
            sub.add_argument("--case", required=True)
            sub.add_argument("--import-file", required=True, help="JSON list of unit specs")
        elif name == "readers":
            sub.add_argument("--case", required=True)
            sub.add_argument("--concurrency", type=int, default=5)
            sub.add_argument("--mock", action="store_true", help="Use the offline heuristic mock")
            sub.add_argument("--reports", default=None, help="Comma-separated report ids (default: all)")
        elif name == "evaluate":
            sub.add_argument("--case", required=True)
            sub.add_argument("--gold", required=True, help="Gold events JSONL path")
    return parser


def _cmd_ingest(args: argparse.Namespace) -> int:
    from pathlib import Path

    from ask_alie import config
    from ask_alie.ingest.service import ingest_case

    workspace = Path(args.workspace) if args.workspace else config.workspace_root()
    manifest, summary = ingest_case(Path(args.input), args.case_id, workspace)
    print(f"case {manifest.case_id}: {len(manifest.documents)} document(s)")
    print(summary.render())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "ingest":
        return _cmd_ingest(args)
    if args.command == "tokenize":
        from pathlib import Path

        from ask_alie.privacy.tokenize import tokenize_case

        print(tokenize_case(Path(args.case)).render())
        return 0
    if args.command == "reports":
        import json
        from pathlib import Path

        from ask_alie.reports.service import create_units_from_specs
        from ask_alie.workspace.paths import CasePaths

        paths = CasePaths(root=Path(args.case))
        specs = json.loads(Path(args.import_file).read_text(encoding="utf-8"))
        units = create_units_from_specs(paths, specs)
        print(f"report map now has {len(units)} unit(s)")
        return 0
    if args.command == "readers":
        import asyncio
        from pathlib import Path

        from ask_alie.readers.dispatcher import dispatch_readers
        from ask_alie.reports.map import load_report_map
        from ask_alie.workspace.paths import CasePaths

        paths = CasePaths(root=Path(args.case))
        if args.mock:
            from ask_alie.llm.mock import HeuristicReaderMock

            client = HeuristicReaderMock()
        else:
            from ask_alie.llm.client import ClaudeModelClient

            client = ClaudeModelClient()
        report_ids = (
            args.reports.split(",")
            if args.reports
            else [u.report_id for u in load_report_map(paths)]
        )
        summary = asyncio.run(
            dispatch_readers(paths, client, report_ids, max_concurrency=args.concurrency)
        )
        print(summary.render())
        return 0 if summary.failed == 0 else 1
    if args.command == "evaluate":
        from pathlib import Path

        from ask_alie.evals.metrics import evaluate_case
        from ask_alie.evals.report import render_run_summary
        from ask_alie.workspace.paths import CasePaths

        report = evaluate_case(CasePaths(root=Path(args.case)), Path(args.gold))
        print(render_run_summary(report))
        return 0
    print(f"'{args.command}' is not implemented yet (arrives with packet {_PENDING_PACKET[args.command]}).")
    return 1
