from __future__ import annotations

import ctypes
from pathlib import Path

APP_ID = "Trustware.DevVault"

try:
    from winotify import Notification, audio
except Exception:
    Notification = None
    audio = None


def _message_box(title: str, message: str) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, str(message), str(title), 0x00000040)
    except Exception:
        pass


def show_toast(title: str, message: str) -> None:
    if Notification is None:
        _message_box(title, message)
        return

    try:
        icon_path = Path(__file__).resolve().parents[1] / "devvault_desktop" / "assets" / "icon.png"
        toast = Notification(
            app_id=APP_ID,
            title=str(title),
            msg=str(message),
            icon=str(icon_path) if icon_path.exists() else "",
            duration="short",
        )
        if audio is not None:
            toast.set_audio(audio.Default, loop=False)
        toast.show()
    except Exception:
        _message_box(title, message)
