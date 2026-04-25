"""
Usage Examples for UI Base Architecture

Examples demonstrating how to use UIBase and related patterns.
"""
from typing import List, Optional
from dataclasses import dataclass

import pygame
from pygame import Surface, Rect

# Import the core components
from uibase_core import UIOptions, BoxModelResult, TPosType
from uibase import UIBase, create_simple_rect, create_options


# ============================================================================
# Example 1: ProgressBar - Simple Animated Widget
# ============================================================================

# Default options for ProgressBar
PROGRESSBAR_DEFAULTS = {
    "width": 250,
    "height": 24,
    "border_width": 2,
    "border_radius": 6,
    "padding_x": 2,
    "padding_y": 2,
    "margin_x": 0,
    "margin_y": 0,
    "border_color": (40, 44, 52, 255),
    "background": (33, 37, 43, 255),
    "fill_color": (255, 255, 255, 255),
}


class SimpleInterpolation:
    """Simple value interpolation with easing."""
    
    def __init__(self, speed: float = 0.1):
        self.speed = speed
        self.target = 0.0
        self.current = 0.0
    
    def set(self, value: float) -> None:
        self.target = max(0.0, min(1.0, value))
    
    def update(self) -> None:
        diff = self.target - self.current
        if abs(diff) > 0.001:
            self.current += diff * self.speed
        else:
            self.current = self.target


class ProgressBarUI(UIBase):
    """
    A simple progress bar widget.
    
    Usage:
        bar = ProgressBarUI()
        bar.set_progress(0.5)  # 50%
        
        while running:
            bar.update()
            bar.render(screen, (100, 100))
    """
    
    def __init__(self, **overrides):
        options = {**PROGRESSBAR_DEFAULTS, **overrides}
        super().__init__(options)
        
        # Extract fill color
        self.colors["fill"] = options.get("fill_color", (255, 255, 255, 255))
        
        # Interpolation for smooth animation
        self.interpolation = SimpleInterpolation(speed=0.05)
    
    def set_progress(self, value: float) -> None:
        """Set progress value (0.0 to 1.0)."""
        self.interpolation.set(value)
    
    def get_progress(self) -> float:
        """Get current progress value."""
        return self.interpolation.current
    
    def update(self) -> None:
        """Update interpolation. Call each frame."""
        self.interpolation.update()
    
    def render(self, screen: Surface, pos_offset: TPosType = (0, 0)) -> None:
        self.draw_base()
        
        # Draw fill
        intrp_current = self.interpolation.current
        if intrp_current > 0:
            fill_width = int(self.box_model["content_width"] * intrp_current)
            inner_radius = max(0, self.border["radius"] - self.border["width"])
            
            pygame.draw.rect(
                self.local_surface,
                self.colors["fill"],
                (
                    self.box_model["left"],
                    self.box_model["top"],
                    fill_width,
                    self.box_model["content_height"],
                ),
                border_radius=inner_radius,
            )
        
        super().render(screen, pos_offset)


# ============================================================================
# Example 2: Dropdown / Selection Menu
# ============================================================================

# Default options for Dropdown
DROPDOWN_DEFAULTS = {
    "width": 200,
    "height": 28,
    "border_width": 1,
    "border_radius": 4,
    "margin_x": 0,
    "margin_y": 0,
    "border_color": (60, 60, 60),
    "background": (35, 38, 44),
    "item_height": 28,
}


@dataclass
class DropdownItem:
    """An item in a dropdown."""
    label: str
    value: str = ""
    icon: Optional[Surface] = None


