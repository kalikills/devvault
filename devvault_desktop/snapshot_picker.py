from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from dataclasses import dataclass
from pathlib import Path

from scanner.adapters.filesystem import OSFileSystem
from scanner.snapshot_listing import list_snapshots


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

        fs = OSFileSystem()
        snaps = list_snapshots(fs=fs, backup_root=vault_dir)

        if not snaps:
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

        for s in snaps:
            self._list.insert(tk.END, s.snapshot_id)

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
        self._snap_by_id = {s.snapshot_id: s.snapshot_dir for s in snaps}

    def _cancel(self) -> None:
        self._picked = None
        self.destroy()

    def _select(self) -> None:
        sel = self._list.curselection()
        if not sel:
            return
        snap_id = str(self._list.get(sel[0]))
        snap_dir = self._snap_by_id[snap_id]
        self._picked = PickedSnapshot(snapshot_id=snap_id, snapshot_dir=snap_dir)
        self.destroy()

    def pick(self) -> PickedSnapshot | None:
        self.wait_window(self)
        return self._picked
