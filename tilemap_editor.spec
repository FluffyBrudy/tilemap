# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Tilemap Editor
This file can be customized as needed during development.

To build: pyinstaller tilemap_editor.spec
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ============================================================================
# CONFIGURATION - Edit these as needed
# ============================================================================

# Application metadata
APP_NAME = 'TilemapEditor'
MAIN_SCRIPT = 'src/editor.py'
ICON_FILE = None  # Set to 'path/to/icon.ico' or 'path/to/icon.png' if you have one

# Console mode (True = show terminal, False = windowed app)
CONSOLE_MODE = True  # Set to True for debugging

# Build options
ONE_FILE = True  # True = single exe (standalone), False = folder with dependencies (faster startup)
UPX_ENABLED = True  # Compression (can cause issues, disable if needed)

# Directories to include as data
DATA_DIRS = [
    ('data', 'data'),  # (source, destination in bundle)
    ('src/configs', 'configs'),  # Include any config files
]

# Additional files to include (fonts, images, etc.)
# Add your asset files here as they're created
ADDITIONAL_FILES = [
    # ('path/to/font.ttf', 'fonts'),  # Example
    # ('path/to/image.png', 'assets'),  # Example
]

# Hidden imports (modules that PyInstaller might miss)
HIDDEN_IMPORTS = [
    'pygame',
    'pygame.freetype',
    # Add any other modules that are imported dynamically
]

# Exclude unnecessary modules to reduce size
EXCLUDES = [
    'tkinter',
    'matplotlib',
    'numpy',
    'pandas',
    'scipy',
    'PIL',  # Remove if you're using Pillow
]

# ============================================================================
# ANALYSIS - PyInstaller configuration
# ============================================================================

block_cipher = None

# Collect data files
datas = []
for src, dst in DATA_DIRS:
    src_path = Path(src)
    if src_path.exists():
        datas.append((str(src_path), dst))
    else:
        print(f"Warning: Data directory '{src}' not found, skipping...")

# Add additional files
for src, dst in ADDITIONAL_FILES:
    src_path = Path(src)
    if src_path.exists():
        datas.append((str(src_path), dst))
    else:
        print(f"Warning: File '{src}' not found, skipping...")

# Automatically collect pygame data files
try:
    pygame_datas = collect_data_files('pygame')
    datas.extend(pygame_datas)
except Exception as e:
    print(f"Warning: Could not collect pygame data files: {e}")

# Analysis - tell PyInstaller what to include
a = Analysis(
    [MAIN_SCRIPT],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove duplicate files
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ============================================================================
# EXECUTABLE CONFIGURATION
# ============================================================================

if ONE_FILE:
    # Single file executable
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=UPX_ENABLED,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=CONSOLE_MODE,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON_FILE,
    )
else:
    # Directory with dependencies (recommended for development)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=UPX_ENABLED,
        console=CONSOLE_MODE,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=ICON_FILE,
    )
    
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=UPX_ENABLED,
        upx_exclude=[],
        name=APP_NAME,
    )

# ============================================================================
# PLATFORM-SPECIFIC NOTES
# ============================================================================
# 
# Linux:
#   - The output will be in dist/TilemapEditor/
#   - Run with: ./dist/TilemapEditor/TilemapEditor
#
# Windows:
#   - Output: dist/TilemapEditor/TilemapEditor.exe
#   - Set ICON_FILE to .ico file for Windows executable icon
#
# macOS:
#   - Can create .app bundle by uncommenting the BUNDLE section below
#   - Set ICON_FILE to .icns file for macOS app icon
#
# ============================================================================

# Uncomment for macOS .app bundle
# app = BUNDLE(
#     coll,
#     name=f'{APP_NAME}.app',
#     icon=ICON_FILE,
#     bundle_identifier='com.tilemap.editor',
#     info_plist={
#         'NSPrincipalClass': 'NSApplication',
#         'NSHighResolutionCapable': 'True',
#     },
# )