class DropdownUI(UIBase):
    """
    A dropdown/selection menu.
    
    Based on patterns found in:
    - animation_editor.py dropdown (animation selection)
    - menubar.py (menu items)
    - fileinput.py (autocomplete)
    
    Usage:
        dropdown = DropdownUI(items=[
            DropdownItem("Option 1", "opt1"),
            DropdownItem("Option 2", "opt2"),
        ])
        
        while running:
            dropdown.handle_event(event)
            dropdown.draw(screen)
    """
    
    def __init__(self, items: Optional[List[DropdownItem]] = None, **overrides):
        options = {**DROPDOWN_DEFAULTS, **overrides}
        super().__init__(options)
        
        self.items = items or []
        self.selected_index = 0
        self.is_open = False
        self.hover_index = -1
        
        # Colors
        self.colors["hover"] = (60, 70, 90)
        self.colors["text"] = (220, 220, 220)
        self.colors["text_muted"] = (140, 140, 140)
    
    def set_items(self, items: List[DropdownItem]) -> None:
        """Set dropdown items."""
        self.items = items
        self.selected_index = 0
    
    def get_selected(self) -> Optional[DropdownItem]:
        """Get currently selected item."""
        if 0 <= self.selected_index < len(self.items):
            return self.items[self.selected_index]
        return None
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle mouse/keyboard events. Returns True if handled."""
        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos
            
            # Main button click - toggle open
            if self.rect.collidepoint(pos):
                self.is_open = not self.is_open
                return True
            
            # If open, check item clicks
            if self.is_open:
                for i in range(len(self.items)):
                    item_rect = self._get_item_rect(i)
                    if item_rect.collidepoint(pos):
                        self.selected_index = i
                        self.is_open = False
                        return True
                
                # Click outside closes dropdown
                self.is_open = False
                return True
        
        if self.is_open and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.is_open = False
                return True
            elif event.key == pygame.K_DOWN:
                self.selected_index = min(len(self.items) - 1, self.selected_index + 1)
                return True
            elif event.key == pygame.K_UP:
                self.selected_index = max(0, self.selected_index - 1)
                return True
            elif event.key == pygame.K_RETURN:
                self.is_open = False
                return True
        
        return False
    
    def _get_item_rect(self, index: int) -> Rect:
        """Get rect for an item at index."""
        item_h = self.box_model["content_height"]
        y = self.box_model["top"] + index * item_h
        return Rect(
            self.box_model["left"],
            y,
            self.box_model["content_width"],
            item_h,
        )
    
    @property
    def rect(self) -> Rect:
        """Get the main dropdown rect."""
        return Rect(
            self.box_model["offset_x"],
            self.box_model["offset_y"],
            self.box_model["full_width"],
            self.box_model["full_height"],
        )
    
    def update(self) -> None:
        """Update hover state."""
        if self.is_open:
            mouse_pos = pygame.mouse.get_pos()
            
            # Check hover for each item
            for i in range(len(self.items)):
                if self._get_item_rect(i).collidepoint(mouse_pos):
                    self.hover_index = i
                    break
            else:
                self.hover_index = -1
    
    def draw(self, screen: Surface) -> None:
        self.draw_base()
        
        # Draw selected item text
        if self.items:
            selected = self.items[self.selected_index]
            text_surf = pygame.font.SysFont("Arial", 14).render(
                selected.label, True, self.colors["text"]
            )
            text_pos = (
                self.box_model["left"] + 8,
                self.box_model["top"] + (self.box_model["content_height"] - text_surf.get_height()) // 2,
            )
            screen.blit(text_surf, text_pos)
        
        # Draw toggle indicator
        indicator = "▼" if self.is_open else "▶"
        ind_surf = pygame.font.SysFont("Arial", 10).render(indicator, True, self.colors["text_muted"])
        screen.blit(ind_surf, (
            self.box_model["left"] + self.box_model["content_width"] - 20,
            self.box_model["top"] + (self.box_model["content_height"] - ind_surf.get_height()) // 2,
        ))
        
        # Draw dropdown items if open
        if self.is_open:
            items_y = self.box_model["top"] + self.box_model["content_height"]
            
            for i, item in enumerate(self.items):
                item_rect = Rect(
                    self.box_model["left"],
                    items_y + i * self.box_model["content_height"],
                    self.box_model["content_width"],
                    self.box_model["content_height"],
                )
                
                # Item background
                is_hover = (i == self.hover_index)
                is_selected = (i == self.selected_index)
                
                bg_color = self.colors["hover"] if is_hover else self.colors["bg"]
                pygame.draw.rect(screen, bg_color, item_rect)
                
                # Item text
                text_color = self.colors["text"]
                if is_selected:
                    text_color = self.colors.get("fill", (255, 255, 255))
                
                text_surf = pygame.font.SysFont("Arial", 14).render(
                    item.label, True, text_color
                )
                screen.blit(text_surf, (item_rect.x + 8, item_rect.y + (item_rect.height - text_surf.get_height()) // 2))
            
            # Border for dropdown
            total_h = len(self.items) * self.box_model["content_height"]
            dropdown_rect = Rect(
                self.box_model["left"],
                items_y,
                self.box_model["content_width"],
                total_h,
            )
            pygame.draw.rect(screen, self.border["color"], dropdown_rect, self.border["width"])
        
        super().render(screen)


# ============================================================================
# Example 3: Usage Demonstration
# ============================================================================

def demo():
    """Demo showing usage patterns."""
    # Create components
    progress_bar = ProgressBarUI(width=300, height=30, fill_color=(100, 200, 100))
    dropdown = DropdownUI(items=[
        DropdownItem("Animation 1", "anim1"),
        DropdownItem("Animation 2", "anim2"),
        DropdownItem("Animation 3", "anim3"),
    ])
    
    # Set values
    progress_bar.set_progress(0.0)
    
    # Update loop
    progress_bar.update()
    dropdown.update()
    
    # Event handling
    for event in pygame.event.get():
        dropdown.handle_event(event)
    
    # Rendering
    screen = pygame.display.set_mode((800, 600))
    
    progress_bar.render(screen, (50, 50))
    dropdown.draw(screen)


if __name__ == "__main__":
    demo()