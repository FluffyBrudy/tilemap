"""Viewport — draw-only canvas: sheet, grid, selection, tool overlays, header.

Never mutates the document, never owns interaction state. Coordinate
helpers are the pygame-side complement of the pure `Camera`.

Theme: all colors come from COLORS, all fonts from FONTS (repo-wide rule).
Geometry: the header bar sits at the top of the viewport; the camera
origin (world 0,0 = sheet top-left) is one header-height below it, so the
sheet is never covered by the header.
"""

from __future__ import annotations

import math

import pygame
from pygame import Rect, Surface

from widgets.ui.theme import COLORS, FONTS

from .camera import Camera
from .document import Document
from .overlays import draw_alpha_fill, draw_selection_fill, snapped_origin
from .selection import Selection

MAX_CACHE_SIZE = 8192
HEADER_H = 24


class Viewport:
    def __init__(self, rect: Rect, doc: Document, camera: Camera, selection: Selection):
        self.rect = Rect(rect)
        self.doc = doc
        self.camera = camera
        self.selection = selection
        self.show_grid = True
        self.show_regions = True
        self._sheet_cache: dict[tuple, Surface] = {}
        self._last_sheet_key: tuple | None = None
        self._last_sheet: Surface | None = None
        self._sync_camera()

    def resize(self, rect: Rect) -> None:
        self.rect = Rect(rect)
        self._sync_camera()

    @property
    def content_rect(self) -> Rect:
        """The sheet area below the header bar."""
        return Rect(
            self.rect.x,
            self.rect.y + HEADER_H,
            self.rect.w,
            max(0, self.rect.h - HEADER_H),
        )

    def _sync_camera(self) -> None:
        # world (0,0) sits at the bottom edge of the header bar
        self.camera.viewport_x = float(self.rect.x)
        self.camera.viewport_y = float(self.rect.y + HEADER_H)

    def world_to_screen(self, x: float, y: float) -> tuple[float, float]:
        return self.camera.world_to_screen(x, y)

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return self.camera.screen_to_world(sx, sy)

    def cell_at_screen(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        wx, wy = self.screen_to_world(*pos)
        return self.doc.cell_at(wx, wy)

    def cell_at_screen_unbounded(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        """Cell under a screen point, allowing cells past the canvas edge
        (used for moves/pastes that may expand the canvas)."""
        wx, wy = self.screen_to_world(*pos)
        return self.doc.cell_at_unbounded(wx, wy)

    def index_at_screen(self, pos: tuple[int, int]) -> int:
        wx, wy = self.screen_to_world(*pos)
        return self.doc.index_at(wx, wy)

    def sheet_screen_rect(self) -> Rect | None:
        """Edge-snapped screen rect of the whole sheet.

        Snaps offsets relative to the world-origin (not absolute screen
        positions) so the sheet's right/bottom edge lands exactly on the
        grid line for `cols*tw` / `rows*th` at every zoom/pan.
        """
        if self.doc.surface is None:
            return None
        w, h = self.doc.size
        x0, y0 = snapped_origin(self.camera)
        zoom = self.camera.zoom
        return Rect(x0, y0, round(w * zoom), round(h * zoom))

    def world_rect_to_screen(self, x: float, y: float, w: float, h: float) -> Rect:
        """Snap a world rect relative to the world origin (shared rule)."""
        x0, y0 = snapped_origin(self.camera)
        zoom = self.camera.zoom
        rx0 = x0 + round(x * zoom)
        ry0 = y0 + round(y * zoom)
        rx1 = x0 + round((x + w) * zoom)
        ry1 = y0 + round((y + h) * zoom)
        return Rect(rx0, ry0, max(0, rx1 - rx0), max(0, ry1 - ry0))

    def cell_screen_rect(self, col: int, row: int) -> Rect:
        rect = self.doc.tile_rect(col, row)
        return self.world_rect_to_screen(rect.x, rect.y, rect.w, rect.h)

    def draw(self, screen: Surface, tool) -> None:
        pygame.draw.rect(screen, COLORS.panel, self.rect)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)

        self._draw_header(screen)

        # canvas rendering is clipped to the content area (below the header)
        # so the sheet/grid/overlays can never bleed into the header or the
        # toolbar, no matter how far the user pans (same pattern as TileGrid)
        content = self.content_rect
        prev_clip = screen.get_clip()
        screen.set_clip(content)
        try:
            if not self.doc.has_canvas:
                self._draw_empty(screen)
                return
            self._draw_sheet(screen)
            self._draw_canvas_bounds(screen)
            if self.show_grid:
                self._draw_grid(screen)
            draw_selection_fill(screen, self.doc, self.camera, self.selection)
            if tool is not None:
                if self.show_regions or getattr(tool, "overlay_kind", "") != "regions":
                    tool.draw_overlay(screen)
        finally:
            screen.set_clip(prev_clip)

    def _draw_empty(self, screen: Surface) -> None:
        font = FONTS.get_medium_font()
        text = font.render("No spritesheet loaded — click Open", True, COLORS.text_muted)
        screen.blit(text, text.get_rect(center=self.content_rect.center))

    def _draw_sheet(self, screen: Surface) -> None:
        surface = self.doc.surface
        if surface is None:
            return
        zoom = self.camera.zoom
        w, h = surface.get_size()
        # exact-zoom pixel size: quantized only by the resulting pixel
        # dimensions (not by the zoom float), so the sheet can never drift
        # off the grid between zoom steps yet the cache stays stable.
        # revision: in-place mutations (move/paste/flip/cut) leave the same
        # surface object + size, so it must be part of the cache key
        sw, sh = max(1, round(w * zoom)), max(1, round(h * zoom))
        key = (id(surface), self.doc.revision, surface.get_size(), sw, sh)
        if key != self._last_sheet_key or self._last_sheet is None:
            cw = min(MAX_CACHE_SIZE, sw)
            ch = min(MAX_CACHE_SIZE, sh)
            scaled = pygame.transform.smoothscale(surface, (cw, ch))
            self._last_sheet_key = key
            self._last_sheet = scaled
        dest = self.sheet_screen_rect()
        if dest is None:
            return
        true_w, true_h = dest.w, dest.h
        if (true_w, true_h) != self._last_sheet.get_size():
            # over the GPU-friendly cap: scale only the visible source
            # patch to the on-screen destination size, so dimensions past
            # the cap never allocate a full-size intermediate surface.
            try:
                sx, sy = self.camera.world_to_screen(0, 0)
                scale = zoom if zoom > 0 else self.camera.zoom
                dest_rect = Rect(dest.x, dest.y, max(1, true_w), max(1, true_h))
                vis = dest_rect.clip(self.content_rect)
                if vis.w <= 0 or vis.h <= 0:
                    return
                fx0 = (vis.x - sx) / scale
                fy0 = (vis.y - sy) / scale
                fx1 = (vis.right - sx) / scale
                fy1 = (vis.bottom - sy) / scale
                ix0 = max(0, min(w, math.floor(fx0)))
                iy0 = max(0, min(h, math.floor(fy0)))
                ix1 = max(0, min(w, math.ceil(fx1)))
                iy1 = max(0, min(h, math.ceil(fy1)))
                src_rect = Rect(ix0, iy0, max(0, ix1 - ix0), max(0, iy1 - iy0))
                src_rect = src_rect.clip(surface.get_rect())
                if src_rect.w <= 0 or src_rect.h <= 0:
                    return
                patch = surface.subsurface(src_rect).copy()
                scaled = pygame.transform.smoothscale(patch, (max(1, vis.w), max(1, vis.h)))
            except (ValueError, pygame.error):
                return
            screen.blit(scaled, vis.topleft)
        else:
            screen.blit(self._last_sheet, dest.topleft)

    def _draw_canvas_bounds(self, screen: Surface) -> None:
        """Hint-only canvas limit border (never blocks drawing).

        Top/left world edges are a hard wall (negative cells are rejected
        by the document); bottom/right grows transparently. The border
        encodes that: warning rails on top+left, accent rails on
        bottom+right with small "+" growth ticks at the live corner.
        """
        dest = self.sheet_screen_rect()
        if dest is None or dest.w <= 0 or dest.h <= 0:
            return
        content = self.content_rect
        # dim the out-of-canvas area so the live extent reads at any pan
        dim = 56
        if dest.x > content.x:
            draw_alpha_fill(
                screen,
                Rect(content.x, content.y, dest.x - content.x, content.h),
                (0, 0, 0), dim,
            )
        if dest.y > content.y:
            draw_alpha_fill(
                screen,
                Rect(max(content.x, dest.x), content.y,
                     min(content.right, dest.right) - max(content.x, dest.x),
                     dest.y - content.y),
                (0, 0, 0), dim,
            )
        right_w = content.right - dest.right
        if right_w > 0:
            draw_alpha_fill(
                screen, Rect(dest.right, content.y, right_w, content.h), (0, 0, 0), dim,
            )
        bottom_h = content.bottom - dest.bottom
        if bottom_h > 0:
            draw_alpha_fill(
                screen,
                Rect(max(content.x, dest.x), dest.bottom,
                     min(content.right, dest.right) - max(content.x, dest.x), bottom_h),
                (0, 0, 0), dim,
            )
        # structural rails: warning = blocked top/left, accent = live edge
        pygame.draw.line(screen, COLORS.warning, dest.topleft, dest.topright, 2)
        pygame.draw.line(screen, COLORS.warning, dest.topleft, dest.bottomleft, 2)
        pygame.draw.line(screen, COLORS.accent_active, dest.bottomleft, dest.bottomright, 2)
        pygame.draw.line(screen, COLORS.accent_active, dest.topright, dest.bottomright, 2)
        # origin L-marker (the hard 0,0 corner) + growth ticks bottom-right
        o = dest.topleft
        pygame.draw.lines(screen, COLORS.warning, False,
                          [(o[0], o[1] + 10), o, (o[0] + 10, o[1])], 3)
        br = dest.bottomright
        tick = 7
        pygame.draw.line(screen, COLORS.accent_active,
                         (br[0] - tick, br[1]), (br[0] + tick, br[1]), 2)
        pygame.draw.line(screen, COLORS.accent_active,
                         (br[0], br[1] - tick), (br[0], br[1] + tick), 2)

    def _draw_grid(self, screen: Surface) -> None:
        """Full-canvas graph-paper grid, like TileGrid: lines span the whole
        visible content area (including past the sheet edge), aligned to the
        world origin via the shared snapped-origin rule."""
        surface = self.doc.surface
        if surface is None:
            return
        content = self.content_rect
        left, top = self.screen_to_world(content.x, content.y)
        right, bottom = self.screen_to_world(content.right, content.bottom)
        c0 = int(left // self.doc.tw)
        c1 = int(right // self.doc.tw)
        r0 = int(top // self.doc.th)
        r1 = int(bottom // self.doc.th)
        color = COLORS.text_muted
        x0, y0 = snapped_origin(self.camera)
        zoom = self.camera.zoom
        for col in range(c0, c1 + 1):
            px = x0 + round(col * self.doc.tw * zoom)
            pygame.draw.line(screen, color, (px, content.y), (px, content.bottom))
        for row in range(r0, r1 + 1):
            py = y0 + round(row * self.doc.th * zoom)
            pygame.draw.line(screen, color, (content.x, py), (content.right, py))

    def _draw_header(self, screen: Surface) -> None:
        """Canvas header data — concise, no floating labels."""
        header_rect = Rect(self.rect.x, self.rect.y, self.rect.w, HEADER_H)
        pygame.draw.rect(screen, COLORS.header, header_rect)
        pygame.draw.line(
            screen,
            COLORS.border_soft,
            header_rect.bottomleft,
            header_rect.bottomright,
        )

        parts: list[str] = []
        if self.doc.has_canvas:
            w, h = self.doc.size
            parts.append(f"{w}×{h}")
            parts.append(f"Tiles {self.doc.cols}×{self.doc.rows}")
            parts.append(f"{self.doc.tw}×{self.doc.th}")
            parts.append(f"{self.camera.zoom * 100:.0f}%")
            if self.selection:
                parts.append(f"selected: {len(self.selection)}")
        else:
            parts.append("blank canvas")
        font = FONTS.get_small_font()
        label = font.render("   ".join(parts), True, COLORS.text)
        screen.blit(label, (self.rect.x + 6, header_rect.centery - label.get_height() // 2 + 1))
