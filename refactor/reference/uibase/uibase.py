"""
UIBase - Foundation Class for UI Components

Based on patterns from refactor reference.
Provides common infrastructure for renderable UI widgets.
"""
from typing import Any, Callable, List, Tuple

import pygame
from pygame import Rect, Surface, SRCALPHA

from uibase_core import UIOptions, generate_box_model


class UIBase:
    """
    Base class for UI components.
    
    Provides:
    - box_model: Computed layout (padding, margin, border, content)
    - local_surface: Off-screen render surface
    - colors: Extracted color values
    - border: Border configuration
    - add_plugin(): Extend rendering
    
    Usage:
        class MyWidget(UIBase):
            def __init__(self, options: UIOptions):
                super().__init__(options)
                self.add_plugin(self.draw_content)
            
            def draw_content(self, surface):
                # Custom rendering
                pass
    """
    
    def __init__(self, options: UIOptions) -> None:
        # Extract and store colors
        self.colors = {
            "bg": options.get("background", (0, 0, 0, 0)),
        }
        
        # Compute box model
        width = options.get("width", 0)
        height = options.get("height", 0)
        
        box_input = {
            "width": width,
            "height": height,
            "padding_x": options.get("padding_x", 0),
            "padding_y": options.get("padding_y", 0),
            "border_width": options.get("border_width", 0),
            "margin_x": options.get("margin_x", 0),
            "margin_y": options.get("margin_y", 0),
        }
        self.box_model = generate_box_model(box_input)
        
        # Store border configuration
        self.border = {
            "radius": options.get("border_radius", 0),
            "width": options.get("border_width", 0),
            "color": options.get("border_color", (0, 0, 0, 0)),
        }
        
        # Create off-screen surface for compositing
        local_size = self.box_model["full_width"], self.box_model["full_height"]
        self.local_surface = Surface(local_size, SRCALPHA)
        
        # Plugin list for extensibility
        self.renderable_plugins: List[Callable[[Surface], Any]] = []
    
    def add_plugin(self, cb: Callable[[Surface], Any]) -> None:
        """Add a rendering plugin function."""
        self.renderable_plugins.append(cb)
    
    def draw_base(self) -> None:
        """
        Draw background and border to local_surface.
        
        Called before plugins render content.
        """
        local_surf = self.local_surface
        local_surf.fill((0, 0, 0, 0))  # Clear
        
        bg_color = self.colors.get("bg", (0, 0, 0, 0))
        border_width = self.border.get("width", 0)
        border_radius = self.border.get("radius", 0)
        border_color = self.border.get("color", (0, 0, 0, 0))
        
        content_pos = self.box_model["left"], self.box_model["top"]
        content_size = self.box_model["content_width"], self.box_model["content_height"]
        surface_size = local_surf.get_size()
        
        # Draw border if present
        if border_width > 0:
            pygame.draw.rect(
                local_surf,
                border_color,
                (0, 0, *surface_size),
                width=border_width,
                border_radius=border_radius,
            )
        
        # Draw background
        pygame.draw.rect(
            local_surf,
            bg_color,
            (*content_pos, *content_size),
            border_radius=max(0, border_radius - border_width),
        )
    
    @property
    def fullsize(self) -> tuple[int, int]:
        """Return full (width, height) of the component."""
        return (self.box_model["full_width"], self.box_model["full_height"])
    
    def render(self, screen: Surface, pos_offset: Tuple[int, int] = (0, 0)) -> None:
        """
        Render the component to screen.
        
        Args:
            screen: The surface to render to
            pos_offset: (x, y) offset for positioning
        """
        self.draw_base()
        
        # Run all plugins
        for plugin in self.renderable_plugins:
            plugin(self.local_surface)
        
        # Blit to screen at computed position
        pos_x = self.box_model["offset_x"] + pos_offset[0]
        pos_y = self.box_model["offset_y"] + pos_offset[1]
        screen.blit(self.local_surface, (pos_x, pos_y))


# Convenience functions

def create_options(**kwargs) -> UIOptions:
    """Helper to create UIOptions from keyword arguments."""
    return UIOptions(kwargs)


def create_simple_rect(
    width: int,
    height: int,
    bg_color: tuple = (30, 30, 30),
    border_color: tuple = (60, 60, 60),
    border_width: int = 1,
    border_radius: int = 4,
) -> UIOptions:
    """Create simple rectangular UIOptions."""
    return {
        "width": width,
        "height": height,
        "background": bg_color,
        "border_color": border_color,
        "border_width": border_width,
        "border_radius": border_radius,
    }