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
        self.pan_btn_rect = Rect(x + 10, y + 7, 60, 20)
        self.checkbox_rect = Rect(x + 10, y + 10, 14, 14)

    def resize(self, width: int):
        self.rect.width = width

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.pan_btn_rect.collidepoint(event.pos) or self.checkbox_rect.inflate(10, 10).collidepoint(event.pos):
                self.editor.pan_mode = not self.editor.pan_mode
                return True
        return False

    def draw(self, screen: pygame.Surface):
        pygame.draw.rect(screen, self.bg_color, self.rect)
        pygame.draw.line(screen, self.border_color, (self.rect.x, self.rect.bottom - 1), (self.rect.right, self.rect.bottom - 1))
        
        # Draw Pan Mode Toggle
        is_pan = getattr(self.editor, "pan_mode", False)
        
        # Checkbox
        pygame.draw.rect(screen, (30, 30, 35), self.checkbox_rect)
        pygame.draw.rect(screen, self.border_color, self.checkbox_rect, 1)
        if is_pan:
            # Draw a square check
            inner = self.checkbox_rect.inflate(-6, -6)
            pygame.draw.rect(screen, self.accent_color, inner)
            
        # Label
        label_surf = self.font.render("Pan Mode (Space)", True, self.text_color)
        screen.blit(label_surf, (self.checkbox_rect.right + 8, self.rect.y + 10))
        
        # Tooltip-like background if hovering
        if self.pan_btn_rect.inflate(20, 0).collidepoint(pygame.mouse.get_pos()):
            pygame.draw.rect(screen, (255, 255, 255, 20), self.pan_btn_rect.inflate(40, 5), border_radius=3)
