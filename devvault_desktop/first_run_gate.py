from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass

from devvault_desktop.winmon import get_work_area_for_window


@dataclass(frozen=True)
class FirstRunDecision:
    """
    Test-backed decision result for first-run gating.
    """
    allowed: bool
    uncovered_candidates: tuple[str, ...]
    require_scan: bool


def evaluate_first_run_gate(*, first_run_done: bool, uncovered_candidates: list[str]) -> FirstRunDecision:
    """
    PURE decision function (no UI).

    Contract (per tests):
    - If first_run_done is True -> allow and uncovered_candidates must be empty.
    - If not done and uncovered candidates exist -> block and include sorted tuple.
    - If not done and no uncovered -> allow and uncovered_candidates empty.
    """
    if first_run_done:
        return FirstRunDecision(allowed=True, uncovered_candidates=(), require_scan=False)

    # deterministic: sorted tuple
    uc = tuple(sorted(uncovered_candidates))

    if uc:
        return FirstRunDecision(allowed=False, uncovered_candidates=uc, require_scan=True)

    return FirstRunDecision(allowed=True, uncovered_candidates=(), require_scan=False)


class FirstRunDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk) -> None:
        super().__init__(parent)
        self.title("First-Time Setup Required")

        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        self._run_scan: bool | None = None

        body = tk.Frame(self)
        body.pack(padx=18, pady=14, fill="both", expand=True)

        msg = (
            "Welcome to DevVault.\n\n"
            "First-time setup requires a scan to identify important projects\n"
            "and confirm they are protected.\n\n"
            "Without this first scan, DevVault cannot continue.\n\n"
            "Do you agree to run the first-time scan now?"
        )

        tk.Label(body, text=msg, justify="left").pack(anchor="w")

        btns = tk.Frame(self)
        btns.pack(padx=18, pady=(0, 14), fill="x")

        tk.Button(btns, text="Yes", width=10, command=self._yes).pack(side="right", padx=(8, 0))
        tk.Button(btns, text="No", width=10, command=self._no).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._no)

        # Stable placement: withdraw → place → deiconify
        self.withdraw()
        self.after(0, lambda: self._apply_geometry(parent))

    def _apply_geometry(self, parent: tk.Tk) -> None:
        self.update_idletasks()
        wa = get_work_area_for_window(parent)

        w = min(720, max(560, int(wa.w * 0.55)))
        h = min(360, max(260, int(wa.h * 0.30)))

        x = wa.x + max(0, (wa.w - w) // 2)
        y = wa.y + max(0, (wa.h - h) // 2)

        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.lift()
        try:
            self.attributes("-topmost", True)
            self.after(200, lambda: self.attributes("-topmost", False))
        except Exception:
            pass
        self.focus_force()

    def show(self) -> bool | None:
        self.wait_window(self)
        return self._run_scan

    def _yes(self) -> None:
        self._run_scan = True
        self.destroy()

    def _no(self) -> None:
        self._run_scan = False
        self.destroy()


def prompt_first_run_scan(parent: tk.Tk) -> bool:
    """
    UI helper. Returns True if operator agrees to run scan now.
    """
    d = FirstRunDialog(parent)
    r = d.show()
    return bool(r)
