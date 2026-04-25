"""
Input Fields Base

Base classes for text input fields with common functionality.
"""
from typing import Callable, Optional, List

import pygame
from pygame import Rect, Surface

from ..theme import COLORS
from .uibase import UIBase, UIOptions, create_simple_options
from utils.font_manager import font_manager, FontWeight


class InputBase(UIBase):
    """
    Base class for text input fields.
    
    Provides:
    - text management (text, cursor, selection)
    - focus handling
    - keyboard event handling with shortcuts:
      - Ctrl+A: select all
      - Ctrl+Left/Right: word navigation
      - Ctrl+Backspace: delete word
      - Home/End: move to start/end
      - Selection support
    - placeholder support
    
    Usage:
        class MyInput(InputBase):
            def __init__(self, rect: Rect, placeholder: str = ""):
                opts = create_simple_options(rect.width, rect.height)
                super().__init__(opts)
                self.placeholder = placeholder
    """
    
    def __init__(
        self,
        options: UIOptions,
        placeholder: str = "",
        on_confirm: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        super().__init__(options)
        
        self.placeholder = placeholder
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        
        self.text = ""
        self.is_focused = False
        
        # Font
        self.font = font_manager.get_font("Arial", 14, FontWeight.REGULAR)
        
        # Cursor & Selection
        self.cursor_pos = 0
        self.selection_start = 0
        self.selection_end = 0
        self.show_cursor = True
    
    def _get_selection(self) -> tuple:
        """Get normalized selection start/end."""
        start, end = self.selection_start, self.selection_end
        if start <= end:
            return start, end
        return end, start
    
    def _select_all(self) -> None:
        """Select all text."""
        self.selection_start = 0
        self.selection_end = len(self.text)
        self.cursor_pos = len(self.text)
    
    def _delete_selection(self) -> bool:
        """Delete selected text. Returns True if deleted."""
        if self.selection_start != self.selection_end:
            start, end = self._get_selection()
            self.text = self.text[:start] + self.text[end:]
            self.cursor_pos = start
            self.selection_start = self.selection_end = self.cursor_pos
            return True
        return False
    
    def _delete_word_left(self) -> bool:
        """Delete word to the left of cursor."""
        if self._delete_selection():
            return True
        
        pos = self.cursor_pos
        while pos > 0 and self.text[pos - 1].isspace():
            pos -= 1
        while pos > 0 and not self.text[pos - 1].isspace():
            pos -= 1
        
        if pos < self.cursor_pos:
            self.text = self.text[:pos] + self.text[self.cursor_pos:]
            self.cursor_pos = pos
            return True
        return False
    
    def _move_cursor_word_left(self, extend: bool = False) -> None:
        """Move cursor one word left."""
        pos = self.cursor_pos
        while pos > 0 and self.text[pos - 1].isspace():
            pos -= 1
        while pos > 0 and not self.text[pos - 1].isspace():
            pos -= 1
        self.cursor_pos = pos
        if not extend:
            self.selection_start = self.selection_end = self.cursor_pos
    
    def _move_cursor_word_right(self, extend: bool = False) -> None:
        """Move cursor one word right."""
        pos = self.cursor_pos
        while pos < len(self.text) and self.text[pos].isspace():
            pos += 1
        while pos < len(self.text) and not self.text[pos].isspace():
            pos += 1
        self.cursor_pos = pos
        if not extend:
            self.selection_start = self.selection_end = self.cursor_pos
    
    def set_focus(self, focused: bool) -> None:
        self.is_focused = focused
        if focused:
            self.cursor_pos = len(self.text)
            self.selection_start = self.selection_end = 0
    
    def clear(self) -> None:
        self.text = ""
        self.cursor_pos = 0
        self.selection_start = self.selection_end = 0
    
    def get_value(self) -> str:
        return self.text
    
    def _add_char(self, char: str) -> bool:
        if char and char.isprintable():
            self.text += char
            self.cursor_pos = len(self.text)
            return True
        return False
    
    def _delete_char(self) -> bool:
        if self.text:
            self.text = self.text[:-1]
            self.cursor_pos = len(self.text)
            return True
        return False
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.is_focused:
            return False
        
        if event.type == pygame.KEYDOWN:
            # Support both Ctrl (Linux/Win) and Cmd (Mac)
            ctrl_held = event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
            shift_held = event.mod & pygame.KMOD_SHIFT
            
            if event.key == pygame.K_ESCAPE:
                if self.on_cancel:
                    self.on_cancel()
                self.is_focused = False
                return True
            
            if event.key == pygame.K_RETURN:
                if self.on_confirm:
                    self.on_confirm(self.text)
                self.is_focused = False
                return True
            
            # Ctrl/Cmd+A: Select all
            if event.key == pygame.K_a and ctrl_held:
                self._select_all()
                return True
            
            # Ctrl/Cmd+Backspace: Delete word left
            if event.key == pygame.K_BACKSPACE and ctrl_held:
                return self._delete_word_left()
            
            # Ctrl/Cmd+Left: Move word left
            if event.key == pygame.K_LEFT and ctrl_held:
                self._move_cursor_word_left(shift_held)
                return True
            
            # Ctrl/Cmd+Right: Move word right
            if event.key == pygame.K_RIGHT and ctrl_held:
                self._move_cursor_word_right(shift_held)
                return True
            
            # Ctrl/Cmd+Backspace (without modifier is handled below)
            if event.key == pygame.K_BACKSPACE:
                if not self._delete_selection():
                    return self._delete_char()
                return True
            
            # Left/Right arrows
            if event.key == pygame.K_LEFT:
                if self.cursor_pos > 0:
                    self.cursor_pos -= 1
                if not shift_held:
                    self.selection_start = self.selection_end = self.cursor_pos
                return True
            if event.key == pygame.K_RIGHT:
                if self.cursor_pos < len(self.text):
                    self.cursor_pos += 1
                if not shift_held:
                    self.selection_start = self.selection_end = self.cursor_pos
                return True
            
            # Home/End
            if event.key == pygame.K_HOME:
                self.cursor_pos = 0
                if not shift_held:
                    self.selection_start = self.selection_end = 0
                return True
            if event.key == pygame.K_END:
                self.cursor_pos = len(self.text)
                if not shift_held:
                    self.selection_start = self.selection_end = self.cursor_pos
                return True
            
            if event.key == pygame.K_TAB:
                return False
            
            return self._add_char(event.unicode)
        
        return False
    
    def handle_mousedown(self, pos: tuple) -> bool:
        was_focused = self.is_focused
        self.is_focused = self.rect.collidepoint(pos)
        return self.is_focused and not was_focused
    
    def draw(self, surface: Surface) -> None:
        if self.local_surface is None:
            return
        
        self.draw_base()
        
        # Draw text
        if self.text:
            text_color = COLORS.text
            text_surf = self.font.render(self.text, True, text_color)
        else:
            text_color = COLORS.text_muted
            text_surf = self.font.render(self.placeholder, True, text_color)
        
        text_y = self.box_model["top"] + (self.box_model["content_height"] - text_surf.get_height()) // 2
        surface.blit(text_surf, (self.box_model["left"] + 8, text_y))
        
        # Draw cursor
        if self.is_focused and self.show_cursor:
            cursor_x = self.box_model["left"] + 8 + text_surf.get_width()
            if int(pygame.time.get_ticks() * 0.002) % 2 == 0:
                pygame.draw.line(
                    surface,
                    COLORS.text,
                    (cursor_x, self.box_model["top"] + 4),
                    (cursor_x, self.box_model["top"] + self.box_model["content_height"] - 4),
                    2,
                )
        
        super().render(surface)


class NumericInput(InputBase):
    """Numeric input field that only accepts digits."""
    
    def __init__(
        self,
        options: UIOptions,
        placeholder: str = "",
        on_confirm: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        super().__init__(options, placeholder, on_confirm, on_cancel)
    
    def _add_char(self, char: str) -> bool:
        if char.isdigit():
            self.text += char
            self.cursor_pos = len(self.text)
            return True
        return False
    
    def get_value(self) -> int:
        return int(self.text) if self.text else 0
    
    def _get_cursor_x(self) -> int:
        """Get x position of cursor."""
        text_before = self.text[:self.cursor_pos]
        return self.box_model["left"] + 5 + self.font.size(text_before)[0]
    
    def draw(self, surface: Surface) -> None:
        if self.local_surface is None:
            return
        
        self.draw_base()
        
        # Draw selection highlight
        if self.selection_start != self.selection_end:
            start, end = self._get_selection()
            text_before_start = self.text[:start]
            text_selected = self.text[start:end]
            sel_x = self.box_model["left"] + 5 + self.font.size(text_before_start)[0]
            sel_w = self.font.size(text_selected)[0]
            sel_rect = pygame.Rect(sel_x, self.box_model["top"] + 3, sel_w, self.box_model["content_height"] - 6)
            pygame.draw.rect(surface, COLORS.selected, sel_rect)
        
        # Draw text
        if self.text:
            text_surf = self.font.render(self.text, True, COLORS.text)
        else:
            text_surf = self.font.render(self.placeholder, True, COLORS.text_muted)
        
        text_y = self.box_model["top"] + (self.box_model["content_height"] - text_surf.get_height()) // 2
        surface.blit(text_surf, (self.box_model["left"] + 5, text_y))
        
        # Draw blinking cursor
        if self.is_focused and self.show_cursor:
            cursor_x = self._get_cursor_x()
            if int(pygame.time.get_ticks() * 0.002) % 2 == 0:
                pygame.draw.line(
                    surface,
                    COLORS.text,
                    (cursor_x, self.box_model["top"] + 4),
                    (cursor_x, self.box_model["top"] + self.box_model["content_height"] - 4),
                    2,
                )
        
        super().render(surface)


class SuggestionInput(InputBase):
    """Input field with autocomplete suggestions."""
    
    def __init__(
        self,
        options: UIOptions,
        placeholder: str = "",
        on_confirm: Optional[Callable[[str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
    ):
        super().__init__(options, placeholder, on_confirm, on_cancel)
        
        self.suggestions: List[str] = []
        self.selected_idx = -1
    
    def _update_suggestions(self) -> None:
        """Override in subclass to provide suggestions."""
        pass
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.is_focused:
            return False
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True
            
            if event.key == pygame.K_RETURN:
                if self.selected_idx >= 0 and self.suggestions:
                    self.text = self.suggestions[self.selected_idx]
                    self.selected_idx = -1
                    self._update_suggestions()
                else:
                    if self.on_confirm:
                        self.on_confirm(self.text)
                    self.hide()
                return True
            
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                self.selected_idx = -1
                self._update_suggestions()
                return True
            
            if event.key == pygame.K_UP:
                self.selected_idx = max(-1, self.selected_idx - 1)
                return True
            
            if event.key == pygame.K_DOWN:
                self.selected_idx = min(len(self.suggestions) - 1, self.selected_idx + 1)
                return True
            
            if event.key == pygame.K_TAB:
                if self.suggestions:
                    self.text = self.suggestions[0]
                    self._update_suggestions()
                return True
            
            if event.unicode.isprintable():
                self.text += event.unicode
                self.selected_idx = -1
                self._update_suggestions()
                return True
        
        return False
    
    def show(self) -> None:
        self.is_focused = True
        self.text = ""
        self.suggestions = []
        self.selected_idx = -1
        self._update_suggestions()
    
    def hide(self) -> None:
        self.is_focused = False
        self.suggestions = []
        self.selected_idx = -1
    
    def draw(self, surface: Surface) -> None:
        super().draw(surface)
        
        if not self.is_focused or not self.suggestions:
            return
        
        # Draw suggestions dropdown
        box_h = 25
        total_h = len(self.suggestions) * box_h
        sugg_rect = Rect(
            self.box_model["offset_x"],
            self.box_model["offset_y"] + self.box_model["full_height"],
            self.box_model["full_width"],
            total_h,
        )
        
        pygame.draw.rect(surface, COLORS.panel_alt, sugg_rect)
        pygame.draw.rect(surface, COLORS.border_soft, sugg_rect, 1)
        
        for i, suggestion in enumerate(self.suggestions):
            row_rect = Rect(
                sugg_rect.x,
                sugg_rect.y + i * box_h,
                sugg_rect.width,
                box_h,
            )
            
            if i == self.selected_idx:
                pygame.draw.rect(surface, COLORS.selected, row_rect)
            
            s_txt = self.font.render(suggestion, True, COLORS.text_dim)
            surface.blit(s_txt, (row_rect.x + 10, row_rect.y + 4))