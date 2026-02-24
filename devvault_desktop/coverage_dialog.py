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


# --- Win32: monitor work-area (excludes taskbar), per-window monitor-aware ---
def _work_area_for_window(hwnd: int) -> tuple[int, int, int, int] | None:
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        MONITOR_DEFAULTTONEAREST = 2

        class RECT(ctypes.Structure):
            _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG), ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        MonitorFromWindow = user32.MonitorFromWindow
        MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        MonitorFromWindow.restype = wintypes.HMONITOR

        GetMonitorInfoW = user32.GetMonitorInfoW
        GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
        GetMonitorInfoW.restype = wintypes.BOOL

        hmon = MonitorFromWindow(wintypes.HWND(hwnd), MONITOR_DEFAULTTONEAREST)
        if not hmon:
            return None

        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if not GetMonitorInfoW(hmon, ctypes.byref(mi)):
            return None

        wa = mi.rcWork
        x = int(wa.left)
        y = int(wa.top)
        w = int(wa.right - wa.left)
        h = int(wa.bottom - wa.top)
        return (x, y, w, h)
    except Exception:
        return None


class CoverageDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, *, uncovered: list[Path]) -> None:
        super().__init__(parent)
        self.title("Coverage Required")

        # Modal behavior
        self.transient(parent)
        self.grab_set()

        # Prevent the “giant DPI” runaway and allow proper layout
        self.resizable(True, True)

        self._uncovered = uncovered
        self._result: CoverageDecision | None = None

        # Build UI first
        banner = tk.Label(
            self,
            text="UNPROTECTED PROJECTS DETECTED",
            font=("Segoe UI", 12, "bold"),
            fg="#c1121f",
        )
        banner.pack(padx=16, pady=(14, 6), anchor="w")

        sub = tk.Label(
            self,
            text="DevVault requires an explicit decision before backup can proceed.",
            font=("Segoe UI", 10),
        )
        sub.pack(padx=16, pady=(0, 10), anchor="w")

        # List area (fill available space)
        frame = tk.Frame(self)
        frame.pack(padx=16, pady=(0, 10), fill="both", expand=True)

        self.listbox = tk.Listbox(frame)
        self.listbox.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(frame, orient="vertical", command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=sb.set)

        for pth in uncovered:
            self.listbox.insert("end", str(pth))

        btns = tk.Frame(self)
        btns.pack(padx=16, pady=(0, 14), fill="x")

        tk.Button(btns, text="Protect All", command=self._protect_all).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="Ignore All", command=self._ignore_all).pack(side="left", padx=(0, 8))
        tk.Button(btns, text="Close (Still Blocked)", command=self._close_blocked).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._close_blocked)

        # Place AFTER widgets exist, on the correct monitor, inside the work-area.
        # Withdraw first to prevent the “flash then jump”.
        self.withdraw()
        self.after(0, lambda: self._apply_geometry(parent))

    def _apply_geometry(self, parent: tk.Tk) -> None:
        self.update_idletasks()

        # Prefer the parent’s monitor, fallback to self’s screen
        hwnd = int(parent.winfo_id()) if parent.winfo_exists() else int(self.winfo_id())
        wa = _work_area_for_window(hwnd)

        if wa is None:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            wa_x, wa_y, wa_w, wa_h = 0, 0, sw, sh
        else:
            wa_x, wa_y, wa_w, wa_h = wa

        # Dialog size: smaller than main window feel, hard-capped
        w = min(780, max(620, int(wa_w * 0.55)))
        h = min(460, max(340, int(wa_h * 0.40)))

        # Center within work area (keeps it above taskbar)
        x = wa_x + max(0, (wa_w - w) // 2)
        y = wa_y + max(0, (wa_h - h) // 2)

        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(620, 340)
        self.maxsize(780, 460)

        # Ensure it’s on top and focused
        self.deiconify()
        self.lift()
        try:
            self.attributes("-topmost", True)
            self.after(200, lambda: self.attributes("-topmost", False))
        except Exception:
            pass
        self.focus_force()

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
            "Ignore Coverage?",
            "Ignored projects will NOT be protected.\n\nAre you sure?",
            parent=self,
        ):
            return
        for pth in self._uncovered:
            ignore_candidate(str(pth))
        self._result = CoverageDecision(protected=[], ignored=list(self._uncovered))
        self.destroy()

    def _close_blocked(self) -> None:
        self._result = None
        self.destroy()
