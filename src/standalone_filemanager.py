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
import sys
import os
from pathlib import Path
from typing import List, Optional

# Suppress pygame welcome message
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
from pygame import Rect

# Ensure we can import from src
_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from constants import BASE_PATH
from widgets.filemanager import FileManager


class StandaloneFileManager:
    """Wrapper for FileManager that runs as a standalone process."""

    def __init__(
        self,
        mode: str = "open",
        initial_dir: Optional[Path] = None,
        allowed_exts: List[str] = [],
        default_name: str = "",
        multi_select: bool = False,
        window_size: tuple[int, int] = (800, 600),
    ):
        pygame.init()
        self.screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
        pygame.display.set_caption(f"File Manager - {mode.capitalize()}")
        self.clock = pygame.time.Clock()
        self.running = True
        self.window_size = window_size

        # Resolve initial directory relative to BASE_PATH if it's relative
        if initial_dir and not initial_dir.is_absolute():
            initial_dir = BASE_PATH / initial_dir

        if not initial_dir or not initial_dir.exists():
            raise RuntimeError(f"Initial directory does not exist: {initial_dir}")

        # Create FileManager widget - fill entire window (no margins for standalone)
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
            draw_overlay=False,  # No overlay in standalone mode
            enable_window_drag=False,  # OS handles window dragging
            enable_resize_handles=False,  # OS handles window resizing
        )

    def _on_select(self, path):
        """Handle file selection - output to stdout and exit."""
        if isinstance(path, list):
            # Multi-select
            result = {
                "status": "selected",
                "paths": [str(p.resolve()) for p in path],
            }
        else:
            # Single select
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
                elif event.type == pygame.VIDEORESIZE:
                    # Update window size
                    self.window_size = (event.w, event.h)
                    # Don't recreate screen on every resize, pygame handles it
                    # Just update the file manager rect
                    self.file_manager.rect.x = 0
                    self.file_manager.rect.y = 0
                    self.file_manager.rect.width = event.w
                    self.file_manager.rect.height = event.h
                    # Update resize handler to track new rect
                    self.file_manager.resize_handler.widget_rect = (
                        self.file_manager.rect
                    )
                    # Don't handle this event further to avoid double processing
                    continue
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self._on_cancel()
                        break

                # Handle events
                self.file_manager.handle_event(event)

            # Draw - no background fill needed, FileManager draws its own background
            self.file_manager.draw(self.screen)
            pygame.display.flip()

        pygame.quit()


def main(argv: List[str] | None = None) -> None:
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

    args = parser.parse_args(argv)

    # Parse window size
    try:
        w, h = map(int, args.window_size.split("x"))
        window_size = (w, h)
    except ValueError:
        window_size = (800, 600)

    # Parse allowed extensions
    allowed_exts = [
        ext.strip() if ext.startswith(".") else f".{ext.strip()}"
        for ext in args.allowed_exts.split(",")
    ]

    # Parse initial directory
    initial_dir = None
    if args.initial_dir:
        initial_dir = Path(args.initial_dir)

    # Create and run standalone file manager
    fm = StandaloneFileManager(
        mode=args.mode,
        initial_dir=initial_dir,
        allowed_exts=allowed_exts,
        default_name=args.default_name,
        multi_select=args.multi_select,
        window_size=window_size,
    )
    fm.run()


if __name__ == "__main__":
    main()
