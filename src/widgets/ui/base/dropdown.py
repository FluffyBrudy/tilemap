"""
Dropdown Base

Base classes for dropdown/selection components.
"""
from typing import Callable, List, Optional, Any

import pygame
from pygame import Rect, Surface

from ..theme import COLORS, SHAPE
from .uibase import UIBase, UIOptions
from utils.font_manager import font_manager, FontWeight


class DropdownItem:
    """Represents an item in a dropdown."""
    
    def __init__(self, label: str, value: Any = None, icon: Optional[Surface] = None):
        self.label = label
        self.value = value if value is not None else label
        self.icon = icon


class DropdownBase(UIBase):
    """
    Base class for dropdown/selection menus.
    
    Provides:
    - item list management
    - selection state
    - open/close state
    - hover highlighting
    - keyboard navigation
    
    Usage:
        class MyDropdown(DropdownBase):
            def __init__(self, rect: Rect, items: List[DropdownItem]):
                opts = create_simple_options(rect.width, rect.height)
                super().__init__(opts)
                self.set_items(items)
    """
    
    def __init__(
        self,
        options: UIOptions,
        items: Optional[List[DropdownItem]] = None,
        on_select: Optional[Callable[[DropdownItem], None]] = None,
    ):
        super().__init__(options)
        
        self.items = items or []
        self.selected_idx = 0
        self.is_open = False
        self.hover_idx = -1
        self.on_select = on_select
        
        # Font
        self.font = font_manager.get_font("Arial", 14, FontWeight.REGULAR)
        
        # Colors
        self.colors["hover"] = COLORS.hover
        self.colors["text"] = COLORS.text
        self.colors["text_muted"] = COLORS.text_dim
        self.colors["selected"] = COLORS.selected
    
    def set_items(self, items: List[DropdownItem]) -> None:
        self.items = items
        if items and not (0 <= self.selected_idx < len(items)):
            self.selected_idx = 0
    
    def get_selected(self) -> Optional[DropdownItem]:
        if 0 <= self.selected_idx < len(self.items):
            return self.items[self.selected_idx]
        return None
    
    def _get_item_rect(self, index: int) -> Rect:
        item_h = self.box_model["content_height"]
        y = self.box_model["top"] + index * item_h
        return Rect(
            self.box_model["left"],
            y,
            self.box_model["content_width"],
            item_h,
        )
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse_pos = pygame.mouse.get_pos()
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Main button click toggles open
            if self.rect.collidepoint(mouse_pos):
                self.is_open = not self.is_open
                return True
            
            # If open, check item clicks
            if self.is_open:
                for i in range(len(self.items)):
                    if self._get_item_rect(i).collidepoint(mouse_pos):
                        self.selected_idx = i
                        self.is_open = False
                        if self.on_select:
                            self.on_select(self.items[i])
                        return True
                
                # Click outside closes
                self.is_open = False
                return True
        
        if self.is_open and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.is_open = False
                return True
            elif event.key == pygame.K_DOWN:
                self.selected_idx = min(len(self.items) - 1, self.selected_idx + 1)
                return True
            elif event.key == pygame.K_UP:
                self.selected_idx = max(0, self.selected_idx - 1)
                return True
            elif event.key == pygame.K_RETURN:
                self.is_open = False
                if self.on_select and self.items:
                    self.on_select(self.items[self.selected_idx])
                return True
        
        return False
    
    def update(self) -> None:
        """Update hover state. Call each frame."""
        mouse_pos = pygame.mouse.get_pos()
        
        if self.is_open:
            self.hover_idx = -1
            for i in range(len(self.items)):
                if self._get_item_rect(i).collidepoint(mouse_pos):
                    self.hover_idx = i
                    break
        else:
            self.hover_idx = -1
    
    def draw(self, surface: Surface) -> None:
        self.draw_base()
        
        # Draw selected item
        if self.items:
            selected = self.items[self.selected_idx]
            text_color = self.colors["text"]
            text_surf = self.font.render(selected.label, True, text_color)
            
            text_x = self.box_model["left"] + 8
            text_y = self.box_model["top"] + (
                self.box_model["content_height"] - text_surf.get_height()
            ) // 2
            
            self.local_surface.blit(text_surf, (text_x, text_y))
        
        # Draw dropdown arrow
        arrow = "▼" if self.is_open else "▶"
        arrow_surf = self.font.render(arrow, True, self.colors["text_muted"])
        
        arrow_x = self.box_model["left"] + self.box_model["content_width"] - 20
        arrow_y = self.box_model["top"] + (
            self.box_model["content_height"] - arrow_surf.get_height()
        ) // 2
        
        self.local_surface.blit(arrow_surf, (arrow_x, arrow_y))
        
        # Draw dropdown items if open
        if self.is_open and self.items:
            items_y = self.box_model["top"] + self.box_model["content_height"]
            
            for i, item in enumerate(self.items):
                item_rect = Rect(
                    self.box_model["left"],
                    items_y + i * self.box_model["content_height"],
                    self.box_model["content_width"],
                    self.box_model["content_height"],
                )
                
                is_hover = (i == self.hover_idx)
                is_selected = (i == self.selected_idx)
                
                # Item background
                bg_color = self.colors["hover"] if is_hover else COLORS.panel
                pygame.draw.rect(surface, bg_color, item_rect)
                
                # Item border
                pygame.draw.rect(
                    surface,
                    COLORS.border_soft,
                    item_rect,
                    1,
                )
                
                # Item text
                text_color = self.colors["text"]
                if is_selected:
                    text_color = COLORS.accent
                
                text_surf = self.font.render(item.label, True, text_color)
                text_x = item_rect.x + 8
                text_y = item_rect.y + (
                    item_rect.height - text_surf.get_height()
                ) // 2
                
                surface.blit(text_surf, (text_x, text_y))
        
        super().render(surface)


