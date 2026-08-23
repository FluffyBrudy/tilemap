
import pygame

from utils.font_manager import FontWeight, font_manager
from widgets.ui.theme import COLORS, FONTS, SHAPE

from .draw_utils import draw_soft_rect


class TooltipManager:
    def __init__(self):
        self.text: str | None = None
        self.pos: tuple[int, int] = (0, 0)
        self.visible = False
        self.font = FONTS.get_small_font()

    def show(self, text: str, pos: tuple[int, int]):
        self.text = text
        self.pos = pos
        self.visible = True

    def hide(self):
        self.visible = False

    def draw(self, surface: pygame.Surface):
        if not self.visible or not self.text:
            return
        text_surf = self.font.render(self.text, True, COLORS.text)
        pad_x, pad_y = 8, 5
        w = text_surf.get_width() + pad_x * 2
        h = text_surf.get_height() + pad_y * 2
        x, y = self.pos

        x = min(max(5, x), surface.get_width() - w - 5)
        y = min(max(5, y), surface.get_height() - h - 5)
        rect = pygame.Rect(x, y, w, h)
        draw_soft_rect(
            surface, rect, COLORS.panel_alt, radius=SHAPE.radius_sm, alpha=230
        )
        pygame.draw.rect(
            surface, COLORS.border_soft, rect, 1, border_radius=SHAPE.radius_sm
        )
        surface.blit(text_surf, (x + pad_x, y + pad_y))
