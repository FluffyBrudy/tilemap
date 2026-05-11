"""
Simple dialog for selecting tileset type (tile vs object).
"""

import pygame
from pygame import Rect, Surface
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

        self.radio_tile_rect = Rect(0, 0, 20, 20)
        self.radio_object_rect = Rect(0, 0, 20, 20)
        self.radio_tile_label_rect = Rect(0, 0, 0, 0)
        self.radio_object_label_rect = Rect(0, 0, 0, 0)
        self.radio_tile_row_rect = Rect(0, 0, 0, 0)
        self.radio_object_row_rect = Rect(0, 0, 0, 0)

        self.btn_ok = Rect(0, 0, 80, 30)
        self.btn_cancel = Rect(0, 0, 80, 30)

        self.font_title = pygame.font.SysFont("Arial", 18, bold=True)
        self.font_text = pygame.font.SysFont("Arial", 14)

        self.btn_ok_hover = False
        self.btn_cancel_hover = False
        self._layout()

    def _layout(self):
        """Position child controls from the current dialog rect."""
        self.rect.center = self.editor_rect.center

        radio_x = self.rect.x + 42
        row_w = self.rect.w - 84
        row_h = 38
        first_y = self.rect.y + 58
        gap = 12

        self.radio_tile_row_rect = Rect(radio_x - 10, first_y - 9, row_w, row_h)
        self.radio_object_row_rect = Rect(
            radio_x - 10, first_y + row_h + gap - 9, row_w, row_h
        )

        self.radio_tile_rect = Rect(radio_x, first_y, 20, 20)
        self.radio_object_rect = Rect(radio_x, first_y + row_h + gap, 20, 20)

        label_x = radio_x + 34
        self.radio_tile_label_rect = Rect(label_x, first_y - 4, row_w - 44, 28)
        self.radio_object_label_rect = Rect(
            label_x, first_y + row_h + gap - 4, row_w - 44, 28
        )

        btn_y = self.rect.y + 166
        self.btn_ok = Rect(self.rect.centerx - 94, btn_y, 80, 30)
        self.btn_cancel = Rect(self.rect.centerx + 14, btn_y, 80, 30)

    def show(self, on_confirm: Callable[[str], None], on_cancel: Callable[[], None]):
        """Show the dialog."""
        print(f"DEBUG: TilesetTypeDialog.show() called, active={self.active}")
        # Force hide first to ensure clean state
        if self.active:
            print("DEBUG: Dialog was already active, hiding first")
            self.hide()
        self.active = True
        self.selected_type = "tile"
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.btn_ok_hover = False
        self.btn_cancel_hover = False
        print("DEBUG: TilesetTypeDialog is now active")

    def hide(self):
        """Hide the dialog."""
        self.active = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle events. Returns True if event was consumed."""
        if not self.active:
            return False

        self._layout()
        mouse_pos = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

            if self.radio_tile_row_rect.collidepoint(mouse_pos):
                self.selected_type = "tile"
                return True
            if self.radio_object_row_rect.collidepoint(mouse_pos):
                self.selected_type = "object"
                return True

            if self.btn_ok.collidepoint(mouse_pos):
                print(f"DEBUG: OK button clicked, selected_type={self.selected_type}")
                if self.on_confirm and self.selected_type:
                    self.on_confirm(self.selected_type)
                self.hide()
                return True
            if self.btn_cancel.collidepoint(mouse_pos):
                print("DEBUG: Cancel button clicked")
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

        self._layout()
        pygame.draw.rect(surface, self.bg_color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 2)

        title = self.font_title.render("Tileset Type", True, self.text_color)
        title_rect = title.get_rect(topleft=(self.rect.x + 20, self.rect.y + 15))
        surface.blit(title, title_rect)

        self._draw_radio(
            surface,
            self.radio_tile_rect,
            self.radio_tile_row_rect,
            self.selected_type == "tile",
            "Tile Tileset (grid-based)",
            self.radio_tile_label_rect,
        )

        self._draw_radio(
            surface,
            self.radio_object_rect,
            self.radio_object_row_rect,
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
        row_rect: Rect,
        is_selected: bool,
        label: str,
        label_rect: Rect,
    ):
        """Draw a radio button with label."""
        pygame.draw.rect(surface, (48, 48, 48), row_rect, border_radius=6)
        pygame.draw.rect(surface, self.border_color, row_rect, 1, border_radius=6)

        center = (radio_rect.centerx, radio_rect.centery)
        radius = radio_rect.width // 2

        pygame.draw.circle(surface, self.border_color, center, radius, 2)

        if is_selected:

            pygame.draw.circle(surface, self.radio_color, center, radius - 4)

        label_surf = self.font_text.render(label, True, self.text_color)
        label_pos = label_surf.get_rect(midleft=(label_rect.x, radio_rect.centery))
        surface.blit(label_surf, label_pos)
