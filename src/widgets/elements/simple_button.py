from typing import Callable, Optional, Tuple, Any
from pygame import Rect, Surface, Color
import pygame


class SimpleButton:
    def __init__(
        self,
        rect: Rect,
        label: str,
        normal_color: Tuple[int, int, int] = (80, 120, 80),
        hover_color: Tuple[int, int, int] = (100, 160, 100),
        text_color: Tuple[int, int, int] = (220, 220, 220),
        border_radius: int = 4,
        on_click: Optional[Callable[[], None]] = None,
    ):
        self.rect = rect
        self.label = label
        self.normal_color = normal_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.border_radius = border_radius
        self.on_click = on_click

        self.is_hovered = False

    def update(self, mouse_pos: Tuple[int, int]) -> None:
        self.is_hovered = self.rect.collidepoint(mouse_pos)

    def handle_click(self, mouse_pos: Tuple[int, int]) -> bool:
        if self.rect.collidepoint(mouse_pos):
            if self.on_click:
                self.on_click()
            return True
        return False

    def handle_click_with_data(self, mouse_pos: Tuple[int, int], data: Any) -> bool:
        if self.rect.collidepoint(mouse_pos):
            if self.on_click:
                self.on_click(data)
            return True
        return False

    def draw(self, screen: Surface, font: Optional[pygame.font.Font] = None) -> None:
        color = self.hover_color if self.is_hovered else self.normal_color
        pygame.draw.rect(screen, color, self.rect, border_radius=self.border_radius)

        if self.label and font:
            text_surf = font.render(self.label, True, self.text_color)
            text_rect = text_surf.get_rect(
                center=(self.rect.centerx, self.rect.centery)
            )
            screen.blit(text_surf, text_rect)