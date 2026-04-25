"""
Dialog for selecting tileset type (tile vs object).
"""
import pygame
from pygame import Rect, Surface
from typing import Callable, Optional

from .theme import COLORS
from .base.uibase import create_simple_options
from .base.button import ButtonBase
from .base.dropdown import RadioGroup
from utils.font_manager import font_manager, FontWeight


class TilesetTypeDialog:
    """Dialog to select whether a tileset is tile-based or object-based."""

    def __init__(self, editor_rect: Rect):
        self.editor_rect = editor_rect
        self.rect = Rect(0, 0, 400, 220)
        self.rect.center = editor_rect.center

        self.active = False
        self.selected_type: Optional[str] = "tile"
        self.on_confirm: Optional[Callable[[str], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        self.bg_color = COLORS.panel
        self.border_color = COLORS.border_soft
        self.text_color = COLORS.text

        # Radio group for type selection
        radio_opts = create_simple_options(50, 30, margin_x=40, margin_y=60)
        self.radio_group = RadioGroup(
            radio_opts,
            ["Tile Tileset (grid-based)", "Object Tileset (free-positioned)"],
            on_change=self._on_radio_change,
        )

        # Buttons
        self.btn_ok = ButtonBase(
            create_simple_options(80, 30, bg_color=COLORS.accent),
            label="OK",
            on_click=self._on_ok_click,
        )
        self.btn_cancel = ButtonBase(
            create_simple_options(80, 30),
            label="Cancel",
            on_click=self._on_cancel_click,
        )

        self.font_title = font_manager.get_font("Arial", 18, FontWeight.BOLD)

    def _on_radio_change(self, idx: int) -> None:
        self.selected_type = "tile" if idx == 0 else "object"

    def _on_ok_click(self) -> None:
        if self.on_confirm and self.selected_type:
            self.on_confirm(self.selected_type)
        self.hide()

    def _on_cancel_click(self) -> None:
        if self.on_cancel:
            self.on_cancel()
        self.hide()

    def show(self, on_confirm: Callable[[str], None], on_cancel: Callable[[], None]):
        """Show the dialog."""
        self.active = True
        self.selected_type = "tile"
        self.radio_group.set_selected(0)
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

    def hide(self):
        """Hide the dialog."""
        self.active = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False

        if event.type == pygame.KEYDOWN:
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

        # Pass to radio group
        self.radio_group.handle_event(event)

        # Button events
        mouse_pos = pygame.mouse.get_pos()
        btn_ok_rect = Rect(self.rect.x + 100, self.rect.y + 160, 80, 30)
        btn_cancel_rect = Rect(self.rect.x + 220, self.rect.y + 160, 80, 30)

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if btn_ok_rect.collidepoint(mouse_pos):
                self._on_ok_click()
                return True
            if btn_cancel_rect.collidepoint(mouse_pos):
                self._on_cancel_click()
                return True

        return False

    def draw(self, surface: Surface):
        if not self.active:
            return

        # Background
        pygame.draw.rect(surface, self.bg_color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 2)

        # Title
        title = self.font_title.render("Tileset Type", True, self.text_color)
        surface.blit(title, (self.rect.x + 20, self.rect.y + 15))

        # Draw radio group at position
        self.radio_group.rect = Rect(self.rect.x, self.rect.y, 400, 220)
        self.radio_group.draw(surface)

        # Buttons
        self.btn_ok.rect = Rect(self.rect.x + 100, self.rect.y + 160, 80, 30)
        self.btn_ok.render(surface, (0, 0))

        self.btn_cancel.rect = Rect(self.rect.x + 220, self.rect.y + 160, 80, 30)
        self.btn_cancel.render(surface, (0, 0))
