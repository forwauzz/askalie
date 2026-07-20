"""Command-line entry points for Ask ALIE."""

from __future__ import annotations

import argparse

COMMANDS: dict[str, str] = {
    "ingest": "Ingest case PDFs into a local case workspace",
    "tokenize": "Replace identifiers and dates with stable tokens",
    "readers": "Run the reader pass over report units",
    "run": "Run the adaptive orchestrator on a case",
    "evaluate": "Score a case against a gold chronology",
    "serve": "Serve the local review UI",
    "doctor": "Check environment prerequisites for live runs",
}

IMPLEMENTED: frozenset[str] = frozenset({"ingest", "tokenize"})

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
    print(f"'{args.command}' is not implemented yet (arrives with packet {_PENDING_PACKET[args.command]}).")
    return 1
