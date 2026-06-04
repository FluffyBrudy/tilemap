import pygame
from pygame import Rect, Surface
from typing import Callable, Optional


class ConfirmDialog:
    def __init__(self, editor_rect: Rect):
        self.editor_rect = editor_rect
        self.rect = Rect(0, 0, 420, 180)
        self.rect.center = editor_rect.center

        self.active = False
        self.title = ""
        self.message = ""
        self.on_confirm: Optional[Callable[[], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        self.bg_color = (40, 40, 40)
        self.border_color = (100, 100, 100)
        self.text_color = (255, 255, 255)
        self.warn_color = (255, 200, 60)
        self.button_color = (60, 100, 180)
        self.button_hover_color = (80, 120, 200)

        self.btn_proceed = Rect(0, 0, 110, 30)
        self.btn_cancel = Rect(0, 0, 110, 30)

        self.font_title = pygame.font.SysFont("Arial", 18, bold=True)
        self.font_text = pygame.font.SysFont("Arial", 14)
        self.font_btn = pygame.font.SysFont("Arial", 14, bold=True)

        self.btn_proceed_hover = False
        self.btn_cancel_hover = False
        self._layout()

    def _layout(self):
        self.rect.center = self.editor_rect.center
        btn_y = self.rect.bottom - 50
        cx = self.rect.centerx
        self.btn_cancel = Rect(cx - 120, btn_y, 110, 30)
        self.btn_proceed = Rect(cx + 10, btn_y, 110, 30)

    def show(
        self,
        title: str,
        message: str,
        on_confirm: Callable[[], None],
        on_cancel: Callable[[], None],
    ):
        if self.active:
            self.hide()
        self.active = True
        self.title = title
        self.message = message
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.btn_proceed_hover = False
        self.btn_cancel_hover = False
        self._layout()

    def hide(self):
        self.active = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False

        self._layout()
        mouse_pos = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.btn_proceed.collidepoint(mouse_pos):
                if self.on_confirm:
                    self.on_confirm()
                self.hide()
                return True
            if self.btn_cancel.collidepoint(mouse_pos):
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True
            elif event.key == pygame.K_RETURN:
                if self.on_confirm:
                    self.on_confirm()
                self.hide()
                return True

        elif event.type == pygame.MOUSEMOTION:
            self.btn_proceed_hover = self.btn_proceed.collidepoint(mouse_pos)
            self.btn_cancel_hover = self.btn_cancel.collidepoint(mouse_pos)

        return False

    def draw(self, surface: Surface):
        if not self.active:
            return

        self._layout()
        pygame.draw.rect(surface, self.bg_color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 2)

        title_surf = self.font_title.render(self.title, True, self.warn_color)
        title_rect = title_surf.get_rect(topleft=(self.rect.x + 20, self.rect.y + 15))
        surface.blit(title_surf, title_rect)

        lines = self._wrap_text(self.message, self.rect.width - 40)
        y = self.rect.y + 50
        for line in lines:
            line_surf = self.font_text.render(line, True, self.text_color)
            surface.blit(line_surf, (self.rect.x + 20, y))
            y += 22

        proceed_color = self.button_hover_color if self.btn_proceed_hover else self.button_color
        cancel_color = self.button_hover_color if self.btn_cancel_hover else (60, 60, 60)

        pygame.draw.rect(surface, cancel_color, self.btn_cancel)
        pygame.draw.rect(surface, proceed_color, self.btn_proceed)

        cancel_text = self.font_btn.render("Cancel", True, self.text_color)
        proceed_text = self.font_btn.render("Proceed", True, self.text_color)

        cancel_text_rect = cancel_text.get_rect(center=self.btn_cancel.center)
        proceed_text_rect = proceed_text.get_rect(center=self.btn_proceed.center)

        surface.blit(cancel_text, cancel_text_rect)
        surface.blit(proceed_text, proceed_text_rect)

    def _wrap_text(self, text: str, max_width: int):
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if self.font_text.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
