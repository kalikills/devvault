from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from devvault_desktop.business_fleet_status import publish_business_fleet_status
from devvault_desktop.business_protection_state import load_business_protection_state
from devvault_desktop.business_runtime_config import get_business_api_base_url, load_runtime


APP_NAME = "DevVault"
DEFAULT_INTERVAL_SECONDS = 30
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_API_BASE_ENV = "DEVVAULT_BUSINESS_API_BASE_URL"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _machine_data_dir() -> Path:
    p = Path(r"C:\ProgramData") / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path() -> Path:
    return _machine_data_dir() / "business_worker_state.json"


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")




def _worker_log_path() -> Path:
    return _machine_data_dir() / "business_worker.log"


def _log_worker_line(message: str) -> None:
    try:
        ts = utc_now_iso()
        line = f"{ts} | {message.strip()}\n"
        _worker_log_path().open("a", encoding="utf-8").write(line)
    except Exception:
        pass



def trim_message(text: str, limit: int = 500) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    data: bytes | None = None
    headers = {"Content-Type": "application/json"}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = Request(url=url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc

    try:
        outer = json.loads(raw)
    except Exception as exc:
        raise RuntimeError(f"Non-JSON response from {url}: {raw}") from exc

    if isinstance(outer, dict) and "body" in outer:
        body = outer.get("body")
        if isinstance(body, str):
            try:
                return json.loads(body)
            except Exception:
                return {"raw_body": body}
        if isinstance(body, dict):
            return body

    return outer if isinstance(outer, dict) else {"raw": outer}


@dataclass
class WorkerConfig:
    api_base_url: str
    seat_id: str
    fleet_id: str
    subscription_id: str
    customer_id: str
    assigned_device_id: str | None
    assigned_hostname: str | None
    business_nas_path: str | None
    interval_seconds: int
    backup_cmd: str | None


class BusinessServiceWorker:
    def __init__(self, cfg: WorkerConfig) -> None:
        self.cfg = cfg
        self.state_path = _state_path()
        self.state = load_json_file(self.state_path)
        if not str(self.state.get("service_started_at") or "").strip():
            self.state["service_started_at"] = utc_now_iso()
            self.save_state()

    @classmethod
    def from_local_config(
        cls,
        *,
        api_base_url: str,
        interval_seconds: int,
        backup_cmd: str | None,
    ) -> "BusinessServiceWorker":
        runtime = load_runtime() or {}
        identity = runtime.get("seat") or {}

        seat_id = str(identity.get("seat_id") or "").strip()
        fleet_id = str(identity.get("fleet_id") or "").strip()
        subscription_id = str(identity.get("subscription_id") or "").strip()
        customer_id = str(identity.get("customer_id") or "").strip()

        if not seat_id:
            raise RuntimeError(
                "No local Business seat identity found in ProgramData runtime config."
            )
        if not fleet_id or not subscription_id or not customer_id:
            raise RuntimeError(
                "Incomplete Business seat identity in ProgramData runtime config."
            )

        assigned_device_id = str(identity.get("assigned_device_id") or "").strip() or None
        assigned_hostname = str(identity.get("assigned_hostname") or "").strip() or None
        business_nas_path = str(((runtime.get("storage") or {}).get("nas_path")) or "").strip() or None

        return cls(
            WorkerConfig(
                api_base_url=api_base_url.rstrip("/"),
                seat_id=seat_id,
                fleet_id=fleet_id,
                subscription_id=subscription_id,
                customer_id=customer_id,
                assigned_device_id=assigned_device_id,
                assigned_hostname=assigned_hostname,
                business_nas_path=business_nas_path,
                interval_seconds=interval_seconds,
                backup_cmd=backup_cmd,
            )
        )

    def save_state(self) -> None:
        save_json_file(self.state_path, self.state)

    def heartbeat_payload(self) -> dict[str, Any]:
        protection_state = load_business_protection_state()
        unprotected_count = max(0, int(protection_state.get("unprotected_count", 0) or 0))
        last_local_update_at = str(protection_state.get("last_local_update_at") or "").strip() or utc_now_iso()
        protection_status = str(protection_state.get("status") or "").strip().lower()
        if not protection_status:
            protection_status = "attention_required" if unprotected_count > 0 else "protected"

        payload: dict[str, Any] = {
            "seat_id": self.cfg.seat_id,
            "fleet_id": self.cfg.fleet_id,
            "subscription_id": self.cfg.subscription_id,
            "customer_id": self.cfg.customer_id,
            "reported_at": utc_now_iso(),
            "hostname": socket.gethostname(),
            "app_version": os.environ.get("DEVVAULT_APP_VERSION", "").strip(),
            "sent_at": utc_now_iso(),
            "service_started_at": str(self.state.get("service_started_at") or "").strip() or utc_now_iso(),
            "last_local_update_at": last_local_update_at,
            "presence": {
                "worker_online": True,
                "hostname": socket.gethostname(),
            },
            "protection": {
                "status": protection_status,
                "protected": unprotected_count <= 0,
                "unprotected_count": unprotected_count,
                "last_unprotected_detected_at": str(protection_state.get("last_unprotected_detected_at") or "").strip(),
                "last_backup_completed_at": str(protection_state.get("last_backup_completed_at") or "").strip(),
            },
            "findings_summary": {
                "attention_count": unprotected_count,
                "unprotected_count": unprotected_count,
                "status_message": str(protection_state.get("status_message") or "").strip(),
            },
            "command_state": {},
        }
        if self.cfg.assigned_device_id:
            payload["device_id"] = self.cfg.assigned_device_id
            payload["assigned_device_id"] = self.cfg.assigned_device_id
        if self.cfg.assigned_hostname:
            payload["assigned_hostname"] = self.cfg.assigned_hostname
        return payload

    def send_heartbeat(self) -> dict[str, Any]:
        url = f"{self.cfg.api_base_url}/api/business/fleet/seat-heartbeat"
        payload = self.heartbeat_payload()

        resp = request_json(method="POST", url=url, payload=payload)

        self.state["last_heartbeat_at"] = utc_now_iso()
        self.state["last_heartbeat_response"] = resp
        _log_worker_line("heartbeat_ok")
        self.save_state()

        try:
            protection_state = load_business_protection_state()
            publish_business_fleet_status(
                nas_path=str(self.cfg.business_nas_path or "").strip(),
                seat_id=self.cfg.seat_id,
                assigned_hostname=str(self.cfg.assigned_hostname or "").strip(),
                seat_label=str(self.cfg.assigned_hostname or "").strip(),
                status=str(protection_state.get("status") or "").strip().lower(),
                status_message=str(protection_state.get("status_message") or "").strip(),
                unprotected_count=int(protection_state.get("unprotected_count", 0) or 0),
                last_local_update_at=str(protection_state.get("last_local_update_at") or "").strip(),
            )
        except Exception as exc:
            self.state["last_fleet_status_publish_error_at"] = utc_now_iso()
            self.state["last_fleet_status_publish_error"] = trim_message(str(exc), 1000)
            self.save_state()

        return resp


    def update_action(
        self,
        *,
        action_id: str,
        status: str,
        result_message: str,
    ) -> dict[str, Any]:
        url = f"{self.cfg.api_base_url}/api/business/fleet/action/update"
        payload = {
            "action_id": action_id,
            "seat_id": self.cfg.seat_id,
            "status": status,
            "result_message": trim_message(result_message),
            "reported_at": utc_now_iso(),
        }
        resp = request_json(method="POST", url=url, payload=payload)
        self.state["last_action_update_at"] = utc_now_iso()
        self.state["last_action_update_response"] = resp
        self.save_state()
        return resp

    def _run_backup_command(self) -> tuple[bool, str]:
        cmd = (self.cfg.backup_cmd or "").strip()
        if not cmd:
            return False, "No backup command configured for worker."

        completed = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        stdout = trim_message(completed.stdout or "")
        stderr = trim_message(completed.stderr or "")

        if completed.returncode == 0:
            msg = "Backup command completed successfully."
            if stdout:
                msg += f" stdout: {stdout}"
            return True, msg

        msg = f"Backup command failed with exit code {completed.returncode}."
        if stderr:
            msg += f" stderr: {stderr}"
        elif stdout:
            msg += f" stdout: {stdout}"
        return False, msg


    def _append_recent_action(
        self,
        *,
        action_id: str,
        action_name: str,
        status: str,
        started_at: str,
        finished_at: str,
        duration_seconds: float,
        result_message: str,
        retry_count: int = 0,
    ) -> None:
        try:
            items = self.state.get("recent_actions")
            if not isinstance(items, list):
                items = []

            items.append(
                {
                    "action_id": str(action_id or "").strip(),
                    "action_name": str(action_name or "").strip(),
                    "status": str(status or "").strip(),
                    "started_at": str(started_at or "").strip(),
                    "finished_at": str(finished_at or "").strip(),
                    "duration_seconds": round(float(duration_seconds), 3),
                    "result_message": trim_message(result_message, 1000),
                    "retry_count": int(retry_count or 0),
                }
            )

            self.state["recent_actions"] = items[-20:]
            self.save_state()
        except Exception:
            pass

    def process_action(self, action: dict[str, Any]) -> None:
        action_id = str(
            action.get("action_id")
            or action.get("id")
            or ""
        ).strip()

        action_name = str(
            action.get("action")
            or action.get("action_type")
            or action.get("command")
            or ""
        ).strip().lower()

        if not action_id:
            return

        if action_name != "force_backup_now":
            self.update_action(
                action_id=action_id,
                status="failed",
                result_message=f"Unsupported action: {action_name or 'unknown'}",
            )
            self._append_recent_action(
                action_id=action_id,
                action_name=action_name or "unknown",
                status="failed",
                started_at=utc_now_iso(),
                finished_at=utc_now_iso(),
                duration_seconds=0.0,
                result_message=f"Unsupported action: {action_name or 'unknown'}",
                retry_count=0,
            )
            return

        started_at = utc_now_iso()
        started_mono = time.monotonic()

        self.update_action(
            action_id=action_id,
            status="running",
            result_message="Backup execution started by business worker.",
        )
        _log_worker_line(f"action_start:{action_id}")

        ok, message = self._run_backup_command()
        final_status = "succeeded" if ok else "failed"
        finished_at = utc_now_iso()
        duration_seconds = time.monotonic() - started_mono

        _log_worker_line(f"action_result:{action_id}:{'success' if ok else 'fail'}")

        self.update_action(
            action_id=action_id,
            status=final_status,
            result_message=message,
        )

        self._append_recent_action(
            action_id=action_id,
            action_name=action_name or "force_backup_now",
            status=final_status,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            result_message=message,
            retry_count=0,
        )

    def run_once(self) -> int:
        resp = self.send_heartbeat()
        actions = resp.get("actions")
        if not isinstance(actions, list):
            actions = []

        self.state["last_action_count"] = len(actions)
        self.save_state()

        for action in actions:
            if isinstance(action, dict):
                self.process_action(action)

        return 0

    def run_loop(self) -> int:
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                return 0
            except Exception as exc:
                self.state["last_error_at"] = utc_now_iso()
                self.state["last_error"] = trim_message(str(exc), 1000)
                _log_worker_line(f"heartbeat_error: {str(exc)}")
                self.save_state()
                try:
                    time.sleep(2)
                    self.run_once()
                except KeyboardInterrupt:
                    return 0
                except Exception as retry_exc:
                    self.state["last_retry_error_at"] = utc_now_iso()
                    self.state["last_retry_error"] = trim_message(str(retry_exc), 1000)
                    _log_worker_line(f"heartbeat_retry_error: {str(retry_exc)}")
                    self.save_state()
            time.sleep(max(5, int(self.cfg.interval_seconds)))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DevVault Business fleet action worker"
    )
    parser.add_argument(
        "--api-base-url",
        default=get_business_api_base_url() or None,
        help="Business API base URL. Defaults to ProgramData runtime config, then built-in production URL, with DEVVAULT_BUSINESS_API_BASE_URL as override.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Polling interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--backup-cmd",
        default=None,
        help="Command to run when force_backup_now is received.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single heartbeat/action cycle and exit.",
    )
    return parser.parse_args(argv)




def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    api_base_url = str(args.api_base_url or "").strip()
    if not api_base_url:
        raise RuntimeError("No Business API base URL available.")

    worker = BusinessServiceWorker.from_local_config(
        api_base_url=api_base_url,
        interval_seconds=args.interval,
        backup_cmd=args.backup_cmd,
    )

    if args.once:
        print('[worker] running single execution mode')
        return worker.run_once()
    return worker.run_loop()


if __name__ == "__main__":
    raise SystemExit(main())