class RadioGroup:
    """Group of radio buttons with mutual exclusion."""
    
    def __init__(
        self,
        options: UIOptions,
        labels: List[str],
        on_change: Optional[Callable[[int], None]] = None,
    ):
        self.options = options
        self.labels = labels
        self.on_change = on_change
        
        self.selected_idx = 0
        
        # Colors
        self.colors = {
            "normal": COLORS.border_soft,
            "selected": COLORS.accent,
            "text": COLORS.text,
        }
        
        # Font
        self.font = font_manager.get_font("Arial", 14, FontWeight.REGULAR)
        
        # Create rects for each option
        y = options.margin_y
        self.radio_rects = []
        for label in labels:
            rect = Rect(
                options.margin_x,
                y,
                20,
                20,
            )
            self.radio_rects.append(rect)
            y += 30
    
    def get_selected(self) -> int:
        return self.selected_idx
    
    def set_selected(self, idx: int) -> None:
        if 0 <= idx < len(self.labels):
            self.selected_idx = idx
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            for i, rect in enumerate(self.radio_rects):
                if rect.collidepoint(pos):
                    self.selected_idx = i
                    if self.on_change:
                        self.on_change(i)
                    return True
        return False
    
    def draw(self, surface: Surface) -> None:
        for i, (rect, label) in enumerate(zip(self.radio_rects, self.labels)):
            is_selected = (i == self.selected_idx)
            
            # Draw radio circle
            center = rect.center
            radius = rect.width // 2
            
            pygame.draw.circle(
                surface,
                self.colors["normal"],
                center,
                radius,
                2,
            )
            
            if is_selected:
                pygame.draw.circle(
                    surface,
                    self.colors["selected"],
                    center,
                    radius - 4,
                )
            
            # Draw label
            label_rect = Rect(rect.right + 10, rect.y, 200, rect.height)
            label_surf = self.font.render(label, True, self.colors["text"])
            surface.blit(label_surf, (label_rect.x, label_rect.y))