from __future__ import annotations

import base64
import os
from pathlib import Path

from scanner.errors import SnapshotCorrupt


def _is_windows() -> bool:
    return os.name == "nt"


def _vault_key_dir(vault_root: Path) -> Path:
    return vault_root / ".devvault"


def _vault_key_path(vault_root: Path) -> Path:
    return _vault_key_dir(vault_root) / "manifest_hmac_key.dpapi.b64"


def _dpapi_protect_local_machine(plaintext: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    CryptProtectData = crypt32.CryptProtectData
    CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    CryptProtectData.restype = wintypes.BOOL

    LocalFree = kernel32.LocalFree
    LocalFree.argtypes = [ctypes.c_void_p]
    LocalFree.restype = ctypes.c_void_p

    in_blob = DATA_BLOB(
        len(plaintext),
        ctypes.cast(ctypes.create_string_buffer(plaintext), ctypes.POINTER(ctypes.c_byte)),
    )
    out_blob = DATA_BLOB()

    CRYPTPROTECT_LOCAL_MACHINE = 0x4
    ok = CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None, CRYPTPROTECT_LOCAL_MACHINE, ctypes.byref(out_blob)
    )
    if not ok:
        raise RuntimeError("DPAPI protect failed.")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        LocalFree(out_blob.pbData)


def _dpapi_unprotect(ciphertext: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    CryptUnprotectData = crypt32.CryptUnprotectData
    CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    ]
    CryptUnprotectData.restype = wintypes.BOOL

    LocalFree = kernel32.LocalFree
    LocalFree.argtypes = [ctypes.c_void_p]
    LocalFree.restype = ctypes.c_void_p

    in_blob = DATA_BLOB(
        len(ciphertext),
        ctypes.cast(ctypes.create_string_buffer(ciphertext), ctypes.POINTER(ctypes.c_byte)),
    )
    out_blob = DATA_BLOB()

    ok = CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob))
    if not ok:
        raise RuntimeError("DPAPI unprotect failed.")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        LocalFree(out_blob.pbData)


def try_load_manifest_hmac_key(vault_root: Path) -> bytes | None:
    kp = _vault_key_path(vault_root)
    if not kp.exists():
        return None

    raw = kp.read_text(encoding="utf-8").strip()
    if raw == "":
        raise SnapshotCorrupt("Vault key file is empty; refusing.")

    try:
        blob = base64.b64decode(raw, validate=True)
    except Exception:
        raise SnapshotCorrupt("Vault key file is invalid base64; refusing.") from None

    if not _is_windows():
        raise SnapshotCorrupt("Vault-managed key requires Windows DPAPI; refusing (non-Windows runtime).")

    try:
        key = _dpapi_unprotect(blob)
    except Exception:
        raise SnapshotCorrupt("Vault-managed key could not be unprotected; refusing.") from None

    if len(key) < 32:
        raise SnapshotCorrupt("Vault-managed key is invalid (too short); refusing.")
    return key[:32]


def init_manifest_hmac_key_if_missing(vault_root: Path) -> bytes | None:
    if not _is_windows():
        return None

    kp = _vault_key_path(vault_root)
    if kp.exists():
        return try_load_manifest_hmac_key(vault_root)

    kd = _vault_key_dir(vault_root)
    kd.mkdir(parents=True, exist_ok=True)

    key = os.urandom(32)
    blob = _dpapi_protect_local_machine(key)
    b64 = base64.b64encode(blob).decode("ascii")

    tmp = kp.with_suffix(kp.suffix + ".tmp")
    tmp.write_text(b64 + "\n", encoding="utf-8")
    tmp.replace(kp)

    return key
