"""
Standalone launcher for the Tileset Collision Editor.

Usage:
    python standalone.py path/to/tileset.png [--tile-size 32x32]
    python standalone.py path/to/tileset.png --tile-size 16x16
    python standalone.py path/to/tileset.png --load collision.json
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add src directory to path for imports
_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent.parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

# Fix HiDPI/Retina blur on macOS
if sys.platform == "darwin":
    os.environ.setdefault("SDL_VIDEO_MAC_SCREEN_SCALE", "1")

import pygame
import thorpy as tp

from .editor import TilesetCollisionEditor
from utils import error_handler, error_context


def parse_tile_size(s: str) -> tuple[int, int]:
    """Parse '32x32' or '16x16' into (w, h)."""
    parts = s.lower().split("x")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    v = int(parts[0])
    return v, v


def main(argv: list[str] | None = None) -> None:
    # Global exception handler for standalone collision editor
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        error_handler.capture(exc_value, context="collision_editor_exception")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    try:
        parser = argparse.ArgumentParser(
            description="Tileset Collision Editor — create collision shapes for tileset tiles",
        )
        parser.add_argument(
            "image",
            type=Path,
            help="Path to a tileset image (PNG, JPG, etc.)",
        )
        parser.add_argument(
            "--tile-size",
            type=str,
            default="32x32",
            help="Tile size as WxH, e.g. 32x32 or 16x16 (default: 32x32)",
        )
        parser.add_argument(
            "--load",
            type=Path,
            default=None,
            help="Load an existing collision .json file on startup",
        )
        parser.add_argument(
            "--window-size",
            type=str,
            default="1200x800",
            help="Window size as WxH (default: 1200x800)",
        )

        args = parser.parse_args(argv)

        if not args.image.exists():
            error_handler.capture(
                Exception(f"File not found: {args.image}"),
                context="collision_editor_args",
            )
            print(f"Error: File not found: {args.image}", file=sys.stderr)
            sys.exit(1)

        with error_context("collision_editor_main"):
            tile_size = parse_tile_size(args.tile_size)
            window_size = parse_tile_size(args.window_size)

            pygame.init()
            screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
            pygame.display.set_caption(f"Tileset Collision Editor — {args.image.name}")

            tp.set_default_font("arial", 16)
            tp.init(screen, tp.theme_game2)

            editor = TilesetCollisionEditor.from_path(
                args.image,
                tile_size=tile_size,
                window_size=window_size,
            )

            if args.load and args.load.exists():
                editor.load_from_file(args.load)
                print(f"Loaded collision data from {args.load}")

            print("\nControls:")
            print("  Bottom Panel (Tileset Selector):")
            print("    - Left-click: Select tile (Ctrl+click for multi-select)")
            print("    - Middle mouse OR Space+Left mouse: Pan")
            print("    - Mouse wheel: Zoom")
            print("    - H: Recenter view")
            print("  Middle Panel (Collision Painter):")
            print("    - Left-click: Add vertex")
            print("    - Right-click/Enter: Complete polygon")
            print("    - Escape: Cancel current polygon")
            print("    - Delete/Backspace: Remove selected polygon")
            print("    - Shift+Delete: Clear collision for selected tiles")
            print("    - O: Toggle one-way collision (selected polygon)")
            print("    - G: Toggle grid")
            print("    - S: Toggle snap to grid")
            print("    - R: Reset view")
            print("  Side Panel (Painted Tiles):")
            print("    - Click to select painted tile")
            print("    - Shows only tiles with collision")
            print("  General:")
            print("    - Ctrl+S: Save collision data")
            print("    - Ctrl+L: Load collision data")
            print("    - Drag handle between panels to resize")
            print()

            editor.run()

    except KeyboardInterrupt:
        print("\nCollision editor interrupted by user")
    except Exception as e:
        error_handler.capture(e, context="collision_editor_main")
        print(f"Failed to start collision editor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
