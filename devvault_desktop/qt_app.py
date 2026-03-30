from __future__ import annotations

# --- GLOBAL ADMIN SESSION ---
_GLOBAL_ADMIN_SESSION = {}


import os
import sys
from datetime import datetime, timezone
import subprocess
import uuid
from pathlib import Path
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog

from PySide6.QtCore import Qt
from PySide6.QtCore import QObject, Signal, QThread, QTimer
from PySide6.QtGui import QFont, QPixmap, QGuiApplication, QIcon, QAction, QColor, QPainter, QCursor
from PySide6.QtWidgets import (
    QSizePolicy,
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
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
    QSystemTrayIcon,
    QMenu,
    QPlainTextEdit,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect
from devvault_desktop.coverage_assurance import compute_uncovered_candidates
from devvault_desktop.nas_auth import save_windows_nas_credentials
from devvault_desktop.config import (
    add_protected_root,
    clear_business_seat_identity,
    config_dir,
    get_business_nas_path,
    get_business_seat_identity,
    set_business_nas_path,
    set_business_seat_identity,
    set_vault_dir,
)
from devvault_desktop.license_gate import check_license
from devvault_desktop.nas_enforcement import NASNotConfiguredError, enforce_business_nas_requirement
from devvault_desktop.business_vault_authority import validate_business_vault_authority
from devvault_desktop.reporting import (
    build_advanced_scan_report,
    build_business_administrative_visibility_report,
    build_business_fleet_health_summary_report,
    build_business_org_recovery_audit_report,
    build_business_seat_protection_state_report,
    build_business_vault_health_intelligence_report,
    build_recovery_audit_report,
    build_snapshot_comparison_report,
    export_advanced_scan_report_json_dict,
    render_advanced_scan_report_text,
    render_business_administrative_visibility_text,
    render_business_fleet_health_summary_text,
    render_business_org_recovery_audit_text,
    render_business_seat_protection_state_text,
    render_business_vault_health_intelligence_text,
    render_recovery_audit_text,
    render_snapshot_comparison_text,
)
from devvault.licensing import LicenseError, install_license_text, verify_license_string, read_installed_license_text
from devvault.validation_state import save_state
from devvault.validation_client import validate_now
from devvault.reminder_state import mark_unprotected, mark_protected

from devvault_desktop.seat_registry import SeatRegistryEngine, SeatRecord
from devvault_desktop.business_fetchers import (
    AdministrativeVisibilityFetcher,
    FetchRequest,
    FleetHealthSummaryFetcher,
    OrganizationRecoveryAuditFetcher,
    SeatProtectionStateFetcher,
    VaultHealthIntelligenceFetcher,
)
from devvault_desktop.business_runtime_config import ensure_business_runtime_config
from devvault_desktop.business_seat_api import (
    BusinessSeatApiError,
    create_business_invite,
    enroll_business_seat,
    issue_business_admin_seat_login_token,
    list_business_invites,
    list_business_seats,
    login_business_admin_with_password,
    login_business_admin_with_seat_token,
    resend_business_invite,
    reset_business_admin_password,
    set_business_admin_password,
    revoke_business_invite,
    revoke_business_seat,
)
from devvault_desktop.business_seat_models import (
    BusinessInviteRow,
    BusinessSeatRow,
    count_active_business_seats,
    normalize_business_invite_rows,
    normalize_business_seat_rows,
)


ASSET_DIR = Path(__file__).resolve().parent / "assets"

ASSET_WATERMARK = ASSET_DIR / "brand" / "trustware-shield-watermark.png"
ASSET_BG_LOCKS = ASSET_DIR / "bg_locks_with_text.png"
ASSET_ICON = ASSET_DIR / "vault.ico"

def _simulated_entitlements_from_env() -> set[str]:
    raw = (os.environ.get("DEVVAULT_SIM_ENTITLEMENTS", "") or "").strip().lower()
    if not raw:
        return set()

    presets = {
        "core": {
            "core_scan_system",
            "core_backup_engine",
        },
        "pro": {
            "core_scan_system",
            "core_backup_engine",
            "pro_advanced_scan_reports",
            "pro_snapshot_comparison",
            "pro_recovery_audit_reports",
            "pro_export_reports",
        },
        "business": {
            "core_scan_system",
            "core_backup_engine",
            "pro_advanced_scan_reports",
            "pro_snapshot_comparison",
            "pro_recovery_audit_reports",
            "pro_export_reports",
            "biz_org_audit_logging",
            "biz_seat_admin_tools",
        },
    }

    if raw in presets:
        return set(presets[raw])

    normalized = raw.replace(";", ",")
    return {
        part.strip()
        for part in normalized.split(",")
        if part.strip()
    }

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






DEVVAULT_CUSTOM_DIALOG_STYLE = """
QDialog {
    background-color: #070707;
    color: #f5c400;
}

QLabel {
    background: transparent;
    color: #f5c400;
}

QPushButton {
    background-color: #101010;
    color: #f5c400;
    border: 1px solid #3a3a3a;
    min-width: 110px;
    padding: 8px 16px;
}

QPushButton:hover {
    border: 1px solid #f5c400;
}

QPushButton:pressed {
    background-color: #181818;
}

QListWidget {
    background-color: #0b0b0b;
    color: #f5c400;
    border: 1px solid #2a2a2a;
    outline: none;
}

QListWidget::item {
    background-color: transparent;
    color: #f5c400;
    padding: 6px 8px;
}

QListWidget::item:selected {
    background-color: #141414;
    color: #ffd84d;
}

QTextEdit {
    background-color: #0b0b0b;
    color: #f5c400;
    border: 1px solid #2a2a2a;
    selection-background-color: #2a2a2a;
    selection-color: #ffd84d;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollBar:vertical {
    background: #0b0b0b;
    width: 12px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #2a2a2a;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #f5c400;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QCheckBox {
    background: transparent;
    color: #f5c400;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
}

QCheckBox::indicator:unchecked {
    border: 1px solid #666666;
    background: #0b0b0b;
}


/* List rows */
QListWidget::item {
    padding: 6px 10px;
}

QListWidget::item:hover {
    background-color: #141414;
}

QListWidget::item:selected {
    background-color: #1a1a1a;
    color: #ffd84d;
}

/* DevVault gold checkboxes */
QListWidget::indicator {
    width: 18px;
    height: 18px;
}

QListWidget::indicator:unchecked {
    border: 1px solid #666666;
    background: #0b0b0b;
}

QListWidget::indicator:unchecked:hover {
    border: 1px solid #f5c400;
}

QListWidget::indicator:checked {
    border: 1px solid #f5c400;
    background: #101010;
}

QListWidget::indicator:checked:hover {
    background: #1a1a1a;
}

QCheckBox::indicator:checked {
    border: 1px solid #f5c400;
    background: #101010;
}
"""

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
        self.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)

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
        self.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)

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
    Cheap best-effort drive health check.

    IMPORTANT:
    - Do NOT enumerate the root directory here.
    - Root listing can block badly on removable/cloud-backed paths.
    - A simple exists()/is_dir() probe is enough for the watcher.
    """
    try:
        return root.exists() and root.is_dir()
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

        # Elapsed timer / heartbeat
        self._dots = QLabel("Elapsed: 00:00")
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
        self._elapsed_s = 0

        self._t_lock = QTimer(self)
        self._t_lock.setInterval(500)
        self._t_lock.timeout.connect(self._tick_lock)

        self._t_dots = QTimer(self)
        self._t_dots.setInterval(1000)
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


    def set_title(self, text: str) -> None:
        try:
            self._title.setText(str(text or "Securing changes"))
        except Exception:
            pass

    def set_phase(self, text: str) -> None:
        try:
            self._phase.setText(str(text or ""))
        except Exception:
            pass

    def set_context_lines(self, lines: list[str]) -> None:
        try:
            safe_lines = [str(x) for x in (lines or []) if str(x).strip()]
            self._ctx.setText("\n".join(safe_lines))
        except Exception:
            self._ctx.setText("")

    def start(self) -> None:
        try:
            self._elapsed_s = 0
            self._render_lock()
            self._dots.setText("Elapsed: 00:00")
            self.setGeometry(self.parent().rect())
            self.raise_()
            self.show()
            self._t_lock.start()
            self._t_dots.start()
        except Exception:
            pass

    def stop(self, allow_close: bool = True) -> None:
        try:
            self._t_lock.stop()
        except Exception:
            pass
        try:
            self._t_dots.stop()
        except Exception:
            pass
        try:
            self.btn_cancel.setEnabled(bool(allow_close))
        except Exception:
            pass
        try:
            self.hide()
        except Exception:
            pass

    def resizeEvent(self, event) -> None:
        try:
            if self.parent() is not None:
                self.setGeometry(self.parent().rect())
        except Exception:
            pass
        try:
            super().resizeEvent(event)
        except Exception:
            pass

    def _tick_lock(self) -> None:
        self._lock_state = not self._lock_state
        self._render_lock()

    def _tick_dots(self) -> None:
        self._elapsed_s += 1
        mm = self._elapsed_s // 60
        ss = self._elapsed_s % 60
        self._dots.setText(f"Elapsed: {mm:02d}:{ss:02d}")

    def _render_lock(self) -> None:
        self._lock.setText("🔓" if self._lock_state else "🔒")
        f = self._lock.font()
        try:
            f.setPointSize(64)
        except Exception:
            pass
        self._lock.setFont(f)


def _centered_message(
    parent,
    first,
    second=None,
    buttons=None,
    default_button=None,
    icon=None,
):
    title = "DevVault"
    text = ""

    if isinstance(first, QMessageBox.Icon):
        icon = first
        title = str(second or "DevVault")
        text = ""
    else:
        title = str(first or "DevVault")
        text = str(second or "")

    if icon is None:
        icon = QMessageBox.Icon.Information
    if buttons is None:
        buttons = QMessageBox.StandardButton.Ok
    if default_button is None:
        default_button = QMessageBox.StandardButton.Ok

    msg = QMessageBox(parent)
    msg.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)
    msg.setIcon(icon)
    msg.setWindowTitle(title)
    msg.setText(text)
    
    # HARDEN BUTTON TYPE
    if isinstance(buttons, str):
        buttons = QMessageBox.StandardButton.Ok

    msg.setStandardButtons(buttons)

    msg.setDefaultButton(default_button)

    try:
        final_size = msg.sizeHint().expandedTo(msg.minimumSizeHint())
        msg.resize(final_size)
    except Exception:
        pass

    try:
        if parent is not None:
            try:
                parent.raise_()
                parent.activateWindow()
            except Exception:
                pass
        _center_widget_on_parent(msg, parent)
    except Exception:
        pass

    try:
        msg.raise_()
        msg.activateWindow()
    except Exception:
        pass

    try:
        QTimer.singleShot(0, lambda: _center_widget_on_parent(msg, parent))
        QTimer.singleShot(15, lambda: _center_widget_on_parent(msg, parent))
    except Exception:
        pass

    return msg.exec()


def _center_widget_on_parent(widget, parent) -> None:
    try:
        if parent is not None and parent.isVisible():
            parent_geo = parent.frameGeometry()
            widget_geo = widget.frameGeometry()
            widget_geo.moveCenter(parent_geo.center())
            widget.move(widget_geo.topLeft())
        else:
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                widget_geo = widget.frameGeometry()
                widget_geo.moveCenter(avail.center())
                widget.move(widget_geo.topLeft())
    except Exception:
        pass


def _group_token(token: str) -> str:
    raw = str(token or "").strip()
    if not raw:
        return ""

    compact = raw.replace("-", "").replace(" ", "").upper()
    if not compact:
        return ""

    return "-".join(
        compact[i:i + 4]
        for i in range(0, len(compact), 4)
    )


def _safe_app_version() -> str:
    try:
        from devvault_desktop import __version__  # type: ignore
        return str(__version__)
    except Exception:
        return "unknown"


def _collect_installed_license_context() -> dict:
    try:
        st = check_license()

        license_id = ""
        plan = ""
        seats = 0

        try:
            text = read_installed_license_text()
            if text.strip():
                claims = verify_license_string(text)
                license_id = str(getattr(claims, "license_id", "") or "").strip()
                plan = str(getattr(claims, "plan", "") or "").strip()
                seats_raw = getattr(claims, "seats", 0)
                try:
                    seats = int(seats_raw or 0)
                except Exception:
                    seats = 0
        except Exception:
            pass

        return {
            "license_id": license_id,
            "plan": plan,
            "seats": seats,
            "state": str(getattr(st, "state", "") or "").strip(),
        }
    except Exception:
        return {}


def _collect_vault_evidence_summary() -> dict:
    try:
        roots: list[str] = []

        try:
            configured_root = str(getattr(DevVaultQt, "vault_path", "") or "").strip()
        except Exception:
            configured_root = ""

        if configured_root:
            root = Path(configured_root).expanduser()
            vault_dir = root / ".devvault"
            roots.append(str(vault_dir))

        roots = [r for r in dict.fromkeys(roots) if str(r).strip()]

        has_history = False
        for r in roots:
            try:
                snap = Path(r) / "snapshots"
                if snap.exists():
                    has_history = True
                    break
            except Exception:
                pass

        return {
            "vault_root_count": len(roots),
            "known_vault_roots": roots,
            "has_snapshot_history": has_history,
        }
    except Exception:
        return {}


def _compute_device_fingerprint() -> str:
    try:
        import hashlib
        import os
        import platform

        hostname = str(
            os.environ.get("COMPUTERNAME")
            or os.environ.get("HOSTNAME")
            or platform.node()
            or ""
        ).strip().lower()

        arch = str(platform.machine() or "").strip().lower()
        system = str(platform.system() or "").strip().lower()
        device = str(os.environ.get("PROCESSOR_IDENTIFIER") or "").strip().lower()

        raw = "|".join([hostname, arch, system, device])

        if not raw.strip():
            return ""

        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    except Exception:
        return ""


class SnapshotSelectDialog(QDialog):
    def __init__(self, parent, snapshots):
        self._business_nas_required = True # ensure defined early
        super().__init__(parent)
        self.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)
        self.setWindowTitle("Select Snapshot")
        self.setModal(True)
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)

        lbl = QLabel("Select a snapshot to restore", self)
        root.addWidget(lbl)

        self.combo = QComboBox(self)
        self.combo.addItems(snapshots)
        root.addWidget(self.combo)

        btn_row = QHBoxLayout()

        btn_row.addStretch(1)

        btn_ok = QPushButton("OK", self)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        root.addLayout(btn_row)

    @staticmethod
    def ask(parent, snapshots):
        dlg = SnapshotSelectDialog(parent, snapshots)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        if not ok:
            return False, None
        return True, dlg.combo.currentText()



class EnrollSeatDialog(QDialog):
    def __init__(self, parent, *, subscription_id: str, customer_id: str):
        self._business_nas_required = True # ensure defined early
        super().__init__(parent)
        self.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)
        self.setWindowTitle("Enroll Seat")
        self.setModal(True)
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)

        title = QLabel("Enroll Seat", self)
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)

        subtitle = QLabel(
            "Create a licensed server-backed Business seat enrollment record.",
            self
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#b8b8b8;")
        root.addWidget(subtitle)

        root.addSpacing(8)

        root.addWidget(QLabel("Subscription ID", self))
        self.txt_subscription_id = QLineEdit(self)
        self.txt_subscription_id.setText(subscription_id)
        self.txt_subscription_id.setReadOnly(True)
        self.txt_subscription_id.setStyleSheet("color:#8a8a8a;")
        root.addWidget(self.txt_subscription_id)

        root.addWidget(QLabel("Customer ID", self))
        self.txt_customer_id = QLineEdit(self)
        self.txt_customer_id.setText(customer_id)
        self.txt_customer_id.setReadOnly(True)
        self.txt_customer_id.setStyleSheet("color:#8a8a8a;")
        root.addWidget(self.txt_customer_id)

        email_label = QLabel("Assigned Email (Same E-Mail as invite) *", self)
        email_label.setStyleSheet("color:#ff8a8a;font-weight:700;")
        root.addWidget(email_label)

        self.txt_assigned_email = QLineEdit(self)
        self.txt_assigned_email.setPlaceholderText("Example: seat-01@trustware.dev")
        root.addWidget(self.txt_assigned_email)

        email_hint = QLabel("Required. Must match the invite email when the invite is email-bound.", self)
        email_hint.setWordWrap(True)
        email_hint.setStyleSheet("color:#b8b8b8;font-size:11px;")
        root.addWidget(email_hint)

        root.addWidget(QLabel("Assigned Device ID", self))
        self.txt_assigned_device_id = QLineEdit(self)
        self.txt_assigned_device_id.setPlaceholderText("Example: WORKSTATION-01")
        root.addWidget(self.txt_assigned_device_id)

        authority_hint = QLabel(
            "Invite-defined seat metadata is server-authoritative and is not re-entered during enrollment.",
            self,
        )
        authority_hint.setWordWrap(True)
        authority_hint.setStyleSheet("color:#b8b8b8;font-size:11px;")
        root.addWidget(authority_hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_ok = QPushButton("Enroll Seat", self)
        btn_ok.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        root.addSpacing(10)
        root.addLayout(btn_row)

    def _validate_and_accept(self) -> None:
        assigned_email = self.txt_assigned_email.text().strip()
        if not assigned_email:
            _centered_message(
                self,
                "Enroll Seat",
                "Assigned Email is required.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Warning,
            )
            self.txt_assigned_email.setFocus()
            return

        if "@" not in assigned_email or "." not in assigned_email.split("@", 1)[-1]:
            _centered_message(
                self,
                "Enroll Seat",
                "Assigned Email must be a valid email address.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Warning,
            )
            self.txt_assigned_email.setFocus()
            return

        self.accept()

    @staticmethod
    def ask(parent, *, subscription_id: str, customer_id: str):
        dlg = EnrollSeatDialog(
            parent,
            subscription_id=subscription_id,
            customer_id=customer_id,
        )
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        if not ok:
            return False, None

        return True, {
            "subscription_id": dlg.txt_subscription_id.text().strip(),
            "customer_id": dlg.txt_customer_id.text().strip(),
            "assigned_email": dlg.txt_assigned_email.text().strip(),
            "assigned_device_id": dlg.txt_assigned_device_id.text().strip(),
        }


class ProHubDialog(QDialog):
    def __init__(self, parent):
        self._business_nas_required = True # ensure defined early
        super().__init__(parent)
        self.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)
        self.setWindowTitle("Pro Tools")
        self.setModal(True)
        self.setMinimumWidth(620)

        root = QVBoxLayout(self)

        title = QLabel("Pro Tools", self)
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)

        subtitle = QLabel(
            "Open Pro reports and utilities without backing out to the main menu.",
            self,
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#b8b8b8;")
        root.addWidget(subtitle)

        root.addSpacing(10)

        self.btn_scan = QPushButton("Advanced Scan Report", self)
        self.btn_compare = QPushButton("Compare Snapshots", self)
        self.btn_recovery = QPushButton("Recovery Audit", self)

        for btn in (self.btn_scan, self.btn_compare, self.btn_recovery):
            btn.setMinimumHeight(42)
            root.addWidget(btn)

        root.addSpacing(12)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        root.addLayout(btn_row)

        self.btn_scan.clicked.connect(self._open_advanced_scan_report)
        self.btn_compare.clicked.connect(self._open_snapshot_comparison)
        self.btn_recovery.clicked.connect(self._open_recovery_audit_report)

    def _open_advanced_scan_report(self) -> None:
        parent = self.parent()
        if parent is not None:
            parent.open_advanced_scan_report()

    def _open_snapshot_comparison(self) -> None:
        parent = self.parent()
        if parent is not None:
            parent.open_snapshot_comparison()

    def _open_recovery_audit_report(self) -> None:
        parent = self.parent()
        if parent is not None:
            parent.open_recovery_audit_report()


class CreateInviteDialog(QDialog):
    def __init__(self, parent):
        self._business_nas_required = True # ensure defined early
        super().__init__(parent)
        self.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)
        self.setWindowTitle("Create Invite")
        self.setModal(True)
        self.setMinimumWidth(620)

        root = QVBoxLayout(self)

        title = QLabel("Create Invite", self)
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)

        subtitle = QLabel(
            "Create a server-authoritative Business fleet invite.",
            self,
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#b8b8b8;")
        root.addWidget(subtitle)

        root.addSpacing(8)

        email_label = QLabel("Invitee Email *", self)
        email_label.setStyleSheet("color:#ff8a8a;font-weight:700;")
        root.addWidget(email_label)

        self.txt_invitee_email = QLineEdit(self)
        self.txt_invitee_email.setPlaceholderText("Example: teammate@trustware.dev")
        root.addWidget(self.txt_invitee_email)

        email_hint = QLabel(
            "Required. Invite delivery and email-bound enrollment use this address.",
            self,
        )
        email_hint.setWordWrap(True)
        email_hint.setStyleSheet("color:#b8b8b8;font-size:11px;")
        root.addWidget(email_hint)

        root.addSpacing(6)

        root.addWidget(QLabel("Invited Role *", self))
        self.combo_role = QComboBox(self)
        self.combo_role.addItems(["admin", "operator", "viewer"])
        self.combo_role.setCurrentText("viewer")
        root.addWidget(self.combo_role)

        root.addWidget(QLabel("Seat Label *", self))
        self.txt_seat_label = QLineEdit(self)
        self.txt_seat_label.setPlaceholderText("Example: Accounting Workstation")
        root.addWidget(self.txt_seat_label)

        root.addWidget(QLabel("Assigned Hostname (optional)", self))
        self.txt_assigned_hostname = QLineEdit(self)
        self.txt_assigned_hostname.setPlaceholderText("Example: WORKSTATION-01")
        root.addWidget(self.txt_assigned_hostname)

        root.addWidget(QLabel("Notes (optional)", self))
        self.txt_notes = QLineEdit(self)
        self.txt_notes.setPlaceholderText("Notes")
        root.addWidget(self.txt_notes)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_ok = QPushButton("Create Invite", self)
        btn_ok.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        root.addSpacing(10)
        root.addLayout(btn_row)

    def _validate_and_accept(self) -> None:
        invitee_email = self.txt_invitee_email.text().strip()
        seat_label = self.txt_seat_label.text().strip()

        if not invitee_email:
            _centered_message(
                self,
                "Create Invite",
                "Invitee Email is required.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Warning,
            )
            self.txt_invitee_email.setFocus()
            return

        if "@" not in invitee_email or "." not in invitee_email.split("@", 1)[-1]:
            _centered_message(
                self,
                "Create Invite",
                "Invitee Email must be a valid email address.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Warning,
            )
            self.txt_invitee_email.setFocus()
            return

        if not seat_label:
            _centered_message(
                self,
                "Create Invite",
                "Seat Label is required.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Warning,
            )
            self.txt_seat_label.setFocus()
            return

        self.accept()

    @staticmethod
    def ask(parent):
        dlg = CreateInviteDialog(parent)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        if not ok:
            return False, None

        return True, {
            "invitee_email": dlg.txt_invitee_email.text().strip(),
            "invited_role": dlg.combo_role.currentText().strip().lower(),
            "seat_label": dlg.txt_seat_label.text().strip(),
            "assigned_hostname": dlg.txt_assigned_hostname.text().strip(),
            "notes": dlg.txt_notes.text().strip(),
        }


class InviteCreatedDialog(QDialog):
    def __init__(
        self,
        parent,
        *,
        invitee_email: str,
        invited_role: str,
        seat_label: str,
        assigned_hostname: str,
        notes: str,
        token_id: str,
        expires_at: str,
        raw_token: str,
        grouped_token: str,
        invite_email_delivery: str,
        invite_email_delivery_error: str,
    ):
        super().__init__(parent)
        self.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)
        self.setWindowTitle("Invite Created")
        self.setModal(True)
        self.setMinimumWidth(720)

        self._raw_token = str(raw_token or "").strip()

        root = QVBoxLayout(self)

        title = QLabel("Invite Created", self)
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)

        subtitle = QLabel(
            "Invite email delivery is the normal operator path. "
            "Raw token copy remains available only as fallback.",
            self,
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#b8b8b8;")
        root.addWidget(subtitle)

        root.addSpacing(8)

        details = QTextEdit(self)
        details.setReadOnly(True)
        details.setMinimumHeight(220)

        delivery_state = str(invite_email_delivery or "").strip().lower()
        if delivery_state == "sent":
            delivery_text = "SENT"
        else:
            delivery_text = "FAILED"

        lines = [
            "Invite created successfully.",
            "",
            "Primary delivery: invite email",
            f"Invite Email Delivery: {delivery_text}",
            f"Invitee Email: {invitee_email or 'n/a'}",
            f"Invited Role: {invited_role or 'n/a'}",
            f"Seat Label: {seat_label or 'n/a'}",
            f"Assigned Hostname: {assigned_hostname or 'n/a'}",
            f"Notes: {notes or 'n/a'}",
            f"Token ID: {token_id or 'n/a'}",
            f"Expires At: {expires_at or 'n/a'}",
        ]

        if delivery_text == "FAILED" and str(invite_email_delivery_error or "").strip():
            lines.extend(
                [
                    "",
                    "Email Error:",
                    str(invite_email_delivery_error or "").strip(),
                ]
            )

        lines.extend(
            [
                "",
                "Fallback raw token (copy only if needed):",
                grouped_token or raw_token or "n/a",
                "",
                "DevVault does not store the raw bearer token locally after creation.",
            ]
        )

        details.setPlainText("\n".join(lines))
        root.addWidget(details)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_copy = QPushButton("Copy Token", self)
        btn_copy.clicked.connect(self._copy_token)
        btn_row.addWidget(btn_copy)

        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        root.addLayout(btn_row)

    def _copy_token(self) -> None:
        token = str(self._raw_token or "").strip()
        if not token:
            _centered_message(
                self,
                "Copy Token",
                "No raw invite token is available to copy.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Warning,
            )
            return

        try:
            QApplication.clipboard().setText(token)
            _centered_message(
                self,
                "Copy Token",
                "Raw invite token copied to clipboard.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Information,
            )
        except Exception as e:
            _centered_message(
                self,
                "Copy Token",
                f"Could not copy invite token.\n\n{e}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Critical,
            )

    @staticmethod
    def show_dialog(
        parent,
        *,
        invitee_email: str,
        invited_role: str,
        seat_label: str,
        assigned_hostname: str,
        notes: str,
        token_id: str,
        expires_at: str,
        raw_token: str,
        grouped_token: str,
        invite_email_delivery: str,
        invite_email_delivery_error: str,
    ) -> None:
        dlg = InviteCreatedDialog(
            parent,
            invitee_email=invitee_email,
            invited_role=invited_role,
            seat_label=seat_label,
            assigned_hostname=assigned_hostname,
            notes=notes,
            token_id=token_id,
            expires_at=expires_at,
            raw_token=raw_token,
            grouped_token=grouped_token,
            invite_email_delivery=invite_email_delivery,
            invite_email_delivery_error=invite_email_delivery_error,
        )
        dlg.exec()


class RevokeSeatDialog(QDialog):
    def __init__(self, parent, seat_choices):
        self._business_nas_required = True # ensure defined early
        super().__init__(parent)
        self.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)
        self.setWindowTitle("Revoke Seat")
        self.setModal(True)
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)

        title = QLabel("Revoke Seat", self)
        title.setStyleSheet("font-size:20px;font-weight:700;")
        root.addWidget(title)

        subtitle = QLabel(
            "Select an active licensed server seat to revoke. "
            "This preserves history instead of deleting the record.",
            self
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#b8b8b8;")
        root.addWidget(subtitle)

        root.addSpacing(8)

        root.addWidget(QLabel("Active Seat", self))
        self.combo = QComboBox(self)
        self._choices = list(seat_choices)
        self.combo.addItems([label for label, _ in self._choices])
        root.addWidget(self.combo)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_ok = QPushButton("Revoke Seat", self)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_ok)

        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        root.addSpacing(10)
        root.addLayout(btn_row)

    @staticmethod
    def ask(parent, seat_choices):
        dlg = RevokeSeatDialog(parent, seat_choices)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        if not ok:
            return False, None

        index = dlg.combo.currentIndex()
        if index < 0 or index >= len(dlg._choices):
            return False, None

        return True, dlg._choices[index][1]



class ClickableCard(QLabel):
    def __init__(self, *args, on_click=None, **kwargs):
        self._business_nas_required = True # ensure defined early
        super().__init__(*args, **kwargs)
        self._on_click = on_click
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        try:
            if callable(self._on_click):
                self._on_click()
        except Exception:
            pass
        super().mousePressEvent(event)


class BusinessHubDialog(QDialog):

    def __init__(self, parent):
        self._business_nas_required = True # ensure defined early
        super().__init__(parent)
        self.setWindowTitle("DevVault Business Console")
        self.resize(1040, 640)
        self.setMinimumSize(820, 520)
        self.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)
        self.setWindowFlags(
            Qt.Dialog
            | Qt.CustomizeWindowHint
            | Qt.WindowTitleHint
        )

        self.watermark = QLabel(self)
        self.watermark.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.watermark.setAlignment(Qt.AlignCenter)
        self._apply_business_watermark(wm_size=420, opacity=0.10)
        self._fit_to_available_screen()

        root = QHBoxLayout(self)

        # --- Left Tool Rail ---
        rail_widget = QWidget()
        rail_widget.setMinimumWidth(215)
        rail_widget.setMaximumWidth(235)

        rail = QVBoxLayout(rail_widget)
        rail.setContentsMargins(0, 0, 0, 0)
        rail.setSpacing(8)
        root.addWidget(rail_widget, 0)

        self.btn_dashboard = QPushButton("Dashboard")
        self.btn_org = QPushButton("Organization Recovery Audit")
        self.btn_seats = QPushButton("Seat Identity / Readiness")
        self.btn_seat_mgmt = QPushButton("Seat Management")
        self.btn_set_admin_password = QPushButton("Set Admin Password")
        self.btn_set_admin_password.clicked.connect(self._set_admin_password_for_seat)

        self.btn_invites = QPushButton("Invite Management")
        self.btn_nas_config = QPushButton("Business NAS Configuration")
        self.btn_fleet = QPushButton("Fleet Health Summary")
        self.btn_vault = QPushButton("Vault Health Intelligence")
        self.btn_admin = QPushButton("Administrative Visibility")
        self.btn_history = QPushButton("Historical Records")

        for b in (
            self.btn_dashboard,
            self.btn_org,
            self.btn_seats,
            self.btn_seat_mgmt,
            self.btn_set_admin_password,
            self.btn_invites,
            self.btn_nas_config,
            self.btn_fleet,
            self.btn_vault,
            self.btn_admin,
            self.btn_history,
        ):
            b.setMinimumHeight(42)
            rail.addWidget(b)

        rail.addStretch()

        # --- Right Surface ---
        self.surface = QStackedWidget()
        root.addWidget(self.surface, 1)

        

        # --- Dashboard Surface ---
        self.dashboard_widget = QWidget()
        dash_layout = QVBoxLayout(self.dashboard_widget)

        dash_header = QHBoxLayout()

        dash_title = QLabel("Business Dashboard")
        dash_title.setStyleSheet("font-size:22px;font-weight:700;")
        dash_header.addWidget(dash_title)

        dash_header.addStretch()

        self.btn_refresh_dashboard = QPushButton("Refresh")
        self.btn_refresh_dashboard.setMinimumHeight(38)
        self.btn_refresh_dashboard.clicked.connect(self._on_refresh_dashboard_clicked)
        dash_header.addWidget(self.btn_refresh_dashboard)

        dash_layout.addLayout(dash_header)

        self.lbl_dashboard_refresh = QLabel("Last Refresh: --")
        self.lbl_dashboard_refresh.setStyleSheet("font-size:12px;color:#8a8a8a;padding:2px 0 8px 2px;")
        dash_layout.addWidget(self.lbl_dashboard_refresh)

        cards = QHBoxLayout()

        self.seats_used_card = QLabel("Seats Used\n...")

        self.seats_card = QLabel("Seats Protected to NAS\n...")
        self.vault_card = QLabel("NAS Health\n...")
        self.nas_card = QLabel("NAS Capacity\n...")

        for card in (
            self.seats_used_card,
            self.seats_card,
            self.vault_card,
            self.nas_card,
        ):
            card.setWordWrap(True)
            card.setMinimumWidth(170)

        cards.addWidget(self.seats_used_card, 1)
        cards.addWidget(self.seats_card, 1)
        cards.addWidget(self.vault_card, 1)
        cards.addWidget(self.nas_card, 1)

        dash_layout.addLayout(cards)

        self.seat_status_board = QTextEdit()
        self.seat_status_board.setReadOnly(True)
        self.seat_status_board.setMinimumHeight(180)
        self.seat_status_board.setPlainText("Loading seat status...")
        dash_layout.addWidget(self.seat_status_board)

        dashboard_action_links = QHBoxLayout()
        self.btn_view_attention_seats = QPushButton("View Seats Needing Attention")
        self.btn_view_attention_seats.setMinimumHeight(34)
        dashboard_action_links.addWidget(self.btn_view_attention_seats)
        dashboard_action_links.addStretch()
        dash_layout.addLayout(dashboard_action_links)

        dashboard_actions = QHBoxLayout()
        dashboard_actions.addStretch()
        self.btn_business_console_sign_out = QPushButton("Sign Out Business Session")
        self.btn_business_console_sign_out.setMinimumHeight(36)
        dashboard_actions.addWidget(self.btn_business_console_sign_out)
        dash_layout.addLayout(dashboard_actions)

        dash_layout.addStretch()

        self.surface.addWidget(self.dashboard_widget)

        self._refresh_business_dashboard()

        self.seat_widget = QWidget()
        seat_layout = QVBoxLayout(self.seat_widget)

        seat_title = QLabel("Seat Identity / Readiness")
        seat_title.setStyleSheet("font-size:22px;font-weight:700;")
        seat_layout.addWidget(seat_title)

        seat_subtitle = QLabel(
            "Review local Business seat identity, Business NAS readiness, admin session state, and current blockers before using Business management tools."
        )
        seat_subtitle.setWordWrap(True)
        seat_subtitle.setStyleSheet("color:#b8b8b8;")
        seat_layout.addWidget(seat_subtitle)

        self.lbl_readiness_summary = QLabel("Business readiness: Loading...")
        self.lbl_readiness_summary.setWordWrap(True)
        self.lbl_readiness_summary.setStyleSheet(
            "font-size:14px;font-weight:700;color:#8fd3ff;padding:6px 0 8px 0;"
        )
        seat_layout.addWidget(self.lbl_readiness_summary)

        self.readiness_report = QTextEdit()
        self.readiness_report.setReadOnly(True)
        self.readiness_report.setPlainText("Loading...")
        seat_layout.addWidget(self.readiness_report, 1)

        readiness_actions = QHBoxLayout()
        self.btn_refresh_readiness = QPushButton("Refresh Readiness")
        self.btn_refresh_readiness.setMinimumHeight(36)
        readiness_actions.addWidget(self.btn_refresh_readiness)
        readiness_actions.addStretch()
        seat_layout.addLayout(readiness_actions)

        signout_row = QHBoxLayout()
        signout_row.addStretch()
        self.btn_signout_readiness = QPushButton("Sign Out Business Session")
        self.btn_signout_readiness.setMinimumHeight(36)
        signout_row.addWidget(self.btn_signout_readiness)
        seat_layout.addLayout(signout_row)

        self.surface.addWidget(self.seat_widget)

        self.seat_mgmt_widget = QWidget()
        seat_mgmt_layout = QVBoxLayout(self.seat_mgmt_widget)

        seat_mgmt_title = QLabel("Seat Management")
        seat_mgmt_title.setStyleSheet("font-size:22px;font-weight:700;")
        seat_mgmt_layout.addWidget(seat_mgmt_title)

        seat_mgmt_subtitle = QLabel(
            "Server-authoritative licensed seat lifecycle. Local discovery and governance inventory remain separate."
        )
        seat_mgmt_subtitle.setWordWrap(True)
        seat_mgmt_subtitle.setStyleSheet("color:#b8b8b8;")
        seat_mgmt_layout.addWidget(seat_mgmt_subtitle)

        self.lbl_invite_capacity_warning = QLabel("")
        self.lbl_invite_capacity_warning.setWordWrap(True)
        self.lbl_invite_capacity_warning.setStyleSheet(
            "color:#ff8a8a;font-weight:700;padding:6px 0 2px 0;"
        )
        self.lbl_invite_capacity_warning.hide()
        seat_mgmt_layout.addWidget(self.lbl_invite_capacity_warning)

        self.lbl_local_seat_identity = QLabel("Local Device Seat Identity: Not enrolled")
        self.lbl_local_seat_identity.setWordWrap(True)
        self.lbl_local_seat_identity.setStyleSheet("color:#8fd3ff;padding:4px 0 8px 0;")
        seat_mgmt_layout.addWidget(self.lbl_local_seat_identity)

        seat_mgmt_actions = QHBoxLayout()
        self.btn_refresh_seat_mgmt = QPushButton("Refresh")
        self.btn_add_manual_seat = QPushButton("Enroll Seat")
        self.btn_reassign_local_identity = QPushButton("Reset Identity")
        self.btn_run_seat_health = QPushButton("Seat Health")
        self.btn_remove_manual_seat = QPushButton("Revoke")

        for b in (
            self.btn_refresh_seat_mgmt,
            self.btn_add_manual_seat,
            self.btn_reassign_local_identity,
            self.btn_run_seat_health,
            self.btn_remove_manual_seat,
        ):
            b.setMinimumHeight(36)
            seat_mgmt_actions.addWidget(b)

        seat_mgmt_actions.addStretch()
        seat_mgmt_layout.addLayout(seat_mgmt_actions)

        self.seat_mgmt_report = QTextEdit()
        self.seat_mgmt_report.setReadOnly(True)
        self.seat_mgmt_report.setPlainText("Loading...")
        seat_mgmt_layout.addWidget(self.seat_mgmt_report, 1)

        signout_row = QHBoxLayout()
        signout_row.addStretch()
        self.btn_signout_seat_mgmt = QPushButton("Sign Out Business Session")
        self.btn_signout_seat_mgmt.setMinimumHeight(36)
        signout_row.addWidget(self.btn_signout_seat_mgmt)
        seat_mgmt_layout.addLayout(signout_row)

        self.surface.addWidget(self.seat_mgmt_widget)

        self.invite_widget = QWidget()
        invite_layout = QVBoxLayout(self.invite_widget)

        invite_title = QLabel("Invite Management")
        invite_title.setStyleSheet("font-size:22px;font-weight:700;")
        invite_layout.addWidget(invite_title)

        invite_subtitle = QLabel(
            "Create, resend, review, and revoke server-authoritative fleet invite tokens."
        )
        invite_subtitle.setWordWrap(True)
        invite_subtitle.setStyleSheet("color:#b8b8b8;")
        invite_layout.addWidget(invite_subtitle)

        invite_actions = QHBoxLayout()
        self.btn_refresh_invites = QPushButton("Refresh Invites")
        self.btn_create_invite = QPushButton("Create Invite")
        self.btn_resend_invite = QPushButton("Resend Invite")
        self.btn_revoke_invite = QPushButton("Revoke Invite")

        for b in (
            self.btn_refresh_invites,
            self.btn_create_invite,
            self.btn_resend_invite,
            self.btn_revoke_invite,
        ):
            b.setMinimumHeight(36)
            invite_actions.addWidget(b)

        invite_actions.addStretch()
        invite_layout.addLayout(invite_actions)

        self.invite_report = QTextEdit()
        self.invite_report.setReadOnly(True)
        self.invite_report.setPlainText("Loading...")
        invite_layout.addWidget(self.invite_report, 1)

        signout_row = QHBoxLayout()
        signout_row.addStretch()
        self.btn_signout_invites = QPushButton("Sign Out Business Session")
        self.btn_signout_invites.setMinimumHeight(36)
        signout_row.addWidget(self.btn_signout_invites)
        invite_layout.addLayout(signout_row)

        self.surface.addWidget(self.invite_widget)

        self.nas_widget = QWidget()
        nas_layout = QVBoxLayout(self.nas_widget)

        nas_title = QLabel("Business NAS Configuration")
        nas_title.setStyleSheet("font-size:22px;font-weight:700;")
        nas_layout.addWidget(nas_title)

        nas_subtitle = QLabel(
            "Detect, validate, and set the authoritative NAS target used by Business backups."
        )
        nas_subtitle.setWordWrap(True)
        nas_subtitle.setStyleSheet("color:#b8b8b8;")
        nas_layout.addWidget(nas_subtitle)

        self.lbl_nas_current = QLabel("Current Business NAS: Not configured")
        self.lbl_nas_current.setWordWrap(True)
        self.lbl_nas_current.setStyleSheet("color:#8fd3ff;padding:4px 0 8px 0;")
        nas_layout.addWidget(self.lbl_nas_current)

        self.lbl_nas_status = QLabel("STATUS: NOT CONFIGURED")
        self.lbl_nas_status.setWordWrap(True)
        self.lbl_nas_status.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.lbl_nas_status.setStyleSheet(
            "font-size:14px;font-weight:700;color:#f5c400;padding:6px 10px;"
            "background: rgba(20,20,20,170); border:1px solid rgba(120,120,120,120); border-radius:8px;"
        )
        nas_layout.addWidget(self.lbl_nas_status)

        nas_actions = QHBoxLayout()
        self.btn_nas_refresh = QPushButton("Detect NAS Shares")
        self.btn_nas_test = QPushButton("Test Selected NAS")
        self.btn_nas_save = QPushButton("Set As Business Vault")
        self.btn_nas_initialize = QPushButton("Initialize Vault")

        for b in (
            self.btn_nas_refresh,
            self.btn_nas_test,
            self.btn_nas_save,
            self.btn_nas_initialize,
        ):
            b.setMinimumHeight(36)
            nas_actions.addWidget(b)

        nas_actions.addStretch()
        nas_layout.addLayout(nas_actions)

        nas_detected_title = QLabel("Detected NAS Shares")
        nas_detected_title.setStyleSheet("font-size:18px;font-weight:700;padding-top:8px;")
        nas_layout.addWidget(nas_detected_title)

        self.lst_nas_candidates = QListWidget()
        nas_layout.addWidget(self.lst_nas_candidates, 1)

        nas_manual_title = QLabel("Manual UNC Entry")
        nas_manual_title.setStyleSheet("font-size:18px;font-weight:700;padding-top:8px;")
        nas_layout.addWidget(nas_manual_title)

        self.txt_nas_manual = QLineEdit()
        self.txt_nas_manual.setPlaceholderText(r"Example: \SERVER\Share")
        nas_layout.addWidget(self.txt_nas_manual)

        nas_manual_actions = QHBoxLayout()
        self.btn_nas_test_manual = QPushButton("Test Manual UNC")
        self.btn_nas_save_manual = QPushButton("Save Manual UNC")
        self.btn_nas_login = QPushButton("NAS Login")

        for b in (
            self.btn_nas_test_manual,
            self.btn_nas_save_manual,
            self.btn_nas_login,
        ):
            b.setMinimumHeight(36)
            nas_manual_actions.addWidget(b)

        nas_manual_actions.addStretch()
        nas_layout.addLayout(nas_manual_actions)

        self.nas_status_report = QPlainTextEdit()
        self.nas_status_report.setReadOnly(True)
        self.nas_status_report.setPlainText("Ready.")
        nas_layout.addWidget(self.nas_status_report, 1)

        signout_row = QHBoxLayout()
        signout_row.addStretch()
        self.btn_signout_nas = QPushButton("Sign Out Business Session")
        self.btn_signout_nas.setMinimumHeight(36)
        signout_row.addWidget(self.btn_signout_nas)
        nas_layout.addLayout(signout_row)

        self.surface.addWidget(self.nas_widget)

        self.fleet_widget = QWidget()
        fleet_layout = QVBoxLayout(self.fleet_widget)

        fleet_title = QLabel("Fleet Health Summary")
        fleet_title.setStyleSheet("font-size:22px;font-weight:700;")
        fleet_layout.addWidget(fleet_title)

        self.fleet_report = QTextEdit()
        self.fleet_report.setReadOnly(True)
        self.fleet_report.setPlainText("Loading...")
        fleet_layout.addWidget(self.fleet_report, 1)
        fleet_layout.addLayout(
            self._build_business_export_bar(
                self.fleet_report,
                default_name="devvault_business_fleet_health_summary_report",
                title="Fleet Health Summary",
            )
        )

        signout_row = QHBoxLayout()
        signout_row.addStretch()
        self.btn_signout_fleet = QPushButton("Sign Out Business Session")
        self.btn_signout_fleet.setMinimumHeight(36)
        signout_row.addWidget(self.btn_signout_fleet)
        fleet_layout.addLayout(signout_row)

        self.surface.addWidget(self.fleet_widget)

        self.org_widget = QWidget()
        org_layout = QVBoxLayout(self.org_widget)

        org_title = QLabel("Organization Recovery Audit")
        org_title.setStyleSheet("font-size:22px;font-weight:700;")
        org_layout.addWidget(org_title)

        self.org_report = QTextEdit()
        self.org_report.setReadOnly(True)
        self.org_report.setPlainText("Loading...")
        org_layout.addWidget(self.org_report, 1)
        org_layout.addLayout(
            self._build_business_export_bar(
                self.org_report,
                default_name="devvault_business_org_recovery_audit_report",
                title="Business Org Recovery Audit",
            )
        )

        signout_row = QHBoxLayout()
        signout_row.addStretch()
        self.btn_signout_org = QPushButton("Sign Out Business Session")
        self.btn_signout_org.setMinimumHeight(36)
        signout_row.addWidget(self.btn_signout_org)
        org_layout.addLayout(signout_row)

        self.surface.addWidget(self.org_widget)

        self.vault_widget = QWidget()
        vault_layout = QVBoxLayout(self.vault_widget)

        vault_title = QLabel("Vault Health Intelligence")
        vault_title.setStyleSheet("font-size:22px;font-weight:700;")
        vault_layout.addWidget(vault_title)

        self.vault_report = QTextEdit()
        self.vault_report.setReadOnly(True)
        self.vault_report.setPlainText("Loading...")
        vault_layout.addWidget(self.vault_report, 1)
        vault_layout.addLayout(
            self._build_business_export_bar(
                self.vault_report,
                default_name="devvault_business_vault_health_intelligence_report",
                title="Vault Health Intelligence",
            )
        )

        signout_row = QHBoxLayout()
        signout_row.addStretch()
        self.btn_signout_vault = QPushButton("Sign Out Business Session")
        self.btn_signout_vault.setMinimumHeight(36)
        signout_row.addWidget(self.btn_signout_vault)
        vault_layout.addLayout(signout_row)

        self.surface.addWidget(self.vault_widget)

        self.admin_widget = QWidget()
        admin_layout = QVBoxLayout(self.admin_widget)

        admin_title = QLabel("Administrative Visibility")
        admin_title.setStyleSheet("font-size:22px;font-weight:700;")
        admin_layout.addWidget(admin_title)

        admin_subtitle = QLabel(
            "Review live administrative visibility and owner/admin recovery actions.",
        )
        admin_subtitle.setWordWrap(True)
        admin_subtitle.setStyleSheet("color:#b8b8b8;")
        admin_layout.addWidget(admin_subtitle)

        admin_actions = QHBoxLayout()
        self.btn_admin_live_view = QPushButton("Live View")
        self.btn_issue_admin_login_token = QPushButton("Issue Login Token")

        for b in (
            self.btn_admin_live_view,
            self.btn_issue_admin_login_token,
        ):
            b.setMinimumHeight(36)
            admin_actions.addWidget(b)

        admin_actions.addStretch()
        admin_layout.addLayout(admin_actions)

        self.lbl_admin_mode = QLabel("Mode: Live Administrative Visibility")
        self.lbl_admin_mode.setStyleSheet("color:#8fd3ff;padding:4px 0 6px 0;")
        admin_layout.addWidget(self.lbl_admin_mode)

        self.admin_report = QTextEdit()
        self.admin_report.setReadOnly(True)
        self.admin_report.setPlainText("Loading...")
        admin_layout.addWidget(self.admin_report, 1)
        admin_layout.addLayout(
            self._build_business_export_bar(
                self.admin_report,
                default_name="devvault_business_administrative_visibility_report",
                title="Administrative Visibility",
            )
        )

        signout_row = QHBoxLayout()
        signout_row.addStretch()
        self.btn_signout_admin = QPushButton("Sign Out Business Session")
        self.btn_signout_admin.setMinimumHeight(36)
        signout_row.addWidget(self.btn_signout_admin)
        admin_layout.addLayout(signout_row)

        self.surface.addWidget(self.admin_widget)

        self.history_widget = QWidget()
        history_layout = QVBoxLayout(self.history_widget)

        history_title = QLabel("Historical Records")
        history_title.setStyleSheet("font-size:22px;font-weight:700;")
        history_layout.addWidget(history_title)

        history_subtitle = QLabel(
            "Review historical Business seat and invite records without mixing them into live admin control flow."
        )
        history_subtitle.setWordWrap(True)
        history_subtitle.setStyleSheet("color:#b8b8b8;")
        history_layout.addWidget(history_subtitle)

        history_actions = QHBoxLayout()
        self.btn_view_historical_seats = QPushButton("Historical Seats")
        self.btn_view_historical_invites = QPushButton("Historical Invites")

        for b in (
            self.btn_view_historical_seats,
            self.btn_view_historical_invites,
        ):
            b.setMinimumHeight(36)
            history_actions.addWidget(b)

        history_actions.addStretch()
        history_layout.addLayout(history_actions)

        self.lbl_history_mode = QLabel("Mode: Historical Seat Records")
        self.lbl_history_mode.setStyleSheet("color:#8fd3ff;padding:4px 0 6px 0;")
        history_layout.addWidget(self.lbl_history_mode)

        self.history_report = QTextEdit()
        self.history_report.setReadOnly(True)
        self.history_report.setPlainText("Loading...")
        history_layout.addWidget(self.history_report, 1)

        signout_row = QHBoxLayout()
        signout_row.addStretch()
        self.btn_signout_history = QPushButton("Sign Out Business Session")
        self.btn_signout_history.setMinimumHeight(36)
        signout_row.addWidget(self.btn_signout_history)
        history_layout.addLayout(signout_row)

        self.surface.addWidget(self.history_widget)

        self.btn_dashboard.clicked.connect(
            lambda: (
                self._refresh_business_dashboard(),
                self.surface.setCurrentWidget(self.dashboard_widget)
            )
        )
        self.btn_org.clicked.connect(
            lambda: (
                self.org_report.setPlainText(self.parent()._build_business_org_recovery_audit_report_text()),
                self.surface.setCurrentWidget(self.org_widget)
            )
        )
        self.btn_seats.clicked.connect(
            lambda: (
                self._refresh_readiness_surface(),
                self.surface.setCurrentWidget(self.seat_widget)
            )
        )
        self.btn_seat_mgmt.clicked.connect(
            lambda: (
                self._refresh_seat_management_surface(),
                self.surface.setCurrentWidget(self.seat_mgmt_widget)
            )
        )
        self.btn_invites.clicked.connect(
            lambda: (
                self._refresh_invite_management_surface(),
                self.surface.setCurrentWidget(self.invite_widget)
            )
        )
        self.btn_refresh_readiness.clicked.connect(self._refresh_readiness_surface)
        self.btn_refresh_seat_mgmt.clicked.connect(self._on_refresh_seat_management_clicked)
        self.btn_refresh_invites.clicked.connect(self._on_refresh_invites_clicked)
        self.btn_nas_config.clicked.connect(
            lambda: (
                self._refresh_business_nas_surface(),
                self._auto_refresh_nas_state(),
                self.surface.setCurrentWidget(self.nas_widget)
            )
        )
        self.btn_nas_refresh.clicked.connect(self._refresh_business_nas_surface)
        self.btn_nas_test.clicked.connect(self._test_selected_business_nas_candidate)
        self.btn_nas_save.clicked.connect(self._save_selected_business_nas_candidate)
        self.btn_nas_test_manual.clicked.connect(self._test_manual_business_nas_candidate)
        self.btn_nas_save_manual.clicked.connect(self._save_manual_business_nas_candidate)
        self.btn_nas_login.clicked.connect(self._login_business_nas_credentials)
        self.btn_nas_initialize.clicked.connect(self.parent()._initialize_business_nas_vault)
        self.btn_add_manual_seat.clicked.connect(self._enroll_seat_from_dialog)
        self.btn_create_invite.clicked.connect(self._create_invite_from_dialog)
        self.btn_resend_invite.clicked.connect(self._resend_invite_from_dialog)
        self.btn_revoke_invite.clicked.connect(self._revoke_invite_from_dialog)
        self.btn_reassign_local_identity.clicked.connect(self._reset_or_reassign_local_seat_identity)
        self.btn_run_seat_health.clicked.connect(self._run_selected_seat_health_check)
        self.btn_remove_manual_seat.clicked.connect(self._revoke_seat_from_dialog)
        self.btn_admin_live_view.clicked.connect(self._show_admin_live_view)
        self.btn_view_historical_seats.clicked.connect(self._show_historical_seat_records)
        self.btn_view_historical_invites.clicked.connect(self._show_historical_invites)
        self.btn_issue_admin_login_token.clicked.connect(self._issue_admin_login_token_for_selected_seat)
        self.btn_history.clicked.connect(self._show_historical_seat_records)
        self.btn_view_attention_seats.clicked.connect(self._open_attention_seats_view)
        self.btn_business_console_sign_out.clicked.connect(self._sign_out_and_close_console)
        self.btn_signout_readiness.clicked.connect(self._sign_out_and_close_console)
        self.btn_signout_seat_mgmt.clicked.connect(self._sign_out_and_close_console)
        self.btn_signout_invites.clicked.connect(self._sign_out_and_close_console)
        self.btn_signout_nas.clicked.connect(self._sign_out_and_close_console)
        self.btn_signout_fleet.clicked.connect(self._sign_out_and_close_console)
        self.btn_signout_org.clicked.connect(self._sign_out_and_close_console)
        self.btn_signout_vault.clicked.connect(self._sign_out_and_close_console)
        self.btn_signout_admin.clicked.connect(self._sign_out_and_close_console)
        self.btn_signout_history.clicked.connect(self._sign_out_and_close_console)
        self.btn_fleet.clicked.connect(
            lambda: (
                self.fleet_report.setPlainText(self.parent()._build_business_fleet_health_summary_report_text()),
                self.surface.setCurrentWidget(self.fleet_widget)
            )
        )
        self.btn_vault.clicked.connect(
            lambda: (
                self.vault_report.setPlainText(self.parent()._build_business_vault_health_intelligence_report_text()),
                self.surface.setCurrentWidget(self.vault_widget)
            )
        )
        self.btn_admin.clicked.connect(self._show_admin_live_view)

        placeholder = QLabel("Select a Business tool.")
        placeholder.setAlignment(Qt.AlignCenter)
        self.surface.addWidget(placeholder)

        self._local_seat_identity_mismatch = False
        self._business_refresh_cooldowns = {}
        self._last_business_refresh_at = 0.0
        self._last_seat_health_selection = ""
        self._business_nas_onboarding_prompted = False
        self._fit_to_available_screen()
        self.watermark.lower()

    
    def _fit_to_available_screen(self) -> None:
        try:
            screen = QGuiApplication.primaryScreen()
            if screen is None:
                return

            avail = screen.availableGeometry()
            width = max(820, min(1040, avail.width() - 40))
            height = max(520, min(700, avail.height() - 40))
            self.resize(width, height)

            geo = self.frameGeometry()
            geo.moveCenter(avail.center())
            self.move(geo.topLeft())
        except Exception:
            pass

    def _open_attention_seats_view(self):
        try:
            self.surface.setCurrentWidget(self.seat_mgmt_widget)
            self._seat_mgmt_filter_mode = "attention"
            self._refresh_seat_management_surface()
        except Exception:
            pass

    def _sign_out_and_close_console(self) -> None:
        try:
            self.parent()._business_admin_sign_out()
        except Exception:
            pass
        try:
            super().reject()
        except Exception:
            self.close()

    def reject(self) -> None:
        return

    def keyPressEvent(self, event) -> None:
        try:
            if event.key() == Qt.Key_Escape:
                event.ignore()
                return
        except Exception:
            pass
        super().keyPressEvent(event)

    def _set_nas_status(self, lines: list[str]) -> None:
        try:
            self.nas_status_report.setPlainText("\n".join(lines))
        except Exception:
            pass

    def _set_nas_banner(self, status: str, detail: str = "") -> None:
        normalized = str(status or "").strip().upper() or "UNKNOWN"
        if normalized == "VALIDATED":
            color = "#52d273"
        elif normalized in ("UNREACHABLE", "PERMISSION FAILURE"):
            color = "#ff8a8a"
        elif normalized == "NOT CONFIGURED":
            color = "#f5c400"
        else:
            color = "#ffd84d"

        text = f"STATUS: {normalized}"
        if detail:
            text += f" — {detail}"

        self.lbl_nas_status.setText(text)
        self.lbl_nas_status.setStyleSheet(
            f"font-size:14px;font-weight:700;color:{color};padding:6px 10px;"
            "background: rgba(20,20,20,170); border:1px solid rgba(120,120,120,120); border-radius:8px;"
        )

    def _refresh_business_nas_surface(self) -> None:
        current = ""
        try:
            current = get_business_nas_path()
        except Exception:
            current = ""

        current_display = current.strip() if str(current or "").strip() else "Not configured"
        self.lbl_nas_current.setText(f"Current Business NAS: {current_display}")

        candidates = []
        try:
            candidates = list(self.parent()._available_business_nas_roots())
        except Exception:
            candidates = []

        self.lst_nas_candidates.clear()
        for item in candidates:
            self.lst_nas_candidates.addItem(item)

        if current and current in candidates:
            for i in range(self.lst_nas_candidates.count()):
                if self.lst_nas_candidates.item(i).text().strip() == current:
                    self.lst_nas_candidates.setCurrentRow(i)
                    break
        elif candidates:
            self.lst_nas_candidates.setCurrentRow(0)

        if current:
            self._set_nas_banner("VALIDATED", "Saved NAS target present")
        else:
            self._set_nas_banner("NOT CONFIGURED", "No Business NAS is saved")

        self._set_nas_status([
            "Business NAS Configuration",
            f"Current: {current_display}",
            f"Detected Shares: {len(candidates)}",
            "Use Detect / Test / Set to manage the authoritative Business NAS target.",
        ])

    def _business_nas_write_probe(self, candidate: str) -> tuple[bool, str]:
        try:
            root = Path(candidate)
            probe = root / f".dv_probe_{uuid.uuid4().hex}.tmp"
            probe.write_text("devvault nas probe", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True, "Write probe OK."
        except PermissionError:
            return False, "Business NAS vault permission denied. Verify share access rights."
        except Exception as e:
            return False, str(e)

    def _business_nas_probe(self, raw_path: str) -> tuple[bool, str, str]:
        candidate = ""
        try:
            candidate = self.parent()._normalize_business_nas_root(raw_path)
        except Exception:
            candidate = ""

        if not candidate:
            return False, "NOT CONFIGURED", "Invalid UNC NAS path."

        try:
            from devvault_desktop.nas_enforcement import enforce_business_nas_requirement
            enforce_business_nas_requirement(
                license_kind="business",
                nas_path=candidate,
            )
        except Exception as e:
            msg = str(e)
            if "permission" in msg.lower():
                return False, "PERMISSION FAILURE", msg
            if "unreachable" in msg.lower() or "offline" in msg.lower():
                return False, "UNREACHABLE", msg
            return False, "NOT CONFIGURED", msg

        ok, write_msg = self._business_nas_write_probe(candidate)
        if not ok:
            if "permission" in write_msg.lower():
                return False, "PERMISSION FAILURE", write_msg
            return False, "UNREACHABLE", write_msg

        return True, "VALIDATED", f"Connection OK: {candidate}\n{write_msg}"

    def _auto_refresh_nas_state(self) -> None:
        self._refresh_business_nas_surface()
        current = ""
        try:
            current = get_business_nas_path()
        except Exception:
            current = ""

        if not current:
            self._set_nas_banner("NOT CONFIGURED", "No Business NAS is saved")
            return

        ok, status, msg = self._business_nas_probe(current)
        self._set_nas_banner(status, "" if status == "VALIDATED" else "Action required")
        self._set_nas_status([
            "Business NAS Configuration",
            f"Current: {current}",
            f"Health: {status}",
            msg,
        ])

    def _business_nas_onboarding_required(self) -> bool:
        try:
            parent = self.parent()
        except Exception:
            parent = None

        business_mode = False

        try:
            if parent is not None and hasattr(parent, "_business_nas_mode_active"):
                business_mode = bool(parent._business_nas_mode_active())
        except Exception:
            business_mode = False

        if not business_mode:
            try:
                business_mode = bool(get_business_seat_identity())
            except Exception:
                business_mode = False

        if not business_mode:
            return False

        try:
            current_nas = str(get_business_nas_path() or "").strip()
        except Exception:
            current_nas = ""

        return not bool(current_nas)

    def _maybe_force_business_nas_onboarding(self, *, reason: str = "", prompt_once: bool = True) -> None:
        if not self._business_nas_onboarding_required():
            self._business_nas_onboarding_prompted = False
            return

        self._refresh_business_nas_surface()
        self._auto_refresh_nas_state()
        self.surface.setCurrentWidget(self.nas_widget)

        if prompt_once and getattr(self, "_business_nas_onboarding_prompted", False):
            return

        self._business_nas_onboarding_prompted = True

        msg = (
            "Business NAS setup is required before Business backup can run.\n\n"
            "Open the Business NAS Configuration screen and set a valid UNC NAS target now."
        )
        if reason:
            msg += f"\n\nReason: {reason}"

        _centered_message(
            self,
            "Business NAS Setup Required",
            msg,
            QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Ok,
            QMessageBox.Icon.Warning,
        )

    def _test_selected_business_nas_candidate(self) -> None:
        item = self.lst_nas_candidates.currentItem()
        if item is None:
            self._set_nas_banner("NOT CONFIGURED", "No selection")
            self._set_nas_status(["No NAS share selected."])
            return

        candidate = item.text().strip()
        ok, status, msg = self._business_nas_probe(candidate)
        self._set_nas_banner(status, "" if ok else "Action required")
        self._set_nas_status([
            f"Selected: {candidate}",
            f"Result: {'OK' if ok else 'FAILED'}",
            msg,
        ])

    def _save_selected_business_nas_candidate(self) -> None:
        item = self.lst_nas_candidates.currentItem()
        if item is None:
            self._set_nas_banner("NOT CONFIGURED", "No selection")
            self._set_nas_status(["No NAS share selected."])
            return

        candidate = item.text().strip()
        ok, status, msg = self._business_nas_probe(candidate)
        if not ok:
            self._set_nas_banner(status, "Save blocked")
            self._set_nas_status([
                f"Selected: {candidate}",
                "Result: FAILED",
                msg,
            ])
            return

        set_business_nas_path(candidate)
        try:
            self.parent().vault_path = candidate
            self.parent().update_vault_display()
        except Exception:
            pass

        self._business_nas_onboarding_prompted = False
        self._refresh_business_nas_surface()
        self._set_nas_banner("VALIDATED", "Saved")
        self._set_nas_status([
            f"Selected: {candidate}",
            "Result: SAVED",
            "Business NAS target updated successfully.",
        ])
        self._force_restart_for_runtime_refresh(
            "Business NAS target updated successfully. DevVault will now restart to refresh vault authority and runtime state."
        )

    def _test_manual_business_nas_candidate(self) -> None:
        candidate = self.txt_nas_manual.text().strip()
        ok, status, msg = self._business_nas_probe(candidate)
        self._set_nas_banner(status, "" if ok else "Action required")
        self._set_nas_status([
            f"Manual UNC: {candidate or '(empty)'}",
            f"Result: {'OK' if ok else 'FAILED'}",
            msg,
        ])

    def _save_manual_business_nas_candidate(self) -> None:
        candidate = self.txt_nas_manual.text().strip()
        ok, status, msg = self._business_nas_probe(candidate)
        if not ok:
            self._set_nas_banner(status, "Save blocked")
            self._set_nas_status([
                f"Manual UNC: {candidate or '(empty)'}",
                "Result: FAILED",
                msg,
            ])
            return

        set_business_nas_path(candidate)
        try:
            self.parent().vault_path = candidate
            self.parent().update_vault_display()
        except Exception:
            pass

        self._business_nas_onboarding_prompted = False
        self._refresh_business_nas_surface()
        self._set_nas_banner("VALIDATED", "Saved")
        self._set_nas_status([
            f"Manual UNC: {candidate}",
            "Result: SAVED",
            "Business NAS target updated successfully.",
        ])
        self._force_restart_for_runtime_refresh(
            "Business NAS target updated successfully. DevVault will now restart to refresh vault authority and runtime state."
        )


    def _login_business_nas_credentials(self) -> None:
        candidate = self.txt_nas_manual.text().strip()

        if not candidate:
            self._set_nas_banner("NOT CONFIGURED", "Login blocked")
            self._set_nas_status([
                "Manual UNC: (empty)",
                "Result: FAILED",
                "Enter a UNC path first.",
            ])
            return

        username, ok = QInputDialog.getText(self, "NAS Login", "Username:")
        if not ok or not username.strip():
            return

        password, ok = QInputDialog.getText(
            self,
            "NAS Login",
            "Password:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not password:
            return

        ok, msg = save_windows_nas_credentials(candidate, username, password)
        probe_ok, status, probe_msg = self._business_nas_probe(candidate)

        self._set_nas_banner("AUTH OK" if probe_ok else status, "Saved" if probe_ok else "Action required")
        self._set_nas_status([
            f"UNC: {candidate}",
            f"Cred Save: {'OK' if ok else 'FAILED'}",
            msg,
            f"Probe: {'OK' if probe_ok else 'FAILED'}",
            probe_msg,
        ])

        if probe_ok:
            self.txt_nas_manual.setText(candidate)
    def _build_historical_seat_records_text(self) -> str:
        try:
            subscription_id = self._business_subscription_id()
            api_payload = list_business_seats(subscription_id)
            rows = normalize_business_seat_rows(api_payload)
        except Exception as e:
            return f"Failed to load historical seat records.\n\n{e}"

        active_statuses = {"active", "enrolled", "assigned"}

        historical_rows = [
            row
            for row in rows
            if str(row.seat_status or "").strip().lower() not in active_statuses
        ]

        lines = [
            "DEVVAULT BUSINESS HISTORICAL SEAT RECORDS",
            "=========================================",
            "",
            f"Historical Records: {len(historical_rows)}",
            "",
        ]

        if not historical_rows:
            lines.append("No historical seat records found.")
            return "\n".join(lines)

        for row in historical_rows:
            lines.extend(
                [
                    f"Seat ID: {row.seat_id or 'n/a'}",
                    f"Status: {row.seat_status or 'n/a'}",
                    f"Role: {getattr(row, 'seat_role', '') or 'n/a'}",
                    f"Assigned Email: {row.assigned_email or 'n/a'}",
                    f"Assigned Device ID: {row.assigned_device_id or 'n/a'}",
                    f"Assigned Hostname: {row.assigned_hostname or 'n/a'}",
                    f"Seat Label: {row.seat_label or 'n/a'}",
                    f"Created At: {row.created_at or 'n/a'}",
                    f"Revoked At: {row.revoked_at or 'n/a'}",
                    "-" * 48,
                ]
            )

        return "\n".join(lines)

    def _build_historical_invites_text(self) -> str:
        try:
            subscription_id = self._business_subscription_id()
            seat_payload = list_business_seats(subscription_id)
            seat_rows = normalize_business_seat_rows(seat_payload)
            fleet_id, inviter_seat_id, inviter_role = self._resolve_local_inviter_context(
                seat_payload,
                seat_rows,
            )
            invite_payload = list_business_invites(
                fleet_id=fleet_id,
                inviter_seat_id=inviter_seat_id,
                inviter_role=inviter_role,
            )
            invite_rows = normalize_business_invite_rows(invite_payload)
        except Exception as e:
            return f"Failed to load historical invites.\n\n{e}"

        historical_rows = [
            row
            for row in invite_rows
            if str(row.effective_status or '').strip().lower() != "pending"
        ]

        lines = [
            "DEVVAULT BUSINESS HISTORICAL INVITES",
            "====================================",
            "",
            f"Historical Invites: {len(historical_rows)}",
            "",
        ]

        if not historical_rows:
            lines.append("No historical invites found.")
            return "\n".join(lines)

        for row in historical_rows:
            lines.extend(
                [
                    f"Token ID: {row.token_id or 'n/a'}",
                    f"Status: {row.status or 'n/a'}",
                    f"Effective Status: {row.effective_status or 'n/a'}",
                    f"Invited Role: {row.invited_role or 'n/a'}",
                    f"Invitee Email: {row.invitee_email or 'n/a'}",
                    f"Inviter Seat ID: {row.inviter_seat_id or 'n/a'}",
                    f"Inviter Role: {row.inviter_role or 'n/a'}",
                    f"Created At: {row.created_at or 'n/a'}",
                    f"Expires At: {row.expires_at or 'n/a'}",
                    f"Consumed At: {row.consumed_at or 'n/a'}",
                    f"Revoked At: {row.revoked_at or 'n/a'}",
                    "-" * 48,
                ]
            )

        return "\n".join(lines)

    def _show_text_report_dialog(self, title_text: str, report_text: str) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(title_text)
        dlg.setModal(True)
        dlg.setMinimumWidth(860)
        dlg.setMinimumHeight(520)
        dlg.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(title_text, dlg)
        title.setWordWrap(True)
        root.addWidget(title)

        details = QTextEdit(dlg)
        details.setReadOnly(True)
        details.setPlainText(report_text)
        root.addWidget(details, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_close = QPushButton("Close", dlg)
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)

        root.addLayout(btn_row)
        dlg.exec()

    def _show_historical_seat_records(self) -> None:
        try:
            self.history_report.setPlainText(
                self._build_historical_seat_records_text()
            )
            self._set_history_mode_text("Historical Seat Records")
            self.surface.setCurrentWidget(self.history_widget)
        except Exception as e:
            self.history_report.setPlainText(
                "Failed to load Historical Seat Records.\n\n"
                f"{e}"
            )
            self._set_history_mode_text("Historical Seat Records (Error)")

    def _show_historical_invites(self) -> None:
        try:
            self.history_report.setPlainText(
                self._build_historical_invites_text()
            )
            self._set_history_mode_text("Historical Invites")
            self.surface.setCurrentWidget(self.history_widget)
        except Exception as e:
            self.history_report.setPlainText(
                "Failed to load Historical Invites.\n\n"
                f"{e}"
            )
            self._set_history_mode_text("Historical Invites (Error)")

    def _business_refresh_allowed(self, key: str, *, cooldown_seconds: float = 1.75) -> bool:
        import time

        now = time.monotonic()

        last_any = float(getattr(self, "_last_business_refresh_at", 0.0) or 0.0)
        if now - last_any < cooldown_seconds:
            return False

        state = getattr(self, "_business_refresh_cooldowns", None)
        if not isinstance(state, dict):
            state = {}
            self._business_refresh_cooldowns = state

        last = float(state.get(key, 0.0) or 0.0)
        if now - last < cooldown_seconds:
            return False

        state[key] = now
        self._last_business_refresh_at = now
        return True

    def _business_disable_button_temporarily(self, button, *, delay_ms: int = 1750) -> None:
        try:
            button.setEnabled(False)
            QTimer.singleShot(delay_ms, lambda: button.setEnabled(True))
        except Exception:
            pass

    def _on_refresh_dashboard_clicked(self) -> None:
        if not self._business_refresh_allowed("dashboard_refresh"):
            return
        self._business_disable_button_temporarily(self.btn_refresh_dashboard)
        self._refresh_business_dashboard()

    def _on_refresh_seat_management_clicked(self) -> None:
        if not self._business_refresh_allowed("seat_management_refresh"):
            return
        self._business_disable_button_temporarily(self.btn_refresh_seat_mgmt)
        self._refresh_seat_management_surface()

    def _on_refresh_invites_clicked(self) -> None:
        if not self._business_refresh_allowed("invite_refresh"):
            return
        self._business_disable_button_temporarily(self.btn_refresh_invites)
        self._refresh_invite_management_surface()

    def _preferred_seat_health_default_index(self, seat_choices: list[tuple[str, str]]) -> int:
        if not seat_choices:
            return 0

        last_selected = str(getattr(self, "_last_seat_health_selection", "") or "").strip()
        if last_selected:
            for idx, (_, seat_id) in enumerate(seat_choices):
                if str(seat_id).strip() == last_selected:
                    return idx

        try:
            identity = get_business_seat_identity()
        except Exception:
            identity = None

        local_seat_id = ""
        if isinstance(identity, dict):
            local_seat_id = str(identity.get("seat_id") or "").strip()

        if local_seat_id:
            for idx, (_, seat_id) in enumerate(seat_choices):
                if str(seat_id).strip() == local_seat_id:
                    return idx

        return 0

    def _set_admin_mode_text(self, value: str) -> None:
        try:
            self.lbl_admin_mode.setText(f"Mode: {value}")
        except Exception:
            pass

    def _set_history_mode_text(self, value: str) -> None:
        try:
            self.lbl_history_mode.setText(f"Mode: {value}")
        except Exception:
            pass

    def _show_admin_live_view(self) -> None:
        try:
            self.surface.setCurrentWidget(self.admin_widget)
        except Exception:
            pass

        try:
            self.admin_report.setPlainText(
                self.parent()._build_business_administrative_visibility_report_text()
            )
            self._set_admin_mode_text("Live Administrative Visibility")
        except Exception as e:
            try:
                self.admin_report.setPlainText(
                    "Failed to load Administrative Visibility.\n\n"
                    f"{e}"
                )
            except Exception:
                pass
            try:
                self._set_admin_mode_text("Live Administrative Visibility (Error)")
            except Exception:
                pass
            try:
                self.parent().append_log(
                    f"Administrative Visibility load failed: {e}"
                )
            except Exception:
                pass

    def _fit_to_available_screen(self) -> None:
        try:
            target = self.parent() if self.parent() is not None else self
        except Exception:
            target = self

        screen = None
        try:
            wh = target.windowHandle()
            if wh is not None:
                screen = wh.screen()
        except Exception:
            screen = None

        if screen is None:
            try:
                screen = QGuiApplication.screenAt(QCursor.pos())
            except Exception:
                screen = None

        if screen is None:
            try:
                screen = QGuiApplication.primaryScreen()
            except Exception:
                screen = None

        if screen is None:
            return

        try:
            avail = screen.availableGeometry()
            width = max(820, min(1040, avail.width() - 40))
            height = max(520, min(700, avail.height() - 40))
            self.resize(width, height)

            widget_geo = self.frameGeometry()
            widget_geo.moveCenter(avail.center())
            self.move(widget_geo.topLeft())
        except Exception:
            pass

    def _business_card_style(self, color: str, *, border_width: int = 2) -> str:
        return (
            "font-size:18px;"
            "padding:16px;"
            "background-color:#0b0b0b;"
            "border-radius:8px;"
            "min-height:72px;"
            f"color:{color};"
            f"border:{border_width}px solid {color};"
        )



    def _build_seat_status_summary_text(
        self,
        *,
        seat_id: str,
        seat_label: str = "",
        assigned_hostname: str = "",
        banner_status: str = "",
        banner_message: str = "",
    ) -> str:
        seat_id = str(seat_id or "").strip()
        seat_label = str(seat_label or "").strip()
        assigned_hostname = str(assigned_hostname or "").strip()

        last_backup_at = ""
        seat_state = "unknown"

        if seat_id:
            try:
                import json
                from datetime import datetime, timezone

                nas_path = str(get_business_nas_path() or "").strip()
                if nas_path:
                    index_path = Path(nas_path) / ".devvault" / "snapshot_index.json"
                    latest = None

                    if index_path.exists():
                        raw = json.loads(index_path.read_text(encoding="utf-8"))
                        for row in raw.get("snapshots", []) or []:
                            if not isinstance(row, dict):
                                continue

                            row_seat_id = str(row.get("seat_id") or "").strip()
                            if row_seat_id != seat_id:
                                continue

                            created_at = str(row.get("created_at") or "").strip()
                            if latest is None:
                                latest = row
                                continue

                            prev_created = str(latest.get("created_at") or "").strip()
                            if created_at > prev_created:
                                latest = row

                    if latest is None:
                        seat_state = "never_backed_up"
                    else:
                        last_backup_at = str(latest.get("created_at") or "").strip()
                        seat_state = "protected"
                        try:
                            created_dt = datetime.fromisoformat(last_backup_at)
                            if created_dt.tzinfo is None:
                                created_dt = created_dt.replace(tzinfo=timezone.utc)
                            age_seconds = (datetime.now(timezone.utc) - created_dt).total_seconds()
                            if age_seconds > (72 * 3600):
                                seat_state = "needs_backup"
                        except Exception:
                            seat_state = "protected"
            except Exception:
                seat_state = "unknown"

        if seat_state == "protected":
            state_text = "Protected"
        elif seat_state == "needs_backup":
            state_text = "Needs backup"
        elif seat_state == "never_backed_up":
            state_text = "Never backed up"
        else:
            state_text = "Unknown"

        lines = [
            "THIS SEAT / PC STATUS",
            "=====================",
        ]

        if str(banner_status or "").strip():
            lines.append(f"Main Banner: {str(banner_status).strip()}")
            if str(banner_message or "").strip():
                lines.append(str(banner_message).strip())
        else:
            lines.append(f"NAS Status: {state_text}")

        if seat_label:
            lines.append(f"Seat: {seat_label}")
        if assigned_hostname:
            lines.append(f"Host: {assigned_hostname}")
        if seat_id:
            lines.append(f"Seat ID: {seat_id}")
        if last_backup_at:
            lines.append(f"Last NAS Backup: {last_backup_at}")

        return "\n".join(lines)



    def _dashboard_status_for_seat(
        self,
        *,
        seat_id: str,
        seat_label: str = "",
        assigned_hostname: str = "",
        latest_snapshot_at: str = "",
        nas_reachable: bool,
    ) -> str:
        seat_id = str(seat_id or "").strip()
        seat_label = str(seat_label or "").strip()
        assigned_hostname = str(assigned_hostname or "").strip()
        latest_snapshot_at = str(latest_snapshot_at or "").strip()

        if not nas_reachable:
            return "Unreachable"

        try:
            local_identity = get_business_seat_identity()
        except Exception:
            local_identity = None

        local_seat_id = ""
        if isinstance(local_identity, dict):
            local_seat_id = str(local_identity.get("seat_id") or "").strip()

        if local_seat_id and seat_id == local_seat_id:
            try:
                banner = str(self.parent().protection_status_label.text() or "").strip().upper()
            except Exception:
                banner = ""

            if "UNPROTECTED" in banner:
                try:
                    msg = str(self.parent().protection_status_message.text() or "").strip()
                except Exception:
                    msg = ""
                return f"Unprotected — {msg}" if msg else "Unprotected"

            if "PROTECTED" in banner:
                return "Protected"

        if not latest_snapshot_at:
            return "Never backed up"

        try:
            from datetime import datetime, timezone
            created_dt = datetime.fromisoformat(latest_snapshot_at)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            age_seconds = (datetime.now(timezone.utc) - created_dt).total_seconds()
            if age_seconds > (72 * 3600):
                return "Unprotected"
        except Exception:
            pass

        return "Protected"

    def _refresh_dashboard_seat_status_board(self) -> None:
        try:
            subscription_id = self._business_subscription_id()
            seat_payload = list_business_seats(subscription_id)
            rows = normalize_business_seat_rows(seat_payload)
        except Exception as e:
            self.seat_status_board.setPlainText(
                "SEAT STATUS OVERVIEW\n====================\n\nFailed to load seat status.\n\n" + str(e)
            )
            return

        active_statuses = {"active", "enrolled", "assigned"}

        active_rows = [
            row for row in rows
            if str(getattr(row, "seat_status", "") or "").strip().lower() in active_statuses
        ]

        try:
            nas_path = str(get_business_nas_path() or "").strip()
        except Exception:
            nas_path = ""

        nas_reachable = False
        if nas_path:
            try:
                nas_reachable = Path(nas_path).exists()
            except Exception:
                nas_reachable = False

        latest_by_seat = {}
        if nas_reachable:
            try:
                import json
                index_path = Path(nas_path) / ".devvault" / "snapshot_index.json"
                if index_path.exists():
                    raw = json.loads(index_path.read_text(encoding="utf-8"))
                    for row in raw.get("snapshots", []) or []:
                        if not isinstance(row, dict):
                            continue
                        seat_id = str(row.get("seat_id") or "").strip()
                        created_at = str(row.get("created_at") or "").strip()
                        if not seat_id:
                            continue
                        prev = latest_by_seat.get(seat_id, "")
                        if created_at > prev:
                            latest_by_seat[seat_id] = created_at
            except Exception:
                pass

        lines = [
            "SEAT STATUS OVERVIEW",
            "====================",
            "",
        ]

        if not active_rows:
            lines.append("No active seats found.")
        else:
            for row in active_rows:
                seat_id = str(getattr(row, "seat_id", "") or "").strip()
                seat_label = str(getattr(row, "seat_label", "") or "").strip()
                hostname = str(getattr(row, "assigned_hostname", "") or "").strip()
                latest_snapshot_at = str(latest_by_seat.get(seat_id, "") or "").strip()

                status = self._dashboard_status_for_seat(
                    seat_id=seat_id,
                    seat_label=seat_label,
                    assigned_hostname=hostname,
                    latest_snapshot_at=latest_snapshot_at,
                    nas_reachable=nas_reachable,
                )

                left = seat_label or seat_id or "Unknown Seat"
                if hostname:
                    left += f" ({hostname})"

                lines.append(f"{left} - {status}")

        self.seat_status_board.setPlainText("\n".join(lines))

    def _refresh_business_surfaces(self) -> None:
        try:
            current = self.surface.currentWidget()
        except Exception:
            current = None

        try:
            if current is self.dashboard_widget:
                self._refresh_business_dashboard()
            elif current is self.seat_widget:
                self._refresh_readiness_surface()
            elif current is self.org_widget:
                self.org_report.setPlainText(
                    self.parent()._build_business_org_recovery_audit_report_text()
                )
            elif current is self.fleet_widget:
                self.fleet_report.setPlainText(
                    self.parent()._build_business_fleet_health_summary_report_text()
                )
            elif current is self.vault_widget:
                self.vault_report.setPlainText(
                    self.parent()._build_business_vault_health_intelligence_report_text()
                )
            elif current is self.admin_widget:
                self.admin_report.setPlainText(
                    self.parent()._build_business_administrative_visibility_report_text()
                )
            elif current is self.seat_mgmt_widget:
                self._refresh_seat_management_surface()
            else:
                self._refresh_business_dashboard()
        except Exception:
            pass

    def _refresh_business_dashboard(self) -> None:
        from datetime import datetime
        import shutil

        snapshot = self.parent()._dashboard_snapshot()

        try:
            self.lbl_dashboard_refresh.setText(
                f"Last Refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        except Exception:
            pass

        def _safe_int(value, default=0):
            try:
                if value in (None, "", "?"):
                    return default
                return int(value)
            except Exception:
                return default

        protected_count = _safe_int(snapshot.get("seats_protected", 0), 0)
        total_count = _safe_int(snapshot.get("seats_total", 0), 0)
        risky_vaults = _safe_int(snapshot.get("risky_vaults", 0), 0)

        try:
            nas_path = str(get_business_nas_path() or "").strip()
        except Exception:
            nas_path = ""

        attention_count = max(total_count - protected_count, 0)

        try:
            self._attention_seat_ids = tuple(
                snapshot.get("attention_seats") or ()
            )
        except Exception:
            self._attention_seat_ids = ()
        if risky_vaults > attention_count:
            attention_count = risky_vaults

        seats_used = int(snapshot.get("active_seat_count", total_count) or 0)
        seat_limit = 0
        try:
            seat_limit = int(snapshot.get("seat_limit", 0) or 0)
        except Exception:
            seat_limit = 0

        if seat_limit <= 0:
            try:
                seat_limit = int(self.parent()._installed_business_seat_limit() or 0)
            except Exception:
                seat_limit = 0

        if seat_limit <= 0:
            seats_color = "#8a8a8a"
            seats_text = f"Seats Used\n{seats_used} used"
        elif seats_used < seat_limit:
            seats_color = "#52d273"
            seats_text = f"Seats Used\n{seats_used} of {seat_limit} used"
        elif seats_used == seat_limit:
            seats_color = "#f5c400"
            seats_text = f"Seats Used\n{seats_used} of {seat_limit} used"
        else:
            seats_color = "#ff8a8a"
            seats_text = f"Seats Used\n{seats_used} of {seat_limit} used"

        self.seats_used_card.setText(seats_text)
        self.seats_used_card.setStyleSheet(self._business_card_style(seats_color))

        if total_count <= 0:
            seats_protected_color = "#8a8a8a"
        elif protected_count == total_count:
            seats_protected_color = "#52d273"
        else:
            seats_protected_color = "#f5c400"

        self.seats_card.setText(f"Seats Protected to NAS\n{protected_count} / {total_count}")
        self.seats_card.setStyleSheet(self._business_card_style(seats_protected_color))

        self._refresh_dashboard_seat_status_board()

        # NAS health
        nas_health_text = "Unknown"
        nas_health_color = "#8a8a8a"
        if not nas_path:
            nas_health_text = "Not configured"
            nas_health_color = "#ff8a8a"
        else:
            try:
                if Path(nas_path).exists():
                    nas_health_text = "Online"
                    nas_health_color = "#52d273"
                else:
                    nas_health_text = "Offline"
                    nas_health_color = "#ff8a8a"
            except Exception:
                nas_health_text = "Unavailable"
                nas_health_color = "#ff8a8a"

        self.vault_card.setText(f"NAS Health\n{nas_health_text}")
        self.vault_card.setStyleSheet(self._business_card_style(nas_health_color))

        # NAS capacity
        cap_text = "Unavailable"
        cap_color = "#8a8a8a"
        if nas_path:
            try:
                usage = shutil.disk_usage(nas_path)
                free_gb = usage.free / (1024 ** 3)
                used_pct = 0 if usage.total <= 0 else int(round((usage.used / usage.total) * 100))
                cap_text = f"{free_gb:.1f} GB free\n{used_pct}% used"
                cap_color = "#52d273" if used_pct < 80 else "#f5c400" if used_pct < 90 else "#ff8a8a"
            except Exception:
                cap_text = "Unavailable"
                cap_color = "#ff8a8a"

        self.nas_card.setText(f"NAS Capacity\n{cap_text}")
        self.nas_card.setStyleSheet(self._business_card_style(cap_color))

    def _business_subscription_id(self) -> str:
        value = os.environ.get("DEVVAULT_BUSINESS_SUBSCRIPTION_ID", "").strip()
        if value:
            return value

        try:
            identity = get_business_seat_identity()
        except Exception:
            identity = None

        if isinstance(identity, dict):
            value = str(identity.get("subscription_id") or "").strip()
            if value:
                return value

        try:
            session = self.parent()._current_business_admin_session()
        except Exception:
            session = None

        if isinstance(session, dict):
            value = str(session.get("subscription_id") or "").strip()
            if value:
                return value

        raise RuntimeError(
            "Business subscription id is unavailable from runtime context. "
            "Re-enroll this device seat or sign in again."
        )

    def _installed_business_seat_limit(self) -> int | None:
        try:
            raw = read_installed_license_text()
            if not raw.strip():
                return None

            import json

            doc = json.loads(raw)
            payload = doc.get("payload", {})
            seats = payload.get("seats")

            if seats in (None, ""):
                return None

            return int(seats)
        except Exception:
            return None

    def _visible_seat_management_rows(
        self,
        rows: list[BusinessSeatRow],
    ) -> list[BusinessSeatRow]:
        active_rows = [
            row
            for row in rows
            if str(row.seat_status or "").strip().lower() == "active"
        ]
        if active_rows:
            return active_rows
        return rows

    def _build_business_seat_management_text(
        self,
        api_payload: dict,
        rows: list[BusinessSeatRow],
    ) -> str:
        active_count = count_active_business_seats(rows)

        seat_limit_raw = (
            api_payload.get("seat_limit")
            or api_payload.get("max_seats")
            or api_payload.get("licensed_seat_limit")
            or api_payload.get("subscription_seat_limit")
        )

        seat_limit = None
        if seat_limit_raw not in (None, ""):
            try:
                seat_limit = int(seat_limit_raw)
            except (TypeError, ValueError):
                seat_limit = None

        if seat_limit is None:
            seat_limit = self._installed_business_seat_limit()

        server_active = api_payload.get("active_seat_count")
        server_remaining = api_payload.get("remaining_capacity")
        reclaimable = api_payload.get("reclaimable_seat_count")

        if server_active is not None:
            active_count = int(server_active)

        if server_remaining is not None:
            remaining_capacity = int(server_remaining)
        else:
            remaining_capacity = None
            if seat_limit is not None:
                remaining_capacity = max(seat_limit - active_count, 0)

        visible_rows = self._visible_seat_management_rows(rows)
        hidden_rows = max(len(rows) - len(visible_rows), 0)

        lines = [
            "DEVVAULT BUSINESS SEAT MANAGEMENT",
            "================================",
            "",
            f"Subscription ID: {self._business_subscription_id()}",
            f"Server Seats Returned: {len(rows)}",
            f"Visible Seats: {len(visible_rows)}",
            f"Hidden Historical Seats: {hidden_rows}",
            f"Active Seats: {active_count}",
            f"Seat Limit: {seat_limit if seat_limit is not None else 'n/a'}",
            f"Remaining Capacity: {remaining_capacity if remaining_capacity is not None else 'n/a'}",
            f"Reclaimable Seats: {reclaimable if reclaimable is not None else 'n/a'}",
            "",
            "Showing active seats by default.",
            "",
        ]

        if not visible_rows:
            lines.append("No server seats found.")
            return "\n".join(lines)

        for row in visible_rows:
            lines.extend(
                [
                    f"Seat ID: {row.seat_id or 'n/a'}",
                    f"Status: {row.seat_status or 'n/a'}",
                    f"Role: {getattr(row, 'seat_role', '') or 'n/a'}",
                    f"Assigned Email: {row.assigned_email or 'n/a'}",
                    f"Assigned Device ID: {row.assigned_device_id or 'n/a'}",
                    f"Assigned Hostname: {row.assigned_hostname or 'n/a'}",
                    f"Seat Label: {row.seat_label or 'n/a'}",
                    f"Created At: {row.created_at or 'n/a'}",
                    f"Revoked At: {row.revoked_at or 'n/a'}",
                    "-" * 48,
                ]
            )

        return "\n".join(lines)


    def _business_fleet_id_from_payload(self, api_payload: dict) -> str:
        return str(
            api_payload.get("fleet_id")
            or api_payload.get("resolved_fleet_id")
            or ""
        ).strip()

    def _resolve_local_inviter_context(
        self,
        api_payload: dict,
        rows: list[BusinessSeatRow],
    ) -> tuple[str, str, str]:
        fleet_id = self._business_fleet_id_from_payload(api_payload)
        if not fleet_id:
            raise RuntimeError("Fleet ID is unavailable from the current server seat inventory.")

        try:
            session = self.parent()._current_business_admin_session()
        except Exception:
            session = None

        if not isinstance(session, dict):
            raise RuntimeError(
                "No active Business admin session is available. "
                "Sign in again before managing invites."
            )

        inviter_seat_id = str(session.get("seat_id") or "").strip()
        if not inviter_seat_id:
            raise RuntimeError("Active Business admin session is missing a seat id.")

        inviter_role = str(session.get("seat_role") or "").strip().lower()
        if inviter_role not in {"owner", "admin"}:
            raise RuntimeError(
                f"Active Business admin session role '{inviter_role or 'n/a'}' cannot manage invites."
            )

        row = next((r for r in rows if str(r.seat_id).strip() == inviter_seat_id), None)
        if row is None:
            raise RuntimeError(
                "The signed-in Business admin seat is not present in the current server seat inventory."
            )

        seat_status = str(row.seat_status or "").strip().lower()
        if seat_status != "active":
            raise RuntimeError(
                f"Signed-in Business admin seat '{inviter_seat_id}' is not active and cannot manage invites."
            )

        row_role = str(getattr(row, "seat_role", "") or "").strip().lower()
        if row_role and row_role not in {"owner", "admin"}:
            raise RuntimeError(
                f"Signed-in Business admin seat '{inviter_seat_id}' has role '{row_role}' and cannot manage invites."
            )

        if row_role in {"owner", "admin"}:
            inviter_role = row_role

        return fleet_id, inviter_seat_id, inviter_role

    def _visible_invite_management_rows(
        self,
        rows: list[BusinessInviteRow],
    ) -> list[BusinessInviteRow]:
        pending_rows = [
            row
            for row in rows
            if str(row.effective_status or "").strip().lower() == "pending"
        ]
        if pending_rows:
            return pending_rows
        return rows

    def _build_business_invite_management_text(
        self,
        api_payload: dict,
        rows: list[BusinessInviteRow],
    ) -> str:
        visible_rows = self._visible_invite_management_rows(rows)
        hidden_rows = max(len(rows) - len(visible_rows), 0)

        lines = [
            "DEVVAULT BUSINESS INVITE MANAGEMENT",
            "==================================",
            "",
            f"Fleet ID: {str(api_payload.get('fleet_id') or 'n/a').strip() or 'n/a'}",
            f"Invite Records Returned: {len(rows)}",
            f"Visible Invites: {len(visible_rows)}",
            f"Hidden Historical Invites: {hidden_rows}",
            "",
            "Showing pending invites by default.",
            "",
        ]

        if not visible_rows:
            lines.append("No invite records found.")
            return "\n".join(lines)

        for row in visible_rows:
            status = str(row.effective_status or row.status or "unknown").strip().upper() or "UNKNOWN"
            invitee_email = row.invitee_email or "n/a"
            invited_role = row.invited_role or "n/a"
            token_id = row.token_id or "n/a"
            expires_at = row.expires_at or "n/a"
            created_at = row.created_at or "n/a"
            consumed_at = row.consumed_at or "n/a"
            revoked_at = row.revoked_at or "n/a"
            inviter_seat_id = row.inviter_seat_id or "n/a"
            inviter_role = row.inviter_role or "n/a"

            lines.extend(
                [
                    f"[{status}] Invite for {invitee_email}",
                    f"Role: {invited_role}",
                    f"Expires: {expires_at}",
                    f"Token ID: {token_id}",
                    f"Created: {created_at}",
                    f"Inviter: {inviter_seat_id} ({inviter_role})",
                    f"Consumed: {consumed_at}",
                    f"Revoked: {revoked_at}",
                    "-" * 48,
                ]
            )

        return "\n".join(lines)

    def _refresh_invite_management_surface(self) -> None:
        try:
            subscription_id = self._business_subscription_id()
            seat_payload = list_business_seats(subscription_id)
            seat_rows = normalize_business_seat_rows(seat_payload)
            fleet_id, inviter_seat_id, inviter_role = self._resolve_local_inviter_context(
                seat_payload,
                seat_rows,
            )

            invite_payload = list_business_invites(
                fleet_id=fleet_id,
                inviter_seat_id=inviter_seat_id,
                inviter_role=inviter_role,
            )
            invite_rows = normalize_business_invite_rows(invite_payload)

            merged_payload = dict(invite_payload)
            if "fleet_id" not in merged_payload:
                merged_payload["fleet_id"] = fleet_id

            self.invite_report.setPlainText(
                self._build_business_invite_management_text(merged_payload, invite_rows)
            )
        except Exception as e:
            self.invite_report.setPlainText(
                "Failed to load server invite inventory.\n\n"
                f"{e}"
            )

    def _pending_invite_choices(self) -> tuple[str, str, str, list[BusinessInviteRow]]:
        subscription_id = self._business_subscription_id()
        seat_payload = list_business_seats(subscription_id)
        seat_rows = normalize_business_seat_rows(seat_payload)
        fleet_id, inviter_seat_id, inviter_role = self._resolve_local_inviter_context(
            seat_payload,
            seat_rows,
        )

        invite_payload = list_business_invites(
            fleet_id=fleet_id,
            inviter_seat_id=inviter_seat_id,
            inviter_role=inviter_role,
        )
        invite_rows = normalize_business_invite_rows(invite_payload)

        pending = [
            row
            for row in invite_rows
            if str(row.effective_status or "").strip().lower() == "pending"
        ]
        return fleet_id, inviter_seat_id, inviter_role, pending

    def _create_invite_from_dialog(self) -> None:
        try:
            subscription_id = self._business_subscription_id()
            seat_payload = list_business_seats(subscription_id)
            seat_rows = normalize_business_seat_rows(seat_payload)
            self._update_seat_management_capacity_state(seat_payload, seat_rows)

            fleet_id, inviter_seat_id, inviter_role = self._resolve_local_inviter_context(
                seat_payload,
                seat_rows,
            )

            ok, payload = CreateInviteDialog.ask(self)
            if not ok or payload is None:
                return

            invited_role = str(payload.get("invited_role") or "").strip().lower()
            invitee_email = str(payload.get("invitee_email") or "").strip()
            seat_label = str(payload.get("seat_label") or "").strip()
            assigned_hostname = str(payload.get("assigned_hostname") or "").strip()
            notes = str(payload.get("notes") or "").strip()

            result = create_business_invite(
                fleet_id=fleet_id,
                inviter_seat_id=inviter_seat_id,
                inviter_role=inviter_role,
                invited_role=invited_role,
                invitee_email=invitee_email,
                expires_in_days=7,
            )

            self._refresh_invite_management_surface()
            self._refresh_seat_management_surface()

            invite_record = result
            if not isinstance(invite_record, dict):
                invite_record = result.get("record")
            if not isinstance(invite_record, dict):
                invite_record = {}

            invite_token = str(
                result.get("invite_token")
                or result.get("raw_token")
                or invite_record.get("invite_token")
                or invite_record.get("raw_token")
                or ""
            ).strip()

            grouped_invite_token = _group_token(invite_token)
            display_invite_token = grouped_invite_token or (invite_token or "n/a")

            token_id = str(
                result.get("token_id")
                or invite_record.get("token_id")
                or ""
            ).strip() or "n/a"

            invited_role_text = str(
                result.get("invited_role")
                or invite_record.get("invited_role")
                or invited_role
                or ""
            ).strip() or "n/a"

            invitee_email_text = str(
                result.get("invitee_email")
                or invite_record.get("invitee_email")
                or invitee_email
                or ""
            ).strip() or "n/a"

            expires_at_text = str(
                result.get("expires_at")
                or invite_record.get("expires_at")
                or ""
            ).strip() or "n/a"

            seat_label_text = seat_label or "n/a"
            assigned_hostname_text = assigned_hostname or "n/a"
            notes_text = notes or "n/a"

            invite_email_delivery = str(
                result.get("invite_email_delivery")
                or invite_record.get("invite_email_delivery")
                or ""
            ).strip().lower()

            invite_email_delivery_error = str(
                result.get("invite_email_delivery_error")
                or invite_record.get("invite_email_delivery_error")
                or ""
            ).strip()

            InviteCreatedDialog.show_dialog(
                self,
                invitee_email=invitee_email_text,
                invited_role=invited_role_text,
                seat_label=seat_label_text,
                assigned_hostname=assigned_hostname_text,
                notes=notes_text,
                token_id=token_id,
                expires_at=expires_at_text,
                raw_token=invite_token,
                grouped_token=display_invite_token,
                invite_email_delivery=invite_email_delivery,
                invite_email_delivery_error=invite_email_delivery_error,
            )

            if invite_email_delivery == "failed":
                failure_msg = (
                    "The invite was created, but invite email delivery failed.\n\n"
                    f"Invitee Email: {invitee_email_text}\n"
                    f"Token ID: {token_id}\n\n"
                    "Fallback: copy the raw invite token from the created invite dialog and deliver it manually."
                )
                if invite_email_delivery_error:
                    failure_msg += f"\n\nEmail Error:\n{invite_email_delivery_error}"

                _centered_message(
                    self,
                    "Invite Email Delivery Failed",
                    failure_msg,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Warning,
                )
        except Exception as e:
            _centered_message(
                self,
                "Invite Management Error",
                f"Failed to create invite.\n\n{e}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Critical,
            )

    def _resend_invite_from_dialog(self) -> None:
        try:
            fleet_id, inviter_seat_id, inviter_role, pending = self._pending_invite_choices()
            if not pending:
                _centered_message(
                    self,
                    "Resend Invite",
                    "There are no pending invites available to resend.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Information,
                )
                return

            choice_map = {}
            labels = []
            for row in pending:
                label = " | ".join(
                    [
                        row.invitee_email or "no-email",
                        row.invited_role or "n/a",
                        row.token_id or "n/a",
                    ]
                )
                labels.append(label)
                choice_map[label] = row.token_id

            selected_label, ok = QInputDialog.getItem(
                self,
                "Resend Invite",
                "Select pending invite:",
                labels,
                0,
                False,
            )
            if not ok or not str(selected_label).strip():
                return

            token_id = choice_map[str(selected_label).strip()]
            result = resend_business_invite(
                fleet_id=fleet_id,
                inviter_seat_id=inviter_seat_id,
                inviter_role=inviter_role,
                token_id=token_id,
            )

            self._refresh_invite_management_surface()

            invite_email_delivery = str(
                result.get("invite_email_delivery")
                or ((result.get("invite") or {}).get("invite_email_delivery"))
                or ""
            ).strip().lower()

            invite_email_delivery_error = str(
                result.get("invite_email_delivery_error")
                or ((result.get("invite") or {}).get("invite_email_delivery_error"))
                or ""
            ).strip()

            if invite_email_delivery == "failed":
                msg = (
                    f"Invite '{token_id}' was resent, but email delivery failed."
                )
                if invite_email_delivery_error:
                    msg += f"\n\nEmail Error:\n{invite_email_delivery_error}"

                _centered_message(
                    self,
                    "Invite Email Delivery Failed",
                    msg,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Warning,
                )
            else:
                _centered_message(
                    self,
                    "Invite Resent",
                    f"Invite '{token_id}' was resent successfully.\n\nInvite Email Delivery: SENT",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Information,
                )
        except Exception as e:
            _centered_message(
                self,
                "Invite Management Error",
                f"Failed to resend invite.\n\n{e}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Critical,
            )

    def _revoke_invite_from_dialog(self) -> None:
        try:
            fleet_id, inviter_seat_id, inviter_role, pending = self._pending_invite_choices()
            if not pending:
                _centered_message(
                    self,
                    "Revoke Invite",
                    "There are no pending invites available to revoke.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Information,
                )
                return

            choice_map = {}
            labels = []
            for row in pending:
                label = " | ".join(
                    [
                        row.invitee_email or "no-email",
                        row.invited_role or "n/a",
                        row.token_id or "n/a",
                    ]
                )
                labels.append(label)
                choice_map[label] = row.token_id

            selected_label, ok = QInputDialog.getItem(
                self,
                "Revoke Invite",
                "Select pending invite:",
                labels,
                0,
                False,
            )
            if not ok or not str(selected_label).strip():
                return

            token_id = choice_map[str(selected_label).strip()]

            answer = _centered_message(
                self,
                "Confirm Invite Revoke",
                f"Revoke invite '{token_id}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
                QMessageBox.Icon.Warning,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

            revoke_business_invite(
                fleet_id=fleet_id,
                inviter_seat_id=inviter_seat_id,
                inviter_role=inviter_role,
                token_id=token_id,
            )

            self._refresh_invite_management_surface()

            _centered_message(
                self,
                "Invite Revoked",
                f"Invite '{token_id}' was revoked successfully.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Information,
            )
        except Exception as e:
            _centered_message(
                self,
                "Invite Management Error",
                f"Failed to revoke invite.\n\n{e}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Critical,
            )


    def _update_seat_management_capacity_state(
        self,
        api_payload: dict | None,
        rows: list[BusinessSeatRow] | None = None,
    ) -> None:
        rows = rows or []

        try:
            if not api_payload:
                self.lbl_invite_capacity_warning.hide()
                self.lbl_invite_capacity_warning.setText("")
                self.btn_add_manual_seat.setEnabled(True)
                self.btn_add_manual_seat.setText("Enroll Seat")
                return

            active_count = count_active_business_seats(rows)

            seat_limit_raw = (
                api_payload.get("seat_limit")
                or api_payload.get("max_seats")
                or api_payload.get("licensed_seat_limit")
                or api_payload.get("subscription_seat_limit")
            )

            seat_limit = None
            if seat_limit_raw not in (None, ""):
                try:
                    seat_limit = int(seat_limit_raw)
                except (TypeError, ValueError):
                    seat_limit = None

            if seat_limit is None:
                seat_limit = self._installed_business_seat_limit()

            server_active = api_payload.get("active_seat_count")
            if server_active not in (None, ""):
                try:
                    active_count = int(server_active)
                except (TypeError, ValueError):
                    pass

            remaining_capacity = None
            server_remaining = api_payload.get("remaining_capacity")
            if server_remaining not in (None, ""):
                try:
                    remaining_capacity = int(server_remaining)
                except (TypeError, ValueError):
                    remaining_capacity = None
            elif seat_limit is not None:
                remaining_capacity = max(seat_limit - active_count, 0)

            runtime_fleet_status = str(
                api_payload.get("fleet_status")
                or api_payload.get("runtime_fleet_status")
                or ""
            ).strip().lower()

            over_capacity = False
            if runtime_fleet_status == "over_capacity":
                over_capacity = True
            elif seat_limit is not None:
                over_capacity = active_count > seat_limit

            at_capacity = (
                not over_capacity
                and remaining_capacity is not None
                and remaining_capacity <= 0
            )

            if getattr(self, "_local_seat_identity_mismatch", False):
                self.lbl_invite_capacity_warning.setText(
                    "Stored local seat identity does not match this runtime device. "
                    "Use Reset / Reassign Seat Identity before enrolling another device."
                )
                self.lbl_invite_capacity_warning.show()
                self.btn_add_manual_seat.setEnabled(False)
                self.btn_add_manual_seat.setText("Enroll Seat (Blocked)")
            elif over_capacity:
                self.lbl_invite_capacity_warning.setText(
                    "Fleet is over licensed capacity. "
                    "Active seats exceed plan limit. Revoke seats or upgrade plan to restore compliance before enrolling another device."
                )
                self.lbl_invite_capacity_warning.show()
                self.btn_add_manual_seat.setEnabled(False)
                self.btn_add_manual_seat.setText("Enroll Seat (Blocked)")
            elif at_capacity:
                self.lbl_invite_capacity_warning.setText(
                    "Invites blocked: fleet is at licensed capacity. "
                    "Revoke a seat to free space before enrolling another device."
                )
                self.lbl_invite_capacity_warning.show()
                self.btn_add_manual_seat.setEnabled(False)
                self.btn_add_manual_seat.setText("Enroll Seat (Blocked)")
            else:
                self.lbl_invite_capacity_warning.hide()
                self.lbl_invite_capacity_warning.setText("")
                self.btn_add_manual_seat.setEnabled(True)
                self.btn_add_manual_seat.setText("Enroll Seat")
        except Exception:
            self.lbl_invite_capacity_warning.hide()
            self.lbl_invite_capacity_warning.setText("")
            self.btn_add_manual_seat.setEnabled(True)
            self.btn_add_manual_seat.setText("Enroll Seat")

    def _runtime_local_identity_matches(self, identity: dict | None) -> bool:
        if not isinstance(identity, dict):
            return True

        stored_hostname = str(identity.get("assigned_hostname") or "").strip()
        stored_device_id = str(identity.get("assigned_device_id") or "").strip()

        runtime_hostname = str(
            os.environ.get("COMPUTERNAME")
            or os.environ.get("HOSTNAME")
            or ""
        ).strip()

        runtime_hostname_upper = runtime_hostname.upper()
        stored_hostname_upper = stored_hostname.upper()
        stored_device_id_upper = stored_device_id.upper()

        hostname_ok = (
            not stored_hostname_upper
            or not runtime_hostname_upper
            or stored_hostname_upper == runtime_hostname_upper
        )
        device_ok = (
            not stored_device_id_upper
            or not runtime_hostname_upper
            or stored_device_id_upper == runtime_hostname_upper
        )

        return hostname_ok and device_ok

    def _refresh_local_seat_identity_status(self) -> None:
        try:
            identity = get_business_seat_identity()
            if not isinstance(identity, dict):
                self._local_seat_identity_mismatch = False
                self.lbl_local_seat_identity.setText(
                    "Local Device Seat Identity: Not enrolled"
                )
                return

            seat_id = str(identity.get("seat_id") or "").strip() or "n/a"
            assigned_device_id = str(identity.get("assigned_device_id") or "").strip() or "n/a"
            assigned_hostname = str(identity.get("assigned_hostname") or "").strip() or "n/a"
            seat_label = str(identity.get("seat_label") or "").strip() or "n/a"
            enrolled_at_utc = str(identity.get("enrolled_at_utc") or "").strip() or "n/a"

            self._local_seat_identity_mismatch = not self._runtime_local_identity_matches(identity)

            suffix = ""
            if self._local_seat_identity_mismatch:
                runtime_hostname = str(
                    os.environ.get("COMPUTERNAME")
                    or os.environ.get("HOSTNAME")
                    or ""
                ).strip() or "unknown"
                suffix = (
                    "\n\nWARNING: Stored local seat identity does not match this runtime device. "
                    "Use Reset / Reassign Seat Identity to repair this device before continuing.\n"
                    f"Current runtime hostname: {runtime_hostname}"
                )

            self.lbl_local_seat_identity.setText(
                "Local Device Seat Identity:\n"
                f"Seat ID: {seat_id}\n"
                f"Device ID: {assigned_device_id}\n"
                f"Hostname: {assigned_hostname}\n"
                f"Seat Label: {seat_label}\n"
                f"Enrolled At (UTC): {enrolled_at_utc}"
                f"{suffix}"
            )
        except Exception:
            self._local_seat_identity_mismatch = False
            self.lbl_local_seat_identity.setText(
                "Local Device Seat Identity: Unavailable"
            )

    def _refresh_readiness_surface(self) -> None:
        try:
            identity = get_business_seat_identity()
        except Exception:
            identity = None

        has_identity = isinstance(identity, dict) and bool(str(identity.get("seat_id") or "").strip())

        seat_id = "n/a"
        assigned_device_id = "n/a"
        assigned_hostname = "n/a"
        seat_label = "n/a"
        enrolled_at_utc = "n/a"

        if has_identity:
            seat_id = str(identity.get("seat_id") or "").strip() or "n/a"
            assigned_device_id = str(identity.get("assigned_device_id") or "").strip() or "n/a"
            assigned_hostname = str(identity.get("assigned_hostname") or "").strip() or "n/a"
            seat_label = str(identity.get("seat_label") or "").strip() or "n/a"
            enrolled_at_utc = str(identity.get("enrolled_at_utc") or "").strip() or "n/a"

        try:
            identity_matches = bool(has_identity and self._runtime_local_identity_matches(identity))
        except Exception:
            identity_matches = False

        try:
            nas_path = str(get_business_nas_path() or "").strip()
        except Exception:
            nas_path = ""

        session = None
        try:
            session = self.parent()._current_business_admin_session()
        except Exception:
            session = None

        session_active = isinstance(session, dict)
        session_role = str((session or {}).get("seat_role") or "").strip() or "n/a"
        session_email = str((session or {}).get("email") or "").strip() or "n/a"
        session_expires = str((session or {}).get("session_expires_at") or "").strip() or "n/a"

        blockers = []
        if not has_identity:
            blockers.append("Local Business seat identity is not enrolled.")
        elif not identity_matches:
            blockers.append("Stored local Business seat identity does not match this runtime device.")
        if not nas_path:
            blockers.append("Business NAS target is not configured.")
        if not session_active:
            blockers.append("Business admin session is not active.")

        if blockers:
            self.lbl_readiness_summary.setText(
                "Business readiness: BLOCKED\n" + "\n".join(f"- {x}" for x in blockers)
            )
            self.lbl_readiness_summary.setStyleSheet(
                "font-size:14px;font-weight:700;color:#ff8a8a;padding:6px 0 8px 0;"
            )
        else:
            self.lbl_readiness_summary.setText(
                "Business readiness: READY\n- Local seat identity present\n- NAS configured\n- Admin session active"
            )
            self.lbl_readiness_summary.setStyleSheet(
                "font-size:14px;font-weight:700;color:#52d273;padding:6px 0 8px 0;"
            )

        lines = [
            "DEVVAULT BUSINESS SEAT IDENTITY / READINESS",
            "===========================================",
            "",
            f"Seat Identity Present: {'YES' if has_identity else 'NO'}",
            f"Seat Identity Matches Runtime Device: {'YES' if identity_matches else 'NO'}",
            f"Business NAS Configured: {'YES' if nas_path else 'NO'}",
            f"Business Admin Session Active: {'YES' if session_active else 'NO'}",
            "",
            "LOCAL SEAT IDENTITY",
            "-------------------",
            f"Seat ID: {seat_id}",
            f"Device ID: {assigned_device_id}",
            f"Hostname: {assigned_hostname}",
            f"Seat Label: {seat_label}",
            f"Enrolled At (UTC): {enrolled_at_utc}",
            "",
            "BUSINESS NAS",
            "------------",
            f"Configured Path: {nas_path or 'Not configured'}",
            "",
            "ADMIN SESSION",
            "-------------",
            f"Session Active: {'YES' if session_active else 'NO'}",
            f"Role: {session_role}",
            f"Email: {session_email}",
            f"Session Expires: {session_expires}",
            "",
            "BLOCKERS",
            "--------",
        ]

        if blockers:
            lines.extend(f"- {item}" for item in blockers)
        else:
            lines.append("- None")

        self.readiness_report.setPlainText("\n".join(lines))

    def _refresh_seat_management_surface(self) -> None:
        try:
            subscription_id = self._business_subscription_id()
            api_payload = list_business_seats(subscription_id)
            rows = normalize_business_seat_rows(api_payload)

            filter_mode = getattr(self, "_seat_mgmt_filter_mode", None)
            attention_ids = set(getattr(self, "_attention_seat_ids", ()))

            if filter_mode == "attention" and attention_ids:
                rows = [r for r in rows if str(r.seat_id) in attention_ids]

            self.seat_mgmt_report.setPlainText(
                self._build_business_seat_management_text(api_payload, rows)
            )
            self._update_seat_management_capacity_state(api_payload, rows)
            self._refresh_local_seat_identity_status()
        except (BusinessSeatApiError, ValueError, RuntimeError) as e:
            self.seat_mgmt_report.setPlainText(
                "Failed to load server seat inventory.\n\n"
                f"{e}"
            )
            self._update_seat_management_capacity_state(None, [])
            self._refresh_local_seat_identity_status()
        except Exception as e:
            self.seat_mgmt_report.setPlainText(
                "Failed to load server seat inventory.\n\n"
                f"{e}"
            )
            self._update_seat_management_capacity_state(None, [])
            self._refresh_local_seat_identity_status()

    def _business_customer_id(self) -> str:
        value = os.environ.get("DEVVAULT_BUSINESS_CUSTOMER_ID", "").strip()
        if value:
            return value

        try:
            identity = get_business_seat_identity()
        except Exception:
            identity = None

        if isinstance(identity, dict):
            value = str(identity.get("customer_id") or "").strip()
            if value:
                return value

        try:
            session = self.parent()._current_business_admin_session()
        except Exception:
            session = None

        if isinstance(session, dict):
            value = str(session.get("customer_id") or "").strip()
            if value:
                return value

        raise RuntimeError(
            "Business customer id is unavailable from runtime context. "
            "Re-enroll this device seat or sign in again."
        )

    def _format_seat_enroll_error(self, exc: Exception) -> str:
        if isinstance(exc, BusinessSeatApiError):
            payload = exc.payload if isinstance(exc.payload, dict) else {}
            result = str(payload.get("result") or payload.get("reason") or "").strip().lower()

            seat_limit = payload.get("seat_limit")
            active_seats = payload.get("active_seats")
            if active_seats is None:
                active_seats = payload.get("active_seat_count")
            remaining_capacity = payload.get("remaining_capacity")

            if result == "seat_identity_exists":
                return (
                    "This device identity is already assigned to an active server seat.\n\n"
                    f"Existing seat id: {payload.get('seat_id') or 'n/a'}\n"
                    f"Matched on: {payload.get('matched_on') or 'n/a'}\n"
                    f"Assigned email: {payload.get('assigned_email') or 'n/a'}\n"
                    f"Assigned device id: {payload.get('assigned_device_id') or 'n/a'}\n"
                    f"Assigned hostname: {payload.get('assigned_hostname') or 'n/a'}\n"
                    f"Seat role: {payload.get('seat_role') or 'n/a'}\n"
                    f"Seat label: {payload.get('seat_label') or 'n/a'}\n\n"
                    "Use Reset / Reassign Seat Identity on the intended device instead of enrolling a duplicate seat."
                )

            if result == "seat_limit_reached":
                if seat_limit is not None and active_seats is not None:
                    return (
                        "Seat limit reached for this subscription.\n\n"
                        f"Active seats: {active_seats}\n"
                        f"Seat limit: {seat_limit}\n"
                        f"Remaining capacity: {remaining_capacity if remaining_capacity is not None else 0}"
                    )
                return "Seat limit reached for this subscription."

            if result == "over_capacity":
                return (
                    "Fleet is over capacity.\n\n"
                    "Revoke a seat before enrolling another device."
                )

            if result == "expired_locked":
                return (
                    "Subscription expired.\n\n"
                    "Fleet enrollment is locked until billing is restored."
                )

            if result == "cancelled_locked":
                return (
                    "Subscription cancelled.\n\n"
                    "Fleet enrollment is locked for this fleet."
                )

            if result == "blocked":
                return (
                    "Fleet is blocked.\n\n"
                    "Billing or account status requires attention before enrollment can continue."
                )

            if result == "fleet_not_found":
                return "Fleet was not found for this subscription."

        return f"Failed to enroll server seat.\n\n{exc}"

    def _enroll_seat_from_dialog(self) -> None:
        try:
            subscription_id = self._business_subscription_id()
            latest_payload = list_business_seats(subscription_id)
            latest_rows = normalize_business_seat_rows(latest_payload)
            self._update_seat_management_capacity_state(latest_payload, latest_rows)

            active_count = count_active_business_seats(latest_rows)

            seat_limit_raw = (
                latest_payload.get("seat_limit")
                or latest_payload.get("max_seats")
                or latest_payload.get("licensed_seat_limit")
                or latest_payload.get("subscription_seat_limit")
            )

            seat_limit = None
            if seat_limit_raw not in (None, ""):
                try:
                    seat_limit = int(seat_limit_raw)
                except (TypeError, ValueError):
                    seat_limit = None

            if seat_limit is None:
                seat_limit = self._installed_business_seat_limit()

            server_active = latest_payload.get("active_seat_count")
            if server_active not in (None, ""):
                try:
                    active_count = int(server_active)
                except (TypeError, ValueError):
                    pass

            remaining_capacity = None
            server_remaining = latest_payload.get("remaining_capacity")
            if server_remaining not in (None, ""):
                try:
                    remaining_capacity = int(server_remaining)
                except (TypeError, ValueError):
                    remaining_capacity = None
            elif seat_limit is not None:
                remaining_capacity = max(seat_limit - active_count, 0)

            runtime_fleet_status = str(
                latest_payload.get("fleet_status")
                or latest_payload.get("runtime_fleet_status")
                or ""
            ).strip().lower()

            over_capacity = False
            if runtime_fleet_status == "over_capacity":
                over_capacity = True
            elif seat_limit is not None:
                over_capacity = active_count > seat_limit

            at_capacity = (
                not over_capacity
                and remaining_capacity is not None
                and remaining_capacity <= 0
            )

            if getattr(self, "_local_seat_identity_mismatch", False):
                _centered_message(
                    self,
                    "Enroll Seat Blocked",
                    "Stored local seat identity does not match this runtime device. Use Reset / Reassign Seat Identity before enrolling another device.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Warning,
                )
                return

            if over_capacity:
                _centered_message(
                    self,
                    "Enroll Seat Blocked",
                    "Fleet is over licensed capacity. Revoke seats or upgrade plan before enrolling another device.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Warning,
                )
                return

            if at_capacity:
                _centered_message(
                    self,
                    "Enroll Seat Blocked",
                    "Fleet is at licensed capacity. Revoke a seat to free space before enrolling another device.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Warning,
                )
                return

            ok, payload = EnrollSeatDialog.ask(
                self,
                subscription_id=subscription_id,
                customer_id=self._business_customer_id(),
            )
            if not ok or payload is None:
                return

            required_fields = [
                "subscription_id",
                "customer_id",
                "assigned_email",
                "assigned_device_id",
                "assigned_hostname",
                "seat_label",
            ]
            missing = [name for name in required_fields if not str(payload.get(name, "")).strip()]
            if missing:
                _centered_message(
                    self,
                    "Enroll Seat",
                    "All required fields must be provided.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Warning,
                )
                return

            invite_token, ok = QInputDialog.getText(
                self,
                "Enroll Seat",
                "Paste invite token:",
                QLineEdit.Normal,
                "",
            )
            if not ok or not str(invite_token).strip():
                return

            existing_identity = get_business_seat_identity()
            candidate_seat_id = ""
            if isinstance(existing_identity, dict):
                candidate_seat_id = str(existing_identity.get("seat_id") or "").strip()

            runtime_hostname = str(
                os.environ.get("COMPUTERNAME")
                or os.environ.get("HOSTNAME")
                or payload.get("assigned_hostname")
                or ""
            ).strip()

            response = enroll_business_seat(
                subscription_id=str(payload["subscription_id"]).strip(),
                customer_id=str(payload["customer_id"]).strip(),
                assigned_email=str(payload["assigned_email"]).strip(),
                assigned_device_id=str(payload["assigned_device_id"]).strip(),
                assigned_hostname=str(payload["assigned_hostname"]).strip(),
                seat_label=str(payload["seat_label"]).strip(),
                notes=str(payload.get("notes", "")).strip(),
                invite_token=str(invite_token).strip(),
                candidate_seat_id=candidate_seat_id,
                display_name=str(payload["seat_label"]).strip(),
                                hostname=runtime_hostname,
                                app_version=_safe_app_version(),
                                installed_license=_collect_installed_license_context(),
                                vault_evidence=_collect_vault_evidence_summary(),
                fingerprint_hash=_compute_device_fingerprint(),




            )

            self._refresh_seat_management_surface()
            try:
                self.parent()._refresh_business_dashboard()
            except Exception:
                pass

            seat_id = str(response.get("seat_id", "")).strip() or "new seat"

            if seat_id and seat_id != "new seat":
                existing_identity = get_business_seat_identity()
                existing_seat_id = ""
                if isinstance(existing_identity, dict):
                    existing_seat_id = str(existing_identity.get("seat_id") or "").strip()

                if existing_seat_id and existing_seat_id != seat_id:
                    _centered_message(
                        self,
                        "Seat Identity Reassignment Blocked",
                        (
                            "A different local business seat identity is already stored on this device.\n\n"
                            f"Stored seat id: {existing_seat_id}\n"
                            f"New seat id: {seat_id}\n\n"
                            "DevVault will not silently replace the stored local seat identity. "
                            "Use an explicit reassignment/reset workflow before changing device seat identity."
                        ),
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.Icon.Warning,
                    )
                else:
                    seat_role = str(response.get("seat_role") or "").strip()
                    if not seat_role:
                        seat_role = self._seat_role_for_server_seat_id(seat_id)

                    set_business_seat_identity(
                        seat_id=seat_id,
                        fleet_id=str(response.get("fleet_id") or "").strip(),
                        subscription_id=str(payload["subscription_id"]).strip(),
                        customer_id=str(payload["customer_id"]).strip(),
                        assigned_email=str(payload["assigned_email"]).strip(),
                        assigned_device_id=str(payload["assigned_device_id"]).strip(),
                        assigned_hostname=str(payload["assigned_hostname"]).strip(),
                        seat_label=str(payload["seat_label"]).strip(),
                        seat_role=seat_role,
                    )
                    self._refresh_local_seat_identity_status()

                    # Force password bootstrap for owner/admin seats
                    try:
                        if seat_role in {"owner", "admin"}:
                            reset_ok = self._business_admin_force_password_reset(
                                email=str(payload["assigned_email"]).strip(),
                                current_password="",
                            )
                            if not reset_ok:
                                return
                    except Exception:
                        pass

                    self._maybe_force_business_nas_onboarding(
                        reason="Business seat enrollment completed. NAS setup is now required.",
                        prompt_once=False,
                    )

            _centered_message(
                self,
                "Seat Enrolled",
                f"Server seat '{seat_id}' was enrolled successfully.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Information,
            )

        except Exception as e:
            try:
                self._refresh_seat_management_surface()
            except Exception:
                pass

            _centered_message(
                self,
                "Seat Management Error",
                self._format_seat_enroll_error(e),
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Critical,
            )


    def _set_admin_password_for_seat(self) -> None:
        if not self.parent()._require_action_entitlement(
            "biz_seat_admin_tools",
            action_name="Set Admin Password",
        ):
            return

        try:
            subscription_id = self._business_subscription_id()
            api_payload = list_business_seats(subscription_id)
            rows = normalize_business_seat_rows(api_payload)

            identity = get_business_seat_identity()
            if not isinstance(identity, dict):
                _centered_message(self, "Set Admin Password", "No local seat identity.", QMessageBox.Ok)
                return

            invoker_role = str(identity.get("seat_role") or identity.get("role") or "").strip().lower()

            if invoker_role != "owner":
                _centered_message(
                    self,
                    "Set Admin Password",
                    "Only owner can set/reset admin passwords.",
                    QMessageBox.Ok,
                )
                return

            target_choices = []
            for row in rows:
                seat_status = str(getattr(row, "seat_status", "") or "").strip().lower()
                seat_role = str(getattr(row, "seat_role", "") or "").strip().lower()
                seat_id = str(getattr(row, "seat_id", "") or "").strip()

                if seat_status != "active":
                    continue
                if seat_role not in {"owner", "admin"}:
                    continue

                label = f"{seat_role} | {seat_id}"
                target_choices.append((label, seat_id))

            if not target_choices:
                _centered_message(self, "Set Admin Password", "No eligible seats found.", QMessageBox.Ok)
                return

            labels = [l for l, _ in target_choices]
            mapping = {l: sid for l, sid in target_choices}

            selected, ok = QInputDialog.getItem(
                self,
                "Set Admin Password",
                "Select seat:",
                labels,
                0,
                False,
            )
            if not ok:
                return

            target_seat_id = mapping[selected]

            new_password, ok = QInputDialog.getText(
                self,
                "Set Admin Password",
                "Enter new password:",
                QLineEdit.Password,
            )
            if not ok or not new_password.strip():
                return

            try:
                parent = self.parent()
            except Exception:
                parent = None

            if parent is None or not hasattr(parent, "_require_business_admin_session"):
                raise RuntimeError("Business admin session authority is unavailable")

            if not parent._require_business_admin_session("Set Admin Password"):
                return

            session = parent._current_business_admin_session()
            token = str((session or {}).get("admin_session_token") or "").strip()
            if not token:
                global _GLOBAL_ADMIN_SESSION
                token = str((_GLOBAL_ADMIN_SESSION or {}).get("admin_session_token") or "").strip()
            if not token:
                raise RuntimeError(
                    "No admin session token available. Sign in first."
                )

            set_business_admin_password(
                email=str((session or {}).get("email") or "").strip(),
                new_password=new_password.strip(),
                token=token,
            )

            _centered_message(
                self,
                "Set Admin Password",
                "Password updated successfully.",
                QMessageBox.Ok,
            )

        except Exception as e:
            _centered_message(
                self,
                "Set Admin Password",
                f"Failed:\n\n{e}",
                QMessageBox.Ok,
            )

    def _seat_role_for_server_seat_id(self, seat_id: str) -> str:
        normalized_seat_id = str(seat_id or "").strip()
        if not normalized_seat_id:
            return ""

        try:
            subscription_id = self._business_subscription_id()
            api_payload = list_business_seats(subscription_id)
            rows = normalize_business_seat_rows(api_payload)
        except Exception:
            return ""

        for row in rows:
            if str(getattr(row, "seat_id", "") or "").strip() == normalized_seat_id:
                return str(getattr(row, "seat_role", "") or "").strip().lower()

        return ""

    def _owner_seat_mutation_blocked(self, seat_id: str, action_name: str) -> bool:
        role = self._seat_role_for_server_seat_id(seat_id)
        if role != "owner":
            return False

        _centered_message(
            self,
            f"{action_name} Blocked",
            (
                "Owner seat is protected and cannot be changed from the desktop app.\n\n"
                "Owner role issuance, reassignment, revoke, and recovery must be performed "
                "only by Trustware control-plane support."
            ),
            QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Ok,
            QMessageBox.Icon.Warning,
        )
        return True

    def _reset_or_reassign_local_seat_identity(self) -> None:
        try:
            identity = get_business_seat_identity()

            if not isinstance(identity, dict):
                answer = _centered_message(
                    self,
                    "Reset / Reassign Seat Identity",
                    (
                        "No local business seat identity is stored on this device.\n\n"
                        "Open the enroll workflow now?"
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                    QMessageBox.Icon.Question,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    self._enroll_seat_from_dialog()
                return

            stored_seat_id = str(identity.get("seat_id") or "").strip() or "n/a"
            assigned_device_id = str(identity.get("assigned_device_id") or "").strip() or "n/a"
            assigned_hostname = str(identity.get("assigned_hostname") or "").strip() or "n/a"
            seat_label = str(identity.get("seat_label") or "").strip() or "n/a"
            enrolled_at_utc = str(identity.get("enrolled_at_utc") or "").strip() or "n/a"

            if stored_seat_id and stored_seat_id != "n/a":
                if self._owner_seat_mutation_blocked(stored_seat_id, "Reset / Reassign Seat Identity"):
                    return

            answer = _centered_message(
                self,
                "Confirm Seat Identity Reassignment",
                (
                    "This will attempt to revoke the currently stored server seat identity, "
                    "clear the local device seat identity, and then open enrollment.\n\n"
                    f"Stored seat id: {stored_seat_id}\n"
                    f"Device id: {assigned_device_id}\n"
                    f"Hostname: {assigned_hostname}\n"
                    f"Seat label: {seat_label}\n"
                    f"Enrolled at (UTC): {enrolled_at_utc}\n\n"
                    "Continue?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
                QMessageBox.Icon.Warning,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

            revoke_error = None
            if stored_seat_id and stored_seat_id != "n/a":
                try:
                    revoke_business_seat(stored_seat_id)
                except Exception as exc:
                    revoke_error = exc

            if revoke_error is not None:
                force_answer = _centered_message(
                    self,
                    "Server Revoke Failed",
                    (
                        "DevVault could not revoke the currently stored server seat identity.\n\n"
                        f"Stored seat id: {stored_seat_id}\n\n"
                        f"Error: {revoke_error}\n\n"
                        "You may stop here, or force-clear the local seat identity only and continue to re-enroll."
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                    QMessageBox.Icon.Warning,
                )
                if force_answer != QMessageBox.StandardButton.Yes:
                    return

            clear_business_seat_identity()
            self._refresh_local_seat_identity_status()
            self._refresh_seat_management_surface()

            _centered_message(
                self,
                "Local Seat Identity Cleared",
                (
                    "The local business seat identity has been cleared.\n\n"
                    "DevVault will now open the enroll workflow."
                ),
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Information,
            )

            self._enroll_seat_from_dialog()

        except Exception as e:
            _centered_message(
                self,
                "Seat Identity Reset Failed",
                f"Could not reset/reassign local seat identity.\n\n{e}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Critical,
            )


    def _issue_admin_login_token_for_selected_seat(self) -> None:
        if not self.parent()._require_action_entitlement(
            "biz_seat_admin_tools",
            action_name="Issue Admin Login Token",
        ):
            return

        try:
            subscription_id = self._business_subscription_id()
            api_payload = list_business_seats(subscription_id)
            rows = normalize_business_seat_rows(api_payload)

            identity = get_business_seat_identity()
            if not isinstance(identity, dict):
                _centered_message(self, "Issue Admin Login Token", "No local seat identity.", QMessageBox.Ok)
                return

            invoker_role = str(identity.get("seat_role") or identity.get("role") or "").strip().lower()
            if invoker_role not in {"owner", "admin"}:
                _centered_message(self, "Issue Admin Login Token", "Only owner/admin allowed.", QMessageBox.Ok)
                return

            # existing logic continues below (unchanged)

        except Exception as e:
            _centered_message(self, "Issue Admin Login Token", f"Failed:\n\n{e}", QMessageBox.Ok)


    def _show_one_time_admin_login_token_dialog(self, result: dict) -> None:
        seat_token = str(result.get("seat_token") or "").strip()
        token_id = str(result.get("token_id") or "").strip() or "n/a"
        target_seat_id = str(result.get("target_seat_id") or "").strip() or "n/a"
        target_seat_role = str(result.get("target_seat_role") or "").strip().lower() or "n/a"
        revoked_count = int(result.get("revoked_count") or 0)

        if not seat_token:
            raise RuntimeError("API did not return a seat token.")

        dlg = QDialog(self)
        dlg.setWindowTitle("Issued Admin Login Token")
        dlg.setModal(True)
        dlg.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)
        dlg.setMinimumWidth(760)

        layout = QVBoxLayout(dlg)

        lbl_intro = QLabel(
            "This token is shown only now. Copy it and use it to sign in on the target machine."
        )
        lbl_intro.setWordWrap(True)
        layout.addWidget(lbl_intro)

        lbl_meta = QLabel(
            "Target Seat: "
            f"{target_seat_id}\n"
            f"Target Role: {target_seat_role}\n"
            f"Token ID: {token_id}\n"
            f"Revoked Prior Active Tokens: {revoked_count}"
        )
        lbl_meta.setWordWrap(True)
        layout.addWidget(lbl_meta)

        token_box = QPlainTextEdit(dlg)
        token_box.setReadOnly(True)
        token_box.setPlainText(seat_token)
        token_box.setMinimumHeight(120)
        layout.addWidget(token_box)

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("Copy Token", dlg)
        btn_close = QPushButton("Close", dlg)
        btn_row.addWidget(btn_copy)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        def _copy_token() -> None:
            QApplication.clipboard().setText(seat_token)
            _centered_message(
                dlg,
                "Issued Admin Login Token",
                "Seat login token copied to clipboard.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Information,
            )

        btn_copy.clicked.connect(_copy_token)
        btn_close.clicked.connect(dlg.accept)

        try:
            _center_widget_on_parent(dlg, self)
            QTimer.singleShot(0, lambda: _center_widget_on_parent(dlg, self))
        except Exception:
            pass

        dlg.exec()

    def _run_selected_seat_health_check(self) -> None:
        if not self.parent()._require_action_entitlement(
            "biz_seat_admin_tools",
            action_name="Run Seat Health Check",
        ):
            return

        try:
            seat_choices = self._active_server_seat_choices()
            if not seat_choices:
                _centered_message(
                    self,
                    "Run Seat Health Check",
                    "No active server-backed seats are available.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Information,
                )
                return

            labels = [label for label, _ in seat_choices]
            choice_map = {label: seat_id for label, seat_id in seat_choices}
            default_index = self._preferred_seat_health_default_index(seat_choices)

            selected_label, ok = QInputDialog.getItem(
                self,
                "Run Seat Health Check",
                "Select seat:",
                labels,
                default_index,
                False,
            )
            if not ok or not str(selected_label).strip():
                return

            selected_seat_id = choice_map[str(selected_label).strip()]
            self._last_seat_health_selection = str(selected_seat_id).strip()
            self._admin_run_health_check(str(selected_seat_id).strip())

        except Exception as e:
            _centered_message(
                self,
                "Run Seat Health Check",
                f"Could not start seat health check.\n\n{e}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Critical,
            )

    def _active_server_seat_choices(self) -> list[tuple[str, str]]:
        subscription_id = self._business_subscription_id()
        api_payload = list_business_seats(subscription_id)
        rows = normalize_business_seat_rows(api_payload)

        choices: list[tuple[str, str]] = []
        for row in rows:
            if row.seat_status.strip().lower() != "active":
                continue

            label = " | ".join(
                part for part in [
                    row.seat_label or "n/a",
                    row.assigned_hostname or "n/a",
                    row.seat_id or "n/a",
                ]
                if part
            )
            choices.append((label, row.seat_id))

        return choices

    def _revoke_seat_from_dialog(self) -> None:
        try:
            seat_choices = self._active_server_seat_choices()
            if not seat_choices:
                _centered_message(
                    self,
                    "Revoke Seat",
                    "There are no active server seats to revoke.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Information,
                )
                return

            ok, selected_seat_id = RevokeSeatDialog.ask(self, seat_choices)
            if not ok or not str(selected_seat_id).strip():
                return

            if self._owner_seat_mutation_blocked(str(selected_seat_id).strip(), "Revoke Seat"):
                return

            answer = _centered_message(
                self,
                "Confirm Seat Revoke",
                f"Revoke server seat '{selected_seat_id}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
                QMessageBox.Icon.Warning,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

            revoke_business_seat(str(selected_seat_id).strip())

            self._refresh_seat_management_surface()
            try:
                self.parent()._refresh_business_dashboard()
            except Exception:
                pass

            _centered_message(
                self,
                "Seat Revoked",
                f"Server seat '{selected_seat_id}' was revoked successfully.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Information,
            )

        except Exception as e:
            _centered_message(
                self,
                "Seat Management Error",
                f"Failed to revoke server seat.\n\n{e}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Critical,
            )

    def _admin_run_health_check(self, seat_id: str) -> None:
        if not self.parent()._require_action_entitlement(
            "biz_seat_admin_tools",
            action_name="Run Seat Health Check",
        ):
            return

        if not self.parent()._require_business_admin_session("Run Seat Health Check"):
            return

        try:
            normalized_seat_id = str(seat_id).strip()
            if not normalized_seat_id:
                _centered_message(
                    self,
                    "Run Health Check",
                    "A seat id is required.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Warning,
                )
                return

            registry = SeatRegistryEngine(
                registry_root=config_dir()
            )
            records = list(registry.sync())
            selected = None
            live_row = None

            try:
                subscription_id = self._business_subscription_id()
                api_payload = list_business_seats(subscription_id)
                live_rows = normalize_business_seat_rows(api_payload)

                live_row = next(
                    (
                        row
                        for row in live_rows
                        if str(getattr(row, "seat_id", "") or "").strip() == normalized_seat_id
                    ),
                    None,
                )

                if live_row is not None:
                    match_keys = set()

                    assigned_hostname = str(getattr(live_row, "assigned_hostname", "") or "").strip().upper()
                    assigned_device_id = str(getattr(live_row, "assigned_device_id", "") or "").strip().upper()

                    if assigned_hostname:
                        match_keys.add(assigned_hostname)
                    if assigned_device_id:
                        match_keys.add(assigned_device_id)

                    if match_keys:
                        selected = next(
                            (
                                seat
                                for seat in records
                                if str(getattr(seat, "seat_id", "") or "").strip().upper() in match_keys
                                or bool({
                                    str(x).strip().upper()
                                    for x in getattr(seat, "hostnames", ()) or ()
                                    if str(x).strip()
                                } & match_keys)
                            ),
                            None,
                        )
            except Exception:
                selected = None
                live_row = None

            if selected is None:
                selected = next(
                    (
                        seat
                        for seat in records
                        if str(getattr(seat, "seat_id", "") or "").strip() == normalized_seat_id
                    ),
                    None,
                )

            if selected is None:
                _centered_message(
                    self,
                    "Run Health Check",
                    f"Seat '{normalized_seat_id}' was not found in local registry evidence.",
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Warning,
                )
                return

            roots: set[Path] = set()
            for endpoint in getattr(selected, "vault_endpoints", ()) or ():
                try:
                    roots.add(Path(endpoint).expanduser())
                except Exception:
                    continue

            request = FetchRequest(
                scope_id=f"seat-health-check-{normalized_seat_id.lower()}",
                vault_roots=(Path(get_business_nas_path()),),
                selected_seats=(normalized_seat_id,),
                include_details=True,
            )

            result = SeatProtectionStateFetcher().fetch(request)
            report = build_business_seat_protection_state_report(result)
            report_text = render_business_seat_protection_state_text(report)

            banner_status = ""
            banner_message = ""

            try:
                local_identity = get_business_seat_identity()
            except Exception:
                local_identity = None

            try:
                local_seat_id = str((local_identity or {}).get("seat_id") or "").strip()
            except Exception:
                local_seat_id = ""

            if local_seat_id and local_seat_id == normalized_seat_id:
                try:
                    banner_status = str(self.parent().protection_status_label.text() or "").strip()
                except Exception:
                    banner_status = ""
                try:
                    banner_message = str(self.parent().protection_status_message.text() or "").strip()
                except Exception:
                    banner_message = ""

            seat_status_text = self._build_seat_status_summary_text(
                seat_id=normalized_seat_id,
                seat_label=(
                    str(getattr(live_row, "seat_label", "") or "").strip()
                    if live_row is not None else ""
                ),
                assigned_hostname=(
                    str(getattr(live_row, "assigned_hostname", "") or "").strip()
                    if live_row is not None else ""
                ),
                banner_status=banner_status,
                banner_message=banner_message,
            )
            if seat_status_text.strip():
                report_text = seat_status_text + "\n\n" + report_text

            self._refresh_seat_management_surface()
            try:
                self._refresh_business_dashboard()
            except Exception:
                pass
            try:
                self.parent()._refresh_business_dashboard()
            except Exception:
                pass

            seat_label = ""
            seat_role = ""
            assigned_hostname = ""

            if live_row is not None:
                seat_label = str(getattr(live_row, "seat_label", "") or "").strip()
                seat_role = str(getattr(live_row, "seat_role", "") or "").strip().lower()
                assigned_hostname = str(getattr(live_row, "assigned_hostname", "") or "").strip()

            title_parts = []
            if seat_label:
                title_parts.append(seat_label)
            elif assigned_hostname:
                title_parts.append(assigned_hostname)
            else:
                title_parts.append(normalized_seat_id)

            if seat_role:
                title_parts.append(f"({seat_role})")

            friendly_title = " ".join(title_parts).strip()

            dlg = QDialog(self)
            dlg.setWindowTitle(f"Seat Health Check — {friendly_title}")
            dlg.setModal(True)
            dlg.setMinimumWidth(860)
            dlg.setMinimumHeight(520)
            dlg.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)

            root = QVBoxLayout(dlg)
            root.setContentsMargins(16, 16, 16, 16)
            root.setSpacing(12)

            title = QLabel(f"Seat Health Check — {friendly_title}", dlg)
            title.setWordWrap(True)
            root.addWidget(title)

            details = QTextEdit(dlg)
            details.setReadOnly(True)
            details.setPlainText(report_text)
            root.addWidget(details, 1)

            lbl_command_status = QLabel("Last Command: None\nStatus: Idle", dlg)
            lbl_command_status.setWordWrap(True)
            lbl_command_status.setStyleSheet("color:#8fd3ff;padding:4px 0 6px 0;")
            root.addWidget(lbl_command_status)

            btn_row = QHBoxLayout()

            btn_force_backup = QPushButton("Force Backup Now", dlg)
            btn_force_backup.setMinimumWidth(160)

            def _force_backup():
                try:
                    from datetime import datetime, timezone

                    issued_at = datetime.now(timezone.utc).isoformat()

                    self.parent().append_log(
                        f"Force backup command queued for seat {normalized_seat_id} at {issued_at}"
                    )

                    try:
                        lbl_command_status.setText(
                            "Last Command: Force Backup Requested — "
                            + issued_at
                            + "\nStatus: Pending"
                        )
                        lbl_command_status.setStyleSheet("color:#f5c400;padding:4px 0 6px 0;")
                    except Exception:
                        pass

                    _centered_message(
                        self,
                        "Force Backup",
                        f"Backup request queued for seat '{normalized_seat_id}'.\n\n"
                        "Device will execute backup when online.",
                    )
                except Exception as e:
                    try:
                        lbl_command_status.setText(
                            "Last Command: Force Backup Requested\nStatus: Failed to queue"
                        )
                        lbl_command_status.setStyleSheet("color:#ff8a8a;padding:4px 0 6px 0;")
                    except Exception:
                        pass

                    _centered_message(
                        self,
                        "Force Backup Error",
                        str(e),
                    )

            btn_force_backup.clicked.connect(_force_backup)
            btn_row.addWidget(btn_force_backup)
            btn_row.addStretch(1)

            btn_close = QPushButton("Close", dlg)
            btn_close.clicked.connect(dlg.accept)
            btn_row.addWidget(btn_close)

            root.addLayout(btn_row)

            dlg.exec()

        except Exception as e:
            _centered_message(
                self,
                "Health Check Failed",
                f"Could not run seat health check.\n\n{e}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
                QMessageBox.Icon.Critical,
            )

    def _build_business_export_bar(
        self,
        report_widget: QTextEdit,
        *,
        default_name: str,
        title: str,
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)

        btn_export_txt = QPushButton("Export TXT")
        btn_export_txt.clicked.connect(
            lambda: self.parent()._export_text_report(
                report_text=report_widget.toPlainText(),
                default_name=default_name,
                title=title,
                fmt="txt",
            )
        )
        row.addWidget(btn_export_txt)

        btn_export_md = QPushButton("Export MD")
        btn_export_md.clicked.connect(
            lambda: self.parent()._export_text_report(
                report_text=report_widget.toPlainText(),
                default_name=default_name,
                title=title,
                fmt="md",
            )
        )
        row.addWidget(btn_export_md)

        return row

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_business_watermark()

    def _apply_business_watermark(self, wm_size: int, opacity: float) -> None:
        if ASSET_WATERMARK.exists():
            pm = QPixmap(str(ASSET_WATERMARK))
            pm = pm.scaled(
                wm_size, wm_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.watermark.setPixmap(pm)

            eff = QGraphicsOpacityEffect(self.watermark)
            eff.setOpacity(opacity)
            self.watermark.setGraphicsEffect(eff)

        self._position_business_watermark()

    def _position_business_watermark(self) -> None:
        pm = self.watermark.pixmap()
        if pm is None:
            return

        x = (self.width() - pm.width()) // 2
        y = (self.height() - pm.height()) // 2 + 10
        self.watermark.setGeometry(x, y, pm.width(), pm.height())


class DevVaultQt(QMainWindow):
    _business_nas_required = False

    def __init__(self, *args, **kwargs):
        self._business_nas_required = True
        super().__init__(*args, **kwargs)
        self._business_nas_required = False

    def open_snapshot_comparison(self):
        from devvault_desktop.reporting import open_snapshot_comparison_ui
        open_snapshot_comparison_ui(parent=self)



    
    def _restart_devvault_app(self) -> None:
        import subprocess
        import sys
        from pathlib import Path
        from PySide6.QtWidgets import QApplication

        started = False
        last_error = ''

        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable], close_fds=False)
            else:
                repo_root = Path(__file__).resolve().parents[1]
                subprocess.Popen(
                    [sys.executable, '-m', 'devvault_desktop.qt_app'],
                    cwd=str(repo_root),
                    close_fds=False,
                )
            started = True
        except Exception as e:
            last_error = str(e)

        if not started:
            _centered_message(
                self,
                'Restart Failed',
                f'DevVault could not restart automatically.\n\n{last_error}',
            )
            return

        try:
            QApplication.quit()
        except Exception:
            try:
                self.close()
            except Exception:
                pass

    def _force_restart_for_runtime_refresh(self, reason: str) -> None:
        _centered_message(
            self,
            "Restarting DevVault",
            reason,
        )
        self._restart_devvault_app()

    def _initialize_business_nas_vault(self) -> None:
        from pathlib import Path
        from devvault_desktop.business_vault_bootstrap import (
            bootstrap_business_vault,
            BusinessVaultBootstrapError,
        )
        try:
            nas = str(get_business_nas_path() or "").strip()
        except Exception:
            nas = ""

        if not nas:
            _centered_message(
                self,
                "Initialize Vault Refused",
                "No Business NAS path is configured.",
            )
            return

        try:
            nas_path = Path(nas)

            # Ensure NAS root exists
            if not nas_path.exists():
                raise Exception("NAS path is not reachable. Verify network share.")

            # Ensure .devvault structure exists
            dv_root = nas_path / ".devvault"
            snapshots = dv_root / "snapshots"

            try:
                dv_root.mkdir(parents=True, exist_ok=True)
                snapshots.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise Exception(f"Failed to prepare vault structure: {e}")

            # Run bootstrap (final authority step)
            bootstrap_business_vault(nas_path)
        except BusinessVaultBootstrapError as e:
            _centered_message(
                self,
                "Initialize Vault Refused",
                str(e),
            )
            return
        except Exception as e:
            _centered_message(
                self,
                "Initialize Vault Failed",
                f"Unexpected error:\n\n{e}",
            )
            return

        self.append_log("Business NAS vault initialized.")

        self._force_restart_for_runtime_refresh(
            "Business NAS vault initialized. DevVault will now restart to load vault authority."
        )


    def _seat_activation_bootstrap(self) -> None:
        try:
            plan = ""
            try:
                status = self._current_license_status()
                plan = str(getattr(status, "plan", "") or "").lower()
            except Exception:
                plan = ""

            if "business" not in plan:
                try:
                    plan = str(self.license_line_state.text() or "").lower()
                except Exception:
                    plan = plan or ""

            if "business" not in plan:
                _centered_message(
                    self,
                    "Seat Activation",
                    "Business license required for seat activation."
                )
                return

            try:
                identity = get_business_seat_identity()
            except Exception:
                identity = None

            if not isinstance(identity, dict) or not str(identity.get("seat_id") or "").strip():
                try:
                    import json
                    import socket

                    assigned_email, ok = QInputDialog.getText(
                        self,
                        "Seat Activation",
                        "Enter your email:",
                        QLineEdit.Normal,
                        "",
                    )
                    if not ok or not str(assigned_email).strip():
                        return

                    invite_token, ok = QInputDialog.getText(
                        self,
                        "Seat Activation",
                        "Paste invite token:",
                        QLineEdit.Normal,
                        "",
                    )
                    if not ok or not str(invite_token).strip():
                        return

                    raw = read_installed_license_text()
                    if not raw.strip():
                        raise RuntimeError("Installed Business license not found.")

                    lic_doc = json.loads(raw)
                    lic_payload = lic_doc.get("payload", {}) if isinstance(lic_doc, dict) else {}

                    subscription_id = str(lic_payload.get("subscription_id") or "").strip()
                    customer_id = str(lic_payload.get("customer_id") or "").strip()

                    if not subscription_id:
                        raise RuntimeError("Installed license is missing subscription_id.")
                    if not customer_id:
                        raise RuntimeError("Installed license is missing customer_id.")

                    hostname = (
                        str(os.environ.get("COMPUTERNAME") or "").strip()
                        or str(os.environ.get("HOSTNAME") or "").strip()
                        or socket.gethostname().strip()
                    )

                    try:
                        response = enroll_business_seat(
                            subscription_id=subscription_id,
                            customer_id=customer_id,
                            assigned_email=str(assigned_email).strip(),
                            assigned_device_id=hostname,
                            assigned_hostname=hostname,
                            seat_label=hostname,
                            notes="",
                            invite_token=str(invite_token).strip(),
                            candidate_seat_id="",
                            display_name=hostname,
                            hostname=hostname,
                            app_version=_safe_app_version(),
                            installed_license=_collect_installed_license_context(),
                            vault_evidence=_collect_vault_evidence_summary(),
                            fingerprint_hash=_compute_device_fingerprint(),
                        )
                    except BusinessSeatApiError as e:
                        payload = dict(getattr(e, "payload", {}) or {})
                        if int(getattr(e, "status_code", 0) or 0) == 409 and str(payload.get("reason") or "").strip().lower() == "seat_identity_exists":
                            response = payload
                        else:
                            raise

                    seat_id = str(response.get("seat_id") or "").strip()
                    fleet_id = str(response.get("fleet_id") or "").strip()

                    if not seat_id:
                        raise RuntimeError("Seat activation did not return a seat_id.")

                    set_business_seat_identity(
                        seat_id=seat_id,
                        fleet_id=fleet_id,
                        subscription_id=subscription_id,
                        customer_id=customer_id,
                        assigned_email=str(response.get("assigned_email") or assigned_email).strip(),
                        assigned_device_id=str(response.get("assigned_device_id") or hostname).strip(),
                        assigned_hostname=str(response.get("assigned_hostname") or hostname).strip(),
                        seat_label=str(response.get("seat_label") or hostname).strip(),
                    )

                    self._force_restart_for_runtime_refresh(
                        "Seat activation completed successfully. DevVault will now restart to load the enrolled seat identity."
                    )
                except Exception as exc:
                    _centered_message(
                        self,
                        "Seat Activation Error",
                        f"Seat enrollment failed.\n\n{exc}"
                    )
                return

            self.open_business_tools()

        except Exception as exc:
            _centered_message(
                self,
                "Seat Activation Error",
                str(exc)
            )

    def _business_subscription_id(self) -> str:
        value = os.environ.get("DEVVAULT_BUSINESS_SUBSCRIPTION_ID", "").strip()
        if value:
            return value

        try:
            identity = get_business_seat_identity()
        except Exception:
            identity = None

        if isinstance(identity, dict):
            value = str(identity.get("subscription_id") or "").strip()
            if value:
                return value

        try:
            session = self._current_business_admin_session()
        except Exception:
            session = None

        if isinstance(session, dict):
            value = str(session.get("subscription_id") or "").strip()
            if value:
                return value

        raise RuntimeError(
            "Business subscription id is unavailable from runtime context. "
            "Re-enroll this device seat or sign in again."
        )

    def _business_customer_id(self) -> str:
        value = os.environ.get("DEVVAULT_BUSINESS_CUSTOMER_ID", "").strip()
        if value:
            return value

        try:
            identity = get_business_seat_identity()
        except Exception:
            identity = None

        if isinstance(identity, dict):
            value = str(identity.get("customer_id") or "").strip()
            if value:
                return value

        try:
            session = self._current_business_admin_session()
        except Exception:
            session = None

        if isinstance(session, dict):
            value = str(session.get("customer_id") or "").strip()
            if value:
                return value

        raise RuntimeError(
            "Business customer id is unavailable from runtime context. "
            "Re-enroll this device seat or sign in again."
        )

    def _build_business_fetch_request(self):
        registry = SeatRegistryEngine(registry_root=config_dir())
        registry_records = list(registry.sync())

        active_server_ids: tuple[str, ...] = ()
        active_server_match_keys: set[str] = set()

        try:
            subscription_id = self._business_subscription_id()
            api_payload = list_business_seats(subscription_id)
            live_rows = normalize_business_seat_rows(api_payload)

            active_rows = [
                row
                for row in live_rows
                if str(row.seat_status or "").strip().lower() == "active"
                and str(row.seat_id or "").strip()
            ]

            active_server_ids = tuple(
                str(row.seat_id).strip()
                for row in active_rows
            )

            for row in active_rows:
                assigned_hostname = str(getattr(row, "assigned_hostname", "") or "").strip().upper()
                assigned_device_id = str(getattr(row, "assigned_device_id", "") or "").strip().upper()

                if assigned_hostname:
                    active_server_match_keys.add(assigned_hostname)
                if assigned_device_id:
                    active_server_match_keys.add(assigned_device_id)

        except Exception:
            active_server_ids = ()
            active_server_match_keys = set()

        matched_registry_records = []
        if active_server_match_keys:
            for seat in registry_records:
                seat_id = str(getattr(seat, "seat_id", "") or "").strip().upper()
                hostnames = {
                    str(x).strip().upper()
                    for x in getattr(seat, "hostnames", ()) or ()
                    if str(x).strip()
                }

                if seat_id in active_server_match_keys or bool(hostnames & active_server_match_keys):
                    matched_registry_records.append(seat)

        if matched_registry_records:
            registry_scope_records = matched_registry_records
        else:
            registry_scope_records = registry_records

        roots: set[Path] = set()
        for seat in registry_scope_records:
            for endpoint in getattr(seat, "vault_endpoints", ()) or ():
                try:
                    roots.add(Path(endpoint).expanduser())
                except Exception:
                    continue

        if active_server_ids:
            selected_seats = tuple(sorted(active_server_ids))
        else:
            selected_seats = tuple(
                str(seat.seat_id).strip()
                for seat in registry_records
                if str(getattr(seat, "seat_id", "") or "").strip()
            )

        business_nas = str(get_business_nas_path() or "").strip()
        nas_roots = (Path(business_nas),) if business_nas else tuple()

        return FetchRequest(
            scope_id="local-business-dashboard",
            vault_roots=nas_roots,
            selected_seats=selected_seats,
            include_details=True,
        )

    def _dashboard_snapshot(self):
        try:
            from devvault_desktop.business_fetchers import (
                SeatProtectionStateFetcher,
                FleetHealthSummaryFetcher,
                OrganizationRecoveryAuditFetcher,
                FetchRequest,
            )
            import shutil
            from pathlib import Path

            request = self._build_business_fetch_request()

            seat_result = SeatProtectionStateFetcher().fetch(request)
            fleet_result = FleetHealthSummaryFetcher().fetch(request)
            org_result = OrganizationRecoveryAuditFetcher().fetch(request)

            seat_raw = dict(seat_result.raw_payload or {})
            org_raw = dict(org_result.raw_payload or {})

            api_payload = {}
            try:
                subscription_id = self._business_subscription_id()
                api_payload = list_business_seats(subscription_id)
                if not isinstance(api_payload, dict):
                    api_payload = {}
            except Exception:
                api_payload = {}

            attention_seats: list[str] = []
            try:
                for finding in tuple(getattr(seat_result, "findings", ()) or ()):
                    key = str(getattr(finding, "key", "") or "").strip()
                    if key.startswith("seat_degraded:") or key.startswith("seat_never:") or key.startswith("seat_unknown:"):
                        seat_id = key.split(":", 1)[1].strip()
                        if seat_id and seat_id not in attention_seats:
                            attention_seats.append(seat_id)
            except Exception:
                attention_seats = []

            nas_path = ""
            nas_name = "Not configured"
            nas_free_pct = "?"
            nas_used_pct = "?"
            nas_state = "not_configured"

            try:
                nas_path = str(get_business_nas_path() or "").strip()
            except Exception:
                nas_path = ""

            if nas_path:
                nas_name = Path(nas_path.rstrip("\\/")).name or nas_path
                try:
                    usage = shutil.disk_usage(nas_path)
                    total = int(usage.total or 0)
                    free = int(usage.free or 0)
                    if total > 0:
                        free_pct = round((free / total) * 100)
                        used_pct = 100 - free_pct
                        nas_free_pct = f"{free_pct}% free"
                        nas_used_pct = f"{used_pct}% used"
                        nas_state = "ok"
                    else:
                        nas_state = "unknown"
                except Exception:
                    nas_state = "unreachable"

            seat_limit = 0
            try:
                seat_limit = int(
                    api_payload.get("seat_limit")
                    or api_payload.get("max_seats")
                    or api_payload.get("licensed_seat_limit")
                    or api_payload.get("subscription_seat_limit")
                    or 0
                )
            except Exception:
                seat_limit = 0

            # Server-authoritative active seat count ONLY
            try:
                active_seat_count = int(
                    api_payload.get("active_seat_count")
                    or api_payload.get("total_active_seats")
                    or api_payload.get("seats_used")
                    or 0
                )
            except Exception:
                active_seat_count = 0

            return {
                "seats_protected": seat_raw.get("protected", "?"),
                "seats_total": len(request.selected_seats),
                "active_seat_count": active_seat_count,
                "seat_limit": seat_limit,
                "fleet_severity": fleet_result.severity or "unknown",
                "risky_vaults": (
                    int(seat_raw.get("degraded", 0) or 0)
                    + int(seat_raw.get("never", 0) or 0)
                    + int(seat_raw.get("unknown", 0) or 0)
                ),
                "attention_seats": tuple(attention_seats),
                "nas_name": nas_name,
                "nas_path": nas_path,
                "nas_free_pct": nas_free_pct,
                "nas_used_pct": nas_used_pct,
                "nas_state": nas_state,
            }

        except Exception as e:
            import traceback
            traceback.print_exc()

            return {
                "seats_protected": 0,
                "seats_total": 0,
                "active_seat_count": 0,
                "fleet_severity": "ERROR",
                "risky_vaults": 0,
                "nas_name": "ERROR",
                "nas_path": "",
                "nas_free_pct": "?",
                "nas_used_pct": "?",
                "nas_state": "error",
            }

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("TSW", "DevVault")
        self._startup_popup = None
        self._last_scan_payload: dict | None = None
        self._startup_popup_shown = False
        self._business_nas_startup_prompted = False
        self._business_admin_session: dict | None = None

        raw_vault = self.settings.value("vault_path", "", type=str) or ""
        self.vault_path = self._normalize_vault_root(raw_vault)

        try:
            persisted_business_nas = self._normalize_vault_root(get_business_nas_path())
        except Exception:
            persisted_business_nas = ""

        if persisted_business_nas:
            self.vault_path = persisted_business_nas


        if not self.vault_path:
            drives = self._available_drive_roots()
            self.vault_path = drives[0] if drives else "C:\\"
        self.settings.setValue("vault_path", self.vault_path)
        try:
            set_vault_dir(self.vault_path)
        except Exception:
            pass

        # Recover from prior crash/kill: remove any leftover .incomplete-* staging dirs
        # from the canonical snapshot staging location.
        try:
            import shutil

            snapshot_root = None

            cleanup_vault = ""
            try:
                if self._business_nas_mode_active():
                    cleanup_vault = str(get_business_nas_path() or "").strip()
                else:
                    cleanup_vault = str(self.vault_path or "").strip()
            except Exception:
                cleanup_vault = str(self.vault_path or "").strip()

            if cleanup_vault:
                snapshot_root = Path(cleanup_vault) / ".devvault" / "snapshots"

            if snapshot_root is not None and snapshot_root.exists():
                for p in snapshot_root.iterdir():
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

        self.tray_icon = None
        self.tray_menu = None
        self.tray_status_action = None
        self._tray_status_text = "Protection Status: Checking..."
        self._tray_pulse_on = False
        self._tray_current_state = "checking"
        self._tray_pulse_timer = QTimer(self)

        self.setMinimumSize(900, 600)

        # Protection header state
        self._protection_state = "PROTECTED"
        self._unprotected_count = 0

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
                background: transparent;
                border: 1px solid rgba(120,120,120,140);
                padding: 10px 16px;
                min-width: 160px;
            }}
            QPushButton:hover {{
                border-color: #e6c200;
                background: rgba(255,215,0,0.05);
            }}
            QPushButton:pressed {{
                background: rgba(255,215,0,0.10);
            }}
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
        self.protection_status_label = QLabel("STATUS: PROTECTED")
        self.protection_status_label.setAlignment(Qt.AlignHCenter)
        self.protection_status_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.protection_status_label.setStyleSheet("color: #22c55e;")

        self.protection_status_message = QLabel("Checking protection status...")
        self.protection_status_message.setAlignment(Qt.AlignHCenter)
        self.protection_status_message.setFont(QFont("Segoe UI", 10))
        self.protection_status_message.setStyleSheet("color: rgba(220,220,220,190);")

        title = QLabel("🔒  D E V V A U L T  🔒")
        title.setAlignment(Qt.AlignHCenter)
        title.setFont(QFont("Segoe UI", 26, QFont.Bold))

        slogan = QLabel(
            "DevVault is a safety system for people whose work cannot be replaced."
        )
        slogan.setAlignment(Qt.AlignHCenter)
        slogan.setFont(QFont("Segoe UI", 11))

        self.license_panel = QFrame()
        self.license_panel.setFixedWidth(300)
        self.license_panel.setStyleSheet(
            '''
            QFrame {
                background: transparent;
                border: none;
            }
            '''
        )
        license_layout = QVBoxLayout(self.license_panel)
        license_layout.setContentsMargins(12, 8, 12, 8)
        license_layout.setSpacing(0)

        self.license_line_state = QLabel("• PLAN: —\n• LICENSE: UNKNOWN\n• SEAT#: —")
        self.license_line_state.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.license_line_state.setFont(QFont("Consolas", 14, QFont.Bold))
        self.license_line_state.setStyleSheet("margin-top: 18px;")

        self.license_line_licensee = QLabel("Licensee: —")
        self.license_line_licensee.hide()

        self.license_line_expiration = QLabel("Expiration: —")
        self.license_line_expiration.hide()

        self.license_line_validation = QLabel("Last / Next Validation: —")
        self.license_line_validation.hide()

        license_layout.addWidget(self.license_line_state)

        top_left_row = QHBoxLayout()
        top_left_row.setContentsMargins(0, 0, 0, 0)
        top_left_row.addWidget(self.license_panel, 0, Qt.AlignLeft)
        top_left_row.addStretch(1)

        self.btn_settings = QPushButton("Tools")
        self.btn_settings.setFixedWidth(140)
        self.btn_settings.clicked.connect(self.open_settings_menu)
        top_left_row.addWidget(self.btn_settings, 0, Qt.AlignRight)

        main.addLayout(top_left_row)

        main.addWidget(self.protection_status_label)
        main.addWidget(self.protection_status_message)
        main.addWidget(title)
        main.addWidget(slogan)

        # --- Backup Location selector (ABOVE the location box) ---
        change_container = QVBoxLayout()
        change_container.setSpacing(0)
        change_container.setAlignment(Qt.AlignHCenter)

        self.vault_combo = QComboBox()
        self.vault_combo.setFixedWidth(BTN_W)
        self.vault_combo.setEditable(False)
        
        change_container.addWidget(self.vault_combo)
        
        main.addLayout(change_container)
        main.addSpacing(-6)
        main.addSpacing(-6)
        self.vault_combo.setStyleSheet(
            """
            QComboBox {
                font-weight: bold;
                color: #e6c200;
                background: transparent;
                border: 1px solid rgba(120,120,120,140);
                padding: 10px;
                }
            QComboBox:hover { border-color: #e6c200; background: rgba(255,215,0,0.05); }
            QComboBox QAbstractItemView {
                font-weight: bold;
                color: #e6c200;
                background: transparent;
                selection-background-color: #222;
                border: 1px solid rgba(120,120,120,140);
            }
        """
        )
        change_row = QHBoxLayout()
        change_row.setAlignment(Qt.AlignHCenter)
        change_row.addWidget(self.vault_combo)

        main.addLayout(change_row)

        # --- Smoked glass box (match width of two buttons) ---
        glass = QFrame()
        glass.setFixedWidth(BTN_W + 120)
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
        glass_layout.setContentsMargins(0, 10, 0, 0)
        glass_layout.setSpacing(0)

        self.vault_line_1 = QLabel(r"Current backup location: E:\ ")
        self.vault_line_1.setAlignment(Qt.AlignHCenter)
        self.vault_line_1.setWordWrap(True)
        self.vault_line_1.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.vault_line_1.setStyleSheet("background: transparent; border: none; padding-left: 10px; padding-right: 10px;")

        # No inner bubble — just text
        self.vault_line_2 = QLabel(r"")
        self.vault_line_2.setAlignment(Qt.AlignHCenter)
        self.vault_line_2.setWordWrap(True)
        self.vault_line_2.setStyleSheet("background: transparent; border: none; padding-left: 10px; padding-right: 10px;")
        glass_layout.addWidget(self.vault_line_1)
        glass_layout.addWidget(self.vault_line_2)
        self.update_vault_display()

        main.addWidget(glass, 0, Qt.AlignHCenter)
        # Buttons row (where Change Vault used to be)
        row = QHBoxLayout()
        row.setSpacing(24)
        row.setAlignment(Qt.AlignHCenter)

        self.btn_backup = QPushButton("Single File Backup")
        self.btn_backup.setFixedWidth(BTN_W)

        self.btn_restore = QPushButton("Restore Backup")
        self.btn_restore.setFixedWidth(BTN_W)

        self.btn_scan = QPushButton("Full Scan")
        self.btn_scan.setFixedWidth(BTN_W)

        self.btn_install_license = QPushButton("Install License")
        self.btn_install_license.setFixedWidth(BTN_W)

        self.btn_validate_license = QPushButton("Validate License Now")
        self.btn_validate_license.setFixedWidth(BTN_W)

        row.addWidget(self.btn_backup)
        self.btn_backup.clicked.connect(self.make_backup)

        row.addWidget(self.btn_restore)
        self.btn_restore.clicked.connect(self.restore_backup)

        row.addWidget(self.btn_scan)
        self.btn_scan.clicked.connect(self.run_scan)

        # License actions live in Settings menu only
        self.btn_install_license.clicked.connect(self.install_license)
        self.btn_validate_license.clicked.connect(self.validate_license_now)

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
                background: rgba(0,0,0,100);
                border: 1px solid rgba(120,120,120,140);
                color: #1FEB1C;
                padding: 12px;
            }
        """
        )
        self.log.setFont(QFont("Consolas", 11))
        startup_log = (
            "Welcome to DevVault.\n"
            "Trustware: if anything looks unsafe, DevVault refuses.\n"
            "Choose an action: Single File Backup or Restore Backup.\n"
            "Vault open and ready....\n"
        )
        try:
            st = check_license()
            startup_log += f"\nLicense state: {st.state}\n{st.message}\n"

            self._startup_popup = None

            # Restricted-mode operator warning
            if st.state == "RESTRICTED":
                self._startup_popup = (
                    "License Validation Required",
                    (
                        "License validation is overdue beyond the grace period.\n\n"
                        "Protected actions are disabled until license validation succeeds.\n\n"
                        "Restore operations remain available.\n"
                        "Run 'Validate License Now' once internet connectivity is available."
                    ),
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Critical,
                )

            # Invalid-license operator warning
            if st.state == "INVALID":
                self._startup_popup = (
                    "Invalid License",
                    (
                        "The installed DevVault license is invalid.\n\n"
                        f"{st.message}\n\n"
                        "Backups are disabled. Restore operations remain available.\n"
                        "Install a valid DevVault license file to continue."
                    ),
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Critical,
                )

            # Unlicensed operator prompt
            if st.state == "UNLICENSED":
                self._startup_popup = (
                    "DevVault License Required",
                    (
                        "No DevVault license is installed.\n\n"
                        f"{st.message}\n"
                        "Backups are disabled. Restore operations remain available.\n\n"
                        "Use 'Install License' to add your DevVault license file."
                    ),
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Information,
                )

            # Grace-mode operator warning
            if st.state == "GRACE":
                self._startup_popup = (
                    "License Validation Overdue",
                    (
                        "License validation is overdue.\n\n"
                        "DevVault is running in GRACE mode.\n"
                        "Backups remain available, but if validation does not succeed\n"
                        "this system may enter restricted mode.\n\n"
                        "Connect to the internet and run 'Validate License Now'."
                    ),
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Warning,
                )

        except Exception as e:
            startup_log += f"\nLicense status check failed: {e}\n"

        self.log.setText(startup_log)
        self._refresh_license_panel()
        self.setFocus()
        self.setFocus()
        main.addWidget(self.log, stretch=1)
        # Footer
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.setSpacing(12)

        footer_left = QLabel("DevVault — Built by Trustware Technologies")
        footer_left.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        footer_left.setMaximumWidth(240)
        footer_left.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        footer_left.setStyleSheet("color: rgba(220,220,220,150); background: transparent; border: none; font-size: 11px;")

        footer_right = QLabel("© 2026 TSW Technologies LLC")
        footer_right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        footer_right.setMaximumWidth(210)
        footer_right.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        footer_right.setStyleSheet("color: rgba(220,220,220,150); background: transparent; border: none; font-size: 11px;")

        self.footer_license_details = QLabel("Licensee: — | Expiration: — | Last Validation: — | Next Validation: —")
        self.footer_license_details.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.footer_license_details.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.footer_license_details.setStyleSheet("color: rgba(220,220,220,185); background: transparent; border: none; font-size: 11px;")

        footer_row.addWidget(footer_left, 0)
        footer_row.addSpacing(8)
        footer_row.addWidget(self.footer_license_details, 1)
        footer_row.addSpacing(8)
        footer_row.addWidget(footer_right, 0)
        main.addLayout(footer_row)

        self._refresh_license_panel()
        self._init_tray()
        self._set_tray_state("checking")

        # Ensure watermark is behind everything
        self.watermark.lower()

        self._populate_vault_combo()

        self.vault_combo.currentTextChanged.connect(self.change_vault)
        self._apply_vault_ui_mode()
        QTimer.singleShot(0, self._run_startup_validation_if_due)
        QTimer.singleShot(250, self._run_startup_protection_check)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_watermark()

    def showEvent(self, event) -> None:
        super().showEvent(event)

        if not getattr(self, "_business_nas_startup_prompted", False):
            self._business_nas_startup_prompted = True
            QTimer.singleShot(700, self._show_business_nas_onboarding_if_required)

        if getattr(self, "_startup_popup_shown", False):
            return
        if not getattr(self, "_startup_popup", None):
            return

        self._startup_popup_shown = True
        QTimer.singleShot(250, self._show_startup_popup_if_ready)

    def _show_startup_popup_if_ready(self) -> None:
        popup = getattr(self, "_startup_popup", None)
        if not popup:
            return

        try:
            self.raise_()
            self.activateWindow()
            self.repaint()
        except Exception:
            pass

        try:
            title, text, buttons, default_button, icon = popup
            _centered_message(
                self,
                title,
                text,
                buttons,
                default_button,
                icon,
            )
        except Exception:
            pass

    def _business_nas_startup_required(self) -> bool:
        try:
            seat_identity = get_business_seat_identity()
        except Exception:
            seat_identity = None

        license_kind = None
        try:
            st = check_license()
            license_kind = getattr(st, "plan", None) or getattr(st, "tier", None) or getattr(st, "kind", None)
        except Exception:
            license_kind = None

        business_mode = bool(seat_identity) or str(license_kind or "").strip().lower() == "business"
        if not business_mode:
            return False

        try:
            current_nas = str(get_business_nas_path() or "").strip()
        except Exception:
            current_nas = ""

        return not bool(current_nas)

    def _show_business_nas_onboarding_if_required(self) -> None:
        if not self._business_nas_startup_required():
            return

        try:
            dlg = BusinessHubDialog(self)
            dlg._refresh_business_nas_surface()
            dlg._auto_refresh_nas_state()
            dlg.surface.setCurrentWidget(dlg.nas_widget)
            dlg._maybe_force_business_nas_onboarding(
                reason="Business seat detected at startup with no NAS configured.",
                prompt_once=False,
            )
            dlg.exec()
        except Exception as e:
            try:
                self.append_log(f"Business NAS onboarding startup prompt failed: {e}")
            except Exception:
                pass

    def _make_tinted_icon(self, color_hex: str) -> QIcon:
        try:
            if ASSET_ICON.exists():
                pix = QPixmap(str(ASSET_ICON))
            else:
                pix = QPixmap(32, 32)
                pix.fill(Qt.transparent)

            if pix.isNull():
                pix = QPixmap(32, 32)
                pix.fill(Qt.transparent)

            tinted = QPixmap(pix.size())
            tinted.fill(Qt.transparent)

            painter = QPainter(tinted)
            painter.drawPixmap(0, 0, pix)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(tinted.rect(), QColor(color_hex))
            painter.end()

            return QIcon(tinted)
        except Exception:
            return self.windowIcon()

    def _show_from_tray(self) -> None:
        try:
            self.showNormal()
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

    def _init_tray(self) -> None:
        try:
            if self.tray_icon is not None:
                return

            self.tray_icon = QSystemTrayIcon(self)
            self.tray_menu = QMenu(self)

            self.tray_status_action = QAction("Protection Status: Checking...", self)
            self.tray_status_action.setEnabled(False)

            show_action = QAction("Show DevVault", self)
            show_action.triggered.connect(self._show_from_tray)

            exit_action = QAction("Exit DevVault", self)
            exit_action.triggered.connect(self.close)

            self.tray_menu.addAction(self.tray_status_action)
            self.tray_menu.addSeparator()
            self.tray_menu.addAction(show_action)
            self.tray_menu.addAction(exit_action)

            self.tray_icon.setContextMenu(self.tray_menu)
            self.tray_icon.activated.connect(
                lambda reason: self._show_from_tray()
                if reason == QSystemTrayIcon.ActivationReason.Trigger
                else None
            )
            self.tray_icon.setIcon(self._make_tinted_icon("#facc15"))
            self.tray_icon.setToolTip("DevVault Protection Status")
            self.tray_icon.show()

            self._tray_pulse_timer.setInterval(700)
            self._tray_pulse_timer.timeout.connect(self._toggle_tray_pulse)
        except Exception as e:
            try:
                self.append_log(f"Tray init warning: {e}")
            except Exception:
                pass

    def _update_tray_status_text(self, text: str) -> None:
        self._tray_status_text = text
        try:
            if self.tray_status_action is not None:
                self.tray_status_action.setText(text)
            if self.tray_icon is not None:
                self.tray_icon.setToolTip("DevVault\n" + text)
        except Exception:
            pass

    def _stop_tray_pulse(self) -> None:
        try:
            self._tray_pulse_timer.stop()
        except Exception:
            pass
        self._tray_pulse_on = False

    def _toggle_tray_pulse(self) -> None:
        if self.tray_icon is None:
            return
        self._tray_pulse_on = not self._tray_pulse_on
        icon = self._make_tinted_icon("#ff3b30" if self._tray_pulse_on else "#7a120d")
        self.tray_icon.setIcon(icon)

    def _set_tray_state(self, state: str) -> None:
        self._tray_current_state = state
        if self.tray_icon is None:
            return

        if state == "protected":
            self._stop_tray_pulse()
            self.tray_icon.setIcon(self._make_tinted_icon("#22c55e"))
            self._update_tray_status_text("✓ Protected")
        elif state == "unprotected":
            self._update_tray_status_text("⚠ Unprotected items detected")
            if not self._tray_pulse_timer.isActive():
                self._tray_pulse_on = False
                self._tray_pulse_timer.start()
                self._toggle_tray_pulse()
        else:
            self._stop_tray_pulse()
            self.tray_icon.setIcon(self._make_tinted_icon("#facc15"))
            self._update_tray_status_text("Checking protection status...")


    def _resolve_business_protection_banner_state(self) -> dict | None:
        try:
            if not self._business_nas_mode_active():
                return None
        except Exception:
            return None

        try:
            identity = get_business_seat_identity()
        except Exception:
            identity = None

        if not isinstance(identity, dict):
            return None

        seat_id = str(identity.get("seat_id") or "").strip()
        if not seat_id:
            return None

        try:
            nas_path = str(get_business_nas_path() or "").strip()
        except Exception:
            nas_path = ""

        if not nas_path:
            return {
                "state": "unknown",
                "seat_id": seat_id,
                "detail": "Business NAS is not configured.",
                "last_backup_at": "",
            }

        try:
            import json
            from datetime import datetime, timezone

            index_path = Path(nas_path) / ".devvault" / "snapshot_index.json"
            latest = None

            if index_path.exists():
                raw = json.loads(index_path.read_text(encoding="utf-8"))
                for row in raw.get("snapshots", []) or []:
                    if not isinstance(row, dict):
                        continue

                    row_seat_id = str(row.get("seat_id") or "").strip()
                    if row_seat_id != seat_id:
                        continue

                    created_at = str(row.get("created_at") or "").strip()
                    if latest is None:
                        latest = row
                        continue

                    prev_created = str(latest.get("created_at") or "").strip()
                    if created_at > prev_created:
                        latest = row

            if not latest:
                return {
                    "state": "never_backed_up",
                    "seat_id": seat_id,
                    "detail": "This Business seat has never completed a NAS backup.",
                    "last_backup_at": "",
                }

            created_raw = str(latest.get("created_at") or "").strip()
            state = "protected"

            try:
                created_dt = datetime.fromisoformat(created_raw)
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                age_seconds = (datetime.now(timezone.utc) - created_dt).total_seconds()
                if age_seconds > (72 * 3600):
                    state = "degraded"
            except Exception:
                state = "protected"

            detail = "This Business seat is protected by recent NAS snapshot evidence."
            if state == "degraded":
                detail = "This Business seat needs backup. NAS snapshot evidence is stale."

            return {
                "state": state,
                "seat_id": seat_id,
                "detail": detail,
                "last_backup_at": created_raw,
            }

        except Exception as e:
            return {
                "state": "unknown",
                "seat_id": seat_id,
                "detail": f"Business protection status could not be resolved from NAS authority: {e}",
                "last_backup_at": "",
            }

    def _update_protection_status(self, count: int) -> None:
        self._unprotected_count = max(0, int(count or 0))
        if self._unprotected_count > 0:
            self._protection_state = "UNPROTECTED"
            self.protection_status_label.setText("STATUS: UNPROTECTED")
            self.protection_status_label.setStyleSheet("color: #fb923c;")
            noun = "item" if self._unprotected_count == 1 else "items"
            self.protection_status_message.setText(
                f"{self._unprotected_count} new {noun} detected — backup recommended."
            )
            self._set_tray_state("unprotected")
        else:
            self._protection_state = "PROTECTED"
            self.protection_status_label.setText("STATUS: PROTECTED")
            self.protection_status_label.setStyleSheet("color: #22c55e;")
            self.protection_status_message.setText("All detected work is protected.")
            self._set_tray_state("protected")


    def _cleanup_startup_scan_thread(self) -> None:
        self._startup_scan_worker = None
        self._startup_scan_thread = None

    def _run_startup_protection_check(self) -> None:
        if getattr(self, "_startup_scan_thread", None) is not None:
            return

        try:
            self.protection_status_message.setText("Checking protection status...")
            self._set_tray_state("checking")
        except Exception:
            pass

        self._startup_scan_thread = QThread()
        business_mode = False
        business_nas_path = ""
        try:
            business_mode = bool(self._business_nas_mode_active())
        except Exception:
            business_mode = False

        if business_mode:
            try:
                business_nas_path = str(get_business_nas_path() or "").strip()
            except Exception:
                business_nas_path = ""

        self._startup_scan_worker = _ScanWorker(
            business_mode=business_mode,
            business_nas_path=business_nas_path,
        )
        self._startup_scan_worker.moveToThread(self._startup_scan_thread)

        self._startup_scan_thread.started.connect(self._startup_scan_worker.run)
        self._startup_scan_worker.done.connect(self._on_startup_scan_done, type=Qt.QueuedConnection)
        self._startup_scan_worker.error.connect(self._on_startup_scan_err, type=Qt.QueuedConnection)

        self._startup_scan_thread.finished.connect(self._startup_scan_worker.deleteLater)
        self._startup_scan_thread.finished.connect(self._startup_scan_thread.deleteLater)
        self._startup_scan_thread.finished.connect(self._cleanup_startup_scan_thread, type=Qt.QueuedConnection)

        self._startup_scan_thread.start()

    def _on_startup_scan_done(self, payload: dict) -> None:
        uncovered = payload.get("uncovered") or []
        self._update_protection_status(len(uncovered))
        try:
            if uncovered:
                mark_unprotected(len(uncovered))
            else:
                mark_protected()
        except Exception as e:
            self.append_log(f"Warning: could not update reminder state: {e}")
        try:
            if uncovered:
                self.append_log(f"Startup protection check: {len(uncovered)} unprotected item(s) detected.")
            else:
                self.append_log("Startup protection check: all detected work is protected.")
        except Exception:
            pass

        try:
            if getattr(self, "_startup_scan_thread", None) is not None:
                self._startup_scan_thread.quit()
        except Exception:
            pass

    def _on_startup_scan_err(self, msg: str) -> None:
        try:
            self.append_log(f"Startup protection check failed: {msg}")
            self.protection_status_message.setText("Run Scan to refresh protection status.")
        except Exception:
            pass

        try:
            if getattr(self, "_startup_scan_thread", None) is not None:
                self._startup_scan_thread.quit()
        except Exception:
            pass

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

    def _refresh_license_panel(self) -> None:
        def _fmt_dt(dt_obj) -> str:
            if not dt_obj:
                return "—"
            try:
                return dt_obj.strftime("%Y-%m-%d %H:%M")
            except Exception:
                return str(dt_obj)

        try:
            st = check_license()
        except Exception as e:
            self.license_line_state.setText("• PLAN: —\n• LICENSE: ERROR\n• SEAT#: —")
            self.license_line_state.setStyleSheet("color: #ff4d4f; background: transparent; border: none;")
            self.license_line_licensee.setText("")
            self.license_line_expiration.setText("")
            self.license_line_validation.setText(f"License check failed: {e}")
            if hasattr(self, "footer_license_details"):
                self.footer_license_details.setText("Licensee: — | Expiration: — | Last Validation: — | Next Validation: —")
            return

        state_text = str(st.state)
        color_map = {
            "VALID": "#22c55e",
            "GRACE": "#f59e0b",
            "RESTRICTED": "#fb923c",
            "INVALID": "#ff4d4f",
            "UNLICENSED": "#ff4d4f",
        }
        color = color_map.get(state_text, "#e6c200")

        plan_text = str(getattr(st, "plan", "") or "—").upper()
        seats_value = getattr(st, "seats", None)
        seat_text = str(seats_value) if seats_value not in (None, "") else "—"

        self.license_line_state.setText(
            f"• PLAN: {plan_text}\n• LICENSE: {state_text}\n• SEAT#: {seat_text}"
        )
        self.license_line_state.setStyleSheet(f"color: {color}; background: transparent; border: none;")

        self.license_line_licensee.setText("")
        self.license_line_expiration.setText("")
        self.license_line_validation.setText("")

        exp = _fmt_dt(st.expires_at_utc)
        last_val = _fmt_dt(st.last_validated_at_utc)
        next_val = _fmt_dt(st.next_checkin_due_utc)

        if hasattr(self, "footer_license_details"):
            self.footer_license_details.setText(
                f"Licensee: {st.licensee or '—'} | Expiration: {exp} | Last Validation: {last_val} | Next Validation: {next_val}"
            )

    def _run_startup_validation_if_due(self) -> None:



        try:
            st = check_license()
        except Exception as e:
            self.append_log(f"Startup validation skipped: license check failed: {e}")
            return

        if st.state == "GRACE":
            self.append_log("Validation due: contacting Trustware validation service...")
            try:
                result = validate_now()
                self.append_log(result.message)
                self._refresh_license_panel()
            except Exception as e:
                self.append_log(f"Startup validation failed: {e}")
                self._refresh_license_panel()

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

            try:
                existing_text = read_installed_license_text()
                if existing_text:
                    existing_claims = verify_license_string(existing_text)
                    if existing_claims.license_id == claims.license_id:
                        self.append_log("License install skipped: this license is already installed.")
                        try:
                            _centered_message(
                                self,
                                "License Already Installed",
                                "This license is already installed.",
                            )
                        except Exception:
                            pass
                        self._refresh_license_panel()
                        return True
            except Exception:
                pass

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

        save_state(
            license_id=claims.license_id,
            last_validated_at=datetime.now(timezone.utc),
        )

        self.append_log(f"License installed: {dest}")
        self.append_log(f"Licensed to {claims.licensee} until {claims.expires_at.astimezone(timezone.utc).isoformat()}")
        self._refresh_license_panel()

        try:
            _centered_message(
                self,
                "License Installed",
                (
                    f"License installed successfully.\\n\\n"
                    f"Licensed to: {claims.licensee}\\n"
                    f"Installed at: {dest}"
                ),
            )
        except Exception:
            pass

        # FORCE RESTART AFTER LICENSE INSTALL (CORRECT LOCATION)
        try:
            self._force_restart_for_runtime_refresh(
                "License installed successfully. DevVault will now restart to load license state."
            )
        except Exception:
            pass

        return True


    

    def _resolve_refusal_ui(self, payload: dict) -> tuple[str, str]:
        code = str(payload.get("code") or "").strip().upper()
        msg = str(payload.get("operator_message") or payload.get("error") or "Operation refused.").strip()

        if code == "NAS_UNREACHABLE":
            return "NAS Unreachable", msg

        if code == "NAS_PATH_INVALID":
            return "NAS Path Invalid", msg

        if code == "NAS_AUTH_FAILED":
            return "NAS Access Denied", msg

        if code == "VAULT_KEY_INVALID":
            return "Vault Security Failure", msg

        if code == "CAPACITY_DENIED":
            return "Vault Capacity Denied", msg

        if code == "DEVICE_DISCONNECTED":
            return "Device Disconnected", msg

        if code == "LICENSE_BLOCKED":
            return "License Blocked", msg

        if code == "OPERATOR_CANCELLED":
            return "Operation Cancelled", msg

        return "Operation Failed", msg

    def _ui_critical(self, title: str, text: str) -> None:
        # Always show critical popups from the UI thread.
        def _show() -> None:
            try:
                _centered_message(
                    self,
                    title,
                    text,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Critical,
                )
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

            # Allow UNC roots for Business NAS vaults
            if s.startswith("\\"):
                parts = s.split("\\")
                if len(parts) >= 4:
                    return "\\" + parts[2] + "\\" + parts[3] + "\\"
                return ""

            if len(s) < 3 or s[1:3] != ":\\":
                return ""

            if any(part.lower() == ".devvault" for part in p.parts):
                return ""

            return s[:3]
        except Exception:
            return ""

    def _available_drive_roots(self) -> list[str]:
        roots: list[str] = []
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            root = f"{letter}:\\"
            try:
                if Path(root).exists():
                    roots.append(root)
            except Exception:
                pass
        return roots

    def _normalize_business_nas_root(self, raw: str) -> str:
        try:
            value = str(raw or "").strip()
            if not value:
                return ""
            if not value.startswith("\\\\"):
                return ""
            trimmed = value.rstrip("\\")
            parts = [p for p in trimmed.split("\\") if p]
            if len(parts) < 2:
                return ""
            return "\\\\" + "\\".join(parts)
        except Exception:
            return ""

    def _available_business_nas_roots(self) -> list[str]:
        roots: list[str] = []

        def _add(candidate: str) -> None:
            norm = self._normalize_business_nas_root(candidate)
            if not norm:
                return
            if norm not in roots:
                roots.append(norm)

        try:
            persisted = get_business_nas_path()
            _add(persisted)
        except Exception:
            pass

        try:
            import os
            import subprocess

            host = os.environ.get("COMPUTERNAME", "").strip()
            if host:
                ps = (
                    "Get-SmbShare | "
                    "Where-Object { $_.Name -notlike 'ADMIN$' -and $_.Name -notlike 'IPC$' -and $_.Name -notlike 'C$' -and $_.Name -notlike 'D$' -and $_.Name -notlike 'E$' } | "
                    "Select-Object -ExpandProperty Name"
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps],
                    capture_output=True,
                    text=True,
                    timeout=6,
                )
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        share = str(line or "").strip()
                        if share:
                            _add(f"\\\\{host}\\{share}")
        except Exception:
            pass

        try:
            import subprocess
            result = subprocess.run(
                ["cmd", "/c", "net use"],
                capture_output=True,
                text=True,
                timeout=6,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if "\\\\" not in line:
                        continue
                    parts = line.split()
                    for part in parts:
                        if part.startswith("\\\\"):
                            _add(part)
        except Exception:
            pass

        return roots

    def _business_nas_mode_active(self) -> bool:
        try:
            if get_business_seat_identity():
                return True
        except Exception:
            pass
        try:
            st = check_license()
            kind = getattr(st, "plan", None) or getattr(st, "tier", None) or getattr(st, "kind", None)
            return str(kind or "").strip().lower() == "business"
        except Exception:
            return False

    def _populate_vault_combo(self) -> None:
        if self._business_nas_mode_active():
            saved_nas = ""
            try:
                saved_nas = self._normalize_business_nas_root(get_business_nas_path())
            except Exception:
                saved_nas = ""

            choices = [saved_nas] if saved_nas else ["Not configured"]

            self.vault_combo.blockSignals(True)
            self.vault_combo.clear()
            self.vault_combo.addItems(choices)
            self.vault_combo.setCurrentIndex(0)
            self.vault_combo.blockSignals(False)

            self.vault_path = saved_nas
            self.update_vault_display()
            return
        else:
            choices = self._available_drive_roots()
            if self.vault_path and self.vault_path not in choices:
                choices.insert(0, self.vault_path)
            if not choices:
                choices = [self.vault_path or "C:\\"]

        self.vault_combo.blockSignals(True)
        self.vault_combo.clear()
        self.vault_combo.addItems(choices)
        idx = self.vault_combo.findText(self.vault_path)
        if idx >= 0:
            self.vault_combo.setCurrentIndex(idx)
        elif choices:
            self.vault_combo.setCurrentIndex(0)
            self.vault_path = choices[0]
        self.vault_combo.blockSignals(False)
        self.update_vault_display()

    def _format_unc_for_display(self, value: str) -> str:
        try:
            raw = str(value or "").strip()
            if not raw:
                return ""
            if raw.startswith("\\"):
                trimmed = raw.rstrip("\\")
                parts = [p for p in trimmed.split("\\") if p]
                if len(parts) >= 2:
                    return "\\" + "\\".join(parts)
            return raw.rstrip("\\")
        except Exception:
            return str(value or "")

    def _apply_vault_ui_mode(self) -> None:
        business_mode = False
        try:
            business_mode = self._business_nas_mode_active()
        except Exception:
            business_mode = False

        if business_mode:
            self.vault_combo.setEnabled(False)
            self.vault_combo.setToolTip("Business NAS target is managed by Business Admin.")
            self.vault_line_2.setText("Managed by Business Admin")
            self.vault_line_2.show()
        else:
            self.vault_combo.setEnabled(True)
            self.vault_combo.setToolTip("")
            self.vault_line_2.setText("")
            self.vault_line_2.hide()

    def update_vault_display(self) -> None:
        business_mode = False
        try:
            business_mode = self._business_nas_mode_active()
        except Exception:
            business_mode = False

        if business_mode:
            saved_nas = ""
            try:
                saved_nas = self._normalize_business_nas_root(get_business_nas_path())
            except Exception:
                saved_nas = ""

            display_path = self._format_unc_for_display(saved_nas) if saved_nas else "Not configured"
            self.vault_line_1.setText(f"Business NAS Target:\n{display_path}")
        else:
            self.vault_line_1.setText(f"Current backup location: {self.vault_path}")

        self._apply_vault_ui_mode()

    def change_vault(self, folder: str) -> None:
        if self._business_nas_mode_active():
            normalized = self._normalize_business_nas_root(folder)
        else:
            normalized = self._normalize_vault_root(folder)

        if not normalized:
            self.append_log(f"Vault selection refused: {folder}")
            self._populate_vault_combo()
            return

        if normalized != self.vault_path:
            self.vault_path = normalized
            self.settings.setValue("vault_path", normalized)
            try:
                set_vault_dir(normalized)
            except Exception:
                pass
            try:
                st = check_license()
                license_kind = getattr(st, "plan", None) or getattr(st, "tier", None) or getattr(st, "kind", None)
                if self._business_nas_mode_active() or str(license_kind or "").strip().lower() == "business":
                    set_business_nas_path(normalized)
            except Exception:
                pass
            self.update_vault_display()
            self.append_log(f"Vault updated: {normalized}")

    def _set_busy(self, busy: bool) -> None:
        business_mode = False
        try:
            business_mode = self._business_nas_mode_active()
        except Exception:
            business_mode = False

        if business_mode:
            self.vault_combo.setEnabled(False)
        else:
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
        # Launch-grade cancel lifecycle — instant UI release
        def _do_cancel() -> None:
            self._exec_cancelled = True

            try:
                self.append_log("Cancellation requested…")
            except Exception:
                pass

            try:
                w = getattr(self, "_backup_exec", None)
                if w is not None:
                    w.cancel()
            except Exception:
                pass

            # 🚀 Immediate UX release — DO NOT wait for engine unwind
            try:
                self._set_busy(False)
            except Exception:
                pass

            try:
                self._op_stop(allow_close=True)
            except Exception:
                pass

            try:
                ov = getattr(self, "op_overlay", None)
                if ov:
                    ov.btn_cancel.setEnabled(False)
                    ov.hide()
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

    def _op_bind_cancel_scan(self) -> None:
        def _do_cancel() -> None:
            self.append_log("Scan cancelled by operator.")
            self._scan_cancelled = True

            try:
                w = getattr(self, "_scan_worker", None)
                if w is not None and hasattr(w, "cancel"):
                    w.cancel()
            except Exception:
                pass

            try:
                t = getattr(self, "_scan_thread", None)
                if t is not None:
                    t.requestInterruption()
                    t.quit()
            except Exception:
                pass

            try:
                ov = getattr(self, "op_overlay", None)
                if ov:
                    ov.btn_cancel.setEnabled(False)
                    ov.stop(allow_close=True)
            except Exception:
                pass

            try:
                self._set_busy(False)
            except Exception:
                pass

        self._op_cancel_handler = _do_cancel

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
        try:
            self._enforce_business_nas_backup_requirement()
        except NASNotConfiguredError as e:
            msg = str(e)
            self.append_log(f"Backup refused: {msg}")
            try:
                self._ui_critical("Business NAS Required", msg)
            except Exception:
                pass
            return False

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

        try:
            mark_protected()
        except Exception as e:
            self.append_log(f"Warning: could not update reminder state: {e}")

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
    def _on_backup_exec_err(self, payload: object) -> None:
        if isinstance(payload, dict):
            code = str(payload.get("code") or "").strip().upper()
            title, text = self._resolve_refusal_ui(payload)

            if code == "OPERATOR_CANCELLED":
                pass
            else:
                self.append_log(f"Backup refused: {text}")
                try:
                    self._ui_critical(title, text)
                except Exception:
                    pass
        else:
            msg = str(payload or "").strip()
            if msg == "Cancelled by operator.":
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

        verification_state = str(payload.get("restore_verification") or "").strip()
        checksum_state = str(payload.get("checksum_verification") or "").strip()
        destination_dir = str(payload.get("destination_dir") or "").strip()

        self.append_log("Restore complete.")
        if verification_state:
            self.append_log(f"Restore verification: {verification_state}")
        if checksum_state:
            self.append_log(f"Checksum verification: {checksum_state}")
        if destination_dir:
            self.append_log(f"Restore destination: {destination_dir}")
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

    
    def _on_restore_err(self, payload: object) -> None:
        # Stop overlay / modal state first
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

        if isinstance(payload, dict):
            code = str(payload.get("code") or "").strip().upper()
            title, text = self._resolve_refusal_ui(payload)

            if code != "OPERATOR_CANCELLED":
                self.append_log(f"Restore refused: {text}")
                try:
                    self._ui_critical(title, text)
                except Exception:
                    pass
        else:
            msg = str(payload or "").strip()
            if msg != "Cancelled by operator.":
                self.append_log(f"Restore refused: {msg}")
                try:
                    self._ui_critical("Restore Failed", msg)
                except Exception:
                    pass

        try:
            if getattr(self, "_restore_thread", None) is not None:
                self._restore_thread.quit()
        except Exception:
            pass

        self._set_busy(False)


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

    def _count_files_for_zip_hint(self, root: Path, limit: int = 500) -> int:
        """
        Fast UI-thread heuristic only.

        IMPORTANT:
        - Do NOT recurse the full tree here.
        - This function exists only to decide whether to show the
          'zip first recommended' warning without freezing the UI.
        - Exact counts happen later in subprocess preflight.
        """
        count = 0
        try:
            for p in root.iterdir():
                count += 1
                if count >= limit:
                    return count
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

        likely_large_data = False
        try:
            parent_name = folder.parent.name.strip().lower()
            if parent_name in ("pictures", "videos", "downloads"):
                likely_large_data = True
        except Exception:
            pass

        top_level_count = self._count_files_for_zip_hint(folder, limit=500)

        if not likely_large_data and top_level_count < 500:
            return True

        size_hint = f"{top_level_count}+" if top_level_count >= 500 else str(top_level_count)

        msg = (
            "Large folder detected.\n\n"
            f"Folder:\n  {folder}\n\n"
            f"Top-level items detected: {size_hint}\n\n"
            "This folder looks like user data and may take a while during preflight and backup.\n"
            "For faster and cleaner archival backups, zip this folder first.\n"
            "DevVault can back up archive files directly (.zip, .7z, .rar, .tar, .gz).\n\n"
            "Continue backing up this folder anyway?"
        )

        answer = _centered_message(
            self,
            "Zip First Recommended",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _require_action_entitlement(self, entitlement: str, *, action_name: str) -> bool:
        sim_allowed = _simulated_entitlements_from_env()
        if sim_allowed:
            sim_raw = (os.environ.get("DEVVAULT_SIM_ENTITLEMENTS", "") or "").strip()
            if entitlement in sim_allowed:
                self.append_log(
                    f"{action_name}: dev entitlement override allowed ({sim_raw}) -> {entitlement}"
                )
                return True

        try:
            st = check_license()
        except Exception as e:
            self.append_log(f"{action_name} refused: license check failed: {e}")
            _centered_message(
                self,
                f"{action_name} Refused",
                f"License check failed:\n\n{e}",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Ok,
            )
            return False

        try:
            st.require_entitlement(entitlement)
            return True
        except PermissionError:
            self.append_log(f"{action_name} refused: missing required entitlement: {entitlement}")
            _centered_message(
                self,
                f"{action_name} Refused",
                f"This license does not include the required entitlement for {action_name.lower()}.\n\n"
                f"Required: {entitlement}",
            )
            return False

    def _enforce_business_nas_backup_requirement(self) -> None:
        license_kind = None
        try:
            st = check_license()
            license_kind = getattr(st, "plan", None) or getattr(st, "tier", None) or getattr(st, "kind", None)
        except Exception:
            license_kind = None

        try:
            seat_identity = get_business_seat_identity()
        except Exception:
            seat_identity = None

        if seat_identity:
            license_kind = "business"

        nas_path = ""
        try:
            nas_path = get_business_nas_path()
        except Exception:
            nas_path = ""

        enforce_business_nas_requirement(
            license_kind=license_kind,
            nas_path=nas_path,
        )

        normalized_kind = str(license_kind or "").strip().lower()
        if normalized_kind != "business":
            return

        nas_path = str(nas_path or "").strip()
        if not nas_path:
            return

        authority = validate_business_vault_authority(Path(nas_path))
        if not authority.ok:
            raise NASNotConfiguredError(
                f"{authority.operator_message}\n\nAuthority state: {authority.state.value}"
            )

    def run_scan(self) -> None:
        if not self._require_action_entitlement("core_scan_system", action_name="Scan"):
            return
        self.append_log("Scan requested.")
        self.append_log("Scanning your workspaces...")
        self._scan_cancelled = False
        self._op_bind_cancel_scan()

        try:
            self._op_show(
                "Scanning your workspaces",
                "Scan in progress",
                [
                    "DevVault is reviewing this PC for unprotected work.",
                    "Large scans may take a moment.",
                    "System locations are filtered from results.",
                ],
                allow_cancel=True,
            )
        except Exception:
            pass

        QApplication.processEvents()

        self.append_log("Checking for uncovered projects...")
        self._set_busy(True)

        self._scan_thread = QThread()
        business_mode = False
        business_nas_path = ""
        try:
            business_mode = bool(self._business_nas_mode_active())
        except Exception:
            business_mode = False

        if business_mode:
            try:
                business_nas_path = str(get_business_nas_path() or "").strip()
            except Exception:
                business_nas_path = ""

        self._scan_worker = _ScanWorker(
            business_mode=business_mode,
            business_nas_path=business_nas_path,
        )
        self._scan_worker.moveToThread(self._scan_thread)

        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.log.connect(self.append_log)
        self._scan_worker.done.connect(self._on_scan_done, type=Qt.QueuedConnection)
        self._scan_worker.error.connect(self._on_scan_err, type=Qt.QueuedConnection)

        self._scan_thread.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.finished.connect(self._cleanup_scan_thread, type=Qt.QueuedConnection)

        self._scan_thread.start()

    def _on_scan_done(self, payload: dict) -> None:
        if bool(getattr(self, "_scan_cancelled", False)):
            self._scan_cancelled = False
            self.append_log("Scan cancelled.")
            try:
                self._op_stop(allow_close=True)
            except Exception:
                pass
            self._set_busy(False)
            try:
                if getattr(self, "_scan_thread", None) is not None:
                    self._scan_thread.quit()
            except Exception:
                pass
            return

        try:
            self._op_stop()
        except Exception:
            pass
        try:
            self._op_stop()
        except Exception:
            pass
        self._last_scan_payload = dict(payload or {})
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

        self._update_protection_status(len(uncovered))
        try:
            if uncovered:
                mark_unprotected(len(uncovered))
            else:
                mark_protected()
        except Exception as e:
            self.append_log(f"Warning: could not update reminder state: {e}")

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

            if p.is_dir():
                if self._confirm_large_folder_backup(p):
                    approved_paths.append(selected)
                else:
                    self.append_log(f"Skipped after zip suggestion: {selected}")
                continue

            if p.is_file():
                approved_paths.append(selected)
                continue

            self.append_log(f"Skipped unavailable scan item: {selected}")

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
        if bool(getattr(self, "_scan_cancelled", False)) and (msg or "").strip().lower() == "scan cancelled by operator.":
            self._scan_cancelled = False
            self.append_log("Scan cancelled.")
            try:
                self._op_stop(allow_close=True)
            except Exception:
                pass
            self._set_busy(False)
            try:
                if getattr(self, "_scan_thread", None) is not None:
                    self._scan_thread.quit()
            except Exception:
                pass
            return

        try:
            self._op_stop()
        except Exception:
            pass
        try:
            self._op_stop()
        except Exception:
            pass
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
        try:
            _centered_message(
                self,
                "Install DevVault License",
                (
                    "Select your DevVault license file (.dvlic).\n\n"
                    "DevVault will verify the license signature before installing it.\n"
                    "If the same license is already installed, DevVault will skip the duplicate install.\n\n"
                    "After a successful install, license status will refresh immediately."
                ),
            )
        except Exception:
            pass

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



    
    def _current_business_admin_session(self) -> dict | None:
        session = getattr(self, "_business_admin_session", None)
        if not isinstance(session, dict):
            return None

        if self._business_admin_session_expired(session):
            self._clear_business_admin_session()
            return None

        seat_role = str(session.get("seat_role") or "").strip().lower()
        seat_status = str(session.get("seat_status") or "").strip().lower()

        if seat_role not in {"owner", "admin"}:
            return None
        if seat_status != "active":
            return None

        return session

    def _business_admin_session_allowed(self) -> bool:
        session = self._current_business_admin_session()
        if isinstance(session, dict):
            try:
                seat_role = str(session.get("seat_role") or "").strip().lower()
                seat_status = str(session.get("seat_status") or "").strip().lower()
                if seat_role in {"owner", "admin"} and seat_status == "active":
                    return True
            except Exception:
                pass

        try:
            identity = get_business_seat_identity()
        except Exception:
            identity = None

        try:
            if isinstance(identity, dict):
                role = str(
                    identity.get("seat_role")
                    or identity.get("role")
                    or ""
                ).strip().lower()

                seat_id = str(identity.get("seat_id") or "").strip().lower()
                seat_label = str(identity.get("seat_label") or "").strip().lower()

                if not role:
                    if seat_id.startswith("seat_owner_") or " owner" in f" {seat_label} ":
                        role = "owner"

                if role == "owner" and self._runtime_local_identity_matches(identity):
                    return True
        except Exception:
            pass

        return False

    def _require_business_admin_session(self, action_name: str = "This action") -> bool:
        if self._business_admin_session_allowed():
            return True

        _centered_message(
            self,
            "Business Admin Session Required",
            f"{action_name} requires an active Business admin session.\n\nPlease sign in again.",
        )
        return False

    def _business_admin_session_expired(self, session: dict | None = None) -> bool:
        if not isinstance(session, dict):
            return True

        expires_at = str(session.get("session_expires_at") or "").strip()
        if not expires_at:
            return False

        try:
            normalized = expires_at.replace("Z", "+00:00")
            expires_dt = datetime.fromisoformat(normalized)
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) >= expires_dt.astimezone(timezone.utc)
        except Exception:
            return False

    def _stop_business_admin_session_watchdog(self) -> None:
        timer = getattr(self, "_business_admin_session_watchdog", None)
        if timer is None:
            return
        try:
            timer.stop()
        except Exception:
            pass

    def _start_business_admin_session_watchdog(self) -> None:
        timer = getattr(self, "_business_admin_session_watchdog", None)
        if timer is None:
            timer = QTimer(self)
            timer.setInterval(30000)
            timer.timeout.connect(self._business_admin_session_watchdog_tick)
            self._business_admin_session_watchdog = timer

        try:
            if not timer.isActive():
                timer.start()
        except Exception:
            pass

    def _business_admin_session_watchdog_tick(self) -> None:
        session = getattr(self, "_business_admin_session", None)
        if not isinstance(session, dict):
            self._stop_business_admin_session_watchdog()
            return

        if not self._business_admin_session_expired(session):
            return

        self._clear_business_admin_session()
        _centered_message(
            self,
            "Business Admin Session Expired",
            "Your Business admin session expired. Please sign in again.",
        )


    def _clear_business_admin_session(self) -> None:
        self._business_admin_session = None
        self._last_admin_reset_password = ""
        self._stop_business_admin_session_watchdog()

    
    def _business_admin_sign_in(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Business Admin Sign In")
        dlg.setModal(True)
        dlg.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)
        dlg.setMinimumWidth(560)

        layout = QVBoxLayout(dlg)

        lbl_intro = QLabel("Sign in using a one-time seat login token (recommended), or admin email/password if mapped to a seat.")
        lbl_intro.setWordWrap(True)
        layout.addWidget(lbl_intro)

        txt_email = QLineEdit(dlg)
        txt_email.setPlaceholderText("Admin email")
        layout.addWidget(txt_email)

        txt_password = QLineEdit(dlg)
        txt_password.setPlaceholderText("Password")
        txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(txt_password)

        txt_token = QLineEdit(dlg)
        txt_token.setPlaceholderText("One-time seat token (optional)")
        layout.addWidget(txt_token)

        btn_row = QHBoxLayout()
        btn_sign_in = QPushButton("Sign In", dlg)
        btn_cancel = QPushButton("Cancel", dlg)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_sign_in)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        btn_cancel.clicked.connect(dlg.reject)
        btn_sign_in.clicked.connect(dlg.accept)

        try:
            identity = get_business_seat_identity()
            default_email = ""
            if isinstance(identity, dict):
                default_email = str(identity.get("assigned_email") or "").strip()
            if default_email:
                txt_email.setText(default_email)
        except Exception:
            pass

        try:
            _center_widget_on_parent(dlg, self)
            QTimer.singleShot(0, lambda: _center_widget_on_parent(dlg, self))
        except Exception:
            pass

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        email = str(txt_email.text() or "").strip().lower()
        password = str(txt_password.text() or "").strip()
        seat_token = str(txt_token.text() or "").strip()

        if not email:
            _centered_message(
                self,
                "Business Admin Sign In",
                "Admin email is required.",
            )
            return

        if not password and not seat_token:
            _centered_message(
                self,
                "Business Admin Sign In",
                "Enter either a password or a one-time seat token.",
            )
            return

        hostname = str(
            os.environ.get("COMPUTERNAME")
            or os.environ.get("HOSTNAME")
            or ""
        ).strip()
        device_id = hostname

        try:
            if seat_token:
                from inspect import signature

                token_kwargs = {"seat_token": seat_token}
                sig = signature(login_business_admin_with_seat_token)

                if "email" in sig.parameters:
                    token_kwargs["email"] = email
                if "hostname" in sig.parameters:
                    token_kwargs["hostname"] = hostname
                if "device_id" in sig.parameters:
                    token_kwargs["device_id"] = device_id
                if "app_version" in sig.parameters:
                    token_kwargs["app_version"] = _safe_app_version()

                result = login_business_admin_with_seat_token(**token_kwargs)

                # Normalize seat-token login response to match admin session contract
                if isinstance(result, dict):
                    if "seat_role" not in result:
                        result["seat_role"] = "owner"
                    if "seat_status" not in result:
                        result["seat_status"] = "active"

            else:
                result = login_business_admin_with_password(
                    email=email,
                    password=password,
                    hostname=hostname,
                    device_id=device_id,
                    app_version=_safe_app_version(),
                )
        except BusinessSeatApiError as e:
            self._clear_business_admin_session()
            mode_label = "seat token" if seat_token else "email/password"
            _centered_message(
                self,
                "Business Admin Sign In",
                f"Could not sign in with {mode_label}.\n\n{e}",
            )
            return
        except Exception as e:
            self._clear_business_admin_session()
            _centered_message(
                self,
                "Business Admin Sign In",
                f"Unexpected sign-in failure.\n\n{e}",
            )
            return

        seat_role = str(result.get("seat_role") or "").strip().lower()
        seat_status = str(result.get("seat_status") or "").strip().lower()

        if seat_role not in {"owner", "admin"} or seat_status != "active":
            self._clear_business_admin_session()

            mode_hint = "Use a seat login token issued from an owner/admin machine."
            if not seat_token:
                mode_hint = "Password login must map to an active owner/admin seat. If this fails, use a seat login token."

            _centered_message(
                self,
                "Business Admin Sign In",
                "The provided credentials are not mapped to an active owner/admin seat.\n\n"
                + mode_hint,
            )
            return

        session = dict(result)

        # Hydrate missing seat_id from local identity
        if not str(session.get("seat_id") or "").strip():
            try:
                local_identity = get_business_seat_identity()
                if isinstance(local_identity, dict):
                    local_seat_id = str(local_identity.get("seat_id") or "").strip()
                    if local_seat_id:
                        session["seat_id"] = local_seat_id
            except Exception:
                pass

        self._business_admin_session = session

        # --- GLOBAL SESSION WRITE ---
        global _GLOBAL_ADMIN_SESSION
        _GLOBAL_ADMIN_SESSION = session


        # --- CANONICAL SESSION AUTHORITY WRITE ---
        try:
            root = self
            # climb to top-level window
            while hasattr(root, "parent") and callable(root.parent):
                nxt = root.parent()
                if not nxt:
                    break
                root = nxt

            if root is not None:
                setattr(root, "_business_admin_session", session)

        except Exception:
            pass


        try:
            parent = self.parent()
        except Exception:
            parent = None

        if parent is not None and hasattr(parent, "_business_admin_session"):
            parent._business_admin_session = session
            try:
                if hasattr(parent, "_start_business_admin_session_watchdog"):
                    parent._start_business_admin_session_watchdog()
            except Exception:
                pass

        if bool(result.get("password_reset_required")):
            reset_ok = self._business_admin_force_password_reset(
                email=email,
                current_password=password,
            )
            if not reset_ok:
                self._clear_business_admin_session()
                return

            try:
                refreshed = login_business_admin_with_password(
                    email=email,
                    password=self._last_admin_reset_password,
                    hostname=hostname,
                    device_id=device_id,
                    app_version=_safe_app_version(),
                )
                refreshed_session = dict(refreshed)

                if not str(refreshed_session.get("seat_id") or "").strip():
                    try:
                        local_identity = get_business_seat_identity()
                        if isinstance(local_identity, dict):
                            local_seat_id = str(local_identity.get("seat_id") or "").strip()
                            if local_seat_id:
                                refreshed_session["seat_id"] = local_seat_id
                    except Exception:
                        pass

                self._business_admin_session = refreshed_session
            except Exception as e:
                self._clear_business_admin_session()
                _centered_message(
                    self,
                    "Business Admin Sign In",
                    f"Password reset succeeded, but session refresh failed.\n\n{e}",
                )
                return

        self._start_business_admin_session_watchdog()

        _centered_message(
            self,
            "Business Admin Sign In",
            (
                "Business admin session unlocked for this app session.\n\n"
                f"Role: {self._business_admin_session.get('seat_role') or 'n/a'}\n"
                f"Seat: {self._business_admin_session.get('seat_id') or 'n/a'}\n"
                f"Email: {self._business_admin_session.get('email') or email}\n"
                f"Session Expires: {self._business_admin_session.get('session_expires_at') or 'n/a'}"
            ),
        )

    def _business_admin_force_password_reset(
        self,
        *,
        email: str,
        current_password: str,
    ) -> bool:
        dlg = QDialog(self)
        dlg.setWindowTitle("Set Permanent Password")
        dlg.setModal(True)
        dlg.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)
        dlg.setMinimumWidth(560)

        layout = QVBoxLayout(dlg)

        lbl_intro = QLabel(
            "A permanent password is required before Business Console access can continue."
        )
        lbl_intro.setWordWrap(True)
        layout.addWidget(lbl_intro)

        txt_new_password = QLineEdit(dlg)
        txt_new_password.setPlaceholderText("New password (12+ characters)")
        txt_new_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(txt_new_password)

        txt_confirm_password = QLineEdit(dlg)
        txt_confirm_password.setPlaceholderText("Confirm new password")
        txt_confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(txt_confirm_password)

        btn_row = QHBoxLayout()
        btn_set = QPushButton("Set Password", dlg)
        btn_cancel = QPushButton("Cancel", dlg)
        btn_row.addStretch(1)
        btn_row.addWidget(btn_set)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        btn_cancel.clicked.connect(dlg.reject)
        btn_set.clicked.connect(dlg.accept)

        try:
            _center_widget_on_parent(dlg, self)
            QTimer.singleShot(0, lambda: _center_widget_on_parent(dlg, self))
        except Exception:
            pass

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return False

        new_password = str(txt_new_password.text() or "")
        confirm_password = str(txt_confirm_password.text() or "")

        if len(new_password) < 12:
            _centered_message(
                self,
                "Set Permanent Password",
                "The new password must be at least 12 characters.",
            )
            return False

        if new_password != confirm_password:
            _centered_message(
                self,
                "Set Permanent Password",
                "The password confirmation does not match.",
            )
            return False

        try:
            reset_business_admin_password(
                email=email,
                current_password=current_password,
                new_password=new_password,
                token=self._business_admin_session.get("admin_session_token"),
            )
        except BusinessSeatApiError as e:
            _centered_message(
                self,
                "Set Permanent Password",
                f"Could not set permanent password.\n\n{e}",
            )
            return False
        except Exception as e:
            _centered_message(
                self,
                "Set Permanent Password",
                f"Unexpected password reset failure.\n\n{e}",
            )
            return False

        self._last_admin_reset_password = new_password

        _centered_message(
            self,
            "Set Permanent Password",
            "Permanent password saved successfully.",
        )
        return True

    def _business_admin_sign_out(self) -> None:

        self._clear_business_admin_session()
        _centered_message(
            self,
            "Business Admin Sign Out",
            "Business admin session cleared for this app session.",
        )

    def open_business_tools(self) -> None:
        ensure_business_runtime_config()

        if not self._require_action_entitlement(
            "biz_seat_admin_tools",
            action_name="Business Tools",
        ):
            ensure_business_runtime_config()
            return

        try:
            identity = get_business_seat_identity()
        except Exception:
            identity = None

        if not isinstance(identity, dict) or not str(identity.get("seat_id") or "").strip():
            _centered_message(
                self,
                "Business Tools",
                (
                    "This device is not enrolled in the Business fleet yet.\n\n"
                    "Use Seat Activation from the Tools menu first."
                ),
            )
            return

        try:
            nas_path = str(get_business_nas_path() or "").strip()
        except Exception:
            nas_path = ""

        if not nas_path:
            _centered_message(
                self,
                "Business Tools",
                (
                    "Business Console requires a configured Business NAS target.\n\n"
                    "Set and validate the Business NAS path first."
                ),
            )
            return

        owner_local_access = False
        try:
            identity_role = ""
            if isinstance(identity, dict):
                identity_role = str(
                    identity.get("seat_role")
                    or identity.get("role")
                    or ""
                ).strip().lower()

                if not identity_role:
                    seat_id = str(identity.get("seat_id") or "").strip().lower()
                    seat_label = str(identity.get("seat_label") or "").strip().lower()
                    if seat_id.startswith("seat_owner_") or " owner" in f" {seat_label} ":
                        identity_role = "owner"

            owner_local_access = (
                isinstance(identity, dict)
                and identity_role == "owner"
                and not getattr(self, "_local_seat_identity_mismatch", False)
            )
        except Exception:
            owner_local_access = False
        # Local owner auto-auth DISABLED for launch validation.
        # All Business admin access must come from real server-backed session.

        if not owner_local_access and not self._business_admin_session_allowed():
            _centered_message(
                self,
                "Business Tools",
                (
                    "Business Console requires owner/admin sign-in for this session.\n\n"
                    "Use Business Admin Sign In first."
                ),
            )
            return

        dlg = BusinessHubDialog(self)
        dlg.exec()
        return

    def _show_business_dashboard(self):

        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel

        dlg = QDialog(self)
        dlg.setWindowTitle("DevVault Business Dashboard")
        dlg.setMinimumWidth(600)

        layout = QVBoxLayout(dlg)

        title = QLabel("Business Dashboard — Surface Active")
        title.setStyleSheet("font-size:20px;font-weight:700;")

        layout.addWidget(title)

        dlg.exec()
        return


    def open_pro_features(self) -> None:
        dlg = ProHubDialog(self)
        dlg.exec()

    def open_advanced_scan_report(self) -> None:
        if not self._require_action_entitlement(
            "pro_advanced_scan_reports",
            action_name="Advanced Scan Report",
        ):
            return

        payload = getattr(self, "_last_scan_payload", None)
        if not payload:
            _centered_message(
                self,
                "Advanced Scan Report",
                "No scan report is available yet.\n\nRun Full Scan first, then open Pro Tools again.",
            )
            return

        report = build_advanced_scan_report(payload)
        report_text = render_advanced_scan_report_text(report)

        dlg = QDialog(self)
        dlg.setWindowTitle("Advanced Scan Report")
        dlg.setModal(True)
        dlg.setMinimumWidth(860)
        dlg.setMinimumHeight(520)
        dlg.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("DevVault Advanced Scan Report", dlg)
        title.setWordWrap(True)
        root.addWidget(title)

        details = QTextEdit(dlg)
        details.setReadOnly(True)
        details.setPlainText(report_text)
        root.addWidget(details, 1)

        btn_row = QHBoxLayout()

        btn_export_txt = QPushButton("Export TXT", dlg)
        btn_export_txt.clicked.connect(lambda: self._export_advanced_scan_report(report, "txt"))
        btn_row.addWidget(btn_export_txt)

        btn_export_json = QPushButton("Export JSON", dlg)
        btn_export_json.clicked.connect(lambda: self._export_advanced_scan_report(report, "json"))
        btn_row.addWidget(btn_export_json)

        btn_export_md = QPushButton("Export Markdown", dlg)
        btn_export_md.clicked.connect(lambda: self._export_advanced_scan_report(report, "md"))
        btn_row.addWidget(btn_export_md)

        btn_row.addStretch(1)

        btn_close = QPushButton("Close", dlg)
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)

        root.addLayout(btn_row)

        dlg.exec()

    def open_recovery_audit_report(self) -> None:
        if not self._require_action_entitlement(
            "pro_recovery_audit_reports",
            action_name="Recovery Audit",
        ):
            return

        try:
            report = build_recovery_audit_report(Path(self.vault_path))
            report_text = render_recovery_audit_text(report)
        except Exception as e:
            self.append_log(f"Recovery audit failed: {e}")
            _centered_message(self, "Recovery Audit", f"Could not build recovery audit report:\n\n{e}")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Recovery Audit")
        dlg.setModal(True)
        dlg.setMinimumWidth(860)
        dlg.setMinimumHeight(520)
        dlg.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("DevVault Recovery Audit", dlg)
        title.setWordWrap(True)
        root.addWidget(title)

        details = QTextEdit(dlg)
        details.setReadOnly(True)
        details.setPlainText(report_text)
        root.addWidget(details, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_export_txt = QPushButton("Export TXT", dlg)
        btn_export_txt.clicked.connect(
            lambda: self._export_text_report(
                report_text=report_text,
                default_name="devvault_recovery_audit_report",
                title="Recovery Audit",
                fmt="txt",
            )
        )
        btn_row.addWidget(btn_export_txt)

        btn_export_md = QPushButton("Export MD", dlg)
        btn_export_md.clicked.connect(
            lambda: self._export_text_report(
                report_text=report_text,
                default_name="devvault_recovery_audit_report",
                title="Recovery Audit",
                fmt="md",
            )
        )
        btn_row.addWidget(btn_export_md)

        btn_close = QPushButton("Close", dlg)
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)

        root.addLayout(btn_row)

        dlg.exec()



    def _build_business_seat_protection_state_report_text(self) -> str:
        base_request = self._build_business_fetch_request()
        request = FetchRequest(
            scope_id="local-business-seat-state",
            vault_roots=base_request.vault_roots,
            selected_seats=base_request.selected_seats,
            include_details=True,
        )
        fetcher = SeatProtectionStateFetcher()
        fetch_result = fetcher.fetch(request)
        report = build_business_seat_protection_state_report(fetch_result)
        return render_business_seat_protection_state_text(report)

    def open_business_seat_protection_state(self) -> None:
        if not self._require_action_entitlement(
            "biz_seat_admin_tools",
            action_name="Legacy Seat Protection Report",
        ):
            return

        try:
            report_text = self._build_business_seat_protection_state_report_text()
        except Exception as e:
            self.append_log(f"Business seat protection state failed: {e}")
            _centered_message(
                self,
                "Legacy Seat Protection Report",
                f"Could not build seat protection state report:\n\n{e}",
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Legacy Seat Protection Report")
        dlg.setModal(True)
        dlg.setMinimumWidth(860)
        dlg.setMinimumHeight(520)
        dlg.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("DevVault Business Legacy Seat Protection Report", dlg)
        title.setWordWrap(True)
        root.addWidget(title)

        details = QTextEdit(dlg)
        details.setReadOnly(True)
        details.setPlainText(report_text)
        root.addWidget(details, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        btn_export_txt = QPushButton("Export TXT", dlg)
        btn_export_txt.clicked.connect(
            lambda: self._export_text_report(
                report_text=report_text,
                default_name="devvault_business_legacy_seat_protection_report",
                title="Legacy Seat Protection Report",
                fmt="txt",
            )
        )
        btn_row.addWidget(btn_export_txt)

        btn_export_md = QPushButton("Export MD", dlg)
        btn_export_md.clicked.connect(
            lambda: self._export_text_report(
                report_text=report_text,
                default_name="devvault_business_legacy_seat_protection_report",
                title="Legacy Seat Protection Report",
                fmt="md",
            )
        )
        btn_row.addWidget(btn_export_md)

        btn_close = QPushButton("Close", dlg)
        btn_close.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_close)

        root.addLayout(btn_row)

        dlg.exec()






    def _normalize_business_report_text(
        self,
        report_text: str,
        *,
        include_health_summary: bool,
    ) -> str:
        text = str(report_text or "")
        lines = text.splitlines()

        try:
            business_nas = str(get_business_nas_path() or "").strip()
        except Exception:
            business_nas = ""

        normalized: list[str] = []
        for line in lines:
            stripped = line.strip()

            if stripped.startswith("Entitlement:"):
                continue

            if not include_health_summary and stripped.startswith("Health Summary:"):
                continue

            if stripped.startswith("Vault Path:"):
                normalized.append(f"Vault Path: {business_nas or 'n/a'}")
                continue

            normalized.append(line)

        out: list[str] = []
        prev_blank = False
        for line in normalized:
            is_blank = not line.strip()
            if is_blank and prev_blank:
                continue
            out.append(line)
            prev_blank = is_blank

        return "\n".join(out).strip()

    def _build_business_org_recovery_audit_report_text(self) -> str:
        request = self._build_business_fetch_request()
        fetch_result = OrganizationRecoveryAuditFetcher().fetch(request)
        report = build_business_org_recovery_audit_report(fetch_result)
        report_text = render_business_org_recovery_audit_text(report)
        return self._normalize_business_report_text(
            report_text,
            include_health_summary=False,
        )

    def _build_business_fleet_health_summary_report_text(self) -> str:
        request = self._build_business_fetch_request()
        fetch_result = FleetHealthSummaryFetcher().fetch(request)
        report = build_business_fleet_health_summary_report(fetch_result)
        report_text = render_business_fleet_health_summary_text(report)
        return self._normalize_business_report_text(
            report_text,
            include_health_summary=True,
        )

    def _build_business_vault_health_intelligence_report_text(self) -> str:
        request = self._build_business_fetch_request()
        fetch_result = VaultHealthIntelligenceFetcher().fetch(request)
        report = build_business_vault_health_intelligence_report(fetch_result)
        report_text = render_business_vault_health_intelligence_text(report)
        return self._normalize_business_report_text(
            report_text,
            include_health_summary=False,
        )

    def _build_business_administrative_visibility_report_text(self) -> str:
        try:
            subscription_id = self._business_subscription_id()
        except Exception:
            subscription_id = "n/a"

        try:
            session = self._current_business_admin_session()
        except Exception:
            session = None

        try:
            nas_path = str(get_business_nas_path() or "").strip()
        except Exception:
            nas_path = ""

        try:
            seat_payload = list_business_seats(subscription_id) if subscription_id != "n/a" else {}
        except Exception:
            seat_payload = {}

        active_seats = 0
        protected = 0
        degraded = 0
        never = 0
        unknown = 0

        try:
            snapshot = self._dashboard_snapshot()
        except Exception:
            snapshot = {}

        def _safe_int(v, default=0):
            try:
                if v in (None, "", "?"):
                    return default
                return int(v)
            except Exception:
                return default

        total_seats = _safe_int(snapshot.get("seats_total", 0), 0)
        protected = _safe_int(snapshot.get("seats_protected", 0), 0)
        active_seats = _safe_int(snapshot.get("active_seat_count", total_seats), total_seats)

        try:
            request = self._build_business_fetch_request()
            seat_result = SeatProtectionStateFetcher().fetch(request)
            vault_result = VaultHealthIntelligenceFetcher().fetch(request)
        except Exception:
            seat_result = None
            vault_result = None

        if seat_result is not None:
            for m in getattr(seat_result, "metrics", ()) or ():
                if m.key == "protected_count":
                    protected = _safe_int(m.value, protected)
                elif m.key == "degraded_count":
                    degraded = _safe_int(m.value, 0)
                elif m.key == "never_count":
                    never = _safe_int(m.value, 0)
                elif m.key == "unknown_count":
                    unknown = _safe_int(m.value, 0)
                elif m.key == "seat_count":
                    total_seats = _safe_int(m.value, total_seats)

        healthy_vaults = 0
        stale_vaults = 0
        never_vaults = 0
        unavailable_vaults = 0

        if vault_result is not None:
            for m in getattr(vault_result, "metrics", ()) or ():
                if m.key == "healthy_count":
                    healthy_vaults = _safe_int(m.value, 0)
                elif m.key == "stale_count":
                    stale_vaults = _safe_int(m.value, 0)
                elif m.key == "never_count":
                    never_vaults = _safe_int(m.value, 0)
                elif m.key == "unreachable_count":
                    unavailable_vaults = _safe_int(m.value, 0)

        seats_at_risk = degraded + never + unknown

        coverage_pct = 0
        if total_seats > 0:
            coverage_pct = int(round((protected / total_seats) * 100))

        vault_endpoint_count = healthy_vaults + stale_vaults + never_vaults + unavailable_vaults
        vault_evidence_healthy = healthy_vaults
        vault_evidence_pct = 0
        if vault_endpoint_count > 0:
            vault_evidence_pct = int(round((vault_evidence_healthy / vault_endpoint_count) * 100))

        seat_limit = None
        try:
            seat_limit_raw = (
                seat_payload.get("seat_limit")
                or seat_payload.get("max_seats")
                or seat_payload.get("licensed_seat_limit")
                or seat_payload.get("subscription_seat_limit")
            )
            if seat_limit_raw not in (None, ""):
                seat_limit = int(seat_limit_raw)
        except Exception:
            seat_limit = None

        if seat_limit is None:
            try:
                seat_limit = int(self._installed_business_seat_limit() or 0)
                if seat_limit <= 0:
                    seat_limit = None
            except Exception:
                seat_limit = None

        capacity_pressure = "UNKNOWN"
        remaining_capacity = None
        if seat_limit is not None:
            remaining_capacity = max(seat_limit - active_seats, 0)
            if active_seats > seat_limit:
                capacity_pressure = "OVER CAPACITY"
            elif remaining_capacity == 0:
                capacity_pressure = "HIGH"
            elif remaining_capacity <= 1:
                capacity_pressure = "MEDIUM"
            else:
                capacity_pressure = "LOW"

        session_active = isinstance(session, dict)
        session_role = str((session or {}).get("seat_role") or "").strip() or "n/a"
        session_email = str((session or {}).get("email") or "").strip() or "n/a"
        session_expires = str((session or {}).get("session_expires_at") or "").strip() or "n/a"

        signals: list[str] = []
        actions: list[str] = []

        if total_seats <= 0:
            signals.append("No Business seats are currently in active governance scope.")

        if seats_at_risk > 0:
            signals.append(f"{seats_at_risk} seat(s) currently lack healthy protection posture.")
            actions.append("Review Fleet Health and run backups for seats missing protection evidence.")

        if never > 0:
            signals.append(f"{never} seat(s) have never completed a NAS backup.")
            actions.append("Run first successful NAS backup for newly enrolled or unprotected seats.")

        if degraded > 0:
            signals.append(f"{degraded} seat(s) have stale NAS protection evidence.")
            actions.append("Refresh stale seats to restore protection cadence.")

        if unavailable_vaults > 0:
            signals.append(f"{unavailable_vaults} vault endpoint(s) are currently unavailable.")
            actions.append("Restore NAS reachability before relying on administrative posture.")

        if never_vaults > 0:
            signals.append(f"{never_vaults} vault endpoint(s) have not yet recorded snapshot history.")
            actions.append("Initialize snapshot history on NAS-backed Business storage.")

        if seat_limit is not None and capacity_pressure in {"HIGH", "OVER CAPACITY"}:
            signals.append(f"Seat capacity pressure is {capacity_pressure}.")
            actions.append("Review seat allocation before adding new devices.")

        if not nas_path:
            signals.append("Business NAS path is not configured.")
            actions.append("Configure and validate Business NAS path.")

        if not session_active:
            signals.append("Business admin session is not active.")
            actions.append("Sign in with owner/admin credentials before governance actions.")

        if not signals:
            signals.append("Governance posture is healthy with no active blockers detected.")

        if not actions:
            actions.append("Continue normal monitoring of fleet, seat, and NAS posture.")

        lines = [
            "DEVVAULT BUSINESS ADMINISTRATIVE VISIBILITY",
            "===========================================",
            "",
            f"Generated (UTC): {__import__('datetime').datetime.now(timezone.utc).isoformat()}Z",
            f"Vault Path: {nas_path or 'n/a'}",
            "",
            "BUSINESS GOVERNANCE POSTURE",
            "---------------------------",
            f"Fleet Protection Coverage: {coverage_pct}% ({protected} / {total_seats} seats protected)" if total_seats > 0 else "Fleet Protection Coverage: n/a",
            f"Seats At Risk: {seats_at_risk}",
            f"Vault Evidence Coverage: {vault_evidence_pct}% ({vault_evidence_healthy} / {vault_endpoint_count} healthy endpoints)" if vault_endpoint_count > 0 else "Vault Evidence Coverage: n/a",
            f"Seat Capacity Pressure: {capacity_pressure}",
            f"Active Seats: {active_seats}",
            f"Seat Limit: {seat_limit if seat_limit is not None else 'n/a'}",
            f"Remaining Capacity: {remaining_capacity if remaining_capacity is not None else 'n/a'}",
            f"Admin Session: {'ACTIVE' if session_active else 'INACTIVE'}",
            f"Admin Role: {session_role}",
            f"Admin Email: {session_email}",
            f"Session Expires: {session_expires}",
            f"NAS Path Configured: {'YES' if nas_path else 'NO'}",
            "",
            "GOVERNANCE SIGNALS",
            "------------------",
        ]

        for item in signals:
            lines.append(f"- {item}")

        lines.extend([
            "",
            "RECOMMENDED GOVERNANCE ACTIONS",
            "------------------------------",
        ])

        seen_actions = set()
        for item in actions:
            key = item.strip().lower()
            if key in seen_actions:
                continue
            seen_actions.add(key)
            lines.append(f"- {item}")

        return "\n".join(lines)


    def _export_text_report(
        self,
        *,
        report_text: str,
        default_name: str,
        title: str,
        fmt: str,
    ) -> None:
        if not self._require_action_entitlement(
            "pro_export_reports",
            action_name="Export Report",
        ):
            return

        if fmt == "txt":
            path, _ = QFileDialog.getSaveFileName(
                self,
                f"Export {title} TXT Report",
                f"{default_name}.txt",
                "Text Files (*.txt)",
            )
            if not path:
                return
            Path(path).write_text(report_text, encoding="utf-8")
            _centered_message(self, "Export Complete", f"TXT report saved:\n\n{path}")
            return

        if fmt == "md":
            path, _ = QFileDialog.getSaveFileName(
                self,
                f"Export {title} Markdown Report",
                f"{default_name}.md",
                "Markdown Files (*.md)",
            )
            if not path:
                return
            Path(path).write_text(report_text, encoding="utf-8")
            _centered_message(self, "Export Complete", f"Markdown report saved:\n\n{path}")
            return


    def _export_advanced_scan_report(self, report: dict, fmt: str) -> None:
        if not self._require_action_entitlement(
            "pro_export_reports",
            action_name="Export Report",
        ):
            return

        default_name = "devvault_advanced_scan_report"
        if fmt == "txt":
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export TXT Report",
                f"{default_name}.txt",
                "Text Files (*.txt)",
            )
            if not path:
                return
            text = render_advanced_scan_report_text(report)
            Path(path).write_text(text, encoding="utf-8")
            _centered_message(self, "Export Complete", f"TXT report saved:\n\n{path}")
            return

        if fmt == "json":
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export JSON Report",
                f"{default_name}.json",
                "JSON Files (*.json)",
            )
            if not path:
                return
            export_payload = export_advanced_scan_report_json_dict(report)
            import json
            Path(path).write_text(
                json.dumps(export_payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            _centered_message(self, "Export Complete", f"JSON report saved:\n\n{path}")
            return

        if fmt == "md":
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Markdown Report",
                f"{default_name}.md",
                "Markdown Files (*.md)",
            )
            if not path:
                return

            lines = [
                "# DevVault Advanced Scan Report",
                "",
                "## Protection Status",
                report.protected_status_text,
                "",
                "## Scanned Directories",
                str(report.scanned_directories),
                "",
                "## Skipped Directories",
                str(report.skipped_directories),
                "",
                "## Uncovered Paths",
                str(report.uncovered_count),
                "",
                "## Scan Roots",
            ]
            for item in report.scan_roots:
                lines.append(f"- {item}")

            lines.append("")
            lines.append("## Uncovered Paths List")
            if report.uncovered_paths:
                for item in report.uncovered_paths:
                    lines.append(f"- {item}")
            else:
                lines.append("- None")

            Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
            _centered_message(self, "Export Complete", f"Markdown report saved:\n\n{path}")
            return

    def open_settings_menu(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Tools")
        dlg.setModal(True)
        dlg.setMinimumWidth(760)
        dlg.setStyleSheet(DEVVAULT_CUSTOM_DIALOG_STYLE)

        root = QVBoxLayout(dlg)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        title = QLabel("Tools", dlg)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:22px;font-weight:700;")
        root.addWidget(title)

        subtitle = QLabel("Choose a tool or action:", dlg)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color:#d7b300;font-size:14px;")
        root.addWidget(subtitle)

        row1 = QHBoxLayout()
        row1.setSpacing(10)

        btn_install = QPushButton("Install License", dlg)
        btn_validate = QPushButton("Validate License", dlg)
        btn_pro = QPushButton("Pro Tools", dlg)

        for b in (btn_install, btn_validate, btn_pro):
            b.setMinimumHeight(44)
            row1.addWidget(b)

        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)

        btn_business = QPushButton("Business Tools", dlg)
        btn_business_sign_in = QPushButton("Business Admin Sign In", dlg)
        btn_business_sign_out = QPushButton("Business Admin Sign Out", dlg)
        btn_seat_activation = QPushButton("Seat Activation", dlg)

        for b in (btn_business, btn_seat_activation, btn_business_sign_in, btn_business_sign_out):
            b.setMinimumHeight(44)
            row2.addWidget(b)

        root.addLayout(row2)

        btn_close = QPushButton("Close", dlg)
        btn_close.setMinimumHeight(40)
        btn_close.clicked.connect(dlg.reject)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_row.addWidget(btn_close)
        root.addLayout(close_row)

        btn_install.clicked.connect(lambda: (dlg.accept(), self.install_license()))
        btn_validate.clicked.connect(lambda: (dlg.accept(), self.validate_license_now()))
        btn_pro.clicked.connect(lambda: (dlg.accept(), self.open_pro_features()))
        btn_business.clicked.connect(lambda: (dlg.accept(), self.open_business_tools()))
        btn_seat_activation.clicked.connect(lambda: (dlg.accept(), self._seat_activation_bootstrap()))
        btn_business_sign_in.clicked.connect(lambda: (dlg.accept(), self._business_admin_sign_in()))
        btn_business_sign_out.hide()

        try:
            _center_widget_on_parent(dlg, self)
            QTimer.singleShot(0, lambda: _center_widget_on_parent(dlg, self))
        except Exception:
            pass

        dlg.exec()

    def validate_license_now(self) -> None:


        self.append_log("Manual license validation requested.")
        try:
            result = validate_now()
            self.append_log(result.message)

            if result.result == "valid":
                self._refresh_license_panel()
                st = check_license()
                self.append_log(f"License state: {st.state}")
                self.append_log(st.message)
                try:
                    _centered_message(
                        self,
                        "License Validation",
                        result.message,
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.Icon.Information,
                    )
                except Exception:
                    pass
                return

            if result.result == "license_update_required":
                self._refresh_license_panel()
                try:
                    _centered_message(
                        self,
                        "License Update Required",
                        (
                            "A newer DevVault license is available for this installation.\n\n"
                            "Backups remain available, but you should install the updated\n"
                            "license file to maintain uninterrupted validation.\n\n"
                            "Use 'Install License' to import the new license file."
                        ),
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.Icon.Warning,
                    )
                except Exception:
                    pass
                return

            if result.result == "validation_service_internal_error":
                self._refresh_license_panel()
                try:
                    _centered_message(
                        self,
                        "License Validation",
                        (
                            "License validation reached the server, but the validation service "
                            "reported an internal error.\n\n"
                            "Your current local license state remains unchanged.\n\n"
                            "Please try validation again shortly."
                        ),
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.Icon.Warning,
                    )
                except Exception:
                    pass
                return

            if result.result == "revoked":
                self._refresh_license_panel()
                try:
                    _centered_message(
                        self,
                        "License Revoked",
                        (
                            "This DevVault license has been revoked.\n\n"
                            "Backups are disabled. Restore operations remain available.\n\n"
                            "Install a valid license or contact Trustware support."
                        ),
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.Icon.Critical,
                    )
                except Exception:
                    pass
                return

            if result.result == "unknown_license":
                self._refresh_license_panel()
                try:
                    _centered_message(
                        self,
                        "License Not Recognized",
                        (
                            "This DevVault license was not recognized by the validation service.\n\n"
                            "Backups are disabled. Restore operations remain available.\n\n"
                            "Install a valid license or contact Trustware support."
                        ),
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.StandardButton.Ok,
                        QMessageBox.Icon.Critical,
                    )
                except Exception:
                    pass
                return

            self._refresh_license_panel()
            try:
                _centered_message(
                    self,
                    "License Validation",
                    result.message,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.StandardButton.Ok,
                    QMessageBox.Icon.Warning,
                )
            except Exception:
                pass

        except Exception as e:
            self.append_log(f"Manual validation failed: {e}")
            try:
                self._refresh_license_panel()
            except Exception:
                pass

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

        chosen = Path(folder)

        try:
            if not self._confirm_large_folder_backup(chosen):
                self.append_log("Backup canceled (operator declined large-folder backup).")
                return
        except Exception:
            pass

        self._start_backup_for_source(chosen)

    def _start_backup_for_source(self, source_dir: Path) -> None:
        if not self._require_action_entitlement("core_backup_engine", action_name="Backup"):
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
                    _centered_message(
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

        # Vault capacity refusal is handled inside subprocess preflight.
        vault_total = None
        vault_free = None

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

    
    def _on_backup_pre_err(self, payload: object) -> None:
        # Stop overlay / modal state first so the refusal dialog is not blocked behind it.
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

        if isinstance(payload, dict):
            title, text = self._resolve_refusal_ui(payload)
            self.append_log(f"Backup preflight refused: {text}")
        else:
            text = str(payload or "").strip()
            title = "Backup Preflight Failed"
            self.append_log(f"Backup preflight refused: {text}")

        try:
            if getattr(self, "_backup_thread", None) is not None:
                self._backup_thread.quit()
        except Exception:
            pass

        self._set_busy(False)

        try:
            self._ui_critical(title, text)
        except Exception:
            pass

    def restore_backup(self) -> None:
        # 1) Select snapshot from hidden DevVault-managed snapshot store
        vault_dir = Path(self.vault_path).expanduser().resolve()

        try:
            from scanner.adapters.filesystem import OSFileSystem
            from scanner.snapshot_rows import get_snapshot_rows
            from scanner.snapshot_listing import snapshot_storage_root
            from devvault_desktop.business_vault_authority import validate_business_vault_authority

            authority = validate_business_vault_authority(vault_dir)
            if not authority.ok:
                _centered_message(self, "Restore Refused", authority.operator_message)
                self.append_log(f"Restore refused: {authority.state.value}: {authority.operator_message}")
                return

            fs = OSFileSystem()
            rows = get_snapshot_rows(fs=fs, backup_root=vault_dir)
            store_root = snapshot_storage_root(vault_dir)
        except Exception as e:
            _centered_message(self, "Restore Refused", f"Could not load snapshots: {e}")
            self.append_log(f"Restore refused: could not load snapshots: {e}")
            return

        if not rows:
            _centered_message(
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

        ok, selected_label = SnapshotSelectDialog.ask(self, labels)
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
            _centered_message(self, "Restore Refused", f"Could not prepare restore folder: {e}")
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
            if _centered_message(self, "OneDrive Destination Warning", warn, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
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
        if _centered_message(self, "Confirm Restore", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
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



class _BackupPreflightWorker(QObject):
    log = Signal(str)
    done = Signal(dict)
    error = Signal(object)

    def __init__(self, source_dir: Path, vault_dir: Path):
        self._business_nas_required = True # ensure defined early
        super().__init__()
        self.source_dir = Path(source_dir)
        self.vault_dir = Path(vault_dir)

    def run(self) -> None:
        try:
            from devvault_desktop.engine_subprocess import _backup_preflight_payload

            self.log.emit("Backup preflight started...")
            result = _backup_preflight_payload(self.source_dir, self.vault_dir)

            if not isinstance(result, dict):
                self.error.emit("Backup preflight returned an invalid response.")
                return

            if result.get("ok", True) is False:
                self.error.emit(result)
                return

            payload = result.get("payload")
            if not isinstance(payload, dict):
                self.error.emit("Backup preflight payload was missing or invalid.")
                return

            self.done.emit(payload)
        except Exception as e:
            self.error.emit(str(e))


class _BackupExecuteWorker(QObject):
    log = Signal(str)
    done = Signal(dict)
    error = Signal(object)

    def __init__(self, source_dir: Path, vault_dir: Path):
        self._business_nas_required = True # ensure defined early
        super().__init__()
        self.source_dir = Path(source_dir)
        self.vault_dir = Path(vault_dir)
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            from devvault_desktop.engine_subprocess import run_backup_execute_with_drive_watch

            self.log.emit("Backup execution started...")
            result = run_backup_execute_with_drive_watch(
                self.source_dir,
                self.vault_dir,
                cancel_check=lambda: self._cancel_requested,
            )

            if not isinstance(result, dict):
                self.error.emit("Backup execution returned an invalid response.")
                return

            if result.get("ok", True) is False:
                self.error.emit(result)
                return

            self.done.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _RestoreWorker(QObject):
    log = Signal(str)
    done = Signal(dict)
    error = Signal(object)

    def __init__(self, snapshot_dir: Path, destination_dir: Path):
        self._business_nas_required = True # ensure defined early
        super().__init__()
        self.snapshot_dir = Path(snapshot_dir)
        self.destination_dir = Path(destination_dir)
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:
        try:
            from devvault_desktop.engine_subprocess import run_restore_with_drive_watch

            self.log.emit("Restore execution started...")
            result = run_restore_with_drive_watch(
                self.snapshot_dir,
                self.destination_dir,
                cancel_check=lambda: self._cancel_requested,
            )

            if not isinstance(result, dict):
                self.error.emit("Restore execution returned an invalid response.")
                return

            if result.get("ok", True) is False:
                self.error.emit(result)
                return

            self.done.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class _ScanWorker(QObject):
    log = Signal(str)
    done = Signal(dict)
    error = Signal(str)

    def __init__(self, *, business_mode: bool = False, business_nas_path: str = "") -> None:
        super().__init__()
        self._business_mode = bool(business_mode)
        self._business_nas_path = str(business_nas_path or "").strip()

    def run(self) -> None:
        try:
            thread = QThread.currentThread()

            if self._business_mode and self._business_nas_path:
                try:
                    set_vault_dir(self._business_nas_path)
                    self.log.emit(f"Business mode active: using NAS vault authority {self._business_nas_path}")
                except Exception as e:
                    self.log.emit(f"Warning: could not set Business NAS vault authority: {e}")

            scan_roots = []
            candidates = [
                Path("C:/"),
            ]

            for r in candidates:
                if thread.isInterruptionRequested():
                    self.error.emit("Scan cancelled by operator.")
                    return
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
                if thread.isInterruptionRequested():
                    self.error.emit("Scan cancelled by operator.")
                    return
                self.log.emit(f"Scan root: {r}")

            if thread.isInterruptionRequested():
                self.error.emit("Scan cancelled by operator.")
                return

            cov = compute_uncovered_candidates(
                scan_roots=scan_roots,
                depth=4,
                top=30,
            )

            if thread.isInterruptionRequested():
                self.error.emit("Scan cancelled by operator.")
                return

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























































































































# TODO: Section6 — Determine final placement for Force-Backup button
