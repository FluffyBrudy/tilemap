"""
Placeholder marker palette generator (headless CLI).

Generates an MxN grid of uniquely distinct colored cells for use as a
marker tileset (e.g. player spawn positions): import the PNG as an
object tileset for 1x1, or as a tile tileset for MxN paintable markers.

Usage:
    python standalone_marker_palette.py
    python standalone_marker_palette.py --rows 5 --cols 5 --cell 32
    python standalone_marker_palette.py --rows 1 --cols 1 --out spawn.png
    python standalone_marker_palette.py --output-dir assets/markers --name enemies
"""

from __future__ import annotations

import argparse
import colorsys
import os
import sys
from pathlib import Path

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

MAX_GRID = 20
DEFAULT_CELL = 32


def marker_color(index: int, total: int, saturation: float = 0.9,
                 value: float = 0.95) -> tuple[int, int, int]:
    """Distinct color per cell via golden-angle hue rotation."""
    hue = ((index * 137.508) % 360.0) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    return (int(r * 255), int(g * 255), int(b * 255))


def build_palette(rows: int, cols: int, cell: int, saturation: float = 0.9,
                  value: float = 0.95, grid_lines: bool = True) -> pygame.Surface:
    """Build the marker grid surface (no display needed)."""
    total = rows * cols
    surf = pygame.Surface((cols * cell, rows * cell), pygame.SRCALPHA)
    for i in range(total):
        r, c = divmod(i, cols)
        color = marker_color(i, total, saturation, value)
        surf.fill(color, pygame.Rect(c * cell, r * cell, cell, cell))
    if grid_lines and cell >= 4:
        line = (20, 20, 20, 255)
        for c in range(cols + 1):
            surf.fill(line, pygame.Rect(c * cell - 1, 0, 2, rows * cell))
        for r in range(rows + 1):
            surf.fill(line, pygame.Rect(0, r * cell - 1, cols * cell, 2))
    return surf


def resolve_output(args) -> Path:
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = Path.cwd() / out
        return out
    out_dir = Path(args.output_dir) if args.output_dir else Path.cwd()
    if not out_dir.is_absolute():
        out_dir = Path.cwd() / out_dir
    name = args.name or f"markers_{args.cols}x{args.rows}_c{args.cell}"
    if not name.lower().endswith(".png"):
        name += ".png"
    return out_dir / name


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a placeholder marker palette PNG.")
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--cell", type=int, default=DEFAULT_CELL,
                        help="Square cell size in px (use the project tile size)")
    parser.add_argument("--output-dir", default=None,
                        help="Target dir (default: cwd)")
    parser.add_argument("--out", default=None,
                        help="Exact output file (overrides --output-dir/--name)")
    parser.add_argument("--name", default=None,
                        help="File stem (default: markers_{cols}x{rows}_c{cell})")
    parser.add_argument("--saturation", type=float, default=0.9)
    parser.add_argument("--value", type=float, default=0.95)
    parser.add_argument("--no-grid-lines", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    for label, val in (("rows", args.rows), ("cols", args.cols)):
        if not 1 <= val <= MAX_GRID:
            print(f"error: --{label} must be 1..{MAX_GRID}, got {val}",
                  file=sys.stderr)
            return 2
    if args.cell < 1:
        print(f"error: --cell must be positive, got {args.cell}", file=sys.stderr)
        return 2
    for label, val in (("saturation", args.saturation), ("value", args.value)):
        if not 0.0 <= val <= 1.0:
            print(f"error: --{label} must be 0..1, got {val}", file=sys.stderr)
            return 2

    out = resolve_output(args)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"error: cannot create {out.parent}: {e}", file=sys.stderr)
        return 1

    pygame.init()
    try:
        surf = build_palette(args.rows, args.cols, args.cell,
                             args.saturation, args.value,
                             grid_lines=not args.no_grid_lines)
        pygame.image.save(surf, str(out))
    except (OSError, pygame.error) as e:
        print(f"error: cannot write {out}: {e}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()
    print(str(out.resolve()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
