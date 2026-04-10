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

from typing import Callable, List, Optional, Tuple

import pygame
from pygame import Rect

from .models import AnimationFrame

# ---------------------------------------------------------------------------
_COLORS = {
    "bg": (30, 32, 36),
    "cell": (42, 45, 50),
    "cell_hover": (52, 56, 64),
    "selected": (50, 70, 110),
    "border": (60, 62, 65),
    "border_accent": (80, 120, 200),
    "text": (230, 230, 230),
    "text_dim": (140, 140, 140),
    "text_edit": (255, 220, 100),
    "scrubber": (220, 80, 80),
    "drag_line": (80, 180, 120),
    "header": (40, 42, 46),
    "empty_hint": (100, 100, 100),
}

THUMB_SIZE = 48
CELL_W = 64
CELL_H_TOTAL = 90  # thumb + duration label + padding
CELL_PAD = 6
HEADER_H = 22


class Timeline:
    """Horizontal frame strip with drag-reorder and per-frame duration editing."""

    def __init__(
        self,
        rect: Rect,
        surface: pygame.Surface,
        tile_size: Tuple[int, int],
    ):
        self.rect = rect
        self.surface = surface
        self.tile_size = tile_size

        self.frames: List[AnimationFrame] = []
        self.selected_index: int = -1
        self.scroll_x: float = 0

        # Drag-reorder state
        self._dragging = False
        self._drag_from: int = -1
        self._drag_insert: int = -1
        self._drag_mouse_x: int = 0

        # Duration text editing
        self._editing_dur = False
        self._editing_idx: int = -1
        self._dur_text = ""

        # Playback scrubber position (0–1 fraction through the animation)
        self.scrubber_frac: float = 0.0

        # Callbacks
        self.on_frame_selected: Optional[Callable[[int], None]] = None
        self.on_frames_changed: Optional[Callable[[], None]] = None

        # Fonts
        self._font: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None

        # Cache frame thumbnails
        self._thumb_cache: dict[int, pygame.Surface] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_frames(self, frames: List[AnimationFrame]) -> None:
        self.frames = frames
        self.selected_index = min(self.selected_index, len(frames) - 1)
        self._thumb_cache.clear()

    def set_surface(self, surface: pygame.Surface, tile_size: Optional[Tuple[int, int]] = None) -> None:
        self.surface = surface
        if tile_size:
            self.tile_size = tile_size
        self._thumb_cache.clear()

    def resize(self, rect: Rect) -> None:
        self.rect = rect

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse = pygame.mouse.get_pos()

        # Duration editing keyboard
        if self._editing_dur:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._commit_duration()
                    return True
                elif event.key == pygame.K_ESCAPE:
                    self._editing_dur = False
                    return True
                elif event.key == pygame.K_BACKSPACE:
                    self._dur_text = self._dur_text[:-1]
                    return True
                elif event.unicode and (event.unicode.isdigit() or event.unicode == "."):
                    if len(self._dur_text) < 6:
                        self._dur_text += event.unicode
                    return True
            # Click outside editing area → commit
            if event.type == pygame.MOUSEBUTTONDOWN:
                self._commit_duration()

        if not self.rect.collidepoint(mouse) and event.type not in (
            pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION
        ):
            return False

        # Keyboard shortcuts (when timeline has focus)
        if event.type == pygame.KEYDOWN and self.rect.collidepoint(mouse):
            if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                self._delete_selected()
                return True
            if event.key == pygame.K_d:
                self._duplicate_selected()
                return True

        # Left-click
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse):
                idx = self._cell_at(mouse)
                # Check if clicking on duration label
                if idx >= 0 and self._is_duration_click(mouse, idx):
                    self._start_dur_edit(idx)
                    return True
                if idx >= 0:
                    self.selected_index = idx
                    self._dragging = True
                    self._drag_from = idx
                    self._drag_mouse_x = mouse[0]
                    if self.on_frame_selected:
                        self.on_frame_selected(idx)
                return True

        if event.type == pygame.MOUSEMOTION and self._dragging:
            self._drag_mouse_x = mouse[0]
            self._drag_insert = self._insert_index_at(mouse)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                if self._drag_insert >= 0 and self._drag_insert != self._drag_from:
                    self._reorder(self._drag_from, self._drag_insert)
                self._dragging = False
                self._drag_from = -1
                self._drag_insert = -1
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
        pygame.draw.rect(screen, _COLORS["bg"], self.rect)
        pygame.draw.rect(screen, _COLORS["border"], self.rect, 1)

        # Header
        hdr = Rect(self.rect.x, self.rect.y, self.rect.w, HEADER_H)
        pygame.draw.rect(screen, _COLORS["header"], hdr)
        label = f"Timeline  ({len(self.frames)} frames)"
        screen.blit(self._font.render(label, True, _COLORS["text"]), (hdr.x + 6, hdr.y + 3))

        content_y = self.rect.y + HEADER_H + 4

        if not self.frames:
            hint = self._font.render(
                "Click tiles in the spritesheet to add frames →", True, _COLORS["empty_hint"]
            )
            screen.blit(hint, (self.rect.x + 12, content_y + 20))
            screen.set_clip(clip)
            return

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
                bg = _COLORS["selected"]
            elif is_hover:
                bg = _COLORS["cell_hover"]
            else:
                bg = _COLORS["cell"]

            cell_rect = Rect(cx, cy, CELL_W, CELL_H_TOTAL - HEADER_H)
            pygame.draw.rect(screen, bg, cell_rect, border_radius=4)
            if is_selected:
                pygame.draw.rect(screen, _COLORS["border_accent"], cell_rect, 2, border_radius=4)
            else:
                pygame.draw.rect(screen, _COLORS["border"], cell_rect, 1, border_radius=4)

            # Thumbnail
            thumb = self._get_thumb(frame.variant_id)
            if thumb:
                tx = cx + (CELL_W - THUMB_SIZE) // 2
                ty = cy + 4
                screen.blit(thumb, (tx, ty))

            # Frame index
            idx_label = self._font_sm.render(f"#{frame.variant_id}", True, _COLORS["text_dim"])
            screen.blit(idx_label, (cx + 4, cy + 4))

            # Duration
            dur_y = cy + THUMB_SIZE + 8
            if self._editing_dur and self._editing_idx == i:
                dur_str = self._dur_text + ("|" if (pygame.time.get_ticks() // 500) % 2 else "")
                dur_surf = self._font_sm.render(f"{dur_str}ms", True, _COLORS["text_edit"])
            else:
                dur_surf = self._font_sm.render(f"{frame.duration_ms:.0f}ms", True, _COLORS["text"])
            dur_x = cx + (CELL_W - dur_surf.get_width()) // 2
            screen.blit(dur_surf, (dur_x, dur_y))

        # Drag insert indicator
        if self._dragging and self._drag_insert >= 0:
            insert_x = self.rect.x + CELL_PAD + self._drag_insert * (CELL_W + CELL_PAD) - int(self.scroll_x) - 2
            pygame.draw.line(
                screen, _COLORS["drag_line"],
                (insert_x, content_y), (insert_x, content_y + CELL_H_TOTAL - HEADER_H),
                3,
            )

        # Scrubber
        if self.frames and self.scrubber_frac > 0:
            total_w = len(self.frames) * (CELL_W + CELL_PAD)
            sx = self.rect.x + CELL_PAD + int(self.scrubber_frac * total_w) - int(self.scroll_x)
            if self.rect.x <= sx <= self.rect.right:
                pygame.draw.line(
                    screen, _COLORS["scrubber"],
                    (sx, content_y - 2), (sx, content_y + CELL_H_TOTAL - HEADER_H + 2),
                    2,
                )

        # Scroll bar
        total_content_w = len(self.frames) * (CELL_W + CELL_PAD) + CELL_PAD
        if total_content_w > self.rect.w:
            bar_w = max(20, int(self.rect.w * (self.rect.w / total_content_w)))
            bar_x = self.rect.x + int((self.scroll_x / (total_content_w - self.rect.w)) * (self.rect.w - bar_w))
            bar_rect = Rect(bar_x, self.rect.bottom - 5, bar_w, 3)
            pygame.draw.rect(screen, _COLORS["border"], bar_rect, border_radius=2)

        screen.set_clip(clip)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _cell_at(self, mouse: Tuple[int, int]) -> int:
        if not self.rect.collidepoint(mouse):
            return -1
        content_y = self.rect.y + HEADER_H + 4
        if mouse[1] < content_y or mouse[1] > content_y + CELL_H_TOTAL - HEADER_H:
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

    def _insert_index_at(self, mouse: Tuple[int, int]) -> int:
        rx = mouse[0] - self.rect.x + self.scroll_x
        idx = int((rx + (CELL_W + CELL_PAD) // 2) // (CELL_W + CELL_PAD))
        return max(0, min(idx, len(self.frames)))

    def _is_duration_click(self, mouse: Tuple[int, int], idx: int) -> bool:
        content_y = self.rect.y + HEADER_H + 4
        dur_y = content_y + THUMB_SIZE + 8
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
                self.frames[self._editing_idx].duration_ms = max(10.0, min(val, 10000.0))
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
            copy = AnimationFrame(variant_id=orig.variant_id, duration_ms=orig.duration_ms)
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

    def _get_thumb(self, variant_id: int) -> Optional[pygame.Surface]:
        if variant_id in self._thumb_cache:
            return self._thumb_cache[variant_id]
        tw, th = self.tile_size
        cols = max(1, self.surface.get_width() // tw)
        col = variant_id % cols
        row = variant_id // cols
        src = Rect(col * tw, row * th, tw, th)
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
            self._font = pygame.font.SysFont("Arial", 13)
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("Arial", 11)
