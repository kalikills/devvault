from __future__ import annotations

from scanner.errors import SnapshotCorrupt, RestoreRefused

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scanner.checksum import hash_path
from scanner.manifest_integrity import verify_manifest_integrity
from scanner.integrity_keys import load_manifest_hmac_key
from scanner.manifest_schema import validate_crypto_stanza
from scanner.ports.filesystem import FileSystemPort


@dataclass(frozen=True)
class RestoreRequest:
    snapshot_dir: Path
    destination_dir: Path


class RestoreEngine:
    def __init__(self, fs: FileSystemPort):
        self.fs = fs

    def _vault_root_for_snapshot(self, snapshot_dir: Path) -> Path:
        parent = snapshot_dir.parent
        if parent.name == "snapshots" and parent.parent.name == ".devvault":
            return parent.parent.parent
        return parent

    def _validate_snapshot_identity(self, *, snapshot_dir: Path, manifest: dict) -> None:
        backup_id = manifest.get("backup_id")
        if backup_id is None:
            return
        if not isinstance(backup_id, str) or not backup_id.strip():
            raise SnapshotCorrupt("Invalid manifest: backup_id must be a non-empty string.")

        display_name = manifest.get("display_name")
        if display_name is not None and not isinstance(display_name, str):
            raise SnapshotCorrupt("Invalid manifest: display_name must be a string.")

        expected_dir_name = backup_id.strip()
        if isinstance(display_name, str) and display_name.strip():
            expected_dir_name = f"{backup_id.strip()} - {display_name.strip()}"

        if snapshot_dir.name != expected_dir_name:
            raise SnapshotCorrupt(
                "Snapshot identity mismatch: folder name does not match manifest metadata."
            )

    def _build_restore_manifest_text(
        self,
        *,
        snapshot_id: str,
        restored_at: str,
        mappings: list[tuple[Path, Path]],
    ) -> str:
        lines = [
            "DevVault Restore Manifest",
            f"Snapshot ID: {snapshot_id}",
            f"Restore Timestamp: {restored_at}",
            "",
            "Mapping:",
        ]
        for original_rel, restored_rel in mappings:
            lines.append(f"{original_rel.as_posix()} -> {restored_rel.as_posix()}")
        lines.append("")
        return "\n".join(lines)

    def _write_restore_manifest(
        self,
        *,
        destination_dir: Path,
        snapshot_id: str,
        mappings: list[tuple[Path, Path]],
    ) -> None:
        manifest_path = destination_dir / "_restore_manifest.txt"
        manifest_text = self._build_restore_manifest_text(
            snapshot_id=snapshot_id,
            restored_at=datetime.now(timezone.utc).isoformat(),
            mappings=mappings,
        )
        self.fs.write_text(manifest_path, manifest_text, encoding="utf-8")

    def restore(self, req: RestoreRequest, cancel_check=None) -> None: # Section7 runtime fix
        # --- Validate snapshot ---
        if not self.fs.exists(req.snapshot_dir):
            raise SnapshotCorrupt("Snapshot directory does not exist.")

        if not self.fs.is_dir(req.snapshot_dir):
            raise SnapshotCorrupt("Snapshot path is not a directory.")

        # Safety boundary: never restore from an incomplete snapshot directory name.
        if req.snapshot_dir.name.startswith(".incomplete-"):
            raise SnapshotCorrupt("Refusing to restore from an incomplete snapshot.")

        manifest_path = req.snapshot_dir / "manifest.json"
        if not self.fs.exists(manifest_path):
            raise SnapshotCorrupt("Snapshot is missing manifest.json")

        # --- Validate destination (do not create yet) ---
        if self.fs.exists(req.destination_dir):
            if not self.fs.is_dir(req.destination_dir):
                raise RestoreRefused("Destination exists but is not a directory.")
            if any(self.fs.iterdir(req.destination_dir)):
                raise RestoreRefused("Destination directory must be empty.")

        # --- Load + validate manifest (fail closed) ---
        try:
            manifest = json.loads(self.fs.read_text(manifest_path))
        except json.JSONDecodeError:
            raise RuntimeError(
                f"Snapshot manifest is invalid JSON; refusing restore. Path: {manifest_path}"
            ) from None

        hmac_key = load_manifest_hmac_key(
            vault_root=self._vault_root_for_snapshot(req.snapshot_dir)
        )

        ok, reason = verify_manifest_integrity(manifest, hmac_key=hmac_key)
        if not ok:
            if reason == "missing-hmac-key":
                raise SnapshotCorrupt("Business vault manifest HMAC key is missing; refusing restore.")
            raise SnapshotCorrupt("Invalid manifest: integrity check failed.")

        validate_crypto_stanza(manifest)
        self._validate_snapshot_identity(snapshot_dir=req.snapshot_dir, manifest=manifest)

        files = manifest.get("files")
        if not isinstance(files, list):
            raise SnapshotCorrupt("Invalid manifest: expected 'files' list.")

        manifest_version = manifest.get("manifest_version")
        is_v2 = manifest_version == 2

        checksum_algo = manifest.get("checksum_algo") if is_v2 else None
        if is_v2 and checksum_algo != "sha256":
            raise SnapshotCorrupt("Invalid manifest: unsupported checksum algorithm.")

        # Preflight: validate paths + source file existence + size before touching destination.
        # For v2, also validate digest fields are present and plausible.
        to_copy: list[tuple[Path, Path, int, str | None]] = []

        for item in files:
            rel = item.get("path")
            size = item.get("size")

            if not isinstance(rel, str) or rel == "":
                raise SnapshotCorrupt("Invalid manifest entry: file path must be a non-empty string.")
            if not isinstance(size, int) or size < 0:
                raise SnapshotCorrupt("Invalid manifest entry: file size must be a non-negative integer.")

            digest_hex: str | None = None
            if is_v2:
                dh = item.get("digest_hex")
                if not isinstance(dh, str) or dh == "":
                    raise SnapshotCorrupt("Invalid manifest entry: missing digest.")
                if len(dh) != 64:
                    raise SnapshotCorrupt("Invalid manifest entry: invalid digest format.")
                digest_hex = dh

            rel_path = Path(rel)

            # Security: refuse absolute paths and traversal segments.
            if rel_path.is_absolute() or ".." in rel_path.parts:
                raise SnapshotCorrupt("Invalid manifest entry: unsafe path.")

            src = req.snapshot_dir / rel_path
            dst_rel = rel_path

            if not self.fs.exists(src) or not self.fs.is_file(src):
                raise SnapshotCorrupt("Snapshot is corrupt: referenced file missing.")

            st = self.fs.stat(src)
            if st.st_size != size:
                raise SnapshotCorrupt("Snapshot is corrupt: file size mismatch.")

            to_copy.append((src, dst_rel, size, digest_hex))

        # --- Apply restore (now we touch destination) ---
        # If destination does not exist, stage into a sibling directory and only promote on success.
        staged = False
        stage_dir = req.destination_dir.parent / (req.destination_dir.name + ".devvault.staging")
        restore_root = req.destination_dir

        if not self.fs.exists(req.destination_dir):
            if self.fs.exists(stage_dir):
                raise RestoreRefused("Refusing restore: staging directory already exists.")
            self.fs.mkdir(stage_dir, parents=True)
            restore_root = stage_dir
            staged = True

        restored_mappings: list[tuple[Path, Path]] = []

        for src, rel_path, _size, digest_hex in to_copy:
            dst = restore_root / rel_path

            parent = dst.parent
            if not self.fs.exists(parent):
                self.fs.mkdir(parent, parents=True)

            if not is_v2:
                try:
                    self.fs.copy_file(src, dst)
                    restored_mappings.append((rel_path, rel_path))
                    continue
                except Exception as e:
                    raise RuntimeError(
                        "Restore file apply failed: "
                        f"src={src} | dst={dst} | rel={rel_path} | error={e}"
                    ) from e

            tmp = Path(str(dst) + ".devvault.tmp")

            try:
                self.fs.copy_file(src, tmp)
            except Exception as e:
                raise RuntimeError(
                    "Restore temp copy failed: "
                    f"src={src} | tmp={tmp} | dst={dst} | rel={rel_path} | error={e}"
                ) from e

            try:
                d = hash_path(self.fs, tmp, algo="sha256")
                if d.hex != digest_hex:
                    raise SnapshotCorrupt("Restore verification failed: checksum mismatch.")
                self.fs.rename(tmp, dst)
                restored_mappings.append((rel_path, rel_path))
            except Exception as e:
                if self.fs.exists(tmp):
                    try:
                        self.fs.unlink(tmp)
                    except Exception:
                        pass
                raise RuntimeError(
                    "Restore finalize failed: "
                    f"src={src} | tmp={tmp} | dst={dst} | rel={rel_path} | error={e}"
                ) from e

        # Promote staged restore only after all files verified.
        if staged:
            self.fs.rename(stage_dir, req.destination_dir)

        self._write_restore_manifest(
            destination_dir=req.destination_dir,
            snapshot_id=req.snapshot_dir.name,
            mappings=restored_mappings,
        )
