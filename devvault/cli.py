from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path as _Path

from devvault.formatters import format_found, format_json, write_output
from scanner.adapters.filesystem import OSFileSystem
from scanner.backup_engine import BackupEngine
from scanner.engine import scan as scan_engine
from scanner.models import ScanRequest
from scanner.models.backup import BackupRequest
from scanner.restore_engine import RestoreEngine, RestoreRequest
from scanner.verify_engine import VerifyEngine, VerifyRequest


_COMMANDS = {"scan", "backup", "restore", "verify"}


def _rewrite_argv_for_backcompat(argv: list[str]) -> list[str]:
    """
    Backwards-compatible behavior:
      - `devvault` defaults to `devvault scan`
      - `devvault <roots...>` becomes `devvault scan <roots...>`
    While allowing real subcommands like `devvault backup ...`.
    """
    if not argv:
        return ["scan"]

    # Find first non-flag token (flags start with '-')
    first_non_flag = None
    for tok in argv:
        if not tok.startswith("-"):
            first_non_flag = tok
            break

    # If user already specified a command, do nothing.
    if first_non_flag in _COMMANDS:
        return argv

    # Otherwise, treat as scan roots: insert 'scan' before first non-flag token.
    out: list[str] = []
    inserted = False
    for tok in argv:
        if not inserted and not tok.startswith("-"):
            out.append("scan")
            inserted = True
        out.append(tok)

    if not inserted:
        # argv was all flags; default to scan
        out.insert(0, "scan")
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    if argv is None:
        argv = sys.argv[1:]

    help_requested = any(t in ("-h", "--help") for t in argv)
    cmd_present = any((not t.startswith("-")) and (t in _COMMANDS) for t in argv)
    help_only = help_requested and not cmd_present

    if not help_only:
        argv = _rewrite_argv_for_backcompat(argv)

    require_subcommand = not help_only

    parser = argparse.ArgumentParser(
        prog="devvault",
        description="DevVault — Professional project backup and risk detection CLI.",
    )

    sub = parser.add_subparsers(dest="command", required=require_subcommand)

    # -------------------------
    # scan
    # -------------------------
    scan = sub.add_parser("scan", help="Scan for development projects.")
    scan.add_argument("roots", nargs="*", help="Directories to scan (default: ~/dev).")
    scan.add_argument("--json", action="store_true", help="Output results as JSON.")
    scan.add_argument("--depth", type=int, default=4)
    scan.add_argument("--limit", type=int, default=30)
    scan.add_argument(
        "--top",
        type=int,
        default=0,
        help="Only include the N most recently modified projects (0 = all).",
    )
    scan.add_argument("--include", type=str, default="", help="Only show projects matching this text.")
    scan.add_argument("--output", type=str, default="", help="Write output to a file instead of printing to stdout.")

    # -------------------------
    # backup
    # -------------------------
    backup = sub.add_parser("backup", help="Create a snapshot backup.")
    backup.add_argument("source_root", help="Directory to back up.")
    backup.add_argument("backup_root", help="Destination root where snapshots are created.")
    backup.add_argument("--dry-run", action="store_true", help="Plan only; do not write any data.")
    backup.add_argument("--json", action="store_true", help="Output results as JSON.")
    backup.add_argument("--output", type=str, default="", help="Write output to a file instead of printing to stdout.")

    # -------------------------
    # restore
    # -------------------------
    restore = sub.add_parser("restore", help="Restore a snapshot into an empty destination directory.")
    restore.add_argument("snapshot_dir", help="Snapshot directory to restore from.")
    restore.add_argument("destination_dir", help="Empty destination directory to restore into.")
    restore.add_argument("--json", action="store_true", help="Output results as JSON.")
    restore.add_argument("--output", type=str, default="", help="Write output to a file instead of printing to stdout.")

    # -------------------------
    # verify
    # -------------------------
    verify = sub.add_parser("verify", help="Verify a snapshot without restoring.")
    verify.add_argument("snapshot_dir", help="Snapshot directory to verify.")
    verify.add_argument("--json", action="store_true", help="Output results as JSON.")
    verify.add_argument("--output", type=str, default="", help="Write output to a file instead of printing to stdout.")

    return parser.parse_args(argv)


