"""
Mode Indicator — Reusable component for showing and switching between workflow modes.

Features:
- Two or more mode states
- Visual indication of active mode
- Click to switch (with optional validation)
- Color-coded states
"""

from __future__ import annotations

from typing import List, Tuple, Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum, auto

import pygame
from pygame import Rect, Surface

from widgets.ui.theme import COLORS, SHAPE
from utils.font_manager import font_manager, FontWeight


@dataclass
class Mode:
    """A workflow mode with ID, label, and optional icon"""
    id: str
    label: str
    description: str = ""
    icon: Optional[Surface] = None
    can_enter: Optional[Callable[[], bool]] = None
    on_enter: Optional[Callable[[], None]] = None


class ModeIndicator:
    """
    Mode indicator/switcher component.
    
    Shows available modes as clickable buttons/tabs,
    with visual indication of which mode is active.
    """
    
    def __init__(
        self,
        rect: Rect,
        modes: Optional[List[Mode]] = None,
        active_mode: str = "",
    ):
        self.rect = rect
        self.modes: List[Mode] = modes or []
        self.active_mode_id = active_mode
        
        # Visual settings
        self.button_padding = 12
        self.button_spacing = 4
        self.button_height = 28
        
        # Font
        self._font = font_manager.get_font("Arial", 12, FontWeight.REGULAR)
        self._font_sm = font_manager.get_font("Arial", 10, FontWeight.REGULAR)
        
        # Callbacks
        self.on_mode_changed: Optional[Callable[[str, str], None]] = None  # (old, new)
        self.on_mode_change_rejected: Optional[Callable[[str, str], None]] = None  # (from, to)
    
    def add_mode(self, mode: Mode) -> None:
        """Add a mode"""
        self.modes.append(mode)
    
    def remove_mode(self, mode_id: str) -> bool:
        """Remove a mode by ID"""
        for i, mode in enumerate(self.modes):
            if mode.id == mode_id:
                self.modes.pop(i)
                if self.active_mode_id == mode_id:
                    self.active_mode_id = self.modes[0].id if self.modes else ""
                return True
        return False
    
    def set_active(self, mode_id: str, force: bool = False) -> bool:
        """
        Set active mode.
        Returns True if mode was changed.
        """
        if mode_id == self.active_mode_id:
            return False
        
        # Find mode
        new_mode = None
        for mode in self.modes:
            if mode.id == mode_id:
                new_mode = mode
                break
        
        if not new_mode:
            return False
        
        # Check if we can enter this mode
        if not force and new_mode.can_enter:
            if not new_mode.can_enter():
                if self.on_mode_change_rejected:
                    self.on_mode_change_rejected(self.active_mode_id, mode_id)
                return False
        
        old_mode_id = self.active_mode_id
        self.active_mode_id = mode_id
        
        # Trigger callback
        if new_mode.on_enter:
            new_mode.on_enter()
        
        if self.on_mode_changed:
            self.on_mode_changed(old_mode_id, mode_id)
        
        return True
    
    def get_active_mode(self) -> Optional[Mode]:
        """Get currently active mode"""
        for mode in self.modes:
            if mode.id == self.active_mode_id:
                return mode
        return None
    
    def get_mode(self, mode_id: str) -> Optional[Mode]:
        """Get mode by ID"""
        for mode in self.modes:
            if mode.id == mode_id:
                return mode
        return None
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle input events.
        Returns True if event was handled.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse = pygame.mouse.get_pos()
            if self.rect.collidepoint(mouse):
                # Check which mode button was clicked
                button_rects = self._get_button_rects()
                for mode, button_rect in button_rects:
                    if button_rect.collidepoint(mouse):
                        self.set_active(mode.id)
                        return True
        
        return False
    
    def _get_button_rects(self) -> List[Tuple[Mode, Rect]]:
        """Get button rectangles for each mode"""
        if not self.modes:
            return []
        
        # Calculate button widths
        total_width = self.rect.width - 2 * self.button_padding
        spacing = self.button_spacing * (len(self.modes) - 1)
        available_width = total_width - spacing
        button_width = available_width // len(self.modes)
        
        result = []
        x = self.rect.x + self.button_padding
        y = self.rect.centery - self.button_height // 2
        
        for i, mode in enumerate(self.modes):
            # Last button takes remaining space
            if i == len(self.modes) - 1:
                width = self.rect.right - self.button_padding - x
            else:
                width = button_width
            
            rect = Rect(x, y, width, self.button_height)
            result.append((mode, rect))
            x += width + self.button_spacing
        
        return result
    
    def draw(self, screen: Surface) -> None:
        """Draw the mode indicator"""
        # Background
        pygame.draw.rect(screen, COLORS.panel, self.rect)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)
        
        # Draw mode buttons
        button_rects = self._get_button_rects()
        mouse = pygame.mouse.get_pos()
        
        for mode, button_rect in button_rects:
            is_active = mode.id == self.active_mode_id
            is_hovered = button_rect.collidepoint(mouse)
            
            # Background
            if is_active:
                bg_color = COLORS.accent
                text_color = COLORS.text
            elif is_hovered:
                bg_color = COLORS.hover
                text_color = COLORS.text
            else:
                bg_color = COLORS.panel_alt
                text_color = COLORS.text_dim
            
            pygame.draw.rect(
                screen,
                bg_color,
                button_rect,
                border_radius=SHAPE.radius_sm,
            )
            
            # Border for non-active
            if not is_active:
                pygame.draw.rect(
                    screen,
                    COLORS.border_soft,
                    button_rect,
                    1,
                    border_radius=SHAPE.radius_sm,
                )
            
            # Label
            label_surf = self._font.render(mode.label, True, text_color)
            label_x = button_rect.centerx - label_surf.get_width() // 2
            label_y = button_rect.centery - label_surf.get_height() // 2
            screen.blit(label_surf, (label_x, label_y))
        
        # Draw separator line between inactive and active areas
        if len(self.modes) >= 2 and self.active_mode_id:
            for i, (mode, button_rect) in enumerate(button_rects):
                if mode.id == self.active_mode_id and i > 0:
                    prev_rect = button_rects[i - 1][1]
                    sep_x = (prev_rect.right + button_rect.x) // 2
                    pygame.draw.line(
                        screen,
                        COLORS.border,
                        (sep_x, self.rect.y + 4),
                        (sep_x, self.rect.bottom - 4),
                    )
                    break
    
    def resize(self, rect: Rect) -> None:
        """Resize the component"""
        self.rect = rect
    
    def set_modes(self, modes: List[Mode]) -> None:
        """Set all modes at once"""
        self.modes = modes
        if not self.active_mode_id and modes:
            self.active_mode_id = modes[0].id
