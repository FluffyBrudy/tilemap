from __future__ import annotations

import argparse
import sys

from editor import Editor
from utils import error_handler, error_context


def _parse_size(text: str) -> tuple[int, int]:
    parts = text.lower().split("x")
    if len(parts) == 1:
        n = int(parts[0])
        return n, n
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    raise ValueError("size must be WIDTHxHEIGHT")


def main() -> None:
    # Global exception handler to catch everything
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        error_handler.capture(exc_value, context="global_exception")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    try:
        parser = argparse.ArgumentParser(description="Run tilemap editor")
        parser.add_argument(
            "--size", default="1500x900", help="Window size as WIDTHxHEIGHT"
        )
        parser.add_argument("--fps", type=int, default=60, help="Editor FPS")
        args = parser.parse_args()

        with error_context("cli_main"):
            size = _parse_size(args.size)
            editor = Editor(size=size, fps=max(1, args.fps))
            editor.run()
    except KeyboardInterrupt:
        print("\nEditor interrupted by user")
    except Exception as e:
        error_handler.capture(e, context="cli_main")
        print(f"Failed to start editor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
