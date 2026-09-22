"""Commands — every document mutation goes through a Command.

Commands hold **data, never events** (`MoveCommand(offset)`). Each command
snapshots the document (canvas + regions) and the selection before and
after; undo/redo restores state so the "what was selected" is remembered.
"""

from __future__ import annotations

import pygame
from pygame import Rect, Surface

from .document import Document, Region
from .selection import Selection


class Command:
    name: str = "Edit"

    def apply(self, doc: Document, selection: Selection) -> None:
        """Run the mutation; captures before/after snapshots."""
        self.before_doc = doc.snapshot()
        self.before_selection = selection.sorted_cells()
        self._do(doc, selection)
        self.after_doc = doc.snapshot()
        self.after_selection = selection.sorted_cells()

    def undo(self, doc: Document, selection: Selection) -> None:
        doc.restore(self.before_doc)
        selection.replace(self.before_selection)

    def redo(self, doc: Document, selection: Selection) -> None:
        doc.restore(self.after_doc)
        selection.replace(self.after_selection)

    def _do(self, doc: Document, selection: Selection) -> None:
        raise NotImplementedError


class MoveCommand(Command):
    """Carry selected tiles to a grid offset (dc, dr)."""

    name = "Move"

    def __init__(self, cells: list[tuple[int, int]], offset_col: int, offset_row: int):
        self.cells = list(cells)
        self.dc = int(offset_col)
        self.dr = int(offset_row)

    def _do(self, doc: Document, selection: Selection) -> None:
        placements: dict[tuple[int, int], pygame.Surface] = {}
        for col, row in self.cells:
            placements[(col + self.dc, row + self.dr)] = doc.extract_tile(col, row)
        doc.clear_tiles(self.cells)
        # write_tile auto-grows the canvas and shifts the origin for negative
        # destinations — no placement is ever dropped, selection stays intact
        for (col, row), surf in placements.items():
            doc.write_tile(col, row, surf)
        selection.replace(list(placements.keys()))


class PasteCommand(Command):
    """Write clipboard tiles anchored at a target cell."""

    name = "Paste"

    def __init__(
        self,
        target_col: int,
        target_row: int,
        tiles: list[tuple[int, int, pygame.Surface]],
        src_tile_size: tuple[int, int] | None = None,
    ):
        self.target = (int(target_col), int(target_row))
        self.tiles = list(tiles)
        self.src_tile_size = src_tile_size

    def _do(self, doc: Document, selection: Selection) -> None:
        surfs = self.tiles
        if (
            self.src_tile_size
            and self.src_tile_size != doc.tile_size
            and self.src_tile_size[0] > 0
            and self.src_tile_size[1] > 0
        ):
            # grid changed since the copy: retile surfaces to the
            # current cell size instead of overflowing neighbors
            sx = doc.tw / self.src_tile_size[0]
            sy = doc.th / self.src_tile_size[1]
            scaled = []
            for dx, dy, surf in self.tiles:
                w, h = max(1, round(surf.get_width() * sx)), max(1, round(surf.get_height() * sy))
                scaled.append((dx, dy, pygame.transform.scale(surf, (w, h))))
            surfs = scaled
        placements = [(self.target[0] + dx, self.target[1] + dy, surf) for dx, dy, surf in surfs]
        # write_tile auto-grows the canvas / shifts the origin as needed
        for col, row, surf in placements:
            doc.write_tile(col, row, surf)
        selection.replace([(col, row) for col, row, _ in placements])


class ClearCommand(Command):
    """Make the given cells transparent."""

    name = "Clear"

    def __init__(self, cells: list[tuple[int, int]]):
        self.cells = list(cells)

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.clear_tiles(self.cells)
        # auto-trim: cleared-away edges collapse so no empty gap remains.
        # write_tile/paste paths re-expand on demand; undo restores via snapshot.
        doc.trim_to_content()
        selection.replace([], anchor=None)


class FlipCommand(Command):
    """Mirror the selected bounding box horizontally and/or vertically."""

    name = "Flip"

    def __init__(self, cells: list[tuple[int, int]], flip_x: bool, flip_y: bool):
        self.cells = list(cells)
        self.flip_x = bool(flip_x)
        self.flip_y = bool(flip_y)

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.flip_tiles(self.cells, self.flip_x, self.flip_y)


