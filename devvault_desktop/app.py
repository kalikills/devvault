from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from devvault_desktop.config import set_vault_dir
from devvault_desktop.vault_gate import require_vault_ready
from devvault_desktop.snapshot_picker import SnapshotPicker
from devvault_desktop.restore_preflight import preflight_restore_destination

from devvault_desktop.runner import (
    DEFAULT_VAULT_WINDOWS,
    best_effort_fs_warning,
    get_vault_dir,
    vault_preflight,
    backup,
    restore,
)

SLOGAN = "DevVault is a safety system for people whose work cannot be Replaced."
TRUSTWARE_LINE = "Trustware: if anything looks unsafe, DevVault refuses."


class DevVaultApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        # Crime-scene theme (black + caution yellow + red accent)
        self.BG = "#0b0b0b"
        self.FG = "#f5d000"      # caution yellow
        self.ACCENT = "#c1121f"  # warning red
        self.BTN_BG = "#141414"
        self.LOG_BG = "#000000"  # "white box" feel
        self.LOG_FG = "#1FEB1C"

        self.title("DevVault")
        self.minsize(560, 360)
        self.configure(bg=self.BG)

        # Titlebar icon (top-left) — use .ico (reliable on Windows)
        try:
            ico_path = Path(__file__).with_name("assets") / "vault.ico"
            if ico_path.exists():
                self.iconbitmap(default=str(ico_path))
        except Exception:
            pass

        # ---------- ROOT CONTAINER (centers the entire UI) ----------
        container = tk.Frame(self, bg=self.BG)
        container.pack(expand=True)

        # ---------- Header ----------
        header = tk.Frame(container, bg=self.BG)
        header.pack(padx=12, pady=(14, 6))

        title_row = tk.Frame(header, bg=self.BG)
        title_row.pack()

        tk.Label(
            title_row,
            text="🔒",
            font=("Arial", 20, "bold"),
            fg=self.FG,
            bg=self.BG,
        ).pack(side="left", padx=(0, 10))

        tk.Label(
            title_row,
            text="D E V V A U L T",
            font=("Arial", 22, "bold"),
            fg=self.FG,
            bg=self.BG,
        ).pack(side="left")

        tk.Label(
            title_row,
            text=" 🔒",
            font=("Arial", 20, "bold"),
            fg=self.FG,
            bg=self.BG,
        ).pack(side="left", padx=(0, 10))

        tk.Label(
            header,
            text=SLOGAN,
            font=("Arial", 10),
            fg=self.FG,
            bg=self.BG,
        ).pack(pady=(4, 0))

        # ---------- Vault Labels ----------
        self.vault_label = tk.Label(
            container,
            text="",
            font=("Arial", 10, "bold"),
            fg=self.FG,
            bg=self.BG,
        )
        self.vault_label.pack(pady=(10, 0))

        self.vault_default_label = tk.Label(
            container,
            text="",
            font=("Arial", 9),
            fg=self.FG,
            bg=self.BG,
        )
        self.vault_default_label.pack(pady=(2, 0))

        self.warn_label = tk.Label(
            container,
            text="",
            font=("Arial", 10, "bold"),
            fg=self.ACCENT,
            bg=self.BG,
        )
        self.warn_label.pack(pady=(6, 10))

        # ---------- Buttons ----------
        btn_frame = tk.Frame(container, bg=self.BG)
        btn_frame.pack(pady=(0, 10))

        self.backup_btn = tk.Button(
            btn_frame,
            text="Make Backup",
            width=18,
            command=self.on_backup,
            bg=self.BTN_BG,
            fg=self.FG,
            activebackground=self.ACCENT,
            activeforeground="white",
            relief="raised",
        )
        self.backup_btn.grid(row=0, column=0, padx=8)

        self.restore_btn = tk.Button(
            btn_frame,
            text="Restore Backup",
            width=18,
            command=self.on_restore,
            bg=self.BTN_BG,
            fg=self.FG,
            activebackground=self.ACCENT,
            activeforeground="white",
            relief="raised",
        )
        self.restore_btn.grid(row=0, column=1, padx=8)

        # ---------- Vault Button ----------
        settings_frame = tk.Frame(container, bg=self.BG)
        settings_frame.pack(pady=(0, 10))

        self.change_vault_btn = tk.Button(
            settings_frame,
            text="Change Vault",
            width=18,
            command=self.on_change_vault,
            bg=self.BTN_BG,
            fg=self.FG,
            activebackground=self.ACCENT,
            activeforeground="white",
            relief="raised",
        )
        self.change_vault_btn.pack()

        tk.Label(
            settings_frame,
            text="Vault = where your backups are safe.",
            font=("Arial", 9),
            fg=self.FG,
            bg=self.BG,
        ).pack(pady=(4, 0))

        # ---------- Loading overlay (hidden unless busy) ----------
        self._loading_running = False
        self._loading_phase = 0

        self.loading_icon_var = tk.StringVar(value="🔒")
        self.loading_msg_var = tk.StringVar(value="Working…")
        self.loading_dots_var = tk.StringVar(value="")

        self.loading_overlay = tk.Frame(self, bg=self.BG)

        overlay_card = tk.Frame(self.loading_overlay, bg=self.BG)
        overlay_card.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            overlay_card,
            textvariable=self.loading_icon_var,
            font=("Segoe UI", 48, "bold"),
            fg=self.FG,
            bg=self.BG,
        ).pack()

        tk.Label(
            overlay_card,
            textvariable=self.loading_msg_var,
            font=("Segoe UI", 14, "bold"),
            fg=self.FG,
            bg=self.BG,
        ).pack(pady=(10, 0))

        tk.Label(
            overlay_card,
            textvariable=self.loading_dots_var,
            font=("Segoe UI", 14, "bold"),
            fg=self.FG,
            bg=self.BG,
        ).pack()


        # ---------- Log ----------
        self.log = tk.Text(
            container,
            height=10,
            width=78,
            state="disabled",
            bg=self.LOG_BG,
            fg=self.LOG_FG,
        )
        self.log.pack(padx=24, pady=(8, 12), fill="both", expand=True)

        # Initialize label text after widgets exist
        self._refresh_vault_ui()

        # Startup log (no slogan repeat)
        self._log("Welcome to DevVault.")
        self._log(TRUSTWARE_LINE)
        self._log("Choose an action: Make Backup or Restore Backup.")
        self._log("Vault open and ready....")

    def _log(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", msg.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_status(self, msg: str) -> None:
        self._log(msg)

    def _show_loading(self, msg: str = "Working…") -> None:
        self.loading_msg_var.set(msg)
        self.loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.loading_overlay.lift()
        self._loading_running = True
        self._loading_phase = 0
        self._tick_loading()

    def _hide_loading(self) -> None:
        self._loading_running = False
        self.loading_overlay.place_forget()

    def _tick_loading(self) -> None:
        if not getattr(self, "_loading_running", False):
            return

        # Lock animation: 🔓 → 🔒 → 🔒 (shake dots) → 🔓 ...
        frames = ["🔓", "🔒", "🔒", "🔒"]
        dots = ["", ".", "..", "..."]
        icon = frames[self._loading_phase % len(frames)]
        trail = dots[self._loading_phase % len(dots)]

        self.loading_icon_var.set(icon)
        self.loading_dots_var.set(trail)

        self._loading_phase += 1
        self.after(220, self._tick_loading)


    def _set_busy(self, busy: bool, status: str | None = None) -> None:
        state = "disabled" if busy else "normal"
        self.backup_btn.configure(state=state)
        self.restore_btn.configure(state=state)
        self.change_vault_btn.configure(state=state)

        if status:
            self._set_status(status)

        # Loading screen only while busy
        try:
            if busy:
                self._show_loading("Securing changes…")
            else:
                self._hide_loading()
        except Exception:
            pass

        self.update_idletasks()


    def _refresh_vault_ui(self) -> None:
        vault_resolved = get_vault_dir()

        self.vault_label.configure(text=f"Current backup location: {vault_resolved}")
        self.vault_default_label.configure(text=f"System default: {DEFAULT_VAULT_WINDOWS}")

        warn = best_effort_fs_warning(vault_resolved)
        self.warn_label.configure(text=f"WARNING: {warn}" if warn else "")

    def _require_healthy_vault(self) -> bool:
        vault_dir = get_vault_dir()
        res = require_vault_ready(vault_dir=vault_dir)
        if not res.ok:
            messagebox.showerror(
                "Vault Unhealthy",
                f"Vault is not ready:\n{vault_dir}\n\nReason: {res.reason}",
            )
            return False
        return True

    def on_change_vault(self) -> None:
        chosen = filedialog.askdirectory(title="Select vault folder (backup destination)")
        if not chosen:
            return

        chosen_path = Path(chosen)

        reason = vault_preflight(chosen_path)
        if reason is not None:
            messagebox.showerror(
                "Vault Not Available",
                f"Vault not available:\n{chosen_path}\n\nReason: {reason}",
            )
            return

        try:
            set_vault_dir(str(chosen_path))
        except Exception as e:
            messagebox.showerror("Save Failed", str(e))
            return

        self._refresh_vault_ui()
        self._set_status(f"Vault updated: {chosen_path}")
        messagebox.showinfo("Vault Updated", f"Vault set to:\n{chosen_path}")

    def on_backup(self) -> None:
        src = filedialog.askdirectory(title="Select folder to back up")
        if not src:
            return

        src_path = Path(src)

        if not self._require_healthy_vault():
            return

        self._set_busy(True, status=f"Backup started: {src_path}")
        try:
            self._refresh_vault_ui()
            payload = backup(source_dir=src_path)
            backup_path = payload.get("backup_path", "")
            self._set_status(f"Backup complete: {backup_path}")
            messagebox.showinfo("Backup Complete", f"Backup created:\n{backup_path}")
        except Exception as e:
            self._set_status(f"ERROR (backup): {e}")
            messagebox.showerror("Backup Failed", str(e))
        finally:
            self._set_busy(False, status="Vault open and ready....")

    def on_restore(self) -> None:
        vault_dir = get_vault_dir()

        if not self._require_healthy_vault():
            return

        picker = SnapshotPicker(self, vault_dir=vault_dir)
        picked = picker.pick()
        if not picked:
            return

        dst = filedialog.askdirectory(title="Select EMPTY destination directory for restore")
        if not dst:
            return

        snap_path = picked.snapshot_dir
        dst_path = Path(dst)

        pre = preflight_restore_destination(dst_path)
        if not pre.ok:
            messagebox.showerror("Invalid Restore Destination", pre.reason)
            return

        self._set_busy(True, status=f"Restore started: {snap_path} → {dst_path}")
        try:
            self._refresh_vault_ui()
            _payload = restore(snapshot_dir=snap_path, destination_dir=dst_path)
            self._set_status("Restore complete.")
            messagebox.showinfo("Restore Complete", "Restore completed successfully.")
        except Exception as e:
            self._set_status(f"ERROR (restore): {e}")
            messagebox.showerror("Restore Failed", str(e))
        finally:
            self._set_busy(False, status="Vault open and ready....")


def main() -> int:
    app = DevVaultApp()
    app.mainloop()
    return 0
