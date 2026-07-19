"""
Collision Painter — Godot-like polygon drawing/erasing for tile collision shapes.

Features:
- Click to add polygon vertices
- Right-click or Enter to complete polygon
- Escape to cancel current polygon
- Click on existing polygon to select it
- Delete key to remove selected polygon
- Visual feedback with semi-transparent overlays
- Grid snapping (optional)
"""

from __future__ import annotations

import math
from collections.abc import Callable
from enum import Enum

import pygame
from pygame import Rect

from utils.font_manager import FontWeight, font_manager
from utils.icon_manager import icon_manager
from widgets.ui.theme import COLORS


class PaintMode(Enum):
    """Collision painter modes"""

    DRAW = "draw"
    ERASE = "erase"
    SELECT = "select"


_COLORS = {
    "bg": (25, 27, 30),
    "grid": (255, 255, 255),
    "polygon_fill": (80, 180, 255),
    "polygon_stroke": (100, 200, 255),
    "polygon_selected": (255, 180, 80),
    "vertex": (255, 255, 255),
    "vertex_hover": (255, 220, 80),
    "vertex_first": (80, 255, 120),
    "preview_line": (200, 200, 200),
    "text": (230, 230, 230),
    "text_dim": (140, 140, 140),
    "header": (40, 42, 46),
    "border": (60, 62, 65),
    "border_soft": (80, 82, 85),
    "accent": (80, 180, 255),
    "one_way": (255, 120, 120),
    "edge_mode": (120, 255, 120),
    "help_bg": (15, 17, 20),
}


VERTEX_RADIUS = 5
VERTEX_HOVER_RADIUS = 7
SNAP_THRESHOLD = 10


HELP_PANEL_WIDTH = 360
HELP_PANEL_HEIGHT = 450
HELP_SCROLL_SPEED = 30
HELP_SCROLLBAR_WIDTH = 12
HELP_CONTENT_PADDING = 10
HELP_CLOSE_BTN_SIZE = 20
HELP_TITLE_HEIGHT = 40
HELP_FOOTER_HEIGHT = 30
HELP_SCROLL_MARGIN = 80
HELP_THUMB_MIN_HEIGHT = 30


INFO_BTN_SIZE = 28
INFO_BTN_OFFSET_X = 36
INFO_BTN_OFFSET_Y = 8


