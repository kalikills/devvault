from __future__ import annotations

import os
import sys
import subprocess
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
    QDialog,
    QScrollArea,
    QInputDialog,
    QComboBox,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect
from devvault_desktop.coverage_assurance import compute_uncovered_candidates
from devvault_desktop.config import add_protected_root
from devvault_desktop.license_gate import check_license
from devvault.licensing import LicenseError, install_license_text, verify_license_string


ASSET_DIR = Path(__file__).resolve().parent / "assets"

ASSET_WATERMARK = ASSET_DIR / "brand" / "trustware-shield-watermark.png"
ASSET_BG_LOCKS = ASSET_DIR / "bg_locks_with_text.png"
ASSET_ICON = ASSET_DIR / "vault.ico"

def _ensure_devvault_restores_shortcut(target_dir: Path) -> None:
    desktop_dir = None

    one_drive = os.environ.get("OneDrive")
    if one_drive:
        candidate = Path(one_drive) / "Desktop"
        if candidate.exists():
            desktop_dir = candidate

    if desktop_dir is None:
        candidate = Path.home() / "Desktop"
        if candidate.exists():
            desktop_dir = candidate

    if desktop_dir is None:
        desktop_dir = Path.home()

    shortcut_path = desktop_dir / "DevVault Restores.lnk"

    ps = (
        "$WshShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{str(shortcut_path).replace("'", "''")}'); "
        f"$Shortcut.TargetPath = '{str(target_dir).replace("'", "''")}'; "
        f"$Shortcut.WorkingDirectory = '{str(target_dir).replace("'", "''")}'; "
        "$Shortcut.Description = 'Open DevVault Restores'; "
        "$Shortcut.Save()"
    )

    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
        check=True,
        capture_output=True,
        text=True,
    )


class BackupConfirmDialog(QDialog):
    """
    Wide, scrollable confirmation dialog for backup execution.
    Wiring-only: does not modify global styling or brand assets.
    """

    def __init__(
        self,
        parent: QWidget,
        *,
        title: str,
        summary_lines: list[str],
        details_text: str,
        approve_text: str = "Run Backup",
        cancel_text: str = "Cancel",
        min_width: int = 860,
        min_height: int = 520,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(min_width)
        self.setMinimumHeight(min_height)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QWidget(self)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        for line in summary_lines:
            lbl = QLabel(line, header)
            lbl.setWordWrap(True)
            header_layout.addWidget(lbl)

        root.addWidget(header)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)

        details_host = QWidget(scroll)
        details_layout = QVBoxLayout(details_host)
        details_layout.setContentsMargins(0, 0, 0, 0)

        details = QTextEdit(details_host)
        details.setReadOnly(True)
        details.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        details.setAcceptRichText(True)
        if "<" in details_text and ">" in details_text:
            details.setHtml(details_text)
        else:
            details.setPlainText(details_text)

        details_layout.addWidget(details)
        scroll.setWidget(details_host)

        root.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(10)

        btn_copy = QPushButton("Copy Details", self)
        btn_copy.clicked.connect(lambda: self._copy(details_text))
        btn_row.addWidget(btn_copy)

        btn_row.addStretch(1)

        btn_cancel = QPushButton(cancel_text, self)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_ok = QPushButton(approve_text, self)
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        root.addLayout(btn_row)

    def _copy(self, text: str) -> None:
        try:
            cb = QApplication.clipboard()
            cb.setText(text)
        except Exception:
            pass

    @staticmethod
    def ask(
        parent: QWidget,
        *,
        title: str,
        summary_lines: list[str],
        details_text: str,
        approve_text: str = "Run Backup",
        cancel_text: str = "Cancel",
    ) -> bool:
        dlg = BackupConfirmDialog(
            parent,
            title=title,
            summary_lines=summary_lines,
            details_text=details_text,
            approve_text=approve_text,
            cancel_text=cancel_text,
        )
        return dlg.exec() == QDialog.DialogCode.Accepted



