from __future__ import annotations

import json

from dataclasses import dataclass
from pathlib import Path

from scanner.adapters.filesystem import OSFileSystem
from scanner.engine import scan as scan_engine
from scanner.models import ScanRequest
from scanner.snapshot_listing import list_snapshots
from scanner.snapshot_metadata import read_snapshot_metadata

from devvault_desktop.config import (
    get_ignored_candidates,
    get_protected_roots,
    get_vault_dir,
    get_known_vault_dirs,
)


DATA_ROOT_NAMES = {"pictures", "videos", "downloads"}
DATA_FOLDER_MIN_FILES = 35
ARCHIVE_MIN_BYTES = 10 * 1024 * 1024
ARCHIVE_EXTENSIONS = {
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
}
IGNORED_FILE_SUFFIXES = {
    ".tmp",
    ".temp",
    ".part",
    ".crdownload",
    ".ds_store",
}


@dataclass(frozen=True)
class CoverageResult:
    uncovered: list[Path]
    scanned_directories: int
    skipped_directories: int


def _is_covered(candidate: Path, protected_roots: list[Path]) -> bool:
    try:
        c = candidate.resolve()
    except Exception:
        c = candidate

    for r in protected_roots:
        try:
            rr = r.resolve()
        except Exception:
            rr = r

        try:
            c.relative_to(rr)
            return True
        except Exception:
            continue

    return False


def _known_vault_paths() -> list[Path]:
    known_vaults: list[str] = []
    active = (get_vault_dir() or "").strip()
    if active:
        known_vaults.append(active)

    for v in get_known_vault_dirs():
        if v not in known_vaults:
            known_vaults.append(v)

    out: list[Path] = []
    for vault_dir in known_vaults:
        try:
            p = Path(vault_dir).expanduser()
        except Exception:
            continue
        out.append(p)
    return out


def _is_devvault_runtime_path(candidate: Path) -> bool:
    try:
        p = candidate.expanduser().resolve()
    except Exception:
        try:
            p = candidate.expanduser()
        except Exception:
            p = candidate

    parts = {part.strip().lower() for part in p.parts}
    lowered = str(p).lower().replace("/", "\\")

    if "devvault restores" in parts:
        return True

    noisy_parts = {
        "$recycle.bin",
        "system volume information",
        "program files",
        "program files (x86)",
        "programdata",
        "windows",
        ".devvault",
        "_bak",
        "_artifacts",
        "crossdevice",
        "vscode-remote-wsl",
        "backups",
    }
    if parts & noisy_parts:
        return True

    noisy_fragments = (
        "\\trustware\\backups\\",
        "\\trustware\\company\\_artifacts\\",
        "\\trustware_archive\\",
        "\\new folder\\devvault_source_current.zip",
        "\\devvault_source_current.zip.zip",
    )
    if any(fragment in lowered for fragment in noisy_fragments):
        return True

    return False


def _live_protected_roots() -> list[Path]:
    """
    Source of truth for coverage: live snapshot evidence across all currently
    reachable known vaults.

    Safety rule:
    - unreachable vaults do NOT count as protection
    - only live snapshots in reachable vaults count

    Compatibility bridge:
    - Older snapshots may not yet have manifest.source_root.
    - For those, keep a remembered protected_root only if a live snapshot exists
      in a reachable vault with a matching source_name (filename / leaf name).
    """
    fs = OSFileSystem()

    roots: list[Path] = []
    legacy_names: set[str] = set()

    for backup_root in _known_vault_paths():
        try:
            if not backup_root.exists() or not backup_root.is_dir():
                continue
        except Exception:
            continue

        try:
            snaps = list_snapshots(fs=fs, backup_root=backup_root)
        except Exception:
            continue

        for snap in snaps:
            try:
                md = read_snapshot_metadata(fs=fs, snapshot_dir=snap.snapshot_dir)
            except Exception:
                continue

            if md.source_root:
                try:
                    roots.append(Path(md.source_root))
                except Exception:
                    pass
                continue

            if md.source_name:
                legacy_names.add(md.source_name.strip().lower())

    # Always include explicitly protected roots (user intent)
    for remembered in get_protected_roots():
        try:
            rp = Path(remembered).expanduser()
        except Exception:
            continue
        roots.append(rp)

    out: list[Path] = []
    seen: set[str] = set()
    for r in roots:
        try:
            key = str(r.resolve())
        except Exception:
            key = str(r)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _looks_like_data_root(root: Path) -> bool:
    try:
        return root.name.strip().lower() in DATA_ROOT_NAMES
    except Exception:
        return False


