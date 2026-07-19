"""
Standalone FileManager launcher.

Runs FileManager as a separate process, communicating with parent via JSON.

Usage:
    python standalone_filemanager.py --mode open --allowed-exts .png,.jpg --initial-dir /path/to/dir
    python standalone_filemanager.py --mode save --default-name myfile.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from pygame import Rect

_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from utils.standalone import load_standalone_theme
from widgets.filemanager import FileManager
from widgets.ui.theme import COLORS


class StandaloneFileManager:
    """Wrapper for FileManager that runs as a standalone process."""

    def __init__(
        self,
        mode: str = "open",
        initial_dir: Path | None = None,
        allowed_exts: list[str] = None,
        default_name: str = "",
        multi_select: bool = False,
        data_root: Path | None = None,
        window_size: tuple[int, int] = (800, 600),
    ):
        if allowed_exts is None:
            allowed_exts = []
        pygame.init()
        load_standalone_theme()
        self.screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
        pygame.display.set_caption(f"File Manager - {mode.capitalize()}")
        self.clock = pygame.time.Clock()
        self.running = True
        self.window_size = window_size

        if initial_dir and not initial_dir.is_absolute():
            initial_dir = Path.cwd() / initial_dir

        if data_root and not data_root.is_absolute():
            data_root = Path.cwd() / data_root

        if initial_dir is None:
            initial_dir = data_root if data_root else Path.cwd()

        if not initial_dir.exists():
            raise RuntimeError(f"Initial directory does not exist: {initial_dir}")

        rect = Rect(0, 0, window_size[0], window_size[1])
        self.file_manager = FileManager(
            rect=rect,
            initial_dir=initial_dir,
            allowed_exts=allowed_exts or [".png", ".jpg", ".json"],
            on_select=self._on_select,
            on_save=self._on_save if mode == "save" else None,
            mode=mode,
            default_name=default_name,
            on_cancel=self._on_cancel,
            multi_select=multi_select,
            draw_overlay=False,
            enable_window_drag=False,
            enable_resize_handles=False,
            data_root=data_root,
        )

    def _on_select(self, path):
        """Handle file selection - output to stdout and exit."""
        if isinstance(path, list):
            result = {
                "status": "selected",
                "paths": [str(p.resolve()) for p in path],
            }
        else:
            result = {
                "status": "selected",
                "path": str(path.resolve()),
            }

        print(json.dumps(result), flush=True)
        self.running = False

    def _on_save(self, path):
        """Handle save operation - output to stdout and exit."""
        result = {
            "status": "saved",
            "path": str(path.resolve()),
        }
        print(json.dumps(result), flush=True)
        self.running = False

    def _on_cancel(self):
        """Handle cancellation - output to stdout and exit."""
        result = {"status": "cancelled"}
        print(json.dumps(result), flush=True)
        self.running = False

    def run(self, fps: int = 60):
        """Main event loop."""
        while self.running:
            self.clock.tick(fps)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._on_cancel()
                    break
                if event.type == pygame.VIDEORESIZE:
                    self.window_size = (event.w, event.h)

                    self.file_manager.rect.x = 0
                    self.file_manager.rect.y = 0
                    self.file_manager.rect.width = event.w
                    self.file_manager.rect.height = event.h

                    self.file_manager.resize_handler.widget_rect = (
                        self.file_manager.rect
                    )

                    continue
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self._on_cancel()
                        break

                self.file_manager.handle_event(event)

            self.screen.fill(COLORS.bg)
            self.file_manager.draw(self.screen)
            pygame.display.flip()

        pygame.quit()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Standalone File Manager for selecting/saving files"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="open",
        choices=["open", "save"],
        help="File manager mode: open or save (default: open)",
    )
    parser.add_argument(
        "--initial-dir",
        type=str,
        default=None,
        help="Initial directory path (relative to project root or absolute)",
    )
    parser.add_argument(
        "--allowed-exts",
        type=str,
        default=".png,.jpg,.json",
        help="Comma-separated list of allowed extensions (default: .png,.jpg,.json)",
    )
    parser.add_argument(
        "--default-name",
        type=str,
        default="",
        help="Default filename for save mode",
    )
    parser.add_argument(
        "--multi-select",
        action="store_true",
        help="Enable multi-file selection",
    )
    parser.add_argument(
        "--window-size",
        type=str,
        default="800x600",
        help="Window size as WxH (default: 800x600)",
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Project data root for file manager preferences/recents",
    )

    args = parser.parse_args(argv)

    try:
        w, h = map(int, args.window_size.split("x"))
        window_size = (w, h)
    except ValueError:
        window_size = (800, 600)

    allowed_exts = [
        ext.strip() if ext.startswith(".") else f".{ext.strip()}"
        for ext in args.allowed_exts.split(",")
    ]

    initial_dir = None
    if args.initial_dir:
        initial_dir = Path(args.initial_dir)
    data_root = Path(args.data_root) if args.data_root else None

    fm = StandaloneFileManager(
        mode=args.mode,
        initial_dir=initial_dir,
        allowed_exts=allowed_exts,
        default_name=args.default_name,
        multi_select=args.multi_select,
        data_root=data_root,
        window_size=window_size,
    )
    fm.run()


if __name__ == "__main__":
    main()