class ScanSelectionDialog(QDialog):
    """
    Popup checklist dialog for uncovered projects found during scan.
    Operator selects which projects should enter the backup queue.
    """

    def __init__(self, parent: QWidget, paths: list[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Select Projects to Back Up")
        self.setModal(True)
        self.setMinimumWidth(860)
        self.setMinimumHeight(520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("DevVault found items that are not currently protected.", self)
        title.setWordWrap(True)
        root.addWidget(title)

        subtitle = QLabel(
            """These may include:
• Projects
• Large data folders (photos, videos, downloads)
• Archive files (.zip, .7z, .rar, etc)

Tip: Large collections can be zipped first to speed up backups.

Uncheck anything you do not want included, then choose Back Up Selected.""",
            self,
        )
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)

        from pathlib import Path

        projects = []
        data = []
        archives = []

        def fmt_bytes(n: int) -> str:
            units = ["B", "KB", "MB", "GB", "TB"]
            f = float(max(0, int(n)))
            i = 0
            while f >= 1024.0 and i < len(units) - 1:
                f /= 1024.0
                i += 1
            if i == 0:
                return f"{int(f)} {units[i]}"
            return f"{f:.1f} {units[i]}"

        def count_files(root: Path, limit: int = 5000) -> int:
            count = 0
            try:
                for child in root.rglob("*"):
                    try:
                        if child.is_file():
                            count += 1
                            if count >= limit:
                                return count
                    except Exception:
                        continue
            except Exception:
                return count
            return count

        def decorate_path(p: str, group: str) -> str:
            try:
                pp = Path(p)
                if group == "DATA FOLDERS" and pp.is_dir():
                    count = count_files(pp)
                    suffix = f" ({count}+ files)" if count >= 5000 else f" ({count} files)"
                    return str(pp) + suffix
                if group == "ARCHIVES" and pp.is_file():
                    try:
                        size = pp.stat().st_size
                    except Exception:
                        size = 0
                    return str(pp) + f" ({fmt_bytes(size)})"
            except Exception:
                pass
            return str(p)

        for p in paths:
            s = str(p).lower()
            if s.endswith((".zip",".7z",".rar",".tar",".gz",".bz2",".xz")):
                archives.append(p)
            else:
                try:
                    pp = Path(p)
                    if pp.is_dir() and pp.parent.name.lower() in ("pictures","videos","downloads"):
                        data.append(p)
                    else:
                        projects.append(p)
                except Exception:
                    projects.append(p)

        def add_group(title, items):
            if not items:
                return
            header = QListWidgetItem(title)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(header)

            for p in items:
                item = QListWidgetItem("   " + decorate_path(str(p), title))
                item.setData(Qt.ItemDataRole.UserRole, str(p))
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(Qt.CheckState.Checked)
                self.list_widget.addItem(item)

        add_group("PROJECTS", projects)
        add_group("DATA FOLDERS", data)
        add_group("ARCHIVES", archives)


        root.addWidget(self.list_widget, 1)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(10)

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_row.addStretch(1)

        btn_ok = QPushButton("Back Up Selected", self)
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        root.addLayout(btn_row)

    def selected_paths(self) -> list[str]:
        chosen: list[str] = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item is None:
                continue
            if not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                continue
            if item.checkState() == Qt.CheckState.Checked:
                raw = item.data(Qt.ItemDataRole.UserRole)
                chosen.append(str(raw or item.text().strip()))
        return chosen

    @staticmethod
    def ask(parent: QWidget, paths: list[str]) -> tuple[bool, list[str]]:
        dlg = ScanSelectionDialog(parent, paths)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return ok, dlg.selected_paths()


def _drive_alive(root: "Path") -> bool:
    """
    Best-effort drive health check for removable media.
    If listing the root fails, treat it as disconnected.
    """
    try:
        _ = list(root.iterdir())
        return True
    except Exception:
        return False



def _kill_proc_tree(proc) -> None:
    """
    Best-effort hard stop of a subprocess tree on Windows.
    Uses taskkill /T /F to ensure children stop too.
    """
    try:
        import os
        import subprocess
        p = proc
        pid = getattr(p, "pid", None)
        if pid is None:
            return
        # Windows only; harmless no-op elsewhere
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass
        else:
            try:
                p.terminate()
            except Exception:
                pass
            try:
                p.kill()
            except Exception:
                pass
    except Exception:
        pass


def _run_engine_process(
    cmd: list[str],
    watch: list[tuple["Path", str]],
    poll_s: float = 0.15,
    cancel_check=None,
    proc_setter=None,
) -> tuple[int, str, str, str | None]:
    """
    Run engine_subprocess in a separate process and poll for watched drive disappearance.
    Returns: (rc, stdout, stderr, disconnect_message_or_none)
    cancel_check: optional callable returning True if operator requested cancel.
    """
    import subprocess
    import time

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        if proc_setter is not None:
            proc_setter(proc)
    except Exception:
        pass

    while True:
        # Operator cancel
        try:
            if cancel_check is not None and cancel_check():
                try:
                    _kill_proc_tree(proc)
                except Exception:
                    pass
                return -1, "", "", "Cancelled by operator."
        except Exception:
            pass

        rc = proc.poll()
        if rc is not None:
            break

        # Drive disappearance watch
        for root, msg in watch:
            try:
                if not _drive_alive(root):
                    try:
                        _kill_proc_tree(proc)
                    except Exception:
                        pass
                    return -1, "", "", msg
            except Exception:
                pass

        time.sleep(poll_s)

    out = (proc.stdout.read() if proc.stdout else "") or ""
    err = (proc.stderr.read() if proc.stderr else "") or ""
    return rc, out, err, None



class OperationOverlay(QWidget):
    """
    Transparent full-window overlay used as the "Loading / Operation" page.
    (Skeleton only; wiring happens later.)
    """
    cancel_clicked = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("operation_overlay")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Fill parent
        self.setGeometry(parent.rect())
        self.hide()

        # Center card
        self._card = QWidget(self)
        self._card.setObjectName("operation_card")
        self._card.setFixedWidth(520)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(24, 24, 24, 18)
        card_layout.setSpacing(10)

        # Lock icon (painted label; toggles open/closed)
        self._lock = QLabel()
        self._lock.setFixedSize(220, 220)
        self._lock.setAlignment(Qt.AlignCenter)
        self._lock.setObjectName("operation_lock")

        # Title + phase
        self._title = QLabel("Securing changes")
        self._title.setObjectName("operation_title")
        self._title.setAlignment(Qt.AlignCenter)

        self._phase = QLabel("Preflight → Confirm → Execute")
        self._phase.setAlignment(Qt.AlignCenter)

        # Context lines (source/vault/snapshot/destination)
        self._ctx = QLabel("")
        self._ctx.setAlignment(Qt.AlignCenter)
        self._ctx.setWordWrap(True)

        # Dot wave
        self._dots = QLabel(".")
        self._dots.setObjectName("operation_dots")
        self._dots.setAlignment(Qt.AlignCenter)

        # Buttons row (Cancel + Close)
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 12, 0, 0)
        btn_row.setSpacing(12)

        self.btn_cancel = QPushButton("Cancel")

        self.btn_cancel.clicked.connect(self.cancel_clicked.emit)

        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addStretch(1)

        card_layout.addWidget(self._lock, alignment=Qt.AlignCenter)
        card_layout.addWidget(self._title)
        card_layout.addWidget(self._phase)
        card_layout.addWidget(self._ctx)
        card_layout.addWidget(self._dots)
        card_layout.addLayout(btn_row)

        # Outer layout to center the card
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)
        outer.addWidget(self._card, alignment=Qt.AlignCenter)
        outer.addStretch(1)

        # Timers
        self._lock_state = False
        self._dot_i = 0
        self._dot_seq = [".", "..", "...", "....", ".....", ".", "..", "...", "....", "....."]

        self._t_lock = QTimer(self)
        self._t_lock.setInterval(500)
        self._t_lock.timeout.connect(self._tick_lock)

        self._t_dots = QTimer(self)
        self._t_dots.setInterval(150)
        self._t_dots.timeout.connect(self._tick_dots)

        self._apply_styles()
        self._render_lock()

    def _apply_styles(self) -> None:
        # Self-contained overlay styling; does NOT touch root stylesheet.
        self.setStyleSheet("""
        QWidget#operation_overlay {
            background: rgba(0, 0, 0, 140);
        }
        QWidget#operation_card {
            background: rgba(10, 10, 10, 210);
            border: 1px solid rgba(255, 255, 255, 40);
            border-radius: 18px;
        }
        QLabel {
            color: #f2f2f2;
            font-size: 18px;
        }
        QLabel#operation_title {
            font-size: 26px;
            font-weight: 600;
        }
        QLabel#operation_lock {
            font-size: 140px;
            font-weight: 700;
        }
        QLabel#operation_dots {
            font-size: 28px;
            font-weight: 600;
            letter-spacing: 2px;
        }
        QPushButton {
            min-width: 120px;
            padding: 10px 14px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 18);
        }
        QPushButton:disabled {
            background: rgba(255, 255, 255, 8);
            color: rgba(255, 255, 255, 120);
        }
        """)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        p = self.parentWidget()
        if p is not None:
            self.setGeometry(p.rect())

    def start(self) -> None:
        self.show()
        self.raise_()
        self._t_lock.start()
        self._t_dots.start()

    def stop(self, allow_close: bool = True) -> None:
        self._t_lock.stop()
        self._t_dots.stop()
        self.btn_cancel.setEnabled(False)

    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def set_phase(self, text: str) -> None:
        self._phase.setText(text)

    def set_context_lines(self, lines: list[str]) -> None:
        clean = [ln.strip() for ln in lines if (ln or "").strip()]
        self._ctx.setText("\n".join(clean))

    def _tick_dots(self) -> None:
        self._dots.setText(self._dot_seq[self._dot_i % len(self._dot_seq)])
        self._dot_i += 1

    def _tick_lock(self) -> None:
        self._lock_state = not self._lock_state
        self._render_lock()

    def _render_lock(self) -> None:
        # Simple drawn lock using unicode + font; no assets required.
        self._lock.setText("🔓" if self._lock_state else "🔒")
        f = self._lock.font()
        f.setPointSize(64)
        self._lock.setFont(f)


