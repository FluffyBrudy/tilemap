"""
Map Setup Dialog

Dialog for setting up new tilemap dimensions and tile sizes.
"""
import pygame
from typing import TYPE_CHECKING, List
from pygame import Rect


if TYPE_CHECKING:
    from editor import Editor

from .ui.theme import COLORS, FONTS
from .ui.base.input import NumericInput
from .ui.base.uibase import create_simple_options
from utils.font_manager import font_manager, FontWeight


class FormInput(NumericInput):
    """Numeric input field for map setup form."""
    
    def __init__(self, rect: Rect, label: str, key: str, default_val: str = ""):
        self.label = label
        self.key = key
        
        input_rect = Rect(rect.x, rect.y + 20, rect.width, 30)
        opts = create_simple_options(rect.width, 30)
        super().__init__(opts)
        
        self.rect = input_rect
        self.text = default_val
        
        self.font = font_manager.get_font("Arial", 16, FontWeight.REGULAR)
        self.font_label = font_manager.get_font("Arial", 14, FontWeight.REGULAR)
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.is_focused = self.rect.collidepoint(event.pos)
            return self.is_focused
        
        if self.is_focused and event.type == pygame.KEYDOWN:
            ctrl_held = event.mod & (pygame.KMOD_CTRL | pygame.KMOD_META)
            shift_held = event.mod & pygame.KMOD_SHIFT
            
            # Ctrl/Cmd+A: Select all
            if event.key == pygame.K_a and ctrl_held:
                self._select_all()
                return True
            
            # Ctrl/Cmd+Backspace: Delete word
            if event.key == pygame.K_BACKSPACE and ctrl_held:
                self._delete_word_left()
                return True
            
            # Ctrl/Cmd+Left: Word left
            if event.key == pygame.K_LEFT and ctrl_held:
                self._move_cursor_word_left(shift_held)
                return True
            
            # Ctrl/Cmd+Right: Word right
            if event.key == pygame.K_RIGHT and ctrl_held:
                self._move_cursor_word_right(shift_held)
                return True
            
            # Home: Move to start
            if event.key == pygame.K_HOME:
                self.cursor_pos = 0
                if not shift_held:
                    self.selection_start = self.selection_end = 0
                return True
            
            # End: Move to end
            if event.key == pygame.K_END:
                self.cursor_pos = len(self.text)
                if not shift_held:
                    self.selection_start = self.selection_end = len(self.text)
                return True
            
            # Left arrow
            if event.key == pygame.K_LEFT:
                if self.cursor_pos > 0:
                    self.cursor_pos -= 1
                if not shift_held:
                    self.selection_start = self.selection_end = self.cursor_pos
                return True
            
            # Right arrow
            if event.key == pygame.K_RIGHT:
                if self.cursor_pos < len(self.text):
                    self.cursor_pos += 1
                if not shift_held:
                    self.selection_start = self.selection_end = self.cursor_pos
                return True
            
            # Backspace
            if event.key == pygame.K_BACKSPACE:
                if not self._delete_selection():
                    self._delete_char()
                return True
            
            # Return/Tab - don't handle
            if event.key in (pygame.K_RETURN, pygame.K_TAB):
                return False
            
            # Digits only
            if event.unicode.isdigit():
                self._add_char(event.unicode)
                return True
            
            return True
        return False
    
    def get_value(self) -> int:
        return int(self.text) if self.text else 0
    
    def _get_cursor_x(self) -> int:
        """Get x position of cursor based on text before cursor."""
        text_before = self.text[:self.cursor_pos]
        return self.rect.x + 5 + self.font.size(text_before)[0]
    
    def draw(self, screen: pygame.Surface):
        # Draw label
        label_surf = self.font_label.render(self.label, True, COLORS.text_dim)
        screen.blit(label_surf, (self.rect.x, self.rect.y - 18))
        
        # Draw input background
        bg_color = COLORS.panel
        border_color = COLORS.accent if self.is_focused else COLORS.border
        border_width = 2 if self.is_focused else 1
        
        pygame.draw.rect(screen, bg_color, self.rect)
        pygame.draw.rect(screen, border_color, self.rect, border_width)
        
        # Draw selection highlight
        if self.selection_start != self.selection_end:
            start, end = self._get_selection()
            text_before_start = self.text[:start]
            text_selected = self.text[start:end]
            sel_x = self.rect.x + 5 + self.font.size(text_before_start)[0]
            sel_w = self.font.size(text_selected)[0]
            sel_rect = pygame.Rect(sel_x, self.rect.y + 3, sel_w, self.rect.height - 6)
            pygame.draw.rect(screen, COLORS.selected, sel_rect)
        
        # Draw text
        if self.text:
            text_surf = self.font.render(self.text, True, COLORS.text)
        else:
            text_surf = self.font.render(self.placeholder, True, COLORS.text_muted)
        
        screen.blit(text_surf, (self.rect.x + 5, self.rect.y + 5))
        
        # Draw blinking cursor
        if self.is_focused and self.show_cursor:
            cursor_x = self._get_cursor_x()
            if int(pygame.time.get_ticks() * 0.002) % 2 == 0:
                pygame.draw.line(
                    screen,
                    COLORS.text,
                    (cursor_x, self.rect.y + 4),
                    (cursor_x, self.rect.y + self.rect.height - 4),
                    2,
                )


