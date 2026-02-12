from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scanner.checksum import hash_path
from scanner.integrity_keys import load_manifest_hmac_key_from_env
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

    def verify(self, req: VerifyRequest) -> VerifyResult:
        if not self.fs.exists(req.snapshot_dir):
            raise RuntimeError("Snapshot directory does not exist.")
        if not self.fs.is_dir(req.snapshot_dir):
            raise RuntimeError("Snapshot path is not a directory.")
        if req.snapshot_dir.name.startswith(".incomplete-"):
            raise RuntimeError("Refusing to verify an incomplete snapshot.")

        manifest_path = req.snapshot_dir / "manifest.json"
        if not self.fs.exists(manifest_path):
            raise RuntimeError("Snapshot is missing manifest.json")

        try:
            manifest = json.loads(self.fs.read_text(manifest_path))
        except json.JSONDecodeError:
            raise RuntimeError(
                f"Snapshot manifest is invalid JSON; refusing verify. Path: {manifest_path}"
            ) from None

        hmac_key = load_manifest_hmac_key_from_env()
        ok, _reason = verify_manifest_integrity(manifest, hmac_key=hmac_key)
        if not ok:
            raise RuntimeError("Invalid manifest: integrity check failed.")

        validate_crypto_stanza(manifest)

        files = manifest.get("files")
        if not isinstance(files, list):
            raise RuntimeError("Invalid manifest: expected 'files' list.")

        manifest_version = manifest.get("manifest_version")
        is_v2 = manifest_version == 2

        checksum_algo = manifest.get("checksum_algo") if is_v2 else None
        if is_v2 and checksum_algo != "sha256":
            raise RuntimeError("Invalid manifest: unsupported checksum algorithm.")

        verified = 0

        for item in files:
            rel = item.get("path")
            size = item.get("size")

            if not isinstance(rel, str) or rel == "":
                raise RuntimeError("Invalid manifest entry: file path must be a non-empty string.")
            if not isinstance(size, int) or size < 0:
                raise RuntimeError("Invalid manifest entry: file size must be a non-negative integer.")

            digest_hex = None
            if is_v2:
                dh = item.get("digest_hex")
                if not isinstance(dh, str) or dh == "":
                    raise RuntimeError("Invalid manifest entry: missing digest.")
                if len(dh) != 64:
                    raise RuntimeError("Invalid manifest entry: invalid digest format.")
                digest_hex = dh

            rel_path = Path(rel)
            if rel_path.is_absolute() or ".." in rel_path.parts:
                raise RuntimeError("Invalid manifest entry: unsafe path.")

            src = req.snapshot_dir / rel_path
            if not self.fs.exists(src) or not self.fs.is_file(src):
                raise RuntimeError("Snapshot is corrupt: referenced file missing.")

            st = self.fs.stat(src)
            if st.st_size != size:
                raise RuntimeError("Snapshot is corrupt: file size mismatch.")

            if is_v2:
                d = hash_path(self.fs, src, algo="sha256")
                if d.hex != digest_hex:
                    raise RuntimeError("Snapshot verification failed: checksum mismatch.")

            verified += 1

        return VerifyResult(snapshot_dir=req.snapshot_dir, files_verified=verified)

