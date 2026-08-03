"""Drawing helpers for overlays (selection fill, ghost, handles, regions).

Pure drawing was done on the target screen surface; never mutates the
document. Coordinate conversion happens through the camera only.
"""

from __future__ import annotations

from collections.abc import Iterable

import pygame
from pygame import Rect, Surface

from widgets.ui.theme import COLORS, FONTS

from .camera import Camera
from .document import Document, Region
from .selection import Selection

CANVAS_BG = COLORS.bg


def draw_alpha_fill(screen: Surface, rect: Rect, color: tuple[int, int, int], alpha: int) -> None:
    overlay = Surface((max(1, rect.w), max(1, rect.h)), pygame.SRCALPHA)
    overlay.fill((*color, alpha))
    screen.blit(overlay, rect.topleft)


def draw_dashed_border(
    screen: Surface,
    rect: Rect,
    color: tuple[int, int, int],
    dash: int = 4,
    width: int = 1,
) -> None:
    x1, y1 = rect.topleft
    x2, y2 = rect.bottomright
    # top / bottom
    for cx in range(x1, x2, dash * 2):
        pygame.draw.line(screen, color, (cx, y1), (min(cx + dash, x2), y1), width)
        pygame.draw.line(screen, color, (cx, y2 - 1), (min(cx + dash, x2), y2 - 1), width)
    for cy in range(y1, y2, dash * 2):
        pygame.draw.line(screen, color, (x1, cy), (x1, min(cy + dash, y2)), width)
        pygame.draw.line(screen, color, (x2 - 1, cy), (x2 - 1, min(cy + dash, y2)), width)


def ghost_tiles(
    screen: Surface,
    placements: Iterable[tuple[int, int, Surface]],
    doc: Document,
    camera: Camera,
    alpha: int = 160,
) -> None:
    """Blit tile ghosts at (col, row, surface) placements, scaled to zoom."""
    for col, row, tile in placements:
        rect = doc.tile_rect(col, row)
        sx, sy, sw, sh = camera.world_to_screen_rect(rect.x, rect.y, rect.w, rect.h)
        if sw <= 0 or sh <= 0:
            continue
        scaled = pygame.transform.scale(tile, (max(1, round(sw)), max(1, round(sh))))
        scaled.set_alpha(alpha)
        screen.blit(scaled, (round(sx), round(sy)))


def screen_rect_for(camera: Camera, x: float, y: float, w: float, h: float) -> Rect:
    sx, sy, sw, sh = camera.world_to_screen_rect(x, y, w, h)
    return Rect(round(sx), round(sy), round(sw), round(sh))


def draw_selection_fill(screen: Surface, doc: Document, camera: Camera, selection: Selection) -> None:
    for col, row in sorted(selection.cells):
        if not doc.is_valid_cell(col, row):
            continue
        rect = doc.tile_rect(col, row)
        draw_alpha_fill(screen, screen_rect_for(camera, rect.x, rect.y, rect.w, rect.h), (80, 120, 200), 60)


def draw_region_shape(
    screen: Surface,
    camera: Camera,
    region: Region,
    *,
    selected: bool = False,
    hovered: bool = False,
    accent: tuple[int, int, int] = (220, 180, 80),
    fill_alpha: int = 28,
) -> None:
    rect = screen_rect_for(camera, region.x, region.y, region.w, region.h)
    if rect.w < 1 or rect.h < 1:
        return
    draw_alpha_fill(screen, rect, accent if selected else (150, 150, 150), fill_alpha)
    border_color = accent if (selected or hovered) else (200, 200, 200)
    pygame.draw.rect(screen, border_color, rect, 2 if selected else 1)
    if region.name:
        font = FONTS.get_small_font()
        label = font.render(region.name, True, COLORS.text)
        lx = rect.x + 4
        ly = rect.y + 4
        if rect.x + rect.w - label.get_width() > screen.get_width():
            lx = rect.right - label.get_width() - 4
        pygame.draw.rect(screen, COLORS.panel, (lx - 2, ly - 1, label.get_width() + 4, label.get_height() + 2))
        screen.blit(label, (lx, ly))


HANDLES = (
    ("tl", -1, -1),
    ("t", 0, -1),
    ("tr", 1, -1),
    ("l", -1, 0),
    ("r", 1, 0),
    ("bl", -1, 1),
    ("b", 0, 1),
    ("br", 1, 1),
)


def draw_handles(
    screen: Surface,
    rect: Rect,
    color: tuple[int, int, int],
    handle_size: int = 8,
    hover: str | None = None,
) -> None:
    for name, hx, hy in HANDLES:
        cx = rect.centerx if hx == 0 else (rect.x if hx == -1 else rect.right)
        cy = rect.centery if hy == 0 else (rect.y if hy == -1 else rect.bottom)
        hr = Rect(cx - handle_size // 2, cy - handle_size // 2, handle_size, handle_size)
        pygame.draw.rect(screen, color if name != hover else (255, 255, 255), hr)


def handle_at(rect: Rect, pos: tuple[int, int], handle_size: int = 8) -> str | None:
    """Return the handle id under a screen point, or None.

    Uses an inclusive distance check (not Rect.collidepoint) so points on the
    exact half-size boundary still hit.
    """
    half = max(1, handle_size // 2)
    for name, hx, hy in HANDLES:
        x = rect.centerx if hx == 0 else (rect.x if hx == -1 else rect.right)
        y = rect.centery if hy == 0 else (rect.y if hy == -1 else rect.bottom)
        if abs(pos[0] - x) <= half and abs(pos[1] - y) <= half:
            return name
    return None


def cursor_for_handle(name: str | None) -> str:
    if name in ("w", "e"):
        return "sizeew"
    if name in ("n", "s"):
        return "sizens"
    if name in ("nw", "se"):
        return "sizenwse"
    if name in ("ne", "sw"):
        return "sizenesw"
    return "arrow"
