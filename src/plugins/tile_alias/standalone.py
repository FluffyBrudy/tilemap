"""
Standalone launcher for the Alias Composer.

Usage:
    python standalone.py path/to/tileset.png [--tile-size 32x32]
    python standalone.py path/to/tileset.png --tile-size 16x16 --load stone.alias.json
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

try:
    from .editor import AliasComposerEditor
except ImportError:
    from plugins.tile_alias.editor import AliasComposerEditor
from utils import error_context, error_handler
from utils.standalone import load_standalone_theme


def parse_tile_size(s: str) -> tuple[int, int]:
    """Parse '32x32' or '16x16' into (w, h)."""
    parts = s.lower().split("x")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    v = int(parts[0])
    return v, v


def main(argv: list[str] | None = None) -> None:

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        error_handler.capture(exc_value, context="alias_composer_exception")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    try:
        parser = argparse.ArgumentParser(
            description="Alias Composer — author tile-pattern brushes",
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
            help="Load an existing *.alias.json file on startup",
        )
        parser.add_argument(
            "--window-size",
            type=str,
            default="1200x800",
            help="Window size as WxH (default: 1200x800)",
        )
        parser.add_argument(
            "--data-root",
            type=Path,
            required=True,
            help="Path to project data root directory (REQUIRED)",
        )
        parser.add_argument(
            "--tileset-ref",
            type=str,
            default="",
            help="Project-relative tileset identity recorded in the alias file",
        )

        args = parser.parse_args(argv)

        if not args.image.exists():
            error_handler.capture(
                Exception(f"File not found: {args.image}"),
                context="alias_composer_args",
            )
            print(f"Error: File not found: {args.image}", file=sys.stderr)
            sys.exit(1)

        with error_context("alias_composer_main"):
            tile_size = parse_tile_size(args.tile_size)
            window_size = parse_tile_size(args.window_size)

            pygame.init()
            pygame.display.set_mode(window_size, pygame.RESIZABLE)
            pygame.display.set_caption(f"Alias Composer — {args.image.name}")

            load_standalone_theme()

            editor = AliasComposerEditor.from_path(
                args.image,
                tile_size=tile_size,
                window_size=window_size,
                data_root=args.data_root,
                tileset_ref=args.tileset_ref,
            )

            if args.load and args.load.exists():
                editor.load_from_file(args.load)
                print(f"Loaded aliases from {args.load}")

            print("\nControls:")
            print("  Canvas: LMB-drag paint, RMB-drag erase, wheel zoom,")
            print("          middle-drag or Space+drag pan, Ctrl+Z / Ctrl+Y undo/redo")
            print("  Tileset sheet: drag to select a multi-tile brush,")
            print("          wheel scrolls, Ctrl+wheel zooms, middle/space-drag pans,")
            print("          drag the bar above it to resize")
            print("  Alias list: click to edit, N new, F2 rename, Delete remove")
            print("  [ ] canvas width, ; ' canvas height")
            print("  Ctrl+S save, Ctrl+L reload, Esc quit")
            print()

            editor.run()

    except KeyboardInterrupt:
        print("\nAlias composer interrupted by user")
    except Exception as e:
        error_handler.capture(e, context="alias_composer_main")
        print(f"Failed to start alias composer: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
