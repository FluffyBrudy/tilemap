"""
Simple dialog for selecting tileset type (tile vs object).
"""

import pygame
from pygame import Rect, Surface, Color
from typing import Callable, Optional


class TilesetTypeDialog:
    """Dialog to select whether a tileset is tile-based or object-based."""

    def __init__(self, editor_rect: Rect):
        self.editor_rect = editor_rect
        self.rect = Rect(0, 0, 400, 220)
        self.rect.center = editor_rect.center

        self.active = False
        self.selected_type: Optional[str] = None
        self.on_confirm: Optional[Callable[[str], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        self.bg_color = (40, 40, 40)
        self.border_color = (100, 100, 100)
        self.text_color = (255, 255, 255)
        self.radio_color = (100, 150, 255)
        self.button_color = (60, 100, 180)
        self.button_hover_color = (80, 120, 200)

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

        self.font_title = pygame.font.SysFont("Arial", 18, bold=True)
        self.font_text = pygame.font.SysFont("Arial", 14)

        self.btn_ok_hover = False
        self.btn_cancel_hover = False

    def show(self, on_confirm: Callable[[str], None], on_cancel: Callable[[], None]):
        """Show the dialog."""
        self.active = True
        self.selected_type = "tile"
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.btn_ok_hover = False
        self.btn_cancel_hover = False

    def hide(self):
        """Hide the dialog."""
        self.active = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle events. Returns True if event was consumed."""
        if not self.active:
            return False

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
            if event.key == pygame.K_ESCAPE:
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True
            elif event.key == pygame.K_RETURN:
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

        pygame.draw.rect(surface, self.bg_color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 2)

        title = self.font_title.render("Tileset Type", True, self.text_color)
        title_rect = title.get_rect(topleft=(self.rect.x + 20, self.rect.y + 15))
        surface.blit(title, title_rect)

        self._draw_radio(
            surface,
            self.radio_tile_rect,
            self.selected_type == "tile",
            "Tile Tileset (grid-based)",
            self.radio_tile_label_rect,
        )

        self._draw_radio(
            surface,
            self.radio_object_rect,
            self.selected_type == "object",
            "Object Tileset (free-positioned)",
            self.radio_object_label_rect,
        )

        ok_color = self.button_hover_color if self.btn_ok_hover else self.button_color
        cancel_color = (
            self.button_hover_color if self.btn_cancel_hover else self.button_color
        )

        pygame.draw.rect(surface, ok_color, self.btn_ok)
        pygame.draw.rect(surface, cancel_color, self.btn_cancel)

        ok_text = self.font_text.render("OK", True, self.text_color)
        cancel_text = self.font_text.render("Cancel", True, self.text_color)

        ok_text_rect = ok_text.get_rect(center=self.btn_ok.center)
        cancel_text_rect = cancel_text.get_rect(center=self.btn_cancel.center)

        surface.blit(ok_text, ok_text_rect)
        surface.blit(cancel_text, cancel_text_rect)

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

        pygame.draw.circle(surface, self.border_color, center, radius, 2)

        if is_selected:

            pygame.draw.circle(surface, self.radio_color, center, radius - 4)

        label_surf = self.font_text.render(label, True, self.text_color)
        surface.blit(label_surf, label_rect)
