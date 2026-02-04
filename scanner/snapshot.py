from pathlib import Path
from datetime import datetime


def create_snapshot_root(destination: Path) -> Path:
    """
    Create an *incomplete* DevVault snapshot directory first.

    We write into:
        DevVault/snapshots/.incomplete-YYYY-MM-DD_HH-MM-SS/

    Later (after backup succeeds) we will rename it to:
        DevVault/snapshots/YYYY-MM-DD_HH-MM-SS/
    """

    destination = destination.expanduser().resolve()

    devvault_root = destination / "DevVault"
    snapshots_dir = devvault_root / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # IMPORTANT: mark as incomplete until we "commit" it.
    snapshot_path = snapshots_dir / f".incomplete-{timestamp}"
    snapshot_path.mkdir()

    return snapshot_path

def commit_snapshot(snapshot_path: Path) -> Path:
    """
    Turn an incomplete snapshot into a finalized snapshot by renaming it.

    Input:
        .../snapshots/.incomplete-YYYY-MM-DD_HH-MM-SS

    Output:
        .../snapshots/YYYY-MM-DD_HH-MM-SS
    """

    name = snapshot_path.name
    prefix = ".incomplete-"

    if not name.startswith(prefix):
        raise ValueError(f"Not an incomplete snapshot: {snapshot_path}")

    final_name = name.removeprefix(prefix)
    final_path = snapshot_path.parent / final_name

    snapshot_path.rename(final_path)
    return final_path
