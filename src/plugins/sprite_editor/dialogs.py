from __future__ import annotations

import pygame
from pygame import Rect, Surface

from widgets.input import InputBox
from widgets.ui.dialog_base import DialogBase
from widgets.ui.theme import COLORS, FONTS


class ScaleDialog(DialogBase):
    def __init__(self, editor_rect: Rect):
        super().__init__(editor_rect, (320, 180), "Scale Spritesheet")
        self._input = InputBox(
            Rect(0, 0, 200, 30),
            font=FONTS.get_font(18),
            allowed_chars="0123456789.",
        )
        self._input.text = "1.0"
        self._input.is_focused = True
        self._ok_btn = Rect(0, 0, 80, 30)
        self._cancel_btn = Rect(0, 0, 80, 30)
        self._hover_ok = False
        self._hover_cancel = False

        self._on_apply_cb = None

    def show_scale(self, *, on_apply=None):
        self._on_apply_cb = on_apply
        self._input.text = "1.0"
        self._input.is_focused = True
        self.show(
            on_confirm=lambda: self._apply(),
            on_cancel=self.hide,
        )

    def _apply(self):
        try:
            factor = float(self._input.text)
            if factor <= 0:
                return
            if self._on_apply_cb:
                self._on_apply_cb(factor)
            self.hide()
        except ValueError:
            pass

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False
        if self.handle_event_base(event):
            return True
        if self._input.handle_event(event):
            return True
        if event.type == pygame.MOUSEMOTION:
            self._hover_ok = self._ok_btn.collidepoint(event.pos)
            self._hover_cancel = self._cancel_btn.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._ok_btn.collidepoint(event.pos):
                self._apply()
                return True
            if self._cancel_btn.collidepoint(event.pos):
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._apply()
            return True
        return False

    def draw(self, screen: Surface):
        if not self.active:
            return
        self.draw_base(screen)
        self._draw_title(screen)

        cx = self.rect.centerx
        input_x = cx - 100
        input_y = self.rect.y + 60
        self._input.rect.topleft = (input_x, input_y)
        self._input.draw(screen)

        lbl = FONTS.get_small_font().render("Scale factor", True, COLORS.text_dim)
        screen.blit(lbl, (input_x, input_y - 18))

        ok_x = cx - 90
        btn_y = self.rect.y + 120
        self._ok_btn.topleft = (ok_x, btn_y)
        self._cancel_btn.topleft = (ok_x + 100, btn_y)
        self._draw_button(screen, self._ok_btn, self._hover_ok, "OK")
        self._draw_button(
            screen, self._cancel_btn, self._hover_cancel, "Cancel", color=COLORS.panel_alt, hover_color=COLORS.hover
        )


class GridSizeDialog(DialogBase):
    def __init__(self, editor_rect: Rect):
        super().__init__(editor_rect, (360, 220), "Tile Size")
        self._width_input = InputBox(
            Rect(0, 0, 80, 30),
            font=FONTS.get_font(18),
            allowed_chars="0123456789",
        )
        self._width_input.text = "32"
        self._height_input = InputBox(
            Rect(0, 0, 80, 30),
            font=FONTS.get_font(18),
            allowed_chars="0123456789",
        )
        self._height_input.text = "32"
        self._width_input.is_focused = True
        self._ok_btn = Rect(0, 0, 80, 30)
        self._cancel_btn = Rect(0, 0, 80, 30)
        self._hover_ok = False
        self._hover_cancel = False

        self._on_apply_cb = None

    def show_grid(self, *, on_apply=None, current_size=(32, 32)):
        self._on_apply_cb = on_apply
        self._width_input.text = str(current_size[0])
        self._height_input.text = str(current_size[1])
        self._width_input.is_focused = True
        self.show(
            on_confirm=lambda: self._apply(),
            on_cancel=self.hide,
        )

    def _apply(self):
        try:
            tw = int(self._width_input.text)
            th = int(self._height_input.text)
            if tw < 1 or th < 1:
                return
            if self._on_apply_cb:
                self._on_apply_cb(tw, th)
            self.hide()
        except ValueError:
            pass

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False
        if self.handle_event_base(event):
            return True
        if self._width_input.handle_event(event):
            return True
        if self._height_input.handle_event(event):
            return True
        if event.type == pygame.MOUSEMOTION:
            self._hover_ok = self._ok_btn.collidepoint(event.pos)
            self._hover_cancel = self._cancel_btn.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._ok_btn.collidepoint(event.pos):
                self._apply()
                return True
            if self._cancel_btn.collidepoint(event.pos):
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self._apply()
            return True
        return False

    def draw(self, screen: Surface):
        if not self.active:
            return
        self.draw_base(screen)
        self._draw_title(screen)

        cx = self.rect.centerx
        font_sm = FONTS.get_small_font()

        w_x = cx - 100
        h_x = cx + 20
        input_y = self.rect.y + 60

        self._width_input.rect.topleft = (w_x, input_y)
        self._height_input.rect.topleft = (h_x, input_y)

        screen.blit(font_sm.render("Width", True, COLORS.text_dim), (w_x, input_y - 18))
        screen.blit(font_sm.render("Height", True, COLORS.text_dim), (h_x, input_y - 18))

        self._width_input.draw(screen)
        self._height_input.draw(screen)

        ok_x = cx - 90
        btn_y = self.rect.y + 130
        self._ok_btn.topleft = (ok_x, btn_y)
        self._cancel_btn.topleft = (ok_x + 100, btn_y)
        self._draw_button(screen, self._ok_btn, self._hover_ok, "OK")
        self._draw_button(
            screen, self._cancel_btn, self._hover_cancel, "Cancel", color=COLORS.panel_alt, hover_color=COLORS.hover
        )
