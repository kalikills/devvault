from __future__ import annotations

from scanner.errors import SnapshotCorrupt, RestoreRefused

import json
from dataclasses import dataclass
from pathlib import Path

from scanner.checksum import hash_path
from scanner.integrity_keys import load_manifest_hmac_key
from scanner.manifest_integrity import verify_manifest_integrity
from scanner.manifest_schema import validate_crypto_stanza
from scanner.ports.filesystem import FileSystemPort


@dataclass(frozen=True)
class VerifyRequest:
    snapshot_dir: Path


@dataclass(frozen=True)
class VerifyResult:
    snapshot_dir: Path
    files_verified: int


class VerifyEngine:
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

    def verify(self, req: VerifyRequest) -> VerifyResult:
        if not self.fs.exists(req.snapshot_dir):
            raise SnapshotCorrupt("Snapshot directory does not exist.")
        if not self.fs.is_dir(req.snapshot_dir):
            raise SnapshotCorrupt("Snapshot path is not a directory.")
        if req.snapshot_dir.name.startswith(".incomplete-"):
            raise SnapshotCorrupt("Refusing to verify an incomplete snapshot.")

        manifest_path = req.snapshot_dir / "manifest.json"
        if not self.fs.exists(manifest_path):
            raise SnapshotCorrupt("Snapshot is missing manifest.json")

        try:
            manifest = json.loads(self.fs.read_text(manifest_path))
        except json.JSONDecodeError:
            raise RuntimeError(
                f"Snapshot manifest is invalid JSON; refusing verify. Path: {manifest_path}"
            ) from None

        hmac_key = load_manifest_hmac_key(
            vault_root=self._vault_root_for_snapshot(req.snapshot_dir)
        )
        ok, reason = verify_manifest_integrity(manifest, hmac_key=hmac_key)
        if not ok:
            if reason == "missing-hmac-key":
                raise SnapshotCorrupt("Business vault manifest HMAC key is missing; refusing verify.")
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

        verified = 0

        for item in files:
            rel = item.get("path")
            size = item.get("size")

            if not isinstance(rel, str) or rel == "":
                raise SnapshotCorrupt("Invalid manifest entry: file path must be a non-empty string.")
            if not isinstance(size, int) or size < 0:
                raise SnapshotCorrupt("Invalid manifest entry: file size must be a non-negative integer.")

            digest_hex = None
            if is_v2:
                dh = item.get("digest_hex")
                if not isinstance(dh, str) or dh == "":
                    raise SnapshotCorrupt("Invalid manifest entry: missing digest.")
                if len(dh) != 64:
                    raise SnapshotCorrupt("Invalid manifest entry: invalid digest format.")
                digest_hex = dh

            rel_path = Path(rel)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                raise SnapshotCorrupt("Invalid manifest entry: unsafe path.")

            src = req.snapshot_dir / rel_path
            if not self.fs.exists(src) or not self.fs.is_file(src):
                raise SnapshotCorrupt("Snapshot is corrupt: referenced file missing.")

            st = self.fs.stat(src)
            if st.st_size != size:
                raise SnapshotCorrupt("Snapshot is corrupt: file size mismatch.")

            if is_v2:
                d = hash_path(self.fs, src, algo="sha256")
                if d.hex != digest_hex:
                    raise SnapshotCorrupt("Snapshot verification failed: checksum mismatch.")

            verified += 1

        return VerifyResult(snapshot_dir=req.snapshot_dir, files_verified=verified)


