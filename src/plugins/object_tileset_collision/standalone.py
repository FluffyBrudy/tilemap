"""
Standalone launcher for the Object Tileset Collision Editor.

Usage:
    python standalone.py path/to/object_tileset.png
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent.parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

if sys.platform == "darwin":
    os.environ.setdefault("SDL_VIDEO_MAC_SCREEN_SCALE", "1")

import pygame

from .editor import ObjectTilesetCollisionEditor
from utils import error_handler, error_context


def main(argv: list[str] | None = None) -> None:
    try:
        parser = argparse.ArgumentParser(
            description="Object Tileset Collision Editor",
        )
        parser.add_argument("image", type=Path, help="Path to object tileset image")
        parser.add_argument("--window-size", type=str, default="1200x800", help="Window size WxH")
        parser.add_argument("--data-root", type=Path, required=True, help="Data root path")
        parser.add_argument("--load", type=Path, default=None, help="Load existing collision file")

        args = parser.parse_args(argv)

        if not args.image.exists():
            print(f"Error: File not found: {args.image}")
            sys.exit(1)

        window_size = tuple(int(x) for x in args.window_size.split("x"))

        pygame.init()
        screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
        pygame.display.set_caption(f"Object Tileset Collision — {args.image.name}")

        editor = ObjectTilesetCollisionEditor.from_path(
            args.image,
            window_size=window_size,
            data_root=args.data_root,
        )

        if args.load and args.load.exists():
            editor.load_from_file(args.load)
            print(f"Loaded collision data from {args.load}")

        print(f"\nObject Tileset Collision Editor — {args.image.name}")
        print(f"Data root: {args.data_root}")
        print("\nControls:")
        print("  Define Regions Mode:")
        print("    - Drag on tileset: Create region")
        print("    - Click region: Select")
        print("    - F2: Rename region")
        print("    - Delete: Remove region")
        print("  Paint Collision Mode:")
        print("    - Left-click: Add vertex")
        print("    - Right-click/Enter: Complete polygon")
        print("    - Delete: Remove polygon")
        print("  View:")
        print("    - +/- keys: Zoom in/out")
        print("    - Pan button or Space: Toggle pan mode")
        print("    - Middle mouse drag: Pan (always)")
        print("  General:")
        print("    - Ctrl+S: Save  |  Ctrl+L: Load")
        print("    - ?: Toggle help")
        print("    - Escape: Close help / Quit (when help closed)")
        print()

        editor.run()

    except KeyboardInterrupt:
        print("\nInterrupted")
    except Exception as e:
        error_handler.capture(e, context="object_tileset_collision")
        print(f"Error: {e}")


if __name__ == "__main__":
    main()