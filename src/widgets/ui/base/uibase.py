"""
UIBase - Foundation Class for UI Components

Provides core infrastructure for UI widgets with:
- box_model: Computed layout (margin, border, padding, content)
- local_surface: Off-screen render surface
- colors: Extracted from theme
- border: Border configuration
- add_plugin(): Extend rendering
- draw_base(): Render background/border
- render(): Draw to screen
"""
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import pygame
from pygame import Rect, Surface, SRCALPHA

from ..theme import COLORS


# Position type
TPosType = Tuple[int, int]


class UIOptions:
    """Declarative UI configuration."""
    
    def __init__(
        self,
        width: int = 0,
        height: int = 0,
        background: Tuple[int, int, int, int] = (0, 0, 0, 0),
        border_color: Tuple[int, int, int, int] = (0, 0, 0, 0),
        border_width: int = 0,
        border_radius: int = 0,
        padding_x: int = 0,
        padding_y: int = 0,
        margin_x: int = 0,
        margin_y: int = 0,
    ):
        self.width = width
        self.height = height
        self.background = background
        self.border_color = border_color
        self.border_width = border_width
        self.border_radius = border_radius
        self.padding_x = padding_x
        self.padding_y = padding_y
        self.margin_x = margin_x
        self.margin_y = margin_y
    
    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def _generate_box_model(
    width: int,
    height: int,
    padding_x: int = 0,
    padding_y: int = 0,
    border_width: int = 0,
    margin_x: int = 0,
    margin_y: int = 0,
) -> Dict[str, int]:
    """Compute box model layout values."""
    inner_x = 2 * (padding_x + border_width)
    inner_y = 2 * (padding_y + border_width)
    
    return {
        "left": padding_x + border_width,
        "top": padding_y + border_width,
        "offset_x": margin_x,
        "offset_y": margin_y,
        "full_width": width,
        "full_height": height,
        "content_width": width - inner_x,
        "content_height": height - inner_y,
    }


class UIBase:
    """
    Base class for UI components.
    
    Usage:
        class MyWidget(UIBase):
            def __init__(self, options: UIOptions):
                super().__init__(options)
                self.add_plugin(self.draw_content)
            
            def draw_content(self, surface):
                # Custom rendering
                pass
    """
    
    def __init__(self, options: Optional[UIOptions] = None) -> None:
        if options is None:
            options = UIOptions()
        
        self._options = options
        
        # Extract colors
        self.colors: Dict[str, Tuple] = {
            "bg": options.background,
        }
        
        # Compute box model
        model = _generate_box_model(
            options.width,
            options.height,
            options.padding_x,
            options.padding_y,
            options.border_width,
            options.margin_x,
            options.margin_y,
        )
        self.box_model = model
        
        # Store border config
        self.border: Dict[str, Any] = {
            "radius": options.border_radius,
            "width": options.border_width,
            "color": options.border_color,
        }
        
        # Create off-screen surface
        local_size = model["full_width"], model["full_height"]
        if local_size[0] > 0 and local_size[1] > 0:
            self.local_surface = Surface(local_size, SRCALPHA)
        else:
            self.local_surface = None
        
        # Plugins for extensibility
        self.renderable_plugins: List[Callable[[Surface], Any]] = []
    
    def add_plugin(self, cb: Callable[[Surface], Any]) -> None:
        """Add a rendering plugin function."""
        self.renderable_plugins.append(cb)
    
    def draw_base(self) -> None:
        """Render background and border to local_surface."""
        if self.local_surface is None:
            return
        
        local_surf = self.local_surface
        local_surf.fill((0, 0, 0, 0))  # Clear
        
        bg_color = self.colors.get("bg", (0, 0, 0, 0))
        border_width = self.border.get("width", 0)
        border_radius = self.border.get("radius", 0)
        border_color = self.border.get("color", (0, 0, 0, 0))
        
        content_pos = self.box_model["left"], self.box_model["top"]
        content_size = self.box_model["content_width"], self.box_model["content_height"]
        surface_size = local_surf.get_size()
        
        # Draw border
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
    def fullsize(self) -> Tuple[int, int]:
        """Return full (width, height) of component."""
        return (self.box_model["full_width"], self.box_model["full_height"])
    
    @property
    def rect(self) -> Rect:
        """Return component rect for collision detection."""
        return Rect(
            self.box_model["offset_x"],
            self.box_model["offset_y"],
            self.box_model["full_width"],
            self.box_model["full_height"],
        )
    
    @rect.setter
    def rect(self, value: Rect) -> None:
        """Set rect position."""
        self.box_model["offset_x"] = value.x
        self.box_model["offset_y"] = value.y
    
    def render(self, screen: Surface, pos_offset: TPosType = (0, 0)) -> None:
        """
        Render component to screen.
        
        Args:
            screen: Target surface
            pos_offset: (x, y) offset for positioning
        """
        if self.local_surface is None:
            return
        
        self.draw_base()
        
        # Run plugins
        for plugin in self.renderable_plugins:
            plugin(self.local_surface)
        
        # Blit to screen
        pos_x = self.box_model["offset_x"] + pos_offset[0]
        pos_y = self.box_model["offset_y"] + pos_offset[1]
        screen.blit(self.local_surface, (pos_x, pos_y))


# Convenience functions

def create_options(**kwargs) -> UIOptions:
    """Create UIOptions from keyword arguments."""
    return UIOptions(**kwargs)


def create_simple_options(
    width: int,
    height: int,
    bg_color: Tuple[int, int, int] = (35, 38, 44),
    border_color: Tuple[int, int, int] = (60, 62, 65),
    border_width: int = 1,
    border_radius: int = 4,
    margin_x: int = 0,
    margin_y: int = 0,
) -> UIOptions:
    """Create simple rectangular options."""
    return UIOptions(
        width=width,
        height=height,
        background=(*bg_color, 255),
        border_color=(*border_color, 255),
        border_width=border_width,
        border_radius=border_radius,
        margin_x=margin_x,
        margin_y=margin_y,
    )