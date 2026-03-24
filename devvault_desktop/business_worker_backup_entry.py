from __future__ import annotations

import json
import sys
from pathlib import Path

from devvault_desktop.engine_subprocess import run_backup_execute_with_drive_watch


JOB_PATH = Path(r"C:\ProgramData\DevVault\worker_backup_job.json")


def main() -> int:
    if not JOB_PATH.exists():
        print("Worker job config missing.", file=sys.stderr)
        return 2

    try:
        cfg = json.loads(JOB_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Worker job config invalid: {e}", file=sys.stderr)
        return 2

    source_root = Path(str(cfg.get("source_root") or "").strip())
    backup_root = Path(str(cfg.get("backup_root") or "").strip())

    if not str(source_root).strip():
        print("Worker job config missing source_root.", file=sys.stderr)
        return 2

    if not str(backup_root).strip():
        print("Worker job config missing backup_root.", file=sys.stderr)
        return 2

    try:
        result = run_backup_execute_with_drive_watch(
            source_root,
            backup_root,
            cancel_check=lambda: False,
        )
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1

    if not isinstance(result, dict):
        print("Backup execution returned an invalid response.", file=sys.stderr)
        return 1

    if result.get("ok", True) is False:
        operator_message = str(result.get("operator_message") or "").strip()
        raw_error = str(result.get("error") or "").strip()
        print(operator_message or raw_error or "Backup execution failed.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
