import pygame
from typing import Tuple

from .theme import COLORS, SHAPE


def draw_panel(surface: pygame.Surface, rect: pygame.Rect, bg=None, border=None, radius=None, border_width=None):
    bg = bg if bg is not None else COLORS.panel
    border = border if border is not None else COLORS.border
    radius = SHAPE.radius if radius is None else radius
    border_width = SHAPE.border if border_width is None else border_width
    pygame.draw.rect(surface, bg, rect, border_radius=radius)
    if border_width > 0:
        pygame.draw.rect(surface, border, rect, border_width, border_radius=radius)


def draw_button(surface: pygame.Surface, rect: pygame.Rect, label_surf: pygame.Surface, *, active=False, hover=False, accent=False):
    if accent or active:
        bg = COLORS.accent_active if active else COLORS.accent
        if hover:
            bg = COLORS.accent_hover
        border = COLORS.border_soft
        text_col = COLORS.text
    else:
        bg = COLORS.header if hover else COLORS.panel_alt
        border = COLORS.border_soft
        text_col = COLORS.text

    pygame.draw.rect(surface, bg, rect, border_radius=SHAPE.radius_sm)
    pygame.draw.rect(surface, border, rect, 1, border_radius=SHAPE.radius_sm)
    surface.blit(label_surf, label_surf.get_rect(center=rect.center))
    return text_col


def draw_separator(surface: pygame.Surface, x: int, y: int, h: int, color=None):
    color = color if color is not None else COLORS.border_soft
    pygame.draw.line(surface, color, (x, y), (x, y + h))


def truncate_text(text: str, font: pygame.font.Font, max_width: int) -> Tuple[str, bool]:
    if font.size(text)[0] <= max_width:
        return text, False
    ellipsis = "..."
    ellipsis_w = font.size(ellipsis)[0]
    available = max_width - ellipsis_w
    while text and font.size(text)[0] > available:
        text = text[:-1].rstrip()
    return text + ellipsis, True


def draw_soft_rect(surface: pygame.Surface, rect: pygame.Rect, color: Tuple[int, int, int], radius=4, alpha=255):
    if alpha >= 255:
        pygame.draw.rect(surface, color, rect, border_radius=radius)
        return
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    s.fill((*color, alpha))
    pygame.draw.rect(s, (*color, alpha), s.get_rect(), border_radius=radius)
    surface.blit(s, rect.topleft)
