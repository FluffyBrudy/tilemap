"""Canvas surface, tile size, sheets, and regions."""

from __future__ import annotations

import copy
import math
import uuid
from dataclasses import dataclass, field
from typing import Any

import pygame
from pygame import Rect, Surface


@dataclass
class Region:
    """Rect area on the canvas in float pixels."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    rect: list[float] = field(default_factory=lambda: [0.0, 0.0, 32.0, 32.0])
    name: str = ""

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:8]

    @property
    def x(self) -> float:
        return self.rect[0]

    @property
    def y(self) -> float:
        return self.rect[1]

    @property
    def w(self) -> float:
        return self.rect[2]

    @property
    def h(self) -> float:
        return self.rect[3]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rect": [int(round(v)) for v in self.rect],
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Region:
        r = data.get("rect", [0, 0, 32, 32])
        try:
            rect = [float(v) for v in r]
            if len(rect) != 4:
                raise ValueError("rect needs 4 numbers")
        except (TypeError, ValueError):
            rect = [0.0, 0.0, 32.0, 32.0]
        return cls(
            id=str(data.get("id", "") or uuid.uuid4().hex[:8]),
            rect=rect,
            name=str(data.get("name", "")),
        )


class Document:
    """Edited spritesheet: pixels, tile grid, and regions."""

    def __init__(self, surface: Surface | None = None, tile_size: tuple[int, int] = (32, 32)):
        self.surface: Surface | None = surface
        self.tile_size: tuple[int, int] = (int(tile_size[0]), int(tile_size[1]))
        self.sheets: list[str] = []
        self.regions: list[Region] = []
        # Top-left cell label. Moves negative when canvas grows up or left.
        self.origin_col: int = 0
        self.origin_row: int = 0
        self.revision: int = 0
        self.wrap_cols: int | None = None
        self.wrap_rows: int | None = None

    @property
    def has_canvas(self) -> bool:
        return self.surface is not None

    def set_surface(self, surface: Surface | None) -> None:
        self.origin_col = 0
        self.origin_row = 0
        self.surface = surface
        self._bump()

    @property
    def size(self) -> tuple[int, int]:
        return self.surface.get_size() if self.surface else (0, 0)

    @property
    def tw(self) -> int:
        return self.tile_size[0]

    @property
    def th(self) -> int:
        return self.tile_size[1]

    @property
    def cols(self) -> int:
        w, _ = self.size
        if not self.surface or w <= 0:
            return 0
        return max(1, (w + self.tw - 1) // self.tw)

    @property
    def rows(self) -> int:
        _, h = self.size
        if not self.surface or h <= 0:
            return 0
        return max(1, (h + self.th - 1) // self.th)

    @property
    def cell_count(self) -> int:
        return self.cols * self.rows

    def tile_rect(self, col: int, row: int) -> Rect:
        return Rect(
            (col - self.origin_col) * self.tw,
            (row - self.origin_row) * self.th,
            self.tw,
            self.th,
        )

    def cell_at(self, x: float, y: float) -> tuple[int, int] | None:
        if not self.surface:
            return None
        w, h = self.surface.get_size()
        if x < 0 or y < 0 or x >= w or y >= h:
            return None
        return (math.floor(x / self.tw) + self.origin_col, math.floor(y / self.th) + self.origin_row)

    def cell_at_unbounded(self, x: float, y: float) -> tuple[int, int] | None:
        if not self.surface:
            return None
        if x < 0 or y < 0:
            return None
        return (math.floor(x / self.tw) + self.origin_col, math.floor(y / self.th) + self.origin_row)

    def is_valid_cell(self, col: int, row: int) -> bool:
        if not self.surface:
            return False
        if col < self.origin_col or row < self.origin_row:
            return False
        return col < self.origin_col + self.cols and row < self.origin_row + self.rows

    def cell_index(self, col: int, row: int) -> int:
        return (row - self.origin_row) * self.cols + (col - self.origin_col)

    def cell_col_row(self, idx: int) -> tuple[int, int]:
        if self.cols == 0:
            return (self.origin_col, self.origin_row)
        return (
            idx % self.cols + self.origin_col,
            idx // self.cols + self.origin_row,
        )

    def index_at(self, x: float, y: float) -> int:
        cell = self.cell_at(x, y)
        if cell is None:
            return -1
        return self.cell_index(*cell)

    def extract_tile(self, col: int, row: int) -> Surface:
        tile = Surface((self.tw, self.th), pygame.SRCALPHA)
        if not self.surface:
            return tile
        src = self.tile_rect(col, row)
        clipped = src.clip(self.surface.get_rect())
        if clipped.w > 0 and clipped.h > 0:
            tile.blit(self.surface, (clipped.x - src.x, clipped.y - src.y), clipped)
        return tile

    def write_tile(self, col: int, row: int, tile: Surface) -> None:
        if not self.surface:
            return
        self._absorb_label(col, row)
        self.surface.blit(tile, self.tile_rect(col, row).topleft)
        self._bump()

    def _absorb_label(self, col: int, row: int) -> None:
        """Grow canvas so (col, row) fits. Never drops content."""
        if not self.surface:
            return
        old_cols, old_rows = self.cols, self.rows
        new_origin_col = min(self.origin_col, col)
        new_origin_row = min(self.origin_row, row)
        need_cols = max(self.origin_col + old_cols, col + 1) - new_origin_col
        need_rows = max(self.origin_row + old_rows, row + 1) - new_origin_row
        shift_x = (self.origin_col - new_origin_col) * self.tw
        shift_y = (self.origin_row - new_origin_row) * self.th
        self.origin_col = new_origin_col
        self.origin_row = new_origin_row
        self.expand_canvas_to(need_cols, need_rows, shift=(shift_x, shift_y))

    def clear_tiles(self, cells: list[tuple[int, int]]) -> None:
        if not self.surface or not cells:
            return
        for col, row in cells:
            self.surface.fill((0, 0, 0, 0), self.tile_rect(col, row))
        self._bump()

    def trim_to_content(self) -> bool:
        """Shrink canvas to content. Returns True if changed."""
        if not self.surface:
            return False
        # Any visible pixel counts, so faint pixels are kept.
        mask = pygame.mask.from_surface(self.surface, threshold=1)
        rects = mask.get_bounding_rects()
        if not rects:
            tw, th = max(1, self.tw), max(1, self.th)
            if self.surface.get_size() == (tw, th):
                return False
            self.surface = Surface((tw, th), pygame.SRCALPHA)
            self.surface.fill((0, 0, 0, 0))
            self.origin_col = 0
            self.origin_row = 0
            self.regions = []
            self._bump()
            return True
        min_x = min(r.x for r in rects)
        min_y = min(r.y for r in rects)
        max_x = max(r.right for r in rects)
        max_y = max(r.bottom for r in rects)
        tw, th = max(1, self.tw), max(1, self.th)
        left = (min_x // tw) * tw
        top = (min_y // th) * th
        right = ((max_x + tw - 1) // tw) * tw
        bottom = ((max_y + th - 1) // th) * th
        old_w, old_h = self.surface.get_size()
        if (left, top, right - left, bottom - top) == (0, 0, old_w, old_h):
            return False
        # Clip to canvas before blit.
        dest = Surface((right - left, bottom - top), pygame.SRCALPHA)
        dest.fill((0, 0, 0, 0))
        src_rect = Rect(left, top, right - left, bottom - top).clip(self.surface.get_rect())
        if src_rect.w > 0 and src_rect.h > 0:
            dest.blit(self.surface, (src_rect.x - left, src_rect.y - top), src_rect)
        self.surface = dest
        self.origin_col += left // tw
        self.origin_row += top // th
        new_w, new_h = self.surface.get_size()
        kept = []
        for region in self.regions:
            x, y, w, h = region.rect
            nx, ny = x - left, y - top
            if nx < new_w and ny < new_h and nx + w > 0 and ny + h > 0:
                kept.append(Region(id=region.id, rect=[nx, ny, w, h], name=region.name))
        self.regions = kept
        self._bump()
        return True

    def flip_tiles(self, cells: list[tuple[int, int]], flip_x: bool, flip_y: bool) -> None:
        """Mirror selected box in place."""
        if not self.surface or not cells:
            return
        cols = sorted({c for c, _ in cells})
        rows = sorted({r for _, r in cells})
        c0, c1 = cols[0], cols[-1]
        r0, r1 = rows[0], rows[-1]
        tiles = {(c, r): self.extract_tile(c, r) for c, r in cells}
        dests = {
            ((c0 + c1 - c if flip_x else c), (r0 + r1 - r if flip_y else r))
            for c, r in tiles
        }
        for dc, dr in dests:
            self.surface.fill((0, 0, 0, 0), self.tile_rect(dc, dr))
        for (c, r), tile in tiles.items():
            nc = c0 + c1 - c if flip_x else c
            nr = r0 + r1 - r if flip_y else r
            self.surface.blit(
                pygame.transform.flip(tile, flip_x, flip_y),
                self.tile_rect(nc, nr).topleft,
            )
        self._bump()

    def ensure_contains_cells(self, cells: list[tuple[int, int]]) -> bool:
        """Grow canvas to fit cells. Returns True if changed."""
        if not cells or not self.surface:
            return False
        min_col = min(c for c, _ in cells)
        min_row = min(r for _, r in cells)
        max_col = max(c for c, _ in cells)
        max_row = max(r for _, r in cells)

        old_cols, old_rows = self.cols, self.rows
        new_origin_col = min(self.origin_col, min_col)
        new_origin_row = min(self.origin_row, min_row)
        need_cols = max(self.origin_col + old_cols, max_col + 1) - new_origin_col
        need_rows = max(self.origin_row + old_rows, max_row + 1) - new_origin_row

        shift_x = (self.origin_col - new_origin_col) * self.tw
        shift_y = (self.origin_row - new_origin_row) * self.th
        self.origin_col = new_origin_col
        self.origin_row = new_origin_row
        return self.expand_canvas_to(need_cols, need_rows, shift=(shift_x, shift_y))

    def expand_canvas_to(self, need_cols: int, need_rows: int, shift: tuple[int, int] = (0, 0)) -> bool:
        if not self.surface:
            return False
        cur_w, cur_h = self.surface.get_size()
        new_w = max(cur_w, need_cols * self.tw)
        new_h = max(cur_h, need_rows * self.th)
        if new_w == cur_w and new_h == cur_h and shift == (0, 0):
            return False
        new_surface = Surface((new_w, new_h), pygame.SRCALPHA)
        new_surface.fill((0, 0, 0, 0))
        new_surface.blit(self.surface, shift)
        self.surface = new_surface
        self._bump()
        return True

    def append_sheet(self, sheet: Surface, place: str = "below") -> None:
        if self.surface is None:
            self.surface = sheet.copy()
            self._bump()
            return
        if place not in ("below", "right"):
            place = "below"
        cur_w, cur_h = self.surface.get_size()
        sw, sh = sheet.get_size()
        tw = max(1, self.tw)
        th = max(1, self.th)
        blocks: list[tuple[Rect, tuple[int, int]]] = []
        if place == "below":
            y = math.ceil(cur_h / th) * th
            cap = self.wrap_cols * tw if self.wrap_cols and self.wrap_cols > 0 else 0
            if cap > 0 and sw > cap:
                n = math.ceil(sw / cap)
                for i in range(n):
                    w = min(cap, sw - i * cap)
                    blocks.append((Rect(i * cap, 0, w, sh), (0, y + i * sh)))
                new_size = (max(cur_w, cap), y + n * sh)
            else:
                blocks.append((Rect(0, 0, sw, sh), (0, y)))
                new_size = (max(cur_w, sw), y + sh)
        else:
            x = math.ceil(cur_w / tw) * tw
            cap = self.wrap_rows * th if self.wrap_rows and self.wrap_rows > 0 else 0
            if cap > 0 and sh > cap:
                n = math.ceil(sh / cap)
                for i in range(n):
                    h = min(cap, sh - i * cap)
                    blocks.append((Rect(0, i * cap, sw, h), (x + i * sw, 0)))
                new_size = (x + n * sw, max(cur_h, cap))
            else:
                blocks.append((Rect(0, 0, sw, sh), (x, 0)))
                new_size = (x + sw, max(cur_h, sh))
        new_surface = Surface(new_size, pygame.SRCALPHA)
        new_surface.fill((0, 0, 0, 0))
        new_surface.blit(self.surface, (0, 0))
        for src, pos in blocks:
            new_surface.blit(sheet.subsurface(src), pos)
        self.surface = new_surface
        self._bump()

    def set_tile_size(self, tile_size: tuple[int, int]) -> None:
        tw, th = int(tile_size[0]), int(tile_size[1])
        if tw < 1 or th < 1:
            raise ValueError(f"tile size must be >= 1, got {(tw, th)}")
        self.tile_size = (tw, th)
        self._bump()

    def scale(self, factor: float) -> None:
        """Scale canvas. Tile size stays the same."""
        if not self.surface or factor <= 0:
            return
        w, h = self.surface.get_size()
        nw, nh = max(1, round(w * factor)), max(1, round(h * factor))
        if nw > 8192 or nh > 8192:
            raise ValueError(f"scaled size {(nw, nh)} exceeds 8192px cap")
        self.surface = pygame.transform.scale(self.surface, (nw, nh))
        for region in self.regions:
            x, y, rw, rh = region.rect
            region.rect = [x * factor, y * factor, rw * factor, rh * factor]
        self._bump()

    def region_by_id(self, region_id: str) -> Region | None:
        for region in self.regions:
            if region.id == region_id:
                return region
        return None

    def add_region(self, region: Region) -> None:
        self.regions.append(Region(id=region.id, rect=list(region.rect), name=region.name))
        self._bump()

    def move_region(self, region_id: str, dx: float, dy: float) -> bool:
        region = self.region_by_id(region_id)
        if region is None:
            return False
        region.rect[0] += dx
        region.rect[1] += dy
        self._bump()
        return True

    def resize_region(self, region_id: str, rect: list[float]) -> bool:
        region = self.region_by_id(region_id)
        if region is None:
            return False
        try:
            clean = [float(v) for v in rect]
            if len(clean) != 4:
                return False
        except (TypeError, ValueError):
            return False
        region.rect = clean
        self._bump()
        return True

    def delete_region(self, region_id: str) -> bool:
        old_len = len(self.regions)
        self.regions = [r for r in self.regions if r.id != region_id]
        if len(self.regions) < old_len:
            self._bump()
            return True
        return False

    def rename_region(self, region_id: str, new_name: str) -> bool:
        region = self.region_by_id(region_id)
        if region is None:
            return False
        region.name = str(new_name)
        self._bump()
        return True

    def blit_surface(self, surf: Surface, pos: tuple[int, int]) -> tuple[int, int]:
        """Blit surface at pos. Grows canvas if needed."""
        if not self.surface or surf is None:
            return (0, 0)
        x, y = int(pos[0]), int(pos[1])
        sw, sh = surf.get_size()
        old_w, old_h = self.surface.get_size()
        tw = max(1, self.tw)
        th = max(1, self.th)
        shift_x = -min(0, x)
        shift_y = -min(0, y)
        if shift_x:
            shift_x = ((shift_x + tw - 1) // tw) * tw
        if shift_y:
            shift_y = ((shift_y + th - 1) // th) * th
        need_w = max(old_w, x + sw) + shift_x
        need_h = max(old_h, y + sh) + shift_y
        if shift_x or shift_y:
            new_surface = Surface((need_w, need_h), pygame.SRCALPHA)
            new_surface.fill((0, 0, 0, 0))
            new_surface.blit(self.surface, (shift_x, shift_y))
            self.surface = new_surface
            self.origin_col -= shift_x // tw
            self.origin_row -= shift_y // th
            x += shift_x
            y += shift_y
        elif self.surface.get_width() < need_w or self.surface.get_height() < need_h:
            new_surface = Surface((need_w, need_h), pygame.SRCALPHA)
            new_surface.fill((0, 0, 0, 0))
            new_surface.blit(self.surface, (0, 0))
            self.surface = new_surface
        self.surface.blit(surf, (x, y))
        self._bump()
        return (shift_x, shift_y)

    def clear_rect(self, rect: Rect) -> bool:
        if not self.surface:
            return False
        clipped = Rect(rect).clip(self.surface.get_rect())
        if clipped.w <= 0 or clipped.h <= 0:
            return False
        self.surface.fill((0, 0, 0, 0), clipped)
        self._bump()
        return True

    def move_pixels(self, src: Rect, dx: int, dy: int) -> Rect | None:
        """Move pixel block. Source becomes transparent."""
        if not self.surface:
            return None
        clipped = src.clip(self.surface.get_rect())
        if clipped.w <= 0 or clipped.h <= 0:
            return None
        block = self.surface.subsurface(clipped).copy()
        self.surface.fill((0, 0, 0, 0), clipped)
        self._bump()
        dest = Rect(clipped.x + int(dx), clipped.y + int(dy), clipped.w, clipped.h)
        shift_x, shift_y = self.blit_surface(block, dest.topleft)
        return Rect(dest.x + shift_x, dest.y + shift_y, dest.w, dest.h)

    def mirror_pixels(self, src: Rect, axis: str, side: int = 1) -> Rect | None:
        """Stamp a mirrored copy next to the block. Source is kept."""
        if not self.surface:
            return None
        clipped = src.clip(self.surface.get_rect())
        if clipped.w <= 0 or clipped.h <= 0:
            return None
        block = self.surface.subsurface(clipped).copy()
        if axis == "v":
            block = pygame.transform.flip(block, False, True)
            dx, dy = (0, clipped.h if side >= 0 else -clipped.h)
        else:
            block = pygame.transform.flip(block, True, False)
            dx, dy = (clipped.w if side >= 0 else -clipped.w, 0)
        dest = Rect(clipped.x + dx, clipped.y + dy, clipped.w, clipped.h)
        shift_x, shift_y = self.blit_surface(block, dest.topleft)
        return Rect(dest.x + shift_x, dest.y + shift_y, dest.w, dest.h)

    def scale_pixels(self, src: Rect, dest: Rect) -> Rect | None:
        """Scale pixel block into dest rect."""
        if not self.surface:
            return None
        clipped = src.clip(self.surface.get_rect())
        if clipped.w <= 0 or clipped.h <= 0:
            return None
        dw, dh = max(1, int(dest.w)), max(1, int(dest.h))
        block = self.surface.subsurface(clipped).copy()
        scaled = pygame.transform.scale(block, (dw, dh))
        self.surface.fill((0, 0, 0, 0), clipped)
        self._bump()
        final = Rect(int(dest.x), int(dest.y), dw, dh)
        shift_x, shift_y = self.blit_surface(scaled, final.topleft)
        return Rect(final.x + shift_x, final.y + shift_y, dw, dh)

    def remap_pixels(
        self,
        src: tuple[int, int, int, int],
        dst: tuple[int, int, int, int],
        rect: Rect | None = None,
        tolerance: int = 0,
        contiguous: bool = False,
        seed: tuple[int, int] | None = None,
        dry_run: bool = False,
    ) -> int:
        """Replace src color with dst. Returns replaced count."""
        if not self.surface:
            return 0
        bounds = self.surface.get_rect() if rect is None else Rect(rect).clip(self.surface.get_rect())
        if bounds.w <= 0 or bounds.h <= 0:
            return 0
        sr, sg, sb, sa = (int(src[0]), int(src[1]), int(src[2]), int(src[3]))
        dr, dg, db, da = (int(dst[0]), int(dst[1]), int(dst[2]), int(dst[3]))
        tol = max(0, int(tolerance))
        tol2 = tol * tol * 3

        def matches(r: int, g: int, b: int, a: int) -> bool:
            if a == 0 or sa == 0:
                return a == sa and r == sr and g == sg and b == sb
            dr_ = r - sr
            dg_ = g - sg
            db_ = b - sb
            return dr_ * dr_ + dg_ * dg_ + db_ * db_ <= tol2

        targets: set[tuple[int, int]] = set()
        if contiguous:
            if seed is None:
                return 0
            sx, sy = int(seed[0]), int(seed[1])
            if not bounds.collidepoint(sx, sy):
                return 0
            sc = self.surface.get_at((sx, sy))
            if not matches(sc.r, sc.g, sc.b, sc.a):
                return 0
            stack = [(sx, sy)]
            seen = {(sx, sy)}
            while stack:
                x, y = stack.pop()
                c = self.surface.get_at((x, y))
                if not matches(c.r, c.g, c.b, c.a):
                    continue
                targets.add((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if (nx, ny) in seen or not bounds.collidepoint(nx, ny):
                        continue
                    seen.add((nx, ny))
                    stack.append((nx, ny))
        else:
            for y in range(bounds.y, bounds.y + bounds.h):
                for x in range(bounds.x, bounds.x + bounds.w):
                    c = self.surface.get_at((x, y))
                    if matches(c.r, c.g, c.b, c.a):
                        targets.add((x, y))
        if not targets:
            return 0
        if dry_run:
            return len(targets)
        for x, y in targets:
            self.surface.set_at((x, y), (dr, dg, db, da))
        self._bump()
        return len(targets)

    def snapshot(self) -> tuple[Surface | None, list[Region], tuple[int, int], tuple[int, int]]:
        return (
            self.surface.copy() if self.surface else None,
            copy.deepcopy(self.regions),
            tuple(self.tile_size),
            (self.origin_col, self.origin_row),
        )

    def restore(
        self,
        snap: tuple[Surface | None, list[Region], tuple[int, int], tuple[int, int]],
    ) -> None:
        self.surface = snap[0].copy() if snap[0] else None
        self.regions = copy.deepcopy(snap[1])
        self.tile_size = snap[2]
        self.origin_col, self.origin_row = snap[3]
        self._bump()

    def _bump(self) -> None:
        self.revision += 1
