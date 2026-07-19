from collections.abc import Callable

import pygame
from pygame import Rect, Surface

from ..widget_base import WidgetBase
from .theme import COLORS, FONTS


class DialogBase(WidgetBase):
    def __init__(
        self, editor_rect: Rect, size: tuple[int, int], title: str = "", **kwargs
    ):
        rect = Rect(0, 0, *size)
        super().__init__(rect, **kwargs)
        self.editor_rect = editor_rect
        self.rect.center = editor_rect.center
        self._update_content_rect()

        self.active = False
        self.title = title
        self.on_confirm: Callable | None = None
        self.on_cancel: Callable | None = None

    def center(self):
        self.rect.center = self.editor_rect.center
        self._update_content_rect()

    def show(self, on_confirm=None, on_cancel=None):
        if self.active:
            self.hide()
        self.active = True
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.center()

    def hide(self):
        self.active = False

    def draw_base(self, surface: Surface):
        if not self.active:
            return
        super().draw_base(surface)

    def _draw_title(self, surface: Surface, color=None):
        if not self.title:
            return
        font = FONTS.get_title_font()
        surf = font.render(self.title, True, color or COLORS.text)
        surface.blit(surf, (self.rect.x + 20, self.rect.y + 15))

    def _draw_button(
        self,
        surface: Surface,
        rect: Rect,
        hover: bool,
        text: str,
        *,
        color=None,
        hover_color=None,
        font=None,
    ):
        if color is None:
            color = COLORS.accent
        if hover_color is None:
            hover_color = COLORS.accent_hover
        bg = hover_color if hover else color
        pygame.draw.rect(surface, bg, rect)
        f = font or FONTS.get_medium_font()
        surf = f.render(text, True, COLORS.text)
        surface.blit(surf, surf.get_rect(center=rect.center))

    def handle_event_base(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.on_cancel:
                self.on_cancel()
            self.hide()
            return True
        return False
