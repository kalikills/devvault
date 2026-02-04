from __future__ import annotations

import argparse
from pathlib import Path

from scanner.engine import run_scan, format_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="devvault",
        description="DevVault — Professional project backup and risk detection CLI.",
    )

    # Backwards-compatible root usage
    parser.add_argument(
        "roots",
        nargs="*",
        help="Directories to scan (default: ~/dev).",
    )

    parser.add_argument("--json", action="store_true", help="Output results as JSON.")
    parser.add_argument("--depth", type=int, default=4)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="Only include the N most recently modified projects (0 = all).",
    )
    parser.add_argument(
        "--include",
        type=str,
        default="",
        help="Only show projects matching this text.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Write output to a file instead of printing to stdout.",
    )

    sub = parser.add_subparsers(dest="command")

    # Future-safe subcommand
    scan = sub.add_parser("scan", help="Scan for development projects.")
    scan.add_argument("roots", nargs="*", help=argparse.SUPPRESS)
    scan.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    scan.add_argument("--depth", type=int, default=4, help=argparse.SUPPRESS)
    scan.add_argument("--limit", type=int, default=30, help=argparse.SUPPRESS)
    scan.add_argument("--top", type=int, default=0, help=argparse.SUPPRESS)
    scan.add_argument("--include", type=str, default="", help=argparse.SUPPRESS)
    scan.add_argument("--output", type=str, default="", help=argparse.SUPPRESS)

    args = parser.parse_args()

    # Default command
    if args.command is None:
        args.command = "scan"

    return args


def main() -> int:
    args = parse_args()

    if args.command != "scan":
        return 2

    roots = [Path(r) for r in args.roots] if args.roots else [Path("~/dev")]

    # 🚨 Critical contract:
    # JSON must be silent except for JSON.
    quiet_mode = args.json

    result = run_scan(
        roots=roots,
        depth=args.depth,
        limit=args.limit,
        top=args.top,
        include=args.include,
        output=args.output,
        json_out=args.json,
        quiet=quiet_mode,
    )

    if args.json and not args.output:
        print(format_json(result.projects, result.scanned_directories))


    return 0
