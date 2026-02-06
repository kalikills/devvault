from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

from scanner.vault_health import check_vault_health

from devvault_desktop.config import set_vault_dir
from scanner.adapters.filesystem import OSFileSystem
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


class DevVaultApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("DevVault")
        self.minsize(560, 320)

        # Header
        hdr = tk.Label(self, text="DevVault", font=("Arial", 20, "bold"))
        hdr.pack(pady=(16, 4))

        # Vault label + warning (dynamic)
        self.vault_label = tk.Label(self, text="", font=("Arial", 10))
        self.vault_label.pack(pady=(0, 4))

        self.warn_label = tk.Label(self, text="", fg="orange", font=("Arial", 10))
        self.warn_label.pack(pady=(0, 8))

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=8)

        self.backup_btn = tk.Button(btn_frame, text="Make Backup", width=18, command=self.on_backup)
        self.backup_btn.grid(row=0, column=0, padx=8)

        self.restore_btn = tk.Button(btn_frame, text="Restore Backup", width=18, command=self.on_restore)
        self.restore_btn.grid(row=0, column=1, padx=8)

        # Settings action (not part of daily flow)
        settings_frame = tk.Frame(self)
        settings_frame.pack(pady=(2, 8))

        self.change_vault_btn = tk.Button(
            settings_frame,
            text="Change Vault",
            width=14,
            command=self.on_change_vault,
        )
        self.change_vault_btn.grid(row=0, column=0, padx=8)

        # Log area
        self.log = tk.Text(self, height=10, width=78, state="disabled")
        self.log.pack(padx=12, pady=(12, 12))

        # Initialize label text after widgets exist
        self._refresh_vault_ui()

    def _log(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", msg.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.backup_btn.configure(state=state)
        self.restore_btn.configure(state=state)
        self.change_vault_btn.configure(state=state)
        self.update_idletasks()

    def _refresh_vault_ui(self) -> None:
        vault_resolved = get_vault_dir()
        self.vault_label.configure(
            text=f"Vault: {DEFAULT_VAULT_WINDOWS}  →  {vault_resolved}"
        )

        warn = best_effort_fs_warning(vault_resolved)
        self.warn_label.configure(text=f"Warning: {warn}" if warn else "")

    def _require_healthy_vault(self) -> bool:
        vault_dir = get_vault_dir()
        fs = OSFileSystem()
        res = check_vault_health(fs=fs, backup_root=vault_dir)
        if not res.ok:
            messagebox.showerror(
                "Vault Unhealthy",
                f"Vault is not healthy:\n{vault_dir}\n\nReason: {res.reason}",
            )
            return False
        return True

    def on_change_vault(self) -> None:
        chosen = filedialog.askdirectory(title="Select vault folder (backup destination)")
        if not chosen:
            return

        chosen_path = Path(chosen)

        # Fail-closed: validate before saving.
        reason = vault_preflight(chosen_path)
        if reason is not None:
            messagebox.showerror("Vault Not Available", f"Vault not available:\n{chosen_path}\n\nReason: {reason}")
            return

        # Persist selection (desktop config)
        try:
            set_vault_dir(str(chosen_path))
        except Exception as e:
            messagebox.showerror("Save Failed", str(e))
            return

        self._log(f"Vault set to: {chosen_path}")
        self._refresh_vault_ui()
        messagebox.showinfo("Vault Updated", f"Vault set to:\n{chosen_path}")

    def on_backup(self) -> None:
        src = filedialog.askdirectory(title="Select folder to back up")
        if not src:
            return

        src_path = Path(src)

        if not self._require_healthy_vault():
            return

        self._set_busy(True)
        try:
            self._refresh_vault_ui()
            self._log(f"Backup: source={src_path}")
            payload = backup(source_dir=src_path)
            backup_path = payload.get("backup_path", "")
            self._log(f"OK: backup_path={backup_path}")
            messagebox.showinfo("Backup Complete", f"Backup created:\n{backup_path}")
        except Exception as e:
            self._log(f"ERROR: {e}")
            messagebox.showerror("Backup Failed", str(e))
        finally:
            self._set_busy(False)

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

        # Fail-closed destination preflight BEFORE engine call
        pre = preflight_restore_destination(dst_path)
        if not pre.ok:
            messagebox.showerror("Invalid Restore Destination", pre.reason)
            return

        self._set_busy(True)
        try:
            self._refresh_vault_ui()
            self._log(f"Restore: snapshot={snap_path}")
            self._log(f"Restore: destination={dst_path}")
            _payload = restore(snapshot_dir=snap_path, destination_dir=dst_path)
            self._log("OK: restore completed")
            messagebox.showinfo("Restore Complete", "Restore completed successfully.")
        except Exception as e:
            self._log(f"ERROR: {e}")
            messagebox.showerror("Restore Failed", str(e))
        finally:
            self._set_busy(False)


def main() -> int:
    app = DevVaultApp()
    app.mainloop()
    return 0
