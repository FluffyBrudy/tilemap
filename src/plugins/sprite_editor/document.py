"""Document model — canvas surface, tile size, sheets metadata, regions.

Pure model: knows nothing about UI, rendering, hit-testing or the camera.
Every mutation bumps `revision` so the viewport can invalidate caches.
"""

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
    """A rectangular region in document (sprite-local float) coordinates.

    Shape-compatible with `widgets.ui.region_selector.Region` for sidecar
    persistence (the sprite editor uses its own copy to keep floats).
    """

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
        return cls(
            id=str(data.get("id", "") or uuid.uuid4().hex[:8]),
            rect=[float(v) for v in r],
            name=str(data.get("name", "")),
        )


class Document:
    """The edited spritesheet: pixels + tile grid + regions."""

    def __init__(self, surface: Surface | None = None, tile_size: tuple[int, int] = (32, 32)):
        self.surface: Surface | None = surface
        self.tile_size: tuple[int, int] = (int(tile_size[0]), int(tile_size[1]))
        self.sheets: list[str] = []
        self.regions: list[Region] = []
        # The cell label at the canvas's top-left pixel. Shifts automatically
        # (negative) when content is written above/left of the original origin,
        # so the canvas "grows on top/left" without dropping tiles.
        self.origin_col: int = 0
        self.origin_row: int = 0
        self.revision: int = 0

    # -- state ---------------------------------------------------------
    @property
    def has_canvas(self) -> bool:
        return self.surface is not None

    def set_surface(self, surface: Surface | None) -> None:
        """Replace the whole canvas (new sheet loaded); bumps revision."""
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

    # -- grid math -----------------------------------------------------
    def tile_rect(self, col: int, row: int) -> Rect:
        """Local (document px) rect of a cell. The rect may extend past the
        canvas edge for partial edge tiles."""
        return Rect(
            (col - self.origin_col) * self.tw,
            (row - self.origin_row) * self.th,
            self.tw,
            self.th,
        )

    def cell_at(self, x: float, y: float) -> tuple[int, int] | None:
        """Cell under a document (local px) point, or None if outside."""
        if not self.surface:
            return None
        w, h = self.surface.get_size()
        if x < 0 or y < 0 or x >= w or y >= h:
            return None
        return (int(x) // self.tw + self.origin_col, int(y) // self.th + self.origin_row)

    def cell_at_unbounded(self, x: float, y: float) -> tuple[int, int] | None:
        """Cell index for any non-negative document point, even past the
        canvas edge (negative coordinates still return None)."""
        if not self.surface:
            return None
        if x < 0 or y < 0:
            return None
        return (int(x) // self.tw + self.origin_col, int(y) // self.th + self.origin_row)

    def is_valid_cell(self, col: int, row: int) -> bool:
        if not self.surface:
            return False
        if col < self.origin_col or row < self.origin_row:
            return False
        return col < self.origin_col + self.cols and row < self.origin_row + self.rows

    def cell_index(self, col: int, row: int) -> int:
        """Linear cell index for a given cell, accounting for origin."""
        return (row - self.origin_row) * self.cols + (col - self.origin_col)

    def cell_col_row(self, idx: int) -> tuple[int, int]:
        """Convert linear index to (col, row), accounting for origin."""
        if self.cols == 0:
            return (self.origin_col, self.origin_row)
        return (
            idx % self.cols + self.origin_col,
            idx // self.cols + self.origin_row,
        )

    def index_at(self, x: float, y: float) -> int:
        """Linear cell index under a local px point, or -1."""
        cell = self.cell_at(x, y)
        if cell is None:
            return -1
        return self.cell_index(*cell)

    # -- tile access ---------------------------------------------------
    def extract_tile(self, col: int, row: int) -> Surface:
        """Copy of the cell's pixels (transparent where outside the canvas)."""
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
        """Auto-handle the origin (min/max bounds): shift the origin so the
        label (col, row) is inside the canvas, growing right/down as needed.
        Nothing is ever dropped for negative coordinates."""
        if not self.surface:
            return
        new_origin_col = min(self.origin_col, col)
        new_origin_row = min(self.origin_row, row)
        need_cols = max(self.cols, col - new_origin_col + 1)
        need_rows = max(self.rows, row - new_origin_row + 1)
        self.origin_col = new_origin_col
        self.origin_row = new_origin_row
        self.expand_canvas_to(need_cols, need_rows)

    def clear_tiles(self, cells: list[tuple[int, int]]) -> None:
        if not self.surface or not cells:
            return
        for col, row in cells:
            self.surface.fill((0, 0, 0, 0), self.tile_rect(col, row))
        self._bump()

    def flip_tiles(self, cells: list[tuple[int, int]], flip_x: bool, flip_y: bool) -> None:
        if not self.surface or not cells:
            return
        for col, row in cells:
            tile = self.extract_tile(col, row)
            self.surface.blit(
                pygame.transform.flip(tile, flip_x, flip_y),
                self.tile_rect(col, row).topleft,
            )
        self._bump()

    # -- canvas growth -------------------------------------------------
    def ensure_contains_cells(self, cells: list[tuple[int, int]]) -> bool:
        """Grow the canvas (transparent) so every cell is in bounds.
        Returns True if the canvas changed."""
        if not cells or not self.surface:
            return False
        min_col = min(c for c, _ in cells)
        min_row = min(r for _, r in cells)
        max_col = max(c for c, _ in cells)
        max_row = max(r for _, r in cells)

        new_origin_col = min(self.origin_col, min_col)
        new_origin_row = min(self.origin_row, min_row)
        need_cols = max(self.cols, max_col - new_origin_col + 1)
        need_rows = max(self.rows, max_row - new_origin_row + 1)

        self.origin_col = new_origin_col
        self.origin_row = new_origin_row
        return self.expand_canvas_to(need_cols, need_rows)

    def expand_canvas_to(self, need_cols: int, need_rows: int) -> bool:
        if not self.surface:
            return False
        cur_w, cur_h = self.surface.get_size()
        new_w = max(cur_w, need_cols * self.tw)
        new_h = max(cur_h, need_rows * self.th)
        if new_w == cur_w and new_h == cur_h:
            return False
        new_surface = Surface((new_w, new_h), pygame.SRCALPHA)
        new_surface.fill((0, 0, 0, 0))
        new_surface.blit(self.surface, (0, 0))
        self.surface = new_surface
        self._bump()
        return True

    def append_sheet(self, sheet: Surface, horizontal: bool = False) -> None:
        """Grow the canvas by one imported block, snapped to tile boundaries.
        Never overwrites existing pixels.

        horizontal=True: the block is a *row* (batch hstacked); each import
        pass becomes the next row stacked vertically below the content.
        horizontal=False: the block is a *column* (batch vstacked); each
        pass becomes the next column placed right of the content.
        Blank canvas adopts the sheet as-is."""
        if self.surface is None:
            self.surface = sheet
            self._bump()
            return
        cur_w, cur_h = self.surface.get_size()
        sw, sh = sheet.get_size()
        if horizontal:
            y = math.ceil(cur_h / self.th) * self.th
            pos = (0, y)
            new_size = (max(cur_w, sw), y + sh)
        else:
            x = math.ceil(cur_w / self.tw) * self.tw
            pos = (x, 0)
            new_size = (x + sw, max(cur_h, sh))
        new_surface = Surface(new_size, pygame.SRCALPHA)
        new_surface.fill((0, 0, 0, 0))
        new_surface.blit(self.surface, (0, 0))
        new_surface.blit(sheet, pos)
        self.surface = new_surface
        self._bump()

    def set_tile_size(self, tile_size: tuple[int, int]) -> None:
        self.tile_size = (int(tile_size[0]), int(tile_size[1]))
        self._bump()

    def scale(self, factor: float) -> None:
        """Scale the whole canvas; tile size is unchanged."""
        if not self.surface or factor <= 0:
            return
        w, h = self.surface.get_size()
        self.surface = pygame.transform.scale(
            self.surface,
            (max(1, round(w * factor)), max(1, round(h * factor))),
        )
        self._bump()

    # -- regions -------------------------------------------------------
    def region_by_id(self, region_id: str) -> Region | None:
        for region in self.regions:
            if region.id == region_id:
                return region
        return None

    def add_region(self, region: Region) -> None:
        """Add a region and bump revision."""
        self.regions.append(region)
        self._bump()

    def move_region(self, region_id: str, dx: float, dy: float) -> bool:
        """Move a region by delta and bump revision. Returns True if found."""
        region = self.region_by_id(region_id)
        if region is None:
            return False
        region.rect[0] += dx
        region.rect[1] += dy
        self._bump()
        return True

    def resize_region(self, region_id: str, rect: list[float]) -> bool:
        """Set region rect and bump revision. Returns True if found."""
        region = self.region_by_id(region_id)
        if region is None:
            return False
        region.rect = list(rect)
        self._bump()
        return True

    def delete_region(self, region_id: str) -> bool:
        """Delete a region and bump revision. Returns True if found."""
        old_len = len(self.regions)
        self.regions = [r for r in self.regions if r.id != region_id]
        if len(self.regions) < old_len:
            self._bump()
            return True
        return False

    def rename_region(self, region_id: str, new_name: str) -> bool:
        """Rename a region and bump revision. Returns True if found."""
        region = self.region_by_id(region_id)
        if region is None:
            return False
        region.name = str(new_name)
        self._bump()
        return True

    # -- snapshots (command undo/redo) ---------------------------------
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
