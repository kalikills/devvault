from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

PROGRAMDATA = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
RUNTIME_DIR = Path(PROGRAMDATA) / "DevVault"
RUNTIME_FILE = RUNTIME_DIR / "business_runtime.json"

DEFAULT_BUSINESS_API_BASE_URL = "https://65xctm6uikd7qfnbghdefzda2i0jfewe.lambda-url.us-east-1.on.aws"
ENV_NAME = "DEVVAULT_BUSINESS_API_BASE_URL"


def ensure_runtime_dir() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def runtime_exists() -> bool:
    return RUNTIME_FILE.exists()


def load_runtime() -> Optional[Dict[str, Any]]:
    if not RUNTIME_FILE.exists():
        return None
    try:
        return json.loads(RUNTIME_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_runtime(data: Dict[str, Any]) -> None:
    ensure_runtime_dir()
    tmp = RUNTIME_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(RUNTIME_FILE)


def clear_runtime() -> None:
    if RUNTIME_FILE.exists():
        RUNTIME_FILE.unlink()


def get_mode() -> str:
    data = load_runtime()
    if not data:
        return "setup"
    return str(data.get("mode") or "setup")


def is_active() -> bool:
    return get_mode() == "active"


def get_business_runtime_config_path() -> Path:
    return RUNTIME_FILE


def _normalize_base_url(value: str) -> str:
    value = (value or "").strip()
    return value.rstrip("/")


def load_business_runtime_config() -> dict[str, Any]:
    data = load_runtime()
    if not data:
        return {}
    if not isinstance(data, dict):
        raise RuntimeError(
            f"Business runtime config must be a JSON object: {RUNTIME_FILE}"
        )
    return data


def ensure_business_runtime_config() -> Path:
    ensure_runtime_dir()
    data = load_runtime() or {}
    if not str(data.get("api_base_url") or "").strip():
        data["api_base_url"] = DEFAULT_BUSINESS_API_BASE_URL
        save_runtime(data)
    return RUNTIME_FILE


def get_business_api_base_url() -> str:
    cfg = load_business_runtime_config()
    runtime_value = _normalize_base_url(str(cfg.get("api_base_url", "")))
    legacy_value = _normalize_base_url(str(cfg.get("business_api_base_url", "")))
    built_in = _normalize_base_url(DEFAULT_BUSINESS_API_BASE_URL)
    env_value = _normalize_base_url(os.environ.get(ENV_NAME, ""))

    if env_value:
        return env_value
    if runtime_value:
        return runtime_value
    if legacy_value:
        return legacy_value
    return built_in


def describe_business_api_base_url_source() -> str:
    env_value = _normalize_base_url(os.environ.get(ENV_NAME, ""))
    if env_value:
        return "env"

    cfg = load_business_runtime_config()
    runtime_value = _normalize_base_url(str(cfg.get("api_base_url", "")))
    if runtime_value:
        return "runtime"

    legacy_value = _normalize_base_url(str(cfg.get("business_api_base_url", "")))
    if legacy_value:
        return "legacy_json"

    return "built_in"