def _is_meaningful_file(p: Path) -> bool:
    if _is_generated_protection_artifact(p):
        return False

    try:
        if not p.is_file():
            return False
    except Exception:
        return False

    name = p.name.strip()
    if not name:
        return False

    lowered = name.lower()
    if lowered.startswith("."):
        return False

    if p.suffix.lower() in IGNORED_FILE_SUFFIXES:
        return False

    return True


def _count_meaningful_files(root: Path, max_count: int) -> int:
    count = 0
    try:
        for p in root.rglob("*"):
            try:
                if _is_meaningful_file(p):
                    count += 1
                    if count >= max_count:
                        return count
            except Exception:
                continue
    except Exception:
        return count
    return count



def _is_generated_protection_artifact(path: Path) -> bool:
    try:
        p = path.expanduser().resolve()
    except Exception:
        try:
            p = path.expanduser()
        except Exception:
            p = path

    try:
        name = p.name.strip().lower()
    except Exception:
        name = str(p).strip().lower()

    parts = {part.strip().lower() for part in p.parts}
    lowered = str(p).lower().replace("/", "\\")

    exact_names = {
        ".devvault",
        "_artifacts",
        "_bak",
    }
    if name in exact_names:
        return True

    if parts & exact_names:
        return True

    prefixes = (
        "devvault-clean-backup-",
        "devvault-ui-",
        "devvault_source_current",
    )
    if any(name.startswith(pfx) for pfx in prefixes):
        return True

    if name.endswith(" - backup"):
        return True

    if len(name) >= 15 and name[:8].isdigit() and name[8] == "-" and name[9:15].isdigit():
        if " - backup" in name:
            return True

    noisy_fragments = (
        "\\trustware\\company\\_artifacts\\",
        "\\trustware\\company\\_bak\\",
    )
    if any(fragment in lowered for fragment in noisy_fragments):
        return True

    return False


def _is_archive_candidate(p: Path) -> bool:
    try:
        if not p.is_file():
            return False
    except Exception:
        return False

    name = p.name.strip()
    if not name:
        return False

    lowered = name.lower()
    if lowered.startswith("."):
        return False

    suffixes = [s.lower() for s in p.suffixes]
    if not suffixes:
        return False

    if ".tar" in suffixes and any(s in suffixes for s in (".gz", ".bz2", ".xz")):
        pass
    elif suffixes[-1] not in ARCHIVE_EXTENSIONS:
        return False

    try:
        size = p.stat().st_size
    except Exception:
        return False

    return int(size) >= ARCHIVE_MIN_BYTES


def _find_archive_candidates(
    scan_roots: list[Path],
    ignored: set[str],
) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()

    for root in scan_roots:
        try:
            for p in root.rglob("*"):
                try:
                    if not _is_archive_candidate(p):
                        continue
                except Exception:
                    continue

                p_str = str(p)
                if p_str in ignored:
                    continue

                try:
                    resolved = str(p.resolve())
                except Exception:
                    resolved = p_str

                if resolved in seen:
                    continue

                seen.add(resolved)
                found.append(p)
        except Exception:
            continue

    return found


def _find_data_folder_candidates(
    scan_roots: list[Path],
    protected_roots: list[Path],
    ignored: set[str],
) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()

    for root in scan_roots:
        if not _looks_like_data_root(root):
            continue

        try:
            children = sorted(root.iterdir(), key=lambda p: p.name.lower())
        except Exception:
            continue

        for child in children:
            try:
                if not child.is_dir():
                    continue
            except Exception:
                continue

            child_str = str(child)
            if child_str in ignored:
                continue
            if _is_generated_protection_artifact(child):
                continue
            if _is_covered(child, protected_roots):
                continue

            file_count = _count_meaningful_files(child, DATA_FOLDER_MIN_FILES)
            if file_count < DATA_FOLDER_MIN_FILES:
                continue

            try:
                resolved = str(child.resolve())
            except Exception:
                resolved = child_str

            if resolved in seen:
                continue

            seen.add(resolved)
            found.append(child)

    return found


