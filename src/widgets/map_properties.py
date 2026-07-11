import pygame
from typing import TYPE_CHECKING
from pygame import Rect

from .input import BaseTextInput
from .ui.theme import COLORS, FONTS, SHAPE
from .ui.button import Button

if TYPE_CHECKING:
    from editor import Editor


class MapPropertiesDialog:
    def __init__(self, editor: "Editor", center_rect: Rect):
        self.editor = editor
        self.rect = center_rect
        self.visible = False
        self.error_message = ""

        self.render_scale_input = BaseTextInput(
            Rect(self.rect.x + 20, self.rect.y + 60, self.rect.width - 40, 60),
            "Render Scale",
            "render_scale",
            str(editor.tilemap.render_scale),
            allowed_chars="0123456789.",
        )

        self.btn_save = Button(
            Rect(self.rect.centerx - 130, self.rect.bottom - 50, 120, 35),
            "Apply",
            bg=COLORS.success,
            border_radius=SHAPE.radius_sm,
            font=FONTS.get_medium_font(),
            on_click=self.submit,
        )
        self.btn_cancel = Button(
            Rect(self.rect.centerx + 10, self.rect.bottom - 50, 120, 35),
            "Cancel",
            bg=COLORS.danger,
            border_radius=SHAPE.radius_sm,
            font=FONTS.get_medium_font(),
            on_click=lambda: setattr(self, "visible", False),
        )
        self.font = FONTS.get_bold_font(FONTS.size_lg)
        self.font_info = FONTS.get_small_font()

    def open(self):
        self.render_scale_input.text = str(self.editor.tilemap.render_scale)
        self.render_scale_input.cursor_pos = len(self.render_scale_input.text)
        self.render_scale_input.is_focused = False
        self.error_message = ""
        self.visible = True

    def resize(self, center_rect: Rect):
        self.rect = center_rect
        self.render_scale_input.resize(
            Rect(self.rect.x + 20, self.rect.y + 60, self.rect.width - 40, 60)
        )
        self.btn_save.rect = Rect(
            self.rect.centerx - 130, self.rect.bottom - 50, 120, 35
        )
        self.btn_cancel.rect = Rect(
            self.rect.centerx + 10, self.rect.bottom - 50, 120, 35
        )

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        if self.btn_save.handle_event(event):
            return True
        if self.btn_cancel.handle_event(event):
            return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.visible = False
                return True
            if event.key == pygame.K_RETURN:
                self.submit()
                return True

        self.render_scale_input.handle_event(event)
        return True

    def submit(self):
        try:
            raw = self.render_scale_input.text.strip()
            if not raw:
                raise ValueError("Render Scale is required")
            value = float(raw)
            if value <= 0:
                raise ValueError("Render Scale must be greater than 0")
            self.editor.tilemap.render_scale = value
            self.editor.notifications.notify(f"Render Scale set to {value}")
            self.visible = False
        except ValueError as e:
            self.error_message = str(e)

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return

        overlay = pygame.Surface(
            (self.editor.width, self.editor.height), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        pygame.draw.rect(screen, COLORS.panel, self.rect, border_radius=SHAPE.radius)
        pygame.draw.rect(
            screen, COLORS.border, self.rect, SHAPE.border, border_radius=SHAPE.radius
        )

        title = self.font.render("Map Properties", True, COLORS.text)
        screen.blit(title, (self.rect.x + 20, self.rect.y + 15))

        tm = self.editor.tilemap
        info = f"Tile Size: {tm.tile_size[0]}x{tm.tile_size[1]}  |  Map Size: {tm.map_size[0]}x{tm.map_size[1]}"
        info_surf = self.font_info.render(info, True, COLORS.text_dim)
        screen.blit(info_surf, (self.rect.x + 20, self.rect.y + 42))

        self.render_scale_input.draw(screen)

        self.btn_save.draw(screen)
        self.btn_cancel.draw(screen)

        if self.error_message:
            err = FONTS.get_small_font().render(self.error_message, True, COLORS.danger)
            screen.blit(err, (self.rect.x + 20, self.btn_save.rect.y - 20))
