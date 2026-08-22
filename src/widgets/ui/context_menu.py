"""Reusable right-click popup menu.

Reuses :class:`MenuAction` / :class:`MenuSeparator` from the menubar so the
same item definitions can drive both dropdown and context menus.
"""

from __future__ import annotations

import pygame
from pygame import Rect, Surface

from utils.icon_manager import icon_manager

from .menubar import MenuAction, MenuSeparator
from .theme import COLORS, FONTS


class ContextMenu:
    """Flat popup menu. Show with :meth:`popup`, dismiss on outside click or Esc."""

    ITEM_H = 26
    SEP_H = 12
    MIN_W = 160

    def __init__(self):
        self.items: list = []
        self.rect = Rect(0, 0, 0, 0)
        self.item_rects: list[tuple[Rect, object]] = []
        self.is_open = False

    @property
    def font(self):
        return FONTS.get_medium_font()

    def popup(self, items: list, pos: tuple[int, int], screen_size=None) -> None:
        self.items = list(items)
        width = self.MIN_W
        for action in self.items:
            if isinstance(action, MenuSeparator):
                continue
            label_w = self.font.render(action.label, True, COLORS.text).get_width()
            if action.shortcut:
                sh_w = FONTS.get_small_font().render(
                    action.shortcut, True, COLORS.text_dim
                ).get_width()
                width = max(width, label_w + sh_w + 44)
            else:
                width = max(width, label_w + 34)

        total_h = sum(
            self.SEP_H if isinstance(a, MenuSeparator) else self.ITEM_H
            for a in self.items
        )
        x, y = pos
        if screen_size:
            x = min(x, screen_size[0] - width - 4)
            y = min(y, screen_size[1] - total_h - 8)
        self.rect = Rect(max(0, x), max(0, y), width, total_h + 8)

        self.item_rects = []
        iy = self.rect.y + 4
        for action in self.items:
            h = self.SEP_H if isinstance(action, MenuSeparator) else self.ITEM_H
            self.item_rects.append((Rect(self.rect.x + 2, iy, self.rect.width - 4, h), action))
            iy += h
        self.is_open = True

    def close(self) -> None:
        self.is_open = False

    def _action_at(self, pos: tuple[int, int]):
        for item_rect, action in self.item_rects:
            if item_rect.collidepoint(pos):
                return action
        return None

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Consume all mouse/keyboard events while open."""
        if not self.is_open:
            return False
        mouse_pos = getattr(event, "pos", None) or pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN:
            activate = event.button == 1
            action = self._action_at(mouse_pos)
            self.close()
            if (
                activate
                and isinstance(action, MenuAction)
                and (action.is_enabled is None or action.is_enabled())
            ):
                action.callback()
            return True

        if event.type in (pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION, pygame.MOUSEWHEEL):
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.close()
                return True
            return True

        return True

    def draw(self, screen: Surface) -> None:
        if not self.is_open:
            return

        shadow_rect = self.rect.copy()
        shadow_rect.inflate_ip(4, 4)
        shadow = Surface((shadow_rect.w, shadow_rect.h), pygame.SRCALPHA)
        shadow.fill((*COLORS.bg, 160))
        screen.blit(shadow, shadow_rect.topleft)

        pygame.draw.rect(screen, COLORS.panel, self.rect)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)

        mouse_pos = pygame.mouse.get_pos()
        shortcut_font = FONTS.get_small_font()
        for item_rect, action in self.item_rects:
            if isinstance(action, MenuSeparator):
                mid_y = item_rect.centery
                pygame.draw.line(
                    screen,
                    COLORS.border_soft,
                    (item_rect.x + 8, mid_y),
                    (item_rect.right - 8, mid_y),
                    1,
                )
                continue

            disabled = action.is_enabled is not None and not action.is_enabled()
            hovered = item_rect.collidepoint(mouse_pos) and not disabled
            if hovered:
                pygame.draw.rect(screen, COLORS.accent, item_rect, border_radius=3)
                color = COLORS.text_on_accent
                shortcut_color = COLORS.text_on_accent
            elif disabled:
                color = COLORS.text_muted
                shortcut_color = COLORS.text_muted
            else:
                color = COLORS.text
                shortcut_color = COLORS.text_dim

            label_x = item_rect.x + 10
            if action.is_checked and action.is_checked():
                check_icon = icon_manager.get_icon("check", 14, COLORS.success)
                if check_icon:
                    screen.blit(check_icon, (item_rect.x + 5, item_rect.y + 6))
                label_x = item_rect.x + 24

            label_surf = self.font.render(action.label, True, color)
            screen.blit(label_surf, (label_x, item_rect.y + 5))

            if action.shortcut:
                sh_surf = shortcut_font.render(action.shortcut, True, shortcut_color)
                screen.blit(
                    sh_surf,
                    (item_rect.right - sh_surf.get_width() - 10, item_rect.y + 7),
                )
