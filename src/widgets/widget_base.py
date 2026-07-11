import pygame
from pygame import Rect

from .ui.theme import COLORS, SHAPE


class WidgetBase:
    def __init__(self, rect, *,
                 padding=None, padding_x=None, padding_y=None,
                 border_width=None, border_radius=None,
                 bg=None, border_color=None):
        self.rect = Rect(rect)
        p = padding or 0
        self.px = padding_x if padding_x is not None else p
        self.py = padding_y if padding_y is not None else p
        self.bw = border_width if border_width is not None else SHAPE.border
        self.br = border_radius if border_radius is not None else SHAPE.radius
        self._bg = bg
        self._border = border_color
        self._update_content_rect()

    def resize(self, x, y, w, h):
        self.rect = Rect(x, y, w, h)
        self._update_content_rect()

    def _update_content_rect(self):
        px = self.bw + self.px
        py = self.bw + self.py
        self.content_rect = Rect(
            self.rect.x + px,
            self.rect.y + py,
            max(0, self.rect.w - 2 * px),
            max(0, self.rect.h - 2 * py),
        )

    def draw_base(self, surface):
        bg = self._bg if self._bg is not None else COLORS.panel
        border = self._border if self._border is not None else COLORS.border
        pygame.draw.rect(surface, bg, self.rect, border_radius=self.br)
        if self.bw:
            pygame.draw.rect(surface, border, self.rect, self.bw,
                             border_radius=self.br)
