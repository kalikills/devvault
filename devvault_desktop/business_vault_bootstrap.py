from pathlib import Path
import json
import uuid
import socket
from datetime import datetime, timezone
from scanner.vault_key_shared import init_shared_manifest_key
from scanner.adapters.filesystem import OSFileSystem
from scanner.snapshot_index import repair_snapshot_index


class BusinessVaultBootstrapError(Exception):
    pass


def _atomic_write_json(target: Path, data: dict) -> None:
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(target)


def bootstrap_business_vault(nas_root: Path) -> None:
    try:
        if not nas_root.exists():
            raise BusinessVaultBootstrapError("Business NAS path not reachable.")
    except Exception:
        raise BusinessVaultBootstrapError("Business NAS path not reachable.")

    dv = nas_root / ".devvault"

    if dv.exists():
        shared_key = dv / "manifest_hmac_key.shared"
        snapshots_dir = dv / "snapshots"

        fully_initialized = shared_key.exists() and snapshots_dir.exists()

        if fully_initialized:
            raise BusinessVaultBootstrapError(
                ".devvault already exists - strict bootstrap refusal (repair required)."
            )
    else:
        dv.mkdir(parents=True, exist_ok=False)

    (dv / "snapshots").mkdir(exist_ok=True)
    (dv / "index").mkdir(exist_ok=True)
    (dv / "metadata").mkdir(exist_ok=True)

    init_file = dv / "vault_init.json"

    initializing_doc = {
        "schema_version": 1,
        "state": "initializing",
        "vault_contract_version": 1,
        "initialized_at_utc": datetime.now(timezone.utc).isoformat(),
        "initialized_by": {
            "hostname": socket.gethostname(),
            "device_id": f"dev_{uuid.uuid4().hex[:8]}",
        },
        "key_model": "shared-vault-key-v1",
        "structure": {
            "snapshots_dir": "snapshots",
            "index_dir": "index",
            "metadata_dir": "metadata",
        },
    }

    _atomic_write_json(init_file, initializing_doc)

    init_shared_manifest_key(nas_root)
    repair_snapshot_index(fs=OSFileSystem(), backup_root=nas_root)

    ready_doc = dict(initializing_doc)
    ready_doc["state"] = "ready"

    _atomic_write_json(init_file, ready_doc)
