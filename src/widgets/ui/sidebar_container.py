from collections.abc import Callable

import pygame
from pygame import Rect

from ..widget_base import WidgetBase
from .button import Button
from .theme import COLORS, FONTS


class ToolbarAction:
    def __init__(self, label: str, on_click: Callable, tooltip: str = ""):
        self.label = label
        self.on_click = on_click
        self.tooltip = tooltip


class Tab:
    def __init__(
        self, name: str, widget, actions: list[ToolbarAction] | None = None
    ):
        self.name = name
        self.widget = widget
        self.actions = actions or []


class SidebarContainer(WidgetBase):
    def __init__(self, editor, rect):
        super().__init__(rect, border_radius=0)
        self.editor = editor
        self.tabs: list[Tab] = []
        self.active_idx = 0

        self.tab_bar_h = 30
        self.toolbar_h = 35
        self._toolbar_buttons: list[Button] = []

    def add_tab(self, name: str, widget, actions: list[ToolbarAction] | None = None):
        self.tabs.append(Tab(name, widget, actions or []))
        self._rebuild_toolbar()

    def _rebuild_toolbar(self):
        self._toolbar_buttons.clear()
        if not self.tabs or self.active_idx >= len(self.tabs):
            return
        tab = self.tabs[self.active_idx]
        n = len(tab.actions)
        if n == 0:
            return
        btn_size = 28
        gap = 4
        total_w = n * btn_size + (n - 1) * gap
        start_x = self.content_rect.right - total_w - 6
        btn_y = self.rect.bottom - self.toolbar_h + (self.toolbar_h - btn_size) // 2
        for action in tab.actions:
            btn = Button(
                Rect(start_x, btn_y, btn_size, btn_size),
                action.label,
                on_click=action.on_click,
            )
            btn._tooltip = action.tooltip
            self._toolbar_buttons.append(btn)
            start_x += btn_size + gap

    def _get_tab_bar_rect(self):
        return Rect(self.rect.x, self.rect.y, self.rect.w, self.tab_bar_h)

    def _get_content_rect(self):
        return Rect(
            self.rect.x,
            self.rect.y + self.tab_bar_h,
            self.rect.w,
            self.rect.h - self.tab_bar_h - self.toolbar_h,
        )

    def _get_toolbar_rect(self):
        return Rect(
            self.rect.x, self.rect.bottom - self.toolbar_h, self.rect.w, self.toolbar_h
        )

    def _get_tab_at_pos(self, pos) -> int | None:
        if pos[1] < self.rect.y or pos[1] > self.rect.y + self.tab_bar_h:
            return None
        tab_w = self.rect.w // max(1, len(self.tabs))
        idx = (pos[0] - self.rect.x) // tab_w
        if 0 <= idx < len(self.tabs):
            return idx
        return None

    def resize(self, x, y, w, h):
        super().resize(x, y, w, h)
        content_rect = self._get_content_rect()
        for tab in self.tabs:
            if hasattr(tab.widget, "resize"):
                tab.widget.resize(
                    content_rect.x, content_rect.y, content_rect.w, content_rect.h
                )
        self._rebuild_toolbar()

    def handle_event(self, event: pygame.event.Event) -> bool:

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self._get_tab_at_pos(event.pos)
            if idx is not None and idx != self.active_idx:
                self.active_idx = idx
                self._rebuild_toolbar()
                content_rect = self._get_content_rect()
                tab = self.tabs[self.active_idx]
                if hasattr(tab.widget, "resize"):
                    tab.widget.resize(
                        content_rect.x, content_rect.y, content_rect.w, content_rect.h
                    )
                return True

        for btn in self._toolbar_buttons:
            if btn.handle_event(event):
                return True

        if self.tabs and self.active_idx < len(self.tabs):
            tab = self.tabs[self.active_idx]
            if hasattr(tab.widget, "handle_event"):
                if tab.widget.handle_event(event):
                    return True

        return False

    def draw(self, screen):

        pygame.draw.rect(screen, COLORS.panel, self.rect)

        tab_bar_rect = self._get_tab_bar_rect()
        pygame.draw.rect(screen, COLORS.header, tab_bar_rect)

        if self.tabs:
            tab_w = self.rect.w // len(self.tabs)
            for i, tab in enumerate(self.tabs):
                r = Rect(self.rect.x + i * tab_w, self.rect.y, tab_w, self.tab_bar_h)
                is_active = i == self.active_idx
                bg = COLORS.selected if is_active else COLORS.header
                pygame.draw.rect(screen, bg, r)
                if not is_active:
                    pygame.draw.line(
                        screen, COLORS.border, r.bottomleft, r.bottomright, 1
                    )
                label = FONTS.get_medium_font().render(
                    tab.name,
                    True,
                    COLORS.text_on_accent if is_active else COLORS.text,
                )
                screen.blit(
                    label, (r.x + 8, r.y + (self.tab_bar_h - label.get_height()) // 2)
                )

        if self.tabs and self.active_idx < len(self.tabs):
            tab = self.tabs[self.active_idx]
            if hasattr(tab.widget, "draw"):
                tab.widget.draw(screen)

        toolbar_rect = self._get_toolbar_rect()
        pygame.draw.rect(screen, COLORS.header, toolbar_rect)
        pygame.draw.line(
            screen, COLORS.border, toolbar_rect.topleft, toolbar_rect.topright, 1
        )

        for btn in self._toolbar_buttons:
            btn.draw(screen)

        mx, my = pygame.mouse.get_pos()
        for btn in self._toolbar_buttons:
            if (
                hasattr(btn, "_tooltip")
                and btn._tooltip
                and btn.rect.collidepoint(mx, my)
            ):
                self.editor.tooltip.show(btn._tooltip, (mx + 10, my + 10))
