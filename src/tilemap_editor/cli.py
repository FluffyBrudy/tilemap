from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from editor import Editor
from utils import error_context, error_handler
from utils.project_paths import resolve_project_path

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
        help='Theme name or path to .json theme file (built-in: dark, molokai, monokai, light, semi_light; or "path/to/custom.json")',
    )
    run_parser.add_argument(
        "--sandbox",
        nargs="?",
        const="sandbox",
        default=None,
        metavar="PATH",
        help="Run in sandbox mode: load map.json + assets/ from PATH (default: ./sandbox). "
        "Directory-only; throws away project isolation for experiment maps.",
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


def validate_sandbox(sandbox: Path) -> Path:
    """Pre-flight validation for --sandbox mode.

    Returns the resolved map path. Exits (SystemExit 1) with a message when
    the sandbox directory, map.json, or any referenced tileset is missing.
    """
    sandbox = Path(sandbox).expanduser()
    if not sandbox.is_dir():
        print(
            f"Sandbox directory not found: {sandbox}\n"
            "Expected layout:\n"
            "  sandbox/\n"
            "    map.json          # map exported by PixelForge VFX Studio\n"
            "    map.nodes.json    # optional node sidecar (same stem)\n"
            "    assets/*.png      # tileset images referenced by map.json\n"
            "Create the folder + export, or pass a path: tilemap-editor run --sandbox PATH"
        )
        sys.exit(1)

    map_path = sandbox / "map.json"
    if not map_path.is_file():
        print(f"Sandbox map not found: {map_path}\nExpected a map.json exported into the sandbox directory.")
        sys.exit(1)

    try:
        with open(map_path, encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Failed to read sandbox map {map_path}: {e}")
        sys.exit(1)

    resources = payload.get("resources", {})
    tilesets = resources if isinstance(resources, list) else resources.get("tilesets", []) if isinstance(resources, dict) else []

    missing: list[str] = []
    for entry in tilesets:
        path_str = entry if isinstance(entry, str) else entry.get("path", "")
        if not path_str:
            continue
        resolved = resolve_project_path(path_str, map_path.parent, must_exist=True)
        if not resolved.is_file():
            missing.append(f"  {path_str} (tried: {resolved})")

    if missing:
        print("Sandbox tileset files missing:\n" + "\n".join(missing))
        sys.exit(1)

    return map_path


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
            sandbox_dir = None
            if getattr(args, "sandbox", None):
                sandbox_dir = validate_sandbox(Path(args.sandbox))
                sandbox_dir = sandbox_dir.parent
            editor = Editor(size=size, fps=max(1, args.fps), theme=args.theme, sandbox_dir=sandbox_dir)
            editor.run()
    except KeyboardInterrupt:
        print("\nEditor interrupted by user")
    except Exception as e:
        error_handler.capture(e, context="cli_main")
        print(f"Failed to start editor: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
