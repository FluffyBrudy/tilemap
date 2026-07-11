"""
Dialog for selecting layer type (tile vs object).
"""

import pygame
from pygame import Rect, Surface
from typing import Callable, Optional

from .dialog_base import DialogBase
from .theme import COLORS, FONTS


class LayerTypeDialog(DialogBase):
    """Dialog to select whether a new layer is tile-based or object-based."""

    def __init__(self, editor_rect: Rect):
        super().__init__(editor_rect, (400, 220), title="Layer Type")
        self.selected_type: Optional[str] = None
        self.on_confirm: Optional[Callable[[str], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        self.btn_ok_hover = False
        self.btn_cancel_hover = False
        self._layout()

    def _layout(self):
        self.center()
        radio_y = self.rect.y + 60
        radio_x = self.rect.x + 40
        self.radio_tile_rect = Rect(radio_x, radio_y, 20, 20)
        self.radio_object_rect = Rect(radio_x, radio_y + 50, 20, 20)

        self.radio_tile_label_rect = Rect(radio_x + 35, radio_y - 5, 200, 30)
        self.radio_object_label_rect = Rect(radio_x + 35, radio_y + 45, 200, 30)

        btn_y = self.rect.y + 160
        btn_w, btn_h = 80, 30
        self.btn_ok = Rect(self.rect.x + 100, btn_y, btn_w, btn_h)
        self.btn_cancel = Rect(self.rect.x + 220, btn_y, btn_w, btn_h)

    def show(self, on_confirm: Callable[[str], None], on_cancel: Callable[[], None]):
        """Show the dialog."""
        self.active = True
        self.selected_type = "tile"
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.btn_ok_hover = False
        self.btn_cancel_hover = False
        self._layout()

    def hide(self):
        """Hide the dialog."""
        self.active = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle events. Returns True if event was consumed."""
        if not self.active:
            return False

        if self.handle_event_base(event):
            return True

        mouse_pos = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

            if self.radio_tile_rect.collidepoint(mouse_pos):
                self.selected_type = "tile"
                return True
            if self.radio_object_rect.collidepoint(mouse_pos):
                self.selected_type = "object"
                return True

            if self.btn_ok.collidepoint(mouse_pos):
                if self.on_confirm and self.selected_type:
                    self.on_confirm(self.selected_type)
                self.hide()
                return True
            if self.btn_cancel.collidepoint(mouse_pos):
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self.on_confirm and self.selected_type:
                    self.on_confirm(self.selected_type)
                self.hide()
                return True

        elif event.type == pygame.MOUSEMOTION:
            self.btn_ok_hover = self.btn_ok.collidepoint(mouse_pos)
            self.btn_cancel_hover = self.btn_cancel.collidepoint(mouse_pos)

        return False

    def draw(self, surface: Surface):
        """Draw the dialog on the given surface."""
        if not self.active:
            return

        self._layout()
        super().draw_base(surface)
        self._draw_title(surface)

        self._draw_radio(
            surface,
            self.radio_tile_rect,
            self.selected_type == "tile",
            "Tile Layer (grid-based)",
            self.radio_tile_label_rect,
        )

        self._draw_radio(
            surface,
            self.radio_object_rect,
            self.selected_type == "object",
            "Object Layer (free-positioned)",
            self.radio_object_label_rect,
        )

        self._draw_button(surface, self.btn_ok, self.btn_ok_hover, "OK")
        self._draw_button(surface, self.btn_cancel, self.btn_cancel_hover, "Cancel")

    def _draw_radio(
        self,
        surface: Surface,
        radio_rect: Rect,
        is_selected: bool,
        label: str,
        label_rect: Rect,
    ):
        """Draw a radio button with label."""

        center = (radio_rect.centerx, radio_rect.centery)
        radius = radio_rect.width // 2

        pygame.draw.circle(surface, COLORS.border, center, radius, 2)

        if is_selected:
            pygame.draw.circle(surface, COLORS.accent, center, radius - 4)

        label_surf = FONTS.get_medium_font().render(label, True, COLORS.text)
        label_pos = label_surf.get_rect(midleft=(label_rect.x, radio_rect.centery))
        surface.blit(label_surf, label_pos)
