"""
Toggleable overlay sidebar for collision layer/mask selection.

Wraps CollisionLayerMaskWidget with:
- Slide-in from right overlay
- Toggle button (gear icon)
- Close button (X)
- Semi-transparent dim background
- Zero render cost when closed
"""

from __future__ import annotations

from typing import Callable, Optional

import pygame
from pygame import Rect, Surface

from widgets.ui.theme import COLORS, FONTS, SHAPE
from widgets.ui.collision_layer_mask import CollisionLayerMaskWidget
from utils.font_manager import font_manager, FontWeight


class CollisionLayerSidebar:
    """
    Toggleable overlay sidebar containing the collision layer/mask widget.

    When closed: zero rendering, zero event processing.
    When open: slides in from the right with a dimmed background overlay.
    """

    def __init__(
        self,
        parent_rect: Rect,
        max_layers: int = 16,
        initial_layer: int = 1,
        initial_mask: int = 0xFFFF,
        on_changed: Optional[Callable[[int, int], None]] = None,
    ):
        self._parent_rect = parent_rect
        self._visible = False
        self._close_rect = Rect(0, 0, 28, 28)
        self._max_layers = max_layers

        self._sidebar_width = CollisionLayerMaskWidget.calc_min_width(max_layers)

        self.widget = CollisionLayerMaskWidget(
            Rect(0, 0, self._sidebar_width, 100),
            max_layers=max_layers,
            initial_layer=initial_layer,
            initial_mask=initial_mask,
            on_changed=on_changed,
        )

        self._toggle_rect = Rect(0, 0, 32, 32)
        self._toggle_hover = False
        self._close_hover = False

        self._rebuild_layout()

    @property
    def visible(self) -> bool:
        return self._visible

    def toggle(self) -> None:
        self._visible = not self._visible

    def open(self) -> None:
        self._visible = True
        self._rebuild_widget_layout()

    def close(self) -> None:
        self._visible = False

    def get_layer(self) -> int:
        return self.widget.get_layer()

    def get_mask(self) -> int:
        return self.widget.get_mask()

    def set_layer(self, value: int) -> None:
        self.widget.set_layer(value)

    def set_mask(self, value: int) -> None:
        self.widget.set_mask(value)

    def resize(self, parent_rect: Rect) -> None:
        self._parent_rect = parent_rect
        self._rebuild_layout()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self._visible:
            return False

        pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._close_rect.collidepoint(pos):
                self._visible = False
                return True

            sidebar_rect = self._sidebar_rect()
            if not sidebar_rect.collidepoint(pos):
                self._visible = False
                return True

        if self.widget.handle_event(event):
            return True

        return False

    def draw(self, screen: Surface) -> None:
        if not self._visible:
            return

        sidebar_rect = self._sidebar_rect()

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        screen.blit(overlay, (0, 0))

        draw_panel(screen, sidebar_rect, COLORS.panel, COLORS.border, radius=0)

        header_rect = Rect(sidebar_rect.x, sidebar_rect.y, sidebar_rect.w, 36)
        draw_panel(screen, header_rect, COLORS.header, COLORS.border_soft, radius=0)

        font = font_manager.get_font(FONTS.name, FONTS.size_md, FontWeight.BOLD)
        title = font.render("Collision Layers", True, COLORS.text)
        screen.blit(
            title, (header_rect.x + 10, header_rect.centery - title.get_height() // 2)
        )

        self._close_rect = Rect(header_rect.right - 34, header_rect.y + 4, 28, 28)
        close_bg = COLORS.danger if self._close_hover else COLORS.panel_alt
        pygame.draw.rect(
            screen, close_bg, self._close_rect, border_radius=SHAPE.radius_sm
        )
        pygame.draw.rect(
            screen,
            COLORS.border_soft,
            self._close_rect,
            1,
            border_radius=SHAPE.radius_sm,
        )

        close_font = font_manager.get_font(
            FONTS.name, FONTS.size_md, FontWeight.REGULAR
        )
        close_text = close_font.render("✕", True, COLORS.text)
        screen.blit(close_text, close_text.get_rect(center=self._close_rect.center))

        self._rebuild_widget_layout()
        self.widget.draw(screen)

    def draw_toggle_button(self, screen: Surface) -> None:
        """Draw the toggle button — always visible, even when sidebar is closed."""
        mouse = pygame.mouse.get_pos()
        self._toggle_hover = self._toggle_rect.collidepoint(mouse)

        bg = COLORS.accent if self._toggle_hover else COLORS.panel_alt
        pygame.draw.rect(screen, bg, self._toggle_rect, border_radius=SHAPE.radius_sm)
        pygame.draw.rect(
            screen,
            COLORS.border_soft,
            self._toggle_rect,
            1,
            border_radius=SHAPE.radius_sm,
        )

        font = font_manager.get_font(FONTS.name, FONTS.size_md, FontWeight.REGULAR)
        icon = font.render("⚙", True, COLORS.text)
        screen.blit(icon, icon.get_rect(center=self._toggle_rect.center))

    def handle_toggle_event(self, event: pygame.event.Event) -> bool:
        """Handle events for the toggle button only."""
        pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._toggle_rect.collidepoint(pos):
                self._visible = not self._visible
                return True
        return False

    def _rebuild_layout(self) -> None:
        self._toggle_rect = Rect(
            self._parent_rect.right - self._sidebar_width - 42,
            self._parent_rect.y + 6,
            32,
            32,
        )

    def _rebuild_widget_layout(self) -> None:
        sidebar_rect = self._sidebar_rect()
        widget_rect = Rect(
            sidebar_rect.x + 8,
            sidebar_rect.y + 44,
            sidebar_rect.w - 16,
            sidebar_rect.h - 52,
        )
        self.widget.resize(widget_rect)

    def _sidebar_rect(self) -> Rect:
        return Rect(
            self._parent_rect.right - self._sidebar_width,
            self._parent_rect.y,
            self._sidebar_width,
            self._parent_rect.h,
        )


def draw_panel(surface: Surface, rect: Rect, bg=None, border=None, radius=None) -> None:
    bg = bg if bg is not None else COLORS.panel
    border = border if border is not None else COLORS.border
    radius = SHAPE.radius if radius is None else radius
    pygame.draw.rect(surface, bg, rect, border_radius=radius)
    if border is not None:
        pygame.draw.rect(surface, border, rect, 1, border_radius=radius)
