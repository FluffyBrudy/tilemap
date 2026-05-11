"""
Status Bar — Reusable component for showing operation state and validation feedback.

Features:
- Context-aware status messages
- Visual indicators (colors, icons)
- Multiple status types: info, success, warning, error
- Optional progress/action hints
"""

from __future__ import annotations

from typing import Optional, Tuple, List, Callable
from enum import Enum, auto
from dataclasses import dataclass
import time

import pygame
from pygame import Rect, Surface

from widgets.ui.theme import COLORS, SHAPE
from utils.font_manager import font_manager, FontWeight
from utils.icon_manager import icon_manager


class StatusType(Enum):
    """Types of status messages"""
    INFO = auto()
    SUCCESS = auto()
    WARNING = auto()
    ERROR = auto()
    NEUTRAL = auto()


@dataclass
class StatusItem:
    """A status message with type and optional action"""
    message: str
    status_type: StatusType = StatusType.INFO
    detail: str = ""
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class StatusBar:
    """
    Status bar component for showing current operation state.
    
    Displays:
    - Main status message (e.g., "Defining regions...", "Painting collision")
    - Validation status (e.g., "3 regions defined", "2 missing collision")
    - Contextual help hints
    """
    
    def __init__(
        self,
        rect: Rect,
        show_icons: bool = True,
        show_timestamp: bool = False,
    ):
        self.rect = rect
        self.show_icons = show_icons
        self.show_timestamp = show_timestamp
        
        # Current status
        self.current = StatusItem("Ready", StatusType.NEUTRAL)
        self.history: List[StatusItem] = []
        self.max_history = 50
        
        # Visual settings
        self.icon_size = 16
        self.padding = 8
        self.message_spacing = 4
        
        # Font
        self._font = font_manager.get_font("Arial", 12, FontWeight.REGULAR)
        self._font_sm = font_manager.get_font("Arial", 10, FontWeight.REGULAR)
        self._font_bold = font_manager.get_font("Arial", 12, FontWeight.BOLD)
        
        # Callback for status changes
        self.on_status_changed: Optional[Callable[[StatusItem], None]] = None
    
    def _get_status_color(self, status_type: StatusType) -> Tuple[int, int, int]:
        """Get color for status type"""
        colors = {
            StatusType.INFO: COLORS.accent,
            StatusType.SUCCESS: COLORS.success,
            StatusType.WARNING: COLORS.warning,
            StatusType.ERROR: COLORS.danger,
            StatusType.NEUTRAL: COLORS.text_dim,
        }
        return colors.get(status_type, COLORS.text)
    
    def _get_status_icon(self, status_type: StatusType) -> str:
        """Get icon asset name for status type."""
        icons = {
            StatusType.INFO: "info",
            StatusType.SUCCESS: "check",
            StatusType.WARNING: "warning",
            StatusType.ERROR: "error",
            StatusType.NEUTRAL: "radio",
        }
        return icons.get(status_type, "radio")

    def _render_fit_text(
        self,
        font: pygame.font.Font,
        text: str,
        color: Tuple[int, int, int],
        max_width: int,
    ) -> Surface:
        """Render text, truncating with ellipsis when it must fit a fixed width."""
        if max_width <= 0:
            return font.render("", True, color)

        surf = font.render(text, True, color)
        if surf.get_width() <= max_width:
            return surf

        ellipsis = "..."
        if font.size(ellipsis)[0] > max_width:
            return font.render("", True, color)

        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            candidate = text[:mid].rstrip() + ellipsis
            if font.size(candidate)[0] <= max_width:
                low = mid
            else:
                high = mid - 1

        return font.render(text[:low].rstrip() + ellipsis, True, color)
    
    def set_status(
        self,
        message: str,
        status_type: StatusType = StatusType.INFO,
        detail: str = "",
    ) -> None:
        """Set the current status"""
        old_status = self.current
        self.current = StatusItem(message, status_type, detail)
        
        # Add to history if different from current
        if old_status.message != message or old_status.status_type != status_type:
            self.history.insert(0, old_status)
            if len(self.history) > self.max_history:
                self.history.pop()
        
        if self.on_status_changed:
            self.on_status_changed(self.current)
    
    def info(self, message: str, detail: str = "") -> None:
        """Set info status"""
        self.set_status(message, StatusType.INFO, detail)
    
    def success(self, message: str, detail: str = "") -> None:
        """Set success status"""
        self.set_status(message, StatusType.SUCCESS, detail)
    
    def warning(self, message: str, detail: str = "") -> None:
        """Set warning status"""
        self.set_status(message, StatusType.WARNING, detail)
    
    def error(self, message: str, detail: str = "") -> None:
        """Set error status"""
        self.set_status(message, StatusType.ERROR, detail)
    
    def clear(self) -> None:
        """Clear current status"""
        self.set_status("Ready", StatusType.NEUTRAL)
    
    def get_validation_summary(
        self,
        total: int,
        complete: int,
        incomplete: int,
        item_name: str = "item",
    ) -> str:
        """Generate a validation summary message"""
        parts = []
        if total > 0:
            parts.append(f"{total} {item_name}{'s' if total != 1 else ''}")
        if complete > 0:
            parts.append(f"{complete} complete")
        if incomplete > 0:
            parts.append(f"{incomplete} pending")
        
        return ", ".join(parts) if parts else f"No {item_name}s"
    
    def draw(self, screen: Surface) -> None:
        """Draw the status bar"""
        # Background
        pygame.draw.rect(screen, COLORS.panel, self.rect)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)
        
        x = self.rect.x + self.padding
        y = self.rect.centery
        
        # Icon
        if self.show_icons:
            icon_color = self._get_status_color(self.current.status_type)
            icon_surf = icon_manager.get_icon(
                self._get_status_icon(self.current.status_type),
                self.icon_size,
                icon_color,
            )
            screen.blit(icon_surf, (x, y - self.icon_size // 2))
            x += self.icon_size + 6
        
        right_limit = self.rect.right - self.padding
        time_surf = None
        if self.show_timestamp:
            age = time.time() - self.current.timestamp
            if age < 60:
                time_str = f"{int(age)}s ago"
            elif age < 3600:
                time_str = f"{int(age / 60)}m ago"
            else:
                time_str = f"{int(age / 3600)}h ago"

            time_surf = self._font_sm.render(time_str, True, COLORS.text_muted)
            right_limit -= time_surf.get_width() + self.message_spacing

        # Main message
        msg_color = self._get_status_color(self.current.status_type)
        available = right_limit - x
        detail_reserved = 0
        if self.current.detail and available > 80:
            detail_reserved = min(available // 2, 140)
        msg_surf = self._render_fit_text(
            self._font_bold,
            self.current.message,
            msg_color,
            max(0, available - detail_reserved),
        )
        screen.blit(msg_surf, (x, y - msg_surf.get_height() // 2))
        x += msg_surf.get_width() + self.message_spacing
        
        # Detail
        if self.current.detail:
            detail_surf = self._render_fit_text(
                self._font,
                self.current.detail,
                COLORS.text_dim,
                max(0, right_limit - x),
            )
            screen.blit(detail_surf, (x, y - detail_surf.get_height() // 2))
        
        # Timestamp for history items (if showing history)
        if time_surf is not None:
            time_x = self.rect.right - time_surf.get_width() - self.padding
            screen.blit(time_surf, (time_x, y - time_surf.get_height() // 2))
    
    def resize(self, rect: Rect) -> None:
        """Resize the status bar"""
        self.rect = rect
    
    def get_history(self) -> List[StatusItem]:
        """Get status history"""
        return list(self.history)
    
    def clear_history(self) -> None:
        """Clear status history"""
        self.history.clear()
