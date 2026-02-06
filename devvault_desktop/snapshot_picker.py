from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from dataclasses import dataclass
from pathlib import Path

from scanner.adapters.filesystem import OSFileSystem
from scanner.snapshot_rows import get_snapshot_rows


@dataclass(frozen=True)
class PickedSnapshot:
    snapshot_id: str
    snapshot_dir: Path


class SnapshotPicker(tk.Toplevel):
    """Modal dialog for selecting a snapshot from the vault (no directory browsing)."""

    def __init__(self, parent: tk.Tk, *, vault_dir: Path) -> None:
        super().__init__(parent)

        self.title("Select Snapshot")
        self.minsize(520, 320)
        self.resizable(True, True)

        self.transient(parent)
        self.grab_set()

        self._picked: PickedSnapshot | None = None

        self._vault_dir = vault_dir

        fs = OSFileSystem()
        rows = get_snapshot_rows(fs=fs, backup_root=vault_dir)

        if not rows:
            messagebox.showerror(
                "No snapshots found",
                "No valid snapshots were found in the selected vault.",
                parent=self,
            )
            self.destroy()
            return

        # ---- Layout ----
        header = tk.Label(self, text="Select a snapshot to restore", font=("Arial", 12, "bold"))
        header.pack(padx=12, pady=(12, 6), anchor="w")

        self._list = tk.Listbox(self, height=12)
        self._list.pack(padx=12, pady=(0, 10), fill="both", expand=True)

        for r in rows:
            created = r.created_at.isoformat(sep=" ", timespec="seconds") if r.created_at else "unknown time"
            size_kb = max(1, r.total_bytes // 1024)
            label = f"{created} — {r.file_count} files — {size_kb} KB"
            self._list.insert(tk.END, label)

        self._list.selection_set(0)

        btns = tk.Frame(self)
        btns.pack(padx=12, pady=(0, 12), anchor="e")

        cancel = tk.Button(btns, text="Cancel", width=10, command=self._cancel)
        cancel.grid(row=0, column=0, padx=(0, 8))

        select = tk.Button(btns, text="Select", width=10, command=self._select)
        select.grid(row=0, column=1)

        # convenience keys
        self.bind("<Escape>", lambda _e: self._cancel())
        self.bind("<Return>", lambda _e: self._select())

        # keep ids accessible for selection
        self._snap_by_index = {i: r.snapshot_id for i, r in enumerate(rows)}

    def _cancel(self) -> None:
        self._picked = None
        self.destroy()

    def _select(self) -> None:
        sel = self._list.curselection()
        if not sel:
            return
        idx = sel[0]
        snap_id = self._snap_by_index[idx]
        snap_dir = self._vault_dir / snap_id
        self._picked = PickedSnapshot(snapshot_id=snap_id, snapshot_dir=snap_dir)
        self.destroy()

    def pick(self) -> PickedSnapshot | None:
        self.wait_window(self)
        return self._picked
