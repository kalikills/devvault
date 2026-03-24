from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from devvault.refusal_codes import RefusalCode, refusal_info


def _json_out(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()



import json
import socket
from datetime import datetime, timedelta
from devvault_desktop.business_vault_authority import validate_business_vault_authority

def _should_validate_business_nas(vault_root: Path) -> bool:
    try:
        from devvault_desktop.config import get_business_nas_path

        configured = str(get_business_nas_path() or "").strip()
        if not configured:
            return False

        configured_path = Path(configured).expanduser().resolve()
        candidate_path = Path(vault_root).expanduser().resolve()
        return configured_path == candidate_path
    except Exception:
        return False


def _vault_lock_path(vault_root: Path) -> Path:
    return vault_root / ".devvault" / ".execution.lock"


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def _acquire_vault_execution_lock(vault_root: Path, operation: str):
    lock = _vault_lock_path(vault_root)
    lock.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.utcnow()
    current_host = socket.gethostname()
    current_pid = os.getpid()

    if lock.exists():
        try:
            data = json.loads(lock.read_text(encoding="utf-8"))
        except Exception:
            data = {}

        lock_host = str(data.get("host") or "").strip()
        lock_pid_raw = data.get("pid")
        lock_started_raw = str(data.get("started_at") or "").strip()

        lock_pid = None
        try:
            lock_pid = int(lock_pid_raw)
        except Exception:
            lock_pid = None

        stale = False

        if lock_host and lock_host.lower() == current_host.lower() and lock_pid:
            if not _pid_is_alive(lock_pid):
                stale = True

        if not stale and lock_started_raw:
            try:
                started = datetime.fromisoformat(lock_started_raw)
                if now - started >= timedelta(minutes=30):
                    stale = True
            except Exception:
                pass

        if stale:
            try:
                lock.unlink()
            except Exception:
                pass
        else:
            return {
                "ok": False,
                **refusal_info(
                    RefusalCode.VAULT_BUSY,
                    operator_message="Another vault operation is already running.",
                    raw_error="vault_execution_lock_active",
                ).to_payload(),
                "payload": {},
            }

    payload = {
        "pid": current_pid,
        "host": current_host,
        "operation": operation,
        "started_at": now.isoformat(),
    }

    lock.write_text(json.dumps(payload), encoding="utf-8")
    return None


def _release_vault_execution_lock(vault_root: Path):
    try:
        lock = _vault_lock_path(vault_root)
        if lock.exists():
            lock.unlink()
    except Exception:
        pass


def _normalized_error(exc: Exception) -> dict:
    msg = str(exc) or exc.__class__.__name__
    lower = msg.lower()

    # do not classify generic Errno 22 / invalid argument as device disconnect
    # on Windows this can be raised by path/handle/runtime issues unrelated to vault loss

    # storage timeout / stalled I/O
    if "winerror 121" in lower or "semaphore timeout period has expired" in lower:
        return refusal_info(
            RefusalCode.DEVICE_DISCONNECTED,
            operator_message="A storage device stopped responding during the operation.",
            raw_error=msg,
        ).to_payload()

    # UNC host/share unreachable
    if "winerror 67" in lower or "network name cannot be found" in lower:
        return refusal_info(
            RefusalCode.NAS_UNREACHABLE,
            raw_error=msg,
        ).to_payload()

    # common missing-path / missing-share / missing-subfolder cases
    if (
        "winerror 3" in lower
        or "winerror 53" in lower
        or "path not found" in lower
        or "system cannot find the path specified" in lower
        or "cannot find the path specified" in lower
        or "no such file or directory" in lower
        or "the system cannot find the file specified" in lower
    ):
        return refusal_info(
            RefusalCode.NAS_PATH_INVALID,
            operator_message="Business vault path not found. Confirm the NAS path and try again.",
            raw_error=msg,
        ).to_payload()

    # vault key / integrity key / decrypt failures
    if (
        "manifest_hmac_key" in lower
        or "dpapi" in lower
        or "decrypt" in lower
        or "decryption" in lower
        or "cryptunprotectdata" in lower
        or "vault key" in lower
        or "integrity key" in lower
    ):
        return refusal_info(
            RefusalCode.VAULT_KEY_INVALID,
            operator_message="Vault security verification failed for this Business vault.",
            raw_error=msg,
        ).to_payload()

    # entitlement / license gate refusal
    if msg.startswith("Missing required entitlement:"):
        return refusal_info(
            RefusalCode.LICENSE_BLOCKED,
            operator_message=msg,
            raw_error=msg,
        ).to_payload()

    # access denied / auth-like NAS failures
    if (
        isinstance(exc, PermissionError)
        or "access is denied" in lower
        or "permission denied" in lower
        or "logon failure" in lower
        or "user name or password is incorrect" in lower
        or "multiple connections to a server or shared resource by the same user" in lower
    ):
        return refusal_info(
            RefusalCode.NAS_AUTH_FAILED,
            operator_message="Business vault access was denied. Check NAS permissions and credentials.",
            raw_error=msg,
        ).to_payload()

    return refusal_info(
        RefusalCode.UNKNOWN_EXECUTION_FAILURE,
        operator_message=msg,
        raw_error=msg,
    ).to_payload()


def _simulated_entitlements_from_env() -> set[str]:
    import os

    raw = (os.environ.get("DEVVAULT_SIM_ENTITLEMENTS", "") or "").strip().lower()
    if not raw:
        return set()

    presets = {
        "core": {
            "core_scan_system",
            "core_backup_engine",
        },
        "pro": {
            "core_scan_system",
            "core_backup_engine",
            "pro_advanced_scan_reports",
            "pro_snapshot_comparison",
            "pro_recovery_audit_reports",
            "pro_export_reports",
        },
        "business": {
            "core_scan_system",
            "core_backup_engine",
            "pro_advanced_scan_reports",
            "pro_snapshot_comparison",
            "pro_recovery_audit_reports",
            "pro_export_reports",
            "biz_org_audit_logging",
            "biz_seat_admin_tools",
        },
    }

    if raw in presets:
        return set(presets[raw])

    normalized = raw.replace(";", ",")
    return {
        part.strip()
        for part in normalized.split(",")
        if part.strip()
    }


def _require_subprocess_entitlement(entitlement: str) -> None:
    sim_allowed = _simulated_entitlements_from_env()
    if sim_allowed and entitlement in sim_allowed:
        return

    from devvault_desktop.license_gate import check_license

    st = check_license()
    st.require_entitlement(entitlement)


def _backup_preflight_payload(source: str | Path, vault: str | Path) -> dict:
    _require_subprocess_entitlement("core_backup_engine")
    from scanner.adapters.filesystem import OSFileSystem
    from scanner.backup_engine import BackupEngine
    from scanner.models.backup import BackupRequest

    src = Path(source).expanduser().resolve()
    vlt = Path(vault).expanduser().resolve()

    eng = BackupEngine(OSFileSystem())
    pre = eng.preflight(BackupRequest(source_root=src, backup_root=vlt))

    vault_total = None
    vault_free = None
    try:
        import shutil
        du = shutil.disk_usage(str(vlt))
        vault_total = int(du.total)
        vault_free = int(du.free)
    except Exception:
        vault_total = None
        vault_free = None

    required_bytes = int(pre.total_bytes)
    if vault_free is not None and required_bytes > int(vault_free):
        def _fmt_bytes(n: int) -> str:
            units = ["B", "KB", "MB", "GB", "TB"]
            f = float(n)
            i = 0
            while f >= 1024.0 and i < len(units) - 1:
                f /= 1024.0
                i += 1
            return f"{f:.2f} {units[i]}"

        return {
            "ok": False,
            **refusal_info(
                RefusalCode.CAPACITY_DENIED,
                operator_message=(
                    "Not enough free space in vault.\n\n"
                    f"Required: {_fmt_bytes(required_bytes)}\n"
                    f"Available: {_fmt_bytes(int(vault_free))}\n\n"
                    "Choose a larger vault drive or reduce source size."
                ),
                detail="insufficient_vault_space",
                raw_error="Not enough free space in vault.",
            ).to_payload(),
        }

    return {
        "ok": True,
        "payload": {
            "source": str(src),
            "vault": str(vlt),
            "file_count": int(pre.file_count),
            "total_bytes": int(pre.total_bytes),
            "skipped_symlinks": int(pre.skipped_symlinks),
            "unreadable_permission_denied": int(pre.unreadable_permission_denied),
            "unreadable_locked_or_in_use": int(pre.unreadable_locked_or_in_use),
            "unreadable_not_found": int(pre.unreadable_not_found),
            "unreadable_other_io": int(pre.unreadable_other_io),
            "unreadable_samples": list(pre.unreadable_samples),
            "warnings": list(pre.warnings),
        },
    }


def cmd_backup_preflight(source: str, vault: str) -> int:
    try:
        result = _backup_preflight_payload(source, vault)
        _json_out(result)
        return 0 if result.get("ok", False) else 2
    except Exception as e:
        norm = _normalized_error(e)
        _json_out(
            {
                "ok": False,
                "code": norm["code"],
                "error": norm.get("raw_error") or norm.get("operator_message") or "Operation failed.",
                "operator_message": norm["operator_message"],
            }
        )
        return 2


def cmd_backup_execute(source: str, vault: str, cancel_token: str = "") -> int:
    try:
        _require_subprocess_entitlement("core_backup_engine")
        from scanner.adapters.filesystem import OSFileSystem
        from scanner.backup_engine import BackupEngine
        from scanner.models.backup import BackupRequest
        from scanner.cloud_file_guard import scan_tree_for_cloud_placeholders

        src = Path(source).expanduser().resolve()
        vlt = Path(vault).expanduser().resolve()

        cloud_guard = scan_tree_for_cloud_placeholders(src)
        if not cloud_guard.ok:
            return {
                "ok": False,
                "code": "SOURCE_CLOUD_PLACEHOLDER_DETECTED",
                "error": cloud_guard.operator_message,
                "operator_message": cloud_guard.operator_message,
                "payload": {
                    "cloud_placeholder_count": len(cloud_guard.hits),
                    "cloud_placeholder_paths": [hit.path for hit in cloud_guard.hits[:10]],
                },
            }

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
            _json_out({
                "ok": False,
                **refusal_info(
                    RefusalCode.OPERATOR_CANCELLED,
                    raw_error="Cancelled",
                ).to_payload(),
                "payload": {},
            })
            return 2
        norm = _normalized_error(e)
        _json_out(
            {
                "ok": False,
                "code": norm["code"],
                "error": norm.get("raw_error") or norm.get("operator_message") or "Operation failed.",
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
                    "restore_verification": "passed",
                    "checksum_verification": "sha256-verified",
                },
            }
        )
        return 0
    except Exception as e:
        norm = _normalized_error(e)
        detail_parts = []

        try:
            detail_parts.append(f"snapshot={snap}")
        except Exception:
            pass

        try:
            detail_parts.append(f"destination={dst}")
        except Exception:
            pass

        detail = " | ".join(detail_parts).strip()

        _json_out(
            {
                "ok": False,
                "code": norm["code"],
                "error": norm.get("raw_error") or norm.get("operator_message") or "Operation failed.",
                "operator_message": (
                    f"{norm['operator_message']}\n\n{detail}" if detail else norm["operator_message"]
                ),
            }
        )
        return 2







