# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path(globals().get("SPECPATH", ".")).resolve()
ASSET_ROOT = PROJECT_ROOT / "devvault_desktop" / "assets"
asset_datas = [
    (
        str(path),
        str(Path("devvault_desktop") / "assets" / path.relative_to(ASSET_ROOT).parent),
    )
    for path in sorted(ASSET_ROOT.rglob("*"))
    if path.is_file()
]

a = Analysis(
    ['devvault_desktop\\qt_app.py'],
    pathex=[],
    binaries=[],
    datas=asset_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DevVault',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DevVault',
)
