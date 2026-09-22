"""Active tool interaction. Tools build commands, never edit docs directly."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pygame
from pygame import Rect, Surface

from widgets.input import InputBox
from widgets.ui.theme import COLORS, FONTS, SHAPE
from utils.shortcuts import is_cmd_or_ctrl

from .camera import Camera
from .clipboard import Clipboard
from .commands import (
    ClearCommand,
    ColorReplaceCommand,
    CommandStack,
    MoveCommand,
    PasteCommand,
    PixelClearCommand,
    PixelMirrorCommand,
    PixelMoveCommand,
    PixelScaleCommand,
    PixelStampCommand,
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


    def __init__(self, ctx: ToolContext):
        self.ctx = ctx
        self._panning = False
        self._pan_start = (0, 0)

    def enter(self) -> None:
        pass

    def exit(self) -> None:
        # a switch/focus change between RMB-down and RMB-up must not
        # leave panning latched on forever
        self._panning = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        return False

    def draw_overlay(self, screen: Surface) -> None:
        pass

    def _handle_view_events(self, event: pygame.event.Event) -> bool:
        camera = self.ctx.camera
        if event.type == pygame.MOUSEWHEEL:
            mods = pygame.key.get_mods()
            ctrl = is_cmd_or_ctrl(mods)
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


    overlay_kind = "selection"

    def __init__(self, ctx: ToolContext):
        super().__init__(ctx)
        self._mode = "idle"
        self._marquee_screen_start = (0, 0)
        self._marquee_screen_end = (0, 0)
        self._move_anchor: tuple[int, int] | None = None
        self._move_cells: list[tuple[int, int]] = []
        self._move_ghost: dict[tuple[int, int], Surface] = {}
        self._move_offset = (0, 0)
        self._hover_cell: tuple[int, int] | None = None
        self._hover_screen: tuple[int, int] = (0, 0)
        self._hover_outside: str | None = None

    def enter(self) -> None:
        if self.ctx.selection:
            self.ctx.status(f"Selection: {len(self.ctx.selection)} tiles", "")
        else:
            self.ctx.status("Ready", "")

    def exit(self) -> None:
        super().exit()
        self._mode = "idle"
        self._move_anchor = None
        self._move_cells = []
        self._move_ghost = {}
        self._move_offset = (0, 0)

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
                if self._mode == "marquee":
                    self._mode = "idle"
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
        self._hover_screen = pos
        self._hover_outside = None
        if self._hover_cell is None and self.ctx.doc.has_canvas:
            wx, wy = self.ctx.viewport.screen_to_world(*pos)
            w, h = self.ctx.doc.size
            if wx < 0 or wy < 0:
                self._hover_outside = "blocked"
            elif wx >= w or wy >= h:
                self._hover_outside = "expand"
        if self._mode == "idle":
            if self._hover_cell:
                self.ctx.status("Ready", f"({self._hover_cell[0]}, {self._hover_cell[1]})")
            elif self._hover_outside == "blocked":
                self.ctx.status("Canvas edge — top/left blocked", "")
            elif self._hover_outside == "expand":
                self.ctx.status("Outside canvas — bottom/right expands", "")
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

    def _on_left_down(self, pos: tuple[int, int]) -> None:
        cell = self.ctx.viewport.cell_at_screen(pos)
        ctrl = is_cmd_or_ctrl(pygame.key.get_mods())
        if ctrl:

            self._mode = "marquee"
            self._marquee_screen_start = pos
            self._marquee_screen_end = pos
            return
        if cell is not None and self.ctx.doc.is_valid_cell(*cell):
            if self.ctx.selection.contains(*cell):
                self._begin_move(cell)
                return
            self.ctx.selection.replace([cell])
            self.ctx.status(
                f"Selection: {len(self.ctx.selection)} tile{'s' if len(self.ctx.selection) != 1 else ''}", ""
            )
            return
        self.ctx.selection.clear()
        self._update_hover(pos)
        if self._mode == "idle":
            if self._hover_outside == "blocked":
                self.ctx.status("Canvas edge — top/left blocked", "")
            elif self._hover_outside == "expand":
                self.ctx.status("Outside canvas — bottom/right expands", "")
            else:
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

    def draw_overlay(self, screen: Surface) -> None:
        if self._mode == "move":
            self._draw_move_overlay(screen)
        elif self._mode == "marquee":
            self._draw_marquee_overlay(screen)
        elif self._mode == "idle" and self._hover_cell:
            rect = self.ctx.viewport.cell_screen_rect(*self._hover_cell)
            draw_alpha_fill(screen, rect, (255, 255, 255), 14)
        elif self._mode == "idle" and self._hover_outside:
            color = (232, 184, 84) if self._hover_outside == "blocked" else COLORS.accent
            x, y = self._hover_screen
            marker = Rect(x - 9, y - 9, 18, 18)
            draw_dashed_border(screen, marker, color)

    def _draw_move_overlay(self, screen: Surface) -> None:
        dc, dr = self._move_offset
        for col, row in self._move_cells:
            src_rect = self.ctx.viewport.cell_screen_rect(col, row)
            draw_alpha_fill(screen, src_rect, CANVAS_BG, 200)
        placements = [(col + dc, row + dr, surf) for (col, row), surf in self._move_ghost.items()]
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


    overlay_kind = "paste"

    def __init__(self, ctx: ToolContext):
        super().__init__(ctx)
        self._target: tuple[int, int] = (0, 0)

    def enter(self) -> None:
        cell = self.ctx.viewport.cell_at_screen(pygame.mouse.get_pos())
        if cell is not None:
            self._target = cell
        self.ctx.status("Paste · LMB/Enter to place", "Esc/RMB to cancel")

    def exit(self) -> None:
        pass

    def handle_event(self, event: pygame.event.Event) -> bool:

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self.cancel()
            return True
        if self._handle_view_events(event):
            return True
        if event.type == pygame.MOUSEMOTION:
            cell = self.ctx.viewport.cell_at_screen(event.pos)
            if cell is not None and self.ctx.doc.is_valid_cell(*cell):
                self._target = cell
                self.ctx.status("Paste · LMB/Enter to place", "Esc/RMB to cancel")
            else:
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                w, h = self.ctx.doc.size if self.ctx.doc.has_canvas else (0, 0)
                if wx < 0 or wy < 0:
                    self.ctx.status("Paste · LMB/Enter to place", "Top/left edge blocked")
                elif self.ctx.doc.has_canvas and (wx >= w or wy >= h):
                    self.ctx.status("Paste · LMB/Enter to place", "Outside — canvas expands")
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
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):

            self._clamp_target()
            self._place()
            self.ctx.set_tool("select")
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
        self._clamp_target()

    def _clamp_target(self) -> None:
        doc = self.ctx.doc
        if not doc.has_canvas:
            return
        max_col = doc.origin_col + doc.cols - 1
        max_row = doc.origin_row + doc.rows - 1
        self._target = (
            max(doc.origin_col, min(max_col, self._target[0])),
            max(doc.origin_row, min(max_row, self._target[1])),
        )

    def _place(self) -> None:
        if self.ctx.clipboard.is_empty:
            self.ctx.toast("Nothing to paste")
            return
        self.ctx.commands.push(
            PasteCommand(
                self._target[0],
                self._target[1],
                self.ctx.clipboard.tiles,
                self.ctx.clipboard.tile_size,
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
    """Edit regions: create, move, resize, rename."""

    overlay_kind = "regions"

    def __init__(self, ctx: ToolContext):
        super().__init__(ctx)
        self.selected_id: str | None = None
        self._hover_id: str | None = None
        self._drag: str | None = None
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
        super().exit()
        self._drag = None
        self._end_rename()

    def _selected_region(self) -> Region | None:
        return self.ctx.doc.region_by_id(self.selected_id) if self.selected_id else None

    def _region_at(self, pos: tuple[int, int]) -> Region | None:
        for region in sorted(self.ctx.doc.regions, key=lambda r: r.w * r.h):
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

    def _start_rename(self, region_id: str | None) -> bool:
        region = self.ctx.doc.region_by_id(region_id) if region_id else None
        if region is None:
            return False
        if self._drag is not None:

            self._cancel_drag()
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

    def draw_overlay(self, screen: Surface) -> None:
        if not self.doc.has_canvas:
            return
        for region in self.ctx.doc.regions:
            if region.id == self.selected_id and self._drag in ("move", "resize"):
                continue
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


class FreeTool(Tool):
    """Free pixel mode."""

    overlay_kind = "free"

    def __init__(self, ctx: ToolContext):
        super().__init__(ctx)
        self._drag: str | None = None
        self._press_world: tuple[float, float] = (0.0, 0.0)
        self._pending: list[float] = [0.0, 0.0, 0.0, 0.0]
        self._block: Rect | None = None
        self._move_ghost: Surface | None = None
        self._move_offset: tuple[int, int] = (0, 0)

        self.tight: bool = False

        self._floating: Surface | None = None
        self._floating_pos: tuple[int, int] = (0, 0)
        self._resize_handle: str | None = None
        self._press_block: Rect | None = None
        self._resize_rect: list[int] = [0, 0, 0, 0]
        self._resize_ghost: Surface | None = None
        self._hover_handle: str | None = None

    def enter(self) -> None:
        self._refresh_status()
        if not self.ctx.doc.has_canvas:
            self.ctx.toast("Load a spritesheet first")

    def _refresh_status(self, detail: str = "Enter: region · Del: clear") -> None:
        tight = " · Tight ON" if self.tight else ""
        self.ctx.status(f"Free mode — drag to select pixels{tight}", detail)

    def exit(self) -> None:
        super().exit()
        self._drag = None
        self._move_ghost = None
        self._move_offset = (0, 0)
        self._floating = None
        self._resize_handle = None
        self._press_block = None
        self._resize_ghost = None
        self._hover_handle = None

    @property
    def doc(self) -> Document:
        return self.ctx.doc

    def has_block(self) -> bool:
        return self._validate_block()

    def block_rect(self) -> Rect | None:
        if not self._validate_block():
            return None
        assert self._block is not None
        return Rect(self._block)

    def clear_block(self) -> None:
        self._block = None
        self._drag = None
        self._move_ghost = None
        self._move_offset = (0, 0)
        self._resize_handle = None
        self._press_block = None
        self._resize_ghost = None
        self._hover_handle = None

    def arm_floating(self, surface: Surface) -> None:
        self.clear_block()
        self._floating = surface.copy()
        wx, wy = self.ctx.viewport.screen_to_world(*pygame.mouse.get_pos())
        self._floating_pos = (int(round(wx)), int(round(wy)))
        self.ctx.status("Pixel paste — move to place", "LMB/Enter stamp · Esc cancel")

    def cancel_floating(self) -> bool:
        if self._floating is None:
            return False
        self._floating = None
        self.ctx.toast("Paste canceled")
        self._refresh_status("")
        return True

    def _min_world(self) -> float:
        return MIN_SCREEN_PX / max(0.1, self.ctx.camera.zoom)

    def _clamp_to_canvas(self, wx: float, wy: float) -> tuple[float, float]:
        w, h = self.doc.size
        return (max(0.0, min(wx, float(w))), max(0.0, min(wy, float(h))))

    def _validate_block(self) -> bool:
        if self._block is None or not self.doc.has_canvas:
            self._block = None
            return False
        clipped = self._block.clip(self.doc.surface.get_rect())
        if clipped.w <= 0 or clipped.h <= 0:
            self._block = None
            return False
        return True

    def _block_screen_rect(self) -> Rect | None:
        if not self._validate_block():
            return None
        b = self._block
        assert b is not None
        if self._drag == "move":
            dx, dy = self._move_offset
            return screen_rect_for(self.ctx.camera, b.x + dx, b.y + dy, b.w, b.h)
        return screen_rect_for(self.ctx.camera, b.x, b.y, b.w, b.h)

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

    def _stamp_floating(self) -> None:
        if self._floating is None:
            return
        self.ctx.commands.push(
            PixelStampCommand(self._floating_pos, self._floating),
            self.ctx.doc,
            self.ctx.selection,
        )
        self._floating = None
        self.ctx.toast("Stamped pixels")
        self._refresh_status("")

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and self._floating is not None:
            self.cancel_floating()
            return True
        if self._handle_view_events(event):
            return True
        if self._handle_view_keys(event):
            return True

        if event.type == pygame.MOUSEMOTION:
            if self._floating is not None:
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                self._floating_pos = (int(round(wx)), int(round(wy)))
                self.ctx.status("Pixel paste — move to place", "LMB/Enter stamp · Esc cancel")
                return True
            self._update_hover(event.pos)
            if self._drag == "marquee":
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                cx, cy = self._clamp_to_canvas(wx, wy)
                px, py = self._press_world
                self._pending = self._normalize([px, py, cx - px, cy - py])
            elif self._drag == "move":
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                px, py = self._press_world
                self._move_offset = (round(wx - px), round(wy - py))
            elif self._drag == "resize":
                self._update_resize(event.pos)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._floating is not None:
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                self._floating_pos = (int(round(wx)), int(round(wy)))
                self._stamp_floating()
                return True
            self._on_left_down(event.pos)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._on_left_up()
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and self._drag:
                self._drag = None
                self._move_ghost = None
                self._move_offset = (0, 0)
                self._resize_handle = None
                self._press_block = None
                self._resize_ghost = None
                self._refresh_status("")
                return True
            if event.key == pygame.K_ESCAPE and self._floating is not None:
                self.cancel_floating()
                return True
            if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                return self._clear_block()
            if event.key in (pygame.K_h, pygame.K_v) and self._drag is None and self._floating is None:
                return self._mirror("v" if event.key == pygame.K_v else "h")
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self._floating is not None:
                    self._stamp_floating()
                    return True
                return self._confirm()
        return False

    def _update_hover(self, pos: tuple[int, int]) -> None:
        if self._drag or not self.doc.has_canvas:
            return
        rect = self._block_screen_rect()
        self._hover_handle = handle_at(rect, pos, HANDLE_SIZE) if rect is not None else None
        wx, wy = self.ctx.viewport.screen_to_world(*pos)
        w, h = self.doc.size
        if wx < 0 or wy < 0:
            self.ctx.status("Canvas edge — top/left blocked", "")
        elif wx >= w or wy >= h:
            self.ctx.status("Outside canvas — bottom/right expands", "")
        else:
            self._refresh_status(f"({int(wx)}, {int(wy)})")

    def _update_resize(self, pos: tuple[int, int]) -> None:
        """Update stretch rect from resize drag."""
        if self._press_block is None or self._resize_handle is None:
            return
        handle = self._resize_handle
        x0, y0, w0, h0 = (self._press_block.x, self._press_block.y, self._press_block.w, self._press_block.h)
        right, bottom = x0 + w0, y0 + h0
        wx, wy = self.ctx.viewport.screen_to_world(*pos)
        locked = len(handle) == 2 and bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        if "l" in handle:
            nx = min(int(round(wx)), right - 1)
            nw = right - nx
        elif "r" in handle:
            nx, nw = x0, max(1, int(round(wx)) - x0)
        else:
            nx, nw = x0, w0
        if "t" in handle:
            ny = min(int(round(wy)), bottom - 1)
            nh = bottom - ny
        elif "b" in handle:
            ny, nh = y0, max(1, int(round(wy)) - y0)
        else:
            ny, nh = y0, h0
        if locked and w0 > 0:
            nh = max(1, int(round(h0 * (nw / w0))))
            if "t" in handle:
                ny = bottom - nh
        self._resize_rect = [nx, ny, nw, nh]
        detail = f"{nw}×{nh}" + (" locked" if locked else "")
        self.ctx.status("Stretch pixels", detail + " · Release to commit · Esc cancels")

    def _on_left_down(self, pos: tuple[int, int]) -> None:
        if not self.doc.has_canvas:
            self.ctx.toast("Load a spritesheet first")
            return
        rect = self._block_screen_rect()
        if rect is not None:
            handle = handle_at(rect, pos, HANDLE_SIZE)
            if handle:
                assert self._block is not None
                clipped = self._block.clip(self.doc.surface.get_rect())
                self._resize_ghost = self.doc.surface.subsurface(clipped).copy()
                self._drag = "resize"
                self._resize_handle = handle
                self._press_block = Rect(self._block)
                b = self._block
                self._resize_rect = [b.x, b.y, b.w, b.h]
                self._hover_handle = handle
                self.ctx.status("Stretch pixels", "Shift locks aspect · Release to commit · Esc cancels")
                return
            if rect.inflate(6, 6).collidepoint(pos):
                assert self._block is not None
                clipped = self._block.clip(self.doc.surface.get_rect())
                self._move_ghost = self.doc.surface.subsurface(clipped).copy()
                self._drag = "move"
                self._move_offset = (0, 0)
                self._press_world = self.ctx.viewport.screen_to_world(*pos)
                self.ctx.status("Move pixels", "Release to commit · Esc cancels")
                return
        self._block = None
        self._drag = "marquee"
        px, py = self.ctx.viewport.screen_to_world(*pos)
        self._press_world = self._clamp_to_canvas(px, py)
        self._pending = [self._press_world[0], self._press_world[1], 0.0, 0.0]
        self._refresh_status("")

    def _tighten(self, rect: Rect) -> Rect | None:
        """Shrink marquee to content.

        Transparent counts as empty (min_alpha=1, same rule as the
        document trim). Returns None when nothing visible is inside.
        """
        if self.doc.surface is None:
            return None
        clipped = rect.clip(self.doc.surface.get_rect())
        if clipped.w <= 0 or clipped.h <= 0:
            return None
        try:
            inner = self.doc.surface.subsurface(clipped).get_bounding_rect(min_alpha=1)
        except (ValueError, pygame.error):
            return None
        if inner.w <= 0 or inner.h <= 0:
            return None
        return Rect(clipped.x + inner.x, clipped.y + inner.y, inner.w, inner.h)

    def _on_left_up(self) -> None:
        drag, self._drag = self._drag, None
        if drag == "marquee":
            x, y, w, h = self._pending
            if w < self._min_world() or h < self._min_world():
                self.ctx.toast("Selection too small")
            else:
                block = Rect(int(x), int(y), max(1, int(round(w))), max(1, int(round(h))))
                block = block.clip(self.doc.surface.get_rect())
                if self.tight:
                    tight = self._tighten(block)
                    if tight is None:
                        self.ctx.toast("Empty selection — nothing visible inside")
                        self._refresh_status()
                        return
                    block = tight
                self._block = block
                detail = "Enter: region · Del: clear"
                if self.tight:
                    detail = f"Tight {block.w}×{block.h} · " + detail
                self.ctx.status("Pixel block selected — drag to move", detail)
        elif drag == "move":
            dx, dy = self._move_offset
            self._move_ghost = None
            self._move_offset = (0, 0)
            if (dx != 0 or dy != 0) and self._block is not None:
                self.ctx.commands.push(PixelMoveCommand(self._block, dx, dy), self.ctx.doc, self.ctx.selection)
                self.ctx.toast("Moved pixels")
            self._block = None
            self._refresh_status("")
        elif drag == "resize":
            dest = Rect(self._resize_rect)
            self._resize_handle = None
            self._press_block = None
            self._resize_ghost = None
            if self._block is not None and (dest.x, dest.y, dest.w, dest.h) != (
                self._block.x,
                self._block.y,
                self._block.w,
                self._block.h,
            ):
                cmd = PixelScaleCommand(self._block, dest)
                self.ctx.commands.push(cmd, self.ctx.doc, self.ctx.selection)
                if cmd.dest is not None:
                    self._block = cmd.dest
                    self.ctx.toast(f"Stretched {cmd.dest.w}×{cmd.dest.h}")
                    self._refresh_status("H/V mirror · Enter: region · Del: clear")
                    return
            self._refresh_status("")

    def _clear_block(self) -> bool:
        if self._drag is not None:
            return False
        if not self._validate_block():
            return False
        assert self._block is not None
        self.ctx.commands.push(PixelClearCommand(self._block), self.ctx.doc, self.ctx.selection)
        self._block = None
        self.ctx.toast("Cleared pixels")
        return True

    def _mirror(self, axis: str) -> bool:
        """Stamp mirrored copy next to block.

        The copy becomes the selected block so repeated presses chain
        outward (A → AB → ABA …).
        """
        if not self._validate_block():
            return False
        assert self._block is not None
        shift = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT)
        side = -1 if shift else 1
        cmd = PixelMirrorCommand(self._block, axis, side)
        self.ctx.commands.push(cmd, self.ctx.doc, self.ctx.selection)
        if cmd.dest is not None:
            self._block = cmd.dest
            where = {("h", 1): "right", ("h", -1): "left", ("v", 1): "down", ("v", -1): "up"}[(axis, side)]
            self.ctx.toast(f"Mirrored {where} {cmd.dest.w}×{cmd.dest.h}")
            self.ctx.status(
                "Pixel block selected — drag to move",
                "H/V mirror · Enter: region · Del: clear",
            )
        return True

    def _confirm(self) -> bool:
        """Commit move or save block as region on Enter."""
        if self._drag in ("move", "resize"):
            self._on_left_up()
            return True
        if self._drag is not None or not self._validate_block():
            return False
        assert self._block is not None
        b = self._block
        region = Region(id=Region.new_id(), rect=[float(b.x), float(b.y), float(b.w), float(b.h)], name="")
        self.ctx.commands.push(RegionAddCommand(region), self.ctx.doc, self.ctx.selection)
        self.ctx.toast("Region from block — see Regions mode")
        return True

    def draw_overlay(self, screen: Surface) -> None:
        if not self.doc.has_canvas:
            return
        if self._floating is not None:
            fw, fh = self._floating.get_size()
            fx, fy = self._floating_pos
            dest = screen_rect_for(self.ctx.camera, fx, fy, fw, fh)
            if dest.w > 0 and dest.h > 0:
                try:
                    ghost = pygame.transform.smoothscale(self._floating, (dest.w, dest.h))
                except (ValueError, pygame.error):
                    ghost = pygame.transform.scale(self._floating, (dest.w, dest.h))
                ghost.set_alpha(180)
                screen.blit(ghost, dest.topleft)
                draw_dashed_border(screen, dest, COLORS.accent)
            return
        if self._drag == "marquee" and (self._pending[2] > 0 or self._pending[3] > 0):
            x, y, w, h = self._pending
            rect = screen_rect_for(self.ctx.camera, x, y, max(0.5, w), max(0.5, h))
            draw_alpha_fill(screen, rect, (80, 200, 220), 24)
            draw_dashed_border(screen, rect, COLORS.accent)
            return
        if self._drag == "move" and self._move_ghost is not None and self._block is not None:
            b = self._block
            src_rect = screen_rect_for(self.ctx.camera, b.x, b.y, b.w, b.h)
            draw_alpha_fill(screen, src_rect, CANVAS_BG, 200)
            dx, dy = self._move_offset
            dest = screen_rect_for(self.ctx.camera, b.x + dx, b.y + dy, b.w, b.h)
            if dest.w > 0 and dest.h > 0:
                try:
                    ghost = pygame.transform.smoothscale(self._move_ghost, (dest.w, dest.h))
                except (ValueError, pygame.error):
                    ghost = pygame.transform.scale(self._move_ghost, (dest.w, dest.h))
                ghost.set_alpha(200)
                screen.blit(ghost, dest.topleft)
                draw_dashed_border(screen, dest, COLORS.accent)
            return
        if self._drag == "resize" and self._resize_ghost is not None and self._press_block is not None:
            b = self._press_block
            src_rect = screen_rect_for(self.ctx.camera, b.x, b.y, b.w, b.h)
            draw_alpha_fill(screen, src_rect, CANVAS_BG, 200)
            nx, ny, nw, nh = self._resize_rect
            dest = screen_rect_for(self.ctx.camera, nx, ny, nw, nh)
            if dest.w > 0 and dest.h > 0:
                ghost = pygame.transform.scale(self._resize_ghost, (dest.w, dest.h))
                ghost.set_alpha(200)
                screen.blit(ghost, dest.topleft)
                draw_dashed_border(screen, dest, COLORS.accent)
            return
        rect = self._block_screen_rect()
        if rect is not None and self._drag is None:
            pygame.draw.rect(screen, COLORS.accent, rect, 2)
            draw_handles(screen, rect, COLORS.accent, HANDLE_SIZE, self._hover_handle)


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

    w = max(1, int(round(box_w)))
    h = max(1, int(round(box_h)))
    surf = Surface((w, h), pygame.SRCALPHA)
    if bg is not None:

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
    """Freeform text: drag box, type, Enter to bake."""

    overlay_kind = "text"

    def __init__(self, ctx: ToolContext):
        super().__init__(ctx)
        self._mode: str = "idle"
        self._draft_rect: list[float] = [0.0, 0.0, 0.0, 0.0]
        self._press_world: tuple[float, float] = (0.0, 0.0)
        self._press_rect: list[float] = [0.0, 0.0, 0.0, 0.0]
        self._drag: str | None = None
        self._rotate_start_angle: float = 0.0
        self._rotate_press_angle: float = 0.0

        self._fg: tuple[int, int, int] = (255, 255, 255)
        self._bg: tuple[int, int, int] | None = None
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
        super().exit()
        self._drag = None
        self._mode = "idle"
        self._input.is_focused = False

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
    
        panel_w = (
            _PANEL_PAD * 2
            + len(_TEXT_FG_PALETTE) * (_SWATCH + _SWATCH_GAP)
            + 10
            + len(_TEXT_BG_PALETTE) * (_SWATCH + _SWATCH_GAP)
            + 10
            + 56
            + 30
        )
        panel_w = min(panel_w, self.ctx.viewport.rect.w - 10)
        panel_h = _PANEL_H + 6
        x = srect.centerx - panel_w // 2

        y_above = srect.y - panel_h - 28
        y_below = srect.bottom + 10
        y = y_above if y_above >= self.ctx.viewport.content_rect.y else y_below
        x = max(self.ctx.viewport.rect.x + 4, min(x, self.ctx.viewport.rect.right - panel_w - 4))
        self._panel_rect = Rect(x, y, panel_w, panel_h)
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
        cx += 10
        self._btn_plus = Rect(cx, cy, 22, _SWATCH)
        cx += 24
        self._btn_bold = Rect(cx, cy, 26, _SWATCH)
        self._rot_handle_screen = self._rotation_handle_screen_pos(srect)

    def _normalize_rect(self, r: list[float]) -> list[float]:
        x, y, w, h = r
        if w < 0:
            x += w
            w = -w
        if h < 0:
            y += h
            h = -h
        return [x, y, w, h]

    def _commit(self) -> None:
        text = self._input.text
        if not text.strip():
            self.ctx.toast("Empty label — discarded")
            self._reset_to_idle()
            return
        x, y, w, h = self._draft_rect
        if w < self._min_world() or h < self._min_world():

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

    def cancel(self) -> None:
        self._reset_to_idle()
        self.ctx.toast("Text canceled")

    def _cancel(self) -> None:
        self.cancel()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._handle_view_events(event):
            return True

        if self._mode == "editing" and self._input.is_focused:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    self._commit()
                    return True
                if event.key == pygame.K_ESCAPE:
                    self._cancel()
                    return True
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
                    delta = ang - self._rotate_start_angle
                    self._angle = self._rotate_press_angle + delta
                    snap = round(self._angle / 15.0) * 15.0
                    if abs(self._angle - snap) < 4:
                        self._angle = snap
                return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._mode == "editing" and self._panel_rect:
                srect = self._screen_rect()
                if srect:
                    self._compute_panel_layout(srect)
                if self._panel_rect.collidepoint(event.pos):

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
                if (
                    self._rot_handle_screen
                    and (
                        (event.pos[0] - self._rot_handle_screen[0]) ** 2
                        + (event.pos[1] - self._rot_handle_screen[1]) ** 2
                    )
                    <= (_ROT_HANDLE_R + 4) ** 2
                ):
                    import math

                    srect2 = self._screen_rect()
                    if srect2:
                        cx, cy = srect2.centerx, srect2.centery
                        self._drag = "rotate"
                        self._rotate_press_angle = self._angle
                        self._rotate_start_angle = math.degrees(math.atan2(event.pos[1] - cy, event.pos[0] - cx))
                    return True

            if self._mode == "editing" and self._input.rect.collidepoint(event.pos):
                self._input.handle_event(event)
                self._input.is_focused = True
                return True
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
                        self._input.is_focused = True
                        self._drag = "move"
                        self._press_world = self.ctx.viewport.screen_to_world(*event.pos)
                        self._press_rect = list(self._draft_rect)
                        return True

                    if not (self._panel_rect and self._panel_rect.collidepoint(event.pos)):
                        self._commit()
                        return True
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
                self._draft_rect = self._normalize_rect(self._draft_rect)
                if self._draft_rect[2] < self._min_world() or self._draft_rect[3] < self._min_world():
                    self._draft_rect[2] = max(self._draft_rect[2], 120.0)
                    self._draft_rect[3] = max(self._draft_rect[3], 28.0)
                self._mode = "editing"
                self._input.text = ""
                self._input.is_focused = True
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
        return False

    def draw_overlay(self, screen: Surface) -> None:
        if not self.ctx.doc.has_canvas:
            return
        if self._mode == "drafting" and self._draft_rect[2] >= 0:
            r = screen_rect_for(
                self.ctx.camera,
                self._draft_rect[0],
                self._draft_rect[1],
                max(0.5, self._draft_rect[2]),
                max(0.5, self._draft_rect[3]),
            )
            draw_alpha_fill(screen, r, (255, 220, 120), 22)
            draw_dashed_border(screen, r, (255, 230, 140))
            return
        if self._mode != "editing":
            return
        srect = self._screen_rect()
        if srect is None:
            return
        self._compute_panel_layout(srect)


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

        # when angle !=0, draw rotated border via polygon
        if abs(self._angle) > 0.5:
            import math

            cx, cy = srect.centerx, srect.centery
            w2, h2 = srect.w / 2.0, srect.h / 2.0
            ang = math.radians(self._angle)
            ca, sa = math.cos(ang), math.sin(ang)

            def rot(px, py):
                rx = px * ca - py * sa
                ry = px * sa + py * ca
                return (cx + rx, cy + ry)

            pts = [rot(-w2, -h2), rot(w2, -h2), rot(w2, h2), rot(-w2, h2)]
            pygame.draw.lines(screen, (255, 230, 140), True, pts, 1)
        else:
            draw_dashed_border(screen, srect, (255, 230, 140))
            if self._bg is None:
                draw_alpha_fill(screen, srect, (255, 255, 255), 6)

        hx, hy = self._rotation_handle_screen_pos(srect)
        self._rot_handle_screen = (hx, hy)
        pygame.draw.line(screen, (255, 230, 140), srect.center, (hx, hy), 1)
        pygame.draw.circle(screen, (40, 40, 44), (hx, hy), _ROT_HANDLE_R + 1)
        pygame.draw.circle(screen, (255, 230, 140), (hx, hy), _ROT_HANDLE_R)
        pygame.draw.circle(screen, COLORS.panel, (hx, hy), 2)
        if abs(self._angle) > 0.5:
            lbl = FONTS.get_small_font().render(f"{self._angle:.0f}°", True, COLORS.text)
            screen.blit(lbl, (hx + 10, hy - 7))

        if self._panel_rect:
            pygame.draw.rect(screen, COLORS.panel, self._panel_rect, border_radius=SHAPE.radius_sm)
            pygame.draw.rect(screen, COLORS.border, self._panel_rect, 1, border_radius=SHAPE.radius_sm)
            for i, r in enumerate(self._swatch_rects_fg):
                col = _TEXT_FG_PALETTE[i]
                pygame.draw.rect(screen, col, r, border_radius=3)
                pygame.draw.rect(screen, COLORS.border_soft, r, 1, border_radius=3)
                if col == self._fg:
                    pygame.draw.rect(screen, (255, 255, 255), r.inflate(4, 4), 2, border_radius=4)
                    pygame.draw.rect(screen, (0, 0, 0), r.inflate(4, 4), 1, border_radius=4)
            sep_x = self._swatch_rects_fg[-1].right + 6 if self._swatch_rects_fg else self._panel_rect.x + 10
            pygame.draw.line(
                screen, COLORS.border_soft, (sep_x, self._panel_rect.y + 5), (sep_x, self._panel_rect.bottom - 5), 1
            )
            for i, r in enumerate(self._swatch_rects_bg):
                col = _TEXT_BG_PALETTE[i]
                if col is None:
                    pygame.draw.rect(screen, (60, 60, 65), r, border_radius=3)
                    pygame.draw.rect(screen, (40, 40, 44), Rect(r.x, r.y, r.w // 2, r.h // 2), border_radius=2)
                    pygame.draw.rect(
                        screen, (40, 40, 44), Rect(r.x + r.w // 2, r.y + r.h // 2, r.w // 2, r.h // 2), border_radius=2
                    )
                    pygame.draw.line(screen, (200, 80, 80), r.topleft, r.bottomright, 2)
                else:
                    pygame.draw.rect(screen, col, r, border_radius=3)
                pygame.draw.rect(screen, COLORS.border_soft, r, 1, border_radius=3)
                is_sel = (col == self._bg) or (col is None and self._bg is None)
                if is_sel:
                    pygame.draw.rect(screen, (255, 255, 255), r.inflate(4, 4), 2, border_radius=4)
            if self._btn_minus and self._btn_plus and self._btn_bold:
                for btn, label in [(self._btn_minus, "−"), (self._btn_plus, "+")]:
                    pygame.draw.rect(screen, COLORS.panel_alt, btn, border_radius=3)
                    pygame.draw.rect(screen, COLORS.border_soft, btn, 1, border_radius=3)
                    ts = FONTS.get_font(14).render(label, True, COLORS.text)
                    screen.blit(ts, ts.get_rect(center=btn.center))
                mid_x = (self._btn_minus.right + self._btn_plus.x) // 2
                sz_lbl = FONTS.get_small_font().render(str(self._font_size), True, COLORS.text)
                screen.blit(sz_lbl, sz_lbl.get_rect(center=(mid_x, self._panel_rect.centery)))
                bg_col = COLORS.accent if self._bold else COLORS.panel_alt
                border_col = COLORS.accent_active if self._bold else COLORS.border_soft
                txt_col = COLORS.text_on_accent if self._bold else COLORS.text
                pygame.draw.rect(screen, bg_col, self._btn_bold, border_radius=3)
                pygame.draw.rect(screen, border_col, self._btn_bold, 1, border_radius=3)
                b_lbl = FONTS.get_bold_font(13).render("B", True, txt_col)
                screen.blit(b_lbl, b_lbl.get_rect(center=self._btn_bold.center))

        input_w = min(220, max(120, srect.w))
        irect = Rect(srect.x, srect.bottom + 4, input_w, _INPUT_H)
        if irect.right > self.ctx.viewport.rect.right - 4:
            irect.x = self.ctx.viewport.rect.right - irect.w - 4
        if irect.bottom > self.ctx.viewport.rect.bottom - 4:
            irect.y = srect.y - _INPUT_H - 4
        self._input.rect = irect
        self._input._update_content_rect()
        self._input.draw(screen)
        if not self._input.text:
            hint = FONTS.get_small_font().render("Label…  Enter ✓  Esc ✕", True, COLORS.text_muted)
            screen.blit(hint, (irect.x + 8, irect.y + 6))


_COLOR_PALETTE: list[tuple[int, int, int, int]] = [
    (255, 255, 255, 255),
    (20, 20, 22, 255),
    (220, 60, 60, 255),
    (255, 150, 40, 255),
    (240, 220, 60, 255),
    (80, 180, 90, 255),
    (70, 120, 210, 255),
    (160, 90, 210, 255),
    (128, 128, 128, 255),
    (0, 0, 0, 0),
]
_COLOR_SCOPES: tuple[tuple[str, str], ...] = (
    ("full", "Full"),
    ("marquee", "Marquee"),
    ("flood", "Flood"),
)


def _hex_of(color: tuple[int, int, int, int]) -> str:
    r, g, b, a = (max(0, min(255, int(v))) for v in color)
    if a == 255:
        return f"#{r:02X}{g:02X}{b:02X}"
    return f"#{r:02X}{g:02X}{b:02X}{a:02X}"


def _parse_hex(text: str) -> tuple[int, int, int, int] | None:
    t = text.strip()
    if t.startswith("#"):
        t = t[1:]
    if len(t) not in (6, 8):
        return None
    try:
        vals = [int(t[i : i + 2], 16) for i in range(0, len(t), 2)]
    except ValueError:
        return None
    if len(vals) == 3:
        vals.append(255)
    r, g, b, a = vals
    return (r, g, b, a)


class ColorTool(Tool):
    """Pick a color and replace it. Scopes: full canvas, marquee, flood."""

    overlay_kind = "color"

    def __init__(self, ctx: ToolContext):
        super().__init__(ctx)
        self._src: tuple[int, int, int, int] | None = None
        self._dst: tuple[int, int, int, int] = (255, 255, 255, 255)
        self._target: str = "src"
        self._scope: str = "full"
        self._tolerance: int = 0
        self._drag: str | None = None
        self._marquee: list[float] = [0.0, 0.0, 0.0, 0.0]
        self._press_world: tuple[float, float] = (0.0, 0.0)
        self._seed: tuple[int, int] | None = None
        self._preview_count: int | None = None
        self._panel_rect: Rect | None = None
        self._src_box: Rect | None = None
        self._dst_box: Rect | None = None
        self._swatch_rects: list[Rect] = []
        self._scope_rects: list[Rect] = []
        self._tol_minus: Rect | None = None
        self._tol_plus: Rect | None = None
        self._apply_rect: Rect | None = None
        self._custom_btn: Rect | None = None
        self._custom_open: bool = False
        self._custom_panel: Rect | None = None
        self._field = None
        self._sliders: list = []
        self._slider_keys: list[str] = []
        self._hex: InputBox | None = None
        self._done_rect: Rect | None = None
        self._custom_target: str = "dst"

    def enter(self) -> None:
        self._drag = None
        if not self.ctx.doc.has_canvas:
            self.ctx.toast("Load a spritesheet first")
            self.ctx.status("Color — load an image first", "")
        else:
            self._refresh_count()
            self._push_status()

    def exit(self) -> None:
        super().exit()
        self._drag = None
        self._marquee = [0.0, 0.0, 0.0, 0.0]
        if self._hex is not None:
            self._hex.is_focused = False

    def _push_status(self) -> None:
        if self._src is None:
            self.ctx.status("Color — click to pick source", "Alt+click picks target · Enter applies")
            return
        detail = "Enter applies · Esc clears"
        if self._preview_count is not None:
            detail = f"{self._preview_count} px match · " + detail
        scope_lbl = {"full": "Full", "marquee": "Marquee", "flood": "Flood"}.get(self._scope, "Full")
        self.ctx.status(f"Color — {scope_lbl} {_hex_of(self._src)} → {_hex_of(self._dst)}", detail)

    def _sample(self, pos: tuple[int, int]) -> tuple[int, int, int, int] | None:
        if not self.ctx.doc.has_canvas or self.ctx.doc.surface is None:
            return None
        wx, wy = self.ctx.viewport.screen_to_world(*pos)
        x, y = int(wx), int(wy)
        if not self.ctx.doc.surface.get_rect().collidepoint(x, y):
            return None
        c = self.ctx.doc.surface.get_at((x, y))
        return (c.r, c.g, c.b, c.a)

    def pick_source(self, pos: tuple[int, int]) -> bool:
        c = self._sample(pos)
        if c is None:
            self.ctx.status("Color — outside canvas", "")
            return False
        self._src = c
        if self._scope == "flood":
            wx, wy = self.ctx.viewport.screen_to_world(*pos)
            self._seed = (int(wx), int(wy))
        self._refresh_count()
        self._push_status()
        return True

    def pick_target(self, pos: tuple[int, int]) -> bool:
        c = self._sample(pos)
        if c is None:
            return False
        self._dst = c
        self._refresh_count()
        self._push_status()
        return True

    def _scope_rect(self) -> Rect | None:
        if self._scope != "marquee":
            return None
        x, y, w, h = self._marquee
        if w <= 0 or h <= 0:
            return None
        return Rect(int(x), int(y), int(w), int(h))

    def _refresh_count(self) -> None:
        self._preview_count = None
        if self._src is None or not self.ctx.doc.has_canvas:
            return
        rect = self._scope_rect()
        if self._scope == "marquee" and rect is None:
            return
        seed = self._seed
        if self._scope == "flood" and seed is None:
            return
        try:
            self._preview_count = self.ctx.doc.remap_pixels(
                self._src,
                self._dst,
                rect=rect,
                tolerance=self._tolerance,
                contiguous=self._scope == "flood",
                seed=seed,
                dry_run=True,
            )
        except Exception:
            self._preview_count = None

    def _apply(self) -> None:
        if not self.ctx.doc.has_canvas:
            self.ctx.toast("Load a spritesheet first")
            return
        if self._src is None:
            self.ctx.toast("Pick a source color first")
            return
        rect = self._scope_rect()
        if self._scope == "marquee" and rect is None:
            self.ctx.toast("Drag a marquee first")
            return
        seed = self._seed
        if self._scope == "flood" and seed is None:
            self.ctx.toast("Click a pixel to seed flood")
            return
        cmd = ColorReplaceCommand(
            self._src,
            self._dst,
            rect=rect,
            tolerance=self._tolerance,
            contiguous=self._scope == "flood",
            seed=seed,
        )
        self.ctx.commands.push(cmd, self.ctx.doc, self.ctx.selection)
        n = cmd.replaced
        self._marquee = [0.0, 0.0, 0.0, 0.0]
        self._seed = None
        self._refresh_count()
        self._push_status()
        if n > 0:
            self.ctx.toast(f"Replaced {n} px")
        else:
            self.ctx.toast("No pixels matched")

    def _active_color(self) -> tuple[int, int, int, int]:
        if self._custom_target == "src":
            return self._src or (255, 255, 255, 255)
        return self._dst

    def _set_active_color(self, color: tuple[int, int, int, int]) -> None:
        if self._custom_target == "src":
            self._src = color
        else:
            self._dst = color
        self._refresh_count()
        self._push_status()

    def _open_custom(self, target: str) -> None:
        from widgets.ui.particle_config_dialog import ColorField, Slider

        self._custom_target = target
        self._custom_open = True
        col = self._active_color()
        self._field = ColorField(Rect(0, 0, 180, 100))
        self._field.set_rgb(col[0], col[1], col[2])
        self._sliders = []
        self._slider_keys = ["r", "g", "b", "a"]
        for i, (key, val) in enumerate(
            [("r", col[0]), ("g", col[1]), ("b", col[2]), ("a", col[3])]
        ):
            self._sliders.append(Slider(Rect(0, 0, 150, 18), key.upper(), 0, 255, float(val), "{:.0f}"))
        self._hex = InputBox(
            Rect(0, 0, 110, 22),
            font=FONTS.get_font(13),
            allowed_chars="#0123456789abcdefABCDEF",
        )
        self._hex.text = _hex_of(col)
        self._hex.is_focused = False
        self._sync_custom_widgets(col)

    def _sync_custom_widgets(self, col: tuple[int, int, int, int] | None = None) -> None:
        if self._field is None or not self._sliders or self._hex is None:
            return
        if col is None:
            col = self._active_color()
        self._field.set_rgb(col[0], col[1], col[2])
        for slider, key in zip(self._sliders, self._slider_keys):
            slider.value = float({"r": col[0], "g": col[1], "b": col[2], "a": col[3]}[key])
        self._hex.text = _hex_of(col)

    def _layout_panels(self) -> None:
        vp = self.ctx.viewport
        content = vp.content_rect
        small = FONTS.get_small_font()
        x = content.centerx - 300
        x = max(vp.rect.x + 4, min(x, vp.rect.right - 610))
        y = content.y + 6
        h = 30
        cx = x + 6
        self._src_box = Rect(cx, y + 5, 26, 20)
        cx += 30
        self._dst_box = Rect(cx, y + 5, 26, 20)
        cx += 32
        self._swatch_rects = []
        for _ in _COLOR_PALETTE:
            self._swatch_rects.append(Rect(cx, y + 6, 18, 18))
            cx += 22
        cx += 4
        self._scope_rects = []
        for _key, _label in _COLOR_SCOPES:
            w = max(52, small.size(_label)[0] + 14)
            self._scope_rects.append(Rect(cx, y + 5, w, 20))
            cx += w + 4
        self._tol_minus = Rect(cx, y + 5, 20, 20)
        cx += 24
        self._tol_plus = Rect(cx + 34, y + 5, 20, 20)
        cx += 58
        self._apply_rect = Rect(cx, y + 5, 52, 20)
        cx += 56
        self._custom_btn = Rect(cx, y + 5, 64, 20)
        cx += 64
        self._panel_rect = Rect(x, y, cx - x + 6, h)
        self._custom_panel = None
        self._done_rect = None
        if not self._custom_open:
            return
        cw, ch = 380, 178
        px = max(
            self.ctx.viewport.rect.x + 4,
            min(self._panel_rect.centerx - cw // 2, self.ctx.viewport.rect.right - cw - 4),
        )
        py = self._panel_rect.bottom + 6
        if py + ch > self.ctx.viewport.rect.bottom - 4:
            py = max(self.ctx.viewport.rect.y + 4, self._panel_rect.y - ch - 6)
        self._custom_panel = Rect(px, py, cw, ch)
        fx, fy = px + 10, py + 28
        if self._field is not None:
            self._field.rect = Rect(fx, fy, 180, 110)
        sx = fx + 196
        for i, slider in enumerate(self._sliders):
            slider.rect = Rect(sx, fy + i * 30, 150, 18)
        if self._hex is not None:
            self._hex.rect = Rect(sx, fy + 4 * 30 + 2, 110, 22)
            self._hex._update_content_rect()
        self._done_rect = Rect(px + cw - 70, py + ch - 30, 60, 22)

    def _custom_hit(self, pos: tuple[int, int]) -> bool:
        return bool(self._custom_open and self._custom_panel and self._custom_panel.collidepoint(pos))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._handle_view_events(event):
            return True
        if (
            self._hex is not None
            and self._custom_open
            and self._hex.is_focused
            and event.type == pygame.KEYDOWN
        ):
            if event.key == pygame.K_RETURN:
                parsed = _parse_hex(self._hex.text)
                if parsed is not None:
                    self._set_active_color(parsed)
                    self._sync_custom_widgets(parsed)
                else:
                    self.ctx.toast("Hex like #RRGGBB or #RRGGBBAA")
                return True
            if event.key == pygame.K_ESCAPE:
                self._hex.is_focused = False
                return True
            if self._hex.handle_event(event):
                return True
        if self._handle_view_keys(event):
            return True
        if self._custom_open and event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            field_active = self._field is not None and self._field.dragging_part
            dragged = [s for s in self._sliders if s.dragging]
            if field_active or dragged:
                if field_active and self._field is not None:
                    self._field.handle_event(event)
                    r, g, b = self._field.rgb
                    a = self._active_color()[3]
                    for slider, key in zip(self._sliders, self._slider_keys):
                        if key in ("r", "g", "b"):
                            continue
                        if key == "a":
                            a = max(0, min(255, int(round(slider.value))))
                    self._set_active_color((r, g, b, a))
                    self._sync_custom_widgets((r, g, b, a))
                else:
                    for slider in self._sliders:
                        if slider.dragging:
                            result = slider.handle_event(event)
                            if result is not None:
                                slider.value = result
                    col = self._active_color()
                    vals = {"r": col[0], "g": col[1], "b": col[2], "a": col[3]}
                    for slider, key in zip(self._sliders, self._slider_keys):
                        vals[key] = max(0, min(255, int(round(slider.value))))
                    new_col = (vals["r"], vals["g"], vals["b"], vals["a"])
                    if self._field is not None:
                        self._field.set_rgb(new_col[0], new_col[1], new_col[2])
                    self._set_active_color(new_col)
                    self._sync_custom_widgets(new_col)
                return True
        if event.type == pygame.MOUSEMOTION:
            if self._drag == "marquee":
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                x0, y0 = self._press_world
                self._marquee = [
                    min(x0, wx),
                    min(y0, wy),
                    abs(wx - x0),
                    abs(wy - y0),
                ]
                return True
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._custom_open and self._custom_panel is not None:
                self._layout_panels()
                if self._custom_hit(event.pos):
                    return self._handle_custom_click(event.pos)
            self._layout_panels()
            if self._panel_rect is not None and self._panel_rect.collidepoint(event.pos):
                return self._handle_panel_click(event.pos)
            if not self.ctx.doc.has_canvas:
                self.ctx.toast("Load a spritesheet first")
                return True
            mods = pygame.key.get_mods()
            if mods & pygame.KMOD_ALT:
                return self.pick_target(event.pos)
            if self._scope == "marquee":
                wx, wy = self.ctx.viewport.screen_to_world(*event.pos)
                self._press_world = (wx, wy)
                self._marquee = [wx, wy, 0.0, 0.0]
                self._drag = "marquee"
                return True
            return self.pick_source(event.pos)
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._drag == "marquee":
                self._drag = None
                x, y, w, h = self._marquee
                if w < 2 or h < 2:
                    self._marquee = [0.0, 0.0, 0.0, 0.0]
                self._refresh_count()
                self._push_status()
                return True
            return False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self._custom_open:
                    self._custom_open = False
                    if self._hex is not None:
                        self._hex.is_focused = False
                    return True
                if self._scope_rect() is not None or self._seed is not None:
                    self._marquee = [0.0, 0.0, 0.0, 0.0]
                    self._seed = None
                    self._refresh_count()
                    self._push_status()
                    return True
                return False
            if event.key == pygame.K_RETURN:
                self._apply()
                return True
        return False

    def _handle_panel_click(self, pos: tuple[int, int]) -> bool:
        if self._src_box is not None and self._src_box.collidepoint(pos):
            self._target = "src"
            return True
        if self._dst_box is not None and self._dst_box.collidepoint(pos):
            self._target = "dst"
            return True
        for i, r in enumerate(self._swatch_rects):
            if r.collidepoint(pos):
                col = _COLOR_PALETTE[i]
                if self._target == "src":
                    self._src = col
                else:
                    self._dst = col
                self._refresh_count()
                self._push_status()
                return True
        for i, r in enumerate(self._scope_rects):
            if r.collidepoint(pos):
                self._scope = _COLOR_SCOPES[i][0]
                self._seed = None
                self._refresh_count()
                self._push_status()
                return True
        if self._tol_minus is not None and self._tol_minus.collidepoint(pos):
            self._tolerance = max(0, self._tolerance - 5)
            self._refresh_count()
            self._push_status()
            return True
        if self._tol_plus is not None and self._tol_plus.collidepoint(pos):
            self._tolerance = min(100, self._tolerance + 5)
            self._refresh_count()
            self._push_status()
            return True
        if self._apply_rect is not None and self._apply_rect.collidepoint(pos):
            self._apply()
            return True
        if self._custom_btn is not None and self._custom_btn.collidepoint(pos):
            self._open_custom(self._target)
            return True
        return True

    def _handle_custom_click(self, pos: tuple[int, int]) -> bool:
        if self._field is not None and self._field.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1})
        ):
            r, g, b = self._field.rgb
            a = self._active_color()[3]
            self._set_active_color((r, g, b, a))
            self._sync_custom_widgets()
            return True
        for slider, key in zip(self._sliders, self._slider_keys):
            before = slider.value
            result = slider.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1}))
            if result is not None:
                slider.value = result
            if result is not None or slider.value != before:
                col = self._active_color()
                vals = {"r": col[0], "g": col[1], "b": col[2], "a": col[3]}
                vals[key] = max(0, min(255, int(round(slider.value))))
                new_col = (vals["r"], vals["g"], vals["b"], vals["a"])
                self._set_active_color(new_col)
                self._sync_custom_widgets(new_col)
                return True
        if self._hex is not None and self._hex.rect.collidepoint(pos):
            self._hex.is_focused = True
            self._hex.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1}))
            return True
        if self._done_rect is not None and self._done_rect.collidepoint(pos):
            if self._hex is not None and self._hex.text:
                parsed = _parse_hex(self._hex.text)
                if parsed is not None:
                    self._set_active_color(parsed)
            self._custom_open = False
            if self._hex is not None:
                self._hex.is_focused = False
            return True
        return True

    def draw_overlay(self, screen: Surface) -> None:
        if not self.ctx.doc.has_canvas:
            return
        self._layout_panels()
        if self._scope == "full" and self.ctx.doc.surface is not None:
            sheet = self.ctx.viewport.sheet_screen_rect()
            if sheet is not None:
                draw_alpha_fill(screen, sheet, (120, 200, 255), 16)
                draw_dashed_border(screen, sheet, (120, 200, 255))
        elif self._scope == "marquee":
            rect = self._scope_rect()
            if rect is not None:
                r = screen_rect_for(self.ctx.camera, rect.x, rect.y, rect.w, rect.h)
                draw_alpha_fill(screen, r, (120, 200, 255), 28)
                draw_dashed_border(screen, r, (120, 200, 255))
        elif self._scope == "flood" and self._seed is not None:
            sx, sy = self.ctx.camera.world_to_screen(float(self._seed[0]), float(self._seed[1]))
            six, siy = int(sx), int(sy)
            pygame.draw.line(screen, (120, 200, 255), (six - 8, siy), (six + 8, siy), 2)
            pygame.draw.line(screen, (120, 200, 255), (six, siy - 8), (six, siy + 8), 2)
        self._draw_panel(screen)
        if self._custom_open and self._custom_panel is not None:
            self._draw_custom(screen)

    def _draw_swatches(self, screen: Surface) -> None:
        small = FONTS.get_small_font()
        if self._src_box is not None:
            self._draw_color_box(screen, self._src_box, self._src, self._target == "src")
            lbl = small.render("S", True, COLORS.text_dim)
            screen.blit(lbl, (self._src_box.x + 9, self._src_box.bottom + 1))
        if self._dst_box is not None:
            self._draw_color_box(screen, self._dst_box, self._dst, self._target == "dst")
            lbl = small.render("D", True, COLORS.text_dim)
            screen.blit(lbl, (self._dst_box.x + 9, self._dst_box.bottom + 1))
        for i, r in enumerate(self._swatch_rects):
            self._draw_color_box(screen, r, _COLOR_PALETTE[i], False)

    @staticmethod
    def _draw_color_box(
        screen: Surface, rect: Rect, color: tuple[int, int, int, int] | None, selected: bool
    ) -> None:
        if color is None:
            pygame.draw.rect(screen, (60, 60, 65), rect, border_radius=3)
            pygame.draw.line(screen, (200, 80, 80), rect.topleft, rect.bottomright, 2)
        elif color[3] == 0:
            pygame.draw.rect(screen, (60, 60, 65), rect, border_radius=3)
            pygame.draw.rect(screen, (40, 40, 44), Rect(rect.x, rect.y, rect.w // 2, rect.h // 2))
            pygame.draw.rect(
                screen,
                (40, 40, 44),
                Rect(rect.x + rect.w // 2, rect.y + rect.h // 2, rect.w // 2, rect.h // 2),
            )
            pygame.draw.line(screen, (200, 80, 80), rect.topleft, rect.bottomright, 2)
        else:
            pygame.draw.rect(screen, color[:3], rect, border_radius=3)
            if color[3] < 255:
                pygame.draw.line(screen, (255, 255, 255), (rect.x, rect.bottom - 3), (rect.right, rect.bottom - 3), 1)
        pygame.draw.rect(screen, COLORS.border_soft, rect, 1, border_radius=3)
        if selected:
            pygame.draw.rect(screen, (255, 255, 255), rect.inflate(4, 4), 2, border_radius=4)

    def _draw_panel(self, screen: Surface) -> None:
        if self._panel_rect is None:
            return
        small = FONTS.get_small_font()
        pygame.draw.rect(screen, COLORS.panel, self._panel_rect, border_radius=SHAPE.radius_sm)
        pygame.draw.rect(screen, COLORS.border, self._panel_rect, 1, border_radius=SHAPE.radius_sm)
        self._draw_swatches(screen)
        for i, r in enumerate(self._scope_rects):
            key = _COLOR_SCOPES[i][0]
            active = self._scope == key
            bg = COLORS.accent if active else COLORS.panel_alt
            pygame.draw.rect(screen, bg, r, border_radius=3)
            pygame.draw.rect(screen, COLORS.border_soft, r, 1, border_radius=3)
            fg = COLORS.text_on_accent if active else COLORS.text_dim
            lbl = small.render(_COLOR_SCOPES[i][1], True, fg)
            screen.blit(lbl, lbl.get_rect(center=r.center))
        if self._tol_minus is not None and self._tol_plus is not None:
            for btn, label in [(self._tol_minus, "−"), (self._tol_plus, "+")]:
                pygame.draw.rect(screen, COLORS.panel_alt, btn, border_radius=3)
                pygame.draw.rect(screen, COLORS.border_soft, btn, 1, border_radius=3)
                ts = FONTS.get_font(14).render(label, True, COLORS.text)
                screen.blit(ts, ts.get_rect(center=btn.center))
            mid = (self._tol_minus.right + self._tol_plus.x) // 2
            tlbl = small.render(str(self._tolerance), True, COLORS.text)
            screen.blit(tlbl, tlbl.get_rect(center=(mid, self._panel_rect.centery)))
        if self._apply_rect is not None:
            ready = self._src is not None
            bg = COLORS.accent if ready else COLORS.panel_alt
            pygame.draw.rect(screen, bg, self._apply_rect, border_radius=3)
            pygame.draw.rect(screen, COLORS.border_soft, self._apply_rect, 1, border_radius=3)
            fg = COLORS.text_on_accent if ready else COLORS.text_dim
            lbl = small.render("Apply", True, fg)
            screen.blit(lbl, lbl.get_rect(center=self._apply_rect.center))
        if self._custom_btn is not None:
            pygame.draw.rect(screen, COLORS.panel_alt, self._custom_btn, border_radius=3)
            pygame.draw.rect(screen, COLORS.border_soft, self._custom_btn, 1, border_radius=3)
            lbl = small.render("Custom", True, COLORS.text)
            screen.blit(lbl, lbl.get_rect(center=self._custom_btn.center))
        if self._preview_count is not None and self._src is not None:
            clf = small.render(f"{self._preview_count} px", True, COLORS.text_dim)
            screen.blit(clf, (self._panel_rect.right + 6, self._panel_rect.y + 8))

    def _draw_custom(self, screen: Surface) -> None:
        panel = self._custom_panel
        if panel is None:
            return
        small = FONTS.get_small_font()
        pygame.draw.rect(screen, COLORS.panel, panel, border_radius=SHAPE.radius_sm)
        pygame.draw.rect(screen, COLORS.border, panel, 1, border_radius=SHAPE.radius_sm)
        title = small.render(
            f"Custom {'source' if self._custom_target == 'src' else 'target'}  {_hex_of(self._active_color())}",
            True,
            COLORS.text,
        )
        screen.blit(title, (panel.x + 10, panel.y + 8))
        if self._field is not None:
            self._field.draw(screen)
        for slider in self._sliders:
            slider.draw(screen, COLORS.accent)
        if self._hex is not None:
            self._hex.draw(screen)
            if not self._hex.text:
                hint = small.render("#RRGGBB", True, COLORS.text_muted)
                screen.blit(hint, (self._hex.rect.x + 6, self._hex.rect.y + 4))
        if self._done_rect is not None:
            pygame.draw.rect(screen, COLORS.accent, self._done_rect, border_radius=3)
            lbl = small.render("Done", True, COLORS.text_on_accent)
            screen.blit(lbl, lbl.get_rect(center=self._done_rect.center))
