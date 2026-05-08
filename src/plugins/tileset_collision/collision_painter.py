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

# Constants
VERTEX_RADIUS = 5
VERTEX_HOVER_RADIUS = 7
SNAP_THRESHOLD = 10

# Help panel
HELP_PANEL_WIDTH = 360
HELP_PANEL_HEIGHT = 450
HELP_SCROLL_SPEED = 30
HELP_SCROLLBAR_WIDTH = 12
HELP_CONTENT_PADDING = 10
HELP_CLOSE_BTN_SIZE = 20
HELP_TITLE_HEIGHT = 40
HELP_FOOTER_HEIGHT = 30
HELP_SCROLL_MARGIN = 80  # Extra padding at bottom for scroll
HELP_THUMB_MIN_HEIGHT = 30  # Minimum scrollbar thumb height

# Info button
INFO_BTN_SIZE = 28
INFO_BTN_OFFSET_X = 36
INFO_BTN_OFFSET_Y = 8


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
        self._help_rect = Rect(
            rect.x + (rect.w - HELP_PANEL_WIDTH) // 2,
            rect.y + (rect.h - HELP_PANEL_HEIGHT) // 2,
            HELP_PANEL_WIDTH,
            HELP_PANEL_HEIGHT
        )
        self._help_scroll = 0
        self._help_content_height = 0
        self._help_scrolling = False
        self._help_scroll_start = 0
        self._help_scroll_start_y = 0
        
        # Info button (top-right corner) - position based on initial rect
        self._info_button_rect = Rect(
            rect.right - INFO_BTN_OFFSET_X,
            rect.y + INFO_BTN_OFFSET_Y,
            INFO_BTN_SIZE,
            INFO_BTN_SIZE
        )
        
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
            self.rect.x + (self.rect.w - HELP_PANEL_WIDTH) // 2,
            self.rect.y + (self.rect.h - HELP_PANEL_HEIGHT) // 2,
            HELP_PANEL_WIDTH,
            HELP_PANEL_HEIGHT
        )
        # Info button in top-right
        self._info_button_rect = Rect(
            self.rect.right - INFO_BTN_OFFSET_X,
            self.rect.y + INFO_BTN_OFFSET_Y,
            INFO_BTN_SIZE,
            INFO_BTN_SIZE
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
        
        # Allow Escape to close help even when outside rect
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.show_help:
                self.show_help = False
                return True
            return False
        
        # Block most events when help is open
        if self.show_help:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Close button (X in top-right)
                close_btn = Rect(self._help_rect.right - HELP_CLOSE_BTN_SIZE - HELP_CONTENT_PADDING, self._help_rect.y + HELP_CONTENT_PADDING, HELP_CLOSE_BTN_SIZE, HELP_CLOSE_BTN_SIZE)
                if close_btn.collidepoint(mouse):
                    self.show_help = False
                    self._help_scroll = 0
                    return True
                
                if self._help_rect.collidepoint(mouse):
                    # Check if clicking on scrollbar area (right side)
                    if mouse[0] > self._help_rect.right - HELP_SCROLLBAR_WIDTH:
                        self._help_scrolling = True
                        self._help_scroll_start = self._help_scroll
                        self._help_scroll_start_y = mouse[1]
                        return True
                    return True  # Click inside help content - don't close
                # Click outside help panel - close it
                self.show_help = False
                self._help_scroll = 0
                return True
            
            # Handle scrollbar drag
            if event.type == pygame.MOUSEBUTTONUP:
                if self._help_scrolling:
                    self._help_scrolling = False
                    return True
            
            if event.type == pygame.MOUSEMOTION:
                if self._help_scrolling:
                    dy = mouse[1] - self._help_scroll_start_y
                    self._help_scroll = self._help_scroll_start + dy * 2
                    self._help_scroll = max(0, min(self._help_scroll, max(0, self._help_content_height - self._help_rect.h + HELP_SCROLL_MARGIN)))
                    return True
            
            # Mouse wheel for scrolling
            if event.type == pygame.MOUSEWHEEL:
                if self._help_rect.collidepoint(mouse) or (self._help_rect.right - HELP_SCROLLBAR_WIDTH < mouse[0] < self._help_rect.right):
                    self._help_scroll -= event.y * HELP_SCROLL_SPEED
                    self._help_scroll = max(0, min(self._help_scroll, max(0, self._help_content_height - self._help_rect.h + HELP_SCROLL_MARGIN)))
                    return True
            
            # Escape to close
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.show_help = False
                return True
            
            return False
        
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
        
        # Info button click (only when help is not open)
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
            
            # S - toggle snap (only if Ctrl is not held)
            elif event.key == pygame.K_s:
                mods = pygame.key.get_mods()
                ctrl_held = mods & (pygame.KMOD_CTRL | pygame.KMOD_LMETA)
                if not ctrl_held:
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
        
        # Draw info button (only when help is not shown)
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
        
        # Circle background with gradient-like effect
        bg_color = _COLORS["polygon_fill"] if is_hover else _COLORS["header"]
        border_color = _COLORS["accent"] if is_hover else _COLORS["border_soft"]
        
        # Draw filled circle
        pygame.draw.circle(screen, bg_color, btn.center, btn.width // 2)
        
        # Draw circle border
        pygame.draw.circle(screen, border_color, btn.center, btn.width // 2, 2)
        
        # "i" text - slightly bold
        info_text = self._font.render("i", True, _COLORS["text"])
        text_rect = info_text.get_rect(center=btn.center)
        
        # Add subtle shadow
        shadow_text = self._font.render("i", True, _COLORS["text_dim"])
        shadow_rect = shadow_text.get_rect(center=(btn.centerx + 1, btn.centery + 1))
        screen.blit(shadow_text, shadow_rect)
        screen.blit(info_text, text_rect)
        
        # Add a tooltip hint on hover
        if is_hover:
            hint = self._font_sm.render("Help", True, _COLORS["text"])
            hint_bg = pygame.Surface((hint.get_width() + 12, hint.get_height() + 6), pygame.SRCALPHA)
            hint_bg.fill((*_COLORS["header"], 220))
            hint_x = btn.centerx - hint.get_width() // 2
            hint_y = btn.bottom + 4
            screen.blit(hint_bg, (hint_x - 6, hint_y - 3))
            screen.blit(hint, (hint_x, hint_y))
    
    def _draw_help(self, screen: pygame.Surface) -> None:
        """Draw help panel overlay with scrollbox"""
        self._ensure_fonts()
        
        # Semi-transparent overlay
        overlay = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, self.rect.topleft)
        
        # Help panel background
        panel_rect = self._help_rect
        panel_surf = pygame.Surface((panel_rect.w, panel_rect.h), pygame.SRCALPHA)
        panel_surf.fill((*_COLORS["help_bg"], 245))
        
        # Panel border with rounded corners
        pygame.draw.rect(panel_surf, _COLORS["border"], (0, 0, panel_rect.w, panel_rect.h), 2)
        screen.blit(panel_surf, panel_rect.topleft)
        
        # Title bar
        title = self._font.render("Collision Painter Help", True, _COLORS["text"])
        screen.blit(title, (panel_rect.x + 15, panel_rect.y + 12))
        
        # Close button (X)
        close_btn = Rect(panel_rect.right - 30, panel_rect.y + 10, 20, 20)
        mouse = pygame.mouse.get_pos()
        close_hover = close_btn.collidepoint(mouse)
        close_bg = _COLORS["polygon_stroke"] if close_hover else _COLORS["bg"]
        pygame.draw.rect(screen, close_bg, close_btn)
        pygame.draw.rect(screen, _COLORS["border"], close_btn, 1)
        close_x = self._font.render("×", True, _COLORS["text"])
        screen.blit(close_x, close_x.get_rect(center=close_btn.center))
        
        # Divider
        pygame.draw.line(
            screen, _COLORS["border"],
            (panel_rect.x + 10, panel_rect.y + 40),
            (panel_rect.right - 10, panel_rect.y + 40)
        )
        
        # Scrollable content area
        content_rect = Rect(
            panel_rect.x + HELP_CONTENT_PADDING,
            panel_rect.y + HELP_TITLE_HEIGHT + HELP_CONTENT_PADDING,
            panel_rect.w - HELP_SCROLLBAR_WIDTH - HELP_CONTENT_PADDING,
            panel_rect.h - HELP_TITLE_HEIGHT - HELP_FOOTER_HEIGHT - HELP_CONTENT_PADDING
        )
        
        # Calculate total content height
        help_sections = [
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
                ("Info button (top-right)", "Toggle this help panel"),
            ]),
        ]
        
        # Calculate content height
        self._help_content_height = 0
        for section_title, items in help_sections:
            self._help_content_height += 25  # Section header
            self._help_content_height += len(items) * 20 + 10  # Items + spacing
        
        # Set up clipping for scrollable content
        old_clip = screen.get_clip()
        screen.set_clip(content_rect)
        
        # Draw content with scrolling offset
        y = content_rect.y - self._help_scroll
        for section_title, items in help_sections:
            # Section header
            header = self._font_sm.render(section_title, True, _COLORS["polygon_fill"])
            screen.blit(header, (content_rect.x + 10, y))
            y += 22
            
            for key, desc in items:
                # Key with background
                key_surf = self._font_sm.render(key, True, _COLORS["vertex_first"])
                key_x = content_rect.x + 10
                key_bg = Rect(key_x, y - 2, key_surf.get_width() + 10, key_surf.get_height() + 4)
                pygame.draw.rect(screen, (*_COLORS["bg"], 180), key_bg, border_radius=3)
                screen.blit(key_surf, (key_x + 5, y))
                
                # Description - starts after key with some spacing
                desc_x = key_x + key_bg.width + 8
                desc_surf = self._font_sm.render(desc, True, _COLORS["text"])
                screen.blit(desc_surf, (desc_x, y))
                y += 20
            
            y += 12
        
        screen.set_clip(old_clip)
        
        # Draw scrollbar (if content is longer than view)
        scrollbar_rect = Rect(
            panel_rect.right - 20,
            content_rect.y,
            12,
            content_rect.h
        )
        
        # Scrollbar track
        pygame.draw.rect(screen, (*_COLORS["bg"], 100), scrollbar_rect, border_radius=6)
        
        # Calculate scrollbar thumb
        if self._help_content_height > content_rect.h:
            thumb_height = max(HELP_THUMB_MIN_HEIGHT, int(content_rect.h * content_rect.h / self._help_content_height))
            thumb_y = content_rect.y + int((self._help_scroll / max(1, self._help_content_height - content_rect.h)) * (content_rect.h - thumb_height))
            thumb_rect = Rect(scrollbar_rect.x, thumb_y, 12, thumb_height)
            
            # Scrollbar thumb
            thumb_color = _COLORS["polygon_fill"] if scrollbar_rect.collidepoint(mouse) else _COLORS["border_soft"]
            pygame.draw.rect(screen, thumb_color, thumb_rect, border_radius=6)
        
        # Footer hint
        footer_y = panel_rect.bottom - 30
        footer_hint = self._font_sm.render("Scroll to view all shortcuts", True, _COLORS["text_dim"])
        screen.blit(footer_hint, (panel_rect.x + 15, footer_y))
    
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
