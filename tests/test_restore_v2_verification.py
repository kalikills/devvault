from __future__ import annotations

import json
from pathlib import Path

import pytest

from scanner.adapters.filesystem import OSFileSystem
from scanner.checksum import hash_path
from scanner.manifest_integrity import add_integrity_block
from scanner.integrity_keys import load_manifest_hmac_key_from_env
from scanner.restore_engine import RestoreEngine, RestoreRequest


def _write_v2_manifest(
    snapshot_dir: Path,
    rel_path: str,
    size: int,
    digest_hex: str,
    *,
    with_integrity: bool = False,
) -> None:
    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "files": [
            {
                "path": rel_path,
                "size": size,
                "type": "file",
                "digest_hex": digest_hex,
            }
        ],
    }

    if with_integrity:
        manifest = add_integrity_block(manifest)

    (snapshot_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def test_restore_v2_verifies_checksum_success(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"

    snapshot.mkdir()
    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    d = hash_path(fs, data_file, algo="sha256")
    _write_v2_manifest(snapshot, "hello.txt", size=data_file.stat().st_size, digest_hex=d.hex)

    engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    out = dst / "hello.txt"
    assert out.exists()
    assert out.read_text(encoding="utf-8") == "hello"


def test_restore_v2_checksum_mismatch_fails_and_does_not_promote(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"

    snapshot.mkdir()
    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    bad_digest = "0" * 64  # valid hex length, wrong value
    _write_v2_manifest(snapshot, "hello.txt", size=data_file.stat().st_size, digest_hex=bad_digest)

    with pytest.raises(RuntimeError, match="checksum mismatch"):
        engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    # Final file should NOT exist (we only ever promote after verification)
    assert not (dst / "hello.txt").exists()


def test_restore_rejects_manifest_integrity_mismatch(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"

    snapshot.mkdir()
    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    d = hash_path(fs, data_file, algo="sha256")
    _write_v2_manifest(
        snapshot,
        "hello.txt",
        size=data_file.stat().st_size,
        digest_hex=d.hex,
        with_integrity=True,
    )

    # Tamper with manifest after integrity is computed.
    manifest_path = snapshot / "manifest.json"
    tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
    tampered["files"][0]["size"] = tampered["files"][0]["size"] + 1
    manifest_path.write_text(json.dumps(tampered, indent=2, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeError, match="integrity check failed"):
        engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    # Fail-closed: destination should not be created as a side effect.
    assert not dst.exists()


def test_restore_rejects_hmac_manifest_when_key_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"
    snapshot.mkdir()

    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    d = hash_path(fs, data_file, algo="sha256")

    # Create a manifest with HMAC integrity using a known key.
    monkeypatch.setenv("DEVVAULT_MANIFEST_HMAC_KEY_HEX", "11" * 32)
    hmac_key = load_manifest_hmac_key_from_env()
    assert hmac_key is not None

    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "files": [
            {"path": "hello.txt", "size": data_file.stat().st_size, "type": "file", "digest_hex": d.hex}
        ],
    }
    manifest = add_integrity_block(manifest, hmac_key=hmac_key)
    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    # Now simulate restore on a machine without the key: MUST fail closed.
    monkeypatch.delenv("DEVVAULT_MANIFEST_HMAC_KEY_HEX", raising=False)

    with pytest.raises(RuntimeError, match="integrity check failed"):
        engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    assert not dst.exists()


def test_restore_accepts_hmac_manifest_when_key_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"
    snapshot.mkdir()

    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    d = hash_path(fs, data_file, algo="sha256")

    # Set the key and write an HMAC manifest.
    monkeypatch.setenv("DEVVAULT_MANIFEST_HMAC_KEY_HEX", "22" * 32)
    hmac_key = load_manifest_hmac_key_from_env()
    assert hmac_key is not None

    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "files": [
            {"path": "hello.txt", "size": data_file.stat().st_size, "type": "file", "digest_hex": d.hex}
        ],
    }
    manifest = add_integrity_block(manifest, hmac_key=hmac_key)
    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    out = dst / "hello.txt"
    assert out.exists()
    assert out.read_text(encoding="utf-8") == "hello"


def test_restore_accepts_crypto_scheme_none(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"
    snapshot.mkdir()

    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    d = hash_path(fs, data_file, algo="sha256")

    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "crypto": {"version": 1, "content": {"scheme": "none"}},
        "files": [
            {"path": "hello.txt", "size": data_file.stat().st_size, "type": "file", "digest_hex": d.hex}
        ],
    }
    manifest = add_integrity_block(manifest)

    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))
    assert (dst / "hello.txt").read_text(encoding="utf-8") == "hello"


def test_restore_rejects_unknown_crypto_scheme(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"
    snapshot.mkdir()

    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    d = hash_path(fs, data_file, algo="sha256")

    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "crypto": {"version": 1, "content": {"scheme": "aes-gcm"}},
        "files": [
            {"path": "hello.txt", "size": data_file.stat().st_size, "type": "file", "digest_hex": d.hex}
        ],
    }
    manifest = add_integrity_block(manifest)

    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeError, match="unsupported crypto scheme"):
        engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    assert not dst.exists()


