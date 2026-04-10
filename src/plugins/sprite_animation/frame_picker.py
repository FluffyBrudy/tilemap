"""
Frame Picker — click tiles on a spritesheet to add animation frames.

Displays the spritesheet with a grid overlay. Left-click a tile to
fire on_frame_clicked(variant_id). Frames used in the current
animation are highlighted with a tinted overlay.
"""

from __future__ import annotations

from typing import Callable, Optional, Set, Tuple

import pygame
from pygame import Rect


# ---------------------------------------------------------------------------
# Inline theme constants (avoids hard dependency on widgets.ui.theme)
# ---------------------------------------------------------------------------
_COLORS = {
    "bg": (25, 27, 30),
    "grid": (255, 255, 255),
    "hover": (220, 180, 80),
    "highlight": (80, 180, 120),
    "border": (60, 62, 65),
    "text": (230, 230, 230),
    "text_dim": (140, 140, 140),
    "header": (40, 42, 46),
    "index_bg": (0, 0, 0),
}


class FramePicker:
    """Spritesheet grid view — click tiles to select animation frames."""

    def __init__(
        self,
        rect: Rect,
        surface: pygame.Surface,
        tile_size: Tuple[int, int],
    ):
        self.rect = rect
        self.surface = surface
        self.tile_size = tile_size

        self._recalc_grid()

        # View state
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self.zoom: float = 1.0

        # Interaction
        self.hover_index: int = -1
        self._panning = False
        self._pan_start = (0, 0)
        self._pan_start_offset = (0.0, 0.0)

        # Highlighted frames (belonging to the active animation)
        self.highlighted: Set[int] = set()

        # Callback fired when user clicks a tile
        self.on_frame_clicked: Optional[Callable[[int], None]] = None

        # Fonts (created lazily so pygame.init() can happen anytime before draw)
        self._font: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None

        # Checkerboard tile (8×8) cached
        self._checker: Optional[pygame.Surface] = None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_surface(self, surface: pygame.Surface, tile_size: Optional[Tuple[int, int]] = None) -> None:
        self.surface = surface
        if tile_size:
            self.tile_size = tile_size
        self._recalc_grid()

    def set_highlighted(self, indices: Set[int]) -> None:
        self.highlighted = indices

    def resize(self, rect: Rect) -> None:
        self.rect = rect

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse = pygame.mouse.get_pos()
        if not self.rect.collidepoint(mouse) and event.type not in (
            pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION
        ):
            return False

        # Right-click drag to pan
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.rect.collidepoint(mouse):
                self._panning = True
                self._pan_start = mouse
                self._pan_start_offset = (self.offset_x, self.offset_y)
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            if self._panning:
                self._panning = False
                return True

        if event.type == pygame.MOUSEMOTION and self._panning:
            dx = mouse[0] - self._pan_start[0]
            dy = mouse[1] - self._pan_start[1]
            self.offset_x = self._pan_start_offset[0] + dx
            self.offset_y = self._pan_start_offset[1] + dy
            return True

        # Left-click to select a frame
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse):
                idx = self._index_at(mouse)
                if idx >= 0 and self.on_frame_clicked:
                    self.on_frame_clicked(idx)
                return True

        # Scroll to pan / Ctrl+scroll to zoom
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(mouse):
            mods = pygame.key.get_mods()
            if mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL):
                old = self.zoom
                self.zoom *= 1.12 if event.y > 0 else 0.88
                self.zoom = max(0.25, min(self.zoom, 8.0))
                # Zoom toward mouse
                rel_x = mouse[0] - self.rect.x - self.offset_x
                rel_y = mouse[1] - self.rect.y - self.offset_y
                scale = self.zoom / old
                self.offset_x -= rel_x * (scale - 1)
                self.offset_y -= rel_y * (scale - 1)
            else:
                shift = mods & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT)
                if shift:
                    self.offset_x += event.y * 30
                else:
                    self.offset_y += event.y * 30
            return True

        # Track hover
        if event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(mouse):
                self.hover_index = self._index_at(mouse)
            else:
                self.hover_index = -1

        return False

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()
        clip = screen.get_clip()
        screen.set_clip(self.rect)

        # Background (checkerboard)
        self._draw_checker_bg(screen)

        tw, th = self.tile_size
        z = self.zoom
        img_x = self.rect.x + self.offset_x
        img_y = self.rect.y + self.offset_y
        scaled_w = int(self.surface.get_width() * z)
        scaled_h = int(self.surface.get_height() * z)

        # Draw scaled spritesheet
        if scaled_w > 0 and scaled_h > 0:
            scaled = pygame.transform.smoothscale(self.surface, (scaled_w, scaled_h))
            screen.blit(scaled, (img_x, img_y))

        # Grid lines
        cell_w = tw * z
        cell_h = th * z
        grid_alpha_surf = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        for c in range(self.cols + 1):
            x = int(img_x + c * cell_w) - self.rect.x
            pygame.draw.line(grid_alpha_surf, (*_COLORS["grid"], 40), (x, 0), (x, self.rect.h))
        for r in range(self.rows + 1):
            y = int(img_y + r * cell_h) - self.rect.y
            pygame.draw.line(grid_alpha_surf, (*_COLORS["grid"], 40), (0, y), (self.rect.w, y))
        screen.blit(grid_alpha_surf, self.rect.topleft)

        # Highlighted tiles (used in current animation)
        for idx in self.highlighted:
            col = idx % self.cols
            row = idx // self.cols
            hr = Rect(
                int(img_x + col * cell_w),
                int(img_y + row * cell_h),
                int(cell_w),
                int(cell_h),
            )
            hl_surf = pygame.Surface((hr.w, hr.h), pygame.SRCALPHA)
            hl_surf.fill((*_COLORS["highlight"], 55))
            screen.blit(hl_surf, hr.topleft)
            pygame.draw.rect(screen, _COLORS["highlight"], hr, 1)

        # Hover highlight
        if self.hover_index >= 0:
            col = self.hover_index % self.cols
            row = self.hover_index // self.cols
            hr = Rect(
                int(img_x + col * cell_w),
                int(img_y + row * cell_h),
                int(cell_w),
                int(cell_h),
            )
            pygame.draw.rect(screen, _COLORS["hover"], hr, 2)
            # Index label
            label = self._font_sm.render(str(self.hover_index), True, _COLORS["text"])
            lx = hr.x + 2
            ly = hr.y + 2
            bg_rect = Rect(lx - 1, ly - 1, label.get_width() + 4, label.get_height() + 2)
            bg = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 160))
            screen.blit(bg, bg_rect.topleft)
            screen.blit(label, (lx, ly))

        # Header label
        hdr = Rect(self.rect.x, self.rect.y, self.rect.w, 22)
        hdr_bg = pygame.Surface((hdr.w, hdr.h), pygame.SRCALPHA)
        hdr_bg.fill((*_COLORS["header"], 200))
        screen.blit(hdr_bg, hdr.topleft)
        title = self._font.render(
            f"Spritesheet  ({self.cols}×{self.rows} = {self.total_frames} tiles)  Zoom: {self.zoom:.1f}x",
            True, _COLORS["text"],
        )
        screen.blit(title, (self.rect.x + 6, self.rect.y + 3))

        screen.set_clip(clip)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _recalc_grid(self) -> None:
        tw, th = self.tile_size
        self.cols = max(1, self.surface.get_width() // tw)
        self.rows = max(1, self.surface.get_height() // th)
        self.total_frames = self.cols * self.rows

    def _index_at(self, mouse: Tuple[int, int]) -> int:
        """Return tile index at the given screen position or -1."""
        z = self.zoom
        tw, th = self.tile_size
        rel_x = (mouse[0] - self.rect.x - self.offset_x) / z
        rel_y = (mouse[1] - self.rect.y - self.offset_y) / z
        if rel_x < 0 or rel_y < 0:
            return -1
        col = int(rel_x // tw)
        row = int(rel_y // th)
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return row * self.cols + col
        return -1

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("Arial", 13)
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("Arial", 11)

    def _draw_checker_bg(self, screen: pygame.Surface) -> None:
        if self._checker is None:
            sz = 8
            self._checker = pygame.Surface((sz * 2, sz * 2))
            c1, c2 = (35, 35, 35), (45, 45, 45)
            self._checker.fill(c1)
            pygame.draw.rect(self._checker, c2, (sz, 0, sz, sz))
            pygame.draw.rect(self._checker, c2, (0, sz, sz, sz))
        for y in range(self.rect.y, self.rect.bottom, self._checker.get_height()):
            for x in range(self.rect.x, self.rect.right, self._checker.get_width()):
                screen.blit(self._checker, (x, y))
