from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class PreflightDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, *, title: str, banner_lines: list[str], detail_lines: list[str]) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result: bool | None = None

        # Modal behavior
        self.transient(parent)
        self.grab_set()

        outer = tk.Frame(self, padx=14, pady=12)
        outer.pack(fill="both", expand=True)

        # Banner (trust framing)
        banner = tk.Label(
            outer,
            text="\n".join(banner_lines),
            justify="left",
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        )
        banner.pack(fill="x", pady=(0, 10))

        # Details (monospace block)
        details = tk.Text(
            outer,
            width=64,
            height=min(16, max(8, len(detail_lines) + 2)),
            wrap="none",
            font=("Consolas", 10),
            borderwidth=1,
            relief="solid",
        )
        details.insert("1.0", "\n".join(detail_lines))
        details.configure(state="disabled")
        details.pack(fill="both", expand=True)

        # Buttons
        btn_row = tk.Frame(outer)
        btn_row.pack(fill="x", pady=(12, 0))

        btn_row.columnconfigure(0, weight=1)

        cancel_btn = ttk.Button(btn_row, text="Cancel", command=self._cancel)
        ok_btn = ttk.Button(btn_row, text="OK", command=self._ok)

        cancel_btn.grid(row=0, column=1, padx=(0, 8))
        ok_btn.grid(row=0, column=2)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

        # Center on parent
        self.update_idletasks()
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + (pw // 2) - (w // 2)
            y = py + (ph // 2) - (h // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _ok(self) -> None:
        self.result = True
        self.destroy()

    def _cancel(self) -> None:
        self.result = False
        self.destroy()

    def show(self) -> bool:
        self.wait_window(self)
        return bool(self.result)