class _BackupPreflightWorker(QObject):
    log = Signal(str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, source_dir: Path, vault_dir: Path) -> None:
        super().__init__()
        import tempfile
        import uuid

        self.source_dir = source_dir
        self.vault_dir = vault_dir
        self._cancel_requested = False
        self._proc = None
        self._cancel_token = Path(tempfile.gettempdir()) / f"devvault-cancel-{uuid.uuid4().hex}.token"

    def cancel(self) -> None:
        # Called from UI thread; request cancel, signal the engine, then hard-stop as fallback.
        self._cancel_requested = True
        try:
            token = getattr(self, "_cancel_token", None)
            if token is not None:
                Path(token).write_text("cancelled", encoding="utf-8")
        except Exception:
            pass
        try:
            p = getattr(self, "_proc", None)
            if p is not None and getattr(p, "poll", lambda: None)() is None:
                _kill_proc_tree(p)
        except Exception:
            pass

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
        import tempfile, uuid
        from pathlib import Path

        self.source_dir = source_dir
        self.vault_dir = vault_dir

        # Cancellation state
        self._cancel_requested = False
        self._proc = None

        # Cancel token file watched by engine
        self._cancel_token = Path(tempfile.gettempdir()) / f"devvault-cancel-{uuid.uuid4().hex}.token"


    def cancel(self) -> None:
        # Trustware: operator cancel is authoritative.
        self._cancel_requested = True
        try:
            self.log.emit("Cancellation requested by operator.")
        except Exception:
            pass

        # Signal engine loop to stop at the next cancel_check.
        try:
            self._cancel_token.write_text("cancelled", encoding="utf-8")
        except Exception:
            pass

        # Fallback: hard-stop subprocess tree if still running.
        try:
            p = getattr(self, "_proc", None)
            if p is not None and getattr(p, "poll", lambda: None)() is None:
                _kill_proc_tree(p)
        except Exception:
            pass

    def _cleanup_incomplete_staging(self, vault: Path) -> None:
        # Best-effort cleanup of staging folders produced by the backup engine.
        # This is intentionally scoped to the selected vault root only.
        try:
            import shutil
            for p in vault.iterdir():
                # Engine uses .incomplete-* staging folders; never touch anything else.
                if p.is_dir() and p.name.startswith(".incomplete-"):
                    try:
                        shutil.rmtree(p, ignore_errors=True)
                    except Exception:
                        pass
        except Exception:
            pass

    def run(self) -> None:
        try:
            import json
            import subprocess
            import time
            import sys
            from pathlib import Path

            src = self.source_dir.expanduser().resolve()
            vault = self.vault_dir.expanduser().resolve()

            vault_drive = Path(str(vault)[:3])   # e.g. E:\
            src_drive = Path(str(src)[:3])       # e.g. C:\

            self.log.emit("Backup executing...")

            try:
                if self._cancel_token.exists():
                    self._cancel_token.unlink()
            except Exception:
                pass

            cmd = [
                sys.executable,
                "-m",
                "devvault_desktop.engine_subprocess",
                "backup-execute",
                "--source",
                str(src),
                "--vault",
                str(vault),
                "--cancel-token",
                str(self._cancel_token),
            ]
            rc, out, err, disconnect_msg = _run_engine_process(
                cmd,
                watch=[
                    (vault_drive, "Vault drive disconnected during backup."),
                    (src_drive, "Source drive disconnected during backup."),
                ],
                poll_s=0.15,
                cancel_check=lambda: getattr(self, "_cancel_requested", False),
                proc_setter=lambda p: setattr(self, "_proc", p),
            )

            # Cancel is authoritative: if operator requested cancel at any point, do not proceed to success.
            if bool(getattr(self, "_cancel_requested", False)):
                # Restore worker has no staging cleanup path here.
                self.error.emit("Cancelled by operator.")
                return

            if disconnect_msg:
                self.error.emit(disconnect_msg)
                return


            if not out.strip():
                # Restore worker has no staging cleanup path here.
                self.error.emit(err.strip() or f"Backup failed (no output). Exit={rc}")
                return

            data = json.loads(out)

            if not data.get("ok"):
                op = str(data.get("operator_message") or "").strip()
                msg = str(data.get("error") or "Backup failed.")


                # Restore worker has no staging cleanup path here.
                self.error.emit(op or msg)
                return

            payload = data["payload"]
            try:
                if self._cancel_token.exists():
                    self._cancel_token.unlink()
            except Exception:
                pass
            self.done.emit(payload)

            self._cleanup_incomplete_staging(self.vault_dir.expanduser().resolve())

        except Exception as e:
            try:
                if self._cancel_token.exists():
                    self._cancel_token.unlink()
            except Exception:
                pass
            self._cleanup_incomplete_staging(self.vault_dir.expanduser().resolve())
            self.error.emit(str(e))

class _RestoreWorker(QObject):
    log = Signal(str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, snapshot_dir: Path, destination_dir: Path) -> None:
        super().__init__()
        self.snapshot_dir = snapshot_dir
        self.destination_dir = destination_dir
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            import json
            import subprocess
            import time
            import sys
            from pathlib import Path

            snap = self.snapshot_dir.expanduser().resolve()
            dst = self.destination_dir.expanduser().resolve()

            snap_drive = Path(str(snap)[:3])   # e.g. D:\
            dst_drive = Path(str(dst)[:3])     # e.g. E:\

            self.log.emit(f"Snapshot: {snap}")
            self.log.emit(f"Destination: {dst}")
            self.log.emit("Restore validating snapshot + destination...")

            cmd = [
                sys.executable,
                "-m",
                "devvault_desktop.engine_subprocess",
                "restore",
                "--snapshot",
                str(snap),
                "--destination",
                str(dst),
            ]
            rc, out, err, disconnect_msg = _run_engine_process(
                cmd,
                watch=[
                    (snap_drive, "Vault drive disconnected during restore."),
                    (dst_drive, "Destination drive disconnected during restore."),
                ],
                poll_s=0.15,
                cancel_check=lambda: getattr(self, "_cancel_requested", False),
            )

            if disconnect_msg:
                # Restore worker has no staging cleanup path here.
                self.error.emit(disconnect_msg)
                return


            if not out.strip():
                self.error.emit(err.strip() or f"Restore failed (no output). Exit={rc}")
                return

            data = json.loads(out)

            if not data.get("ok"):
                op = str(data.get("operator_message") or "").strip()
                msg = str(data.get("error") or "Restore failed.")


                self.error.emit(op or msg)
                return

            self.done.emit(data["payload"])

        except Exception as e:
            self.error.emit(str(e))

