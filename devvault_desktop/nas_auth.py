from __future__ import annotations

import subprocess


def _run(cmd: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _normalize_unc_host(target: str) -> str:
    t = str(target or "").strip()
    if not t:
        return ""
    if t.startswith("\\\\"):
        t = t[2:]
    return t.split("\\", 1)[0].strip()


def save_windows_nas_credentials(target: str, username: str, password: str) -> tuple[bool, str]:
    host = _normalize_unc_host(target)
    if not host:
        return False, "UNC host is required."

    username = str(username or "").strip()
    password = str(password or "")

    if not username:
        return False, "Username is required."
    if not password:
        return False, "Password is required."

    try:
        r = _run(["cmdkey", f"/add:{host}", f"/user:{username}", f"/pass:{password}"])
    except Exception as e:
        return False, f"Could not save NAS credentials: {e}"

    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "cmdkey failed").strip()
        return False, msg

    # Force a real auth test using IPC$
    ipc_target = rf"\\{host}\IPC$"

    try:
        # Clear any stale IPC$ session first (ignore failure)
        _run(["net", "use", ipc_target, "/delete", "/y"], timeout=15)

        auth = _run(
            ["net", "use", ipc_target, password, f"/user:{username}"],
            timeout=20,
        )
    except Exception as e:
        return False, f"Credential saved, but verification failed: {e}"

    if auth.returncode != 0:
        msg = (auth.stderr or auth.stdout or "IPC$ auth test failed").strip()
        return False, f"Credential saved, but verification failed: {msg}"

    # Disconnect test session
    try:
        _run(["net", "use", ipc_target, "/delete", "/y"], timeout=15)
    except Exception:
        pass

    return True, f"Saved and verified Windows NAS credentials for {host}."


def delete_windows_nas_credentials(target: str) -> tuple[bool, str]:
    host = _normalize_unc_host(target)
    if not host:
        return False, "UNC host is required."

    try:
        r = _run(["cmdkey", f"/delete:{host}"])
    except Exception as e:
        return False, f"Could not delete NAS credentials: {e}"

    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "cmdkey failed").strip()
        return False, msg

    return True, f"Deleted Windows NAS credentials for {host}."
