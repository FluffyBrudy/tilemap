"""
Frame Picker — click tiles on a spritesheet to add animation frames.

Displays the spritesheet with a grid overlay. Left-click toggles a
tile in/out of the current clip (add vs remove). Ctrl+click jumps the
timeline to a keyframe that uses that cel. Used tiles are tinted green;
the active keyframe also has a blue outline.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pygame
from pygame import Rect

from utils.font_manager import FontWeight
from widgets.ui.theme import COLORS, FONTS, SHAPE

TOP_TITLE_H = 22
TOP_BAR_TOTAL = 42



class FramePicker:
    """Spritesheet grid view — click tiles to select animation frames."""

    def __init__(
        self,
        rect: Rect,
        surface: pygame.Surface,
        tile_size: tuple[int, int],
    ):
        self.rect = rect
        self.surface = surface
        self.tile_size = tile_size

        self.grid_offset_x: int = 0
        self.grid_offset_y: int = 0

        self._recalc_grid()

        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self.zoom: float = 1.0

        self.hover_index: int = -1
        self._panning = False
        self._pan_start = (0, 0)
        self._pan_start_offset = (0.0, 0.0)

        self.highlighted: set[int] = set()
        self.focus_variant: int = -1

        self.filter_text: str = ""
        self.only_unused: bool = False
        self.editing_filter: bool = False
        self._filter_input_rect = Rect(0, 0, 0, 0)
        self._btn_unused_rect = Rect(0, 0, 0, 0)

        self.on_frame_clicked: Callable[[int], None] | None = None
        self.on_frame_paint: Callable[[int, bool], None] | None = None
        self.is_variant_in_clip: Callable[[int], bool] | None = None

        # paint-sweep state (LMB drag across tiles bulk add/remove)
        self._painting = False
        self._paint_add = True
        self._last_paint_idx = -1

        self._font: pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

        self._checker: pygame.Surface | None = None

    def set_surface(
        self, surface: pygame.Surface, tile_size: tuple[int, int] | None = None
    ) -> None:
        self.surface = surface
        if tile_size:
            self.tile_size = tile_size
        self._recalc_grid()

    def set_highlighted(self, indices: set[int]) -> None:
        self.highlighted = indices

    def set_focus_variant(self, variant_id: int) -> None:
        """Outline this tile to match the selected timeline frame (-1 clears)."""
        self.focus_variant = int(variant_id) if variant_id >= 0 else -1

    def scroll_variant_into_view(self, variant_id: int) -> None:
        """Pan so the given variant lies inside the sheet viewport (below the top bar)."""
        if variant_id < 0 or variant_id >= self.total_frames:
            return
        hr = self._tile_screen_rect(variant_id)
        if hr is None:
            return
        margin = 28
        inner = Rect(
            self.rect.x,
            self.rect.y + TOP_BAR_TOTAL,
            self.rect.w,
            self.rect.h - TOP_BAR_TOTAL,
        )
        if hr.width <= 0 or hr.height <= 0:
            return
        if hr.centerx < inner.left + margin:
            self.offset_x += (inner.left + margin) - hr.centerx
        elif hr.centerx > inner.right - margin:
            self.offset_x -= hr.centerx - (inner.right - margin)
        if hr.centery < inner.top + margin:
            self.offset_y += (inner.top + margin) - hr.centery
        elif hr.centery > inner.bottom - margin:
            self.offset_y -= hr.centery - (inner.bottom - margin)

    def resize(self, rect: Rect) -> None:
        self.rect = rect

    def set_grid_offset(self, offset_x: int, offset_y: int) -> None:
        """Set the grid offset for aligning the grid to a specific position in the spritesheet."""
        self.grid_offset_x = offset_x
        self.grid_offset_y = offset_y
        self._recalc_grid()

    def is_filter_input_active(self) -> bool:
        return self.editing_filter

    def handle_filter_keydown(self, event: pygame.event.Event) -> bool:
        if not self.editing_filter or event.type != pygame.KEYDOWN:
            return False
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            self.editing_filter = False
            return True
        if event.key == pygame.K_BACKSPACE:
            self.filter_text = self.filter_text[:-1]
            return True
        if event.unicode and len(self.filter_text) < 20:
            self.filter_text += event.unicode
            return True
        return True

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._painting:
                self._painting = False
                self._last_paint_idx = -1
                return True
        if not self.rect.collidepoint(mouse) and event.type not in (
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
        ):
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse) and mouse[1] < self.rect.y + TOP_BAR_TOTAL:
                if self._filter_input_rect.collidepoint(mouse):
                    self.editing_filter = True
                    return True
                if self._btn_unused_rect.collidepoint(mouse):
                    self.only_unused = not self.only_unused
                    return True
                self.editing_filter = False
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.rect.collidepoint(mouse):
                if mouse[1] < self.rect.y + TOP_BAR_TOTAL:
                    return True
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

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and (
            self.rect.collidepoint(mouse)
            and mouse[1] >= self.rect.y + TOP_BAR_TOTAL
        ):
            idx = self._index_at(mouse)
            if idx >= 0 and self._tile_matches_filter(idx):
                mods = pygame.key.get_mods()
                ctrl_held = bool(
                    mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
                )
                was_in_clip = None
                if not ctrl_held and self.is_variant_in_clip:
                    was_in_clip = self.is_variant_in_clip(idx)
                if self.on_frame_clicked:
                    self.on_frame_clicked(idx)
                # arm a paint sweep only for plain clicks; intent is whatever
                # the initial toggle did (added -> sweep adds, removed -> removes)
                if was_in_clip is not None and self.on_frame_paint:
                    self._painting = True
                    self._paint_add = not was_in_clip
                    self._last_paint_idx = idx
            return True

        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(mouse):
            if mouse[1] < self.rect.y + TOP_BAR_TOTAL:
                return True
            mods = pygame.key.get_mods()
            if mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL):
                old = self.zoom

                if event.y != 0:
                    self.zoom *= 1.12 if event.y > 0 else 0.88
                    self.zoom = max(0.25, min(self.zoom, 8.0))

                    rel_x = mouse[0] - self.rect.x - self.offset_x
                    rel_y = mouse[1] - self.rect.y - self.offset_y
                    scale = self.zoom / old
                    self.offset_x -= rel_x * (scale - 1)
                    self.offset_y -= rel_y * (scale - 1)

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

            if not (
                mods
                & (
                    pygame.KMOD_LCTRL
                    | pygame.KMOD_RCTRL
                    | pygame.KMOD_LSHIFT
                    | pygame.KMOD_RSHIFT
                )
            ):
                zoom_step = 1.15
                if event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                    old = self.zoom
                    self.zoom *= zoom_step
                    self.zoom = min(self.zoom, 8.0)

                    cx = self.rect.w // 2
                    cy = self.rect.h // 2
                    rel_x = cx - self.offset_x
                    rel_y = cy - self.offset_y
                    scale = self.zoom / old
                    self.offset_x -= rel_x * (scale - 1)
                    self.offset_y -= rel_y * (scale - 1)
                    return True
                if event.key == pygame.K_MINUS:
                    old = self.zoom
                    self.zoom /= zoom_step
                    self.zoom = max(self.zoom, 0.25)
                    cx = self.rect.w // 2
                    cy = self.rect.h // 2
                    rel_x = cx - self.offset_x
                    rel_y = cy - self.offset_y
                    scale = self.zoom / old
                    self.offset_x -= rel_x * (scale - 1)
                    self.offset_y -= rel_y * (scale - 1)
                    return True
                if event.key == pygame.K_0:
                    self.zoom = 1.0
                    self.offset_x = 0.0
                    self.offset_y = 0.0
                    return True

                pan_amount = 20
                if event.key == pygame.K_LEFT:
                    self.offset_x += pan_amount
                    return True
                if event.key == pygame.K_RIGHT:
                    self.offset_x -= pan_amount
                    return True
                if event.key == pygame.K_UP:
                    self.offset_y += pan_amount
                    return True
                if event.key == pygame.K_DOWN:
                    self.offset_y -= pan_amount
                    return True

        if event.type == pygame.MOUSEMOTION and self._painting:
            idx = self._index_at(mouse)
            if idx >= 0 and idx != self._last_paint_idx:
                # fast sweeps skip events: paint every index between last
                # and current so nothing along the index path is missed
                # (diagonal drags over-cover row-wrapped cells by design --
                # over-painting beats skipping)
                li, ci = self._last_paint_idx, idx
                step = 1 if idx > li else -1
                cur = li + step
                while (cur - ci) * step <= 0:
                    if (
                        self._tile_matches_filter(cur)
                        and self.on_frame_paint
                    ):
                        self.on_frame_paint(cur, self._paint_add)
                    cur += step
                self._last_paint_idx = idx
            return True

        if event.type == pygame.MOUSEMOTION:
            if self._panning:
                # dragging the view must not look like selecting tiles
                self.hover_index = -1
            elif self.rect.collidepoint(mouse):
                hi = self._index_at(mouse)
                if hi >= 0 and self._tile_matches_filter(hi):
                    self.hover_index = hi
                else:
                    self.hover_index = -1
            else:
                self.hover_index = -1

        return False

    def draw(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()
        clip = screen.get_clip()
        screen.set_clip(self.rect)

        self._draw_checker_bg(screen)

        tw, th = self.tile_size
        z = self.zoom
        img_x = self.rect.x + self.offset_x
        img_y = self.rect.y + self.offset_y
        scaled_w = int(self.surface.get_width() * z)
        scaled_h = int(self.surface.get_height() * z)

        if scaled_w > 0 and scaled_h > 0:
            scaled = pygame.transform.smoothscale(self.surface, (scaled_w, scaled_h))
            screen.blit(scaled, (img_x, img_y))

        cell_w = tw * z
        cell_h = th * z

        sheet_screen_rect = Rect(int(img_x), int(img_y), int(scaled_w), int(scaled_h))

        grid_start_x = img_x + (self.grid_offset_x * z)
        grid_start_y = img_y + (self.grid_offset_y * z)

        grid_clip = sheet_screen_rect.clip(self.rect)
        if grid_clip.width > 0 and grid_clip.height > 0:
            grid_alpha_surf = pygame.Surface(
                (grid_clip.w, grid_clip.h), pygame.SRCALPHA
            )

            for c in range(self.cols + 1):
                x_world = grid_start_x + c * cell_w
                x_local = int(x_world - grid_clip.x)
                if 0 <= x_local <= grid_clip.w:
                    pygame.draw.line(
                        grid_alpha_surf,
                        (*COLORS.border, 40),
                        (x_local, 0),
                        (x_local, grid_clip.h),
                    )

            for r in range(self.rows + 1):
                y_world = grid_start_y + r * cell_h
                y_local = int(y_world - grid_clip.y)
                if 0 <= y_local <= grid_clip.h:
                    pygame.draw.line(
                        grid_alpha_surf,
                        (*COLORS.border, 40),
                        (0, y_local),
                        (grid_clip.w, y_local),
                    )

            screen.blit(grid_alpha_surf, grid_clip.topleft)

        for idx in self.highlighted:
            col = idx % self.cols
            row = idx // self.cols
            hr = Rect(
                int(img_x + (self.grid_offset_x + col * tw) * z),
                int(img_y + (self.grid_offset_y + row * th) * z),
                int(cell_w),
                int(cell_h),
            )
            hl_surf = pygame.Surface((hr.w, hr.h), pygame.SRCALPHA)
            hl_surf.fill((*COLORS.success, 55))
            screen.blit(hl_surf, hr.topleft)
            pygame.draw.rect(screen, COLORS.success, hr, 1)

        for idx in range(self.total_frames):
            if self._tile_matches_filter(idx):
                continue
            hr = self._tile_screen_rect(idx)
            if hr is None:
                continue
            if not self.rect.colliderect(hr):
                continue
            dim = pygame.Surface((hr.w, hr.h), pygame.SRCALPHA)
            dim.fill((*COLORS.bg, 160))
            screen.blit(dim, hr.topleft)

        if self.focus_variant >= 0 and self.focus_variant < self.total_frames:
            fhr = self._tile_screen_rect(self.focus_variant)
            if fhr is not None and self.rect.colliderect(fhr):
                pygame.draw.rect(screen, COLORS.accent, fhr, 3)

        if self.hover_index >= 0:
            col = self.hover_index % self.cols
            row = self.hover_index // self.cols
            hr = Rect(
                int(img_x + (self.grid_offset_x + col * tw) * z),
                int(img_y + (self.grid_offset_y + row * th) * z),
                int(cell_w),
                int(cell_h),
            )
            pygame.draw.rect(screen, COLORS.warning, hr, 2)

            label = self._font_sm.render(str(self.hover_index), True, COLORS.text)
            lx = hr.x + 2
            ly = hr.y + 2
            bg_rect = Rect(
                lx - 1, ly - 1, label.get_width() + 4, label.get_height() + 2
            )
            bg = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
            bg.fill((*COLORS.bg, 180))
            screen.blit(bg, bg_rect.topleft)
            screen.blit(label, (lx, ly))

        hdr = Rect(self.rect.x, self.rect.y, self.rect.w, TOP_TITLE_H)
        hdr_bg = pygame.Surface((hdr.w, hdr.h), pygame.SRCALPHA)
        hdr_bg.fill((*COLORS.header, 200))
        screen.blit(hdr_bg, hdr.topleft)
        title = self._font.render(
            f"Spritesheet  ({self.cols}×{self.rows})  Zoom: {self.zoom:.1f}x"
            f"  ·  click: add/remove  ·  Ctrl+click: select  ·  +/-: zoom  ·  arrows: pan",
            True,
            COLORS.text,
        )
        screen.blit(title, (self.rect.x + 6, self.rect.y + 3))

        row2 = Rect(
            self.rect.x,
            self.rect.y + TOP_TITLE_H,
            self.rect.w,
            TOP_BAR_TOTAL - TOP_TITLE_H,
        )
        row2_bg = pygame.Surface((row2.w, row2.h), pygame.SRCALPHA)
        row2_bg.fill((*COLORS.header, 220))
        screen.blit(row2_bg, row2.topleft)

        self._filter_input_rect = Rect(
            row2.x + 6, row2.y + 4, min(140, row2.w - 100), 18
        )
        fi_bg = COLORS.selected if self.editing_filter else COLORS.panel_alt
        pygame.draw.rect(screen, fi_bg, self._filter_input_rect, border_radius=SHAPE.radius_sm)
        pygame.draw.rect(
            screen, COLORS.border, self._filter_input_rect, 1, border_radius=SHAPE.radius_sm
        )
        ft = self.filter_text + (
            "|" if self.editing_filter and (pygame.time.get_ticks() // 400) % 2 else ""
        )
        lab = "id…" if not self.filter_text and not self.editing_filter else ft
        col = COLORS.accent if self.editing_filter else COLORS.text
        screen.blit(
            self._font_sm.render(lab, True, col),
            (self._filter_input_rect.x + 4, self._filter_input_rect.y + 3),
        )

        self._btn_unused_rect = Rect(
            self._filter_input_rect.right + 8, row2.y + 4, 86, 18
        )
        ub = COLORS.selected if self.only_unused else COLORS.panel_alt
        pygame.draw.rect(screen, ub, self._btn_unused_rect, border_radius=SHAPE.radius_sm)
        pygame.draw.rect(
            screen, COLORS.border, self._btn_unused_rect, 1, border_radius=SHAPE.radius_sm
        )
        ut = "Unused only" if self.only_unused else "All tiles"
        screen.blit(
            self._font_sm.render(ut, True, COLORS.text),
            (self._btn_unused_rect.x + 4, self._btn_unused_rect.y + 3),
        )

        screen.set_clip(clip)

    def _recalc_grid(self) -> None:
        """Recalculate grid dimensions based on tile size and offset."""
        tw, th = self.tile_size

        available_w = self.surface.get_width() - self.grid_offset_x
        available_h = self.surface.get_height() - self.grid_offset_y
        self.cols = max(1, available_w // tw)
        self.rows = max(1, available_h // th)
        self.total_frames = self.cols * self.rows

    def _tile_matches_filter(self, idx: int) -> bool:
        if self.only_unused and idx in self.highlighted:
            return False
        q = self.filter_text.strip().lower()
        if not q:
            return True
        return q in str(idx).lower()

    def _tile_screen_rect(self, idx: int) -> Rect | None:
        if idx < 0 or idx >= self.total_frames:
            return None
        tw, th = self.tile_size
        z = self.zoom
        col = idx % self.cols
        row = idx // self.cols
        img_x = self.rect.x + self.offset_x
        img_y = self.rect.y + self.offset_y
        cell_w = tw * z
        cell_h = th * z
        return Rect(
            int(img_x + (self.grid_offset_x + col * tw) * z),
            int(img_y + (self.grid_offset_y + row * th) * z),
            int(cell_w),
            int(cell_h),
        )

    def _index_at(self, mouse: tuple[int, int]) -> int:
        """Return tile index at the given screen position or -1."""
        if mouse[1] < self.rect.y + TOP_BAR_TOTAL:
            return -1
        z = self.zoom
        tw, th = self.tile_size
        W = float(self.surface.get_width())
        H = float(self.surface.get_height())

        rel_x = (mouse[0] - self.rect.x - self.offset_x) / z
        rel_y = (mouse[1] - self.rect.y - self.offset_y) / z

        eps_tex = max(0.25, 0.5 / max(z, 0.01))

        if rel_x < 0 or rel_y < 0:
            return -1
        if rel_x >= W and rel_x < W + eps_tex:
            rel_x = max(0.0, W - 1e-6)
        if rel_y >= H and rel_y < H + eps_tex:
            rel_y = max(0.0, H - 1e-6)
        if rel_x >= W or rel_y >= H:
            return -1

        grid_rel_x = rel_x - self.grid_offset_x
        grid_rel_y = rel_y - self.grid_offset_y

        if grid_rel_x < 0 or grid_rel_y < 0:
            return -1

        gw = float(self.cols * tw)
        gh = float(self.rows * th)

        if grid_rel_x >= gw and grid_rel_x < gw + eps_tex:
            grid_rel_x = max(0.0, gw - 1e-6)
        if grid_rel_y >= gh and grid_rel_y < gh + eps_tex:
            grid_rel_y = max(0.0, gh - 1e-6)
        if grid_rel_x >= gw or grid_rel_y >= gh:
            return -1

        col = int(math.floor(grid_rel_x / tw))
        row = int(math.floor(grid_rel_y / th))

        if 0 <= col < self.cols and 0 <= row < self.rows:
            return row * self.cols + col
        return -1

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = FONTS.get_bold_font()
        if self._font_sm is None:
            self._font_sm = FONTS.get_small_font(FontWeight.BOLD)

    def _draw_checker_bg(self, screen: pygame.Surface) -> None:
        if self._checker is None:
            sz = 8
            avg = (COLORS.panel[0] + COLORS.panel[1] + COLORS.panel[2]) // 3
            if avg > 128:
                c1 = tuple(max(c - 10, 0) for c in COLORS.panel)
                c2 = tuple(max(c - 20, 0) for c in COLORS.panel)
            else:
                c1 = tuple(min(c + 10, 255) for c in COLORS.panel)
                c2 = tuple(min(c + 20, 255) for c in COLORS.panel)
            self._checker = pygame.Surface((sz * 2, sz * 2))
            self._checker.fill(c1)
            pygame.draw.rect(self._checker, c2, (sz, 0, sz, sz))
            pygame.draw.rect(self._checker, c2, (0, sz, sz, sz))
        for y in range(self.rect.y, self.rect.bottom, self._checker.get_height()):
            for x in range(self.rect.x, self.rect.right, self._checker.get_width()):
                screen.blit(self._checker, (x, y))