def _p(s: str) -> _Path:
    return _Path(s).expanduser()


def main() -> int:
    try:
        args = parse_args()

        # -------------------------
        # scan
        # -------------------------
        if args.command == "scan":
            roots = [_p(r) for r in args.roots] if args.roots else [_p("~/dev")]

            req = ScanRequest(
                roots=roots,
                depth=args.depth,
                limit=args.limit,
                top=args.top,
                include=args.include,
            )

            result = scan_engine(req)

            want_json = args.json or (args.output and args.output.lower().endswith(".json"))

            if want_json:
                out = format_json(result.projects, result.scanned_directories)
            else:
                if not args.output:
                    print("\nScanning for development projects...\n")

                if not result.projects:
                    out = "No projects found."
                else:
                    out = (
                        f"Scanned {result.scanned_directories} directories.\n\n"
                        f"{format_found(result.projects, result.skipped_directories, limit=args.limit)}"
                    )

            if args.output:
                write_output(args.output, out)
                print(f"Wrote report to: {args.output}")
            else:
                print(out)

            return 0

        # -------------------------
        # backup
        # -------------------------
        if args.command == "backup":
            fs = OSFileSystem()
            engine = BackupEngine(fs)

            req = BackupRequest(
                source_root=_p(args.source_root),
                backup_root=_p(args.backup_root),
                dry_run=bool(args.dry_run),
            )

            result = engine.execute(req)

            payload = {
                "backup_id": getattr(result, "backup_id", None),
                "backup_path": str(getattr(result, "backup_path", "")),
                "dry_run": bool(getattr(result, "dry_run", False)),
                "started_at": getattr(result, "started_at", None).isoformat() if getattr(result, "started_at", None) else None,
                "finished_at": getattr(result, "finished_at", None).isoformat() if getattr(result, "finished_at", None) else None,
            }

            want_json = args.json or (args.output and args.output.lower().endswith(".json"))
            out = json.dumps(payload, indent=2, sort_keys=True) if want_json else (
                f"Backup created: {payload['backup_id']}\n"
                f"Path: {payload['backup_path']}\n"
                f"Dry run: {payload['dry_run']}"
            )

            if args.output:
                write_output(args.output, out)
                if not want_json:
                    print(f"Wrote report to: {args.output}")
            else:
                print(out)

            return 0

        # -------------------------
        # restore
        # -------------------------
        if args.command == "restore":
            fs = OSFileSystem()
            engine = RestoreEngine(fs)

            req = RestoreRequest(
                snapshot_dir=_p(args.snapshot_dir),
                destination_dir=_p(args.destination_dir),
            )

            engine.restore(req)

            payload = {
                "status": "ok",
                "snapshot_dir": str(req.snapshot_dir),
                "destination_dir": str(req.destination_dir),
            }

            want_json = args.json or (args.output and args.output.lower().endswith(".json"))
            out = json.dumps(payload, indent=2, sort_keys=True) if want_json else (
                "Restore completed.\n"
                f"Snapshot: {payload['snapshot_dir']}\n"
                f"Destination: {payload['destination_dir']}"
            )

            if args.output:
                write_output(args.output, out)
                if not want_json:
                    print(f"Wrote report to: {args.output}")
            else:
                print(out)

            return 0

        # -------------------------
        # verify
        # -------------------------
        if args.command == "verify":
            fs = OSFileSystem()
            engine = VerifyEngine(fs)

            req = VerifyRequest(snapshot_dir=_p(args.snapshot_dir))
            res = engine.verify(req)

            payload = {
                "status": "ok",
                "snapshot_dir": str(res.snapshot_dir),
                "files_verified": res.files_verified,
            }

            want_json = args.json or (args.output and args.output.lower().endswith(".json"))
            out = json.dumps(payload, indent=2, sort_keys=True) if want_json else (
                "Verify completed.\n"
                f"Snapshot: {payload['snapshot_dir']}\n"
                f"Files verified: {payload['files_verified']}"
            )

            if args.output:
                write_output(args.output, out)
                if not want_json:
                    print(f"Wrote report to: {args.output}")
            else:
                print(out)

            return 0

        return 2

    except RuntimeError as e:
        print(f"devvault: error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
