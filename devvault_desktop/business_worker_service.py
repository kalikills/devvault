import os
import sys
import threading
import time
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devvault_desktop.business_service_worker import BusinessServiceWorker


class DevVaultBusinessWorkerService(win32serviceutil.ServiceFramework):
    _svc_name_ = "DevVaultBusinessWorker"
    _svc_display_name_ = "DevVault Business Worker"
    _svc_description_ = "Runs the DevVault Business fleet heartbeat and action worker."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._stop_requested = False
        self._worker_thread = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._stop_requested = True
        win32event.SetEvent(self.stop_event)

    def _run_worker(self):
        api_base_url = os.environ.get("DEVVAULT_BUSINESS_API_BASE_URL", "").strip()
        if not api_base_url:
            raise RuntimeError("DEVVAULT_BUSINESS_API_BASE_URL is not set.")

        interval_raw = os.environ.get("DEVVAULT_BUSINESS_WORKER_INTERVAL", "").strip()
        try:
            interval_seconds = int(interval_raw) if interval_raw else 30
        except Exception:
            interval_seconds = 30

        backup_cmd = os.environ.get("DEVVAULT_BUSINESS_BACKUP_CMD", "").strip() or None

        worker = BusinessServiceWorker.from_local_config(
            api_base_url=api_base_url,
            interval_seconds=interval_seconds,
            backup_cmd=backup_cmd,
        )

        while not self._stop_requested:
            try:
                worker.run_once()
            except Exception as exc:
                worker.state["last_service_error_at"] = worker.state.get("last_service_error_at") or ""
                worker.state["last_service_error_at"] = __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat()
                worker.state["last_service_error"] = str(exc)[:1000]
                worker.save_state()

                if self._stop_requested:
                    break

                time.sleep(2)
                try:
                    worker.run_once()
                except Exception as retry_exc:
                    worker.state["last_service_retry_error_at"] = __import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ).isoformat()
                    worker.state["last_service_retry_error"] = str(retry_exc)[:1000]
                    worker.save_state()

            if self._stop_requested:
                break

            wait_ms = max(5, int(worker.cfg.interval_seconds)) * 1000
            rc = win32event.WaitForSingleObject(self.stop_event, wait_ms)
            if rc == win32event.WAIT_OBJECT_0:
                break

    def SvcDoRun(self):
        servicemanager.LogInfoMsg(f"{self._svc_name_} starting")
        self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self._worker_thread.start()

        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)

        self._stop_requested = True
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)

        servicemanager.LogInfoMsg(f"{self._svc_name_} stopped")


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(DevVaultBusinessWorkerService)
