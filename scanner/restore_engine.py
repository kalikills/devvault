from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scanner.ports.filesystem import FileSystemPort


@dataclass(frozen=True)
class RestoreRequest:
    snapshot_dir: Path
    destination_dir: Path


class RestoreEngine:
    def __init__(self, fs: FileSystemPort):
        self.fs = fs

    def restore(self, req: RestoreRequest) -> None:
        # --- Validate snapshot ---
        if not self.fs.exists(req.snapshot_dir):
            raise RuntimeError("Snapshot directory does not exist.")

        if not self.fs.is_dir(req.snapshot_dir):
            raise RuntimeError("Snapshot path is not a directory.")

        # Safety boundary: never restore from an incomplete snapshot directory name.
        if req.snapshot_dir.name.startswith(".incomplete-"):
            raise RuntimeError("Refusing to restore from an incomplete snapshot.")

        manifest_path = req.snapshot_dir / "manifest.json"
        if not self.fs.exists(manifest_path):
            raise RuntimeError("Snapshot is missing manifest.json")

        # --- Validate destination ---
        if self.fs.exists(req.destination_dir):
            if not self.fs.is_dir(req.destination_dir):
                raise RuntimeError("Destination exists but is not a directory.")
            # Strong safety rule: destination must be empty.
            if any(self.fs.iterdir(req.destination_dir)):
                raise RuntimeError("Destination directory must be empty.")
        else:
            self.fs.mkdir(req.destination_dir, parents=True)

        # --- Load manifest ---
        manifest = json.loads(self.fs.read_text(manifest_path))

        files = manifest.get("files")
        if not isinstance(files, list):
            raise RuntimeError("Invalid manifest: expected 'files' list.")

        # --- Restore files ---
        for item in files:
            rel = item.get("path")
            if not isinstance(rel, str) or rel == "":
                raise RuntimeError("Invalid manifest entry: file path must be a non-empty string.")

            src = req.snapshot_dir / rel
            dst = req.destination_dir / rel

            parent = dst.parent
            if not self.fs.exists(parent):
                self.fs.mkdir(parent, parents=True)

            self.fs.copy_file(src, dst)
