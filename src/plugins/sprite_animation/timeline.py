"""
Timeline — horizontal strip of animation frames with reordering.

Shows frame thumbnails in sequence. Supports:
  - Click to select a frame
  - Drag to reorder
  - Click duration label to edit per-frame timing
  - Delete / D to remove / duplicate
  - Playback scrubber overlay
"""

from __future__ import annotations

from collections.abc import Callable

import pygame
from pygame import Rect

from utils.font_manager import FontWeight
from widgets.ui.theme import COLORS, FONTS, SHAPE

from .models import AnimationFrame, AnimationMarker

THUMB_SIZE = 48
CELL_W = 64
CELL_H_TOTAL = 90
CELL_BODY_H = 68
CELL_PAD = 6
HEADER_H = 22
MARKER_BAND_H = 16
MARKER_HIT_PAD = 4


class Timeline:
    """Horizontal frame strip with drag-reorder and per-frame duration editing."""

    def __init__(
        self,
        rect: Rect,
        surface: pygame.Surface,
        tile_size: tuple[int, int],
    ):
        self.rect = rect
        self.surface = surface
        self.tile_size = tile_size

        # Grid offset for aligning extraction
        self.grid_offset_x: int = 0
        self.grid_offset_y: int = 0

        self.frames: list[AnimationFrame] = []
        self.selected_index: int = -1
        self.scroll_x: float = 0

        # Drag-reorder state
        self._dragging = False
        self._drag_from: int = -1
        self._drag_insert: int = -1
        self._drag_mouse_x: int = 0
        self._drag_start_x: int = 0
        self._drag_moved = False

        # Click-click move state (-1 = nothing armed)
        self._pending_move: int = -1

        # Duration text editing
        self._editing_dur = False
        self._editing_idx: int = -1
        self._dur_text = ""

        # Playback scrubber position (0–1 fraction through the animation)
        self.scrubber_frac: float = 0.0

        # Named markers (same list as Animation.markers when wired from editor)
        self.markers: list[AnimationMarker] = []
        self._marker_drag_i: int = -1
        self._marker_drag_moved: bool = False
        self._marker_hover_index: int = -1

        # Callbacks
        self.on_frame_selected: Callable[[int], None] | None = None
        self.on_frames_changed: Callable[[], None] | None = None
        self.on_markers_changed: Callable[[], None] | None = None

        # Fonts
        self._font: pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

        # Cache frame thumbnails
        self._thumb_cache: dict[int, pygame.Surface] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_frames(self, frames: list[AnimationFrame]) -> None:
        self.frames = frames
        self.selected_index = min(self.selected_index, len(frames) - 1)
        self._pending_move = -1
        self._thumb_cache.clear()

    def set_markers(self, markers: list[AnimationMarker]) -> None:
        self.markers = markers

    def select_frame(self, index: int) -> None:
        """Select a clip frame by index and notify ``on_frame_selected``."""
        if not self.frames:
            self.selected_index = -1
            return
        i = max(0, min(index, len(self.frames) - 1))
        self.selected_index = i
        if self.on_frame_selected:
            self.on_frame_selected(i)

    def set_surface(
        self, surface: pygame.Surface, tile_size: tuple[int, int] | None = None
    ) -> None:
        self.surface = surface
        if tile_size:
            self.tile_size = tile_size
        self._thumb_cache.clear()

    def invalidate_cache(self) -> None:
        """Clear the thumbnail cache. Call after external changes to surface, tile_size, or grid offset."""
        self._thumb_cache.clear()

    def resize(self, rect: Rect) -> None:
        self.rect = rect

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    DRAG_THRESHOLD = 6  # px of horizontal movement before reorder arms

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse = pygame.mouse.get_pos()

        if self._marker_drag_i >= 0:
            if event.type == pygame.MOUSEMOTION:
                idx = self._frame_index_from_mouse_x(mouse)
                if (
                    idx >= 0
                    and self.markers
                    and self._marker_drag_i < len(self.markers)
                ) and self.markers[self._marker_drag_i].frame_index != idx:
                    self.markers[self._marker_drag_i].frame_index = idx
                    self._marker_drag_moved = True
                return True
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self._marker_drag_moved and self.on_markers_changed:
                    self.on_markers_changed()
                self._marker_drag_i = -1
                self._marker_drag_moved = False
                return True

        # Duration editing keyboard
        if self._editing_dur:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._commit_duration()
                    return True
                if event.key == pygame.K_ESCAPE:
                    self._editing_dur = False
                    return True
                if event.key == pygame.K_BACKSPACE:
                    self._dur_text = self._dur_text[:-1]
                    return True
                if event.unicode and (
                    event.unicode.isdigit() or event.unicode == "."
                ):
                    if len(self._dur_text) < 6:
                        self._dur_text += event.unicode
                    return True
            # Click outside editing area → commit
            if event.type == pygame.MOUSEBUTTONDOWN:
                self._commit_duration()

        if not self.rect.collidepoint(mouse) and event.type not in (
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
        ):
            return False

        # Keyboard shortcuts (when timeline has focus)
        if event.type == pygame.KEYDOWN and self.rect.collidepoint(mouse):
            if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                if self._marker_hover_index >= 0:
                    del self.markers[self._marker_hover_index]
                    if self.on_markers_changed:
                        self.on_markers_changed()
                    return True
                self._delete_selected()
                return True
            if event.key == pygame.K_d:
                self._duplicate_selected()
                return True
            if event.key == pygame.K_ESCAPE and self._pending_move >= 0:
                self._pending_move = -1
                return True

        # Delete marker (right-click on marker diamond)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.rect.collidepoint(mouse):
                mi = self._marker_at(mouse)
                if mi >= 0:
                    del self.markers[mi]
                    if self.on_markers_changed:
                        self.on_markers_changed()
                    return True

        # Left-click
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse):
                mi = self._marker_at(mouse)
                if mi >= 0:
                    self._marker_drag_i = mi
                    self._marker_drag_moved = False
                    return True
                idx = self._cell_at(mouse)
                # Check if clicking on duration label
                if idx >= 0 and self._is_duration_click(mouse, idx):
                    self._start_dur_edit(idx)
                    return True
                if idx >= 0:
                    if 0 <= self._pending_move < len(self.frames):
                        if idx != self._pending_move:
                            insert_at = self._insert_index_at(mouse)
                            self._reorder(self._pending_move, insert_at)
                            if self.on_frame_selected:
                                self.on_frame_selected(self.selected_index)
                        else:
                            self.selected_index = idx
                        self._pending_move = -1
                        return True
                    self.selected_index = idx
                    if self.on_frame_selected:
                        self.on_frame_selected(idx)
                    self._pending_move = idx
                    self._dragging = True
                    self._drag_moved = False
                    self._drag_start_x = mouse[0]
                    self._drag_from = idx
                    self._drag_insert = -1
                    self._drag_mouse_x = mouse[0]
                else:
                    self._pending_move = -1
                return True

        if event.type == pygame.MOUSEMOTION and self._dragging:
            if not self._drag_moved and (
                abs(mouse[0] - self._drag_start_x) <= self.DRAG_THRESHOLD
            ):
                return True
            self._drag_moved = True
            self._drag_mouse_x = mouse[0]
            self._drag_insert = self._insert_index_at(mouse)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                if self._drag_moved:
                    if (
                        self._drag_insert >= 0
                        and self._drag_insert != self._drag_from
                    ):
                        self._reorder(self._drag_from, self._drag_insert)
                    self._pending_move = -1
                self._dragging = False
                self._drag_from = -1
                self._drag_insert = -1
                self._drag_moved = False
                return True

        # Scroll
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(mouse):
            self.scroll_x -= event.y * 40
            self._clamp_scroll()
            return True

        return False

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()
        clip = screen.get_clip()
        screen.set_clip(self.rect)

        # Background
        pygame.draw.rect(screen, COLORS.bg, self.rect)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)

        # Header
        hdr = Rect(self.rect.x, self.rect.y, self.rect.w, HEADER_H)
        pygame.draw.rect(screen, COLORS.header, hdr)
        label = f"Timeline  ({len(self.frames)} frames)"
        screen.blit(
            self._font.render(label, True, COLORS.text), (hdr.x + 6, hdr.y + 3)
        )

        band_top = self.rect.y + HEADER_H
        content_y = band_top + MARKER_BAND_H + 2

        # Marker band background
        band_rect = Rect(self.rect.x, band_top, self.rect.w, MARKER_BAND_H)
        pygame.draw.rect(screen, COLORS.panel_alt, band_rect)
        pygame.draw.line(
            screen,
            COLORS.border,
            (band_rect.x, band_rect.bottom - 1),
            (band_rect.right, band_rect.bottom - 1),
        )
        hint_m = self._font_sm.render(
            "Markers · drag · Del / RMB on diamond removes", True, COLORS.text_dim
        )
        screen.blit(hint_m, (band_rect.x + 6, band_rect.y + 2))

        self._marker_hover_index = -1
        if not self.frames:
            hint = self._font.render(
                "Click tiles in the spritesheet to add frames →",
                True,
                COLORS.text_muted,
            )
            screen.blit(hint, (self.rect.x + 12, content_y + 20))
            screen.set_clip(clip)
            return

        mx = pygame.mouse.get_pos()
        hover_mi = self._marker_at(mx) if self.rect.collidepoint(mx) else -1
        self._marker_hover_index = hover_mi

        for mi, mk in enumerate(self.markers):
            cx = self._cell_left_x(mk.frame_index)
            if cx is None:
                continue
            if cx + CELL_W < self.rect.x or cx > self.rect.right:
                continue
            color = COLORS.marker_colors[mi % len(COLORS.marker_colors)]
            tip_y = band_top + MARKER_BAND_H - 6
            cx_c = cx + CELL_W // 2
            pts = [(cx_c, tip_y - 8), (cx_c - 7, tip_y + 2), (cx_c + 7, tip_y + 2)]
            pygame.draw.polygon(screen, color, pts)
            pygame.draw.polygon(screen, COLORS.border, pts, 1)
            if hover_mi == mi or self._marker_drag_i == mi:
                nm = mk.name[:10] + ("…" if len(mk.name) > 10 else "")
                tag = self._font_sm.render(nm, True, COLORS.text)
                tx = max(
                    self.rect.x + 4,
                    min(
                        cx_c - tag.get_width() // 2,
                        self.rect.right - tag.get_width() - 4,
                    ),
                )
                screen.blit(tag, (tx, band_top + 2))

        # Draw frame cells
        for i, frame in enumerate(self.frames):
            cx = self.rect.x + CELL_PAD + i * (CELL_W + CELL_PAD) - int(self.scroll_x)
            cy = content_y

            if cx + CELL_W < self.rect.x or cx > self.rect.right:
                continue

            # Cell background
            is_selected = i == self.selected_index
            is_hover = self._cell_at(pygame.mouse.get_pos()) == i and not self._dragging
            if is_selected:
                bg = COLORS.selected
            elif is_hover:
                                bg = COLORS.hover
            else:
                bg = COLORS.panel

            cell_rect = Rect(cx, cy, CELL_W, CELL_BODY_H)
            pygame.draw.rect(screen, bg, cell_rect, border_radius=SHAPE.radius)
            if is_selected:
                pygame.draw.rect(
                    screen, COLORS.accent, cell_rect, 2, border_radius=SHAPE.radius
                )
            else:
                pygame.draw.rect(
                    screen, COLORS.border, cell_rect, 1, border_radius=SHAPE.radius
                )

            # Thumbnail
            thumb = self._get_thumb(frame.variant_id)
            if thumb:
                tx = cx + (CELL_W - THUMB_SIZE) // 2
                ty = cy + 4
                screen.blit(thumb, (tx, ty))

            # Frame index
            idx_label = self._font_sm.render(
                f"#{frame.variant_id}", True, COLORS.text_dim
            )
            screen.blit(idx_label, (cx + 4, cy + 4))

            # Duration
            dur_y = cy + THUMB_SIZE + 4
            if self._editing_dur and self._editing_idx == i:
                dur_str = self._dur_text + (
                    "|" if (pygame.time.get_ticks() // 500) % 2 else ""
                )
                dur_surf = self._font_sm.render(
                    f"{dur_str}ms", True, COLORS.accent
                )
            else:
                dur_surf = self._font_sm.render(
                    f"{frame.duration_ms:.0f}ms", True, COLORS.text
                )
            dur_x = cx + (CELL_W - dur_surf.get_width()) // 2
            screen.blit(dur_surf, (dur_x, dur_y))

        # Drag insert indicator
        if self._dragging and self._drag_insert >= 0:
            insert_x = (
                self.rect.x
                + CELL_PAD
                + self._drag_insert * (CELL_W + CELL_PAD)
                - int(self.scroll_x)
                - 2
            )
            pygame.draw.line(
                screen,
                COLORS.success,
                (insert_x, content_y),
                (insert_x, content_y + CELL_BODY_H),
                3,
            )

        # Scrubber
        if self.frames and self.scrubber_frac > 0:
            total_w = len(self.frames) * (CELL_W + CELL_PAD)
            sx = (
                self.rect.x
                + CELL_PAD
                + int(self.scrubber_frac * total_w)
                - int(self.scroll_x)
            )
            if self.rect.x <= sx <= self.rect.right:
                pygame.draw.line(
                    screen,
                    COLORS.danger,
                    (sx, content_y - 2),
                    (sx, content_y + CELL_BODY_H + 2),
                    2,
                )

        # Scroll bar
        total_content_w = len(self.frames) * (CELL_W + CELL_PAD) + CELL_PAD
        if total_content_w > self.rect.w:
            bar_w = max(20, int(self.rect.w * (self.rect.w / total_content_w)))
            bar_x = self.rect.x + int(
                (self.scroll_x / (total_content_w - self.rect.w))
                * (self.rect.w - bar_w)
            )
            bar_rect = Rect(bar_x, self.rect.bottom - 5, bar_w, 3)
            pygame.draw.rect(screen, COLORS.border, bar_rect, border_radius=SHAPE.radius_sm)

        screen.set_clip(clip)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _band_top(self) -> int:
        return self.rect.y + HEADER_H

    def _content_y(self) -> int:
        return self._band_top() + MARKER_BAND_H + 2

    def _cell_left_x(self, idx: int) -> int | None:
        if idx < 0 or idx >= len(self.frames):
            return None
        return self.rect.x + CELL_PAD + idx * (CELL_W + CELL_PAD) - int(self.scroll_x)

    def _frame_index_from_mouse_x(self, mouse: tuple[int, int]) -> int:
        if not self.frames:
            return -1
        rx = mouse[0] - self.rect.x + self.scroll_x - CELL_PAD
        idx = int(rx // (CELL_W + CELL_PAD))
        return max(0, min(idx, len(self.frames) - 1))

    def _marker_at(self, mouse: tuple[int, int]) -> int:
        if not self.markers or not self.frames:
            return -1
        band_top = self._band_top()
        if (
            mouse[1] < band_top - MARKER_HIT_PAD
            or mouse[1] > band_top + MARKER_BAND_H + 8
        ):
            return -1
        for i, m in enumerate(self.markers):
            cx = self._cell_left_x(m.frame_index)
            if cx is None:
                continue
            if cx + CELL_W < self.rect.x or cx > self.rect.right:
                continue
            cx_c = cx + CELL_W // 2
            tip_y = band_top + MARKER_BAND_H - 6
            hit = Rect(cx_c - 16, tip_y - 14, 32, 26)
            if hit.collidepoint(mouse):
                return i
        return -1

    def _cell_at(self, mouse: tuple[int, int]) -> int:
        if not self.rect.collidepoint(mouse):
            return -1
        content_y = self._content_y()
        if mouse[1] < content_y or mouse[1] > content_y + CELL_BODY_H:
            return -1
        rx = mouse[0] - self.rect.x + self.scroll_x - CELL_PAD
        idx = int(rx // (CELL_W + CELL_PAD))
        # Check within cell bounds (not in padding)
        cell_start = CELL_PAD + idx * (CELL_W + CELL_PAD)
        local_x = mouse[0] - self.rect.x + self.scroll_x
        if local_x < cell_start or local_x > cell_start + CELL_W:
            return -1
        if 0 <= idx < len(self.frames):
            return idx
        return -1

    def _insert_index_at(self, mouse: tuple[int, int]) -> int:
        rx = mouse[0] - self.rect.x + self.scroll_x
        idx = int((rx + (CELL_W + CELL_PAD) // 2) // (CELL_W + CELL_PAD))
        return max(0, min(idx, len(self.frames)))

    def _is_duration_click(self, mouse: tuple[int, int], idx: int) -> bool:
        content_y = self._content_y()
        dur_y = content_y + THUMB_SIZE + 4
        return mouse[1] >= dur_y

    def _start_dur_edit(self, idx: int) -> None:
        self._editing_dur = True
        self._editing_idx = idx
        self._dur_text = f"{self.frames[idx].duration_ms:.0f}"
        self.selected_index = idx

    def _commit_duration(self) -> None:
        if self._editing_dur and 0 <= self._editing_idx < len(self.frames):
            try:
                val = float(self._dur_text) if self._dur_text else 100.0
                self.frames[self._editing_idx].duration_ms = max(1.0, min(val, 10000.0))
            except ValueError:
                pass
            if self.on_frames_changed:
                self.on_frames_changed()
        self._editing_dur = False
        self._editing_idx = -1

    def _delete_selected(self) -> None:
        if 0 <= self.selected_index < len(self.frames):
            self.frames.pop(self.selected_index)
            if self.selected_index >= len(self.frames):
                self.selected_index = len(self.frames) - 1
            if self.on_frames_changed:
                self.on_frames_changed()

    def _duplicate_selected(self) -> None:
        if 0 <= self.selected_index < len(self.frames):
            orig = self.frames[self.selected_index]
            copy = AnimationFrame(
                variant_id=orig.variant_id, duration_ms=orig.duration_ms
            )
            self.frames.insert(self.selected_index + 1, copy)
            self.selected_index += 1
            if self.on_frames_changed:
                self.on_frames_changed()

    def _reorder(self, from_idx: int, to_idx: int) -> None:
        if from_idx == to_idx or from_idx < 0 or to_idx < 0:
            return
        frame = self.frames.pop(from_idx)
        insert_at = to_idx if to_idx < from_idx else to_idx - 1
        insert_at = max(0, min(insert_at, len(self.frames)))
        self.frames.insert(insert_at, frame)
        self.selected_index = insert_at
        if self.on_frames_changed:
            self.on_frames_changed()

    def _get_thumb(self, variant_id: int) -> pygame.Surface | None:
        if variant_id in self._thumb_cache:
            return self._thumb_cache[variant_id]
        tw, th = self.tile_size
        # Calculate cols based on available space after offset
        available_w = self.surface.get_width() - self.grid_offset_x
        cols = max(1, available_w // tw)
        col = variant_id % cols
        row = variant_id // cols
        # Apply grid offset to source rect
        src = Rect(self.grid_offset_x + col * tw, self.grid_offset_y + row * th, tw, th)
        if not self.surface.get_rect().contains(src):
            return None
        tile_surf = self.surface.subsurface(src).copy()
        thumb = pygame.transform.smoothscale(tile_surf, (THUMB_SIZE, THUMB_SIZE))
        self._thumb_cache[variant_id] = thumb
        return thumb

    def _clamp_scroll(self) -> None:
        total_w = len(self.frames) * (CELL_W + CELL_PAD) + CELL_PAD
        max_scroll = max(0, total_w - self.rect.w)
        self.scroll_x = max(0.0, min(self.scroll_x, max_scroll))

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = FONTS.get_bold_font()
        if self._font_sm is None:
            self._font_sm = FONTS.get_small_font(FontWeight.BOLD)
