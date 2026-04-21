"""
Error Console UI component for viewing and managing application errors.

Provides a resizable console overlay with Ctrl+` toggle, error filtering,
and file-based log storage for performance.
"""

import json
import pygame
from pygame import Rect, Surface, Color, KEYDOWN, K_BACKQUOTE
from typing import List, Dict, Any, Set
from datetime import datetime
from constants import BASE_PATH
from utils import error_handler


class ErrorConsole:
    """Interactive error console with file-based log storage and filtering."""

    def __init__(self, editor_rect: Rect):
        self.editor_rect = editor_rect
        self.visible = False
        self.needs_redraw = True

        # Console dimensions and positioning
        self.width = min(800, editor_rect.width - 100)
        self.height = min(400, editor_rect.height - 100)
        self.x = (editor_rect.width - self.width) // 2
        self.y = (editor_rect.height - self.height) // 2

        # UI elements
        self.close_button = Rect(self.x + self.width - 30, self.y + 5, 25, 20)
        self.clear_button = Rect(self.x + 5, self.y + 5, 60, 20)
        self.filter_buttons = {
            "error": Rect(self.x + 70, self.y + 5, 50, 20),
            "warning": Rect(self.x + 125, self.y + 5, 60, 20),
            "info": Rect(self.x + 190, self.y + 5, 40, 20),
        }

        # Content area
        self.content_rect = Rect(
            self.x + 5, self.y + 30, self.width - 10, self.height - 35
        )
        self.scroll_offset = 0
        self.line_height = 16

        # Filtering
        self.active_filters: Set[str] = {"error", "warning", "info"}
        self.filtered_errors: List[Dict[str, Any]] = []

        # File-based log storage
        self.log_file = BASE_PATH / "data" / "logs" / "console.jsonl"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Load initial errors from file
        self._load_errors_from_file()

        # Colors
        self.bg_color = Color(40, 40, 40)
        self.border_color = Color(100, 100, 100)
        self.text_color = Color(200, 200, 200)
        self.button_color = Color(60, 60, 60)
        self.button_hover_color = Color(80, 80, 80)

        # Severity colors
        self.severity_colors = {
            "error": Color(255, 100, 100),
            "warning": Color(255, 200, 100),
            "info": Color(100, 150, 255),
        }

        # Fonts
        self.font = pygame.font.Font(None, 12)
        self.button_font = pygame.font.Font(None, 10)

        # Mouse state
        self.mouse_pos = (0, 0)
        self.dragging = False
        self.drag_offset = (0, 0)

    def toggle(self) -> None:
        """Toggle console visibility."""
        self.visible = not self.visible
        if self.visible:
            self._refresh_errors()
            self.needs_redraw = True

    def _load_errors_from_file(self) -> None:
        """Load errors from JSONL log file."""
        self.filtered_errors.clear()

        if not self.log_file.exists():
            return

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            error_data = json.loads(line)
                            if error_data.get("severity") in self.active_filters:
                                self.filtered_errors.append(error_data)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            error_handler.capture(e, context="load_console_errors", severity="warning")

    def _refresh_errors(self) -> None:
        """Refresh errors from both memory and file."""
        self._load_errors_from_file()

        # Add recent errors from memory that might not be in file yet
        recent_errors = error_handler.get_recent_errors(100)
        for error in recent_errors:
            if error.get("severity") in self.active_filters:
                # Avoid duplicates
                if not any(
                    e.get("timestamp") == error.get("timestamp")
                    for e in self.filtered_errors
                ):
                    self.filtered_errors.append(error)

        # Sort by timestamp (newest first)
        self.filtered_errors.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        self.needs_redraw = True

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events for the console."""
        if not self.visible:
            # Check for Ctrl+` toggle
            if event.type == KEYDOWN:
                if event.key == K_BACKQUOTE and (event.mod & pygame.KMOD_CTRL):
                    self.toggle()
                    return True
            return False

        if event.type == KEYDOWN:
            if event.key == K_BACKQUOTE and (event.mod & pygame.KMOD_CTRL):
                self.toggle()
                return True
            elif event.key == pygame.K_ESCAPE:
                self.visible = False
                return True

        elif event.type == pygame.MOUSEMOTION:
            self.mouse_pos = event.pos

            if self.dragging:
                self.x = event.pos[0] - self.drag_offset[0]
                self.y = event.pos[1] - self.drag_offset[1]
                self._update_rects()
                self.needs_redraw = True

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                mouse_pos = event.pos

                # Check close button
                if self.close_button.collidepoint(mouse_pos):
                    self.visible = False
                    return True

                # Check clear button
                if self.clear_button.collidepoint(mouse_pos):
                    self._clear_errors()
                    return True

                # Check filter buttons
                for severity, rect in self.filter_buttons.items():
                    if rect.collidepoint(mouse_pos):
                        self._toggle_filter(severity)
                        return True

                # Check title bar for dragging
                title_rect = Rect(self.x, self.y, self.width, 30)
                if title_rect.collidepoint(mouse_pos):
                    self.dragging = True
                    self.drag_offset = (mouse_pos[0] - self.x, mouse_pos[1] - self.y)
                    return True

                # Check content area for scrolling
                if self.content_rect.collidepoint(mouse_pos):
                    self._handle_content_click(mouse_pos)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.dragging = False

        elif event.type == pygame.MOUSEWHEEL:
            if self.content_rect.collidepoint(self.mouse_pos):
                self.scroll_offset -= event.y * 20
                self.scroll_offset = max(
                    0,
                    min(
                        self.scroll_offset,
                        max(
                            0,
                            len(self.filtered_errors) * self.line_height
                            - self.content_rect.height,
                        ),
                    ),
                )
                self.needs_redraw = True

        return False

    def _update_rects(self) -> None:
        """Update rectangle positions after move/resize."""
        self.close_button = Rect(self.x + self.width - 30, self.y + 5, 25, 20)
        self.clear_button = Rect(self.x + 5, self.y + 5, 60, 20)
        self.filter_buttons = {
            "error": Rect(self.x + 70, self.y + 5, 50, 20),
            "warning": Rect(self.x + 125, self.y + 5, 60, 20),
            "info": Rect(self.x + 190, self.y + 5, 40, 20),
        }
        self.content_rect = Rect(
            self.x + 5, self.y + 30, self.width - 10, self.height - 35
        )

    def _toggle_filter(self, severity: str) -> None:
        """Toggle error severity filter."""
        if severity in self.active_filters:
            self.active_filters.remove(severity)
        else:
            self.active_filters.add(severity)

        self._refresh_errors()

    def _clear_errors(self) -> None:
        """Clear all errors from memory and file."""
        try:
            # Clear memory
            error_handler.clear_errors()

            # Clear file
            if self.log_file.exists():
                self.log_file.unlink()

            # Clear display
            self.filtered_errors.clear()
            self.scroll_offset = 0
            self.needs_redraw = True

        except Exception as e:
            error_handler.capture(e, context="clear_console_errors")

    def _handle_content_click(self, mouse_pos: tuple) -> None:
        """Handle clicks in content area (could expand error details later)."""
        # For now, just handle scrolling
        pass

    def draw(self, screen: Surface) -> None:
        """Draw the error console."""
        if not self.visible:
            return

        if self.needs_redraw:
            self._render_content(screen)
            self.needs_redraw = False

        # Draw main console background
        console_surface = Surface((self.width, self.height))
        console_surface.fill(self.bg_color)
        pygame.draw.rect(
            console_surface, self.border_color, console_surface.get_rect(), 2
        )

        # Draw title bar
        title_rect = Rect(0, 0, self.width, 30)
        pygame.draw.rect(console_surface, self.button_color, title_rect)
        pygame.draw.rect(console_surface, self.border_color, title_rect, 1)

        # Draw title text
        title_text = self.font.render("Error Console", True, self.text_color)
        console_surface.blit(title_text, (10, 8))

        # Draw close button
        close_color = (
            self.button_hover_color
            if self.close_button.collidepoint(self.mouse_pos)
            else self.button_color
        )
        pygame.draw.rect(console_surface, close_color, Rect(self.width - 30, 5, 25, 20))
        pygame.draw.rect(
            console_surface, self.border_color, Rect(self.width - 30, 5, 25, 20), 1
        )
        close_text = self.button_font.render("X", True, self.text_color)
        console_surface.blit(close_text, (self.width - 22, 9))

        # Draw clear button
        clear_color = (
            self.button_hover_color
            if self.clear_button.collidepoint(self.mouse_pos)
            else self.button_color
        )
        pygame.draw.rect(console_surface, clear_color, Rect(5, 5, 60, 20))
        pygame.draw.rect(console_surface, self.border_color, Rect(5, 5, 60, 20), 1)
        clear_text = self.button_font.render("Clear", True, self.text_color)
        console_surface.blit(clear_text, (25, 9))

        # Draw filter buttons
        for severity, rect in self.filter_buttons.items():
            color = self.severity_colors.get(severity, self.text_color)
            if severity in self.active_filters:
                bg_color = Color(color.r // 2, color.g // 2, color.b // 2)
            else:
                bg_color = self.button_color

            hover_color = (
                self.button_hover_color
                if rect.collidepoint(self.mouse_pos)
                else bg_color
            )
            pygame.draw.rect(
                console_surface,
                hover_color,
                Rect(rect.x - self.x, rect.y - self.y, rect.width, rect.height),
            )
            pygame.draw.rect(
                console_surface,
                self.border_color,
                Rect(rect.x - self.x, rect.y - self.y, rect.width, rect.height),
                1,
            )

            text = self.button_font.render(severity.upper(), True, color)
            console_surface.blit(text, (rect.x - self.x + 5, rect.y - self.y + 5))

        # Draw content area
        content_surface = Surface((self.content_rect.width, self.content_rect.height))
        content_surface.fill(Color(30, 30, 30))

        # Draw error entries
        y_offset = -self.scroll_offset
        for error in self.filtered_errors:
            if y_offset + self.line_height > self.content_rect.height:
                break
            if y_offset >= 0:
                self._draw_error_entry(content_surface, error, y_offset)
            y_offset += self.line_height

        # Blit content to console
        console_surface.blit(content_surface, (5, 30))

        # Blit console to screen
        screen.blit(console_surface, (self.x, self.y))

    def _draw_error_entry(
        self, surface: Surface, error: Dict[str, Any], y: int
    ) -> None:
        """Draw a single error entry."""
        severity = error.get("severity", "error")
        color = self.severity_colors.get(severity, self.text_color)

        # Format timestamp
        timestamp = error.get("timestamp", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except (ValueError, TypeError) as e:
                error_handler.capture(
                    e, "Error formatting timestamp(known error)", "info"
                )
                time_str = (
                    timestamp.split("T")[-1][:8] if "T" in timestamp else timestamp[:8]
                )
            except Exception as e:
                error_handler.capture(
                    e, "Error formatting timestamp(unknown error)", "error"
                )
                time_str = "???:???:??"
        else:
            time_str = "???:???:??"

        # Build error line
        context = error.get("context", "")
        message = error.get("message", "")
        error_type = error.get("error_type", "")

        line = f"[{time_str}] "
        if context:
            line += f"{context} - "
        line += f"{error_type}: {message}"

        # Truncate if too long
        if len(line) > 100:
            line = line[:97] + "..."

        text = self.font.render(line, True, color)
        surface.blit(text, (2, y))

    def _render_content(self, screen: Surface) -> None:
        """Render content (placeholder for future optimizations)."""
        pass

    def add_error(self, error_data: Dict[str, Any]) -> None:
        """Add new error to console (called by ErrorHandler)."""
        if error_data.get("severity") in self.active_filters:
            self.filtered_errors.insert(0, error_data)
            if len(self.filtered_errors) > 1000:  # Limit display
                self.filtered_errors.pop()

            # Also append to file
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(error_data) + "\n")
            except Exception as e:
                error_handler.capture(
                    e, context="write_console_log", severity="warning"
                )

            self.needs_redraw = True