class DevVaultQt(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("TSW", "DevVault")
        raw_vault = self.settings.value("vault_path", "", type=str) or ""
        self.vault_path = self._normalize_vault_root(raw_vault)
        if not self.vault_path:
            drives = self._available_drive_roots()
            self.vault_path = drives[0] if drives else "C:\\"
        self.settings.setValue("vault_path", self.vault_path)

        # Recover from prior crash/kill: remove any leftover .incomplete-* staging dirs in the vault root.
        try:
            import shutil
            _v = Path(self.vault_path).expanduser().resolve()
            for p in _v.iterdir():
                if p.is_dir() and p.name.startswith(".incomplete-"):
                    shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass

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

        # Operation overlay (Loading / Operation page). Wiring happens later.
        try:
            self.op_overlay = OperationOverlay(root)
            self._op_cancel_handler = None
            self.op_overlay.cancel_clicked.connect(self._on_op_cancel)
        except Exception:
            self.op_overlay = None

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

        # --- Backup Drive selector (ABOVE the location box) ---
        change_container = QVBoxLayout()
        change_container.setSpacing(4)
        change_container.setAlignment(Qt.AlignHCenter)

        self.vault_combo = QComboBox()
        self.vault_combo.setFixedWidth(BTN_W)
        self.vault_combo.setEditable(True)
        self.vault_combo.lineEdit().setReadOnly(True)
        self.vault_combo.lineEdit().setAlignment(Qt.AlignCenter)
        subtitle = QLabel("Backup Drive = where your backups are saved.")
        subtitle.setAlignment(Qt.AlignHCenter)
        subtitle.setFont(QFont("Segoe UI", 9))
        subtitle.setStyleSheet("color: rgba(230,200,0,160);")

        change_container.addWidget(self.vault_combo)
        change_container.addWidget(subtitle)

        main.addLayout(change_container)
        self.vault_combo.setStyleSheet(
            """
            QComboBox {
                color: #e6c200;
                background: #111114;
                border: 1px solid #3a3a3a;
                padding: 10px;
                text-align: center;
            }
            QComboBox:hover { border-color: #666; }
            QComboBox QAbstractItemView {
                color: #e6c200;
                background: #111114;
                selection-background-color: #222;
                border: 1px solid #3a3a3a;
            }
        """
        )
        change_row = QHBoxLayout()
        change_row.setAlignment(Qt.AlignHCenter)
        change_row.addWidget(self.vault_combo)

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

        self.btn_scan = QPushButton("Scan")
        self.btn_scan.setFixedWidth(BTN_W)

        self.btn_install_license = QPushButton("Install License")
        self.btn_install_license.setFixedWidth(BTN_W)

        row.addWidget(self.btn_backup)
        self.btn_backup.clicked.connect(self.make_backup)

        row.addWidget(self.btn_restore)
        self.btn_restore.clicked.connect(self.restore_backup)

        row.addWidget(self.btn_scan)
        self.btn_scan.clicked.connect(self.run_scan)

        row.addWidget(self.btn_install_license)
        self.btn_install_license.clicked.connect(self.install_license)

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
        startup_log = (
            "Welcome to DevVault.\n"
            "Trustware: if anything looks unsafe, DevVault refuses.\n"
            "Choose an action: Make Backup or Restore Backup.\n"
            "Vault open and ready....\n"
        )
        try:
            st = check_license()
            startup_log += f"\nLicense state: {st.state}\n{st.message}\n"
        except Exception as e:
            startup_log += f"\nLicense status check failed: {e}\n"

        self.log.setText(startup_log)
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

        self._populate_vault_combo()
        self.vault_combo.currentTextChanged.connect(self.change_vault)

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

    def _install_license_file(self, source_path: Path) -> bool:
        try:
            src = source_path.expanduser().resolve()
        except Exception:
            src = source_path

        try:
            text = src.read_text(encoding="utf-8").strip()
        except Exception as e:
            self.append_log(f"License install refused: could not read file: {e}")
            try:
                self._ui_critical("License Install Failed", f"Could not read license file.\n\n{e}")
            except Exception:
                pass
            return False

        try:
            claims = verify_license_string(text)
            dest = install_license_text(text)
        except LicenseError as e:
            self.append_log(f"License install refused: {e}")
            try:
                self._ui_critical("License Install Failed", str(e))
            except Exception:
                pass
            return False
        except Exception as e:
            self.append_log(f"License install failed: {e}")
            try:
                self._ui_critical("License Install Failed", str(e))
            except Exception:
                pass
            return False

        self.append_log(f"License installed: {dest}")
        self.append_log(f"Licensed to {claims.licensee} until {claims.expires_at.astimezone(timezone.utc).isoformat()}")

        try:
            QMessageBox.information(
                self,
                "License Installed",
                f"License installed successfully.\n\nLicensed to: {claims.licensee}\nInstalled at: {dest}",
            )
        except Exception:
            pass

        return True


    def _ui_critical(self, title: str, text: str) -> None:
        # Always show critical popups from the UI thread.
        def _show() -> None:
            try:
                try:
                    self.raise_()
                    self.activateWindow()
                    self.setFocus()
                except Exception:
                    pass

                mb = QMessageBox(self)
                mb.setIcon(QMessageBox.Icon.Critical)
                mb.setWindowTitle(title)
                mb.setText(text)
                mb.setStandardButtons(QMessageBox.StandardButton.Ok)
                mb.setWindowModality(Qt.WindowModality.ApplicationModal)
                mb.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
                mb.exec()

            except Exception as e:
                # Never fail silently—log why popup failed.
                try:
                    self.append_log(f"Popup failed: {e}")
                except Exception:
                    pass

        try:
            app = QApplication.instance()
            if app is not None and app.thread() == QThread.currentThread():
                _show()
            else:
                QTimer.singleShot(0, _show)
        except Exception as e:
            try:
                self.append_log(f"Popup scheduling failed: {e}")
            except Exception:
                pass
    def _normalize_vault_root(self, value: str) -> str:
        try:
            raw = (value or "").strip()
            if not raw:
                return ""

            p = Path(raw).expanduser().resolve()
            s = str(p)

            if len(s) < 3 or s[1:3] != ":\\":
                return ""

            if any(part.lower() == ".devvault" for part in p.parts):
                return ""

            return s[:3]
        except Exception:
            return ""

    def _available_drive_roots(self) -> list[str]:
        roots: list[str] = []
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            root = f"{letter}:\\"
            try:
                if Path(root).exists():
                    roots.append(root)
            except Exception:
                pass
        return roots

    def _populate_vault_combo(self) -> None:
        drives = self._available_drive_roots()
        if not drives:
            drives = [self.vault_path or "C:\\"]
        if self.vault_path and self.vault_path not in drives:
            drives.insert(0, self.vault_path)

        self.vault_combo.blockSignals(True)
        self.vault_combo.clear()
        self.vault_combo.addItems(drives)
        idx = self.vault_combo.findText(self.vault_path)
        if idx >= 0:
            self.vault_combo.setCurrentIndex(idx)
        self.vault_combo.blockSignals(False)
        self.update_vault_display()

    def update_vault_display(self) -> None:
        self.vault_line_1.setText(f"Current backup location: {self.vault_path}")

    def change_vault(self, folder: str) -> None:
        normalized = self._normalize_vault_root(folder)
        if not normalized:
            self.append_log(f"Vault selection refused: {folder}")
            self._populate_vault_combo()
            return

        if normalized != self.vault_path:
            self.vault_path = normalized
            self.settings.setValue("vault_path", normalized)
            self.update_vault_display()
            self.append_log(f"Vault updated: {normalized}")

    def _set_busy(self, busy: bool) -> None:
        self.vault_combo.setEnabled(not busy)
        self.btn_backup.setEnabled(not busy)
        self.btn_restore.setEnabled(not busy)
        self.btn_scan.setEnabled(not busy)


    def _cleanup_new_snapshots(self) -> None:
        """
        Best-effort: after operator cancel, remove any snapshot dirs created during THIS execute run.
        Scoped to vault root only. Never touches existing snapshot dirs.
        """
        try:
            import re
            import shutil
            from pathlib import Path

            vault_dir = getattr(self, "_pending_backup_vault", None)
            before = getattr(self, "_exec_vault_before", None)
            if vault_dir is None or before is None:
                return

            vault = Path(vault_dir).expanduser().resolve()
            if not vault.exists():
                return

            pat = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")
            for p in vault.iterdir():
                try:
                    if not p.is_dir():
                        continue
                    if p.name in before:
                        continue
                    # Remove engine staging + newly-created snapshot dirs
                    if p.name.startswith(".incomplete-") or pat.match(p.name):
                        shutil.rmtree(p, ignore_errors=True)
                except Exception:
                    pass
        except Exception:
            pass

    def _op_show(self, title: str, phase: str, lines: list[str], allow_cancel: bool) -> None:
        ov = getattr(self, "op_overlay", None)
        if not ov:
            return
        try:
            ov.btn_cancel.setEnabled(bool(allow_cancel))
            ov.set_title(title)
            ov.set_phase(phase)
            ov.set_context_lines(lines)
            ov.start()
        except Exception:
            pass

    def _op_stop(self, allow_close: bool = True) -> None:
        ov = getattr(self, "op_overlay", None)
        if not ov:
            return
        try:
            ov.stop(allow_close=allow_close)
        except Exception:
            pass

    def _op_bind_cancel_preflight(self) -> None:
        # No signal disconnect/connect; just install the current cancel handler.
        def _do_cancel() -> None:
            self.append_log("Cancelled by operator.")
            self._preflight_cancelled = True
            try:
                t = getattr(self, "_backup_thread", None)
                if t is not None:
                    t.requestInterruption()
            except Exception:
                pass
            self._set_busy(False)
            self._op_stop(allow_close=True)
            try:
                ov = getattr(self, "op_overlay", None)
                if ov:
                    ov.btn_cancel.setEnabled(False)
                ov.stop(allow_close=True)
            except Exception:
                pass

        self._op_cancel_handler = _do_cancel


    def _op_bind_cancel_execute(self) -> None:
        # No signal disconnect/connect; just install the current cancel handler.
        def _do_cancel() -> None:
            self._exec_cancelled = True
            try:
                self._cleanup_new_snapshots()
            except Exception:
                pass
            try:
                w = getattr(self, "_backup_exec", None)
                if w is not None:
                    w.cancel()
            except Exception:
                pass
            try:
                ov = getattr(self, "op_overlay", None)
                if ov:
                    ov.btn_cancel.setEnabled(False)
                ov.stop(allow_close=True)
            except Exception:
                pass

        self._op_cancel_handler = _do_cancel


    def _on_op_cancel(self) -> None:
        # Single permanent cancel route for the operation overlay.
        try:
            cb = getattr(self, "_op_cancel_handler", None)
            if cb is not None:
                cb()
        except Exception:
            pass

    def _op_bind_cancel_restore(self) -> None:
        def _do_cancel() -> None:
            self.append_log("Cancelled by operator.")
            self._restore_cancelled = True
            try:
                w = getattr(self, "_restore_worker", None)
                if w is not None:
                    w.cancel()
            except Exception:
                pass
            try:
                ov = getattr(self, "op_overlay", None)
                if ov:
                    ov.btn_cancel.setEnabled(False)
                ov.stop(allow_close=True)
            except Exception:
                pass

        self._op_cancel_handler = _do_cancel

    def _cleanup_backup_preflight_thread(self) -> None:
        # Called only when preflight thread has fully finished.
        self._backup_pre = None
        self._backup_thread = None

    def _cleanup_backup_execute_thread(self) -> None:
        # Called only when execute thread has fully finished.
        self._backup_exec = None
        self._backup_exec_thread = None



    def _start_next_queued_backup(self) -> bool:
        queue = list(getattr(self, "_backup_queue", []) or [])
        if not queue:
            return False

        next_source = Path(queue.pop(0))
        self._backup_queue = queue

        try:
            total = int(getattr(self, "_backup_queue_total", 0) or 0)
        except Exception:
            total = 0

        done_count = max(0, total - len(queue) - 1)
        current_num = done_count + 1
        if total > 0:
            self.append_log(f"Queued backup {current_num} of {total}: {next_source}")
        else:
            self.append_log(f"Queued backup starting: {next_source}")

        self._start_backup_for_source(next_source)
        return True
    def _on_backup_exec_done(self, payload: dict) -> None:
        # If operator cancelled during execute, ignore late 'done' results.
        if bool(getattr(self, "_exec_cancelled", False)):
            try:
                self._cleanup_new_snapshots()
            except Exception:
                pass
            self._exec_cancelled = False
            try:
                self._op_stop(allow_close=True)
                ov = getattr(self, "op_overlay", None)
                if ov:
                    ov.hide()
            except Exception:
                pass
            self._set_busy(False)
            try:
                if getattr(self, "_backup_exec_thread", None) is not None:
                    self._backup_exec_thread.quit()
            except Exception:
                pass
            return

        try:
            source_dir = getattr(self, "_pending_backup_source", None)
            if source_dir is not None:
                add_protected_root(str(Path(source_dir).expanduser().resolve()))
        except Exception as e:
            self.append_log(f"Warning: could not record protected root: {e}")

        self.append_log("Backup complete.")
        self.append_log(f"Result: {payload}")
        self._set_busy(False)
        try:
            self._op_stop(allow_close=True)
            ov = getattr(self, "op_overlay", None)
            if ov:
                ov.hide()
        except Exception:
            pass
        try:
            if getattr(self, "_backup_exec_thread", None) is not None:
                self._backup_exec_thread.quit()
        except Exception:
            pass

        if self._start_next_queued_backup():
            return

        if bool(getattr(self, "_backup_queue_total", 0)):
            self.append_log("Queued backup run complete.")
            self._backup_queue = []
            self._backup_queue_total = 0
    def _on_backup_exec_err(self, msg: str) -> None:
        if (msg or "").strip() == "Cancelled by operator.":
            pass
        else:
            self.append_log(f"Backup refused: {msg}")
            try:
                self._ui_critical("Backup Failed", msg)
            except Exception:
                pass
        self._set_busy(False)
        try:
            self._op_stop(allow_close=True)
            ov = getattr(self, "op_overlay", None)
            if ov:
                ov.hide()
        except Exception:
            pass
        try:
            if getattr(self, "_backup_exec_thread", None) is not None:
                self._backup_exec_thread.quit()
        except Exception:
            pass

    def _on_restore_done(self, payload: dict) -> None:
        if bool(getattr(self, "_restore_cancelled", False)):
            self._restore_cancelled = False
            try:
                self._op_stop(allow_close=True)
                ov = getattr(self, "op_overlay", None)
                if ov:
                    ov.hide()
            except Exception:
                pass
            self._set_busy(False)
            try:
                if getattr(self, "_restore_thread", None) is not None:
                    self._restore_thread.quit()
            except Exception:
                pass
            return
        self.append_log("Restore complete.")
        self.append_log(f"Result: {payload}")
        self._set_busy(False)
        try:
            self._op_stop(allow_close=True)
            ov = getattr(self, "op_overlay", None)
            if ov:
                ov.hide()
        except Exception:
            pass
        try:
            if getattr(self, "_restore_thread", None) is not None:
                self._restore_thread.quit()
        except Exception:
            pass

    def _on_restore_err(self, msg: str) -> None:
        if (msg or "").strip() == "Cancelled by operator.":
            pass
        else:
            self.append_log(f"Restore refused: {msg}")
            try:
                self._ui_critical("Restore Failed", msg)
            except Exception:
                pass
        self._set_busy(False)
        try:
            self._op_stop(allow_close=True)
            ov = getattr(self, "op_overlay", None)
            if ov:
                ov.hide()
        except Exception:
            pass
        try:
            if getattr(self, "_restore_thread", None) is not None:
                self._restore_thread.quit()
        except Exception:
            pass

    def _cleanup_scan_thread(self) -> None:
        self._scan_worker = None
        self._scan_thread = None

    def _looks_like_project_path(self, path: Path) -> bool:
        try:
            if not path.is_dir():
                return False
        except Exception:
            return False

        markers = (
            ".git",
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "Cargo.toml",
            "go.mod",
            ".devvault",
        )

        for marker in markers:
            try:
                if (path / marker).exists():
                    return True
            except Exception:
                continue

        return False

    def _count_files_for_zip_hint(self, root: Path, limit: int = 1000) -> int:
        count = 0
        try:
            for p in root.rglob("*"):
                try:
                    if p.is_file():
                        count += 1
                        if count >= limit:
                            return count
                except Exception:
                    continue
        except Exception:
            return count
        return count

    def _confirm_large_folder_backup(self, folder: Path) -> bool:
        try:
            if not folder.is_dir():
                return True
        except Exception:
            return True

        if self._looks_like_project_path(folder):
            return True

        file_count = self._count_files_for_zip_hint(folder, limit=1000)
        if file_count < 1000:
            return True

        msg = (
            "Large folder detected.\n\n"
            f"Folder:\n  {folder}\n\n"
            f"Detected files: {file_count}+\n\n"
            "For faster backups, you may want to zip this folder first.\n"
            "DevVault can back up archive files directly (.zip, .7z, .rar, .tar, .gz).\n\n"
            "Continue backing up this folder anyway?"
        )

        answer = QMessageBox.warning(
            self,
            "Zip Suggestion",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return answer == QMessageBox.StandardButton.Yes

    def run_scan(self) -> None:
        self.append_log("Scan requested.")
        self.append_log("Scanning your workspaces...")
        self.append_log("Checking for uncovered projects...")
        self._set_busy(True)

        self._scan_thread = QThread()
        self._scan_worker = _ScanWorker()
        self._scan_worker.moveToThread(self._scan_thread)

        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.log.connect(self.append_log)
        self._scan_worker.done.connect(self._on_scan_done, type=Qt.QueuedConnection)
        self._scan_worker.error.connect(self._on_scan_err, type=Qt.QueuedConnection)

        self._scan_thread.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.finished.connect(self._cleanup_scan_thread, type=Qt.QueuedConnection)

        self._scan_thread.start()

        pass

    def _on_scan_done(self, payload: dict) -> None:
        roots = payload.get("scan_roots") or []
        uncovered = payload.get("uncovered") or []
        scanned = int(payload.get("scanned_directories", 0) or 0)
        skipped = int(payload.get("skipped_directories", 0) or 0)

        self.append_log(f"Scan complete. scanned_directories={scanned} skipped_directories={skipped}")

        if roots:
            self.append_log("Scan roots used:")
            for r in roots:
                self.append_log(f"  - {r}")

        if uncovered:
            self.append_log("Unprotected project candidates:")
            for p in uncovered:
                self.append_log(f"  - {p}")
        else:
            self.append_log("No uncovered project directories detected.")

        try:
            self._op_stop(True)
        except Exception:
            pass

        self._set_busy(False)

        try:
            if getattr(self, "_scan_thread", None) is not None:
                self._scan_thread.quit()
        except Exception:
            pass

        if not uncovered:
            return

        st = check_license()
        if not st.backups_allowed:
            self.append_log(f"Backup blocked: {st.state}")
            self.append_log(st.message)
            try:
                self._ui_critical("Backup Blocked", st.message)
            except Exception:
                pass
            return

        try:
            self.raise_()
            self.activateWindow()
            self.setFocus()
        except Exception:
            pass

        accepted, selected_paths = ScanSelectionDialog.ask(self, [str(p) for p in uncovered])

        if not accepted:
            self.append_log("Scan selection canceled by operator.")
            return

        if not selected_paths:
            self.append_log("No projects selected for backup.")
            return

        approved_paths: list[str] = []
        for selected in selected_paths:
            p = Path(selected)
            if self._confirm_large_folder_backup(p):
                approved_paths.append(selected)
            else:
                self.append_log(f"Skipped after zip suggestion: {selected}")

        if not approved_paths:
            self.append_log("No projects selected for backup.")
            return

        self.append_log("Operator selected projects from scan results for backup.")

        try:
            self._backup_queue = list(approved_paths)
            self._backup_queue_total = len(self._backup_queue)
        except Exception:
            self._backup_queue = []
            self._backup_queue_total = 0

        if not self._start_next_queued_backup():
            self.append_log("No queued backup sources were available.")

        return

    def _on_scan_err(self, msg: str) -> None:
        self.append_log(f"Scan failed: {msg}")

        try:
            self._ui_critical("Scan Failed", msg)
        except Exception:
            pass

        try:
            self._op_stop(True)
        except Exception:
            pass

        self._set_busy(False)

        try:
            if getattr(self, "_scan_thread", None) is not None:
                self._scan_thread.quit()
        except Exception:
            pass

    def install_license(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select DevVault License File",
            str(Path.home()),
            "DevVault License (*.dvlic);;All Files (*.*)",
        )
        if not file_path:
            self.append_log("License install canceled.")
            return

        self._install_license_file(Path(file_path))

    def make_backup(self) -> None:
        st = check_license()
        if not st.backups_allowed:
            self.append_log(f"Backup blocked: {st.state}")
            self.append_log(st.message)
            try:
                self._ui_critical("Backup Blocked", st.message)
            except Exception:
                pass
            return

        self.append_log(f"License state: {st.state}")
        self.append_log(st.message)

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Back Up",
            str(Path.home()),
        )
        if not folder:
            self.append_log("Backup canceled.")
            return

        self._start_backup_for_source(Path(folder))

    def _start_backup_for_source(self, source_dir: Path) -> None:
        st = check_license()
        if not st.backups_allowed:
            self.append_log(f"Backup blocked: {st.state}")
            self.append_log(st.message)
            try:
                self._ui_critical("Backup Blocked", st.message)
            except Exception:
                pass
            return

        vault_dir = Path(self.vault_path)

        # Safety: prevent recursive backups (same path, vault inside source, or source inside vault).
        try:
            _src = source_dir.expanduser().resolve()
            _vault = vault_dir.expanduser().resolve()
            if _src == _vault or _vault in _src.parents or _src in _vault.parents:
                msg = "Backup refused: source and vault paths overlap (recursive backup risk)."
                self.append_log(msg)
                self.append_log("Tip: Choose a vault directory completely separate from the source folder.")
                try:
                    QMessageBox.critical(
                        self,
                        "Backup Refused",
                        msg + "\n\nChoose a vault directory completely separate from the source folder.",
                    )
                except Exception:
                    pass
                return
        except Exception:
            pass

        self._pending_backup_source = source_dir
        self._pending_backup_vault = vault_dir

        self.append_log(f"Backup starting: {source_dir}")
        self._set_busy(True)

        self._backup_thread = QThread()
        self._backup_pre = _BackupPreflightWorker(source_dir, vault_dir)
        self._backup_pre.moveToThread(self._backup_thread)

        self._backup_thread.started.connect(self._backup_pre.run)
        self._backup_pre.log.connect(self.append_log)
        self._backup_pre.done.connect(self._on_backup_pre_done, type=Qt.QueuedConnection)
        self._backup_pre.error.connect(self._on_backup_pre_err, type=Qt.QueuedConnection)

        self._backup_thread.finished.connect(self._backup_pre.deleteLater)
        self._backup_thread.finished.connect(self._backup_thread.deleteLater)
        self._backup_thread.finished.connect(self._cleanup_backup_preflight_thread, type=Qt.QueuedConnection)
        self._backup_thread.start()

        try:
            self._op_bind_cancel_preflight()
            self._op_show(
                title="Preflight running",
                phase="Preflight → Confirm → Execute",
                lines=[
                    f"Source: {source_dir}",
                    f"Vault: {vault_dir}",
                    "WARNING: BACKUPS ARE ARCHIVAL SNAPSHOTS.",
                    "DO NOT rename snapshot folders.",
                    "DO NOT modify files inside a snapshot.",
                    "Tampering will cause DevVault to refuse restore.",
                ],
                allow_cancel=True,
            )
        except Exception:
            pass

    def _on_backup_pre_done(self, pre: dict) -> None:
        # If operator cancelled during preflight, ignore results and exit cleanly.
        if bool(getattr(self, "_preflight_cancelled", False)):
            self._preflight_cancelled = False
            try:
                self._op_stop(allow_close=True)
            except Exception:
                pass
            try:
                ov = getattr(self, "op_overlay", None)
                if ov:
                    ov.hide()
            except Exception:
                pass
            self._set_busy(False)
            try:
                if getattr(self, "_backup_thread", None) is not None:
                    self._backup_thread.quit()
            except Exception:
                pass
            return
        try:
            self._op_stop(allow_close=False)
        except Exception:
            pass
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
        # Capacity guard: refuse backups that cannot fit in the vault free space.
        try:
            required_bytes = int(pre.get("total_bytes", 0) or 0)
        except Exception:
            required_bytes = 0

        # Vault capacity / free space (best-effort)
        vault_total = None
        vault_free = None
        try:
            import shutil
            _vp = getattr(self, "_pending_backup_vault", None) or pre.get("vault") or ""
            if _vp:
                du = shutil.disk_usage(str(_vp))
                vault_total = int(du.total)
                vault_free = int(du.free)
        except Exception:
            vault_total = None
            vault_free = None

        if vault_free is not None and required_bytes > int(vault_free):
            self.append_log(
                "Backup refused: not enough free space in vault "
                f"(required {fmt_bytes(required_bytes)}, available {fmt_bytes(vault_free)})."
            )
            self.append_log("Tip: Choose a larger vault drive or reduce source size.")
            
            try:
                self._ui_critical(
                    "Backup Refused",
                    f"Not enough free space in vault.\n\nRequired: {fmt_bytes(required_bytes)}\nAvailable: {fmt_bytes(vault_free)}\n\nChoose a larger vault drive or reduce source size."
                )
            except Exception:
                pass
            try:
                self._backup_thread.quit()
            except Exception:
                pass
            self._set_busy(False)
            return
        msg = (
            "Pre-backup validation complete.<br><br>"
            f"Source: {pre.get('source')}<br>"
            f"Vault:&nbsp;&nbsp;{pre.get('vault')}<br><br>"
            f"Files: {pre.get('file_count')}<br>"
            f"Size:&nbsp;&nbsp;{fmt_bytes(pre.get('total_bytes', 0))}<br>"
            f"Unreadable paths: {unread}<br>"
        )

        if vault_total is not None and vault_free is not None:
            pct = 0
            try:
                pct = int(round((vault_free / vault_total) * 100)) if vault_total else 0
            except Exception:
                pct = 0
            msg += (
                f"Vault capacity: {fmt_bytes(vault_total)}<br>"
                f"Free:&nbsp;&nbsp;{fmt_bytes(vault_free)} (~{pct}% free)<br>"
            )
        msg += "<br>"

        if warn_lines:
            msg += "Warnings:<br>" + warn_lines.replace("\n", "<br>") + "<br>"
        if sample_lines:
            msg += "Unreadable samples:<br>" + sample_lines.replace("\n", "<br>") + "<br>"

        msg += (
            "<br><br>"
            "<div style='color:#ff3b3b; font-weight:700;'>⚠ BACKUP SNAPSHOT NOTICE</div>"
            "<div style='color:#ff3b3b; font-weight:700;'>DevVault backups are archival snapshots.</div>"
            "<div style='color:#ff3b3b; font-weight:700;'>DO NOT rename snapshot folders.</div>"
            "<div style='color:#ff3b3b; font-weight:700;'>DO NOT modify files inside a snapshot.</div>"
            "<div style='color:#ff3b3b; font-weight:700;'>DO NOT delete manifest.json.</div>"
            "<div style='color:#ff3b3b; font-weight:700;'>If a snapshot is changed, DevVault will refuse restore.</div>"
            "<br><div>Proceed with backup?</div>"
        )

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

        # CRITICAL: schedule dialog on UI thread
        def _ask_confirm() -> None:
            if not BackupConfirmDialog.ask(

                self,

                title="Confirm Backup",

                summary_lines=[

                    "Pre-backup validation complete.",

                    "Review details below and approve to execute backup.",

                ],

                details_text=msg,

                approve_text="Run Backup",

                cancel_text="Cancel",

            ):

                self.append_log("Backup canceled (operator declined preflight confirmation).")

                try:
                    self._op_stop(allow_close=True)
                    ov = getattr(self, "op_overlay", None)
                    if ov:
                        ov.hide()
                except Exception:
                    pass

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
            self._backup_exec.done.connect(self._on_backup_exec_done, type=Qt.QueuedConnection)
            self._backup_exec.error.connect(self._on_backup_exec_err, type=Qt.QueuedConnection)
            self._backup_exec_thread.finished.connect(self._backup_exec.deleteLater)
            self._backup_exec_thread.finished.connect(self._backup_exec_thread.deleteLater)
            self._backup_exec_thread.finished.connect(self._cleanup_backup_execute_thread, type=Qt.QueuedConnection)
            # Record vault baseline BEFORE execute so cancel can remove any new snapshot dirs from this run.
            try:
                _v = Path(str(vault_dir)).expanduser().resolve()
                self._exec_vault_before = {p.name for p in _v.iterdir() if p.is_dir()}
            except Exception:
                self._exec_vault_before = set()

            self._backup_exec_thread.start()
            # Operation overlay: Backup executing
            try:
                self._op_bind_cancel_execute()
                self._op_show(
                    title="Backup in progress",
                    phase="Preflight → Confirm → Execute",
                    lines=[
                        f"Source: {source_dir}",
                        f"Vault: {vault_dir}",
                    ],
                    allow_cancel=True,
                )
            except Exception:
                pass

        QTimer.singleShot(0, _ask_confirm)

    def _on_backup_pre_err(self, msg: str) -> None:
        try:
            self._op_stop(allow_close=True)
        except Exception:
            pass
        self.append_log(f"Backup refused: {msg}")
        try:
            self._ui_critical("Backup Preflight Failed", msg)
        except Exception:
            pass
        self._set_busy(False)
        try:
            self._backup_thread.quit()
            try:
                pass
            except Exception:
                pass
        except Exception:
            pass

    def restore_backup(self) -> None:
        # 1) Select snapshot from hidden DevVault-managed snapshot store
        vault_dir = Path(self.vault_path).expanduser().resolve()

        try:
            from scanner.adapters.filesystem import OSFileSystem
            from scanner.snapshot_rows import get_snapshot_rows
            from scanner.snapshot_listing import snapshot_storage_root

            fs = OSFileSystem()
            rows = get_snapshot_rows(fs=fs, backup_root=vault_dir)
            store_root = snapshot_storage_root(vault_dir)
        except Exception as e:
            QMessageBox.critical(self, "Restore Refused", f"Could not load snapshots: {e}")
            self.append_log(f"Restore refused: could not load snapshots: {e}")
            return

        if not rows:
            QMessageBox.information(
                self,
                "No Snapshots Found",
                "No restoreable snapshots were found in the hidden DevVault snapshot store.",
            )
            self.append_log("Restore canceled (no snapshots available).")
            return

        def _fmt_bytes(n: int) -> str:
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
            if i == 0:
                return f"{int(f)} {units[i]}"
            return f"{f:.2f} {units[i]}"

        labels: list[str] = []
        label_to_snapshot: dict[str, Path] = {}

        for row in rows:
            snapshot_path = store_root / row.snapshot_id

            try:
                from scanner.snapshot_metadata import read_snapshot_metadata
                md = read_snapshot_metadata(fs=fs, snapshot_dir=snapshot_path)
                src_name = (md.source_name or "").strip()
            except Exception:
                src_name = ""

            if not src_name:
                src_name = snapshot_path.name

            if row.created_at:
                created = row.created_at.date().isoformat()
            else:
                created = row.snapshot_id.split(" - ", 1)[0]

            label = (
                f"{src_name} — "
                f"{created} — "
                f"{row.file_count} files — "
                f"{_fmt_bytes(row.total_bytes)}"
            )

            labels.append(label)
            label_to_snapshot[label] = snapshot_path

        selected_label, ok = QInputDialog.getItem(
            self,
            "Select Snapshot",
            "Select a snapshot to restore",
            labels,
            0,
            False,
        )
        if not ok or not selected_label:
            self.append_log("Restore canceled (no snapshot selected).")
            return

        snapshot_dir = label_to_snapshot[selected_label].expanduser().resolve()

        # 2) Read snapshot metadata and derive restored folder name
        try:
            from scanner.adapters.filesystem import OSFileSystem
            from scanner.snapshot_metadata import read_snapshot_metadata

            md = read_snapshot_metadata(fs=OSFileSystem(), snapshot_dir=snapshot_dir)
            source_name = (md.source_name or "").strip()
        except Exception:
            source_name = ""

        if not source_name:
            source_name = snapshot_dir.name
            if " - " in source_name:
                source_name = source_name.split(" - ", 1)[-1]
            if source_name.endswith(" - backup"):
                source_name = source_name[:-9].rstrip()

        if not source_name:
            source_name = "Restored Backup"

        suggested_restore_name = f"{source_name} - restored"

        # 3) Auto-create restore destination under Desktop\DevVault Restores
        restore_root = (Path.home() / "Desktop" / "DevVault Restores").expanduser().resolve()

        def _unique_restore_dir(root: Path, base_name: str) -> Path:
            candidate = root / base_name
            if not candidate.exists():
                return candidate

            i = 2
            while True:
                candidate = root / f"{base_name} ({i})"
                if not candidate.exists():
                    return candidate
                i += 1

        try:
            restore_root.mkdir(parents=True, exist_ok=True)
            _ensure_devvault_restores_shortcut(restore_root)
            destination_dir = _unique_restore_dir(restore_root, suggested_restore_name)
        except Exception as e:
            QMessageBox.critical(self, "Restore Refused", f"Could not prepare restore folder: {e}")
            self.append_log(f"Restore refused: could not prepare restore folder: {e}")
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
                "Warning: Destination appears to be inside a OneDrive-synced folder.\n"
                "Cloud sync can lock files or modify timestamps during restore.\n"
                "For maximum reliability, restore to a local non-synced folder.\n"
                f"Destination:\n  {destination_dir}\n"
                "Continue anyway?"
            )
            if QMessageBox.warning(self, "OneDrive Destination Warning", warn, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                self.append_log("Restore canceled (OneDrive warning declined).")
                return

        # 4) Confirm restore (explicit, irreversible warning)
        vault_total = None
        vault_free = None

        msg = (
            "Restore will COPY snapshot contents into a new restore folder.\n"
            f"Snapshot:\n  {snapshot_dir}\n"
            f"Suggested restore name:\n  {suggested_restore_name}\n"
            f"Restore root:\n  {restore_root}\n"
            f"Destination (auto-created):\n  {destination_dir}\n"
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


        self._restore_worker.done.connect(self._on_restore_done, type=Qt.QueuedConnection)
        self._restore_worker.error.connect(self._on_restore_err, type=Qt.QueuedConnection)
        self._restore_thread.finished.connect(self._restore_worker.deleteLater)
        self._restore_thread.finished.connect(self._restore_thread.deleteLater)

        self._restore_thread.start()
        # Operation overlay: Restore executing
        try:
            self._op_bind_cancel_restore()
            self._op_show(
                title="Restore in progress",
                phase="Validate → Execute",
                lines=[
                    f"Snapshot: {snapshot_dir}",
                    f"Restore Name: {suggested_restore_name}",
                    f"Destination: {destination_dir}",
                ],
                allow_cancel=True,
            )
        except Exception:
            pass


class _ScanWorker(QObject):
    log = Signal(str)
    done = Signal(dict)
    error = Signal(str)

    def run(self) -> None:
        try:
            scan_roots = []
            candidates = [
                Path("C:/dev"),
                Path.home() / "dev",
                Path.home() / "Documents",
                Path.home() / "Desktop",
                Path.home() / "Pictures",
                Path.home() / "Videos",
                Path.home() / "Downloads",
                Path.home() / "OneDrive" / "Documents",
                Path.home() / "OneDrive" / "Desktop",
                Path.home() / "OneDrive" / "Pictures",
                Path.home() / "OneDrive" / "Videos",
                Path.home() / "OneDrive" / "Downloads",
            ]

            for r in candidates:
                try:
                    if r.exists() and r.is_dir():
                        scan_roots.append(r)
                except Exception:
                    pass

            if not scan_roots:
                self.done.emit({
                    "scan_roots": [],
                    "uncovered": [],
                    "scanned_directories": 0,
                    "skipped_directories": 0,
                })
                return

            self.log.emit("Scan starting...")
            for r in scan_roots:
                self.log.emit(f"Scan root: {r}")

            cov = compute_uncovered_candidates(
                scan_roots=scan_roots,
                depth=4,
                top=30,
            )

            self.done.emit({
                "scan_roots": [str(p) for p in scan_roots],
                "uncovered": [str(p) for p in cov.uncovered],
                "scanned_directories": int(cov.scanned_directories),
                "skipped_directories": int(cov.skipped_directories),
            })
        except Exception as e:
            self.error.emit(str(e))

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


















































































































