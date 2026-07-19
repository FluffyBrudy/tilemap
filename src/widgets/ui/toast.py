from __future__ import annotations

from typing import Literal

import pygame
from pygame import Rect, Surface

from utils.icon_manager import icon_manager
from widgets.ui.theme import COLORS, FONTS
from widgets.widget_base import WidgetBase

ToastVariant = Literal["default", "success", "warning", "error"]


_VARIANT_CFG = {
    "default": {
        "accent": (60, 62, 66),
        "icon_name": "info",
        "icon_color": (150, 150, 150),
        "progress_color": (60, 62, 66),
    },
    "success": {
        "accent": "success",
        "icon_name": "check",
        "icon_color": "success",
        "progress_color": "success",
    },
    "warning": {
        "accent": "warning",
        "icon_name": "warning",
        "icon_color": "warning",
        "progress_color": "warning",
    },
    "error": {
        "accent": "danger",
        "icon_name": "error",
        "icon_color": "danger",
        "progress_color": "danger",
    },
}


def _resolve(color, default=None):
    if isinstance(color, str):
        return getattr(COLORS, color, default or color)
    return color


TOAST_WIDTH = 320
TOAST_MARGIN = 16
ANIM_DURATION = 0.3


class Toast(WidgetBase):
    def __init__(
        self,
        message: str,
        variant: ToastVariant = "default",
        duration: float = 3.0,
        direction: str = "right",
    ):
        super().__init__(
            Rect(0, 0, TOAST_WIDTH, 0),
            padding_x=10,
            padding_y=8,
            border_width=1,
            border_radius=5,
            bg=None,
            border_color=None,
        )
        self.message = message
        self.variant = variant
        self.duration = duration
        self.direction = direction

        self._elapsed = 0.0
        self._done = False

        self._font = FONTS.get_small_font()
        self._text_surf = self._font.render(self.message, True, COLORS.text)
        self._text_size = self._text_surf.get_size()

        icon_size = 14
        cfg = _VARIANT_CFG.get(variant, _VARIANT_CFG["default"])
        icon_color = _resolve(cfg["icon_color"], COLORS.text_dim)
        self._icon_surf = icon_manager.get_icon(cfg["icon_name"], icon_size, icon_color)

        self._icon_w = icon_size + 6
        icon_h = icon_size

        text_x = self.px + 4 + self._icon_w
        text_available = TOAST_WIDTH - text_x - self.px
        text_lines = []
        words = self.message.split(" ")
        current_line = ""
        for word in words:
            test = (current_line + " " + word).strip()
            if self._font.size(test)[0] <= text_available:
                current_line = test
            else:
                if current_line:
                    text_lines.append(current_line)
                current_line = word
        if current_line:
            text_lines.append(current_line)
        self._text_lines = text_lines
        text_h = len(text_lines) * (self._text_size[1] + 2)

        content_h = max(icon_h, text_h)
        toast_h = content_h + self.py * 2 + 4
        self.resize(0, 0, TOAST_WIDTH, toast_h)

        self._slide_distance = TOAST_WIDTH + TOAST_MARGIN
        self._current_x = 0.0

    def update(self, dt: float) -> None:
        self._elapsed += dt
        enter_end = ANIM_DURATION
        visible_end = enter_end + self.duration
        total = visible_end + ANIM_DURATION

        if self._elapsed >= total:
            self._done = True
            return

        if self.direction == "right":
            if self._elapsed < enter_end:
                p = self._elapsed / enter_end
                self._current_x = self._slide_distance * (1.0 - p)
            elif self._elapsed < visible_end:
                self._current_x = 0.0
            else:
                p = (self._elapsed - visible_end) / ANIM_DURATION
                self._current_x = self._slide_distance * p
        else:
            if self._elapsed < enter_end:
                p = self._elapsed / enter_end
                self._current_x = -self._slide_distance * (1.0 - p)
            elif self._elapsed < visible_end:
                self._current_x = 0.0
            else:
                p = (self._elapsed - visible_end) / ANIM_DURATION
                self._current_x = -self._slide_distance * p

    @property
    def done(self) -> bool:
        return self._done

    @property
    def slide_offset(self) -> float:
        return self._current_x

    def handle_event(self, event: pygame.event.Event) -> bool:
        return False

    def resize(self, x: int, y: int, w: int, h: int) -> None:
        super().resize(x, y, w, h)

    def draw(self, screen: Surface) -> None:
        if self._done:
            return

        x = int(self.rect.x + self._current_x)
        y = int(self.rect.y)

        w = self.rect.w
        h = self.rect.h

        bg_alpha = 230
        bg_surf = Surface((w, h), pygame.SRCALPHA)
        bg_surf.fill((*COLORS.bg, bg_alpha))
        pygame.draw.rect(
            bg_surf, (*COLORS.border_soft, bg_alpha), bg_surf.get_rect(), 1, 5
        )
        screen.blit(bg_surf, (x, y))

        cfg = _VARIANT_CFG.get(self.variant, _VARIANT_CFG["default"])
        accent_color = _resolve(cfg["accent"], COLORS.text_dim)
        accent_rect = Rect(x + 1, y + 1, 4, h - 2)
        pygame.draw.rect(screen, accent_color, accent_rect, border_radius=2)

        content_x = x + self.px + 4 + 6
        content_y = y + self.py

        screen.blit(self._icon_surf, (content_x, content_y + 1))

        text_x = content_x + self._icon_w
        line_h = self._text_size[1] + 2
        for i, line in enumerate(self._text_lines):
            line_surf = self._font.render(line, True, COLORS.text)
            screen.blit(line_surf, (text_x, content_y + i * line_h))

        progress = min(self._elapsed / (ANIM_DURATION + self.duration), 1.0)
        bar_w = int((1.0 - progress) * (w - 2))
        if bar_w > 0:
            bar_color = _resolve(cfg["progress_color"], COLORS.accent)
            bar_y = y + h - 3
            bar_rect = Rect(x + 1, bar_y, bar_w, 2)
            pygame.draw.rect(screen, bar_color, bar_rect, border_radius=1)


class ToastManager:
    def __init__(self, position: str = "top-right", direction: str = "right"):
        self.position = position
        self.direction = direction
        self._toasts: list[Toast] = []

    def show(
        self,
        message: str,
        variant: ToastVariant = "default",
        duration: float = 3.0,
    ) -> None:
        toast = Toast(message, variant, duration, self.direction)
        self._toasts.append(toast)

    def success(self, message: str, duration: float = 2.5) -> None:
        self.show(message, "success", duration)

    def warning(self, message: str, duration: float = 3.5) -> None:
        self.show(message, "warning", duration)

    def error(self, message: str, duration: float = 4.0) -> None:
        self.show(message, "error", duration)

    def update(self, screen: Surface, dt: float) -> None:
        screen_w = screen.get_width()

        for toast in self._toasts:
            toast.update(dt)

        self._toasts = [t for t in self._toasts if not t.done]

        y = TOAST_MARGIN
        for toast in self._toasts:
            if self.position == "top-right":
                base_x = screen_w - TOAST_MARGIN - TOAST_WIDTH
            else:
                base_x = TOAST_MARGIN
            toast.resize(base_x, y, toast.rect.w, toast.rect.h)
            y += toast.rect.h + 8

    def draw(self, screen: Surface) -> None:
        for toast in self._toasts:
            toast.draw(screen)
