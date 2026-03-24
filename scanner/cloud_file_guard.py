from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x00040000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x00400000


@dataclass(frozen=True)
class CloudPlaceholderHit:
    path: str
    attributes: int


@dataclass(frozen=True)
class CloudPlaceholderScanResult:
    ok: bool
    hits: tuple[CloudPlaceholderHit, ...]
    operator_message: str = ""


def _file_attrs(path: Path) -> int:
    try:
        st = path.stat(follow_symlinks=False)
    except OSError:
        return 0
    return int(getattr(st, "st_file_attributes", 0) or 0)


def _is_cloud_placeholder_attrs(attrs: int) -> bool:
    return bool(
        attrs & FILE_ATTRIBUTE_OFFLINE
        or attrs & FILE_ATTRIBUTE_RECALL_ON_OPEN
        or attrs & FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
    )


def scan_tree_for_cloud_placeholders(
    root: Path,
    *,
    max_hits: int = 25,
) -> CloudPlaceholderScanResult:
    root = Path(root)

    if os.name != "nt":
        return CloudPlaceholderScanResult(ok=True, hits=(), operator_message="")

    hits: list[CloudPlaceholderHit] = []

    def record(path: Path, attrs: int) -> None:
        if len(hits) >= max_hits:
            return
        hits.append(CloudPlaceholderHit(path=str(path), attributes=attrs))

    try:
        if root.exists():
            root_attrs = _file_attrs(root)
            if root.is_file() and _is_cloud_placeholder_attrs(root_attrs):
                record(root, root_attrs)
    except OSError:
        pass

    if root.is_dir():
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            current = Path(dirpath)

            for name in dirnames:
                p = current / name
                attrs = _file_attrs(p)
                if _is_cloud_placeholder_attrs(attrs):
                    record(p, attrs)
                    if len(hits) >= max_hits:
                        break

            if len(hits) >= max_hits:
                break

            for name in filenames:
                p = current / name
                attrs = _file_attrs(p)
                if _is_cloud_placeholder_attrs(attrs):
                    record(p, attrs)
                    if len(hits) >= max_hits:
                        break

            if len(hits) >= max_hits:
                break

    if not hits:
        return CloudPlaceholderScanResult(ok=True, hits=(), operator_message="")

    preview = "\\n".join(f"  - {hit.path}" for hit in hits[:5])
    more = ""
    if len(hits) > 5:
        more = f"\\n  ... and {len(hits) - 5} more item(s)"

    operator_message = (
        "This backup source contains cloud placeholder files that are not fully local on this device. "
        "Mark the source as 'Always keep on this device' in OneDrive or move it to a fully local folder, then try again.\\n"
        f"{preview}{more}"
    )

    return CloudPlaceholderScanResult(
        ok=False,
        hits=tuple(hits),
        operator_message=operator_message,
    )