class CropCommand(Command):
    """Shrink the canvas to its content (manual autocrop)."""

    name = "Crop"

    def __init__(self):
        self.changed = False

    def _do(self, doc: Document, selection: Selection) -> None:
        self.changed = doc.trim_to_content()
        if not self.changed:
            return
        selection.replace([(c, r) for c, r in selection.sorted_cells() if doc.is_valid_cell(c, r)])


class ScaleCommand(Command):
    """Scale the whole canvas by factor; tile size unchanged."""

    name = "Scale"

    def __init__(self, factor: float):
        self.factor = float(factor)

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.scale(self.factor)
        selection.replace([], anchor=None)


class GridResizeCommand(Command):
    """Change the tile size (grid) without resizing the canvas."""

    name = "Grid Resize"

    def __init__(self, tile_size: tuple[int, int]):
        self.tile_size = (int(tile_size[0]), int(tile_size[1]))

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.set_tile_size(self.tile_size)


class AppendSheetCommand(Command):
    """Stack an imported sheet below (or right of) the existing canvas.

    The imported file names are part of the operation: they are captured
    into the command so undo removes them again and redo re-adds them,
    keeping ``doc.sheets`` in lockstep with the canvas across the cycle.
    """

    name = "Import Sheets"

    def __init__(self, sheet: pygame.Surface, names: list[str], horizontal: bool = False):
        self.sheet = sheet
        self.names = list(names)
        self.horizontal = bool(horizontal)
        self._prev_sheets: list[str] | None = None

    def apply(self, doc: Document, selection: Selection) -> None:
        self._prev_sheets = list(doc.sheets)
        super().apply(doc, selection)

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.append_sheet(self.sheet, horizontal=self.horizontal)
        if self.names:
            doc.sheets.extend(self.names)
        selection.replace([], anchor=None)

    def undo(self, doc: Document, selection: Selection) -> None:
        super().undo(doc, selection)
        if self._prev_sheets is not None:
            doc.sheets = list(self._prev_sheets)

    def redo(self, doc: Document, selection: Selection) -> None:
        super().redo(doc, selection)
        if self.names:
            doc.sheets.extend(self.names)


class PixelMoveCommand(Command):
    """Translate a pixel block; source auto-fills transparent.

    Records the pre-move source rect and the applied delta. Undo/redo
    restores snapshots like every other command, so negative-origin
    growth replays exactly.
    """

    name = "Move Pixels"

    def __init__(self, src_rect: Rect, dx: int, dy: int):
        self.src_rect = Rect(src_rect)
        self.dx = int(dx)
        self.dy = int(dy)

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.move_pixels(self.src_rect, self.dx, self.dy)
        selection.replace([], anchor=None)


class PixelClearCommand(Command):
    """Clear a world-px rect to transparency."""

    name = "Clear Pixels"

    def __init__(self, rect: Rect):
        self.rect = Rect(rect)

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.clear_rect(self.rect)
        selection.replace([], anchor=None)


class PixelStampCommand(Command):
    """Stamp a pixel surface at a world-px position (free paste).

    Canvas growth (incl. negative-origin shifts) is inherited from
    ``blit_surface``; undo/redo restores snapshots like all commands.
    """

    name = "Stamp Pixels"

    def __init__(self, pos: tuple[int, int], surface: Surface):
        self.pos = (int(pos[0]), int(pos[1]))
        self.surface = surface.copy() if surface is not None else None

    def _do(self, doc: Document, selection: Selection) -> None:
        if not doc.has_canvas or self.surface is None:
            return
        doc.blit_surface(self.surface, self.pos)
        selection.replace([], anchor=None)


class PixelMirrorCommand(Command):
    """Stamp a flipped copy of a pixel block abutting its own edge.

    The stamped destination is recorded for chaining (the tool selects
    the copy so repeated mirrors extend outward). Undo/redo restores
    snapshots like all commands.
    """

    name = "Mirror Pixels"

    def __init__(self, src_rect: Rect, axis: str, side: int = 1):
        self.src_rect = Rect(src_rect)
        self.axis = "v" if axis == "v" else "h"
        self.side = -1 if side < 0 else 1
        self.dest: Rect | None = None

    def _do(self, doc: Document, selection: Selection) -> None:
        self.dest = doc.mirror_pixels(self.src_rect, self.axis, self.side)
        selection.replace([], anchor=None)


