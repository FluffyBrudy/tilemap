"""Selection model — the single source of truth for selected tiles.

Shared by every tool, command and the viewport. Tiles are stored as
(col, row) cell coordinates; document converts cell <-> linear index when
needed. No duplicated selection state anywhere.
"""

from __future__ import annotations

from collections.abc import Iterable


class Selection:
    __slots__ = ("_cells", "_anchor")

    def __init__(self) -> None:
        self._cells: set[tuple[int, int]] = set()
        self._anchor: tuple[int, int] | None = None

    # -- query ----------------------------------------------------------
    @property
    def cells(self) -> set[tuple[int, int]]:
        return self._cells

    @property
    def anchor(self) -> tuple[int, int] | None:
        return self._anchor

    @anchor.setter
    def anchor(self, cell: tuple[int, int] | None) -> None:
        self._anchor = cell

    def __len__(self) -> int:
        return len(self._cells)

    def __bool__(self) -> bool:
        return bool(self._cells)

    def has(self) -> bool:
        return bool(self._cells)

    def contains(self, col: int, row: int) -> bool:
        return (col, row) in self._cells

    def contains_index(self, idx: int, cols: int) -> bool:
        return (idx % cols, idx // cols) in self._cells

    def bounds(self) -> tuple[int, int, int, int] | None:
        """Return (min_col, min_row, max_col, max_row) or None if empty."""
        if not self._cells:
            return None
        cols = [c for c, _ in self._cells]
        rows = [r for _, r in self._cells]
        return (min(cols), min(rows), max(cols), max(rows))

    # -- mutation ------------------------------------------------------
    def clear(self) -> None:
        self._cells.clear()
        self._anchor = None

    def add(self, col: int, row: int) -> None:
        self._cells.add((col, row))

    def add_cell(self, cell: tuple[int, int]) -> None:
        self._cells.add(cell)

    def remove(self, col: int, row: int) -> None:
        self._cells.discard((col, row))

    def toggle(self, col: int, row: int) -> None:
        cell = (col, row)
        if cell in self._cells:
            self._cells.remove(cell)
        else:
            self._cells.add(cell)

    def replace(self, cells: Iterable[tuple[int, int]], anchor: tuple[int, int] | None = None) -> None:
        """Replace the whole selection with the given cell iterable."""
        self._cells = set(cells)
        if anchor is not None:
            self._anchor = anchor
        elif not self._cells:
            self._anchor = None

    def copy(self) -> Selection:
        other = Selection()
        other._cells = set(self._cells)
        other._anchor = self._anchor
        return other

    @classmethod
    def from_cells(cls, cells: Iterable[tuple[int, int]]) -> Selection:
        result = cls()
        result.replace(cells)
        return result

    def select_all(self, doc) -> None:
        """Select every cell of the canvas."""
        self._cells = {
            (col, row)
            for col in range(doc.origin_col, doc.origin_col + doc.cols)
            for row in range(doc.origin_row, doc.origin_row + doc.rows)
        }

    def sorted_cells(self) -> list[tuple[int, int]]:
        """Linearly-sorted cells (row-major) for snapshots/persistence."""
        return sorted(self._cells, key=lambda c: (c[1], c[0]))
