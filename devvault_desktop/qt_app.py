from __future__ import annotations

import os
import sys
from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog

from PySide6.QtCore import Qt
from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtGui import QFont, QPixmap, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QSizePolicy,
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QTextEdit,
    QMessageBox,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect


ASSET_DIR = Path(__file__).resolve().parent / "assets"

ASSET_WATERMARK = ASSET_DIR / "brand" / "trustware-shield-watermark.png"
ASSET_BG_LOCKS = ASSET_DIR / "bg_locks_with_text.png"
ASSET_ICON = ASSET_DIR / "vault.ico"


class _BackupPreflightWorker(QObject):
    log = Signal(str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, source_dir: Path, vault_dir: Path) -> None:
        super().__init__()
        self.source_dir = source_dir
        self.vault_dir = vault_dir

    def run(self) -> None:
        try:
            from scanner.adapters.filesystem import OSFileSystem
            from scanner.backup_engine import BackupEngine
            from scanner.models.backup import BackupRequest

            src = self.source_dir.expanduser().resolve()
            vault = self.vault_dir.expanduser().resolve()

            self.log.emit(f"Vault: {vault}")
            self.log.emit(f"Source: {src}")
            self.log.emit("Preflight...")

            eng = BackupEngine(OSFileSystem())
            pre = eng.preflight(BackupRequest(source_root=src, backup_root=vault))

            payload = {
                "source": str(src),
                "vault": str(vault),
                "file_count": int(pre.file_count),
                "total_bytes": int(pre.total_bytes),
                "skipped_symlinks": int(pre.skipped_symlinks),
                "unreadable_permission_denied": int(pre.unreadable_permission_denied),
                "unreadable_locked_or_in_use": int(pre.unreadable_locked_or_in_use),
                "unreadable_not_found": int(pre.unreadable_not_found),
                "unreadable_other_io": int(pre.unreadable_other_io),
                "unreadable_samples": list(pre.unreadable_samples),
                "warnings": list(pre.warnings),
            }

            self.log.emit(
                f"Preflight: files={payload['file_count']} bytes={payload['total_bytes']} symlinks_skipped={payload['skipped_symlinks']}"
            )
            self.done.emit(payload)

        except Exception as e:
            self.error.emit(str(e))


class _BackupExecuteWorker(QObject):
    log = Signal(str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, source_dir: Path, vault_dir: Path) -> None:
        super().__init__()
        self.source_dir = source_dir
        self.vault_dir = vault_dir

    def run(self) -> None:
        try:
            from scanner.adapters.filesystem import OSFileSystem
            from scanner.backup_engine import BackupEngine
            from scanner.models.backup import BackupRequest

            src = self.source_dir.expanduser().resolve()
            vault = self.vault_dir.expanduser().resolve()

            self.log.emit("Backup executing...")

            eng = BackupEngine(OSFileSystem())
            res = eng.execute(BackupRequest(source_root=src, backup_root=vault))

            payload = {
                "backup_id": res.backup_id,
                "backup_path": str(res.backup_path),
                "started_at": res.started_at.isoformat(),
                "finished_at": res.finished_at.isoformat(),
                "dry_run": res.dry_run,
            }

            self.done.emit(payload)

        except Exception as e:
            self.error.emit(str(e))

class _RestoreWorker(QObject):
    log = Signal(str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, snapshot_dir: Path, destination_dir: Path) -> None:
        super().__init__()
        self.snapshot_dir = snapshot_dir
        self.destination_dir = destination_dir

    def run(self) -> None:
        try:
            from scanner.adapters.filesystem import OSFileSystem
            from scanner.restore_engine import RestoreEngine, RestoreRequest

            snap = self.snapshot_dir.expanduser().resolve()
            dst = self.destination_dir.expanduser().resolve()

            self.log.emit(f"Snapshot: {snap}")
            self.log.emit(f"Destination: {dst}")
            self.log.emit("Restore validating snapshot + destination...")

            eng = RestoreEngine(OSFileSystem())
            eng.restore(RestoreRequest(snapshot_dir=snap, destination_dir=dst))

            self.done.emit({
                "snapshot_dir": str(snap),
                "destination_dir": str(dst),
                "status": "restored",
            })
        except Exception as e:
            self.error.emit(str(e))

