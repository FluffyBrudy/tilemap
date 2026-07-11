"""
Standalone launcher for the Sprite Animation Editor.

Usage:
    python standalone.py path/to/spritesheet.png [--tile-size 32x32]
    python standalone.py path/to/spritesheet.png --tile-size 16x16
    python standalone.py path/to/spritesheet.png --load animations.anim.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent.parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import pygame

try:
    from .editor import SpriteAnimationEditor
except ImportError:
    from plugins.sprite_animation.editor import SpriteAnimationEditor
from utils import error_handler, error_context


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
        error_handler.capture(exc_value, context="animation_editor_exception")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    try:
        parser = argparse.ArgumentParser(
            description="Sprite Animation Editor — create frame-based animations from spritesheets",
        )
        parser.add_argument(
            "image",
            type=Path,
            help="Path to a spritesheet image (PNG, JPG, etc.)",
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
            help="Load an existing .anim.json file on startup",
        )
        parser.add_argument(
            "--window-size",
            type=str,
            default="1100x720",
            help="Window size as WxH (default: 1100x720)",
        )
        parser.add_argument(
            "--data-root",
            type=Path,
            default=None,
            help="Path to project data root directory",
        )

        args = parser.parse_args(argv)

        data_root = args.data_root if args.data_root else Path.cwd() / "data"

        if not args.image.exists():
            error_handler.capture(
                Exception(f"File not found: {args.image}"),
                context="animation_editor_args",
            )
            print(f"Error: File not found: {args.image}", file=sys.stderr)
            sys.exit(1)

        with error_context("animation_editor_main"):
            tile_size = parse_tile_size(args.tile_size)
            window_size = parse_tile_size(args.window_size)

            pygame.init()
            editor = SpriteAnimationEditor.from_path(
                args.image,
                tile_size=tile_size,
                window_size=window_size,
                data_root=data_root,
            )

            if args.load and args.load.exists():
                try:
                    from .models import AnimationLibrary
                except ImportError:
                    from plugins.sprite_animation.models import AnimationLibrary

                lib = AnimationLibrary.load(args.load)
                editor.load_animation_data(lib.to_dict())
                editor._resolve_library_paths(args.load)
                print(f"Loaded animations from {args.load}")

            editor.run()
    except KeyboardInterrupt:
        print("\nAnimation editor interrupted by user")
    except Exception as e:
        error_handler.capture(e, context="animation_editor_main")
        print(f"Failed to start animation editor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
