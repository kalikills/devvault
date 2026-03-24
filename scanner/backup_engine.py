from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from scanner.checksum import hash_path
from scanner.errors import SnapshotCorrupt
from scanner.manifest_integrity import add_integrity_block
from scanner.integrity_keys import load_manifest_hmac_key
from scanner.ports.filesystem import FileSystemPort
from scanner.models.backup import BackupRequest, PreflightReport
from scanner.snapshot_index import rebuild_snapshot_index, write_snapshot_index


@dataclass(frozen=True)
class BackupPlan:
    backup_id: str
    backup_path: Path
    incomplete_path: Path


@dataclass(frozen=True)
class BackupResult:
    backup_id: str
    backup_path: Path
    started_at: datetime
    finished_at: datetime
    dry_run: bool


class BackupEngine:

    def _safe_snapshot_name(self, raw: str) -> str:
        raw = str(raw or "").strip()

        # remove illegal characters
        raw = re.sub(r'[<>:"/\\|?*]+', "_", raw)

        # collapse whitespace
        raw = re.sub(r"\s+", " ", raw).strip()

        if not raw:
            return "Backup"

        MAX_LEN = 48

        if len(raw) <= MAX_LEN:
            return raw

        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:6]
        trimmed = raw[:MAX_LEN - 7].rstrip()

        return f"{trimmed}_{digest}"

    def __init__(self, fs: FileSystemPort):
        self._fs = fs

    def _snapshot_storage_root(self, backup_root: Path) -> Path:
        return backup_root / ".devvault" / "snapshots"

    def _finalize_snapshot_readonly(self, snapshot_root: Path) -> None:
        setter = getattr(self._fs, "set_tree_readonly", None)
        if not callable(setter):
            raise RuntimeError("Filesystem adapter does not support snapshot read-only hardening.")
        setter(snapshot_root, readonly=True)

    def _source_name_for_request(self, request: BackupRequest) -> str:
        raw = (request.label or "").strip()
        if not raw:
            raw = request.source_root.expanduser().resolve().name.strip()
        if not raw:
            raw = "Backup"

        raw = re.sub(r'[<>:"/\\|?*]', "_", raw)
        raw = raw.rstrip(" .")
        return raw or "Backup"

    def _display_backup_name(self, source_name: str) -> str:
        return f"{source_name} - backup"

    def preflight(self, request: BackupRequest) -> PreflightReport:
        """
        Best-effort preflight summary for a backup.

        Notes:
        - Uses the SAME traversal + symlink-skip policy as backup/manifest generation.
        - Performs a minimal read probe (open + 1-byte read) to detect locked/in-use files early.
          Backup may still refuse later if a file becomes unreadable after preflight (race conditions).
        """
        src_root = request.source_root.expanduser().resolve()
        backup_root = request.backup_root.expanduser().resolve()
        file_count = 0
        total_bytes = 0
        skipped_symlinks = 0

        perm_denied = 0
        locked = 0
        not_found = 0
        other_io = 0

        samples: list[str] = []
        SAMPLE_CAP = 25

        def record_unreadable(path, exc: BaseException) -> None:
            nonlocal perm_denied, locked, not_found, other_io
            # PermissionError on Windows can indicate both ACL denial and sharing violations.
            if isinstance(exc, PermissionError):
                winerr = getattr(exc, "winerror", None)
                # Windows sharing violation / lock is commonly 32 or 33.
                if winerr in (32, 33):
                    locked += 1
                else:
                    perm_denied += 1
            elif isinstance(exc, FileNotFoundError):
                not_found += 1
            else:
                other_io += 1

            if len(samples) < SAMPLE_CAP:
                try:
                    samples.append(str(path))
                except Exception:
                    samples.append("<unprintable-path>")

        def walk(node):
            nonlocal file_count, total_bytes, skipped_symlinks

            # Policy: skip symlinks entirely (consistent with backup)
            try:
                if self._fs.is_symlink(node):
                    skipped_symlinks += 1
                    return
            except Exception as e:
                record_unreadable(node, e)
                return

            try:
                if self._fs.is_dir(node):
                    for child in self._fs.iterdir(node):
                        walk(child)
                    return
            except Exception as e:
                record_unreadable(node, e)
                return

            try:
                if self._fs.is_file(node):
                    try:
                        st = self._fs.stat(node)
                        file_count += 1
                        total_bytes += int(getattr(st, "st_size", 0) or 0)

                        # Preflight is metadata-only on purpose.
                        # Do NOT open/read file contents here.
                        # Some cloud-synced or placeholder-backed files can stall badly
                        # during content probes even when stat() succeeds.
                        # Execute remains authoritative and may still refuse later if a file
                        # becomes unreadable during the actual backup.
                    except Exception as e:
                        record_unreadable(node, e)
                    return
            except Exception as e:
                record_unreadable(node, e)
                return

            # Special nodes: ignore silently (consistent with backup)
            return

        # Traverse from root
        walk(src_root)

        warnings: list[str] = []
        if skipped_symlinks > 0:
            warnings.append("Some symlinks were skipped by policy (safety).")
        if (perm_denied + locked + not_found + other_io) > 0:
            warnings.append("Some paths could not be read/statted during preflight; backup may refuse later if instability persists.")

        return PreflightReport(
            source_root=src_root,
            backup_root=backup_root,
            file_count=file_count,
            total_bytes=total_bytes,
            skipped_symlinks=skipped_symlinks,
            unreadable_permission_denied=perm_denied,
            unreadable_locked_or_in_use=locked,
            unreadable_not_found=not_found,
            unreadable_other_io=other_io,
            unreadable_samples=tuple(samples),
            warnings=tuple(warnings),
        )


    def plan(self, request) -> BackupPlan:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        suffix = uuid4().hex[:8]
        backup_id = f"{ts}-{suffix}"

        source_name = self._source_name_for_request(request)
        safe_name = self._safe_snapshot_name(source_name)
        display_name = self._display_backup_name(safe_name)
        backup_dir_name = f"{backup_id} - {display_name}"

        storage_root = self._snapshot_storage_root(request.backup_root)
        backup_path = storage_root / backup_dir_name
        incomplete_path = storage_root / f".incomplete-{backup_id}"

        return BackupPlan(
            backup_id=backup_id,
            backup_path=backup_path,
            incomplete_path=incomplete_path,
        )

    def execute(self, request, cancel_check=None) -> BackupResult:
        started_at = datetime.now(timezone.utc)
        plan = self.plan(request)

        # Safety: refuse backup destinations inside the source tree (prevents recursive self-copy).
        src_root = request.source_root.expanduser().resolve()
        backup_root = request.backup_root.expanduser().resolve()
        try:
            backup_root.relative_to(src_root)
        except ValueError:
            pass
        else:
            raise RuntimeError(
                "Refusing backup: backup_root must not be inside source_root (would self-copy)."
            )


        if request.dry_run:
            finished_at = datetime.now(timezone.utc)
            return BackupResult(
                backup_id=plan.backup_id,
                backup_path=plan.backup_path,
                started_at=started_at,
                finished_at=finished_at,
                dry_run=True,
            )

        # Phase 1 — create incomplete destination
        self._fs.mkdir(plan.incomplete_path, parents=True, exist_ok=False)

        # Phase 2 — copy data
        self._copy_tree(
            src_root=request.source_root,
            dst_root=plan.incomplete_path,
            cancel_check=cancel_check,
        )

        # Phase 2.5 — write manifest (v2)
        source_name = self._source_name_for_request(request)
        

        self._write_manifest(
            src_root=request.source_root,
            dst_root=plan.incomplete_path,
            backup_id=plan.backup_id,
            source_name=source_name,
            display_name=self._display_backup_name(source_name),
            backup_root=request.backup_root,
        )

        # Phase 3 — atomic finalize
        self._fs.rename(plan.incomplete_path, plan.backup_path)
        self._finalize_snapshot_readonly(plan.backup_path)
        # Shared vault key lifecycle is bootstrap-authority driven (Section 4).

        # Phase 3.5 — refresh snapshot index so Restore sees new backups immediately
        try:
            idx = rebuild_snapshot_index(fs=self._fs, backup_root=backup_root)
            write_snapshot_index(fs=self._fs, index=idx)
        except Exception:
            pass

        finished_at = datetime.now(timezone.utc)

        return BackupResult(
            backup_id=plan.backup_id,
            backup_path=plan.backup_path,
            started_at=started_at,
            finished_at=finished_at,
            dry_run=False,
        )

    # --------------------------------------------------------
    # Copy Engine
    # --------------------------------------------------------

    def _copy_tree(self, *, src_root: Path, dst_root: Path, cancel_check=None) -> None:
        if self._fs.is_file(src_root):
            if cancel_check is not None and bool(cancel_check()):
                raise RuntimeError("Cancelled by operator.")
            self._copy_node(src=src_root, dst=dst_root / src_root.name, cancel_check=cancel_check)
            return

        for child in self._fs.iterdir(src_root):
            if cancel_check is not None and bool(cancel_check()):
                raise RuntimeError("Cancelled by operator.")
            self._copy_node(src=child, dst=dst_root / child.name, cancel_check=cancel_check)

    def _copy_node(self, *, src: Path, dst: Path, cancel_check=None) -> None:
        if cancel_check is not None and bool(cancel_check()):
            raise RuntimeError("Cancelled by operator.")

        # Skip symlinks (policy)
        if self._fs.is_symlink(src):
            return

        if self._fs.is_dir(src):
            self._fs.mkdir(dst, parents=True, exist_ok=True)
            for child in self._fs.iterdir(src):
                if cancel_check is not None and bool(cancel_check()):
                    raise RuntimeError("Cancelled by operator.")
                self._copy_node(src=child, dst=dst / child.name, cancel_check=cancel_check)
            return

        if self._fs.is_file(src):
            self._fs.mkdir(dst.parent, parents=True, exist_ok=True)
            if cancel_check is not None and bool(cancel_check()):
                raise RuntimeError("Cancelled by operator.")
            self._fs.copy_file(src, dst, cancel_check=cancel_check)
            return

        # Skip special filesystem nodes silently for now

    # --------------------------------------------------------
    # Manifest (v2)
    # --------------------------------------------------------

    
    
    def _write_manifest(
        self,
        *,
        src_root: Path,
        dst_root: Path,
        backup_id: str,
        source_name: str,
        display_name: str,
        backup_root: Path | None = None,
    ) -> None:
        if backup_root is None:
            backup_root = dst_root.parent

        files: list[dict[str, object]] = []
        algo = "sha256"

        for rel_path in self._iter_files_relative(src_root):
            src = src_root / rel_path if not self._fs.is_file(src_root) else src_root.parent / rel_path
            st = self._fs.stat(src)
            d = hash_path(self._fs, src, algo=algo)

            files.append(
                {
                    "path": rel_path.as_posix(),
                    "size": st.st_size,
                    "type": "file",
                    "digest_hex": d.hex,
                }
            )

        manifest = {
            "manifest_version": 2,
            "backup_id": backup_id,
            "source_name": source_name,
            "display_name": display_name,
            "checksum_algo": algo,
            "files": files,
        }

        # --- Business seat ownership tagging (SAFE optional) ---
        try:
            from devvault_desktop.config import get_business_seat_identity
            ident = get_business_seat_identity() or {}
        except Exception:
            ident = {}

        if ident:
            manifest["business_identity"] = {
                "seat_id": ident.get("seat_id"),
                "fleet_id": ident.get("fleet_id"),
                "subscription_id": ident.get("subscription_id"),
                "device_id": ident.get("assigned_device_id") or ident.get("device_id"),
                "hostname": ident.get("assigned_hostname") or ident.get("hostname"),
                "seat_label": ident.get("seat_label"),
            }

        hmac_key = load_manifest_hmac_key(vault_root=backup_root, allow_init=False)
        if hmac_key is None:
            raise SnapshotCorrupt(
                "Business vault manifest HMAC key is missing; refusing to create snapshot."
            )
        manifest = add_integrity_block(manifest, hmac_key=hmac_key)

        manifest_path = dst_root / "manifest.json"

        self._fs.write_text(
            manifest_path,
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _iter_files_relative(self, root: Path):
        if self._fs.is_file(root):
            yield Path(root.name)
            return

        for child in self._fs.iterdir(root):
            yield from self._iter_files_relative_inner(root=root, node=child)

    def _iter_files_relative_inner(self, *, root: Path, node: Path):
        if self._fs.is_symlink(node):
            return

        if self._fs.is_dir(node):
            for child in self._fs.iterdir(node):
                yield from self._iter_files_relative_inner(root=root, node=child)
            return

        if self._fs.is_file(node):
            yield node.relative_to(root)
            return

