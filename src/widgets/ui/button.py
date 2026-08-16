from collections.abc import Callable

import pygame

from utils.icon_manager import icon_manager

from ..widget_base import WidgetBase
from .theme import COLORS, FONTS, SHAPE


class Button(WidgetBase):
    def __init__(
        self,
        rect,
        text="",
        *,
        icon_key=None,
        icon_size=20,
        tooltip_text="",
        font=None,
        text_color=None,
        accent=False,
        danger=False,
        bg=None,
        border_color=None,
        border_radius=None,
        on_click: Callable[[], None] | None = None,
    ):
        border_width = SHAPE.border
        super().__init__(
            rect,
            padding=0,
            border_width=border_width,
            border_radius=border_radius
            if border_radius is not None
            else SHAPE.radius_sm,
            bg=bg,
            border_color=border_color,
        )
        self.text = text
        self.icon_key = icon_key
        self.icon_size = icon_size
        self.tooltip_text = tooltip_text
        self.font = font or FONTS.get_medium_font()
        self._text_color = text_color
        self.accent = accent
        self.danger = danger
        self.on_click = on_click
        self._active = False
        self._hovered = False
        self._pressed = False
        self._enabled = True

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, val):
        self._enabled = val

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, val):
        self._active = val

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self._enabled:
            return False

        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
                if self.on_click:
                    self.on_click()
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._pressed = False
            return False

        return False

    def draw(self, surface):
        if self._active:
            bg = COLORS.accent_active
            border = COLORS.border
            text_color = self._text_color or COLORS.text
        elif self._pressed:
            bg = (
                COLORS.accent_active
                if self.accent
                else (COLORS.danger_hover if self.danger else COLORS.header)
            )
            border = COLORS.border
            text_color = self._text_color or COLORS.text
        elif self._hovered:
            bg = (
                COLORS.accent_hover
                if self.accent
                else (COLORS.danger_hover if self.danger else COLORS.hover)
            )
            border = COLORS.border
            text_color = self._text_color or COLORS.text
        else:
            bg = (
                self._bg
                if self._bg is not None
                else (
                    COLORS.accent
                    if self.accent
                    else COLORS.danger if self.danger else COLORS.panel_alt
                )
            )
            border = self._border if self._border is not None else COLORS.border_soft
            text_color = self._text_color or COLORS.text

        if not self._enabled:
            bg = COLORS.panel_alt
            border = COLORS.border_soft
            text_color = COLORS.text_muted

        rect = self.rect
        pygame.draw.rect(surface, bg, rect, border_radius=self.br)
        if self.bw:
            pygame.draw.rect(surface, border, rect, self.bw, border_radius=self.br)

        if self.icon_key:
            icon = icon_manager.get_icon(self.icon_key, self.icon_size, text_color)
            surface.blit(icon, icon.get_rect(center=rect.center))
        elif self.text:
            label = self.font.render(self.text, True, text_color)
            surface.blit(label, label.get_rect(center=rect.center))
