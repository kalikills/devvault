from __future__ import annotations

from dataclasses import dataclass

try:
    import ctypes
    from ctypes import wintypes
except Exception:  # pragma: no cover
    ctypes = None
    wintypes = None


@dataclass(frozen=True)
class WorkArea:
    x: int
    y: int
    w: int
    h: int


def _fallback_work_area(win) -> WorkArea:
    """
    Best-effort usable area. vroot* often excludes taskbar, but not always
    across multi-monitor/DPI combos.
    """
    win.update_idletasks()
    sw = int(win.winfo_screenwidth())
    sh = int(win.winfo_screenheight())

    try:
        vh = int(win.winfo_vrootheight())
        vy = int(win.winfo_vrooty())
        usable_h = vh if vh > 0 else sh
        top_y = vy if vh > 0 else 0
    except Exception:
        usable_h = sh
        top_y = 0

    return WorkArea(0, top_y, sw, usable_h)


def get_work_area_for_window(win) -> WorkArea:
    """
    Return the monitor WORK AREA (taskbar excluded) for the monitor that
    currently contains the given Tk window.
    """
    win.update_idletasks()

    if ctypes is None:
        return _fallback_work_area(win)

    try:
        hwnd = int(win.winfo_id())
        if hwnd == 0:
            return _fallback_work_area(win)

        user32 = ctypes.windll.user32

        MONITOR_DEFAULTTONEAREST = 2

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        monitor = user32.MonitorFromWindow(wintypes.HWND(hwnd), MONITOR_DEFAULTTONEAREST)
        if not monitor:
            return _fallback_work_area(win)

        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)

        ok = user32.GetMonitorInfoW(monitor, ctypes.byref(info))
        if not ok:
            return _fallback_work_area(win)

        work = info.rcWork
        x = int(work.left)
        y = int(work.top)
        w = int(work.right - work.left)
        h = int(work.bottom - work.top)

        if w <= 0 or h <= 0:
            return _fallback_work_area(win)

        return WorkArea(x, y, w, h)

    except Exception:
        return _fallback_work_area(win)
