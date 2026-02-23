from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox

from devvault_desktop.config import add_protected_root, ignore_candidate


@dataclass(frozen=True)
class CoverageDecision:
    protected: list[Path]
    ignored: list[Path]


class CoverageDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, *, uncovered: list[Path]) -> None:
        super().__init__(parent)
        self.title("Coverage Required")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._uncovered = uncovered
        self._result: CoverageDecision | None = None

        banner = tk.Label(
            self,
            text="UNPROTECTED PROJECTS DETECTED",
            font=("Segoe UI", 12, "bold"),
            fg="#c1121f",
        )
        banner.pack(padx=16, pady=(14, 6))

        sub = tk.Label(
            self,
            text="DevVault requires an explicit decision before backup can proceed.",
            font=("Segoe UI", 10),
        )
        sub.pack(padx=16, pady=(0, 10))

        self.listbox = tk.Listbox(self, width=90, height=min(10, max(4, len(uncovered))))
        for pth in uncovered:
            self.listbox.insert("end", str(pth))
        self.listbox.pack(padx=16, pady=(0, 10))

        btns = tk.Frame(self)
        btns.pack(padx=16, pady=(0, 14), fill="x")

        tk.Button(btns, text="Protect All", command=self._protect_all).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="Ignore All", command=self._ignore_all).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="Close (Still Blocked)", command=self._close_blocked).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._close_blocked)

    def show(self) -> CoverageDecision | None:
        self.wait_window(self)
        return self._result

    def _protect_all(self) -> None:
        for pth in self._uncovered:
            add_protected_root(str(pth))
        self._result = CoverageDecision(protected=list(self._uncovered), ignored=[])
        self.destroy()

    def _ignore_all(self) -> None:
        if not messagebox.askyesno(
            "Confirm Ignore",
            "Ignoring means DevVault will not warn you about these projects again. Continue?",
            parent=self,
        ):
            return
        for pth in self._uncovered:
            ignore_candidate(str(pth))
        self._result = CoverageDecision(protected=[], ignored=list(self._uncovered))
        self.destroy()

    def _close_blocked(self) -> None:
        # No decision recorded; caller should keep backup blocked.
        self._result = None
        self.destroy()
