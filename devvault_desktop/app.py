from __future__ import annotations

import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from devvault_desktop.config import set_vault_dir
from devvault_desktop.preflight_dialog import PreflightDialog
from devvault_desktop.restore_preflight import preflight_restore_destination
from devvault_desktop.snapshot_picker import SnapshotPicker
from devvault_desktop.vault_gate import require_vault_ready
from devvault_desktop.coverage_assurance import compute_uncovered_candidates
from devvault_desktop.coverage_dialog import CoverageDialog
from devvault_desktop.config import is_coverage_first_run_done, set_coverage_first_run_done
from devvault_desktop.config import get_last_backup_at_utc, set_last_backup_at_utc



from devvault_desktop.runner import (
    DEFAULT_VAULT_WINDOWS,
    backup,
    best_effort_fs_warning,
    get_vault_dir,
    preflight_backup,
    restore,
    vault_preflight,
)

SLOGAN = "DevVault is a safety system for people whose work cannot be Replaced."
TRUSTWARE_LINE = "Trustware: if anything looks unsafe, DevVault refuses."


def _human_bytes(n: int) -> str:
    step = 1024.0
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(max(0, int(n)))
    u = 0
    while x >= step and u < len(units) - 1:
        x /= step
        u += 1
    return f"{x:.1f} {units[u]}" if u > 0 else f"{int(x)} B"


class DevVaultApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        # Crime-scene theme (black + caution yellow + red accent)
        self.BG = "#0b0b0b"
        self.FG = "#f5d000"      # caution yellow
        self.ACCENT = "#c1121f"  # warning red
        self.BTN_BG = "#141414"
        self.LOG_BG = "#000000"  # "terminal" feel
        self.LOG_FG = "#1FEB1C"

        self.title("DevVault")
        self.minsize(560, 360)
        self.configure(bg=self.BG)

        # Titlebar icon (source + PyInstaller-safe)
        try:
            if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                base = Path(sys._MEIPASS)  # PyInstaller extraction dir
                ico_path = base / "devvault_desktop" / "assets" / "vault.ico"
            else:
                ico_path = Path(__file__).resolve().parent / "assets" / "vault.ico"

            if ico_path.exists():
                self.iconbitmap(default=str(ico_path))
        except Exception:
            pass

        # ---------- ROOT CONTAINER ----------
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

        # ---------- Loading overlay ----------
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

        self._refresh_vault_ui()
        self._log("Welcome to DevVault.")
        self._log(TRUSTWARE_LINE)
        self._log("Choose an action: Make Backup or Restore Backup.")
        self._log("Vault open and ready....")

        # Coverage First-Run Enforcement (Gate 5)
        # First launch must prevent silent exclusion of likely irreplaceable work.
        try:
            if not is_coverage_first_run_done():
                scan_roots: list[Path] = []
                candidates = [
                    Path("C:/dev"),
                    Path.home() / "dev",
                    Path.home() / "Documents",
                    Path.home() / "Desktop",
                ]
                for r in candidates:
                    if r.exists() and r.is_dir():
                        scan_roots.append(r)

                if scan_roots:
                    cov = compute_uncovered_candidates(scan_roots=scan_roots, depth=4, top=30)
                    if cov.uncovered:
                        dlg = CoverageDialog(self, uncovered=cov.uncovered)
                        decision = dlg.show()
                        if decision is None:
                            # Fail closed: quit app rather than allow unsafe operation.
                            messagebox.showerror(
                                "Coverage Required",
                                "DevVault requires a coverage decision before use.\n\nApp will now close.",
                            )
                            raise SystemExit(2)

                set_coverage_first_run_done(True)
        except SystemExit:
            raise
        except Exception as e:
            # Fail closed: if coverage check fails, refuse to start.
            messagebox.showerror("Coverage Check Failed", str(e))
            raise SystemExit(2)

        # Backup Staleness Reminder
        # If you haven't backed up in a while, DevVault must tell you.
        try:
            from datetime import datetime, timezone

            protected = get_protected_roots()
            last_s = get_last_backup_at_utc().strip()
            if protected and last_s:
                try:
                    last = datetime.fromisoformat(last_s)
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    age_days = (datetime.now(timezone.utc) - last).days
                    if age_days >= 7:
                        warn = (
                            f"WARNING: Last backup was {age_days} days ago. "
                            "Run a backup to stay protected."
                        )
                        self.warn_label.configure(text=warn)
                        self._log(warn)
                except Exception:
                    pass
        except Exception:
            pass

    # ------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------

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

    # ------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------

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

        # Gate 5 — Coverage Assurance (Option B: must acknowledge)
        # If likely projects exist outside protected roots, block until operator decides.
        try:
            scan_roots: list[Path] = []
            candidates = [
                Path("C:/dev"),
                Path.home() / "dev",
                Path.home() / "Documents",
                Path.home() / "Desktop",
            ]
            for r in candidates:
                if r.exists() and r.is_dir():
                    scan_roots.append(r)

            if scan_roots:
                cov = compute_uncovered_candidates(scan_roots=scan_roots, depth=4, top=30)
                if cov.uncovered:
                    self._set_busy(False, status="Coverage decision required.")
                    dlg = CoverageDialog(self, uncovered=cov.uncovered)
                    decision = dlg.show()
                    if decision is None:
                        self._set_status("REFUSED: Coverage not acknowledged. Backup blocked.")
                        self._set_busy(False, status="Vault open and ready....")
                        return
        except Exception as e:
            msg = str(e)
            self._set_status(f"REFUSED (coverage): {msg}")
            messagebox.showerror("Coverage Check Failed", msg)
            self._set_busy(False, status="Vault open and ready....")
            return

        self._set_busy(True, status=f"Preflight scanning: {src_path}")

        def run_backup_worker() -> None:
            try:
                payload = backup(source_dir=src_path)
                backup_path = payload.get("backup_path", "")

                def done() -> None:
                    self._set_status(f"Backup complete: {backup_path}")
                    try:
                        from datetime import datetime, timezone
                        set_last_backup_at_utc(datetime.now(timezone.utc).isoformat())
                    except Exception:
                        pass
                    messagebox.showinfo("Backup Complete", f"Backup created:\n{backup_path}")
                    self._set_busy(False, status="Vault open and ready....")

                self.after(0, done)

            except Exception as e:
                msg = str(e)

                def fail(msg: str = msg) -> None:
                    self._set_status(f"ERROR (backup): {msg}")
                    messagebox.showerror("Backup Failed", msg)
                    self._set_busy(False, status="Vault open and ready....")

                self.after(0, fail)

        def preflight_worker() -> None:
            try:
                rep = preflight_backup(source_dir=src_path)
            except Exception as e:
                msg = str(e)

                def fail(msg: str = msg) -> None:
                    self._set_status(f"ERROR (preflight): {msg}")
                    messagebox.showerror("Preflight Failed", msg)
                    self._set_busy(False, status="Vault open and ready....")

                self.after(0, fail)
                return

            def confirm_and_start() -> None:
                try:
                    unread = rep.get("unreadable", {}) or {}
                    unread_total = (
                        int(unread.get("permission_denied", 0))
                        + int(unread.get("locked_or_in_use", 0))
                        + int(unread.get("not_found", 0))
                        + int(unread.get("other_io", 0))
                    )

                    src_root_s = str(rep.get("source_root", ""))
                    vault_root_s = str(rep.get("backup_root", ""))
                    total_bytes = int(rep.get("total_bytes", 0) or 0)
                    file_count = int(rep.get("file_count", 0) or 0)
                    skipped_symlinks = int(rep.get("skipped_symlinks", 0) or 0)

                    space_line = "WARNING: Destination free space not verified."
                    try:
                        usage = shutil.disk_usage(vault_root_s)
                        free_b = int(usage.free)
                        if free_b >= total_bytes:
                            space_line = f"Destination free space OK: {_human_bytes(free_b)} free."
                        else:
                            space_line = f"WARNING: Low free space: {_human_bytes(free_b)} free (needs ~{_human_bytes(total_bytes)})."
                    except Exception:
                        pass

                    banner_lines: list[str] = [
                        "Verify Backup Plan",
                        f"Source: {src_root_s}",
                        f"Vault:  {vault_root_s}",
                        space_line,
                    ]

                    msg_lines = [
                        "FILES",
                        f"  Count: {file_count}",
                        f"  Size:  {_human_bytes(total_bytes)}",
                        "",
                        "RISK SURFACE",
                        f"  Skipped symlinks: {skipped_symlinks}",
                        f"  Unreadable paths: {unread_total}",
                    ]

                    samples = rep.get("unreadable_samples", []) or []
                    if unread_total > 0 and samples:
                        msg_lines.append("")
                        msg_lines.append("UNREADABLE SAMPLES")
                        for s in samples[:5]:
                            msg_lines.append(f"  - {s}")

                    warnings = rep.get("warnings", []) or []
                    if warnings:
                        msg_lines.append("")
                        msg_lines.append("WARNINGS")
                        for w in warnings[:3]:
                            msg_lines.append(f"  - {w}")

                    # STRICT POSTURE A:
                    # If unreadable paths exist — refuse immediately.
                    if unread_total > 0:
                        banner_lines = [
                            "Backup cannot proceed",
                            "DevVault detected files that cannot be safely read.",
                            f"Unreadable paths: {unread_total}",
                        ]       
                        dlg = PreflightDialog(
                            self,
                            title="Backup Refused",
                            banner_lines=banner_lines,
                            detail_lines=msg_lines,
                            ok_text="Close",
                            ok_enabled=True,
                            show_cancel=False,
                            show_refusal_banner=True,
                        )
                        _ = dlg.show()
                        self._set_status(f"REFUSED (preflight): {unread_total} unreadable paths")
                        self._set_busy(False, status="Vault open and ready....")
                        return

                    dlg = PreflightDialog(
                        self,
                        title="Backup Preflight",
                        banner_lines=banner_lines,
                        detail_lines=msg_lines,
                    )
                    ok = dlg.show()
                    if not ok:
                        self._set_status("Backup cancelled after preflight.")
                        self._set_busy(False, status="Vault open and ready....")
                        return

                    # Reliability posture B: fail closed if ANY unreadable/locked paths exist.
                    if unread_total > 0:
                        banner_lines = [
                            "Backup cannot proceed",
                            "DevVault detected files that cannot be safely read.",
                            f"Unreadable paths: {unread_total}",
                        ]
                        dlg2 = PreflightDialog(
                            self,
                            title="Backup Refused",
                            banner_lines=banner_lines,
                            detail_lines=msg_lines,
                            ok_text="Close",
                            ok_enabled=True,
                            show_cancel=False,
                        )
                        _ = dlg2.show()
                        self._set_status(f"REFUSED (preflight): {unread_total} unreadable paths")
                        self._set_busy(False, status="Vault open and ready....")
                        return

                    self._refresh_vault_ui()
                    self._set_busy(True, status=f"Backup started: {src_path}")
                    threading.Thread(target=run_backup_worker, daemon=True).start()

                except Exception as e:
                    msg = str(e)
                    self._set_status(f"ERROR (preflight-ui): {msg}")
                    messagebox.showerror("Preflight Failed", msg)
                    self._set_busy(False, status="Vault open and ready....")

            self.after(0, confirm_and_start)

        threading.Thread(target=preflight_worker, daemon=True).start()

    def on_restore(self) -> None:
        if not self._require_healthy_vault():
            return

        vault_dir = get_vault_dir()

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

        def restore_worker() -> None:
            try:
                _payload = restore(snapshot_dir=snap_path, destination_dir=dst_path)

                def done() -> None:
                    self._set_status("Restore complete.")
                    messagebox.showinfo("Restore Complete", "Restore completed successfully.")
                    self._set_busy(False, status="Vault open and ready....")

                self.after(0, done)

            except Exception as e:
                msg = str(e)

                def fail(msg: str = msg) -> None:
                    self._set_status(f"ERROR (restore): {msg}")
                    messagebox.showerror("Restore Failed", msg)
                    self._set_busy(False, status="Vault open and ready....")

                self.after(0, fail)

        threading.Thread(target=restore_worker, daemon=True).start()


def main() -> int:
    app = DevVaultApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

