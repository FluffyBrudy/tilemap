"""Clipboard — layout-relative tile data, independent of the UI.

Fixes the old absolute-index clipboard (P5/P6): tiles are stored as
(dx, dy) offsets relative to the clipboard origin, plus a source
tile-size snapshot, so pasting recomputes destination cells in the
*current* grid and never lands in surprising places after Scale/Grid.
"""

from __future__ import annotations

from pygame import Surface

from .document import Document
from .selection import Selection


class Clipboard:
    __slots__ = ("tiles", "tile_size", "origin_local")

    def __init__(self) -> None:
        self.tiles: list[tuple[int, int, Surface]] = []
        self.tile_size: tuple[int, int] = (0, 0)
        self.origin_local: tuple[int, int] = (0, 0)

    def __len__(self) -> int:
        return len(self.tiles)

    @property
    def is_empty(self) -> bool:
        return not self.tiles

    def clear(self) -> None:
        self.tiles = []
        self.tile_size = (0, 0)
        self.origin_local = (0, 0)

    def copy_from_selection(self, doc: Document, selection: Selection) -> bool:
        """Snapshot the selected cells as (dx, dy, surface) tiles.

        Returns True if anything was copied.
        """
        cells = selection.sorted_cells()
        if not cells or not doc.surface:
            self.clear()
            return False
        min_col = min(c for c, _ in cells)
        min_row = min(r for _, r in cells)
        self.tiles = [
            (col - min_col, row - min_row, doc.extract_tile(col, row))
            for col, row in cells
        ]
        self.tile_size = doc.tile_size
        self.origin_local = (min_col * doc.tw, min_row * doc.th)
        return True

    def covered_cells(self, target_col: int, target_row: int) -> list[tuple[int, int]]:
        """Cell list the clipboard would occupy anchored at a target cell."""
        return [
            (target_col + dx, target_row + dy)
            for dx, dy, _ in self.tiles
        ]

    def paste_surfaces(self, target_col: int, target_row: int) -> list[tuple[int, int, Surface]]:
        """(col, row, surface) placements anchored at a target cell."""
        return [
            (target_col + dx, target_row + dy, surf)
            for dx, dy, surf in self.tiles
        ]

    def bounds_cells(self) -> tuple[int, int]:
        """Bounding box (ncols, nrows) of the clipboard tiles."""
        if not self.tiles:
            return (0, 0)
        return (max(dx for dx, _, _ in self.tiles) + 1, max(dy for _, dy, _ in self.tiles) + 1)
