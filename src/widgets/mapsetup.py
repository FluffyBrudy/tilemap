from typing import TYPE_CHECKING

import pygame
from pygame import Rect

from .input import DigitInput
from .ui.button import Button
from .ui.theme import COLORS, FONTS, SPACING
from .widget_base import WidgetBase

if TYPE_CHECKING:
    from editor import Editor


TITLE_H = 30
CELL_H = 70
INPUT_H = 60
BTN_W = 120
BTN_H = 35


class MapSetup(WidgetBase):
    def __init__(self, editor: "Editor", center_rect: Rect):
        super().__init__(center_rect, padding=20, border_width=1)
        self.editor = editor
        self.visible = True
        self.error_message = ""

        self.font = FONTS.get_title_font()
        self.font_sm = FONTS.get_medium_font()

        self.inputs: list[DigitInput] = []
        fields = [
            ("Map Width", "map_w", "30"),
            ("Map Height", "map_h", "20"),
            ("Tile Width", "tile_w", "32"),
            ("Tile Height", "tile_h", "32"),
        ]

        for i, (lbl, key, default) in enumerate(fields):
            self.inputs.append(
                DigitInput(Rect(0, 0, 0, 0), lbl, key, default, tab_index=i)
            )

        self.btn_create = Button(
            Rect(0, 0, BTN_W, BTN_H),
            "Create",
            accent=True,
            font=self.font,
            on_click=self.submit,
        )
        self.btn_open = Button(
            Rect(0, 0, BTN_W, BTN_H),
            "Open map",
            accent=True,
            font=self.font_sm,
            on_click=self._open_map,
        )

        self._relayout()

    def _relayout(self):
        cols = 2
        cell_w = self.content_rect.width // cols
        start_x = self.content_rect.x
        start_y = self.content_rect.y + TITLE_H + SPACING["md"]

        for i, inp in enumerate(self.inputs):
            row, col = divmod(i, cols)
            r = Rect(
                start_x + col * cell_w,
                start_y + row * CELL_H,
                cell_w - SPACING["sm"],
                INPUT_H,
            )
            inp.resize(r)

        rows = (len(self.inputs) + cols - 1) // cols
        last_input_bottom = start_y + (rows - 1) * CELL_H + INPUT_H

        cx = self.rect.centerx
        btn_create_y = last_input_bottom + SPACING["xl"]
        self.btn_create.rect = Rect(cx - BTN_W // 2, btn_create_y, BTN_W, BTN_H)
        or_h = self.font_sm.render("─ OR ─", True, COLORS.text_dim).get_height()
        btn_open_y = btn_create_y + BTN_H + SPACING["md"] + or_h + SPACING["md"]
        self.btn_open.rect = Rect(cx - BTN_W // 2, btn_open_y, BTN_W, BTN_H)

    def resize(self, center_rect: Rect):
        super().resize(center_rect.x, center_rect.y, center_rect.w, center_rect.h)
        self._relayout()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.visible = False
            return True

        if self.btn_create.handle_event(event):
            return True
        if self.btn_open.handle_event(event):
            return True

        if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
            focused = [i for i in self.inputs if i.is_focused]
            shift_held = pygame.key.get_mods() & pygame.KMOD_SHIFT

            if focused:
                current_idx = focused[0].tab_index
                if shift_held:
                    next_idx = (current_idx - 1) % len(self.inputs)
                else:
                    next_idx = (current_idx + 1) % len(self.inputs)
            else:
                next_idx = 0 if not shift_held else len(self.inputs) - 1

            for o in self.inputs:
                o.is_focused = False
            self.inputs[next_idx].is_focused = True
            self.inputs[next_idx].cursor_pos = len(self.inputs[next_idx].text)
            self.inputs[next_idx].selection_start = None
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

    def _open_map(self):
        self.visible = False
        self.editor.perform_load()

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return

        self.draw_base(screen)

        title = self.font.render("Project Setup", True, COLORS.text)
        screen.blit(title, (self.content_rect.x, self.content_rect.y))

        for inp in self.inputs:
            inp.draw(screen)

        self.btn_create.draw(screen)

        or_surf = self.font_sm.render("─ OR ─", True, COLORS.text_dim)
        or_center_y = (
            self.btn_create.rect.bottom
            + (self.btn_open.rect.top - self.btn_create.rect.bottom) // 2
        )
        or_rect = or_surf.get_rect(center=(self.rect.centerx, or_center_y))
        screen.blit(or_surf, or_rect)

        self.btn_open.draw(screen)

        if self.error_message:
            err = FONTS.get_font(12).render(self.error_message, True, COLORS.danger)
            screen.blit(err, (self.content_rect.x, self.btn_create.rect.y - 20))
