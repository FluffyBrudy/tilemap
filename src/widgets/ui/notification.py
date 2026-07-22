import time

import pygame
from pygame import Rect, Surface


class Notification:
    def __init__(self, text: str, color=(200, 200, 200), duration=3.0):
        self.text = text
        self.color = color
        self.duration = duration
        self.start_time = time.time()
        self.y_offset = 0

    @property
    def is_expired(self):
        return time.time() - self.start_time > self.duration


class NotificationManager:
    def __init__(self, editor):
        self.editor = editor
        self.notifications: list[Notification] = []
        self.font = pygame.font.SysFont("Arial", 14, bold=True)

    def notify(self, text: str, color=(200, 200, 200), duration=3.0):
        self.notifications.append(Notification(text, color, duration))
        print(f"NOTIFICATION: {text}")

    def error(self, text: str):
        self.notify(text, color=(255, 100, 100), duration=4.0)

    def warning(self, text: str):
        self.notify(text, color=(255, 200, 50), duration=3.0)

    def success(self, text: str):
        self.notify(text, color=(100, 255, 100), duration=2.5)

    def update(self):
        self.notifications = [n for n in self.notifications if not n.is_expired]

    def draw(self, screen: Surface):
        self.update()
        if not self.notifications:
            return

        screen_w = screen.get_width()
        screen_h = screen.get_height()

        curr_y = screen_h - 40
        for n in reversed(self.notifications):
            text_surf = self.font.render(n.text, True, (255, 255, 255))
            tw, th = text_surf.get_size()

            age = time.time() - n.start_time
            alpha = 255
            if age > n.duration - 0.5:
                alpha = int(255 * (n.duration - age) / 0.5)

            bg_rect = Rect(
                screen_w // 2 - tw // 2 - 10, curr_y - th - 5, tw + 20, th + 10
            )

            s = Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            s.fill((40, 44, 52, min(alpha, 200)))
            pygame.draw.rect(s, (*n.color, alpha), s.get_rect(), 2, border_radius=4)
            screen.blit(s, bg_rect.topleft)

            text_surf.set_alpha(alpha)
            screen.blit(
                text_surf, (bg_rect.centerx - tw // 2, bg_rect.centery - th // 2)
            )

            curr_y -= th + 15
