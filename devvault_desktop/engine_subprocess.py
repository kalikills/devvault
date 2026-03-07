from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _json_out(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()


def _normalized_error(exc: Exception) -> dict:
    msg = str(exc) or exc.__class__.__name__
    lower = msg.lower()

    if "errno 22" in lower or "invalid argument" in lower:
        return {
            "code": "DEVICE_DISCONNECTED",
            "error": msg,
            "operator_message": "A removable drive disconnected during the operation.",
        }

    if "winerror 121" in lower or "semaphore timeout period has expired" in lower:
        return {
            "code": "DEVICE_IO_TIMEOUT",
            "error": msg,
            "operator_message": "A storage device stopped responding during the operation.",
        }

    if isinstance(exc, PermissionError):
        return {
            "code": "PERMISSION_DENIED",
            "error": msg,
            "operator_message": "Permission denied while accessing a file or folder.",
        }

    return {
        "code": "ENGINE_ERROR",
        "error": msg,
        "operator_message": msg,
    }


def cmd_backup_execute(source: str, vault: str, cancel_token: str = "") -> int:
    try:
        from scanner.adapters.filesystem import OSFileSystem
        from scanner.backup_engine import BackupEngine
        from scanner.models.backup import BackupRequest

        src = Path(source).expanduser().resolve()
        vlt = Path(vault).expanduser().resolve()

        token = Path(cancel_token) if (cancel_token or "").strip() else None
        cancel_check = (lambda: token.exists()) if token else None

        eng = BackupEngine(OSFileSystem())
        res = eng.execute(BackupRequest(source_root=src, backup_root=vlt), cancel_check=cancel_check)

        _json_out(
            {
                "ok": True,
                "payload": {
                    "backup_id": res.backup_id,
                    "backup_path": str(res.backup_path),
                    "started_at": res.started_at.isoformat(),
                    "finished_at": res.finished_at.isoformat(),
                    "dry_run": res.dry_run,
                },
            }
        )
        return 0
    except Exception as e:
        # Trustware: cancellation is authoritative and should not look like a crash.
        if str(e).strip() == "Cancelled by operator.":
            print_json({
                "ok": False,
                "operator_message": "Cancelled by operator.",
                "error": "Cancelled",
                "payload": {},
            })
            return 2
        norm = _normalized_error(e)
        _json_out(
            {
                "ok": False,
                "code": norm["code"],
                "error": norm["error"],
                "operator_message": norm["operator_message"],
            }
        )
        return 2


def cmd_restore(snapshot: str, destination: str) -> int:
    try:
        from scanner.adapters.filesystem import OSFileSystem
        from scanner.restore_engine import RestoreEngine, RestoreRequest

        snap = Path(snapshot).expanduser().resolve()
        dst = Path(destination).expanduser().resolve()

        eng = RestoreEngine(OSFileSystem())
        eng.restore(RestoreRequest(snapshot_dir=snap, destination_dir=dst))

        _json_out(
            {
                "ok": True,
                "payload": {
                    "snapshot_dir": str(snap),
                    "destination_dir": str(dst),
                    "status": "restored",
                },
            }
        )
        return 0
    except Exception as e:
        norm = _normalized_error(e)
        _json_out(
            {
                "ok": False,
                "code": norm["code"],
                "error": norm["error"],
                "operator_message": norm["operator_message"],
            }
        )
        return 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backup-execute")
    b.add_argument("--cancel-token", default="", help="Path to cancel token file (created by UI on cancel).")
    b.add_argument("--source", required=True)
    b.add_argument("--vault", required=True)

    r = sub.add_parser("restore")
    r.add_argument("--snapshot", required=True)
    r.add_argument("--destination", required=True)

    ns = ap.parse_args(argv)

    if ns.cmd == "backup-execute":
        return cmd_backup_execute(ns.source, ns.vault, cancel_token=getattr(ns, "cancel_token", ""))
    if ns.cmd == "restore":
        return cmd_restore(ns.snapshot, ns.destination)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