class CollisionPainter:
    """Godot-like collision polygon painter for a single tile."""

    def __init__(
        self,
        rect: Rect,
        tile_surface: pygame.Surface,
        tile_size: tuple[int, int],
    ):
        self.rect = rect
        self.tile_surface = tile_surface
        self.tile_size = tile_size

        self.polygons: list[list[tuple[float, float]]] = []
        self.polygon_one_way: list[bool] = []

        self.mode = PaintMode.DRAW
        self.current_polygon: list[tuple[float, float]] = []
        self.selected_polygon_idx: int | None = None
        self.selected_vertex_idx: int | None = None

        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self.zoom: float = 2.0

        self.hover_vertex: tuple[int, int] | None = None
        self.hover_polygon_idx: int | None = None
        self.mouse_pos: tuple[int, int] = (0, 0)
        self._panning = False
        self._pan_start = (0, 0)
        self._pan_start_offset = (0.0, 0.0)
        self._dragging_vertex = False

        self.snap_to_grid = False
        self.grid_size = 8
        self.show_grid = True
        self.show_angle_hints = False
        self.edge_draw_mode = False
        self._edge_start: tuple[int, int] | None = None
        self._shift_held = False

        self.show_help = False
        self._help_rect = Rect(
            rect.x + (rect.w - HELP_PANEL_WIDTH) // 2,
            rect.y + (rect.h - HELP_PANEL_HEIGHT) // 2,
            HELP_PANEL_WIDTH,
            HELP_PANEL_HEIGHT,
        )
        self._help_scroll = 0
        self._help_content_height = 0
        self._help_scrolling = False
        self._help_scroll_start = 0
        self._help_scroll_start_y = 0

        self._info_button_rect = Rect(
            rect.right - INFO_BTN_OFFSET_X,
            rect.y + INFO_BTN_OFFSET_Y,
            INFO_BTN_SIZE,
            INFO_BTN_SIZE,
        )

        self.on_polygon_added: Callable[[list[tuple[float, float]]], None] | None = (
            None
        )
        self.on_polygon_removed: Callable[[int], None] | None = None
        self.on_polygon_modified: Callable[[int], None] | None = None

        self._font: pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

        self._center_view()

    def _center_view(self) -> None:
        """Center the tile in the viewport"""
        tw, th = self.tile_size
        self.offset_x = (self.rect.w - tw * self.zoom) / 2
        self.offset_y = (self.rect.h - th * self.zoom) / 2

    def _ensure_fonts(self) -> None:
        """Initialize fonts"""
        if self._font is None:
            self._font = font_manager.get_font("Arial", 13, FontWeight.REGULAR)
        if self._font_sm is None:
            self._font_sm = font_manager.get_font("Arial", 11, FontWeight.REGULAR)

    def _screen_to_tile(self, screen_pos: tuple[int, int]) -> tuple[float, float]:
        """Convert screen coordinates to tile-local coordinates"""
        x = (screen_pos[0] - self.rect.x - self.offset_x) / self.zoom
        y = (screen_pos[1] - self.rect.y - self.offset_y) / self.zoom
        return (x, y)

    def _tile_to_screen(self, tile_pos: tuple[float, float]) -> tuple[int, int]:
        """Convert tile-local coordinates to screen coordinates"""
        x = int(self.rect.x + self.offset_x + tile_pos[0] * self.zoom)
        y = int(self.rect.y + self.offset_y + tile_pos[1] * self.zoom)
        return (x, y)

    def _snap_to_grid(self, pos: tuple[float, float]) -> tuple[float, float]:
        """Snap position to grid if enabled"""
        if not self.snap_to_grid:
            return pos
        x = round(pos[0] / self.grid_size) * self.grid_size
        y = round(pos[1] / self.grid_size) * self.grid_size
        return (x, y)

    def _find_vertex_at(self, screen_pos: tuple[int, int]) -> tuple[int, int] | None:
        """Find vertex at screen position, returns (polygon_idx, vertex_idx) or None"""
        for poly_idx, polygon in enumerate(self.polygons):
            for vert_idx, vertex in enumerate(polygon):
                screen_vert = self._tile_to_screen(vertex)
                dist = math.hypot(
                    screen_pos[0] - screen_vert[0], screen_pos[1] - screen_vert[1]
                )
                if dist <= VERTEX_HOVER_RADIUS:
                    return (poly_idx, vert_idx)
        return None

    def _find_polygon_at(self, screen_pos: tuple[int, int]) -> int | None:
        """Find polygon containing the screen position"""
        tile_pos = self._screen_to_tile(screen_pos)

        for poly_idx, polygon in enumerate(self.polygons):
            if len(polygon) < 3:
                continue
            if self._point_in_polygon(tile_pos, polygon):
                return poly_idx
        return None

    def _point_in_polygon(
        self, point: tuple[float, float], polygon: list[tuple[float, float]]
    ) -> bool:
        """Check if point is inside polygon using ray casting"""
        if len(polygon) < 3:
            return False

        x, y = point
        inside = False

        j = len(polygon) - 1
        for i in range(len(polygon)):
            xi, yi = polygon[i]
            xj, yj = polygon[j]

            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside

            j = i

        return inside

    def resize(self, rect: Rect) -> None:
        """Update rect and recenter view"""
        self.rect = rect
        self._center_view()

        self._help_rect = Rect(
            self.rect.x + (self.rect.w - HELP_PANEL_WIDTH) // 2,
            self.rect.y + (self.rect.h - HELP_PANEL_HEIGHT) // 2,
            HELP_PANEL_WIDTH,
            HELP_PANEL_HEIGHT,
        )

        self._info_button_rect = Rect(
            self.rect.right - INFO_BTN_OFFSET_X,
            self.rect.y + INFO_BTN_OFFSET_Y,
            INFO_BTN_SIZE,
            INFO_BTN_SIZE,
        )

    def set_polygons(
        self,
        polygons: list[list[tuple[float, float]]],
        one_way_flags: list[bool] | None = None,
    ) -> None:
        """Load existing polygons"""
        self.polygons = [list(p) for p in polygons]
        if one_way_flags:
            self.polygon_one_way = list(one_way_flags)
        else:
            self.polygon_one_way = [False] * len(polygons)
        self.current_polygon = []
        self.selected_polygon_idx = None

    def get_polygons(self) -> list[list[tuple[float, float]]]:
        """Get all completed polygons"""
        return [list(p) for p in self.polygons]

    def get_one_way_flags(self) -> list[bool]:
        """Get one-way collision flags for all polygons"""
        return list(self.polygon_one_way)

    def toggle_one_way(self) -> None:
        """Toggle one-way flag on the selected polygon"""
        idx = self.selected_polygon_idx
        if idx is not None and 0 <= idx < len(self.polygon_one_way):
            self.polygon_one_way[idx] = not self.polygon_one_way[idx]
            if self.on_polygon_modified:
                self.on_polygon_modified(idx)

    def _get_interior_angle(
        self, polygon: list[tuple[float, float]], idx: int
    ) -> float:
        """Compute interior angle (degrees) at polygon vertex idx."""
        n = len(polygon)
        if n < 3:
            return 0.0
        prev = polygon[(idx - 1) % n]
        curr = polygon[idx]
        nxt = polygon[(idx + 1) % n]
        v1 = (prev[0] - curr[0], prev[1] - curr[1])
        v2 = (nxt[0] - curr[0], nxt[1] - curr[1])
        dot = v1[0] * v2[0] + v1[1] * v2[1]
        mag1 = math.hypot(v1[0], v1[1])
        mag2 = math.hypot(v2[0], v2[1])
        if mag1 < 0.001 or mag2 < 0.001:
            return 0.0
        cos_a = max(-1.0, min(1.0, dot / (mag1 * mag2)))
        return math.degrees(math.acos(cos_a))

    def _draw_angle_hint(
        self,
        screen: pygame.Surface,
        screen_pos: tuple[int, int],
        angle_deg: float,
    ) -> None:
        """Draw a small arc + angle text at a vertex."""
        if angle_deg <= 0.5 or angle_deg >= 179.5:
            return
        arc_radius = 14
        segments = max(4, int(angle_deg / 10))
        angle_rad = math.radians(angle_deg)
        pts = [screen_pos]
        for i in range(segments + 1):
            t = -angle_rad * i / segments
            pts.append(
                (
                    screen_pos[0] + arc_radius * math.cos(t),
                    screen_pos[1] + arc_radius * math.sin(t),
                )
            )
        if len(pts) >= 3:
            wedge = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            pygame.draw.polygon(wedge, (*_COLORS["polygon_fill"], 60), pts)
            screen.blit(wedge, self.rect.topleft)
        label = self._font_sm.render(f"{angle_deg:.0f}°", True, _COLORS["text"])
        label_x = screen_pos[0] + 10
        label_y = screen_pos[1] - label.get_height() - 4
        bg = pygame.Surface(
            (label.get_width() + 4, label.get_height() + 2), pygame.SRCALPHA
        )
        bg.fill((0, 0, 0, 180))
        screen.blit(bg, (label_x - 2, label_y - 1))
        screen.blit(label, (label_x, label_y))

    def clear_all(self) -> None:
        """Clear all polygons"""
        self.polygons = []
        self.polygon_one_way = []
        self.current_polygon = []
        self.selected_polygon_idx = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle input events"""
        mouse = pygame.mouse.get_pos()
        self.mouse_pos = mouse

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.show_help:
                self.show_help = False
                return True
            return False

        if self.show_help:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                close_btn = Rect(
                    self._help_rect.right - HELP_CLOSE_BTN_SIZE - HELP_CONTENT_PADDING,
                    self._help_rect.y + HELP_CONTENT_PADDING,
                    HELP_CLOSE_BTN_SIZE,
                    HELP_CLOSE_BTN_SIZE,
                )
                if close_btn.collidepoint(mouse):
                    self.show_help = False
                    self._help_scroll = 0
                    return True

                if self._help_rect.collidepoint(mouse):
                    if mouse[0] > self._help_rect.right - HELP_SCROLLBAR_WIDTH:
                        self._help_scrolling = True
                        self._help_scroll_start = self._help_scroll
                        self._help_scroll_start_y = mouse[1]
                        return True
                    return True

                self.show_help = False
                self._help_scroll = 0
                return True

            if event.type == pygame.MOUSEBUTTONUP and self._help_scrolling:
                self._help_scrolling = False
                return True

            if event.type == pygame.MOUSEMOTION and self._help_scrolling:
                dy = mouse[1] - self._help_scroll_start_y
                self._help_scroll = self._help_scroll_start + dy * 2
                self._help_scroll = max(
                    0,
                    min(
                        self._help_scroll,
                        max(
                            0,
                            self._help_content_height
                            - self._help_rect.h
                            + HELP_SCROLL_MARGIN,
                        ),
                    ),
                )
                return True

            if event.type == pygame.MOUSEWHEEL:
                if self._help_rect.collidepoint(mouse) or (
                    self._help_rect.right - HELP_SCROLLBAR_WIDTH
                    < mouse[0]
                    < self._help_rect.right
                ):
                    self._help_scroll -= event.y * HELP_SCROLL_SPEED
                    self._help_scroll = max(
                        0,
                        min(
                            self._help_scroll,
                            max(
                                0,
                                self._help_content_height
                                - self._help_rect.h
                                + HELP_SCROLL_MARGIN,
                            ),
                        ),
                    )
                    return True

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.show_help = False
                return True

            return False

        if not self.rect.collidepoint(mouse) and event.type not in (
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
        ):
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            if self.rect.collidepoint(mouse):
                self._panning = True
                self._pan_start = mouse
                self._pan_start_offset = (self.offset_x, self.offset_y)
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            if self._panning:
                self._panning = False
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._info_button_rect.collidepoint(mouse):
                self.show_help = not self.show_help
                return True

        if event.type == pygame.MOUSEMOTION:
            if self._panning:
                dx = mouse[0] - self._pan_start[0]
                dy = mouse[1] - self._pan_start[1]
                self.offset_x = self._pan_start_offset[0] + dx
                self.offset_y = self._pan_start_offset[1] + dy
                return True

            if self.rect.collidepoint(mouse):
                self.hover_vertex = self._find_vertex_at(mouse)
                if not self.hover_vertex:
                    self.hover_polygon_idx = self._find_polygon_at(mouse)
                else:
                    self.hover_polygon_idx = None

                if self._dragging_vertex and self.selected_vertex_idx is not None:
                    poly_idx, vert_idx = self.selected_vertex_idx
                    tile_pos = self._screen_to_tile(mouse)
                    tile_pos = self._snap_to_grid(tile_pos)

                    tw, th = self.tile_size
                    tile_pos = (
                        max(0, min(tw, tile_pos[0])),
                        max(0, min(th, tile_pos[1])),
                    )
                    self.polygons[poly_idx][vert_idx] = tile_pos
                    if self.on_polygon_modified:
                        self.on_polygon_modified(poly_idx)
                    return True

        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(mouse):
            self.zoom *= 1.15 if event.y > 0 else 0.87
            self.zoom = max(0.5, min(self.zoom, 8.0))

            tile_pos = self._screen_to_tile(mouse)
            self.offset_x = mouse[0] - self.rect.x - tile_pos[0] * self.zoom
            self.offset_y = mouse[1] - self.rect.y - tile_pos[1] * self.zoom
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse):
                vertex_hit = self._find_vertex_at(mouse)
                if vertex_hit:
                    poly_idx, vert_idx = vertex_hit
                    self.selected_polygon_idx = poly_idx
                    self.selected_vertex_idx = vertex_hit
                    self._dragging_vertex = True
                    return True

                poly_hit = self._find_polygon_at(mouse)
                if poly_hit is not None:
                    self.selected_polygon_idx = poly_hit
                    self.selected_vertex_idx = None
                    return True

                if self.mode == PaintMode.DRAW:
                    tile_pos = self._screen_to_tile(mouse)

                    if (
                        self.edge_draw_mode
                        and self._shift_held
                        and len(self.current_polygon) > 0
                    ):
                        start = self.current_polygon[-1]
                        dx = tile_pos[0] - start[0]
                        dy = tile_pos[1] - start[1]

                        if abs(dx) > abs(dy):
                            tile_pos = (tile_pos[0], start[1])
                        else:
                            tile_pos = (start[0], tile_pos[1])

                    tile_pos = self._snap_to_grid(tile_pos)

                    tw, th = self.tile_size
                    tile_pos = (
                        max(0, min(tw, tile_pos[0])),
                        max(0, min(th, tile_pos[1])),
                    )

                    if len(self.current_polygon) >= 3:
                        first_screen = self._tile_to_screen(self.current_polygon[0])
                        dist = math.hypot(
                            mouse[0] - first_screen[0], mouse[1] - first_screen[1]
                        )
                        if dist <= SNAP_THRESHOLD:
                            self._complete_polygon()
                            return True

                    self.current_polygon.append(tile_pos)
                    return True

                self.selected_polygon_idx = None
                self.selected_vertex_idx = None
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging_vertex:
                self._dragging_vertex = False
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.rect.collidepoint(mouse):
                if len(self.current_polygon) >= 3:
                    self._complete_polygon()
                    return True
                if self.current_polygon:
                    self.current_polygon = []
                    return True

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA)

            if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                self._shift_held = True

            elif ctrl and event.key == pygame.K_e:
                self.edge_draw_mode = not self.edge_draw_mode
                if not self.edge_draw_mode:
                    self._edge_start = None
                return True

            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if len(self.current_polygon) >= 3:
                    self._complete_polygon()
                    return True

            elif event.key == pygame.K_ESCAPE:
                if self.show_help:
                    self.show_help = False
                    return True
                if self.current_polygon:
                    self.current_polygon = []
                    return True
                if self.selected_polygon_idx is not None:
                    self.selected_polygon_idx = None
                    self.selected_vertex_idx = None
                    return True

            elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                if self.selected_polygon_idx is not None:
                    self._delete_polygon(self.selected_polygon_idx)
                    return True
                if self.current_polygon:
                    self.current_polygon.pop()
                    return True

            elif ctrl and event.key == pygame.K_g:
                self.show_grid = not self.show_grid
                return True

            elif ctrl and event.key == pygame.K_s and (mods & pygame.KMOD_SHIFT):
                self.snap_to_grid = not self.snap_to_grid
                return True

            elif ctrl and event.key == pygame.K_o:
                if self.selected_polygon_idx is not None:
                    idx = self.selected_polygon_idx
                    self.polygon_one_way[idx] = not self.polygon_one_way[idx]
                    if self.on_polygon_modified:
                        self.on_polygon_modified(idx)
                    return True

            elif ctrl and event.key == pygame.K_r:
                self._center_view()
                self.zoom = 2.0
                return True

            elif ctrl and event.key == pygame.K_a:
                self.show_angle_hints = not self.show_angle_hints
                return True

        if event.type == pygame.KEYUP:
            if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                self._shift_held = False

        return False

    def _complete_polygon(self) -> None:
        """Complete the current polygon"""
        if len(self.current_polygon) >= 3:
            self.polygons.append(list(self.current_polygon))
            self.polygon_one_way.append(False)
            if self.on_polygon_added:
                self.on_polygon_added(self.current_polygon)
            self.current_polygon = []

    def _delete_polygon(self, idx: int) -> None:
        """Delete a polygon"""
        if 0 <= idx < len(self.polygons):
            self.polygons.pop(idx)
            self.polygon_one_way.pop(idx)
            if self.on_polygon_removed:
                self.on_polygon_removed(idx)
            self.selected_polygon_idx = None
            self.selected_vertex_idx = None

    def draw(self, screen: pygame.Surface) -> None:
        """Draw the collision painter"""
        self._ensure_fonts()

        screen.set_clip(self.rect)

        screen.fill(COLORS.bg, self.rect)

        tw, th = self.tile_size
        scaled_w = int(tw * self.zoom)
        scaled_h = int(th * self.zoom)

        if scaled_w > 0 and scaled_h > 0:
            tile_x = int(self.rect.x + self.offset_x)
            tile_y = int(self.rect.y + self.offset_y)
            scaled = pygame.transform.scale(self.tile_surface, (scaled_w, scaled_h))
            screen.blit(scaled, (tile_x, tile_y))

            tile_rect = Rect(tile_x, tile_y, scaled_w, scaled_h)
            pygame.draw.rect(screen, _COLORS["border"], tile_rect, 1)

        if self.show_grid:
            self._draw_grid(screen)

        for idx, polygon in enumerate(self.polygons):
            is_selected = idx == self.selected_polygon_idx
            is_hovered = idx == self.hover_polygon_idx and not is_selected
            is_one_way = self.polygon_one_way[idx]
            self._draw_polygon(screen, polygon, is_selected, is_hovered, is_one_way)

        if self.current_polygon:
            self._draw_current_polygon(screen)

        self._draw_status(screen)

        if self.show_help:
            self._draw_help(screen)

        if self.edge_draw_mode:
            self._draw_edge_mode_indicator(screen)

        if not self.show_help:
            self._draw_info_button(screen)

        screen.set_clip(None)

    def _draw_edge_mode_indicator(self, screen: pygame.Surface) -> None:
        """Draw edge draw mode indicator in top-right corner"""
        self._ensure_fonts()
        indicator = "EDGE DRAW (E) + SHIFT"
        surf = self._font_sm.render(indicator, True, _COLORS["edge_mode"])
        bg_w = surf.get_width() + 16
        bg_h = surf.get_height() + 8
        x = self.rect.right - bg_w - 5
        y = self.rect.y + 5
        bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
        bg.fill((*_COLORS["edge_mode"], 40))
        screen.blit(bg, (x, y))
        pygame.draw.rect(screen, _COLORS["edge_mode"], (x, y, bg_w, bg_h), 1)
        screen.blit(surf, (x + 8, y + 4))

    def _draw_info_button(self, screen: pygame.Surface) -> None:
        """Draw info button in top-right corner"""
        self._ensure_fonts()

        btn = self._info_button_rect
        mouse = pygame.mouse.get_pos()
        is_hover = btn.collidepoint(mouse)

        bg_color = _COLORS["polygon_fill"] if is_hover else _COLORS["header"]
        border_color = _COLORS["accent"] if is_hover else _COLORS["border_soft"]

        pygame.draw.circle(screen, bg_color, btn.center, btn.width // 2)

        pygame.draw.circle(screen, border_color, btn.center, btn.width // 2, 2)

        info_text = self._font.render("i", True, _COLORS["text"])
        text_rect = info_text.get_rect(center=btn.center)

        shadow_text = self._font.render("i", True, _COLORS["text_dim"])
        shadow_rect = shadow_text.get_rect(center=(btn.centerx + 1, btn.centery + 1))
        screen.blit(shadow_text, shadow_rect)
        screen.blit(info_text, text_rect)

        if is_hover:
            hint = self._font_sm.render("Help", True, _COLORS["text"])
            hint_bg = pygame.Surface(
                (hint.get_width() + 12, hint.get_height() + 6), pygame.SRCALPHA
            )
            hint_bg.fill((*_COLORS["header"], 220))
            hint_x = btn.centerx - hint.get_width() // 2
            hint_y = btn.bottom + 4
            screen.blit(hint_bg, (hint_x - 6, hint_y - 3))
            screen.blit(hint, (hint_x, hint_y))

    def _draw_help(self, screen: pygame.Surface) -> None:
        """Draw help panel overlay with scrollbox"""
        self._ensure_fonts()

        overlay = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, self.rect.topleft)

        panel_rect = self._help_rect
        panel_surf = pygame.Surface((panel_rect.w, panel_rect.h), pygame.SRCALPHA)
        panel_surf.fill((*_COLORS["help_bg"], 245))

        pygame.draw.rect(
            panel_surf, _COLORS["border"], (0, 0, panel_rect.w, panel_rect.h), 2
        )
        screen.blit(panel_surf, panel_rect.topleft)

        title = self._font.render("Collision Painter Help", True, _COLORS["text"])
        screen.blit(title, (panel_rect.x + 15, panel_rect.y + 12))

        close_btn = Rect(panel_rect.right - 30, panel_rect.y + 10, 20, 20)
        mouse = pygame.mouse.get_pos()
        close_hover = close_btn.collidepoint(mouse)
        close_bg = _COLORS["polygon_stroke"] if close_hover else COLORS.bg
        pygame.draw.rect(screen, close_bg, close_btn)
        pygame.draw.rect(screen, _COLORS["border"], close_btn, 1)
        close_icon = icon_manager.get_icon("close", 14, _COLORS["text"])
        screen.blit(close_icon, close_icon.get_rect(center=close_btn.center))

        pygame.draw.line(
            screen,
            _COLORS["border"],
            (panel_rect.x + 10, panel_rect.y + 40),
            (panel_rect.right - 10, panel_rect.y + 40),
        )

        content_rect = Rect(
            panel_rect.x + HELP_CONTENT_PADDING,
            panel_rect.y + HELP_TITLE_HEIGHT + HELP_CONTENT_PADDING,
            panel_rect.w - HELP_SCROLLBAR_WIDTH - HELP_CONTENT_PADDING,
            panel_rect.h
            - HELP_TITLE_HEIGHT
            - HELP_FOOTER_HEIGHT
            - HELP_CONTENT_PADDING,
        )

        help_sections = [
            (
                "DRAWING",
                [
                    ("Left-click", "Add vertex"),
                    ("Right-click / Enter", "Complete polygon"),
                    ("Escape", "Cancel current polygon"),
                    ("Shift (edge mode)", "Constrain to axis"),
                    ("Ctrl+E", "Toggle edge draw mode"),
                ],
            ),
            (
                "SELECTION",
                [
                    ("Left-click polygon", "Select polygon"),
                    ("Left-click vertex", "Select & drag vertex"),
                    ("Delete / Backspace", "Remove selected polygon"),
                    ("Ctrl+O", "Toggle one-way collision"),
                ],
            ),
            (
                "VIEW",
                [
                    ("Mouse wheel", "Zoom in/out"),
                    ("Middle mouse / Space+LMB", "Pan view"),
                    ("Ctrl+G", "Toggle grid"),
                    ("Ctrl+Shift+S", "Toggle snap to grid"),
                    ("Ctrl+R", "Reset view"),
                    ("Ctrl+A", "Toggle angle hints"),
                ],
            ),
            (
                "MISC",
                [
                    ("Info button (top-right)", "Toggle this help panel"),
                ],
            ),
        ]

        self._help_content_height = 0
        for section_title, items in help_sections:
            self._help_content_height += 25
            self._help_content_height += len(items) * 20 + 10

        old_clip = screen.get_clip()
        screen.set_clip(content_rect)

        y = content_rect.y - self._help_scroll
        for section_title, items in help_sections:
            header = self._font_sm.render(section_title, True, _COLORS["polygon_fill"])
            screen.blit(header, (content_rect.x + 10, y))
            y += 22

            for key, desc in items:
                key_surf = self._font_sm.render(key, True, _COLORS["vertex_first"])
                key_x = content_rect.x + 10
                key_bg = Rect(
                    key_x, y - 2, key_surf.get_width() + 10, key_surf.get_height() + 4
                )
                pygame.draw.rect(screen, (*COLORS.bg, 180), key_bg, border_radius=3)
                screen.blit(key_surf, (key_x + 5, y))

                desc_x = key_x + key_bg.width + 8
                desc_surf = self._font_sm.render(desc, True, _COLORS["text"])
                screen.blit(desc_surf, (desc_x, y))
                y += 20

            y += 12

        screen.set_clip(old_clip)

        scrollbar_rect = Rect(panel_rect.right - 20, content_rect.y, 12, content_rect.h)

        pygame.draw.rect(screen, (*COLORS.bg, 100), scrollbar_rect, border_radius=6)

        if self._help_content_height > content_rect.h:
            thumb_height = max(
                HELP_THUMB_MIN_HEIGHT,
                int(content_rect.h * content_rect.h / self._help_content_height),
            )
            thumb_y = content_rect.y + int(
                (self._help_scroll / max(1, self._help_content_height - content_rect.h))
                * (content_rect.h - thumb_height)
            )
            thumb_rect = Rect(scrollbar_rect.x, thumb_y, 12, thumb_height)

            thumb_color = (
                _COLORS["polygon_fill"]
                if scrollbar_rect.collidepoint(mouse)
                else _COLORS["border_soft"]
            )
            pygame.draw.rect(screen, thumb_color, thumb_rect, border_radius=6)

        footer_y = panel_rect.bottom - 30
        footer_hint = self._font_sm.render(
            "Scroll to view all shortcuts", True, _COLORS["text_dim"]
        )
        screen.blit(footer_hint, (panel_rect.x + 15, footer_y))

    def _draw_grid(self, screen: pygame.Surface) -> None:
        """Draw grid overlay"""
        tw, th = self.tile_size
        tile_x = int(self.rect.x + self.offset_x)
        tile_y = int(self.rect.y + self.offset_y)
        scaled_w = int(tw * self.zoom)
        scaled_h = int(th * self.zoom)

        grid_surf = pygame.Surface((scaled_w, scaled_h), pygame.SRCALPHA)

        for x in range(0, tw + 1, self.grid_size):
            sx = int(x * self.zoom)
            pygame.draw.line(grid_surf, (*_COLORS["grid"], 30), (sx, 0), (sx, scaled_h))

        for y in range(0, th + 1, self.grid_size):
            sy = int(y * self.zoom)
            pygame.draw.line(grid_surf, (*_COLORS["grid"], 30), (0, sy), (scaled_w, sy))

        screen.blit(grid_surf, (tile_x, tile_y))

    def _draw_polygon(
        self,
        screen: pygame.Surface,
        polygon: list[tuple[float, float]],
        selected: bool,
        hovered: bool,
        one_way: bool,
    ) -> None:
        """Draw a collision polygon"""
        if len(polygon) < 3:
            return

        screen_points = [self._tile_to_screen(p) for p in polygon]

        fill_color = (
            _COLORS["polygon_selected"] if selected else _COLORS["polygon_fill"]
        )
        if one_way:
            fill_color = _COLORS["one_way"]

        alpha = 100 if selected else (70 if hovered else 50)
        poly_surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.polygon(poly_surf, (*fill_color, alpha), screen_points)
        screen.blit(poly_surf, self.rect.topleft)

        stroke_color = (
            _COLORS["polygon_selected"] if selected else _COLORS["polygon_stroke"]
        )
        if one_way:
            stroke_color = _COLORS["one_way"]
        pygame.draw.polygon(screen, stroke_color, screen_points, 2)

        for i, (px, py) in enumerate(screen_points):
            is_first = i == 0
            is_hovered_vertex = (
                self.hover_vertex is not None
                and self.hover_vertex[1] == i
                and self.polygons[self.hover_vertex[0]] == polygon
            )

            color = _COLORS["vertex_first"] if is_first else _COLORS["vertex"]
            if is_hovered_vertex:
                color = _COLORS["vertex_hover"]

            radius = VERTEX_HOVER_RADIUS if is_hovered_vertex else VERTEX_RADIUS
            pygame.draw.circle(screen, color, (px, py), radius)
            pygame.draw.circle(screen, (0, 0, 0), (px, py), radius, 1)

        if selected and one_way and len(polygon) >= 3:
            cx = int(sum(p[0] for p in screen_points) / len(screen_points))
            cy = int(sum(p[1] for p in screen_points) / len(screen_points))
            badge = self._font_sm.render("ONE-WAY", True, (255, 255, 255))
            bx = cx - badge.get_width() // 2
            by = cy - badge.get_height() // 2
            bg = pygame.Surface(
                (badge.get_width() + 8, badge.get_height() + 4), pygame.SRCALPHA
            )
            bg.fill(
                (
                    _COLORS["one_way"][0],
                    _COLORS["one_way"][1],
                    _COLORS["one_way"][2],
                    200,
                )
            )
            screen.blit(bg, (bx - 4, by - 2))
            screen.blit(badge, (bx, by))

        if self.show_angle_hints:
            for i, (px, py) in enumerate(screen_points):
                angle = self._get_interior_angle(polygon, i)
                self._draw_angle_hint(screen, (px, py), angle)

    def _draw_current_polygon(self, screen: pygame.Surface) -> None:
        """Draw the polygon currently being drawn"""
        if not self.current_polygon:
            return

        screen_points = [self._tile_to_screen(p) for p in self.current_polygon]

        if len(screen_points) > 1:
            pygame.draw.lines(screen, _COLORS["preview_line"], False, screen_points, 2)

        if self.rect.collidepoint(self.mouse_pos):
            pygame.draw.line(
                screen, _COLORS["preview_line"], screen_points[-1], self.mouse_pos, 1
            )

        for i, (px, py) in enumerate(screen_points):
            is_first = i == 0
            color = _COLORS["vertex_first"] if is_first else _COLORS["vertex"]
            radius = VERTEX_HOVER_RADIUS if is_first else VERTEX_RADIUS
            pygame.draw.circle(screen, color, (px, py), radius)
            pygame.draw.circle(screen, (0, 0, 0), (px, py), radius, 1)

        if self.show_angle_hints and len(self.current_polygon) >= 3:
            for i, (px, py) in enumerate(screen_points):
                if i == 0 or i == len(screen_points) - 1:
                    continue
                poly = self.current_polygon
                prev = poly[i - 1]
                curr = poly[i]
                nxt = poly[i + 1]
                v1 = (prev[0] - curr[0], prev[1] - curr[1])
                v2 = (nxt[0] - curr[0], nxt[1] - curr[1])
                dot = v1[0] * v2[0] + v1[1] * v2[1]
                mag1 = math.hypot(v1[0], v1[1])
                mag2 = math.hypot(v2[0], v2[1])
                if mag1 > 0.001 and mag2 > 0.001:
                    cos_a = max(-1.0, min(1.0, dot / (mag1 * mag2)))
                    angle = math.degrees(math.acos(cos_a))
                    self._draw_angle_hint(screen, (px, py), angle)

    def _draw_status(self, screen: pygame.Surface) -> None:
        """Draw status text"""
        lines = []

        if self.current_polygon:
            lines.append(f"Drawing polygon: {len(self.current_polygon)} vertices")
            if self.edge_draw_mode:
                lines.append("Edge Mode: Hold Shift to constrain axis")
            if len(self.current_polygon) >= 3:
                lines.append("Right-click or Enter to complete, Esc to cancel")
        elif self.selected_polygon_idx is not None:
            one_way = self.polygon_one_way[self.selected_polygon_idx]
            one_way_str = " (ONE-WAY)" if one_way else ""
            lines.append(f"Selected polygon {self.selected_polygon_idx}{one_way_str}")
            lines.append("Delete to remove, Ctrl+O to toggle one-way")
        else:
            lines.append("Click to add vertices, right-click to complete")

        snap_str = f"Snap: {'ON' if self.snap_to_grid else 'OFF'} (Ctrl+Shift+S)"
        lines.append(
            f"Zoom: {self.zoom:.1f}x | Grid: {'ON' if self.show_grid else 'OFF'} (Ctrl+G) | {snap_str}"
        )
        lines.append(
            f"Polygons: {len(self.polygons)} | Ctrl+R: reset | Ctrl+A: angle hints {'ON' if self.show_angle_hints else 'OFF'}"
        )

        y = self.rect.y + 5
        for line in lines:
            surf = self._font_sm.render(line, True, _COLORS["text"])
            bg_rect = Rect(
                self.rect.x + 5, y, surf.get_width() + 4, surf.get_height() + 2
            )
            bg = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 180))
            screen.blit(bg, bg_rect.topleft)
            screen.blit(surf, (self.rect.x + 7, y + 1))
            y += surf.get_height() + 3
