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
from widgets.ui.theme import FONTS

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
