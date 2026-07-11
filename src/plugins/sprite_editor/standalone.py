"""
Standalone launcher for the Sprite Editor.

Usage:
    python standalone.py
    python standalone.py path/to/spritesheet.png
    python standalone.py path/to/spritesheet.png --tile-size 32
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
from pygame import Rect

try:
    from .editor import SpriteEditor, TOOLBAR_H, STATUS_H
except ImportError:
    from plugins.sprite_editor.editor import SpriteEditor, TOOLBAR_H, STATUS_H
from utils import error_handler, error_context


def parse_window_size(s: str) -> tuple[int, int]:
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
        error_handler.capture(exc_value, context="sprite_editor_exception")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    parser = argparse.ArgumentParser(description="Grid Sprite Editor")
    parser.add_argument(
        "image",
        type=str,
        nargs="?",
        default=None,
        help="Path to spritesheet image (optional — start blank)",
    )
    parser.add_argument(
        "--tile-size", type=str, default="32", help="Tile size (e.g. 32 or 32x32)"
    )
    parser.add_argument(
        "--save", type=str, default=None, help="Output path for modified spritesheet"
    )
    parser.add_argument(
        "--window-size",
        type=str,
        default="1000x700",
        help="Window size WxH (default 1000x700)",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Project data root (for file dialogs)",
    )

    args = parser.parse_args(argv)

    ts_parts = args.tile_size.lower().split("x")
    tw = int(ts_parts[0])
    th = int(ts_parts[1]) if len(ts_parts) > 1 else tw

    window_size = parse_window_size(args.window_size)

    pygame.init()
    screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)

    if args.image:
        image_path = Path(args.image)
        if not image_path.is_file():
            print(f"Error: file not found: {image_path}")
            sys.exit(1)
        data_root = Path(args.data_root) if args.data_root else image_path.parent
        surface = pygame.image.load(str(image_path)).convert_alpha()
        pygame.display.set_caption(f"Sprite Editor - {image_path.name}")
        editor = SpriteEditor(
            screen.get_rect(),
            surface,
            (tw, th),
            image_path=image_path,
            data_root=data_root,
        )
        if args.save:
            editor.set_save_path(Path(args.save))
    else:
        data_root = Path(args.data_root) if args.data_root else Path.cwd()
        pygame.display.set_caption("Sprite Editor — blank")
        editor = SpriteEditor(
            screen.get_rect(),
            tile_size=(tw, th),
            data_root=data_root,
        )

    clock = pygame.time.Clock()
    running = True

    with error_context("sprite_editor"):
        while running:
            clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    screen = pygame.display.set_mode(
                        (event.w, event.h), pygame.RESIZABLE
                    )
                    editor.rect = screen.get_rect()
                    editor.grid.rect = Rect(
                        editor.rect.x,
                        editor.rect.y + TOOLBAR_H,
                        editor.rect.w,
                        editor.rect.h - TOOLBAR_H - STATUS_H,
                    )
                else:
                    editor.handle_event(event)

            screen.fill((0, 0, 0))
            editor.draw(screen)
            pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
