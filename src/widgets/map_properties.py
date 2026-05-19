import pygame
from typing import TYPE_CHECKING
from pygame import Rect

from .input import BaseTextInput

if TYPE_CHECKING:
    from editor import Editor


COLOR_BG = (45, 45, 50)
COLOR_BORDER = (80, 80, 80)
COLOR_ACCENT = (60, 100, 160)
COLOR_TEXT = (220, 220, 220)
COLOR_ERROR = (200, 60, 60)


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

        self.btn_save = Rect(self.rect.centerx - 130, self.rect.bottom - 50, 120, 35)
        self.btn_cancel = Rect(self.rect.centerx + 10, self.rect.bottom - 50, 120, 35)
        self.font = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_info = pygame.font.SysFont("Arial", 14)

    def open(self):
        self.render_scale_input.text = str(self.editor.tilemap.render_scale)
        self.render_scale_input.cursor_pos = len(self.render_scale_input.text)
        self.render_scale_input.is_focused = False
        self.error_message = ""
        self.visible = True

    def resize(self, center_rect: Rect):
        self.rect = center_rect
        self.render_scale_input.rect_area = Rect(
            self.rect.x + 20, self.rect.y + 60, self.rect.width - 40, 60
        )
        self.render_scale_input.rect_input = Rect(
            self.render_scale_input.rect_area.x,
            self.render_scale_input.rect_area.y + 20,
            self.render_scale_input.rect_area.width,
            30,
        )
        self.btn_save = Rect(self.rect.centerx - 130, self.rect.bottom - 50, 120, 35)
        self.btn_cancel = Rect(self.rect.centerx + 10, self.rect.bottom - 50, 120, 35)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.btn_save.collidepoint(event.pos):
                    self.submit()
                    return True
                if self.btn_cancel.collidepoint(event.pos):
                    self.visible = False
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

        pygame.draw.rect(screen, COLOR_BG, self.rect, border_radius=8)
        pygame.draw.rect(screen, COLOR_BORDER, self.rect, 2, border_radius=8)

        title = self.font.render("Map Properties", True, COLOR_TEXT)
        screen.blit(title, (self.rect.x + 20, self.rect.y + 15))

        # Show read-only info about tile and map size
        tm = self.editor.tilemap
        info = f"Tile Size: {tm.tile_size[0]}x{tm.tile_size[1]}  |  Map Size: {tm.map_size[0]}x{tm.map_size[1]}"
        info_surf = self.font_info.render(info, True, (150, 150, 150))
        screen.blit(info_surf, (self.rect.x + 20, self.rect.y + 42))

        self.render_scale_input.draw(screen)

        for btn, text, col in [
            (self.btn_save, "Apply", (40, 150, 80)),
            (self.btn_cancel, "Cancel", (150, 60, 60)),
        ]:
            pygame.draw.rect(screen, col, btn, border_radius=4)
            txt_surf = self.font.render(text, True, COLOR_TEXT)
            screen.blit(txt_surf, txt_surf.get_rect(center=btn.center))

        if self.error_message:
            err = pygame.font.SysFont("Arial", 12).render(
                self.error_message, True, COLOR_ERROR
            )
            screen.blit(err, (self.rect.x + 20, self.btn_save.y - 20))
