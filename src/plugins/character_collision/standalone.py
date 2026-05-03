"""
Standalone launcher for the Character Collision Editor.

Usage:
    python standalone.py path/to/character.png
    python standalone.py path/to/character.png --name "Player"
    python standalone.py path/to/character.png --load collision.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add src directory to path for imports
_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent.parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import pygame

from .editor import CharacterCollisionEditor
from utils import error_handler, error_context


def parse_window_size(s: str) -> tuple[int, int]:
    """Parse '1000x800' into (w, h)."""
    parts = s.lower().split("x")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    v = int(parts[0])
    return v, v


def main(argv: list[str] | None = None) -> None:
    # Global exception handler for standalone character collision editor
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        error_handler.capture(exc_value, context="character_collision_editor_exception")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    try:
        parser = argparse.ArgumentParser(
            description="Character Collision Editor — define collision shapes for character sprites",
        )
        parser.add_argument(
            "image",
            type=Path,
            help="Path to a character sprite image (PNG, JPG, etc.)",
        )
        parser.add_argument(
            "--name",
            type=str,
            default="Character",
            help="Character name (default: Character)",
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
            default="1000x800",
            help="Window size as WxH (default: 1000x800)",
        )
        parser.add_argument(
            "--data-root",
            type=Path,
            required=True,
            help="Path to project data root directory (REQUIRED)",
        )

        args = parser.parse_args(argv)

        data_root = args.data_root

        if not args.image.exists():
            error_handler.capture(
                Exception(f"File not found: {args.image}"),
                context="character_collision_editor_args",
            )
            print(f"Error: File not found: {args.image}", file=sys.stderr)
            sys.exit(1)

        with error_context("character_collision_editor_main"):
            window_size = parse_window_size(args.window_size)

            pygame.init()
            pygame.display.set_caption(f"Character Collision Editor — {args.name}")
            screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)

            editor = CharacterCollisionEditor.from_path(
                args.image,
                window_size=window_size,
                character_name=args.name,
                data_root=data_root,
            )

            if args.load and args.load.exists():
                editor.load_from_file(args.load)
                print(f"Loaded collision data from {args.load}")

            print("\nControls:")
            print("  Shape Types: Click buttons to switch between Rectangle, Circle, Capsule")
            print("  Left-click: Drag handles to adjust shape")
            print("  G: Toggle grid")
            print("  R: Reset view")
            print("  Ctrl+S: Save collision data")
            print("  Ctrl+L: Load collision data")
            print("  Mouse wheel: Zoom")
            print("  Middle mouse: Pan")
            print()

            editor.run()

    except KeyboardInterrupt:
        print("\nCharacter collision editor interrupted by user")
    except Exception as e:
        error_handler.capture(e, context="character_collision_editor_main")
        print(f"Failed to start character collision editor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