def test_restore_accepts_crypto_scheme_aes_gcm_schema_only(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"
    snapshot.mkdir()

    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    d = hash_path(fs, data_file, algo="sha256")

    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "crypto": {
            "version": 1,
            "content": {
                "scheme": "aes-256-gcm",
                "key_id": "default",
                "aad": "manifest-v2",
                "nonce_policy": "per-file-random-12b",
            },
        },
        "files": [
            {"path": "hello.txt", "size": data_file.stat().st_size, "type": "file", "digest_hex": d.hex}
        ],
    }
    manifest = add_integrity_block(manifest)

    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    # Schema-only acceptance: restore currently ignores crypto scheme beyond validation.
    engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))
    assert (dst / "hello.txt").read_text(encoding="utf-8") == "hello"


def test_restore_rejects_aes_gcm_crypto_schema_when_missing_fields(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"
    snapshot.mkdir()

    data_file = snapshot / "hello.txt"
    data_file.write_text("hello", encoding="utf-8")

    d = hash_path(fs, data_file, algo="sha256")

    # Missing nonce_policy
    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "crypto": {
            "version": 1,
            "content": {
                "scheme": "aes-256-gcm",
                "key_id": "default",
                "aad": "manifest-v2",
            },
        },
        "files": [
            {"path": "hello.txt", "size": data_file.stat().st_size, "type": "file", "digest_hex": d.hex}
        ],
    }
    manifest = add_integrity_block(manifest)

    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    with pytest.raises(RuntimeError, match="nonce policy"):
        engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    assert not dst.exists()


def test_restore_rejects_invalid_manifest_json(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"
    snapshot.mkdir()

    # Put at least one file present so this can't be misdiagnosed as "empty snapshot".
    (snapshot / "hello.txt").write_text("hello", encoding="utf-8")

    # Malformed JSON must fail-closed and must not create destination as a side effect.
    (snapshot / "manifest.json").write_text("{", encoding="utf-8")

    with pytest.raises(RuntimeError):
        engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    assert not dst.exists()


def test_restore_rejects_manifest_missing_files(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"
    snapshot.mkdir()

    # Structurally invalid manifest (missing "files")
    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256"
    }

    import json
    (snapshot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError):
        engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    assert not dst.exists()


def test_restore_rejects_missing_snapshot_file(tmp_path: Path) -> None:
    fs = OSFileSystem()
    engine = RestoreEngine(fs)

    snapshot = tmp_path / "snapshot"
    dst = tmp_path / "dst"
    snapshot.mkdir()

    manifest = {
        "manifest_version": 2,
        "checksum_algo": "sha256",
        "files": [
            {"path": "ghost.txt", "size": 5, "type": "file", "digest_hex": "0"*64}
        ],
    }

    from scanner.manifest_integrity import add_integrity_block
    import json
    manifest = add_integrity_block(manifest)

    (snapshot / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError):
        engine.restore(RestoreRequest(snapshot_dir=snapshot, destination_dir=dst))

    assert not dst.exists()
