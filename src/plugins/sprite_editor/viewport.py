"""Viewport — draw-only canvas: sheet, grid, selection, tool overlays, header.

Never mutates the document, never owns interaction state. Coordinate
helpers are the pygame-side complement of the pure `Camera`.

Theme: all colors come from COLORS, all fonts from FONTS (repo-wide rule).
Geometry: the header bar sits at the top of the viewport; the camera
origin (world 0,0 = sheet top-left) is one header-height below it, so the
sheet is never covered by the header.
"""

from __future__ import annotations

import pygame
from pygame import Rect, Surface

from widgets.ui.theme import COLORS, FONTS

from .camera import Camera
from .document import Document
from .overlays import draw_selection_fill
from .selection import Selection

MAX_CACHE_SIZE = 8192
HEADER_H = 24


class Viewport:
    def __init__(self, rect: Rect, doc: Document, camera: Camera, selection: Selection):
        self.rect = Rect(rect)
        self.doc = doc
        self.camera = camera
        self.selection = selection
        self._sheet_cache: dict[tuple, Surface] = {}
        self._last_sheet_key: tuple | None = None
        self._last_sheet: Surface | None = None
        self._sync_camera()

    # -- geometry ------------------------------------------------------
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

    # -- coordinate helpers --------------------------------------------
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

    def cell_screen_rect(self, col: int, row: int) -> Rect:
        rect = self.doc.tile_rect(col, row)
        sx, sy, sw, sh = self.camera.world_to_screen_rect(rect.x, rect.y, rect.w, rect.h)
        return Rect(round(sx), round(sy), round(sw), round(sh))

    # -- rendering -----------------------------------------------------
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
            self._draw_grid(screen)
            draw_selection_fill(screen, self.doc, self.camera, self.selection)
            if tool is not None:
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
        zoom_bucket = round(self.camera.zoom * 20) / 20
        # revision: in-place mutations (move/paste/flip/cut) leave the same
        # surface object + size, so it must be part of the cache key
        key = (id(surface), self.doc.revision, surface.get_size(), zoom_bucket)
        if key != self._last_sheet_key or self._last_sheet is None:
            w, h = surface.get_size()
            sw = min(MAX_CACHE_SIZE, max(1, round(w * zoom_bucket)))
            sh = min(MAX_CACHE_SIZE, max(1, round(h * zoom_bucket)))
            scaled = pygame.transform.smoothscale(surface, (sw, sh))
            self._last_sheet_key = key
            self._last_sheet = scaled
        sx, sy = self.camera.world_to_screen(0, 0)
        screen.blit(self._last_sheet, (round(sx), round(sy)))

    def _draw_grid(self, screen: Surface) -> None:
        """Full-canvas graph-paper grid, like TileGrid: lines span the whole
        visible content area (including past the sheet edge), aligned to the
        world origin."""
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
        for col in range(c0, c1 + 1):
            sx, _ = self.camera.world_to_screen(col * self.doc.tw, 0)
            pygame.draw.line(screen, color, (round(sx), content.y), (round(sx), content.bottom))
        for row in range(r0, r1 + 1):
            _, sy = self.camera.world_to_screen(0, row * self.doc.th)
            pygame.draw.line(screen, color, (content.x, round(sy)), (content.right, round(sy)))

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