def _normalize_snapshot_manifest_files(snapshot_dir: Path, *, fs: OSFileSystem) -> dict[str, tuple[int, str | None]]:
    manifest_path = snapshot_dir / "manifest.json"
    if not fs.exists(manifest_path) or not fs.is_file(manifest_path):
        raise ValueError(f"Snapshot is missing manifest.json: {snapshot_dir}")

    manifest = json.loads(fs.read_text(manifest_path))
    if not isinstance(manifest, dict):
        raise ValueError(f"Snapshot manifest must be an object: {snapshot_dir}")

    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError(f"Snapshot manifest missing files list: {snapshot_dir}")

    out: dict[str, tuple[int, str | None]] = {}
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("Invalid snapshot manifest entry.")
        rel = item.get("path")
        size = item.get("size")
        digest = item.get("sha256")

        if not isinstance(rel, str) or not rel.strip():
            raise ValueError("Invalid snapshot manifest path.")
        if not isinstance(size, int) or size < 0:
            raise ValueError("Invalid snapshot manifest size.")
        if digest is not None and not isinstance(digest, str):
            raise ValueError("Invalid snapshot manifest digest.")

        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise ValueError("Unsafe snapshot manifest path.")

        out[rel_path.as_posix()] = (size, digest)

    return out



DRIFT_REFLAG_RATIO = 0.10  # 10% or more newly-uncovered bytes => drift


def _normalize_live_files_for_drift(root: Path) -> dict[str, tuple[int, None]]:
    out: dict[str, tuple[int, None]] = {}

    try:
        for p in root.rglob("*"):
            try:
                if not _is_meaningful_file(p):
                    continue

                if _is_generated_protection_artifact(p):
                    continue

                rel = p.relative_to(root).as_posix()

                # Ignore small operational churn for drift purposes.
                try:
                    size = int(p.stat().st_size)
                except Exception:
                    size = 0

                if p.suffix.lower() in {".md", ".txt", ".log", ".json"} and size <= 256 * 1024:
                    continue

                rel_parts = {part.strip().lower() for part in Path(rel).parts}
                if rel_parts & {"_artifacts", "_bak", ".devvault", "governance", "launch", "infrastructure", "company", "infra"}:
                    continue

                out[rel] = (size, None)
            except Exception:
                continue
    except Exception:
        return {}

    return out


def _normalize_live_files(root: Path) -> dict[str, tuple[int, None]]:
    out: dict[str, tuple[int, None]] = {}

    try:
        for p in root.rglob("*"):
            try:
                if not _is_meaningful_file(p):
                    continue
                rel = p.relative_to(root).as_posix()
                size = int(p.stat().st_size)
                out[rel] = (size, None)
            except Exception:
                continue
    except Exception:
        return {}

    return out


def _has_drift(*, root: Path, snapshot_dir: Path, fs: OSFileSystem) -> bool:
    if not root.exists() or not root.is_dir():
        return False

    if _is_generated_protection_artifact(root):
        return False

    try:
        raw_snap_files = _normalize_snapshot_manifest_files(snapshot_dir, fs=fs)
    except Exception:
        return False

    snap_files: dict[str, tuple[int, str | None]] = {}
    for rel, (size, digest) in raw_snap_files.items():
        rel_parts = {part.strip().lower() for part in Path(rel).parts}
        if rel_parts & {"_artifacts", "_bak", ".devvault", "governance", "launch", "infrastructure", "company", "infra"}:
            continue
        if Path(rel).suffix.lower() in {".md", ".txt", ".log", ".json"} and int(size) <= 256 * 1024:
            continue
        snap_files[rel] = (int(size), digest)

    live_files = _normalize_live_files_for_drift(root)
    if not live_files and not snap_files:
        return False

    total_live_bytes = 0
    uncovered_bytes = 0

    for rel, (live_size, _live_digest) in live_files.items():
        live_size_i = int(live_size)
        total_live_bytes += live_size_i

        snap_entry = snap_files.get(rel)
        if snap_entry is None:
            uncovered_bytes += live_size_i
            continue

        snap_size, _snap_digest = snap_entry
        if live_size_i != int(snap_size):
            uncovered_bytes += abs(live_size_i - int(snap_size))

    if total_live_bytes <= 0:
        return False

    uncovered_ratio = uncovered_bytes / total_live_bytes
    return uncovered_ratio >= DRIFT_REFLAG_RATIO


