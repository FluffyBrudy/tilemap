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

# Add src directory to path for imports (needed for FileManager, etc.)
# This allows the animation editor to import widgets.filemanager
_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent.parent.parent  # Go up to src/
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import pygame

from .editor import SpriteAnimationEditor


def parse_tile_size(s: str) -> tuple[int, int]:
    """Parse '32x32' or '16x16' into (w, h)."""
    parts = s.lower().split("x")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    v = int(parts[0])
    return v, v


def main(argv: list[str] | None = None) -> None:
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

    args = parser.parse_args(argv)

    if not args.image.exists():
        print(f"Error: File not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    tile_size = parse_tile_size(args.tile_size)
    window_size = parse_tile_size(args.window_size)

    pygame.init()
    editor = SpriteAnimationEditor.from_path(
        args.image, tile_size=tile_size, window_size=window_size,
    )

    if args.load and args.load.exists():
        from .models import AnimationLibrary
        lib = AnimationLibrary.load(args.load)
        editor.load_animation_data(lib.to_dict())
        print(f"Loaded animations from {args.load}")

    editor.run()


if __name__ == "__main__":
    main()
