from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

from pathlib import Path

from devvault_desktop.runner import (
    DEFAULT_VAULT_WINDOWS,
    best_effort_fs_warning,
    get_vault_dir,
    backup,
    restore,
)


class DevVaultApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("DevVault")
        self.minsize(560, 300)

        # Header
        hdr = tk.Label(self, text="DevVault", font=("Arial", 20, "bold"))
        hdr.pack(pady=(16, 4))

        # Show canonical vault (Windows) + resolved (current runtime)
        vault_resolved = get_vault_dir()
        sub = tk.Label(
            self,
            text=f"Vault (fixed): {DEFAULT_VAULT_WINDOWS}  →  {vault_resolved}",
            font=("Arial", 10),
        )
        sub.pack(pady=(0, 8))

        warn = best_effort_fs_warning(vault_resolved)
        if warn:
            w = tk.Label(self, text=f"Warning: {warn}", fg="orange", font=("Arial", 10))
            w.pack(pady=(0, 8))

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=8)

        self.backup_btn = tk.Button(btn_frame, text="Make Backup", width=18, command=self.on_backup)
        self.backup_btn.grid(row=0, column=0, padx=8)

        self.restore_btn = tk.Button(btn_frame, text="Restore Backup", width=18, command=self.on_restore)
        self.restore_btn.grid(row=0, column=1, padx=8)

        # Log area
        self.log = tk.Text(self, height=10, width=78, state="disabled")
        self.log.pack(padx=12, pady=(12, 12))

    def _log(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", msg.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.backup_btn.configure(state=state)
        self.restore_btn.configure(state=state)
        self.update_idletasks()

    def on_backup(self) -> None:
        src = filedialog.askdirectory(title="Select folder to back up")
        if not src:
            return

        src_path = Path(src)

        self._set_busy(True)
        try:
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
        snap = filedialog.askdirectory(title="Select snapshot directory to restore from")
        if not snap:
            return

        dst = filedialog.askdirectory(title="Select EMPTY destination directory for restore")
        if not dst:
            return

        snap_path = Path(snap)
        dst_path = Path(dst)

        self._set_busy(True)
        try:
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
