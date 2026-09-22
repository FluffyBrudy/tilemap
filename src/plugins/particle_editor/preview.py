from __future__ import annotations

import pygame
from pygame import Rect

from widgets.ui.theme import COLORS, FONTS

BACKGROUNDS = ("checker", "dark", "light")
MIN_ZOOM = 0.25
MAX_ZOOM = 4.0


class PreviewCanvas:
    def __init__(self) -> None:
        self.rect = Rect(0, 0, 100, 100)
        self.zoom: float = 1.0
        self.scroll_x: float = 0.0
        self.scroll_y: float = 0.0
        self.bg_mode: str = "checker"
        self.show_bounds: bool = True
        self._panning = False

    def set_rect(self, rect: Rect) -> None:
        self.rect = Rect(rect)

    # camera #

    def world_to_screen(self, wx: float, wy: float) -> tuple[int, int]:
        return (
            int((wx - self.scroll_x) * self.zoom + self.rect.x),
            int((wy - self.scroll_y) * self.zoom + self.rect.y),
        )

    def frame_view(self, area: tuple[float, float, float, float], margin: float = 24.0) -> None:
        _, _, aw, ah = area
        if aw <= 0 or ah <= 0 or self.rect.width <= 0 or self.rect.height <= 0:
            return
        self.zoom = max(
            MIN_ZOOM,
            min(
                MAX_ZOOM,
                min(
                    (self.rect.width - margin * 2) / aw,
                    (self.rect.height - margin * 2) / ah,
                ),
            ),
        )
        ax, ay, _, _ = area
        self.scroll_x = ax + aw / 2 - (self.rect.width / self.zoom) / 2
        self.scroll_y = ay + ah / 2 - (self.rect.height / self.zoom) / 2
        self._panning = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse = pygame.mouse.get_pos()
        if not self.rect.collidepoint(mouse):
            if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
                self._panning = False
            return False
        if event.type == pygame.MOUSEWHEEL:
            old_zoom = self.zoom
            self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom * (1.15**event.y)))
            wx = (mouse[0] - self.rect.x) / old_zoom + self.scroll_x
            wy = (mouse[1] - self.rect.y) / old_zoom + self.scroll_y
            self.scroll_x = wx - (mouse[0] - self.rect.x) / self.zoom
            self.scroll_y = wy - (mouse[1] - self.rect.y) / self.zoom
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            self._panning = True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self._panning = False
            return True
        if event.type == pygame.MOUSEMOTION and self._panning:
            dx, dy = event.rel
            self.scroll_x -= dx / self.zoom
            self.scroll_y -= dy / self.zoom
            return True
        return False

    # draw #

    def _draw_checker(self, screen: pygame.Surface) -> None:
        cell = 16
        base = (38, 38, 46) if self.bg_mode == "checker" else None
        if self.bg_mode == "dark":
            screen.fill((16, 16, 20), self.rect)
            return
        if self.bg_mode == "light":
            screen.fill((210, 210, 215), self.rect)
            return
        assert base is not None
        screen.fill((52, 52, 60), self.rect)
        clip = screen.get_clip()
        screen.set_clip(self.rect)
        x0 = self.rect.x - (self.rect.x % cell)
        y0 = self.rect.y - (self.rect.y % cell)
        x = x0
        toggle_row = ((x0 // cell) + (y0 // cell)) % 2 == 0
        yy = y0
        while yy < self.rect.bottom:
            xx = x
            toggle = toggle_row
            while xx < self.rect.right:
                if toggle:
                    screen.fill(base, (xx, yy, cell, cell))
                toggle = not toggle
                xx += cell
            toggle_row = not toggle_row
            yy += cell
        screen.set_clip(clip)

    def draw_emitter_overlay(
        self,
        screen: pygame.Surface,
        config: dict,
        area: tuple[float, float, float, float],
    ) -> None:
        if not self.show_bounds:
            return

        clip = screen.get_clip()
        screen.set_clip(self.rect)
        try:
            self._draw_emitter_overlay_inner(screen, config, area)
        finally:
            screen.set_clip(clip)

    def _draw_emitter_overlay_inner(
        self,
        screen: pygame.Surface,
        config: dict,
        area: tuple[float, float, float, float],
    ) -> None:
        color = (120, 200, 255)
        ax, ay, aw, ah = area
        shape = str(config.get("emission_shape", "point"))
        if shape == "point":
            cx, cy = self.world_to_screen(ax + aw / 2, ay + ah / 2)
            pygame.draw.line(screen, color, (cx - 8, cy), (cx + 8, cy), 1)
            pygame.draw.line(screen, color, (cx, cy - 8), (cx, cy + 8), 1)
        elif shape == "rect":
            x, y = self.world_to_screen(ax, ay)
            w, h = int(aw * self.zoom), int(ah * self.zoom)
            pygame.draw.rect(screen, color, Rect(x, y, max(1, w), max(1, h)), 1)
        elif shape == "circle":
            cx, cy = self.world_to_screen(ax + aw / 2, ay + ah / 2)
            r = int(min(aw, ah) / 2 * self.zoom)
            if r > 1:
                pygame.draw.circle(screen, color, (cx, cy), r, 1)
        else:
            x1, y1 = self.world_to_screen(ax, ay)
            x2, _ = self.world_to_screen(ax + aw, ay)
            pygame.draw.line(screen, color, (x1, y1), (x2, y1), 2)

    def draw(
        self,
        screen: pygame.Surface,
        sim,
        bg_label_rect: Rect | None = None,
    ) -> None:
        _ = bg_label_rect
        self._draw_checker(screen)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)
        sim.preview.draw(screen, self.scroll_x, self.scroll_y, self.zoom, self.rect)
        self.draw_emitter_overlay(screen, sim.config, sim.area)
        small = FONTS.get_small_font()
        zoom_txt = small.render(f"{int(self.zoom * 100)}%", True, COLORS.text_dim)
        screen.blit(zoom_txt, (self.rect.right - zoom_txt.get_width() - 6, self.rect.y + 4))
