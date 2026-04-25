"""
Notification System

Toast notifications that appear at the bottom of the screen.
"""
import pygame
from pygame import Rect, Surface
import time
from typing import List

from .theme import COLORS
from utils.font_manager import font_manager, FontWeight


class Notification:
    def __init__(self, text: str, color: tuple = None, duration: float = 3.0):
        self.text = text
        self.color = color or COLORS.text
        self.duration = duration
        self.start_time = time.time()

    @property
    def is_expired(self) -> bool:
        return time.time() - self.start_time > self.duration


class NotificationManager:
    def __init__(self, editor):
        self.editor = editor
        self.notifications: List[Notification] = []
        self.font = font_manager.get_font("Arial", 14, FontWeight.BOLD)

    def notify(self, text: str, color: tuple = None, duration: float = 3.0) -> None:
        self.notifications.append(Notification(text, color, duration))

    def error(self, text: str) -> None:
        self.notify(text, color=COLORS.danger, duration=4.0)

    def success(self, text: str) -> None:
        self.notify(text, color=COLORS.success, duration=2.5)

    def update(self) -> None:
        self.notifications = [n for n in self.notifications if not n.is_expired]

    def draw(self, screen: Surface) -> None:
        self.update()
        if not self.notifications:
            return

        screen_w = screen.get_width()
        screen_h = screen.get_height()
        
        # Draw from bottom up
        curr_y = screen_h - 40
        for n in reversed(self.notifications):
            text_surf = self.font.render(n.text, True, COLORS.text)
            tw, th = text_surf.get_size()
            
            # Fade out
            age = time.time() - n.start_time
            alpha = 255
            if age > n.duration - 0.5:
                alpha = int(255 * (n.duration - age) / 0.5)
            
            bg_rect = Rect(screen_w // 2 - tw // 2 - 10, curr_y - th - 5, tw + 20, th + 10)
            
            # Draw BG
            s = Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            s.fill((40, 44, 52, min(alpha, 200)))
            pygame.draw.rect(s, (*n.color, alpha), s.get_rect(), 2, border_radius=4)
            screen.blit(s, bg_rect.topleft)
            
            # Draw Text
            text_surf.set_alpha(alpha)
            screen.blit(text_surf, (bg_rect.centerx - tw // 2, bg_rect.centery - th // 2))
            
            curr_y -= (th + 15)