def _latest_snapshot_for_root(*, target_root: Path, fs: OSFileSystem) -> Path | None:
    target_key = str(target_root)
    try:
        target_key = str(target_root.resolve())
    except Exception:
        pass

    best_snapshot: Path | None = None
    best_id = ""

    for backup_root in _known_vault_paths():
        try:
            if not backup_root.exists() or not backup_root.is_dir():
                continue
        except Exception:
            continue

        try:
            snaps = list_snapshots(fs=fs, backup_root=backup_root)
        except Exception:
            continue

        for snap in snaps:
            try:
                md = read_snapshot_metadata(fs=fs, snapshot_dir=snap.snapshot_dir)
            except Exception:
                continue

            if not md.source_root:
                continue

            try:
                source_key = str(Path(md.source_root).expanduser().resolve())
            except Exception:
                source_key = str(Path(md.source_root).expanduser())

            if source_key != target_key:
                continue

            sid = snap.snapshot_id
            if sid > best_id:
                best_id = sid
                best_snapshot = snap.snapshot_dir

    return best_snapshot


def _find_drifted_protected_roots(
    protected_roots: list[Path],
    ignored: set[str],
) -> list[Path]:
    fs = OSFileSystem()
    out: list[Path] = []
    seen: set[str] = set()

    for root in protected_roots:
        try:
            root_path = root.expanduser().resolve()
        except Exception:
            root_path = root

        root_str = str(root_path)
        if root_str in ignored:
            continue
        if root_str in seen:
            continue

        snapshot_dir = _latest_snapshot_for_root(target_root=root_path, fs=fs)
        if snapshot_dir is None:
            continue

        try:
            if not _has_drift(root=root_path, snapshot_dir=snapshot_dir, fs=fs):
                continue
        except Exception:
            continue

        seen.add(root_str)
        out.append(root_path)

    return out


def compute_uncovered_candidates(
    *,
    scan_roots: list[Path],
    depth: int = 4,
    top: int = 30,
) -> CoverageResult:
    """
    Coverage Assurance v2 + drift detection:

    - Run project discovery scan using existing engine heuristics.
    - Compare discovered project directories against protected_roots.
    - Add data-folder candidates under Pictures / Videos / Downloads
      when a subfolder contains at least 35 meaningful files.
    - Add archive candidates.
    - Add protected roots whose live contents drifted since the latest snapshot.
    - Return actionable backup candidates not explicitly ignored.

    Notes:
    - Project detection remains bounded by depth + top.
    - Data-folder detection only inspects subfolders of the known data roots.
    - Drift detection compares current live files vs latest snapshot manifest.
    - Deterministic: does not mutate state.
    """
    protected = _live_protected_roots()
    ignored = {str(Path(p)) for p in get_ignored_candidates()}

    req = ScanRequest(
        roots=scan_roots,
        depth=int(depth),
        top=int(top),
        include="",
    )
    res = scan_engine(req)

    uncovered: list[Path] = []
    seen: set[str] = set()

    for proj in res.projects:
        p = Path(proj.path)
        if str(p) in ignored:
            continue
        if _is_devvault_runtime_path(p):
            continue
        if _is_covered(p, protected):
            continue

        if _is_generated_protection_artifact(p):
            continue

        try:
            resolved = str(p.resolve())
        except Exception:
            resolved = str(p)

        if resolved in seen:
            continue

        seen.add(resolved)
        uncovered.append(p)

    for data_dir in _find_data_folder_candidates(
        scan_roots=scan_roots,
        protected_roots=protected,
        ignored=ignored,
    ):
        if _is_devvault_runtime_path(data_dir):
            continue

        try:
            resolved = str(data_dir.resolve())
        except Exception:
            resolved = str(data_dir)

        if resolved in seen:
            continue

        seen.add(resolved)
        uncovered.append(data_dir)

    for archive_path in _find_archive_candidates(
        scan_roots=scan_roots,
        ignored=ignored,
    ):
        if _is_devvault_runtime_path(archive_path):
            continue
        if _is_covered(archive_path, protected):
            continue

        try:
            resolved = str(archive_path.resolve())
        except Exception:
            resolved = str(archive_path)

        if resolved in seen:
            continue

        seen.add(resolved)
        uncovered.append(archive_path)

    for drifted_root in _find_drifted_protected_roots(
        protected_roots=protected,
        ignored=ignored,
    ):
        if _is_devvault_runtime_path(drifted_root):
            continue

        try:
            resolved = str(drifted_root.resolve())
        except Exception:
            resolved = str(drifted_root)

        if resolved in seen:
            continue

        seen.add(resolved)
        uncovered.append(drifted_root)

    return CoverageResult(
        uncovered=uncovered,
        scanned_directories=int(res.scanned_directories),
        skipped_directories=int(res.skipped_directories),
    )