class PixelScaleCommand(Command):
    """Resample a pixel block into a new rect (free stretch).

    Records the destination for chaining; undo/redo restores snapshots
    like all commands.
    """

    name = "Scale Pixels"

    def __init__(self, src_rect: Rect, dest_rect: Rect):
        self.src_rect = Rect(src_rect)
        self.dest_rect = Rect(
            int(dest_rect.x),
            int(dest_rect.y),
            max(1, int(dest_rect.w)),
            max(1, int(dest_rect.h)),
        )
        self.dest: Rect | None = None

    def _do(self, doc: Document, selection: Selection) -> None:
        self.dest = doc.scale_pixels(self.src_rect, self.dest_rect)
        selection.replace([], anchor=None)


class RegionAddCommand(Command):
    name = "Add Region"

    def __init__(self, region: Region):
        self.region = region

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.add_region(self.region)


class RegionMoveCommand(Command):
    name = "Move Region"

    def __init__(self, region_id: str, dx: float, dy: float):
        self.region_id = region_id
        self.dx = float(dx)
        self.dy = float(dy)

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.move_region(self.region_id, self.dx, self.dy)


class RegionResizeCommand(Command):
    name = "Resize Region"

    def __init__(self, region_id: str, rect: list[float] | tuple[float, float, float, float]):
        self.region_id = region_id
        self.new_rect = [float(v) for v in rect]

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.resize_region(self.region_id, self.new_rect)


class RegionDeleteCommand(Command):
    name = "Delete Region"

    def __init__(self, region_id: str):
        self.region_id = region_id

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.delete_region(self.region_id)


class RegionRenameCommand(Command):
    name = "Rename Region"

    def __init__(self, region_id: str, new_name: str):
        self.region_id = region_id
        self.new_name = str(new_name)

    def _do(self, doc: Document, selection: Selection) -> None:
        doc.rename_region(self.region_id, self.new_name)


class TextStampCommand(Command):
    """Bake a text surface onto the canvas at a world-space rect.

    Text is rendered at image-pixel scale (respects zoom) and then
    blitted; rotation is baked into the source surface before blit.
    """

    name = "Stamp Text"

    def __init__(
        self,
        rect: tuple[float, float, float, float],
        text_surface: pygame.Surface,
        angle: float = 0.0,
    ):
        self.rect = tuple(float(v) for v in rect)
        # store a copy so redo is deterministic
        self.text_surface = text_surface.copy() if text_surface else None
        self.angle = float(angle)

    def _do(self, doc: Document, selection: Selection) -> None:
        if not doc.has_canvas or self.text_surface is None:
            return
        surf = self.text_surface
        if abs(self.angle) > 0.01:
            surf = pygame.transform.rotate(surf, self.angle)
        x, y, w, h = self.rect
        # center the (possibly rotated) surface in the original rect
        sw, sh = surf.get_size()
        cx = x + w / 2.0
        cy = y + h / 2.0
        blit_x = int(round(cx - sw / 2.0))
        blit_y = int(round(cy - sh / 2.0))
        doc.blit_surface(surf, (blit_x, blit_y))
        selection.replace([], anchor=None)


class CommandStack:
    """Bounded undo/redo stack. Commands hold data, not events."""

    def __init__(self, limit: int = 50):
        self.limit = limit
        self._undo: list[Command] = []
        self._redo: list[Command] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def push(self, command: Command, doc: Document, selection: Selection) -> None:
        command.apply(doc, selection)
        self._undo.append(command)
        if len(self._undo) > self.limit:
            self._undo.pop(0)
        self._redo.clear()

    def discard_last(self) -> bool:
        """Drop the most recently pushed command (for no-op pushes).

        Note: the redo stack cleared by ``push`` is not restored — use
        only for idempotent no-ops (e.g. an already-tight crop) where
        redo loss is acceptable.
        """
        if not self._undo:
            return False
        self._undo.pop()
        return True

    def undo(self, doc: Document, selection: Selection) -> bool:
        if not self._undo:
            return False
        command = self._undo.pop()
        command.undo(doc, selection)
        self._redo.append(command)
        return True

    def redo(self, doc: Document, selection: Selection) -> bool:
        if not self._redo:
            return False
        command = self._redo.pop()
        command.redo(doc, selection)
        self._undo.append(command)
        return True

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def peek_undo(self) -> Command | None:
        return self._undo[-1] if self._undo else None

    def peek_redo(self) -> Command | None:
        return self._redo[-1] if self._redo else None

    def undo_name(self) -> str:
        cmd = self.peek_undo()
        return cmd.name if cmd else ""

    def redo_name(self) -> str:
        cmd = self.peek_redo()
        return cmd.name if cmd else ""
