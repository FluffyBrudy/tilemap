from collections.abc import Callable

import pygame
from pygame import Rect

from .theme import COLORS


class Splitter:
    def __init__(self, rect=None, orientation="horizontal"):
        self.rect = Rect(rect) if rect else Rect(0, 0, 0, 6)
        self.orientation = orientation

        self._dragging = False
        self._hovered = False

        self.on_drag: Callable[[int], None] | None = None

    def resize(self, x, y, w, h):
        self.rect = Rect(x, y, w, h)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.orientation == "horizontal":
            return self._handle_event_axis(event, 1)
        return self._handle_event_axis(event, 0)

    def _handle_event_axis(self, event: pygame.event.Event, axis: int) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()
            if self.rect.collidepoint(pos):
                self._dragging = True
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._dragging:
            self._dragging = False
            return True

        if event.type == pygame.MOUSEMOTION:
            pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()
            if self._dragging:
                if self.on_drag:
                    self.on_drag(pos[axis])
                return True
            was_hovered = self._hovered
            self._hovered = self.rect.collidepoint(pos)
            if self._hovered:
                cursor = (
                    pygame.SYSTEM_CURSOR_SIZENS
                    if axis == 1
                    else pygame.SYSTEM_CURSOR_SIZEWE
                )
                pygame.mouse.set_cursor(cursor)
            elif was_hovered:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

        return False

    def draw(self, screen: pygame.Surface):
        if self.orientation == "horizontal":
            center = self.rect.centerx, self.rect.centery
            line_start = (self.rect.x, center[1])
            line_end = (self.rect.right, center[1])
        else:
            center = self.rect.centerx, self.rect.centery
            line_start = (center[0], self.rect.y)
            line_end = (center[0], self.rect.bottom)

        color = COLORS.accent if self._hovered or self._dragging else COLORS.border_soft
        pygame.draw.line(screen, color, line_start, line_end, 2)

        if self._hovered or self._dragging:
            for i in range(-1, 2):
                if self.orientation == "horizontal":
                    p1 = (self.rect.x + 10, center[1] + i * 3)
                    p2 = (self.rect.right - 10, center[1] + i * 3)
                else:
                    p1 = (center[0] + i * 3, self.rect.y + 10)
                    p2 = (center[0] + i * 3, self.rect.bottom - 10)
                pygame.draw.line(screen, COLORS.text_dim, p1, p2, 1)