class MapSetup:
    def __init__(self, editor: "Editor", center_rect: Rect):
        self.editor = editor
        self.rect = center_rect
        self.visible = True
        self.error_message = ""

        self.inputs: List[FormInput] = []
        fields = [
            ("Map Width", "map_w", "30"),
            ("Map Height", "map_h", "20"),
            ("Tile Width", "tile_w", "32"),
            ("Tile Height", "tile_h", "32"),
        ]

        cols = 2
        cell_w = (self.rect.width - 40) // cols
        cell_h = 70
        start_x = self.rect.x + 20
        start_y = self.rect.y + 60

        for i, (lbl, key, default) in enumerate(fields):
            row, col = divmod(i, cols)
            r = Rect(start_x + col * cell_w, start_y + row * cell_h, cell_w - 10, 60)
            self.inputs.append(FormInput(r, lbl, key, default))

        self.btn_rect = Rect(self.rect.centerx - 60, self.rect.bottom - 50, 120, 35)
        self.font = font_manager.get_font("Arial", 20, FontWeight.BOLD)

    def resize(self, center_rect: Rect):
        self.rect = center_rect
        cols = 2
        cell_w = (self.rect.width - 40) // cols
        cell_h = 70
        start_x = self.rect.x + 20
        start_y = self.rect.y + 60

        for i, inp in enumerate(self.inputs):
            row, col = divmod(i, cols)
            r = Rect(start_x + col * cell_w, start_y + row * cell_h, cell_w - 10, 60)
            inp.rect = Rect(r.x, r.y + 20, r.width, 30)

        self.btn_rect = Rect(self.rect.centerx - 60, self.rect.bottom - 50, 120, 35)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and self.btn_rect.collidepoint(
            event.pos
        ):
            self.submit()
            return True

        for inp in self.inputs:
            if inp.handle_event(event):
                if inp.is_focused:
                    for o in self.inputs:
                        if o != inp:
                            o.is_focused = False
                return True
        return True

    def submit(self):
        try:
            vals = {i.key: i.get_value() for i in self.inputs}
            if any(v <= 0 for v in vals.values()):
                raise ValueError("Values must be > 0")

            map_size = (vals["map_w"], vals["map_h"])
            tile_size = (vals["tile_w"], vals["tile_h"])

            self.editor.tilemap.init_size(tile_size, map_size)
            self.editor.tilemap.initialized = True
            self.editor.post_map_setup()
            self.visible = False

        except ValueError as e:
            self.error_message = str(e)

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return

        # Draw background
        pygame.draw.rect(screen, COLORS.panel, self.rect)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)

        # Draw title
        title = self.font.render("Project Setup", True, COLORS.text)
        screen.blit(title, (self.rect.x + 20, self.rect.y + 15))

        # Draw inputs
        for inp in self.inputs:
            inp.draw(screen)

        # Draw button
        pygame.draw.rect(screen, COLORS.accent, self.btn_rect)
        btn_txt = self.font.render("Create", True, COLORS.text)
        screen.blit(btn_txt, btn_txt.get_rect(center=self.btn_rect.center))

        # Draw error
        if self.error_message:
            err = font_manager.get_font("Arial", 12, FontWeight.REGULAR).render(
                self.error_message, True, COLORS.danger
            )
            screen.blit(err, (self.rect.x + 20, self.btn_rect.y - 20))
