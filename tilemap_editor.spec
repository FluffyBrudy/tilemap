# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

APP_NAME = "TilemapEditor"
MAIN_SCRIPT = "src/run.py"
CONSOLE_MODE = False

datas = []
data_src = Path("data")
if data_src.exists():
    datas.append((str(data_src), "data"))

try:
    pygame_datas = collect_data_files("pygame")
    datas.extend(pygame_datas)
except Exception:
    pass

a = Analysis(
    [MAIN_SCRIPT],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=["pygame", "pygame.freetype"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy", "PIL"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=CONSOLE_MODE,
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

app = BUNDLE(
    coll,
    name=f"{APP_NAME}.app",
    icon=None,
    bundle_identifier="com.tilemap.editor",
    info_plist={
        "NSPrincipalClass": "NSApplication",
        "NSHighResolutionCapable": "True",
    },
)
