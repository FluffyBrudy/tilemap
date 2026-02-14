import pygame
from pygame import Rect, Color
from typing import TYPE_CHECKING, List, Callable

if TYPE_CHECKING:
    from editor import Editor

class Toolbar:
    def __init__(self, editor: "Editor", x: int, y: int, w: int, h: int = 35):
        self.editor = editor
        self.rect = Rect(x, y, w, h)
        self.bg_color = (45, 45, 50)
        self.border_color = (60, 60, 65)
        self.text_color = (220, 220, 220)
        self.accent_color = (66, 135, 245)
        
        self.font = pygame.font.SysFont("Arial", 12)
        
        # Define the pan toggle button
        self.pan_btn_rect = Rect(x + 10, y + 7, 120, 20)
        self.pan_checkbox_rect = Rect(x + 10, y + 10, 14, 14)

        self.auto_btn_rect = Rect(x + 150, y + 7, 120, 20)
        self.auto_checkbox_rect = Rect(x + 150, y + 10, 14, 14)

    def resize(self, width: int):
        self.rect.width = width

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.pan_checkbox_rect.inflate(10, 10).collidepoint(event.pos) or \
               Rect(self.pan_checkbox_rect.right, self.rect.y, 100, self.rect.height).collidepoint(event.pos):
                self.editor.pan_mode = not self.editor.pan_mode
                return True
            
            if self.auto_checkbox_rect.inflate(10, 10).collidepoint(event.pos) or \
               Rect(self.auto_checkbox_rect.right, self.rect.y, 100, self.rect.height).collidepoint(event.pos):
                self.editor.toggle_auto_autotile()
                return True
        return False

    def draw(self, screen: pygame.Surface):
        pygame.draw.rect(screen, self.bg_color, self.rect)
        pygame.draw.line(screen, self.border_color, (self.rect.x, self.rect.bottom - 1), (self.rect.right, self.rect.bottom - 1))
        
        # 1. Pan Mode
        is_pan = getattr(self.editor, "pan_mode", False)
        pygame.draw.rect(screen, (30, 30, 35), self.pan_checkbox_rect)
        pygame.draw.rect(screen, self.border_color, self.pan_checkbox_rect, 1)
        if is_pan:
            pygame.draw.rect(screen, self.accent_color, self.pan_checkbox_rect.inflate(-6, -6))
        
        label_pan = self.font.render("Pan Mode (Space)", True, self.text_color)
        screen.blit(label_pan, (self.pan_checkbox_rect.right + 8, self.rect.y + 10))

        # 2. Autotile Mode
        is_auto = getattr(self.editor, "autotile_mode", False)
        pygame.draw.rect(screen, (30, 30, 35), self.auto_checkbox_rect)
        pygame.draw.rect(screen, self.border_color, self.auto_checkbox_rect, 1)
        if is_auto:
            pygame.draw.rect(screen, self.accent_color, self.auto_checkbox_rect.inflate(-6, -6))
        
        label_auto = self.font.render("Autotile Mode", True, self.text_color)
        screen.blit(label_auto, (self.auto_checkbox_rect.right + 8, self.rect.y + 10))
