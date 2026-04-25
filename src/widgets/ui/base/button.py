"""
Buttons Base

Base classes for button components.
"""
from typing import Callable, Optional

import pygame
from pygame import Rect, Surface

from ..theme import COLORS, SHAPE
from .uibase import UIBase, UIOptions


class ButtonBase(UIBase):
    """
    Base class for buttons.
    
    Provides:
    - click handling
    - hover state
    - disabled state
    - label rendering
    
    Usage:
        class MyButton(ButtonBase):
            def __init__(self, rect: Rect, label: str, on_click: Callable):
                opts = create_simple_options(rect.width, rect.height)
                super().__init__(opts)
                self.label = label
                self.on_click = on_click
    """
    
    def __init__(
        self,
        options: UIOptions,
        label: str = "",
        on_click: Optional[Callable[[], None]] = None,
    ):
        super().__init__(options)
        
        self.label = label
        self.on_click = on_click
        
        self.is_hovered = False
        self.is_pressed = False
        self.is_disabled = False
        
        # Colors from theme
        self.colors["normal"] = COLORS.accent
        self.colors["hover"] = COLORS.accent_hover
        self.colors["pressed"] = COLORS.accent_active
        self.colors["disabled"] = COLORS.panel_alt
        self.colors["text"] = COLORS.text
        self.colors["text_disabled"] = COLORS.text_muted
    
    def set_enabled(self, enabled: bool) -> None:
        self.is_disabled = not enabled
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        if self.is_disabled:
            return False
        
        pos = event.pos if hasattr(event, 'pos') else pygame.mouse.get_pos()
        
        if not self.rect.collidepoint(pos):
            self.is_hovered = False
            self.is_pressed = False
            return False
        
        self.is_hovered = True
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.is_pressed = True
            return True
        
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_pressed and self.on_click:
                self.on_click()
            self.is_pressed = False
            return True
        
        if event.type == pygame.MOUSEMOTION:
            self.is_pressed = pygame.mouse.get_pressed()[0]
            return True
        
        return False
    
    def draw(self, surface: Surface) -> None:
        if self.local_surface is None:
            return
        
        self.draw_base()
        
        # Determine background color
        if self.is_disabled:
            bg_color = self.colors["disabled"]
        elif self.is_pressed:
            bg_color = self.colors["pressed"]
        elif self.is_hovered:
            bg_color = self.colors["hover"]
        else:
            bg_color = self.colors["normal"]
        
        # Draw button background
        pygame.draw.rect(
            self.local_surface,
            bg_color,
            (
                self.box_model["left"],
                self.box_model["top"],
                self.box_model["content_width"],
                self.box_model["content_height"],
            ),
            border_radius=SHAPE.radius_sm,
        )
        
        # Draw label
        if self.label:
            text_color = (
                self.colors["text_disabled"]
                if self.is_disabled
                else self.colors["text"]
            )
            from utils.font_manager import font_manager, FontWeight
            font = font_manager.get_font("Arial", 14, FontWeight.REGULAR)
            text_surf = font.render(self.label, True, text_color)
            
            text_x = self.box_model["left"] + (
                self.box_model["content_width"] - text_surf.get_width()
            ) // 2
            text_y = self.box_model["top"] + (
                self.box_model["content_height"] - text_surf.get_height()
            ) // 2
            
            self.local_surface.blit(text_surf, (text_x, text_y))
        
        super().render(surface)


class IconButton(ButtonBase):
    """Button with icon instead of text label."""
    
    def __init__(
        self,
        options: UIOptions,
        icon_name: str = "",
        on_click: Optional[Callable[[], None]] = None,
    ):
        super().__init__(options, "", on_click)
        
        self.icon_name = icon_name
    
    def draw(self, surface: Surface) -> None:
        if self.local_surface is None:
            return
        
        self.draw_base()
        
        # Draw icon
        if self.icon_name:
            from utils.icon_manager import icon_manager
            
            if self.is_disabled:
                icon_color = COLORS.text_muted
            elif self.is_pressed:
                icon_color = COLORS.text
            elif self.is_hovered:
                icon_color = COLORS.text
            else:
                icon_color = COLORS.text
            
            icon_size = min(
                self.box_model["content_width"],
                self.box_model["content_height"],
            ) - 8
            
            icon = icon_manager.get_icon(self.icon_name, icon_size, icon_color)
            
            if icon:
                icon_x = self.box_model["left"] + (
                    self.box_model["content_width"] - icon.get_width()
                ) // 2
                icon_y = self.box_model["top"] + (
                    self.box_model["content_height"] - icon.get_height()
                ) // 2
                
                self.local_surface.blit(icon, (icon_x, icon_y))
        
        super().render(surface)


class ToggleButton(ButtonBase):
    """Button that toggles between on/off states."""
    
    def __init__(
        self,
        options: UIOptions,
        label: str = "",
        on_click: Optional[Callable[[], None]] = None,
    ):
        super().__init__(options, label, on_click)
        
        self.is_toggled = False
    
    def set_toggled(self, toggled: bool) -> None:
        self.is_toggled = toggled
    
    def draw(self, surface: Surface) -> None:
        if self.local_surface is None:
            return
        
        self.draw_base()
        
        # Toggle shows accent color when on
        if self.is_toggled:
            bg_color = self.colors["normal"]
        elif self.is_disabled:
            bg_color = self.colors["disabled"]
        elif self.is_pressed:
            bg_color = self.colors["pressed"]
        elif self.is_hovered:
            bg_color = self.colors["hover"]
        else:
            bg_color = COLORS.panel_alt
        
        pygame.draw.rect(
            self.local_surface,
            bg_color,
            (
                self.box_model["left"],
                self.box_model["top"],
                self.box_model["content_width"],
                self.box_model["content_height"],
            ),
            border_radius=SHAPE.radius_sm,
        )
        
        # Draw label if present
        if self.label:
            text_color = (
                self.colors["text_disabled"]
                if self.is_disabled
                else self.colors["text"]
            )
            from utils.font_manager import font_manager, FontWeight
            font = font_manager.get_font("Arial", 14, FontWeight.REGULAR)
            text_surf = font.render(self.label, True, text_color)
            
            text_x = self.box_model["left"] + (
                self.box_model["content_width"] - text_surf.get_width()
            ) // 2
            text_y = self.box_model["top"] + (
                self.box_model["content_height"] - text_surf.get_height()
            ) // 2
            
            self.local_surface.blit(text_surf, (text_x, text_y))
        
        super().render(surface)