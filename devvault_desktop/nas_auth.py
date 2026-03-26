from __future__ import annotations
import subprocess
from dataclasses import dataclass


@dataclass
class NASAuthResult:
    ok: bool
    operator_message: str


def _run_net_use_disconnect(unc: str) -> None:
    try:
        subprocess.run(
            ["net", "use", unc, "/delete", "/y"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception:
        pass


def connect_smb_share(unc: str, username: str, password: str) -> NASAuthResult:
    if not unc:
        return NASAuthResult(False, "UNC path is empty.")

    if not username:
        return NASAuthResult(False, "Username is required.")

    _run_net_use_disconnect(unc)

    try:
        result = subprocess.run(
            ["net", "use", unc, f"/user:{username}", password],
            capture_output=True,
            text=True,
            timeout=12,
        )
    except Exception as e:
        return NASAuthResult(False, f"SMB authentication failed to execute: {e}")

    if result.returncode == 0:
        return NASAuthResult(
            True,
            f"Authentication OK. Windows SMB session established for {unc}",
        )

    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    msg = stderr or stdout or "Windows refused SMB login."

    return NASAuthResult(False, msg)
