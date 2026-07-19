from __future__ import annotations

import argparse
import sys

from editor import Editor
from utils import error_context, error_handler

from .settings import init_settings, update_settings


def _parse_size(text: str) -> tuple[int, int]:
    parts = text.lower().split("x")
    if len(parts) == 1:
        n = int(parts[0])
        return n, n
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    raise ValueError("size must be WIDTHxHEIGHT")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tilemap Editor")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    init_parser = subparsers.add_parser(
        "init", help="Initialize a new Tilemap Editor project"
    )
    init_parser.add_argument(
        "--with-main", action="store_true", help="Also create src/main.py boilerplate"
    )

    update_parser = subparsers.add_parser(
        "update", help="Update settings.json base_path for current device"
    )
    update_parser.add_argument(
        "--path",
        default=None,
        help="Explicit base path (default: resolves cwd to absolute path)",
    )

    run_parser = subparsers.add_parser("run", help="Run the tilemap editor")
    run_parser.add_argument(
        "--size", default="1500x900", help="Window size as WIDTHxHEIGHT"
    )
    run_parser.add_argument("--fps", type=int, default=60, help="Editor FPS")
    run_parser.add_argument(
        "--theme",
        default=None,
        help='Theme name or path to .json theme file (e.g. "molokai", "path/to/custom.json")',
    )

    args = parser.parse_args()

    if args.command == "init":
        init_settings(generate_main=args.with_main)
        return

    if args.command == "update":
        update_settings(path=args.path)
        return

    if args.command is None or args.command == "run":
        _run_editor(args)
        return

    parser.print_help()


def _run_editor(args) -> None:
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        error_handler.capture(exc_value, context="global_exception")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    try:
        with error_context("cli_main"):
            size = _parse_size(args.size)
            editor = Editor(size=size, fps=max(1, args.fps), theme=args.theme)
            editor.run()
    except KeyboardInterrupt:
        print("\nEditor interrupted by user")
    except Exception as e:
        error_handler.capture(e, context="cli_main")
        print(f"Failed to start editor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
