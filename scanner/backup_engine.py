from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from scanner.checksum import hash_path
from scanner.manifest_integrity import add_integrity_block
from scanner.integrity_keys import load_manifest_hmac_key
from scanner.ports.filesystem import FileSystemPort
from scanner.models.backup import BackupRequest, PreflightReport


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
    def __init__(self, fs: FileSystemPort):
        self._fs = fs

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

                        # Minimal read probe: detect share-locked/in-use files early (Windows).
                        # This is best-effort: backup may still refuse later due to races.
                        try:
                            with self._fs.open_read(node) as fh:
                                _ = fh.read(1)
                        except Exception as e:
                            record_unreadable(node, e)
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

        backup_path = request.backup_root / backup_id
        incomplete_path = request.backup_root / f".incomplete-{backup_id}"

        return BackupPlan(
            backup_id=backup_id,
            backup_path=backup_path,
            incomplete_path=incomplete_path,
        )

    def execute(self, request) -> BackupResult:
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
        )

        # Phase 2.5 — write manifest (v2)
        self._write_manifest(
            src_root=request.source_root,
            dst_root=plan.incomplete_path,
        )

        # Phase 3 — atomic finalize
        self._fs.rename(plan.incomplete_path, plan.backup_path)

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

    def _copy_tree(self, *, src_root: Path, dst_root: Path) -> None:
        for child in self._fs.iterdir(src_root):
            self._copy_node(src=child, dst=dst_root / child.name)

    def _copy_node(self, *, src: Path, dst: Path) -> None:
        # Skip symlinks (policy)
        if self._fs.is_symlink(src):
            return

        if self._fs.is_dir(src):
            self._fs.mkdir(dst, parents=True, exist_ok=True)
            for child in self._fs.iterdir(src):
                self._copy_node(src=child, dst=dst / child.name)
            return

        if self._fs.is_file(src):
            self._fs.mkdir(dst.parent, parents=True, exist_ok=True)
            self._fs.copy_file(src, dst)
            return

        # Skip special filesystem nodes silently for now

    # --------------------------------------------------------
    # Manifest (v2)
    # --------------------------------------------------------

    def _write_manifest(self, *, src_root: Path, dst_root: Path, backup_root: Path | None = None) -> None:
        if backup_root is None:
            backup_root = dst_root.parent
        files: list[dict[str, object]] = []
        algo = "sha256"

        for rel_path in self._iter_files_relative(src_root):
            src = src_root / rel_path
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
            "checksum_algo": algo,
            "files": files,
        }

        hmac_key = load_manifest_hmac_key(vault_root=dst_root.parent, allow_init=False)
        manifest = add_integrity_block(manifest, hmac_key=hmac_key)

        manifest_path = dst_root / "manifest.json"

        self._fs.write_text(
            manifest_path,
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _iter_files_relative(self, root: Path):
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








