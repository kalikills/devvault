from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROGRAMDATA_RUNTIME_PATH = Path(r"C:\ProgramData\DevVault\business_runtime.json")
DEFAULT_BUSINESS_API_BASE_URL = "https://65xctm6uikd7qfnbghdefzda2i0jfewe.lambda-url.us-east-1.on.aws"
ENV_NAME = "DEVVAULT_BUSINESS_API_BASE_URL"


def get_business_runtime_config_path() -> Path:
    return PROGRAMDATA_RUNTIME_PATH


def _normalize_base_url(value: str) -> str:
    value = (value or "").strip()
    return value.rstrip("/")


def load_business_runtime_config() -> dict[str, Any]:
    path = get_business_runtime_config_path()
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(
            f"Business runtime config is invalid: {path} :: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(
            f"Business runtime config must be a JSON object: {path}"
        )
    return data


def ensure_business_runtime_config() -> Path:
    path = get_business_runtime_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        payload = {
            "business_api_base_url": DEFAULT_BUSINESS_API_BASE_URL,
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def get_business_api_base_url() -> str:
    cfg = load_business_runtime_config()
    json_value = _normalize_base_url(str(cfg.get("business_api_base_url", "")))
    built_in = _normalize_base_url(DEFAULT_BUSINESS_API_BASE_URL)
    env_value = _normalize_base_url(os.environ.get(ENV_NAME, ""))

    if env_value:
        return env_value
    if json_value:
        return json_value
    return built_in


def describe_business_api_base_url_source() -> str:
    env_value = _normalize_base_url(os.environ.get(ENV_NAME, ""))
    if env_value:
        return "env"

    cfg = load_business_runtime_config()
    json_value = _normalize_base_url(str(cfg.get("business_api_base_url", "")))
    if json_value:
        return "json"

    return "built_in"
