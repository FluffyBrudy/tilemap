"""
Placeholder marker palette generator (headless CLI).

Generates an MxN grid of uniquely distinct colored cells for use as a
marker tileset (e.g. player spawn positions): import the PNG as an
object tileset for 1x1, or as a tile tileset for MxN paintable markers.
With --slope, an extra bottom row of slope tiles is appended, each
colored like the solid cell above it.

Usage:
    python standalone_marker_palette.py
    python standalone_marker_palette.py --rows 5 --cols 5 --cell 32
    python standalone_marker_palette.py --rows 1 --cols 1 --out spawn.png
    python standalone_marker_palette.py --output-dir assets/markers --name enemies
    python standalone_marker_palette.py --rows 4 --cols 6 --slope 45
"""

from __future__ import annotations

import argparse
import colorsys
import math
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


def slope_polygon(cell: int, angle_deg: float) -> list[tuple[float, float]]:
    """Solid region of a slope tile in cell-local coords.

    Positive angles ascend to the right (solid = lower-left mass under
    the line ``y = x*tan(angle)``); negative angles mirror it
    (solid = lower-right). Clipped to the square, so any
    ``0 < |angle| < 90`` yields a valid polygon.
    """
    descending = angle_deg < 0
    t = math.tan(math.radians(abs(angle_deg)))
    corners = [(0.0, 0.0), (float(cell), 0.0),
               (float(cell), float(cell)), (0.0, float(cell))]

    def inside(p) -> bool:
        return p[1] >= t * p[0] - 1e-9

    poly: list[tuple[float, float]] = []
    for i in range(4):
        cur, nxt = corners[i], corners[(i + 1) % 4]
        in_cur, in_nxt = inside(cur), inside(nxt)
        if in_cur:
            poly.append(cur)
        if in_cur != in_nxt:
            x1, y1 = cur
            dx, dy = nxt[0] - x1, nxt[1] - y1
            denom = dy - t * dx
            s = ((t * x1) - y1) / denom if denom else 0.0
            poly.append((x1 + s * dx, y1 + s * dy))
    # drop near-duplicate vertices (line through a corner emits both)
    clean: list[tuple[float, float]] = []
    for p in poly:
        if not clean or math.hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > 1e-6:
            clean.append(p)
    if len(clean) > 1 and math.hypot(clean[0][0] - clean[-1][0],
                                     clean[0][1] - clean[-1][1]) <= 1e-6:
        clean.pop()
    poly = clean
    if descending:
        poly = [(cell - x, y) for x, y in poly]
    return poly


def build_palette(rows: int, cols: int, cell: int, saturation: float = 0.9,
                  value: float = 0.95, grid_lines: bool = True,
                  slope: float | None = None) -> pygame.Surface:
    """Build the marker grid surface (no display needed)."""
    total = rows * cols
    extra = 1 if slope is not None else 0
    surf = pygame.Surface((cols * cell, (rows + extra) * cell), pygame.SRCALPHA)
    for i in range(total):
        r, c = divmod(i, cols)
        color = marker_color(i, total, saturation, value)
        surf.fill(color, pygame.Rect(c * cell, r * cell, cell, cell))
    if slope is not None:
        for c in range(cols):
            above = (rows - 1) * cols + c
            color = marker_color(above, total, saturation, value)
            poly = slope_polygon(cell, slope)
            ox, oy = c * cell, rows * cell
            try:
                pygame.draw.polygon(
                    surf, color, [(ox + x, oy + y) for x, y in poly])
            except (ValueError, pygame.error):
                pass
    if grid_lines and cell >= 4:
        line = (20, 20, 20, 255)
        for c in range(cols + 1):
            surf.fill(line, pygame.Rect(c * cell - 1, 0, 2, (rows + extra) * cell))
        for r in range(rows + extra + 1):
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
    if getattr(args, "slope", None) is not None:
        name += f"_s{args.slope:g}"
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
    parser.add_argument("--slope", type=float, default=None,
                        help="Append a slope-tile row at this angle in degrees "
                        "(positive ascends right, negative descends; "
                        "0 < |angle| < 90)")
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
    if args.slope is not None and not 0.0 < abs(args.slope) < 90.0:
        print(f"error: --slope must satisfy 0 < |angle| < 90, got {args.slope}",
              file=sys.stderr)
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
                             grid_lines=not args.no_grid_lines,
                             slope=args.slope)
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
