"""
SpritesheetGrid — reusable spritesheet viewer with tile selection and pixel ops.

Provides:
  - Grid display with zoom/pan
  - Tile selection (click, Ctrl+click toggle, drag rubber-band)
  - extract_tile / write_tile for pixel-level manipulation
  - flip_selected, scale, copy_selected, paste_at
  - save_png
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pygame
from pygame import Rect, Surface, SRCALPHA


TOP_BAR_H = 24
_COLORS = {
    "bg": (25, 27, 30),
    "grid": (200, 200, 200),
    "hover": (220, 180, 80),
    "selected": (80, 160, 220),
    "selected_dim": (60, 120, 180),
    "border": (60, 62, 65),
    "text": (230, 230, 230),
    "text_dim": (140, 140, 140),
    "header": (40, 42, 46),
}


class SpritesheetGrid:
    """Grid overlay + tile selection for a spritesheet surface."""

    def __init__(
        self,
        rect: Rect,
        surface: Surface,
        tile_size: Tuple[int, int],
    ):
        self.rect = rect
        self.surface = surface
        self.tile_size = tile_size

        self.grid_offset_x: int = 0
        self.grid_offset_y: int = 0
        self._recalc_grid()

        # View
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self.zoom: float = 1.0

        # Selection
        self.selected_indices: Set[int] = set()

        # Interaction
        self.hover_index: int = -1
        self._panning = False
        self._pan_start = (0, 0)
        self._pan_start_offset = (0.0, 0.0)
        self._drag_selecting = False
        self._drag_start_col: int = -1
        self._drag_start_row: int = -1
        self._drag_end_col: int = -1
        self._drag_end_row: int = -1

        # Paste mode (external manager sets this)
        self.paste_preview_idx: int = -1

        # Undo / Redo stacks (surface copies)
        self._undo_stack: List[Surface] = []
        self._redo_stack: List[Surface] = []
        self._max_undo: int = 50

        self._font: Optional[pygame.font.Font] = None

    # ------------------------------------------------------------------
    # Grid geometry
    # ------------------------------------------------------------------

    def _recalc_grid(self) -> None:
        tw, th = self.tile_size
        avail_w = self.surface.get_width() - self.grid_offset_x
        avail_h = self.surface.get_height() - self.grid_offset_y
        self.cols = max(1, avail_w // tw)
        self.rows = max(1, avail_h // th)
        self.total_frames = self.cols * self.rows

    # ------------------------------------------------------------------
    # Public: surface / tile_size
    # ------------------------------------------------------------------

    def set_surface(
        self, surface: Surface, tile_size: Optional[Tuple[int, int]] = None
    ) -> None:
        self.surface = surface
        if tile_size:
            self.tile_size = tile_size
        self._recalc_grid()

    def set_tile_size(self, tw: int, th: int) -> None:
        self.tile_size = (tw, th)
        self._recalc_grid()

    def get_surface(self) -> Surface:
        return self.surface

    # ------------------------------------------------------------------
    # Public: selection
    # ------------------------------------------------------------------

    def select_single(self, idx: int) -> None:
        self.selected_indices = {idx} if 0 <= idx < self.total_frames else set()

    def toggle_select(self, idx: int) -> None:
        if idx in self.selected_indices:
            self.selected_indices.discard(idx)
        else:
            self.selected_indices.add(idx)

    def clear_selection(self) -> None:
        self.selected_indices.clear()

    def has_selection(self) -> bool:
        return len(self.selected_indices) > 0

    def get_selected(self) -> List[int]:
        return sorted(self.selected_indices)

    # ------------------------------------------------------------------
    # Public: coordinate helpers
    # ------------------------------------------------------------------

    def grid_coords(self, idx: int) -> Tuple[int, int]:
        return (idx % self.cols, idx // self.cols)

    def index_at(self, idx: int) -> int:
        """Validate index is in range, return -1 if not."""
        return idx if 0 <= idx < self.total_frames else -1

    def tile_screen_rect(self, idx: int) -> Optional[Rect]:
        if idx < 0 or idx >= self.total_frames:
            return None
        tw, th = self.tile_size
        z = self.zoom
        col, row = self.grid_coords(idx)
        cell_w = tw * z
        cell_h = th * z
        img_x = self.rect.x + self.offset_x
        img_y = self.rect.y + TOP_BAR_H + self.offset_y
        return Rect(
            int(img_x + (self.grid_offset_x + col * tw) * z),
            int(img_y + (self.grid_offset_y + row * th) * z),
            int(cell_w),
            int(cell_h),
        )

    def index_at_pos(self, mouse: Tuple[int, int]) -> int:
        """Return tile index at screen position, or -1."""
        if mouse[1] < self.rect.y + TOP_BAR_H:
            return -1
        z = self.zoom
        tw, th = self.tile_size
        W = float(self.surface.get_width())
        H = float(self.surface.get_height())

        rel_x = (mouse[0] - self.rect.x - self.offset_x) / z
        rel_y = (mouse[1] - self.rect.y - TOP_BAR_H - self.offset_y) / z

        eps = max(0.25, 0.5 / max(z, 0.01))
        if rel_x < 0 or rel_y < 0:
            return -1
        if rel_x >= W and rel_x < W + eps:
            rel_x = max(0.0, W - 1e-6)
        if rel_y >= H and rel_y < H + eps:
            rel_y = max(0.0, H - 1e-6)
        if rel_x >= W or rel_y >= H:
            return -1

        gx = rel_x - self.grid_offset_x
        gy = rel_y - self.grid_offset_y
        if gx < 0 or gy < 0:
            return -1

        gw = self.cols * tw
        gh = self.rows * th
        if gx >= gw and gx < gw + eps:
            gx = max(0.0, gw - 1e-6)
        if gy >= gh and gy < gh + eps:
            gy = max(0.0, gh - 1e-6)
        if gx >= gw or gy >= gh:
            return -1

        col = int(math.floor(gx / tw))
        row = int(math.floor(gy / th))
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return row * self.cols + col
        return -1

    def _grid_to_screen(self, col: int, row: int) -> Tuple[float, float]:
        tw, th = self.tile_size
        z = self.zoom
        return (
            self.rect.x + self.offset_x + (self.grid_offset_x + col * tw) * z,
            self.rect.y + TOP_BAR_H + self.offset_y + (self.grid_offset_y + row * th) * z,
        )

    # ------------------------------------------------------------------
    # Public: undo / redo
    # ------------------------------------------------------------------

    def snapshot(self) -> None:
        """Save current surface state for undo."""
        self._undo_stack.append(self.surface.copy())
        self._redo_stack.clear()
        if len(self._undo_stack) > self._max_undo:
            self._undo_stack.pop(0)

    def undo(self) -> bool:
        """Restore previous surface state. Returns True if state changed."""
        if not self._undo_stack:
            return False
        self._redo_stack.append(self.surface.copy())
        self.surface = self._undo_stack.pop()
        self._recalc_grid()
        return True

    def redo(self) -> bool:
        """Restore next surface state. Returns True if state changed."""
        if not self._redo_stack:
            return False
        self._undo_stack.append(self.surface.copy())
        self.surface = self._redo_stack.pop()
        self._recalc_grid()
        return True

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    # ------------------------------------------------------------------
    # Public: tile pixel ops
    # ------------------------------------------------------------------

    def extract_tile(self, idx: int) -> Optional[Surface]:
        """Return a copy of the tile's pixel region, or None."""
        if idx < 0 or idx >= self.total_frames:
            return None
        tw, th = self.tile_size
        col, row = self.grid_coords(idx)
        src = Rect(
            self.grid_offset_x + col * tw,
            self.grid_offset_y + row * th,
            tw, th,
        )
        if self.surface.get_rect().contains(src):
            return self.surface.subsurface(src).copy()
        return None

    def write_tile(self, idx: int, tile_surf: Surface) -> None:
        """Blit a tile-sized surface onto the spritesheet at grid position idx."""
        if idx < 0 or idx >= self.total_frames:
            return
        tw, th = self.tile_size
        if tile_surf.get_size() != (tw, th):
            tile_surf = pygame.transform.scale(tile_surf, (tw, th))
        col, row = self.grid_coords(idx)
        dst_rect = Rect(
            self.grid_offset_x + col * tw,
            self.grid_offset_y + row * th,
            tw, th,
        )
        # Fill destination with transparent black (fill replaces, blit blends)
        self.surface.fill((0, 0, 0, 0), dst_rect)
        self.surface.blit(tile_surf, dst_rect)

    def flip_selected(self, flip_x: bool, flip_y: bool) -> None:
        """In-place pixel flip of each selected tile."""
        if not self.selected_indices:
            return
        self.snapshot()
        for idx in list(self.selected_indices):
            tile = self.extract_tile(idx)
            if tile:
                flipped = pygame.transform.flip(tile, flip_x, flip_y)
                self.write_tile(idx, flipped)

    def scale(self, factor: float) -> None:
        """Resize the spritesheet and tile_size by factor."""
        if factor <= 0:
            return
        self.snapshot()
        w = self.surface.get_width()
        h = self.surface.get_height()
        new_w = max(1, int(w * factor))
        new_h = max(1, int(h * factor))
        self.surface = pygame.transform.smoothscale(self.surface, (new_w, new_h))
        self.tile_size = (max(1, int(self.tile_size[0] * factor)),
                          max(1, int(self.tile_size[1] * factor)))
        self._recalc_grid()

    def copy_selected(self) -> Dict[int, Surface]:
        """Return {local_index: tile_surface} for each selected tile."""
        result: Dict[int, Surface] = {}
        for idx in sorted(self.selected_indices):
            tile = self.extract_tile(idx)
            if tile:
                result[idx] = tile
        return result

    def paste_at(self, target_idx: int, tiles: Dict[int, Surface]) -> None:
        """Write previously copied tiles starting at target grid position.
        
        Tiles are written in sorted source-index order, filling left-to-right
        top-to-bottom from the target cell. Out-of-bounds writes are skipped.
        """
        if not tiles or target_idx < 0 or target_idx >= self.total_frames:
            return
        self.snapshot()
        sorted_src = sorted(tiles.keys())
        for offset, src_idx in enumerate(sorted_src):
            dst = target_idx + offset
            if dst >= self.total_frames:
                break
            tile = tiles[src_idx]
            self.write_tile(dst, tile)
        # Select the newly pasted tiles
        self.selected_indices = {
            target_idx + offset
            for offset in range(len(sorted_src))
            if target_idx + offset < self.total_frames
        }

    def save_png(self, path: Path) -> None:
        """Write current surface to a PNG file."""
        pygame.image.save(self.surface, str(path))

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.rect.collidepoint(mouse) and mouse[1] >= self.rect.y + TOP_BAR_H:
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

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse) and mouse[1] >= self.rect.y + TOP_BAR_H:
                idx = self.index_at_pos(mouse)
                mods = pygame.key.get_mods()
                if mods & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA):
                    if idx >= 0:
                        self.toggle_select(idx)
                    return True
                if idx >= 0:
                    # Start drag selection
                    self._drag_selecting = True
                    col, row = self.grid_coords(idx)
                    self._drag_start_col = col
                    self._drag_start_row = row
                    self._drag_end_col = col
                    self._drag_end_row = row
                    self.selected_indices = {idx}
                else:
                    self.clear_selection()
                return True

        if event.type == pygame.MOUSEMOTION and self._drag_selecting:
            idx = self.index_at_pos(mouse)
            if idx >= 0:
                col, row = self.grid_coords(idx)
                self._drag_end_col = col
                self._drag_end_row = row
                min_c = min(self._drag_start_col, self._drag_end_col)
                max_c = max(self._drag_start_col, self._drag_end_col)
                min_r = min(self._drag_start_row, self._drag_end_row)
                max_r = max(self._drag_start_row, self._drag_end_row)
                sel = set()
                for r in range(min_r, max_r + 1):
                    for c in range(min_c, max_c + 1):
                        if 0 <= r < self.rows and 0 <= c < self.cols:
                            sel.add(r * self.cols + c)
                self.selected_indices = sel
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._drag_selecting:
                self._drag_selecting = False
                return True

        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(mouse):
            if mouse[1] < self.rect.y + TOP_BAR_H:
                return True
            mods = pygame.key.get_mods()
            if mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL):
                old = self.zoom
                if event.y != 0:
                    self.zoom *= 1.12 if event.y > 0 else 0.88
                    self.zoom = max(0.25, min(self.zoom, 8.0))
                    rel_x = mouse[0] - self.rect.x - self.offset_x
                    rel_y = mouse[1] - self.rect.y - TOP_BAR_H - self.offset_y
                    scale_factor = self.zoom / old
                    self.offset_x -= rel_x * (scale_factor - 1)
                    self.offset_y -= rel_y * (scale_factor - 1)
                if event.x != 0:
                    self.offset_x += event.x * 30
            else:
                if event.y != 0:
                    self.offset_y += event.y * 30
                if event.x != 0:
                    self.offset_x += event.x * 30
            return True

        if event.type == pygame.KEYDOWN and self.rect.collidepoint(mouse):
            mods = pygame.key.get_mods()
            if not (mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL |
                            pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT)):
                step = 1.15
                if event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                    old = self.zoom
                    self.zoom = min(self.zoom * step, 8.0)
                    cx = self.rect.w // 2
                    cy = self.rect.h // 2
                    s = self.zoom / old
                    self.offset_x -= (cx - self.offset_x) * (s - 1)
                    self.offset_y -= (cy - self.offset_y) * (s - 1)
                    return True
                elif event.key == pygame.K_MINUS:
                    old = self.zoom
                    self.zoom = max(self.zoom / step, 0.25)
                    cx = self.rect.w // 2
                    cy = self.rect.h // 2
                    s = self.zoom / old
                    self.offset_x -= (cx - self.offset_x) * (s - 1)
                    self.offset_y -= (cy - self.offset_y) * (s - 1)
                    return True
                elif event.key == pygame.K_0:
                    self.zoom = 1.0
                    self.offset_x = 0.0
                    self.offset_y = 0.0
                    return True
                pan = 20
                if event.key == pygame.K_LEFT:
                    self.offset_x += pan
                    return True
                elif event.key == pygame.K_RIGHT:
                    self.offset_x -= pan
                    return True
                elif event.key == pygame.K_UP:
                    self.offset_y += pan
                    return True
                elif event.key == pygame.K_DOWN:
                    self.offset_y -= pan
                    return True

        if event.type == pygame.MOUSEMOTION:
            if self.rect.collidepoint(mouse) and mouse[1] >= self.rect.y + TOP_BAR_H:
                self.hover_index = self.index_at_pos(mouse)
            else:
                self.hover_index = -1

        return False

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, screen: Surface) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("Arial", 12)

        clip = screen.get_clip()
        screen.set_clip(self.rect)

        # Background
        screen.fill(_COLORS["bg"], self.rect)

        tw, th = self.tile_size
        z = self.zoom
        img_x = self.rect.x + self.offset_x
        img_y = self.rect.y + TOP_BAR_H + self.offset_y
        s_w = self.surface.get_width()
        s_h = self.surface.get_height()
        scaled_w = max(1, int(s_w * z))
        scaled_h = max(1, int(s_h * z))

        # Scaled spritesheet
        if scaled_w > 0 and scaled_h > 0:
            scaled = pygame.transform.smoothscale(self.surface, (scaled_w, scaled_h))
            screen.blit(scaled, (img_x, img_y))

        cell_w = tw * z
        cell_h = th * z
        sheet_screen_rect = Rect(int(img_x), int(img_y), scaled_w, scaled_h)
        grid_start_x = img_x + self.grid_offset_x * z
        grid_start_y = img_y + self.grid_offset_y * z

        grid_clip = sheet_screen_rect.clip(self.rect)
        if grid_clip.width > 0 and grid_clip.height > 0:
            ga = pygame.Surface((grid_clip.w, grid_clip.h), pygame.SRCALPHA)
            # Vertical lines
            for c in range(self.cols + 1):
                xw = grid_start_x + c * cell_w
                xl = int(xw - grid_clip.x)
                if 0 <= xl <= grid_clip.w:
                    pygame.draw.line(ga, (*_COLORS["grid"], 40), (xl, 0), (xl, grid_clip.h))
            # Horizontal lines
            for r in range(self.rows + 1):
                yw = grid_start_y + r * cell_h
                yl = int(yw - grid_clip.y)
                if 0 <= yl <= grid_clip.h:
                    pygame.draw.line(ga, (*_COLORS["grid"], 40), (0, yl), (ga.get_width(), yl))
            screen.blit(ga, grid_clip.topleft)

        # Selected tiles
        for idx in self.selected_indices:
            hr = self.tile_screen_rect(idx)
            if hr and self.rect.colliderect(hr):
                sel_surf = pygame.Surface((hr.w, hr.h), pygame.SRCALPHA)
                sel_surf.fill((*_COLORS["selected"], 60))
                screen.blit(sel_surf, hr.topleft)
                pygame.draw.rect(screen, _COLORS["selected"], hr, 2)

        # Paste preview
        if self.paste_preview_idx >= 0:
            hr = self.tile_screen_rect(self.paste_preview_idx)
            if hr and self.rect.colliderect(hr):
                pygame.draw.rect(screen, (100, 220, 100), hr, 3)

        # Hover
        if self.hover_index >= 0 and self.hover_index not in self.selected_indices:
            hr = self.tile_screen_rect(self.hover_index)
            if hr and self.rect.colliderect(hr):
                pygame.draw.rect(screen, _COLORS["hover"], hr, 2)
                label = self._font.render(str(self.hover_index), True, _COLORS["text"])
                lx, ly = hr.x + 2, hr.y + 2
                bg = pygame.Surface((label.get_width() + 4, label.get_height() + 2), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 160))
                screen.blit(bg, (lx - 1, ly - 1))
                screen.blit(label, (lx, ly))

        # Top bar
        hdr = Rect(self.rect.x, self.rect.y, self.rect.w, TOP_BAR_H)
        hdr_bg = pygame.Surface((hdr.w, hdr.h), pygame.SRCALPHA)
        hdr_bg.fill((*_COLORS["header"], 200))
        screen.blit(hdr_bg, hdr.topleft)

        info = f"  {s_w}×{s_h}  Grid: {self.cols}×{self.rows}  Tile: {tw}×{th}  Zoom: {z:.1f}x"
        if self.selected_indices:
            info += f"  Selected: {len(self.selected_indices)}"
        title = self._font.render(info, True, _COLORS["text"])
        screen.blit(title, (self.rect.x + 6, self.rect.y + 5))

        screen.set_clip(clip)
