"""Tools — one active interaction state machine at a time.

Each tool has exactly `enter()`, `exit()`, `handle_event()`, `draw_overlay()`
and nothing else. Tools read the cursor, maintain temporary interaction state
and build Commands from **data** (never events). They never mutate the
Document directly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame
from pygame import Rect, Surface

from widgets.input import InputBox
from widgets.ui.theme import COLORS, FONTS, SHAPE

from .camera import Camera
from .clipboard import Clipboard
from .commands import (
    ClearCommand,
    CommandStack,
    MoveCommand,
    PasteCommand,
    RegionAddCommand,
    RegionDeleteCommand,
    RegionMoveCommand,
    RegionRenameCommand,
    RegionResizeCommand,
    TextStampCommand,
)
from .document import Document, Region
from .overlays import (
    CANVAS_BG,
    draw_alpha_fill,
    draw_dashed_border,
    draw_handles,
    draw_region_shape,
    ghost_tiles,
    handle_at,
    screen_rect_for,
)
from .selection import Selection
from .viewport import Viewport


@dataclass
class ToolContext:
    doc: Document
    selection: Selection
    camera: Camera
    viewport: Viewport
    clipboard: Clipboard
    commands: CommandStack
    status: Callable[[str, str], None]
    toast: Callable[[str], None]
    set_tool: Callable[[str], None]


MIN_SCREEN_PX = 8.0
HANDLE_SIZE = 8


class Tool:
    """Base tool — shared camera gesture handling only."""

    def __init__(self, ctx: ToolContext):
        self.ctx = ctx
        self._panning = False
        self._pan_start = (0, 0)

    def enter(self) -> None:
        pass

    def exit(self) -> None:
        pass

    def handle_event(self, event: pygame.event.Event) -> bool:
        return False

    def draw_overlay(self, screen: Surface) -> None:
        pass

    # -- shared camera gestures ---------------------------------------
    def _handle_view_events(self, event: pygame.event.Event) -> bool:
        camera = self.ctx.camera
        if event.type == pygame.MOUSEWHEEL:
            mods = pygame.key.get_mods()
            ctrl = bool(mods & (pygame.KMOD_CTRL | pygame.KMOD_META))
            if ctrl and event.y != 0:
                factor = 1.12 if event.y > 0 else 1 / 1.12
                camera.zoom_at(pygame.mouse.get_pos(), factor)
            else:
                if event.y != 0:
                    camera.pan(0, event.y * 30)
                if event.x != 0:
                    camera.pan(event.x * 30, 0)
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self._panning = True
            self._pan_start = event.pos
            return True
        if event.type == pygame.MOUSEMOTION and self._panning:
            camera.pan(
                event.pos[0] - self._pan_start[0],
                event.pos[1] - self._pan_start[1],
            )
            self._pan_start = event.pos
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self._panning = False
            return True
        return False

    def _handle_view_keys(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        camera = self.ctx.camera
        center = self.ctx.viewport.rect.center
        if event.key in (pygame.K_PLUS, pygame.K_EQUALS):
            camera.zoom_at(center, 1.25)
            return True
        if event.key == pygame.K_MINUS:
            camera.zoom_at(center, 1 / 1.25)
            return True
        if event.key == pygame.K_0:
            camera.reset()
            return True
        if event.key == pygame.K_f:
            if self.ctx.doc.has_canvas:
                camera.fit(self.ctx.doc.size, (self.ctx.viewport.rect.w, self.ctx.viewport.rect.h))
            return True
        return False


class SelectTool(Tool):
    """Grid-mode tool: click select, rubber-band, drag-move, keyboard edits."""

    overlay_kind = "selection"

    def __init__(self, ctx: ToolContext):
        super().__init__(ctx)
        self._mode = "idle"  # idle | marquee | move
        self._marquee_screen_start = (0, 0)
        self._marquee_screen_end = (0, 0)
        self._move_anchor: tuple[int, int] | None = None
        self._move_cells: list[tuple[int, int]] = []
        self._move_ghost: dict[tuple[int, int], Surface] = {}
        self._move_offset = (0, 0)
        self._hover_cell: tuple[int, int] | None = None

    def enter(self) -> None:
        if self.ctx.selection:
            self.ctx.status(f"Selection: {len(self.ctx.selection)} tiles", "")
        else:
            self.ctx.status("Ready", "")

    # -- interaction ---------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._handle_view_events(event):
            return True
        if self._handle_view_keys(event):
            return True

        if event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
            if self._mode == "move":
                self._update_move(event.pos)
            elif self._mode == "marquee":
                self._marquee_screen_end = event.pos
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._on_left_down(event.pos)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._mode == "move":
                self._commit_move()
                return True
            if self._mode == "marquee":
                self._commit_marquee()
                return True
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self._mode == "move":
                    self._cancel_move()
                    return True
                return False
            if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                if self.ctx.selection:
                    self.ctx.commands.push(
                        ClearCommand(self.ctx.selection.sorted_cells()),
                        self.ctx.doc,
                        self.ctx.selection,
                    )
                    self.ctx.toast("Cleared tiles")
                    self.ctx.status("Ready", "")
                return True
            if event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
                return self._handle_arrows(event.key)
        return False

    def _update_hover(self, pos: tuple[int, int]) -> None:
        cell = self.ctx.viewport.cell_at_screen(pos)
        self._hover_cell = cell if cell is not None and self.ctx.doc.is_valid_cell(*cell) else None
        if self._mode == "idle":
            if self._hover_cell:
                self.ctx.status("Ready", f"({self._hover_cell[0]}, {self._hover_cell[1]})")
            else:
                self.ctx.status("Ready", "")

    def _handle_arrows(self, key: int) -> bool:
        dc = dr = 0
        if key == pygame.K_LEFT:
            dc = -1
        elif key == pygame.K_RIGHT:
            dc = 1
        elif key == pygame.K_UP:
            dr = -1
        elif key == pygame.K_DOWN:
            dr = 1
        if self.ctx.selection:
            self.ctx.commands.push(
                MoveCommand(self.ctx.selection.sorted_cells(), dc, dr),
                self.ctx.doc,
                self.ctx.selection,
            )
            return True
        self.ctx.camera.pan(
            -dc * self.ctx.doc.tw * self.ctx.camera.zoom,
            -dr * self.ctx.doc.th * self.ctx.camera.zoom,
        )
        return True

    # -- press / move / release ---------------------------------------------
    def _on_left_down(self, pos: tuple[int, int]) -> None:
        cell = self.ctx.viewport.cell_at_screen(pos)
        ctrl = pygame.key.get_mods() & (pygame.KMOD_CTRL | pygame.KMOD_META)
        if ctrl:
            # ctrl+drag rubber-bands from anywhere; a click (no drag) toggles
            self._mode = "marquee"
            self._marquee_screen_start = pos
            self._marquee_screen_end = pos
            return
        if cell is not None and self.ctx.doc.is_valid_cell(*cell):
            if self.ctx.selection.contains(*cell):
                self._begin_move(cell)
                return
            self.ctx.selection.replace([cell])
            self.ctx.status(f"Selection: {len(self.ctx.selection)} tile{'s' if len(self.ctx.selection) != 1 else ''}", "")
            return
        self.ctx.selection.clear()
        self.ctx.status("Ready", "")
        self._hover_cell = None

    def _begin_move(self, anchor: tuple[int, int]) -> None:
        self._mode = "move"
        self._move_anchor = anchor
        self._move_cells = self.ctx.selection.sorted_cells()
        self._move_ghost = {c: self.ctx.doc.extract_tile(*c) for c in self._move_cells}
        self._move_offset = (0, 0)
        self.ctx.status(f"Move {len(self._move_cells)} tiles", "Esc to cancel")

    def _update_move(self, pos: tuple[int, int]) -> None:
        cell = self.ctx.viewport.cell_at_screen_unbounded(pos)
        if cell is None or self._move_anchor is None:
            return
        self._move_offset = (cell[0] - self._move_anchor[0], cell[1] - self._move_anchor[1])

    def _commit_move(self) -> None:
        dc, dr = self._move_offset
        if dc != 0 or dr != 0:
            self.ctx.commands.push(MoveCommand(self._move_cells, dc, dr), self.ctx.doc, self.ctx.selection)
            self.ctx.toast(f"Moved {len(self._move_cells)} tiles")
        self._mode = "idle"
        if self.ctx.selection:
            self.ctx.status(f"Selection: {len(self.ctx.selection)} tiles", "")

    def _cancel_move(self) -> None:
        self._mode = "idle"
        self.ctx.status("Ready", "")
        self.ctx.toast("Move canceled")

    def _commit_marquee(self) -> None:
        x0, y0 = self._marquee_screen_start
        x1, y1 = self._marquee_screen_end
        if abs(x1 - x0) <= 3 and abs(y1 - y0) <= 3:
            # it was a ctrl-click, not a drag: toggle the cell under the cursor
            cell = self.ctx.viewport.cell_at_screen((x1, y1))
            if cell is not None and self.ctx.doc.is_valid_cell(*cell):
                self.ctx.selection.toggle(*cell)
            self._mode = "idle"
            return
        wx0, wy0 = self.ctx.viewport.screen_to_world(x0, y0)
        wx1, wy1 = self.ctx.viewport.screen_to_world(x1, y1)
        c0, r0 = (
            int(min(wx0, wx1) // self.ctx.doc.tw) + self.ctx.doc.origin_col,
            int(min(wy0, wy1) // self.ctx.doc.th) + self.ctx.doc.origin_row,
        )
        c1, r1 = (
            int(max(wx0, wx1) // self.ctx.doc.tw) + self.ctx.doc.origin_col,
            int(max(wy0, wy1) // self.ctx.doc.th) + self.ctx.doc.origin_row,
        )
        cells = []
        for col in range(c0, c1 + 1):
            for row in range(r0, r1 + 1):
                if self.ctx.doc.is_valid_cell(col, row):
                    cells.append((col, row))
        self.ctx.selection.replace(cells)
        self._mode = "idle"
        self.ctx.status(f"Selection: {len(cells)} tiles", "")

    # -- overlay --------------------------------------------------------------
    def draw_overlay(self, screen: Surface) -> None:
        if self._mode == "move":
            self._draw_move_overlay(screen)
        elif self._mode == "marquee":
            self._draw_marquee_overlay(screen)
        elif self._mode == "idle" and self._hover_cell:
            rect = self.ctx.viewport.cell_screen_rect(*self._hover_cell)
            draw_alpha_fill(screen, rect, (255, 255, 255), 14)

    def _draw_move_overlay(self, screen: Surface) -> None:
        dc, dr = self._move_offset
        for col, row in self._move_cells:
            src_rect = self.ctx.viewport.cell_screen_rect(col, row)
            draw_alpha_fill(screen, src_rect, CANVAS_BG, 200)
        placements = [
            (col + dc, row + dr, surf)
            for (col, row), surf in self._move_ghost.items()
        ]
        ghost_tiles(screen, placements, self.ctx.doc, self.ctx.camera, alpha=200)

    def _draw_marquee_overlay(self, screen: Surface) -> None:
        x0 = min(self._marquee_screen_start[0], self._marquee_screen_end[0])
        y0 = min(self._marquee_screen_start[1], self._marquee_screen_end[1])
        x1 = max(self._marquee_screen_start[0], self._marquee_screen_end[0])
        y1 = max(self._marquee_screen_start[1], self._marquee_screen_end[1])
        rect = Rect(x0, y0, x1 - x0, y1 - y0)
        draw_alpha_fill(screen, rect, (80, 120, 200), 40)
        draw_dashed_border(screen, rect, (140, 180, 240))


class PasteTool(Tool):
    """Armed by copy/paste; carries a live pixel ghost and places on click."""

    overlay_kind = "paste"

    def __init__(self, ctx: ToolContext):
        super().__init__(ctx)
        self._target: tuple[int, int] = (0, 0)

    def enter(self) -> None:
        self.ctx.status("Paste · LMB to place", "Esc/RMB to cancel")

    def exit(self) -> None:
        pass

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._handle_view_events(event):
            return True
        if event.type == pygame.MOUSEMOTION:
            cell = self.ctx.viewport.cell_at_screen(event.pos)
            if cell is not None:
                self._target = cell
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            cell = self.ctx.viewport.cell_at_screen(event.pos)
            if cell is None or not self.ctx.doc.is_valid_cell(*cell):
                self.cancel()
            else:
                self._target = cell
                self._place()
                self.ctx.set_tool("select")
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self.cancel()
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.cancel()
            return True
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
            self._move_target(event.key)
            return True
        return False

    def _move_target(self, key: int) -> None:
        dc = dr = 0
        if key == pygame.K_LEFT:
            dc = -1
        elif key == pygame.K_RIGHT:
            dc = 1
        elif key == pygame.K_UP:
            dr = -1
        elif key == pygame.K_DOWN:
            dr = 1
        self._target = (self._target[0] + dc, self._target[1] + dr)

    def _place(self) -> None:
        self.ctx.commands.push(
            PasteCommand(
                self._target[0],
                self._target[1],
                self.ctx.clipboard.tiles,
            ),
            self.ctx.doc,
            self.ctx.selection,
        )
        self.ctx.toast("Pasted")

    def cancel(self) -> None:
        self.ctx.toast("Paste canceled")
        self.ctx.set_tool("select")

    def draw_overlay(self, screen: Surface) -> None:
        if self.ctx.clipboard.is_empty:
            return
        covered = self.ctx.clipboard.covered_cells(self._target[0], self._target[1])
        if not covered:
            return
        c0 = min(c for c, _ in covered)
        r0 = min(r for _, r in covered)
        c1 = max(c for c, _ in covered)
        r1 = max(r for _, r in covered)
        start_rect = self.ctx.doc.tile_rect(c0, r0)
        end_rect = self.ctx.doc.tile_rect(c1, r1)
        sx, sy = self.ctx.camera.world_to_screen(start_rect.x, start_rect.y)
        ex, ey = self.ctx.camera.world_to_screen(end_rect.right, end_rect.bottom)
        rect = Rect(round(sx), round(sy), round(ex - sx), round(ey - sy))
        draw_alpha_fill(screen, rect, (80, 200, 120), 24)
        draw_dashed_border(screen, rect, (90, 220, 130))
        ghost_tiles(
            screen,
            self.ctx.clipboard.paste_surfaces(self._target[0], self._target[1]),
            self.ctx.doc,
            self.ctx.camera,
            alpha=180,
        )


def _screen_rect_for_region(camera: Camera, region: Region) -> Rect:
    return screen_rect_for(camera, region.x, region.y, region.w, region.h)


class RegionTool(Tool):
    """Region editing: create / select / move / resize / delete / rename."""

    overlay_kind = "regions"

    def __init__(self, ctx: ToolContext):
        super().__init__(ctx)
        self.selected_id: str | None = None
        self._hover_id: str | None = None
        self._drag: str | None = None  # create | move | resize
        self._press_rect: list[float] = [0.0, 0.0, 0.0, 0.0]
        self._press_world: tuple[float, float] = (0.0, 0.0)
        self._pending_rect: list[float] = [0.0, 0.0, 0.0, 0.0]
        self._handle: str | None = None
        self._editing_id: str | None = None
        self._rename_input: InputBox | None = None
        self._hover_handle: str | None = None

    def enter(self) -> None:
        self.ctx.status("Region mode — drag to draw", "F2 rename · Del delete")
        if not self.ctx.doc.has_canvas:
            self.ctx.toast("Load a spritesheet first")

    def exit(self) -> None:
        self._drag = None
        self._end_rename()

    # -- helpers -------------------------------------------------------------
    def _selected_region(self) -> Region | None:
        return self.ctx.doc.region_by_id(self.selected_id) if self.selected_id else None

    def _region_at(self, pos: tuple[int, int]) -> Region | None:
        for region in sorted(self.ctx.doc.regions, key=lambda r: -(r.w * r.h)):
            rect = _screen_rect_for_region(self.ctx.camera, region)
            if rect.inflate(8, 8).collidepoint(pos):
                return region
        return None

    def _min_world(self) -> float:
        return MIN_SCREEN_PX / self.ctx.camera.zoom

    def _clamp_to_doc(self, rect: list[float]) -> list[float]:
        w, h = self.ctx.doc.size
        x = max(0.0, rect[0])
        y = max(0.0, rect[1])
        rw = rect[2]
        rh = rect[3]
        rw = max(0.0, min(rw, w - x))
        rh = max(0.0, min(rh, h - y))
        return [x, y, rw, rh]

    def _resize_rect(self, handle: str, wx: float, wy: float) -> list[float]:
        x0, y0, w0, h0 = self._press_rect
        x, y, w, h = x0, y0, w0, h0
        min_w = min(self._min_world(), w0)
        min_h = min(self._min_world(), h0)
        if "l" in handle:
            x = min(max(wx, 0.0), x0 + w0 - min_w)
            w = x0 + w0 - x
        if "r" in handle:
            w = max(wx - x0, min_w)
            if x0 + w > self.doc.size[0]:
                w = self.doc.size[0] - x0
        if "t" in handle:
            y = min(max(wy, 0.0), y0 + h0 - min_h)
            h = y0 + h0 - y
        if "b" in handle:
            h = max(wy - y0, min_h)
            if y0 + h > self.doc.size[1]:
                h = self.doc.size[1] - y0
        return [x, y, w, h]

    # -- interaction ---------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._handle_view_events(event):
            return True
        if self._editing_id is not None:
            return self._handle_rename(event)
        if self._handle_view_keys(event):
            return True

        if event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
            if self._drag == "create":
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                self._pending_rect = self._clamp_to_doc(
                    [self._press_world[0], self._press_world[1], wx - self._press_world[0], wy - self._press_world[1]]
                )
                self._pending_rect = self._normalize(self._pending_rect)
            elif self._drag == "move":
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                dx = wx - self._press_world[0]
                dy = wy - self._press_world[1]
                x0, y0, w0, h0 = self._press_rect
                new_x = max(0.0, min(x0 + dx, self.doc.size[0] - w0))
                new_y = max(0.0, min(y0 + dy, self.doc.size[1] - h0))
                self._pending_rect = [new_x, new_y, w0, h0]
            elif self._drag == "resize":
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                self._pending_rect = self._clamp_to_doc(self._resize_rect(self._handle, wx, wy))
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._on_left_down(event.pos)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._on_left_up()
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and self._drag:
                self._cancel_drag()
                return True
            if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                return self._delete_selected()
            if event.key == pygame.K_F2:
                return self._start_rename(self.selected_id)
            if event.key == pygame.K_RETURN:
                return False
        return False

    def _update_hover(self, pos: tuple[int, int]) -> None:
        region = self._region_at(pos)
        self._hover_id = region.id if region else None
        if region is not None and region.id == self.selected_id:
            screen_rect = _screen_rect_for_region(self.ctx.camera, region)
            self._hover_handle = handle_at(screen_rect, pos, HANDLE_SIZE)
        else:
            self._hover_handle = None

    def _on_left_down(self, pos: tuple[int, int]) -> None:
        region = self._region_at(pos)
        if region is not None:
            if region.id == self.selected_id:
                screen_rect = _screen_rect_for_region(self.ctx.camera, region)
                handle = handle_at(screen_rect, pos, HANDLE_SIZE)
                if handle:
                    self._start_resize(region, handle, pos)
                    return
            self._start_move(region, pos)
            return
        self._start_create(pos)

    def _start_move(self, region: Region, pos: tuple[int, int]) -> None:
        self.selected_id = region.id
        self._drag = "move"
        self._press_rect = list(region.rect)
        self._pending_rect = list(region.rect)
        self._press_world = self.ctx.viewport.screen_to_world(*pos)
        self.ctx.status("Move region", "Release to commit")

    def _start_resize(self, region: Region, handle: str, pos: tuple[int, int]) -> None:
        self.selected_id = region.id
        self._drag = "resize"
        self._handle = handle
        self._press_rect = list(region.rect)
        self._pending_rect = list(region.rect)
        self._press_world = self.ctx.viewport.screen_to_world(*pos)
        self.ctx.status("Resize region", "Release to commit")

    def _start_create(self, pos: tuple[int, int]) -> None:
        if not self.doc.has_canvas:
            self.ctx.toast("Load a spritesheet first")
            return
        self.selected_id = None
        self._drag = "create"
        self._press_world = self.ctx.viewport.screen_to_world(*pos)
        self._pending_rect = [self._press_world[0], self._press_world[1], 0.0, 0.0]
        self.ctx.status("Region mode — drag to draw", "")

    @staticmethod
    def _normalize(rect: list[float]) -> list[float]:
        x, y, w, h = rect
        if w < 0:
            x += w
            w = -w
        if h < 0:
            y += h
            h = -h
        return [x, y, w, h]

    def _on_left_up(self) -> None:
        drag = self._drag
        self._drag = None
        if drag == "create":
            x, y, w, h = self._pending_rect
            min_world = self._min_world()
            if w < min_world or h < min_world:
                self.ctx.toast("Region too small")
            else:
                region = Region(id=Region.new_id(), rect=[x, y, w, h], name="")
                self.selected_id = region.id
                self.ctx.commands.push(RegionAddCommand(region), self.ctx.doc, self.ctx.selection)
                self.ctx.toast("Region added")
            self.ctx.status("Region mode — drag to draw", "F2 rename · Del delete")
        elif drag == "move":
            x0, y0, _, _ = self._press_rect
            x, y, _, _ = self._pending_rect
            if abs(x - x0) > 1e-6 or abs(y - y0) > 1e-6:
                self.ctx.commands.push(
                    RegionMoveCommand(self.selected_id, x - x0, y - y0),
                    self.ctx.doc,
                    self.ctx.selection,
                )
                self.ctx.toast("Region moved")
            else:
                self.ctx.status("Ready", "")
            self.ctx.status("Region mode — drag to draw", "F2 rename · Del delete")
        elif drag == "resize":
            if self._pending_rect != self._press_rect:
                self.ctx.commands.push(
                    RegionResizeCommand(self.selected_id, self._pending_rect),
                    self.ctx.doc,
                    self.ctx.selection,
                )
                self.ctx.toast("Region resized")
            else:
                self.ctx.status("Region mode — drag to draw", "F2 rename · Del delete")

    def _cancel_drag(self) -> None:
        self._drag = None
        self.ctx.status("Region mode — drag to draw", "F2 rename · Del delete")

    def _delete_selected(self) -> bool:
        if not self.selected_id:
            return False
        self.ctx.commands.push(RegionDeleteCommand(self.selected_id), self.ctx.doc, self.ctx.selection)
        self.selected_id = None
        self.ctx.toast("Region deleted")
        return True

    # -- rename ----------------------------------------------------------------
    def _start_rename(self, region_id: str | None) -> bool:
        region = self.ctx.doc.region_by_id(region_id) if region_id else None
        if region is None:
            return False
        self._editing_id = region_id
        self._rename_input = InputBox(Rect(0, 0, 160, 24), font=FONTS.get_font(15))
        self._rename_input.text = region.name
        self._rename_input.is_focused = True
        self.ctx.status("Rename region", "Enter to confirm · Esc to cancel")
        return True

    def _handle_rename(self, event: pygame.event.Event) -> bool:
        if self._rename_input is None:
            self._end_rename()
            return False
        if self._rename_input.handle_event(event):
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            name = self._rename_input.text.strip()
            self.ctx.commands.push(RegionRenameCommand(self._editing_id, name), self.ctx.doc, self.ctx.selection)
            self._end_rename()
            self.ctx.toast("Region renamed")
            return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._end_rename()
            return True
        return True

    def _end_rename(self) -> None:
        self._editing_id = None
        self._rename_input = None

    # -- overlay --------------------------------------------------------------
    def draw_overlay(self, screen: Surface) -> None:
        if not self.doc.has_canvas:
            return
        for region in self.ctx.doc.regions:
            if region.id == self.selected_id and self._drag in ("move", "resize"):
                continue  # pending rect drawn below
            draw_region_shape(
                screen,
                self.ctx.camera,
                region,
                selected=region.id == self.selected_id,
                hovered=region.id == self._hover_id,
            )
        selected = self._selected_region()
        if (selected is None or self._drag in ("move", "resize", "create")) and self._pending_rect and self._drag:
            rect = _screen_rect_for_region(self.ctx.camera, Region(id="pending", rect=self._pending_rect, name=""))
            draw_alpha_fill(screen, rect, (220, 180, 80), 24)
            draw_dashed_border(screen, rect, (240, 200, 100))
        if selected is not None and self._drag not in ("move", "resize", "create"):
            rect = _screen_rect_for_region(self.ctx.camera, selected)
            draw_handles(screen, rect, (220, 180, 80), HANDLE_SIZE, self._hover_handle)
        if self._editing_id is not None and self._rename_input is not None:
            region = self.ctx.doc.region_by_id(self._editing_id)
            if region:
                rrect = _screen_rect_for_region(self.ctx.camera, region)
                input_rect = Rect(
                    rrect.x,
                    rrect.y - 26,
                    max(160, self._rename_input.rect.w),
                    24,
                )
                self._rename_input.rect = input_rect
                self._rename_input.draw(screen)

    @property
    def doc(self) -> Document:
        return self.ctx.doc


# -- text ---------------------------------------------------------------

# flameshot-like palette: white, black, red, orange, yellow, green, blue, purple
_TEXT_FG_PALETTE: list[tuple[int, int, int]] = [
    (255, 255, 255),
    (20, 20, 22),
    (220, 60, 60),
    (255, 150, 40),
    (240, 220, 60),
    (80, 180, 90),
    (70, 120, 210),
    (160, 90, 210),
]
# bg: None = transparent (shown as checker), then same hues plus white/black
_TEXT_BG_PALETTE: list[tuple[int, int, int] | None] = [
    None,
    (255, 255, 255),
    (20, 20, 22),
    (220, 60, 60),
    (80, 180, 90),
    (70, 120, 210),
]

_ROT_HANDLE_R = 7
_SWATCH = 18
_SWATCH_GAP = 4
_PANEL_PAD = 6
_PANEL_H = 28
_INPUT_H = 26


def _font_for(size: int, bold: bool):
    from utils.font_manager import FontWeight as FW

    return FONTS.get_font(int(size), FW.BOLD if bold else FW.REGULAR)


def _wrap_lines(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
    """Greedy word-wrap to max_w; respects explicit newlines."""
    if not text:
        return [""]
    out: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            out.append("")
            continue
        words = paragraph.split(" ")
        cur = ""
        for w in words:
            test = w if not cur else cur + " " + w
            if font.size(test)[0] <= max_w:
                cur = test
            else:
                if cur:
                    out.append(cur)
                # single word longer than max_w — hard-break by chars
                if font.size(w)[0] > max_w:
                    chunk = ""
                    for ch in w:
                        if font.size(chunk + ch)[0] <= max_w:
                            chunk += ch
                        else:
                            if chunk:
                                out.append(chunk)
                            chunk = ch
                    cur = chunk
                else:
                    cur = w
        if cur or not out:
            out.append(cur)
    return out


def _render_text_surface(
    text: str,
    box_w: int,
    box_h: int,
    font_size: int,
    fg: tuple[int, int, int],
    bg: tuple[int, int, int] | None,
    bold: bool,
) -> Surface:
    """Raster surface at image-pixel scale (respects scale, no zoom factor)."""
    w = max(1, int(round(box_w)))
    h = max(1, int(round(box_h)))
    surf = Surface((w, h), pygame.SRCALPHA)
    if bg is not None:
        # opaque bg pill with small radius so label stands out
        pygame.draw.rect(surf, bg, surf.get_rect(), border_radius=SHAPE.radius_sm)
    else:
        surf.fill((0, 0, 0, 0))
    if not text:
        return surf
    font = _font_for(int(font_size), bold)
    pad = 4
    max_text_w = max(1, w - pad * 2)
    lines = _wrap_lines(text, font, max_text_w)
    line_h = font.get_height()
    # vertical center if lines shorter than box
    total_h = len(lines) * line_h
    y0 = max(pad, (h - total_h) // 2)
    for i, line in enumerate(lines):
        if not line:
            continue
        ls = font.render(line, True, fg)
        surf.blit(ls, (pad, y0 + i * line_h))
        if y0 + (i + 1) * line_h > h - pad:
            break
    return surf


class TextTool(Tool):
    """Flameshot-like freeform text: drag box → type → Enter to bake.

    Exclusive — while a draft exists the tool consumes LMB so grid/region
    interactions cannot interleave (mirrors flameshot's modal text behaviour).
    Rotation handle above the box bakes angle into the stamp.
    """

    overlay_kind = "text"

    def __init__(self, ctx: ToolContext):
        super().__init__(ctx)
        self._mode: str = "idle"  # idle | drafting | editing
        self._draft_rect: list[float] = [0.0, 0.0, 0.0, 0.0]
        self._press_world: tuple[float, float] = (0.0, 0.0)
        self._press_rect: list[float] = [0.0, 0.0, 0.0, 0.0]
        self._drag: str | None = None  # drafting | move | rotate
        self._rotate_start_angle: float = 0.0
        self._rotate_press_angle: float = 0.0

        self._fg: tuple[int, int, int] = (255, 255, 255)
        self._bg: tuple[int, int, int] | None = None  # default transparent per spec
        self._font_size: int = 18
        self._bold: bool = False
        self._angle: float = 0.0

        self._input = InputBox(Rect(0, 0, 160, _INPUT_H), font=FONTS.get_font(15))
        self._input.is_focused = False
        self._panel_rect: Rect | None = None
        self._swatch_rects_fg: list[Rect] = []
        self._swatch_rects_bg: list[Rect] = []
        self._btn_minus: Rect | None = None
        self._btn_plus: Rect | None = None
        self._btn_bold: Rect | None = None
        self._rot_handle_screen: tuple[int, int] | None = None
        self._hover_swatch: tuple[str, int] | None = None

    def enter(self) -> None:
        self._mode = "idle"
        self._drag = None
        self._angle = 0.0
        if not self.ctx.doc.has_canvas:
            self.ctx.toast("Load a spritesheet first")
            self.ctx.status("Text — load an image first", "")
        else:
            self.ctx.status("Text — drag to place label", "Enter commit · Esc cancel")

    def exit(self) -> None:
        self._drag = None
        self._mode = "idle"
        self._input.is_focused = False

    # -- helpers -------------------------------------------------------
    def _min_world(self) -> float:
        return MIN_SCREEN_PX / max(0.1, self.ctx.camera.zoom)

    def _screen_rect(self) -> Rect | None:
        if not self._draft_rect or (self._draft_rect[2] <= 0 and self._mode == "drafting"):
            return None
        x, y, w, h = self._draft_rect
        return screen_rect_for(self.ctx.camera, x, y, w, h)

    def _rotation_handle_screen_pos(self, srect: Rect) -> tuple[int, int]:
        return (srect.centerx, srect.y - 18)

    def _compute_panel_layout(self, srect: Rect) -> None:
        """Populate _panel_rect and swatch/button rects in screen space."""
        panel_w = (
            _PANEL_PAD * 2
            + len(_TEXT_FG_PALETTE) * (_SWATCH + _SWATCH_GAP)
            + 10
            + len(_TEXT_BG_PALETTE) * (_SWATCH + _SWATCH_GAP)
            + 10
            + 56  # - [size] +
            + 30  # B
        )
        panel_w = min(panel_w, self.ctx.viewport.rect.w - 10)
        panel_h = _PANEL_H + 6
        x = srect.centerx - panel_w // 2
        # try above the box (with rotation handle gap), else below
        y_above = srect.y - panel_h - 28
        y_below = srect.bottom + 10
        y = y_above if y_above >= self.ctx.viewport.content_rect.y else y_below
        x = max(self.ctx.viewport.rect.x + 4, min(x, self.ctx.viewport.rect.right - panel_w - 4))
        self._panel_rect = Rect(x, y, panel_w, panel_h)
        # layout inside
        cx = x + _PANEL_PAD
        cy = y + (panel_h - _SWATCH) // 2
        self._swatch_rects_fg = []
        for _ in _TEXT_FG_PALETTE:
            self._swatch_rects_fg.append(Rect(cx, cy, _SWATCH, _SWATCH))
            cx += _SWATCH + _SWATCH_GAP
        cx += 6
        self._swatch_rects_bg = []
        for _ in _TEXT_BG_PALETTE:
            self._swatch_rects_bg.append(Rect(cx, cy, _SWATCH, _SWATCH))
            cx += _SWATCH + _SWATCH_GAP
        cx += 6
        self._btn_minus = Rect(cx, cy, 22, _SWATCH)
        cx += 24
        # size label gap 10
        cx += 10
        self._btn_plus = Rect(cx, cy, 22, _SWATCH)
        cx += 24
        self._btn_bold = Rect(cx, cy, 26, _SWATCH)
        self._rot_handle_screen = self._rotation_handle_screen_pos(srect)

    def _hit_panel(self, pos: tuple[int, int]) -> str | None:
        if self._panel_rect and self._panel_rect.collidepoint(pos):
            return "panel"
        return None

    def _normalize_rect(self, r: list[float]) -> list[float]:
        x, y, w, h = r
        if w < 0:
            x += w
            w = -w
        if h < 0:
            y += h
            h = -h
        return [x, y, w, h]

    def _clamp_rect_to_doc(self, rect: list[float]) -> list[float]:
        if not self.ctx.doc.has_canvas:
            return rect
        dw, dh = self.ctx.doc.size
        # allow anywhere; expand canvas will handle positive overflow, but keep x/y >=0
        # and let _blit_surface grow. Minimal clamp: keep non-negative origin
        x, y, w, h = rect
        # don't force inside doc — free anywhere — just prevent negative size
        w = max(self._min_world(), w)
        h = max(self._min_world(), h)
        x = max(0.0, x)
        y = max(0.0, y)
        return [x, y, w, h]

    # -- commit --------------------------------------------------------
    def _commit(self) -> None:
        text = self._input.text
        if not text.strip():
            self.ctx.toast("Empty label — discarded")
            self._reset_to_idle()
            return
        x, y, w, h = self._draft_rect
        if w < self._min_world() or h < self._min_world():
            # auto-size from text if box too small
            font = _font_for(self._font_size, self._bold)
            tw = font.size(text)[0] + 8
            th = font.get_height() + 8
            w = max(w, float(tw))
            h = max(h, float(th))
            self._draft_rect[2] = w
            self._draft_rect[3] = h
        surf = _render_text_surface(text, w, h, self._font_size, self._fg, self._bg, self._bold)
        rect = tuple(self._draft_rect)
        self.ctx.commands.push(TextStampCommand(rect, surf, angle=self._angle), self.ctx.doc, self.ctx.selection)
        self.ctx.toast(f"Stamped '{text[:18]}'")
        self._reset_to_idle()

    def _reset_to_idle(self) -> None:
        self._mode = "idle"
        self._drag = None
        self._angle = 0.0
        self._draft_rect = [0.0, 0.0, 0.0, 0.0]
        self._input.text = ""
        self._input.is_focused = False
        self.ctx.status("Text — drag to place label", "Enter commit · Esc cancel")

    def _cancel(self) -> None:
        self._reset_to_idle()
        self.ctx.toast("Text canceled")

    # -- events --------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._handle_view_events(event):
            # panning handled; if we are editing, keep panel synced
            return True
        # keyboard: InputBox gets first chance when editing (so typing 't' doesn't toggle tool)
        if self._mode == "editing" and self._input.is_focused:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    self._commit()
                    return True
                if event.key == pygame.K_ESCAPE:
                    self._cancel()
                    return True
                # let InputBox consume typing/navigation
                if self._input.handle_event(event):
                    return True
                if event.key in (pygame.K_UP, pygame.K_DOWN):
                    return False

        if self._handle_view_keys(event):
            return True

        if event.type == pygame.MOUSEMOTION:
            if self._drag == "drafting":
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                self._draft_rect = self._normalize_rect(
                    [self._press_world[0], self._press_world[1], wx - self._press_world[0], wy - self._press_world[1]]
                )
                return True
            if self._drag == "move" and self._mode == "editing":
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                dx = wx - self._press_world[0]
                dy = wy - self._press_world[1]
                x0, y0, w0, h0 = self._press_rect
                self._draft_rect = [max(0.0, x0 + dx), max(0.0, y0 + dy), w0, h0]
                return True
            if self._drag == "rotate" and self._mode == "editing":
                srect = self._screen_rect()
                if srect:
                    cx, cy = srect.centerx, srect.centery
                    import math

                    ang = math.degrees(math.atan2(event.pos[1] - cy, event.pos[0] - cx))
                    # press orientation is the handle angle at press; keep delta
                    delta = ang - self._rotate_start_angle
                    self._angle = self._rotate_press_angle + delta
                    # snap to 15° when near
                    snap = round(self._angle / 15.0) * 15.0
                    if abs(self._angle - snap) < 4:
                        self._angle = snap
                return True
            # hover (for cursor feedback) — not essential
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # panel hit takes precedence when editing
            if self._mode == "editing" and self._panel_rect:
                # ensure layout up to date
                srect = self._screen_rect()
                if srect:
                    self._compute_panel_layout(srect)
                if self._panel_rect.collidepoint(event.pos):
                    # swatches / buttons — keep input focused so typing continues
                    self._input.is_focused = True
                    for i, r in enumerate(self._swatch_rects_fg):
                        if r.collidepoint(event.pos):
                            self._fg = _TEXT_FG_PALETTE[i]
                            return True
                    for i, r in enumerate(self._swatch_rects_bg):
                        if r.collidepoint(event.pos):
                            self._bg = _TEXT_BG_PALETTE[i]
                            return True
                    if self._btn_minus and self._btn_minus.collidepoint(event.pos):
                        self._font_size = max(8, self._font_size - 1)
                        return True
                    if self._btn_plus and self._btn_plus.collidepoint(event.pos):
                        self._font_size = min(64, self._font_size + 1)
                        return True
                    if self._btn_bold and self._btn_bold.collidepoint(event.pos):
                        self._bold = not self._bold
                        return True
                    return True
                # clicking the rotation handle
                if self._rot_handle_screen and ((event.pos[0] - self._rot_handle_screen[0]) ** 2 + (event.pos[1] - self._rot_handle_screen[1]) ** 2) <= (_ROT_HANDLE_R + 4) ** 2:
                    import math

                    srect2 = self._screen_rect()
                    if srect2:
                        cx, cy = srect2.centerx, srect2.centery
                        self._drag = "rotate"
                        self._rotate_press_angle = self._angle
                        self._rotate_start_angle = math.degrees(math.atan2(event.pos[1] - cy, event.pos[0] - cx))
                    return True
            # InputBox hit → keep focus and allow cursor placement (no commit)
            if self._mode == "editing" and self._input.rect.collidepoint(event.pos):
                self._input.handle_event(event)
                self._input.is_focused = True
                return True
            # rotation handle hit (even if panel not hit)
            if self._mode == "editing":
                srect = self._screen_rect()
                if srect:
                    hx, hy = self._rotation_handle_screen_pos(srect)
                    if (event.pos[0] - hx) ** 2 + (event.pos[1] - hy) ** 2 <= (_ROT_HANDLE_R + 6) ** 2:
                        import math

                        cx, cy = srect.centerx, srect.centery
                        self._drag = "rotate"
                        self._rotate_press_angle = self._angle
                        self._rotate_start_angle = math.degrees(math.atan2(event.pos[1] - cy, event.pos[0] - cx))
                        return True
                    if srect.collidepoint(event.pos):
                        # drag to move the box — keep input focused
                        self._input.is_focused = True
                        self._drag = "move"
                        self._press_world = self.ctx.viewport.screen_to_world(*event.pos)
                        self._press_rect = list(self._draft_rect)
                        return True
                    # click outside while editing → commit (flameshot behavior)
                    # panel already handled; InputBox handled above
                    if not (self._panel_rect and self._panel_rect.collidepoint(event.pos)):
                        self._commit()
                        return True
            # idle → start drafting
            if self._mode == "idle":
                if not self.ctx.doc.has_canvas:
                    self.ctx.toast("Load a spritesheet first")
                    return True
                self._mode = "drafting"
                self._drag = "drafting"
                self._press_world = self.ctx.viewport.screen_to_world(*event.pos)
                self._draft_rect = [self._press_world[0], self._press_world[1], 0.0, 0.0]
                self.ctx.status("Text — drag to size box, release to type", "")
                return True
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._drag == "drafting":
                self._drag = None
                # normalize and check size
                self._draft_rect = self._normalize_rect(self._draft_rect)
                if self._draft_rect[2] < self._min_world() or self._draft_rect[3] < self._min_world():
                    # too small → make a default box at click pos
                    self._draft_rect[2] = max(self._draft_rect[2], 120.0)
                    self._draft_rect[3] = max(self._draft_rect[3], 28.0)
                self._mode = "editing"
                self._input.text = ""
                self._input.is_focused = True
                # position input at bottom of box (screen) — updated in draw
                self.ctx.status("Text — type label", "Enter commit · Esc cancel · drag box/○ rotate")
                return True
            if self._drag in ("move", "rotate"):
                self._drag = None
                return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self._mode != "idle":
                    self._cancel()
                    return True
            if event.key == pygame.K_RETURN and self._mode == "editing":
                # already handled above when input focused; handle when not
                self._commit()
                return True
            # allow Esc to exit tool back to select via parent — not needed here
        return False

    # -- overlay -----------------------------------------------------
    def draw_overlay(self, screen: Surface) -> None:
        if not self.ctx.doc.has_canvas:
            return
        # drafting rect
        if self._mode == "drafting" and self._draft_rect[2] >= 0:
            r = screen_rect_for(self.ctx.camera, self._draft_rect[0], self._draft_rect[1], max(0.5, self._draft_rect[2]), max(0.5, self._draft_rect[3]))
            draw_alpha_fill(screen, r, (255, 220, 120), 22)
            draw_dashed_border(screen, r, (255, 230, 140))
            return
        if self._mode != "editing":
            return
        srect = self._screen_rect()
        if srect is None:
            return
        self._compute_panel_layout(srect)

        # text preview — render at image-pixel (box) scale, then scale to screen for overlay
        box_w, box_h = self._draft_rect[2], self._draft_rect[3]
        preview_src = _render_text_surface(
            self._input.text or " ",
            max(1, box_w),
            max(1, box_h),
            self._font_size,
            self._fg,
            self._bg,
            self._bold,
        )
        # scale to screen rect size (world*zoom)
        scaled = preview_src
        if preview_src.get_size() != (max(1, srect.w), max(1, srect.h)):
            try:
                scaled = pygame.transform.smoothscale(preview_src, (max(1, srect.w), max(1, srect.h)))
            except Exception:
                scaled = pygame.transform.scale(preview_src, (max(1, srect.w), max(1, srect.h)))
        if abs(self._angle) > 0.5:
            rotated = pygame.transform.rotate(scaled, self._angle)
            screen.blit(rotated, rotated.get_rect(center=srect.center))
        else:
            screen.blit(scaled, srect.topleft)

        # box border
        # when angle !=0, draw rotated border via polygon
        if abs(self._angle) > 0.5:
            import math

            cx, cy = srect.centerx, srect.centery
            w2, h2 = srect.w / 2.0, srect.h / 2.0
            ang = math.radians(self._angle)
            ca, sa = math.cos(ang), math.sin(ang)

            def rot(px, py):
                # rotate (-w2,-h2) etc around center
                rx = px * ca - py * sa
                ry = px * sa + py * ca
                return (cx + rx, cy + ry)

            pts = [rot(-w2, -h2), rot(w2, -h2), rot(w2, h2), rot(-w2, h2)]
            pygame.draw.lines(screen, (255, 230, 140), True, pts, 1)
        else:
            draw_dashed_border(screen, srect, (255, 230, 140))
            # inner fill hint when transparent
            if self._bg is None:
                draw_alpha_fill(screen, srect, (255, 255, 255), 6)

        # rotation handle
        hx, hy = self._rotation_handle_screen_pos(srect)
        self._rot_handle_screen = (hx, hy)
        pygame.draw.line(screen, (255, 230, 140), srect.center, (hx, hy), 1)
        pygame.draw.circle(screen, (40, 40, 44), (hx, hy), _ROT_HANDLE_R + 1)
        pygame.draw.circle(screen, (255, 230, 140), (hx, hy), _ROT_HANDLE_R)
        pygame.draw.circle(screen, COLORS.panel, (hx, hy), 2)
        if abs(self._angle) > 0.5:
            lbl = FONTS.get_small_font().render(f"{self._angle:.0f}°", True, COLORS.text)
            screen.blit(lbl, (hx + 10, hy - 7))

        # floating formatting panel
        if self._panel_rect:
            pygame.draw.rect(screen, COLORS.panel, self._panel_rect, border_radius=SHAPE.radius_sm)
            pygame.draw.rect(screen, COLORS.border, self._panel_rect, 1, border_radius=SHAPE.radius_sm)
            # fg swatches
            for i, r in enumerate(self._swatch_rects_fg):
                col = _TEXT_FG_PALETTE[i]
                pygame.draw.rect(screen, col, r, border_radius=3)
                pygame.draw.rect(screen, COLORS.border_soft, r, 1, border_radius=3)
                if col == self._fg:
                    pygame.draw.rect(screen, (255, 255, 255), r.inflate(4, 4), 2, border_radius=4)
                    pygame.draw.rect(screen, (0, 0, 0), r.inflate(4, 4), 1, border_radius=4)
            # separator
            sep_x = self._swatch_rects_fg[-1].right + 6 if self._swatch_rects_fg else self._panel_rect.x + 10
            pygame.draw.line(screen, COLORS.border_soft, (sep_x, self._panel_rect.y + 5), (sep_x, self._panel_rect.bottom - 5), 1)
            # bg swatches
            for i, r in enumerate(self._swatch_rects_bg):
                col = _TEXT_BG_PALETTE[i]
                if col is None:
                    # checker + cross for transparent
                    pygame.draw.rect(screen, (60, 60, 65), r, border_radius=3)
                    pygame.draw.rect(screen, (40, 40, 44), Rect(r.x, r.y, r.w // 2, r.h // 2), border_radius=2)
                    pygame.draw.rect(screen, (40, 40, 44), Rect(r.x + r.w // 2, r.y + r.h // 2, r.w // 2, r.h // 2), border_radius=2)
                    pygame.draw.line(screen, (200, 80, 80), r.topleft, r.bottomright, 2)
                else:
                    pygame.draw.rect(screen, col, r, border_radius=3)
                pygame.draw.rect(screen, COLORS.border_soft, r, 1, border_radius=3)
                is_sel = (col == self._bg) or (col is None and self._bg is None)
                if is_sel:
                    pygame.draw.rect(screen, (255, 255, 255), r.inflate(4, 4), 2, border_radius=4)
            # font size controls
            if self._btn_minus and self._btn_plus and self._btn_bold:
                for btn, label in [(self._btn_minus, "−"), (self._btn_plus, "+")]:
                    pygame.draw.rect(screen, COLORS.panel_alt, btn, border_radius=3)
                    pygame.draw.rect(screen, COLORS.border_soft, btn, 1, border_radius=3)
                    ts = FONTS.get_font(14).render(label, True, COLORS.text)
                    screen.blit(ts, ts.get_rect(center=btn.center))
                # size value between
                mid_x = (self._btn_minus.right + self._btn_plus.x) // 2
                sz_lbl = FONTS.get_small_font().render(str(self._font_size), True, COLORS.text)
                screen.blit(sz_lbl, sz_lbl.get_rect(center=(mid_x, self._panel_rect.centery)))
                # bold toggle
                bg_col = COLORS.accent if self._bold else COLORS.panel_alt
                border_col = COLORS.accent_active if self._bold else COLORS.border_soft
                txt_col = COLORS.text_on_accent if self._bold else COLORS.text
                pygame.draw.rect(screen, bg_col, self._btn_bold, border_radius=3)
                pygame.draw.rect(screen, border_col, self._btn_bold, 1, border_radius=3)
                b_lbl = FONTS.get_bold_font(13).render("B", True, txt_col)
                screen.blit(b_lbl, b_lbl.get_rect(center=self._btn_bold.center))

        # inline InputBox anchored to box bottom (screen)
        input_w = min(220, max(120, srect.w))
        irect = Rect(srect.x, srect.bottom + 4, input_w, _INPUT_H)
        # keep inside viewport
        if irect.right > self.ctx.viewport.rect.right - 4:
            irect.x = self.ctx.viewport.rect.right - irect.w - 4
        if irect.bottom > self.ctx.viewport.rect.bottom - 4:
            irect.y = srect.y - _INPUT_H - 4
        self._input.rect = irect
        self._input._update_content_rect()
        self._input.draw(screen)
        # hint when empty
        if not self._input.text:
            hint = FONTS.get_small_font().render("Label…  Enter ✓  Esc ✕", True, COLORS.text_muted)
            screen.blit(hint, (irect.x + 8, irect.y + 6))

