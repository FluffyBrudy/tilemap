import pygame
from pygame import Rect, Surface
from typing import Callable, Optional

from .dialog_base import DialogBase
from .theme import COLORS, FONTS


class ConfirmDialog(DialogBase):
    def __init__(self, editor_rect: Rect):
        super().__init__(editor_rect, (420, 180))
        self.message = ""
        self.on_confirm: Optional[Callable[[], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        self.btn_proceed = Rect(0, 0, 110, 30)
        self.btn_cancel = Rect(0, 0, 110, 30)
        self.btn_proceed_hover = False
        self.btn_cancel_hover = False
        self._layout()

    def _layout(self):
        self.rect.center = self.editor_rect.center
        self._update_content_rect()
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

        if self.handle_event_base(event):
            return True

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
            if event.key == pygame.K_RETURN:
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
        super().draw_base(surface)

        self._draw_title(surface, color=COLORS.warning)

        lines = self._wrap_text(self.message, self.rect.width - 40)
        y = self.rect.y + 50
        for line in lines:
            line_surf = FONTS.get_medium_font().render(line, True, COLORS.text)
            surface.blit(line_surf, (self.rect.x + 20, y))
            y += 22

        btn_font = FONTS.get_bold_font()
        self._draw_button(
            surface, self.btn_proceed, self.btn_proceed_hover, "Proceed", font=btn_font
        )
        self._draw_button(
            surface,
            self.btn_cancel,
            self.btn_cancel_hover,
            "Cancel",
            color=COLORS.panel_alt,
            font=btn_font,
        )

    def _wrap_text(self, text: str, max_width: int):
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if FONTS.get_medium_font().size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
