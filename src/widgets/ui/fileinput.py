"""
Filename Input

Text input with autocomplete suggestions for file/directory names.
"""
import pygame
from pygame import Rect, Surface
from pathlib import Path
from typing import Callable, List
import os

from constants import BASE_PATH
from utils.font_manager import font_manager, FontWeight
from .base.input import SuggestionInput
from .base.uibase import create_simple_options
from .theme import COLORS


class FilenameInput(SuggestionInput):
    """Input field with file/directory autocomplete suggestions."""
    
    def __init__(
        self,
        editor_rect: Rect,
        on_confirm: Callable[[str], None],
        on_cancel: Callable[[], None],
    ):
        self.input_rect = Rect(0, 0, 400, 40)
        self.input_rect.center = editor_rect.center
        
        opts = create_simple_options(400, 40)
        super().__init__(
            opts,
            placeholder="Save Map As: (relative to data/)",
            on_confirm=on_confirm,
            on_cancel=on_cancel,
        )
        
        self.font = font_manager.get_font("Consolas", 14, FontWeight.REGULAR)
        self.data_root = BASE_PATH / "data"
    
    @property
    def active(self) -> bool:
        return self.is_focused
    
    @active.setter
    def active(self, value: bool) -> None:
        self.is_focused = value
    
    def _update_suggestions(self) -> None:
        if not self.data_root.exists():
            self.data_root.mkdir(parents=True, exist_ok=True)
        
        candidates: List[str] = []
        
        try:
            for root, dirs, files in os.walk(self.data_root):
                rel_path = Path(root).relative_to(self.data_root)
                depth = len(rel_path.parts)
                
                if str(rel_path) == ".":
                    depth = 0
                
                if depth > 1:
                    continue
                
                for f in files:
                    if f.endswith(".json"):
                        full_p = rel_path / f
                        candidates.append(str(full_p).replace("\\", "/"))
                
                for d in dirs:
                    full_p = rel_path / d
                    candidates.append(str(full_p).replace("\\", "/") + "/")
        except Exception:
            pass
        
        self.suggestions = [c for c in candidates if c.startswith(self.text)]
        self.suggestions.sort()
        self.suggestions = self.suggestions[:5]
    
    def show(self) -> None:
        self.text = ""
        self.suggestions = []
        self.selected_idx = -1
        self.is_focused = True
        self._update_suggestions()
    
    def hide(self) -> None:
        self.is_focused = False
        self.suggestions = []
        self.selected_idx = -1
    
    def draw(self, screen: Surface) -> None:
        if not self.is_focused:
            return
        
        # Draw input background
        pygame.draw.rect(screen, COLORS.panel, self.rect)
        pygame.draw.rect(screen, COLORS.border_soft, self.rect, 2)
        
        # Draw selection highlight
        if self.selection_start != self.selection_end:
            start, end = self._get_selection()
            text_before_start = self.text[:start]
            text_selected = self.text[start:end]
            sel_x = self.rect.x + 10 + self.font.size(text_before_start)[0]
            sel_w = self.font.size(text_selected)[0]
            sel_rect = pygame.Rect(sel_x, self.rect.y + 3, sel_w, self.rect.height - 6)
            pygame.draw.rect(screen, COLORS.selected, sel_rect)
        
        # Draw text
        if self.text:
            txt_surf = self.font.render(self.text, True, COLORS.text)
        else:
            txt_surf = self.font.render(
                self.placeholder, True, COLORS.text_muted
            )
        
        screen.blit(
            txt_surf,
            (self.rect.x + 10, self.rect.centery - txt_surf.get_height() // 2),
        )
        
        # Draw blinking cursor
        if self.show_cursor:
            cursor_x = self.rect.x + 10 + self.font.size(self.text[:self.cursor_pos])[0]
            if int(pygame.time.get_ticks() * 0.002) % 2 == 0:
                pygame.draw.line(
                    screen,
                    COLORS.text,
                    (cursor_x, self.rect.y + 4),
                    (cursor_x, self.rect.y + self.rect.height - 4),
                    2,
                )
        
        # Draw title
        title_surf = self.font.render(
            "Save Map As: (relative to data/)", True, COLORS.text
        )
        screen.blit(title_surf, (self.rect.x, self.rect.y - 20))
        
        # Draw suggestions
        if self.suggestions:
            box_h = 25
            total_h = len(self.suggestions) * box_h
            sugg_rect = Rect(
                self.rect.x,
                self.rect.bottom,
                self.rect.width,
                total_h,
            )
            
            pygame.draw.rect(screen, COLORS.panel_alt, sugg_rect)
            pygame.draw.rect(screen, COLORS.border_soft, sugg_rect, 1)
            
            for i, suggestion in enumerate(self.suggestions):
                row_rect = Rect(
                    sugg_rect.x,
                    sugg_rect.y + i * box_h,
                    sugg_rect.width,
                    box_h,
                )
                
                if i == self.selected_idx:
                    pygame.draw.rect(screen, COLORS.selected, row_rect)
                
                s_txt = self.font.render(suggestion, True, COLORS.text_dim)
                screen.blit(s_txt, (row_rect.x + 10, row_rect.y + 4))
