from __future__ import annotations

from typing import Callable, Optional

import pygame
from pygame import Rect, Surface

from widgets.ui.theme import COLORS, FONTS
from utils.font_manager import font_manager, FontWeight


CHECKBOX_SIZE = 16
CHECKBOX_RADIUS = 3
CHECKBOX_LABEL_GAP = 8
CHECKMARK_OFFSET_X = 3
CHECKMARK_OFFSET_Y = -1


class Checkbox:
    """A toggleable checkbox with label.

    Tracks its own checked and disabled state independently.
    Fires on_changed(checked: bool) when the user toggles it.
    Returns True from handle_event when click is consumed.
    """

    def __init__(
        self,
        rect: Rect,
        label: str,
        checked: bool = False,
        disabled: bool = False,
        on_changed: Optional[Callable[[bool], None]] = None,
    ):
        self.rect = rect
        self.label = label
        self._checked = checked
        self._disabled = disabled
        self._on_changed = on_changed
        self._hovered = False
        self._font = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)

    @property
    def checked(self) -> bool:
        return self._checked

    @checked.setter
    def checked(self, value: bool) -> None:
        self._checked = value

    @property
    def disabled(self) -> bool:
        return self._disabled

    @disabled.setter
    def disabled(self, value: bool) -> None:
        self._disabled = value

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._disabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._checked = not self._checked
                if self._on_changed:
                    self._on_changed(self._checked)
                return True
        return False

    def draw(self, screen: Surface) -> None:
        if self._disabled:
            box_color = (50, 50, 55)
            border_color = (55, 55, 60)
            text_color = (90, 90, 100)
            check_color = (100, 100, 100)
        elif self._checked:
            box_color = COLORS.success
            border_color = (60, 140, 90)
            text_color = COLORS.text_dim
            check_color = (255, 255, 255)
        else:
            box_color = (55, 55, 60)
            border_color = (65, 65, 70)
            text_color = COLORS.text_dim
            check_color = (200, 200, 200)

        cb_y = self.rect.y + (self.rect.h - CHECKBOX_SIZE) // 2
        check_rect = Rect(self.rect.x, cb_y, CHECKBOX_SIZE, CHECKBOX_SIZE)
        pygame.draw.rect(screen, box_color, check_rect, border_radius=CHECKBOX_RADIUS)
        pygame.draw.rect(screen, border_color, check_rect, 1, border_radius=CHECKBOX_RADIUS)

        if self._checked:
            surf = self._font.render("✓", True, check_color)
            screen.blit(surf, (self.rect.x + CHECKMARK_OFFSET_X, cb_y + CHECKMARK_OFFSET_Y))

        label_x = self.rect.x + CHECKBOX_SIZE + CHECKBOX_LABEL_GAP
        label_y = self.rect.y + (self.rect.h - self._font.get_height()) // 2
        lbl = self._font.render(self.label, True, text_color)
        screen.blit(lbl, (label_x, label_y))
