from pathlib import Path
import json
import uuid
import socket
from datetime import datetime, timezone
from scanner.vault_key_shared import init_shared_manifest_key


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
        raise BusinessVaultBootstrapError(
            ".devvault already exists - strict bootstrap refusal (repair required)."
        )

    dv.mkdir(parents=True, exist_ok=False)

    (dv / "snapshots").mkdir()
    (dv / "index").mkdir()
    (dv / "metadata").mkdir()

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

    ready_doc = dict(initializing_doc)
    ready_doc["state"] = "ready"

    _atomic_write_json(init_file, ready_doc)