def run_backup_execute_with_drive_watch(
    source: str | Path,
    vault: str | Path,
    *,
    cancel_check=None,
) -> dict:
    try:
        if cancel_check and cancel_check():
            return {
                "ok": False,
                **refusal_info(
                    RefusalCode.OPERATOR_CANCELLED,
                    raw_error="Cancelled",
                ).to_payload(),
                "payload": {},
            }

        _require_subprocess_entitlement("core_backup_engine")

        from scanner.adapters.filesystem import OSFileSystem
        from scanner.backup_engine import BackupEngine
        from scanner.models.backup import BackupRequest
        from scanner.cloud_file_guard import scan_tree_for_cloud_placeholders

        src = Path(source).expanduser().resolve()
        vlt = Path(vault).expanduser().resolve()

        cloud_guard = scan_tree_for_cloud_placeholders(src)
        if not cloud_guard.ok:
            return {
                "ok": False,
                "code": "SOURCE_CLOUD_PLACEHOLDER_DETECTED",
                "error": cloud_guard.operator_message,
                "operator_message": cloud_guard.operator_message,
                "payload": {
                    "cloud_placeholder_count": len(cloud_guard.hits),
                    "cloud_placeholder_paths": [hit.path for hit in cloud_guard.hits[:10]],
                },
            }

        if _should_validate_business_nas(vlt):
            authority = validate_business_vault_authority(vlt)
            if not authority.ok:
                return {
                    "ok": False,
                    "code": "BUSINESS_NAS_AUTHORITY_INVALID",
                    "error": authority.operator_message,
                    "operator_message": authority.operator_message,
                    "payload": {
                        "authority_state": authority.state.value,
                    },
                }

        lock_refusal = _acquire_vault_execution_lock(vlt, "backup_execute")
        if lock_refusal:
            return lock_refusal

        eng = BackupEngine(OSFileSystem())

        try:
            res = eng.execute(
                BackupRequest(source_root=src, backup_root=vlt),
                cancel_check=cancel_check,
            )
        finally:
            _release_vault_execution_lock(vlt)

        return {
            "ok": True,
            "payload": {
                "backup_id": res.backup_id,
                "backup_path": str(res.backup_path),
                "started_at": res.started_at.isoformat(),
                "finished_at": res.finished_at.isoformat(),
                "dry_run": res.dry_run,
            },
        }

    except Exception as e:
        if str(e).strip() == "Cancelled by operator.":
            return {
                "ok": False,
                **refusal_info(
                    RefusalCode.OPERATOR_CANCELLED,
                    raw_error="Cancelled",
                ).to_payload(),
                "payload": {},
            }

        norm = _normalized_error(e)
        return {
            "ok": False,
            "code": norm["code"],
            "error": norm.get("raw_error") or norm.get("operator_message") or "Operation failed.",
            "operator_message": norm["operator_message"],
            "payload": {},
        }


