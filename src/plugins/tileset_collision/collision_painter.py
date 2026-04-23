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
from typing import List, Tuple, Optional, Set, Callable
from enum import Enum

import pygame
from pygame import Rect
from utils.font_manager import font_manager, FontWeight
from utils.error_handler import error_handler, error_context


class PaintMode(Enum):
    """Collision painter modes"""
    DRAW = "draw"
    ERASE = "erase"
    SELECT = "select"


# Theme colors (matching Godot's collision editor)
_COLORS = {
    "bg": (25, 27, 30),
    "grid": (255, 255, 255),
    "polygon_fill": (80, 180, 255),  # Blue like Godot
    "polygon_stroke": (100, 200, 255),
    "polygon_selected": (255, 180, 80),  # Orange for selection
    "vertex": (255, 255, 255),
    "vertex_hover": (255, 220, 80),
    "vertex_first": (80, 255, 120),  # Green for first vertex
    "preview_line": (200, 200, 200),
    "text": (230, 230, 230),
    "text_dim": (140, 140, 140),
    "header": (40, 42, 46),
    "border": (60, 62, 65),
    "one_way": (255, 120, 120),  # Red for one-way collision
    "edge_mode": (120, 255, 120),  # Green for edge-draw mode
    "help_bg": (15, 17, 20),
}

VERTEX_RADIUS = 5
VERTEX_HOVER_RADIUS = 7
SNAP_THRESHOLD = 10  # pixels


