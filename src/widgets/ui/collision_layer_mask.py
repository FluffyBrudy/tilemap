"""
Collision Layer/Mask Selector Widget.

Godot-inspired physics layer and collision mask selector.
Supports 16 layers with single-select layer and multi-select mask.
"""

from __future__ import annotations

from typing import Callable, Optional

import pygame
from pygame import Rect, Surface

from widgets.ui.theme import COLORS, FONTS, SHAPE
from utils.font_manager import font_manager, FontWeight


class _BitButton:
    """A single bit toggle button."""

    def __init__(
        self,
        rect: Rect,
        bit_index: int,
        label: str,
        is_active: bool = False,
    ):
        self.rect = rect
        self.bit_index = bit_index
        self.label = label
        self.is_active = is_active
        self.is_hovered = False

    def contains(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)

    def draw(self, screen: Surface, is_radio: bool = False) -> None:
        if self.is_active:
            bg = COLORS.accent
            text_col = COLORS.text
        elif self.is_hovered:
            bg = COLORS.accent_hover if not is_radio else COLORS.hover
            text_col = COLORS.text
        else:
            bg = COLORS.panel_alt
            text_col = COLORS.text_dim

        pygame.draw.rect(screen, bg, self.rect, border_radius=SHAPE.radius_sm)
        pygame.draw.rect(
            screen, COLORS.border_soft, self.rect, 1, border_radius=SHAPE.radius_sm
        )

        font = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)
        txt = font.render(self.label, True, text_col)
        screen.blit(txt, txt.get_rect(center=self.rect.center))


class CollisionLayerMaskWidget:
    """
    Reusable collision layer/mask selector.

    Layer: single-select (radio) — only one bit can be set.
    Mask:  multi-select (checkbox) — any combination of bits.

    Values are stored as integers:
        collision_layer = 1 << bit_index  (e.g., layer 1 = 0x1)
        collision_mask  = bitmask          (e.g., layers 1+3 = 0x5)
    """

    BTN_W = 28
    BTN_H = 22
    BTN_GAP = 3
    ROW_GAP = 4
    LABEL_W = 50
    PADDING = 8

    @classmethod
    def calc_min_width(cls, max_layers: int = 16, cols: int = 8) -> int:
        """Calculate minimum width needed to fit all buttons in one row."""
        actual_cols = min(max_layers, cols)
        return (
            cls.PADDING
            + cls.LABEL_W
            + actual_cols * (cls.BTN_W + cls.BTN_GAP)
            - cls.BTN_GAP
            + cls.PADDING
        )

    @classmethod
    def calc_min_height(cls, max_layers: int = 16, cols: int = 8) -> int:
        """Calculate minimum height needed."""
        rows = (max_layers + cols - 1) // cols
        return (
            cls.PADDING
            + 2 * (rows * (cls.BTN_H + cls.BTN_GAP) - cls.BTN_GAP)
            + cls.ROW_GAP
            + cls.PADDING
        )

    def __init__(
        self,
        rect: Rect,
        max_layers: int = 16,
        initial_layer: int = 1,
        initial_mask: int = 0xFFFF,
        on_changed: Optional[Callable[[int, int], None]] = None,
    ):
        self.rect = rect
        self.max_layers = min(max_layers, 32)
        self._collision_layer = initial_layer if initial_layer > 0 else 1
        self._collision_mask = initial_mask
        self._on_changed = on_changed

        self._cols = 8
        self._rows_per_axis = (self.max_layers + self._cols - 1) // self._cols

        self._layer_buttons: list[_BitButton] = []
        self._mask_buttons: list[_BitButton] = []
        self._rebuild_buttons()

    def get_layer(self) -> int:
        return self._collision_layer

    def get_mask(self) -> int:
        return self._collision_mask

    def set_layer(self, value: int) -> None:
        if value <= 0:
            value = 1
        self._collision_layer = value
        self._sync_buttons()

    def set_mask(self, value: int) -> int:
        self._collision_mask = value
        self._sync_buttons()

    def resize(self, rect: Rect) -> None:
        self.rect = rect
        self._rebuild_buttons()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._update_hover(event.pos)
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos

            for btn in self._layer_buttons:
                if btn.contains(pos):
                    self._collision_layer = 1 << btn.bit_index
                    self._sync_buttons()
                    self._fire_changed()
                    return True

            for btn in self._mask_buttons:
                if btn.contains(pos):
                    self._collision_mask ^= 1 << btn.bit_index
                    self._sync_buttons()
                    self._fire_changed()
                    return True

        return False

    def draw(self, screen: Surface) -> None:
        font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)
        bold_font = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.BOLD)

        y = self.rect.y + self.PADDING

        label_surf = bold_font.render("Layer:", True, COLORS.text)
        screen.blit(label_surf, (self.rect.x + self.PADDING, y))
        label_surf.get_width() + self.PADDING

        for btn in self._layer_buttons:
            btn.draw(screen, is_radio=True)

        y += (
            self._rows_per_axis * (self.BTN_H + self.BTN_GAP)
            - self.BTN_GAP
            + self.ROW_GAP
        )

        label_surf = bold_font.render("Mask:", True, COLORS.text)
        screen.blit(label_surf, (self.rect.x + self.PADDING, y))

        for btn in self._mask_buttons:
            btn.draw(screen, is_radio=False)

    def _rebuild_buttons(self) -> None:
        self._layer_buttons.clear()
        self._mask_buttons.clear()

        start_x = self.rect.x + self.PADDING + self.LABEL_W
        start_y_layer = self.rect.y + self.PADDING
        start_y_mask = (
            start_y_layer
            + self._rows_per_axis * (self.BTN_H + self.BTN_GAP)
            + self.ROW_GAP
        )

        for i in range(self.max_layers):
            col = i % self._cols
            row = i // self._cols
            x = start_x + col * (self.BTN_W + self.BTN_GAP)
            y_layer = start_y_layer + row * (self.BTN_H + self.BTN_GAP)
            y_mask = start_y_mask + row * (self.BTN_H + self.BTN_GAP)
            btn_rect = Rect(x, y_layer, self.BTN_W, self.BTN_H)
            mask_rect = Rect(x, y_mask, self.BTN_W, self.BTN_H)

            layer_active = (self._collision_layer >> i) & 1
            mask_active = (self._collision_mask >> i) & 1

            self._layer_buttons.append(
                _BitButton(btn_rect, i, str(i + 1), layer_active)
            )
            self._mask_buttons.append(_BitButton(mask_rect, i, str(i + 1), mask_active))

    def _sync_buttons(self) -> None:
        for btn in self._layer_buttons:
            btn.is_active = bool((self._collision_layer >> btn.bit_index) & 1)
        for btn in self._mask_buttons:
            btn.is_active = bool((self._collision_mask >> btn.bit_index) & 1)

    def _update_hover(self, pos: tuple[int, int]) -> None:
        for btn in self._layer_buttons:
            btn.is_hovered = btn.contains(pos) and not btn.is_active
        for btn in self._mask_buttons:
            btn.is_hovered = btn.contains(pos) and not btn.is_active

    def _fire_changed(self) -> None:
        if self._on_changed:
            self._on_changed(self._collision_layer, self._collision_mask)