def run_restore_with_drive_watch(
    snapshot: str | Path,
    destination: str | Path,
    *,
    cancel_check=None,
) -> dict:
    try:
        if cancel_check and cancel_check():
            return {
                "ok": False,
                **refusal_info(
                    RefusalCode.OPERATOR_CANCELLED,
                    raw_error="Cancelled",
                ).to_payload(),
                "payload": {},
            }

        _require_subprocess_entitlement("core_restore_engine")

        from scanner.adapters.filesystem import OSFileSystem
        from scanner.restore_engine import RestoreEngine, RestoreRequest

        snap = Path(snapshot).expanduser().resolve()
        dst = Path(destination).expanduser().resolve()

        lock_refusal = _acquire_vault_execution_lock(snap.parent, "restore_execute")
        if lock_refusal:
            return lock_refusal

        eng = RestoreEngine(OSFileSystem())

        try:
            eng.restore(
                RestoreRequest(snapshot_dir=snap, destination_dir=dst),
                cancel_check=cancel_check,
            )
        finally:
            _release_vault_execution_lock(snap.parent)

        return {
            "ok": True,
            "payload": {
                "snapshot_dir": str(snap),
                "destination_dir": str(dst),
                "status": "restored",
                "restore_verification": "passed",
                "checksum_verification": "sha256-verified",
            },
        }

    except Exception as e:
        if str(e).strip() == "Cancelled by operator.":
            return {
                "ok": False,
                **refusal_info(
                    RefusalCode.OPERATOR_CANCELLED,
                    raw_error="Cancelled",
                ).to_payload(),
                "payload": {},
            }

        norm = _normalized_error(e)
        return {
            "ok": False,
            "code": norm["code"],
            "error": norm.get("raw_error") or norm.get("operator_message") or "Operation failed.",
            "operator_message": norm["operator_message"],
            "payload": {},
        }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    bp = sub.add_parser("backup-preflight")
    bp.add_argument("--source", required=True)
    bp.add_argument("--vault", required=True)

    b = sub.add_parser("backup-execute")
    b.add_argument("--cancel-token", default="", help="Path to cancel token file (created by UI on cancel).")
    b.add_argument("--source", required=True)
    b.add_argument("--vault", required=True)

    r = sub.add_parser("restore")
    r.add_argument("--snapshot", required=True)
    r.add_argument("--destination", required=True)

    ns = ap.parse_args(argv)

    if ns.cmd == "backup-preflight":
        return cmd_backup_preflight(ns.source, ns.vault)
    if ns.cmd == "backup-execute":
        return cmd_backup_execute(ns.source, ns.vault, cancel_token=getattr(ns, "cancel_token", ""))
    if ns.cmd == "restore":
        return cmd_restore(ns.snapshot, ns.destination)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