class DevVaultQt(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("TSW", "DevVault")
        self.vault_path = self.settings.value("vault_path", "", type=str) or str(Path.home())

        self.setWindowTitle("DevVault")

        # Window icon (top-left)
        try:
            if ASSET_ICON.exists():
                self.setWindowIcon(QIcon(str(ASSET_ICON)))
        except Exception:
            pass

        self.setMinimumSize(900, 600)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        # Sizing constants
        BTN_W = 260
        GLASS_W = int(BTN_W * 1.6)
        WM_SIZE = 520  # watermark max size
        WM_OPACITY = 0.22  # watermark alpha

        # Base styling (black theme)
        # Base styling (black theme + locks background)
        bg = str(ASSET_BG_LOCKS).replace('\\\\','/')
        root.setStyleSheet(
            f"""
            QWidget#root {{
              background-color: #0b0b0b;
            }}
            QLabel {{ color: #e6c200; }}
            QPushButton {{
                color: #e6c200;
                background: #111114;
                border: 1px solid #3a3a3a;
                padding: 10px 16px;
                min-width: 160px;
            }}
            QPushButton:hover {{ border-color: #666; }}
            """
        )


        main = QVBoxLayout(root)
        main.setContentsMargins(40, 30, 40, 30)
        main.setSpacing(16)

        # Watermark (centered, behind content)
        self.watermark = QLabel(root)
        self.watermark.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.watermark.setAlignment(Qt.AlignCenter)
        self._apply_watermark(wm_size=WM_SIZE, opacity=WM_OPACITY)

        # Header
        title = QLabel("🔒  D E V V A U L T  🔒")
        title.setAlignment(Qt.AlignHCenter)
        title.setFont(QFont("Segoe UI", 26, QFont.Bold))

        slogan = QLabel(
            "DevVault is a safety system for people whose work cannot be replaced."
        )
        slogan.setAlignment(Qt.AlignHCenter)
        slogan.setFont(QFont("Segoe UI", 11))

        main.addWidget(title)
        main.addWidget(slogan)

        # --- Change Vault button (ABOVE the location box) ---
        change_container = QVBoxLayout()
        change_container.setSpacing(4)
        change_container.setAlignment(Qt.AlignHCenter)

        self.btn_change = QPushButton("Change Vault")
        self.btn_change.setFixedWidth(BTN_W)
        subtitle = QLabel("Vault = where your backups are saved.")
        subtitle.setAlignment(Qt.AlignHCenter)
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet("color: rgba(230,200,0,160);")

        change_container.addWidget(self.btn_change)
        change_container.addWidget(subtitle)

        main.addLayout(change_container)
        self.btn_change.setFixedWidth(BTN_W)
        self.btn_change.setStyleSheet(
            """
            QPushButton {
                color: #e6c200;
                background: #111114;
                border: 1px solid #3a3a3a;
                padding: 10px;
                text-align: center;
            }
            QPushButton:hover { border-color: #666; }
        """
        )
        change_row = QHBoxLayout()
        change_row.setAlignment(Qt.AlignHCenter)
        change_row.addWidget(self.btn_change)
        self.btn_change.clicked.connect(self.change_vault)

        main.addLayout(change_row)

        # --- Smoked glass box (match width of two buttons) ---
        glass = QFrame()
        glass.setFixedWidth(GLASS_W)
        glass.setStyleSheet(
            """
            QFrame {
                background: rgba(15,15,15,160);
                border: 1px solid rgba(120,120,120,120);
                border-radius: 8px;
            }
        """
        )
        glass_layout = QVBoxLayout(glass)
        glass_layout.setContentsMargins(18, 12, 18, 12)
        glass_layout.setSpacing(6)

        self.vault_line_1 = QLabel(r"Current backup location: E:\ ")
        self.vault_line_1.setAlignment(Qt.AlignHCenter)
        self.vault_line_1.setFont(QFont("Segoe UI", 11, QFont.Bold))

        # No inner bubble — just text
        self.vault_line_2 = QLabel(r"System default: D:\DevVault")
        self.vault_line_2.setAlignment(Qt.AlignHCenter)

        self.vault_line_2.setStyleSheet("background: transparent; border: none;")
        glass_layout.addWidget(self.vault_line_1)
        glass_layout.addWidget(self.vault_line_2)
        self.update_vault_display()

        main.addWidget(glass, 0, Qt.AlignHCenter)
        # Buttons row (where Change Vault used to be)
        row = QHBoxLayout()
        row.setSpacing(24)
        row.setAlignment(Qt.AlignHCenter)

        self.btn_backup = QPushButton("Make Backup")
        self.btn_backup.setFixedWidth(BTN_W)

        self.btn_restore = QPushButton("Restore Backup")
        self.btn_restore.setFixedWidth(BTN_W)

        row.addWidget(self.btn_backup)
        self.btn_backup.clicked.connect(self.make_backup)

        row.addWidget(self.btn_restore)
        self.btn_restore.clicked.connect(self.restore_backup)

        main.addLayout(row)


        self.btn_backup.setFocus()
        # Log box (green terminal style)
        self.log = QTextEdit()
        self.log.setMinimumHeight(140)
        self.log.setMaximumHeight(260)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log.setStyleSheet(
            """
            QTextEdit {
                background: rgba(0,0,0,200);
                border: 1px solid rgba(120,120,120,120);
                color: #1FEB1C;
                padding: 12px;
            }
        """
        )
        self.log.setFont(QFont("Consolas", 11))
        self.log.setText(
            "Welcome to DevVault.\n"
            "Trustware: if anything looks unsafe, DevVault refuses.\n"
            "Choose an action: Make Backup or Restore Backup.\n"
            "Vault open and ready....\n"
        )
        self.setFocus()
        self.setFocus()
        main.addWidget(self.log, stretch=1)
        # Footer
        footer_row = QHBoxLayout()
        footer_left = QLabel("DevVault — Built by Trustware Technologies")
        footer_right = QLabel("© 2026 TSW Technologies LLC")
        footer_left.setStyleSheet("color: rgba(220,220,220,160);")
        footer_right.setStyleSheet("color: rgba(220,220,220,160);")
        footer_row.addWidget(footer_left)
        footer_row.addStretch(1)
        footer_row.addWidget(footer_right)
        main.addLayout(footer_row)

        # Ensure watermark is behind everything
        self.watermark.lower()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_watermark()

    def _apply_watermark(self, wm_size: int, opacity: float) -> None:
        if ASSET_WATERMARK.exists():
            pm = QPixmap(str(ASSET_WATERMARK))
            pm = pm.scaled(
                wm_size, wm_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.watermark.setPixmap(pm)

            eff = QGraphicsOpacityEffect(self.watermark)
            eff.setOpacity(opacity)
            self.watermark.setGraphicsEffect(eff)

        self._position_watermark()

    def _position_watermark(self) -> None:
        w = self.centralWidget().width()
        h = self.centralWidget().height()
        pm = self.watermark.pixmap()
        if pm is None:
            return
        x = (w - pm.width()) // 2
        y = (h - pm.height()) // 2 + 10
        self.watermark.setGeometry(x, y, pm.width(), pm.height())
    def append_log(self, message: str) -> None:
        # Terminal is a QTextEdit in this UI
        self.log.append(message)

    def update_vault_display(self) -> None:
        self.vault_line_1.setText(f"Current backup location: {self.vault_path}")

    def change_vault(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Vault Directory",
            self.vault_path,
        )
        if folder:
            self.vault_path = folder
            self.settings.setValue("vault_path", folder)
            self.update_vault_display()
            self.append_log(f"Vault updated: {folder}")

    def _set_busy(self, busy: bool) -> None:
        self.btn_change.setEnabled(not busy)
        self.btn_backup.setEnabled(not busy)
        self.btn_restore.setEnabled(not busy)

    def make_backup(self) -> None:
        # Choose SOURCE folder to back up (behavior only; no UI layout changes)
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Back Up",
            str(Path.home()),
        )
        if not folder:
            self.append_log("Backup canceled.")
            return

        source_dir = Path(folder)
        vault_dir = Path(self.vault_path)

        # Store pending inputs for UI-thread handlers
        self._pending_backup_source = source_dir
        self._pending_backup_vault = vault_dir

        self.append_log(f"Backup starting: {source_dir}")
        self._set_busy(True)

        self._backup_thread = QThread()
        self._backup_pre = _BackupPreflightWorker(source_dir, vault_dir)
        self._backup_pre.moveToThread(self._backup_thread)

        self._backup_thread.started.connect(self._backup_pre.run)
        self._backup_pre.log.connect(self.append_log)

        # IMPORTANT: connect to real QObject methods (UI thread)
        self._backup_pre.done.connect(self._on_backup_pre_done)
        self._backup_pre.error.connect(self._on_backup_pre_err)

        self._backup_thread.finished.connect(self._backup_pre.deleteLater)
        self._backup_thread.finished.connect(self._backup_thread.deleteLater)

        self._backup_thread.start()

    def _on_backup_pre_done(self, pre: dict) -> None:
        # Build operator confirmation text (UI thread)
        def fmt_bytes(n: int) -> str:
            try:
                n = int(n)
            except Exception:
                return str(n)
            units = ["B", "KB", "MB", "GB", "TB"]
            f = float(n)
            i = 0
            while f >= 1024.0 and i < len(units) - 1:
                f /= 1024.0
                i += 1
            return f"{f:.2f} {units[i]}"

        unread = (
            int(pre.get("unreadable_permission_denied", 0))
            + int(pre.get("unreadable_locked_or_in_use", 0))
            + int(pre.get("unreadable_not_found", 0))
            + int(pre.get("unreadable_other_io", 0))
        )

        sample_lines = ""
        samples = pre.get("unreadable_samples") or []
        if samples:
            sample_lines = "\n".join([f"  - {s}" for s in samples[:10]])
            if len(samples) > 10:
                sample_lines += f"\n  ... (+{len(samples)-10} more)"

        warn_lines = ""
        warns = pre.get("warnings") or []
        if warns:
            warn_lines = "\n".join([f"  - {w}" for w in warns])

        msg = (
            "Pre-backup validation complete.\n\n"
            f"Source:\n  {pre.get('source')}\n\n"
            f"Vault:\n  {pre.get('vault')}\n\n"
            f"Files: {pre.get('file_count')}  Size: {fmt_bytes(pre.get('total_bytes', 0))}\n"
            f"Symlinks skipped: {pre.get('skipped_symlinks')}\n"
            f"Unreadable paths: {unread}\n\n"
        )

        if warn_lines:
            msg += "Warnings:\n" + warn_lines + "\n\n"
        if sample_lines:
            msg += "Unreadable samples:\n" + sample_lines + "\n\n"

        msg += "Proceed with backup?"

        # Stop preflight thread (now that it has delivered results)
        try:
            self._backup_thread.quit()
        except Exception:
            pass

        # Bring window forward (helps on multi-monitor / focus weirdness)
        try:
            self.raise_()
            self.activateWindow()
            self.setFocus()
        except Exception:
            pass

        self.append_log("Confirming backup (operator approval required)...")

        if QMessageBox.warning(self, "Confirm Backup", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            self.append_log("Backup canceled (operator declined preflight confirmation).")
            self._set_busy(False)
            return

        # ---------- Phase 2: Execute ----------
        source_dir = getattr(self, "_pending_backup_source", None)
        vault_dir = getattr(self, "_pending_backup_vault", None)
        if source_dir is None or vault_dir is None:
            self.append_log("Backup refused: internal error (missing pending paths).")
            self._set_busy(False)
            return

        self._backup_exec_thread = QThread()
        self._backup_exec = _BackupExecuteWorker(source_dir, vault_dir)
        self._backup_exec.moveToThread(self._backup_exec_thread)

        self._backup_exec_thread.started.connect(self._backup_exec.run)
        self._backup_exec.log.connect(self.append_log)

        def _done(payload: dict) -> None:
            self.append_log("Backup complete.")
            self.append_log(f"Result: {payload}")
            self._set_busy(False)
            self._backup_exec_thread.quit()

        def _err(msg2: str) -> None:
            self.append_log(f"Backup refused: {msg2}")
            self._set_busy(False)
            self._backup_exec_thread.quit()

        self._backup_exec.done.connect(_done)
        self._backup_exec.error.connect(_err)

        self._backup_exec_thread.finished.connect(self._backup_exec.deleteLater)
        self._backup_exec_thread.finished.connect(self._backup_exec_thread.deleteLater)

        self._backup_exec_thread.start()

    def _on_backup_pre_err(self, msg: str) -> None:
        self.append_log(f"Backup refused: {msg}")
        self._set_busy(False)
        try:
            self._backup_thread.quit()
        except Exception:
            pass

    def restore_backup(self) -> None:
        # 1) Select snapshot (must be inside vault)
        vault_dir = Path(self.vault_path).expanduser().resolve()

        snap_folder = QFileDialog.getExistingDirectory(
            self,
            "Select Snapshot Folder (inside vault)",
            str(vault_dir),
        )
        if not snap_folder:
            self.append_log("Restore canceled (no snapshot selected).")
            return

        snapshot_dir = Path(snap_folder).expanduser().resolve()

        # Guard: snapshot must be inside vault_dir
        try:
            snapshot_dir.relative_to(vault_dir)
        except ValueError:
            QMessageBox.critical(
                self,
                "Restore Refused",
                "Snapshot must be inside the current vault directory.",
            )
            self.append_log("Restore refused: snapshot not inside vault.")
            return

        # 2) Select destination (must be empty directory)
        dest_folder = QFileDialog.getExistingDirectory(
            self,
            "Select EMPTY Destination Folder",
            str(Path.home()),
        )
        if not dest_folder:
            self.append_log("Restore canceled (no destination selected).")
            return

        destination_dir = Path(dest_folder).expanduser().resolve()

        # Guard: destination must exist and be empty (engine enforces too; we pre-check for operator clarity)
        try:
            if destination_dir.exists():
                if not destination_dir.is_dir():
                    QMessageBox.critical(self, "Restore Refused", "Destination exists but is not a directory.")
                    self.append_log("Restore refused: destination not a directory.")
                    return
                if any(destination_dir.iterdir()):
                    QMessageBox.critical(self, "Restore Refused", "Destination directory must be empty.")
                    self.append_log("Restore refused: destination not empty.")
                    return
        except Exception as e:
            QMessageBox.critical(self, "Restore Refused", f"Destination check failed: {e}")
            self.append_log(f"Restore refused: destination check failed: {e}")
            return

        # 3) OneDrive warning + second confirmation (sync can lock files mid-restore)
        dest_s = str(destination_dir)
        onedrive_roots = []
        try:
            for k in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
                v = os.environ.get(k)
                if v:
                    onedrive_roots.append(v)
        except Exception:
            pass

        is_onedrive = ("\\OneDrive\\" in dest_s) or any(dest_s.startswith(r) for r in onedrive_roots)

        if is_onedrive:
            warn = (
                "Warning: Destination appears to be inside a OneDrive-synced folder.\n\n"
                "Cloud sync can lock files or modify timestamps during restore.\n"
                "For maximum reliability, restore to a local non-synced folder.\n\n"
                f"Destination:\n  {destination_dir}\n\n"
                "Continue anyway?"
            )
            if QMessageBox.warning(self, "OneDrive Destination Warning", warn, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                self.append_log("Restore canceled (OneDrive warning declined).")
                return

        # 4) Confirm restore (explicit, irreversible warning)
        msg = (
            "Restore will COPY snapshot contents into the destination folder.\n\n"
            f"Snapshot:\n  {snapshot_dir}\n\n"
            f"Destination (must be empty):\n  {destination_dir}\n\n"
            "Continue?"
        )
        if QMessageBox.warning(self, "Confirm Restore", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            self.append_log("Restore canceled (operator declined confirmation).")
            return

        self.append_log(f"Restore starting: {snapshot_dir} -> {destination_dir}")
        self._set_busy(True)

        self._restore_thread = QThread()
        self._restore_worker = _RestoreWorker(snapshot_dir, destination_dir)
        self._restore_worker.moveToThread(self._restore_thread)

        self._restore_thread.started.connect(self._restore_worker.run)
        self._restore_worker.log.connect(self.append_log)

        def _done(payload: dict) -> None:
            self.append_log("Restore complete.")
            self.append_log(f"Result: {payload}")
            self._set_busy(False)
            self._restore_thread.quit()

        def _err(msg: str) -> None:
            self.append_log(f"Restore refused: {msg}")
            self._set_busy(False)
            self._restore_thread.quit()

        self._restore_worker.done.connect(_done)
        self._restore_worker.error.connect(_err)

        self._restore_thread.finished.connect(self._restore_worker.deleteLater)
        self._restore_thread.finished.connect(self._restore_thread.deleteLater)

        self._restore_thread.start()

def main() -> int:
    app = QApplication(sys.argv)
    win = DevVaultQt()

    # Always open on PRIMARY display (customer-safe default)
    screen = QGuiApplication.primaryScreen()
    geo = screen.availableGeometry()

    w = min(1200, int(geo.width() * 0.92))
    h = min(780, int(geo.height() * 0.88))
    win.resize(w, h)

    x = geo.x() + (geo.width() - w) // 2
    y = geo.y() + (geo.height() - h) // 2
    win.move(x, y)

    win.show()
    win.raise_()
    win.activateWindow()
    win.setFocus()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())






















