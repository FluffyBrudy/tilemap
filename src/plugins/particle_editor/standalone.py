"""
Standalone launcher for the Particle Editor.

Usage:
    python -m plugins.particle_editor [library.particles.json]
    python -m plugins.particle_editor --load path/to/lib.particles.json
    python -m plugins.particle_editor --import-node node.json --export-node out.json
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent.parent.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import pygame

try:
    from .editor import ParticleEditor
    from .models import (
        ParticleLibrary,
        builtin_library,
        builtin_library_path,
        normalize_config,
    )
except ImportError:  # direct script execution
    from plugins.particle_editor.editor import ParticleEditor
    from plugins.particle_editor.models import (
        ParticleLibrary,
        builtin_library,
        builtin_library_path,
        normalize_config,
    )
from utils import error_context, error_handler
from utils.standalone import load_standalone_theme


def _parse_window_size(s: str) -> tuple[int, int]:
    parts = s.lower().split("x")
    if len(parts) == 2:
        return max(800, int(parts[0])), max(600, int(parts[1]))
    v = max(800, int(parts[0]))
    return v, v


def main(argv: list[str] | None = None) -> None:
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        error_handler.capture(exc_value, context="particle_editor_exception")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    try:
        parser = argparse.ArgumentParser(
            description="Particle Editor -- canvas-first particle authoring",
        )
        parser.add_argument(
            "library",
            type=Path,
            nargs="?",
            default=None,
            help="Library .particles.json to open (default: built-in essentials)",
        )
        parser.add_argument("--load", type=Path, default=None, help="Alias for library")
        parser.add_argument(
            "--import-node",
            type=Path,
            default=None,
            help="Start from an exported node JSON ({name, config})",
        )
        parser.add_argument(
            "--export-node",
            type=Path,
            default=None,
            help="Write {name, config} here on every save (tilemap handoff)",
        )
        parser.add_argument("--window-size", type=str, default="1180x760", help="Window size WxH")
        parser.add_argument("--data-root", type=Path, default=None)
        parser.add_argument(
            "--frames",
            type=int,
            default=0,
            help="Quit after N frames (headless smoke tests)",
        )
        args = parser.parse_args(argv)

        data_root = args.data_root if args.data_root else Path.cwd() / "data"

        with error_context("particle_editor_main"):
            lib_arg = args.load or args.library
            library_path: Path | None = None
            if lib_arg is not None:
                if lib_arg.exists():
                    library, warnings = ParticleLibrary.load(lib_arg)
                    library_path = lib_arg
                else:
                    print(
                        f"Library not found: {lib_arg}, using built-in",
                        file=sys.stderr,
                    )
                    library, warnings = builtin_library()
                    library_path = builtin_library_path()
            else:
                library, warnings = builtin_library()
                library_path = builtin_library_path()
            for w in warnings:
                print(f"library warning: {w}", file=sys.stderr)

            pygame.init()
            load_standalone_theme()
            width, height = _parse_window_size(args.window_size)
            screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
            pygame.display.set_caption("Particle Editor")

            editor = ParticleEditor(
                pygame.Rect(0, 0, width, height),
                library,
                library_path,
                data_root,
                export_node=args.export_node,
            )
            if args.import_node and args.import_node.exists():
                try:
                    payload = json.loads(args.import_node.read_text(encoding="utf-8"))
                    name = str(payload.get("name", "Imported"))
                    config, _ = normalize_config(payload.get("config"))
                    editor.load_entry(name, config)
                    print(f"Imported node: {name}")
                except (OSError, ValueError) as e:
                    print(f"Import failed: {e}", file=sys.stderr)

            clock = pygame.time.Clock()
            running = True
            frames = 0
            while running:
                dt = clock.tick(60) / 1000.0
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        if editor.is_dirty():
                            print("Unsaved changes discarded", file=sys.stderr)
                        running = False
                        break
                    if event.type == pygame.VIDEORESIZE:
                        width, height = max(800, event.w), max(600, event.h)
                        screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                        editor.set_rect(pygame.Rect(0, 0, width, height))
                        continue
                    editor.handle_event(event)
                if not running:
                    break
                editor.update(dt)
                editor.toasts.update(screen, dt)
                editor.draw(screen)
                editor.toasts.draw(screen)
                pygame.display.flip()
                frames += 1
                if args.frames and frames >= args.frames:
                    running = False
            pygame.quit()
    except KeyboardInterrupt:
        print("\nParticle editor interrupted by user")
    except Exception as e:
        error_handler.capture(e, context="particle_editor_main")
        print(f"Failed to start particle editor: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
