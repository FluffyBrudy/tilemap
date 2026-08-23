from collections.abc import Callable

import pygame
from pygame import Rect

from .theme import COLORS, SHAPE

THUMB_MIN = 20


class Scrollbar:
    """Interactive scrollbar with drag, track-click, and wheel support."""

    def __init__(
        self,
        orientation: str = "vertical",
        rect: Rect | None = None,
        on_scroll: Callable[[float], None] | None = None,
    ):
        self.orientation = orientation
        self.rect = rect or Rect(0, 0, 10, 100)
        self.on_scroll = on_scroll

        self.content_size = 100
        self.view_size = 50
        self.scroll_pos = 0.0

        self._dragging = False
        self._drag_offset = 0.0
        self._drag_start_scroll = 0.0
        self._hovered = False

    def resize(self, x: int, y: int, w: int, h: int):
        self.rect = Rect(x, y, w, h)

    @property
    def max_scroll(self) -> float:
        return max(0.0, self.content_size - self.view_size)

    @property
    def _track_size(self) -> int:
        return self.rect.h if self.orientation == "vertical" else self.rect.w

    @property
    def thumb_size(self) -> int:
        if self.content_size <= self.view_size:
            return self._track_size
        ratio = self.view_size / self.content_size
        return max(THUMB_MIN, int(self._track_size * ratio))

    @property
    def thumb_pos(self) -> int:
        if self.max_scroll <= 0:
            return 0
        ratio = self.scroll_pos / self.max_scroll
        avail = self._track_size - self.thumb_size
        return int(ratio * avail)

    def _thumb_rect(self) -> Rect:
        tp = self.thumb_pos
        ts = self.thumb_size
        if self.orientation == "vertical":
            return Rect(self.rect.x, self.rect.y + tp, self.rect.w, ts)
        return Rect(self.rect.x + tp, self.rect.y, ts, self.rect.h)

    def set_range(self, content_size: float, view_size: float, scroll_pos: float):
        self.content_size = content_size
        self.view_size = view_size
        max_s = self.max_scroll
        self.scroll_pos = max(0.0, min(scroll_pos, max_s))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(event.pos):
                return False
            tr = self._thumb_rect()
            if tr.collidepoint(event.pos):
                self._dragging = True
                self._drag_start_scroll = self.scroll_pos
                pos_val = event.pos[1 if self.orientation == "vertical" else 0]
                self._drag_offset = (
                    pos_val - tr.y if self.orientation == "vertical" else pos_val - tr.x
                )
            else:
                pos_val = event.pos[1 if self.orientation == "vertical" else 0]
                rel = pos_val - (
                    self.rect.y if self.orientation == "vertical" else self.rect.x
                )
                ratio = rel / self._track_size
                self.scroll_pos = max(
                    0.0, min(ratio * self.max_scroll, self.max_scroll)
                )
                if self.on_scroll:
                    self.on_scroll(self.scroll_pos)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and self._hovered:
            if event.button == 4:
                step = self.view_size * 0.1
                self.scroll_pos = max(0.0, self.scroll_pos - step)
                if self.on_scroll:
                    self.on_scroll(self.scroll_pos)
                return True
            if event.button == 5:
                step = self.view_size * 0.1
                self.scroll_pos = min(self.max_scroll, self.scroll_pos + step)
                if self.on_scroll:
                    self.on_scroll(self.scroll_pos)
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                self._dragging = False
                return True
            return False

        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
            if self._dragging:
                pos_val = event.pos[1 if self.orientation == "vertical" else 0]
                track_start = (
                    self.rect.y if self.orientation == "vertical" else self.rect.x
                )
                rel = pos_val - track_start - self._drag_offset
                avail = self._track_size - self.thumb_size
                if avail > 0:
                    ratio = rel / avail
                    self.scroll_pos = max(
                        0.0, min(ratio * self.max_scroll, self.max_scroll)
                    )
                    if self.on_scroll:
                        self.on_scroll(self.scroll_pos)
                return True
            return False

        if event.type == pygame.MOUSEWHEEL:
            mods = pygame.key.get_mods()
            if self._hovered and not (mods & (pygame.KMOD_CTRL | pygame.KMOD_META)):
                step = self.view_size * 0.1
                if self.orientation == "vertical":
                    self.scroll_pos -= event.y * step
                else:
                    self.scroll_pos += event.x * step
                self.scroll_pos = max(0.0, min(self.scroll_pos, self.max_scroll))
                if self.on_scroll:
                    self.on_scroll(self.scroll_pos)
                return True
            return False

        return False

    def draw(self, screen: pygame.Surface):
        if self.content_size <= self.view_size:
            return
        pygame.draw.rect(screen, COLORS.panel_alt, self.rect, border_radius=SHAPE.radius_sm)
        thumb_col = (
            COLORS.scrollbar_thumb_hover if self._hovered or self._dragging else COLORS.scrollbar_thumb
        )
        pygame.draw.rect(screen, thumb_col, self._thumb_rect(), border_radius=SHAPE.radius_sm)