class CollisionPainter:
    """Godot-like collision polygon painter for a single tile."""

    def __init__(
        self,
        rect: Rect,
        tile_surface: pygame.Surface,
        tile_size: Tuple[int, int],
    ):
        self.rect = rect
        self.tile_surface = tile_surface
        self.tile_size = tile_size
        
        # Current polygons (list of vertex lists)
        self.polygons: List[List[Tuple[float, float]]] = []
        self.polygon_one_way: List[bool] = []  # One-way collision flags
        
        # Drawing state
        self.mode = PaintMode.DRAW
        self.current_polygon: List[Tuple[float, float]] = []
        self.selected_polygon_idx: Optional[int] = None
        self.selected_vertex_idx: Optional[int] = None
        
        # View state
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self.zoom: float = 2.0  # Start zoomed in for precision
        
        # Interaction
        self.hover_vertex: Optional[Tuple[int, int]] = None  # (polygon_idx, vertex_idx)
        self.hover_polygon_idx: Optional[int] = None
        self.mouse_pos: Tuple[int, int] = (0, 0)
        self._panning = False
        self._pan_start = (0, 0)
        self._pan_start_offset = (0.0, 0.0)
        self._dragging_vertex = False
        
        # Settings
        self.snap_to_grid = False
        self.grid_size = 8  # pixels
        self.show_grid = True
        self.edge_draw_mode = False  # E key - straight line drawing
        self._edge_start: Optional[Tuple[int, int]] = None  # Start point for edge draw
        self._shift_held = False
        
        # Help panel
        self.show_help = False
        self._help_rect = Rect(0, 0, 300, 400)
        
        # Callbacks
        self.on_polygon_added: Optional[Callable[[List[Tuple[float, float]]], None]] = None
        self.on_polygon_removed: Optional[Callable[[int], None]] = None
        self.on_polygon_modified: Optional[Callable[[int], None]] = None
        
        # Fonts
        self._font: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None
        
        # Center the tile in view
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
    
    def _screen_to_tile(self, screen_pos: Tuple[int, int]) -> Tuple[float, float]:
        """Convert screen coordinates to tile-local coordinates"""
        x = (screen_pos[0] - self.rect.x - self.offset_x) / self.zoom
        y = (screen_pos[1] - self.rect.y - self.offset_y) / self.zoom
        return (x, y)
    
    def _tile_to_screen(self, tile_pos: Tuple[float, float]) -> Tuple[int, int]:
        """Convert tile-local coordinates to screen coordinates"""
        x = int(self.rect.x + self.offset_x + tile_pos[0] * self.zoom)
        y = int(self.rect.y + self.offset_y + tile_pos[1] * self.zoom)
        return (x, y)
    
    def _snap_to_grid(self, pos: Tuple[float, float]) -> Tuple[float, float]:
        """Snap position to grid if enabled"""
        if not self.snap_to_grid:
            return pos
        x = round(pos[0] / self.grid_size) * self.grid_size
        y = round(pos[1] / self.grid_size) * self.grid_size
        return (x, y)
    
    def _find_vertex_at(self, screen_pos: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        """Find vertex at screen position, returns (polygon_idx, vertex_idx) or None"""
        for poly_idx, polygon in enumerate(self.polygons):
            for vert_idx, vertex in enumerate(polygon):
                screen_vert = self._tile_to_screen(vertex)
                dist = math.hypot(
                    screen_pos[0] - screen_vert[0],
                    screen_pos[1] - screen_vert[1]
                )
                if dist <= VERTEX_HOVER_RADIUS:
                    return (poly_idx, vert_idx)
        return None
    
    def _find_polygon_at(self, screen_pos: Tuple[int, int]) -> Optional[int]:
        """Find polygon containing the screen position"""
        tile_pos = self._screen_to_tile(screen_pos)
        
        for poly_idx, polygon in enumerate(self.polygons):
            if len(polygon) < 3:
                continue
            if self._point_in_polygon(tile_pos, polygon):
                return poly_idx
        return None
    
    def _point_in_polygon(
        self, point: Tuple[float, float], polygon: List[Tuple[float, float]]
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
        # Center help panel in view
        self._help_rect = Rect(
            self.rect.x + (self.rect.w - 300) // 2,
            self.rect.y + (self.rect.h - 400) // 2,
            300,
            400
        )
    
    def set_polygons(self, polygons: List[List[Tuple[float, float]]], one_way_flags: Optional[List[bool]] = None) -> None:
        """Load existing polygons"""
        self.polygons = [list(p) for p in polygons]
        if one_way_flags:
            self.polygon_one_way = list(one_way_flags)
        else:
            self.polygon_one_way = [False] * len(polygons)
        self.current_polygon = []
        self.selected_polygon_idx = None
    
    def get_polygons(self) -> List[List[Tuple[float, float]]]:
        """Get all completed polygons"""
        return [list(p) for p in self.polygons]
    
    def get_one_way_flags(self) -> List[bool]:
        """Get one-way collision flags for all polygons"""
        return list(self.polygon_one_way)
    
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
        
        if not self.rect.collidepoint(mouse) and event.type not in (
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
        ):
            return False
        
        # Middle mouse or Space+drag to pan
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
        
        if event.type == pygame.MOUSEMOTION:
            if self._panning:
                dx = mouse[0] - self._pan_start[0]
                dy = mouse[1] - self._pan_start[1]
                self.offset_x = self._pan_start_offset[0] + dx
                self.offset_y = self._pan_start_offset[1] + dy
                return True
            
            # Update hover state
            if self.rect.collidepoint(mouse):
                self.hover_vertex = self._find_vertex_at(mouse)
                if not self.hover_vertex:
                    self.hover_polygon_idx = self._find_polygon_at(mouse)
                else:
                    self.hover_polygon_idx = None
                
                # Drag vertex
                if self._dragging_vertex and self.selected_vertex_idx is not None:
                    poly_idx, vert_idx = self.selected_vertex_idx
                    tile_pos = self._screen_to_tile(mouse)
                    tile_pos = self._snap_to_grid(tile_pos)
                    # Clamp to tile bounds
                    tw, th = self.tile_size
                    tile_pos = (
                        max(0, min(tw, tile_pos[0])),
                        max(0, min(th, tile_pos[1]))
                    )
                    self.polygons[poly_idx][vert_idx] = tile_pos
                    if self.on_polygon_modified:
                        self.on_polygon_modified(poly_idx)
                    return True
        
        # Mouse wheel to zoom
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(mouse):
            self.zoom *= 1.15 if event.y > 0 else 0.87
            self.zoom = max(0.5, min(self.zoom, 8.0))
            
            # Zoom toward mouse
            tile_pos = self._screen_to_tile(mouse)
            self.offset_x = mouse[0] - self.rect.x - tile_pos[0] * self.zoom
            self.offset_y = mouse[1] - self.rect.y - tile_pos[1] * self.zoom
            return True
        
        # Left click - draw or select
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse):
                # Check if clicking on vertex
                vertex_hit = self._find_vertex_at(mouse)
                if vertex_hit:
                    poly_idx, vert_idx = vertex_hit
                    self.selected_polygon_idx = poly_idx
                    self.selected_vertex_idx = vertex_hit
                    self._dragging_vertex = True
                    return True
                
                # Check if clicking on polygon
                poly_hit = self._find_polygon_at(mouse)
                if poly_hit is not None:
                    self.selected_polygon_idx = poly_hit
                    self.selected_vertex_idx = None
                    return True
                
                # Add vertex to current polygon
                if self.mode == PaintMode.DRAW:
                    tile_pos = self._screen_to_tile(mouse)
                    
                    # Edge draw mode: Shift constrains to horizontal/vertical
                    if self.edge_draw_mode and self._shift_held and len(self.current_polygon) > 0:
                        start = self.current_polygon[-1]
                        dx = tile_pos[0] - start[0]
                        dy = tile_pos[1] - start[1]
                        # Snap to dominant axis
                        if abs(dx) > abs(dy):
                            tile_pos = (tile_pos[0], start[1])
                        else:
                            tile_pos = (start[0], tile_pos[1])
                    
                    tile_pos = self._snap_to_grid(tile_pos)
                    
                    # Clamp to tile bounds
                    tw, th = self.tile_size
                    tile_pos = (
                        max(0, min(tw, tile_pos[0])),
                        max(0, min(th, tile_pos[1]))
                    )
                    
                    # Check if clicking near first vertex to close polygon
                    if len(self.current_polygon) >= 3:
                        first_screen = self._tile_to_screen(self.current_polygon[0])
                        dist = math.hypot(
                            mouse[0] - first_screen[0],
                            mouse[1] - first_screen[1]
                        )
                        if dist <= SNAP_THRESHOLD:
                            self._complete_polygon()
                            return True
                    
                    self.current_polygon.append(tile_pos)
                    return True
                
                # Deselect
                self.selected_polygon_idx = None
                self.selected_vertex_idx = None
                return True
        
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging_vertex:
                self._dragging_vertex = False
                return True
        
        # Right click - complete polygon or delete
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.rect.collidepoint(mouse):
                if len(self.current_polygon) >= 3:
                    self._complete_polygon()
                    return True
                elif self.current_polygon:
                    # Cancel current polygon
                    self.current_polygon = []
                    return True
        
        # Keyboard shortcuts
        if event.type == pygame.KEYDOWN:
            # Track Shift state for edge draw
            if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                self._shift_held = True
            
            # E - toggle edge draw mode
            elif event.key == pygame.K_e:
                self.edge_draw_mode = not self.edge_draw_mode
                if not self.edge_draw_mode:
                    self._edge_start = None
                return True
            
            # H - toggle help panel
            elif event.key == pygame.K_h:
                self.show_help = not self.show_help
                return True
            
            # Enter - complete polygon
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if len(self.current_polygon) >= 3:
                    self._complete_polygon()
                    return True
            
            # Escape - cancel current polygon or deselect or close help
            elif event.key == pygame.K_ESCAPE:
                if self.show_help:
                    self.show_help = False
                    return True
                if self.current_polygon:
                    self.current_polygon = []
                    return True
                elif self.selected_polygon_idx is not None:
                    self.selected_polygon_idx = None
                    self.selected_vertex_idx = None
                    return True
            
            # Delete - remove selected polygon
            elif event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                if self.selected_polygon_idx is not None:
                    self._delete_polygon(self.selected_polygon_idx)
                    return True
                elif self.current_polygon:
                    # Remove last vertex
                    self.current_polygon.pop()
                    return True
            
            # G - toggle grid
            elif event.key == pygame.K_g:
                self.show_grid = not self.show_grid
                return True
            
            # S - toggle snap
            elif event.key == pygame.K_s:
                self.snap_to_grid = not self.snap_to_grid
                return True
            
            # O - toggle one-way collision for selected polygon
            elif event.key == pygame.K_o:
                if self.selected_polygon_idx is not None:
                    idx = self.selected_polygon_idx
                    self.polygon_one_way[idx] = not self.polygon_one_way[idx]
                    if self.on_polygon_modified:
                        self.on_polygon_modified(idx)
                    return True
            
            # R - reset view
            elif event.key == pygame.K_r:
                self._center_view()
                self.zoom = 2.0
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
        
        # Background
        screen.fill(_COLORS["bg"], self.rect)
        
        # Draw tile
        tw, th = self.tile_size
        scaled_w = int(tw * self.zoom)
        scaled_h = int(th * self.zoom)
        
        if scaled_w > 0 and scaled_h > 0:
            tile_x = int(self.rect.x + self.offset_x)
            tile_y = int(self.rect.y + self.offset_y)
            scaled = pygame.transform.scale(self.tile_surface, (scaled_w, scaled_h))
            screen.blit(scaled, (tile_x, tile_y))
            
            # Draw tile border
            tile_rect = Rect(tile_x, tile_y, scaled_w, scaled_h)
            pygame.draw.rect(screen, _COLORS["border"], tile_rect, 1)
        
        # Draw grid
        if self.show_grid:
            self._draw_grid(screen)
        
        # Draw completed polygons
        for idx, polygon in enumerate(self.polygons):
            is_selected = (idx == self.selected_polygon_idx)
            is_hovered = (idx == self.hover_polygon_idx and not is_selected)
            is_one_way = self.polygon_one_way[idx]
            self._draw_polygon(screen, polygon, is_selected, is_hovered, is_one_way)
        
        # Draw current polygon being drawn
        if self.current_polygon:
            self._draw_current_polygon(screen)
        
        # Draw status text
        self._draw_status(screen)
        
        # Draw help panel if enabled
        if self.show_help:
            self._draw_help(screen)
        
        # Draw edge mode indicator
        if self.edge_draw_mode:
            self._draw_edge_mode_indicator(screen)
        
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
    
    def _draw_help(self, screen: pygame.Surface) -> None:
        """Draw help panel overlay"""
        self._ensure_fonts()
        
        # Semi-transparent overlay
        overlay = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, self.rect.topleft)
        
        # Help panel background
        panel_rect = self._help_rect
        panel_surf = pygame.Surface((panel_rect.w, panel_rect.h), pygame.SRCALPHA)
        panel_surf.fill((*_COLORS["help_bg"], 240))
        pygame.draw.rect(panel_surf, _COLORS["border"], (0, 0, panel_rect.w, panel_rect.h), 2)
        screen.blit(panel_surf, panel_rect.topleft)
        
        # Title
        title = self._font.render("Collision Painter Help", True, _COLORS["text"])
        screen.blit(title, (panel_rect.x + 15, panel_rect.y + 15))
        
        # Divider
        pygame.draw.line(
            screen, _COLORS["border"],
            (panel_rect.x + 10, panel_rect.y + 45),
            (panel_rect.right - 10, panel_rect.y + 45)
        )
        
        # Help content
        help_lines = [
            ("DRAWING", [
                ("Left-click", "Add vertex"),
                ("Right-click / Enter", "Complete polygon"),
                ("Escape", "Cancel current polygon"),
                ("Shift (edge mode)", "Constrain to axis"),
                ("E", "Toggle edge draw mode"),
            ]),
            ("SELECTION", [
                ("Left-click polygon", "Select polygon"),
                ("Left-click vertex", "Select & drag vertex"),
                ("Delete / Backspace", "Remove selected polygon"),
                ("O", "Toggle one-way collision"),
            ]),
            ("VIEW", [
                ("Mouse wheel", "Zoom in/out"),
                ("Middle mouse / Space+LMB", "Pan view"),
                ("G", "Toggle grid"),
                ("S", "Toggle snap to grid"),
                ("R", "Reset view"),
            ]),
            ("MISC", [
                ("H", "Toggle this help panel"),
                ("?", "Same as H"),
            ]),
        ]
        
        y = panel_rect.y + 55
        for section_title, items in help_lines:
            # Section header
            header = self._font_sm.render(section_title, True, _COLORS["polygon_fill"])
            screen.blit(header, (panel_rect.x + 15, y))
            y += 20
            
            for key, desc in items:
                # Key
                key_surf = self._font_sm.render(key, True, _COLORS["vertex_first"])
                screen.blit(key_surf, (panel_rect.x + 20, y))
                # Description
                desc_surf = self._font_sm.render(desc, True, _COLORS["text"])
                screen.blit(desc_surf, (panel_rect.x + 130, y))
                y += 18
            
            y += 8
        
        # Close hint
        close_hint = self._font_sm.render("Press H or Escape to close", True, _COLORS["text_dim"])
        screen.blit(close_hint, (panel_rect.x + (panel_rect.w - close_hint.get_width()) // 2, panel_rect.bottom - 25))
    
    def _draw_grid(self, screen: pygame.Surface) -> None:
        """Draw grid overlay"""
        tw, th = self.tile_size
        tile_x = int(self.rect.x + self.offset_x)
        tile_y = int(self.rect.y + self.offset_y)
        scaled_w = int(tw * self.zoom)
        scaled_h = int(th * self.zoom)
        
        grid_surf = pygame.Surface((scaled_w, scaled_h), pygame.SRCALPHA)
        
        # Draw vertical lines
        for x in range(0, tw + 1, self.grid_size):
            sx = int(x * self.zoom)
            pygame.draw.line(
                grid_surf,
                (*_COLORS["grid"], 30),
                (sx, 0),
                (sx, scaled_h)
            )
        
        # Draw horizontal lines
        for y in range(0, th + 1, self.grid_size):
            sy = int(y * self.zoom)
            pygame.draw.line(
                grid_surf,
                (*_COLORS["grid"], 30),
                (0, sy),
                (scaled_w, sy)
            )
        
        screen.blit(grid_surf, (tile_x, tile_y))
    
    def _draw_polygon(
        self,
        screen: pygame.Surface,
        polygon: List[Tuple[float, float]],
        selected: bool,
        hovered: bool,
        one_way: bool
    ) -> None:
        """Draw a collision polygon"""
        if len(polygon) < 3:
            return
        
        # Convert to screen coordinates
        screen_points = [self._tile_to_screen(p) for p in polygon]
        
        # Draw filled polygon
        fill_color = _COLORS["polygon_selected"] if selected else _COLORS["polygon_fill"]
        if one_way:
            fill_color = _COLORS["one_way"]
        
        alpha = 100 if selected else (70 if hovered else 50)
        poly_surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.polygon(poly_surf, (*fill_color, alpha), screen_points)
        screen.blit(poly_surf, self.rect.topleft)
        
        # Draw outline
        stroke_color = _COLORS["polygon_selected"] if selected else _COLORS["polygon_stroke"]
        if one_way:
            stroke_color = _COLORS["one_way"]
        pygame.draw.polygon(screen, stroke_color, screen_points, 2)
        
        # Draw vertices
        for i, (px, py) in enumerate(screen_points):
            is_first = (i == 0)
            is_hovered_vertex = (
                self.hover_vertex is not None and
                self.hover_vertex[1] == i and
                self.polygons[self.hover_vertex[0]] == polygon
            )
            
            color = _COLORS["vertex_first"] if is_first else _COLORS["vertex"]
            if is_hovered_vertex:
                color = _COLORS["vertex_hover"]
            
            radius = VERTEX_HOVER_RADIUS if is_hovered_vertex else VERTEX_RADIUS
            pygame.draw.circle(screen, color, (px, py), radius)
            pygame.draw.circle(screen, (0, 0, 0), (px, py), radius, 1)
    
    def _draw_current_polygon(self, screen: pygame.Surface) -> None:
        """Draw the polygon currently being drawn"""
        if not self.current_polygon:
            return
        
        screen_points = [self._tile_to_screen(p) for p in self.current_polygon]
        
        # Draw lines between vertices
        if len(screen_points) > 1:
            pygame.draw.lines(screen, _COLORS["preview_line"], False, screen_points, 2)
        
        # Draw line to mouse cursor
        if self.rect.collidepoint(self.mouse_pos):
            pygame.draw.line(
                screen,
                _COLORS["preview_line"],
                screen_points[-1],
                self.mouse_pos,
                1
            )
        
        # Draw vertices
        for i, (px, py) in enumerate(screen_points):
            is_first = (i == 0)
            color = _COLORS["vertex_first"] if is_first else _COLORS["vertex"]
            radius = VERTEX_HOVER_RADIUS if is_first else VERTEX_RADIUS
            pygame.draw.circle(screen, color, (px, py), radius)
            pygame.draw.circle(screen, (0, 0, 0), (px, py), radius, 1)
    
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
            lines.append("Delete to remove, O to toggle one-way")
        else:
            lines.append("Click to add vertices, right-click to complete")
        
        lines.append(f"Zoom: {self.zoom:.1f}x | Grid: {'ON' if self.show_grid else 'OFF'} (G) | Snap: {'ON' if self.snap_to_grid else 'OFF'} (S)")
        lines.append(f"Polygons: {len(self.polygons)} | R: reset view")
        
        y = self.rect.y + 5
        for line in lines:
            surf = self._font_sm.render(line, True, _COLORS["text"])
            bg_rect = Rect(self.rect.x + 5, y, surf.get_width() + 4, surf.get_height() + 2)
            bg = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 180))
            screen.blit(bg, bg_rect.topleft)
            screen.blit(surf, (self.rect.x + 7, y + 1))
            y += surf.get_height() + 3
