"""
Shape Editor Widget - Visual editor for collision shapes.

Supports:
- Rectangle: Click and drag to define bounds
- Circle: Click center, drag to set radius
- Capsule: Click and drag to define height, radius adjustable
- Polygon: Click to add vertices (like tileset collision painter)
"""

from __future__ import annotations

import math
from typing import List, Tuple, Optional, Literal
from enum import Enum

import pygame
from pygame import Rect
from utils.font_manager import font_manager, FontWeight
from utils.error_handler import error_handler
from utils.icon_manager import icon_manager


ShapeType = Literal["rectangle", "circle", "capsule", "polygon"]


# Theme colors
_COLORS = {
    "bg": (25, 27, 30),
    "shape_fill": (80, 180, 255),
    "shape_stroke": (100, 200, 255),
    "shape_selected": (255, 180, 80),
    "handle": (255, 255, 255),
    "handle_hover": (255, 220, 80),
    "text": (230, 230, 230),
    "text_dim": (140, 140, 140),
    "grid": (255, 255, 255),
}


class ShapeEditor:
    """Visual editor for collision shapes on a character sprite."""

    def __init__(
        self,
        rect: Rect,
        sprite_surface: pygame.Surface,
    ):
        self.rect = rect
        self.sprite_surface = sprite_surface
        
        # Current shape
        self.shape_type: ShapeType = "rectangle"
        self.shape_data: dict = {}
        
        # Rectangle shape
        self.rect_x: float = 0
        self.rect_y: float = 0
        self.rect_w: float = 32
        self.rect_h: float = 32
        
        # Circle shape
        self.circle_x: float = 16
        self.circle_y: float = 16
        self.circle_radius: float = 16
        
        # Capsule shape
        self.capsule_x: float = 16
        self.capsule_y: float = 8
        self.capsule_height: float = 16
        self.capsule_radius: float = 8
        
        # Polygon shape
        self.polygon_vertices: List[Tuple[float, float]] = []
        self.current_polygon: List[Tuple[float, float]] = []
        
        # View state
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        self.zoom: float = 3.0
        
        # Interaction
        self.dragging_handle: Optional[str] = None
        self.hover_handle: Optional[str] = None
        self._panning = False
        self._pan_mode = False
        self._pan_start = (0, 0)
        self._pan_start_offset = (0.0, 0.0)
        self._move_icon_pos: Tuple[int, int] = (0, 0)
        self._move_icon_hover = False
        self._dragging_shape = False
        self._drag_start = (0, 0)
        self._drag_start_positions: dict = {}
        
        # Settings
        self.show_grid = True
        self.grid_size = 8
        
        # Fonts
        self._font: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None
        
        # Center the sprite
        self._center_view()
        self._center_shape()
    
    def _center_view(self) -> None:
        """Center the sprite in the viewport"""
        sw, sh = self.sprite_surface.get_size()
        self.offset_x = (self.rect.w - sw * self.zoom) / 2
        self.offset_y = (self.rect.h - sh * self.zoom) / 2
    
    def _center_shape(self) -> None:
        """Center all shape types on the sprite"""
        sw, sh = self.sprite_surface.get_size()
        
        # Rectangle: 50% of sprite, centered
        self.rect_w = sw * 0.5
        self.rect_h = sh * 0.5
        self.rect_x = (sw - self.rect_w) / 2
        self.rect_y = (sh - self.rect_h) / 2
        
        # Circle: 25% of min dimension, centered
        self.circle_radius = min(sw, sh) * 0.25
        self.circle_x = sw / 2
        self.circle_y = sh / 2
        
        # Capsule: 50% height, 15% width radius, centered
        self.capsule_height = sh * 0.5
        self.capsule_radius = sw * 0.15
        self.capsule_x = sw / 2
        self.capsule_y = (sh - self.capsule_height) / 2
    
    def _ensure_fonts(self) -> None:
        """Initialize fonts"""
        if self._font is None:
            self._font = font_manager.get_font("Arial", 13, FontWeight.REGULAR)
        if self._font_sm is None:
            self._font_sm = font_manager.get_font("Arial", 11, FontWeight.REGULAR)
    
    def _screen_to_sprite(self, screen_pos: Tuple[int, int]) -> Tuple[float, float]:
        """Convert screen coordinates to sprite-local coordinates"""
        x = (screen_pos[0] - self.rect.x - self.offset_x) / self.zoom
        y = (screen_pos[1] - self.rect.y - self.offset_y) / self.zoom
        return (x, y)
    
    def _sprite_to_screen(self, sprite_pos: Tuple[float, float]) -> Tuple[int, int]:
        """Convert sprite-local coordinates to screen coordinates"""
        x = int(self.rect.x + self.offset_x + sprite_pos[0] * self.zoom)
        y = int(self.rect.y + self.offset_y + sprite_pos[1] * self.zoom)
        return (x, y)
    
    def set_shape_type(self, shape_type: ShapeType) -> None:
        """Change the shape type"""
        self.shape_type = shape_type
        if shape_type == "polygon":
            self.current_polygon = []
    
    def get_shape_data(self) -> dict:
        """Get the current shape data"""
        if self.shape_type == "rectangle":
            return {
                "type": "rectangle",
                "width": self.rect_w,
                "height": self.rect_h,
                "offset": (self.rect_x, self.rect_y),
            }
        elif self.shape_type == "circle":
            return {
                "type": "circle",
                "radius": self.circle_radius,
                "offset": (self.circle_x, self.circle_y),
            }
        elif self.shape_type == "capsule":
            return {
                "type": "capsule",
                "radius": self.capsule_radius,
                "height": self.capsule_height,
                "offset": (self.capsule_x, self.capsule_y),
            }
        elif self.shape_type == "polygon":
            return {
                "type": "polygon",
                "vertices": self.polygon_vertices,
                "offset": (0.0, 0.0),
            }
        return {}
    
    def load_shape_data(self, data: dict) -> None:
        """Load shape data"""
        shape_type = data.get("type", "rectangle")
        self.shape_type = shape_type
        
        if shape_type == "rectangle":
            self.rect_w = data.get("width", 32)
            self.rect_h = data.get("height", 32)
            offset = data.get("offset", (0, 0))
            self.rect_x, self.rect_y = offset
        elif shape_type == "circle":
            self.circle_radius = data.get("radius", 16)
            offset = data.get("offset", (16, 16))
            self.circle_x, self.circle_y = offset
        elif shape_type == "capsule":
            self.capsule_radius = data.get("radius", 8)
            self.capsule_height = data.get("height", 16)
            offset = data.get("offset", (16, 8))
            self.capsule_x, self.capsule_y = offset
        elif shape_type == "polygon":
            self.polygon_vertices = [tuple(v) for v in data.get("vertices", [])]
    
    def resize(self, rect: Rect) -> None:
        """Update rect"""
        self.rect = rect
        self._center_view()
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle input events"""
        mouse = pygame.mouse.get_pos()
        
        if not self.rect.collidepoint(mouse) and event.type not in (
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
            pygame.KEYDOWN,
        ):
            return False
        
        # Middle mouse to pan
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
            
            # Drag handle — always takes priority over shape drag
            if self.dragging_handle:
                self._drag_handle(mouse)
                return True
            
            # Drag entire shape via move icon
            if self._dragging_shape:
                dx = (mouse[0] - self._drag_start[0]) / self.zoom
                dy = (mouse[1] - self._drag_start[1]) / self.zoom
                self._apply_shape_delta(dx, dy)
                return True
            
            # Update hover state
            if self.rect.collidepoint(mouse):
                handle = self._find_handle_at(mouse)
                if handle:
                    self.hover_handle = handle
                else:
                    self.hover_handle = None
        
        # Mouse wheel to zoom
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(mouse):
            old_zoom = self.zoom
            self.zoom *= 1.15 if event.y > 0 else 0.87
            self.zoom = max(0.5, min(self.zoom, 8.0))
            
            # Zoom toward mouse
            sprite_pos = self._screen_to_sprite(mouse)
            self.offset_x = mouse[0] - self.rect.x - sprite_pos[0] * self.zoom
            self.offset_y = mouse[1] - self.rect.y - sprite_pos[1] * self.zoom
            return True
        
        # Left click
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse):
                # Pan mode — start dragging
                if self._pan_mode:
                    self._panning = True
                    self._pan_start = mouse
                    self._pan_start_offset = (self.offset_x, self.offset_y)
                    return True
                
                # Check if clicking on handle
                handle = self._find_handle_at(mouse)
                if handle:
                    self.dragging_handle = handle
                    self._dragging_shape = False
                    return True
                
                # Check if clicking inside the shape body (but not on a handle)
                if self._is_inside_shape(mouse) and not self._pan_mode:
                    self._dragging_shape = True
                    self._drag_start = mouse
                    self._save_shape_positions()
                    return True
                
                # Polygon mode - add vertex
                if self.shape_type == "polygon":
                    sprite_pos = self._screen_to_sprite(mouse)
                    sw, sh = self.sprite_surface.get_size()
                    sprite_pos = (
                        max(0, min(sw, sprite_pos[0])),
                        max(0, min(sh, sprite_pos[1]))
                    )
                    self.current_polygon.append(sprite_pos)
                    return True
        
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._panning:
                self._panning = False
                return True
            if self._dragging_shape:
                self._dragging_shape = False
                return True
            if self.dragging_handle:
                self.dragging_handle = None
                return True
        
        # Right click - complete polygon
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.rect.collidepoint(mouse) and self.shape_type == "polygon":
                if len(self.current_polygon) >= 3:
                    self.polygon_vertices = list(self.current_polygon)
                    self.current_polygon = []
                    return True
        
        # Keyboard shortcuts
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self._pan_mode = not self._pan_mode
                if self._pan_mode:
                    self._pan_start = mouse
                    self._pan_start_offset = (self.offset_x, self.offset_y)
                return True
            elif event.key == pygame.K_g:
                self.show_grid = not self.show_grid
                return True
            elif event.key == pygame.K_r:
                self._center_view()
                self.zoom = 3.0
                return True
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if self.shape_type == "polygon" and len(self.current_polygon) >= 3:
                    self.polygon_vertices = list(self.current_polygon)
                    self.current_polygon = []
                    return True
            elif event.key == pygame.K_ESCAPE:
                if self.shape_type == "polygon":
                    self.current_polygon = []
                    return True
        
        return False
    
    def _find_handle_at(self, screen_pos: Tuple[int, int]) -> Optional[str]:
        """Find handle at screen position"""
        HANDLE_SIZE = 8
        
        if self.shape_type == "rectangle":
            # Corner handles
            corners = {
                "tl": (self.rect_x, self.rect_y),
                "tr": (self.rect_x + self.rect_w, self.rect_y),
                "bl": (self.rect_x, self.rect_y + self.rect_h),
                "br": (self.rect_x + self.rect_w, self.rect_y + self.rect_h),
            }
            for name, pos in corners.items():
                screen_corner = self._sprite_to_screen(pos)
                if math.hypot(screen_pos[0] - screen_corner[0], screen_pos[1] - screen_corner[1]) <= HANDLE_SIZE:
                    return name
        
        elif self.shape_type == "circle":
            # Center and radius handles
            center_screen = self._sprite_to_screen((self.circle_x, self.circle_y))
            if math.hypot(screen_pos[0] - center_screen[0], screen_pos[1] - center_screen[1]) <= HANDLE_SIZE:
                return "center"
            
            radius_point = (self.circle_x + self.circle_radius, self.circle_y)
            radius_screen = self._sprite_to_screen(radius_point)
            if math.hypot(screen_pos[0] - radius_screen[0], screen_pos[1] - radius_screen[1]) <= HANDLE_SIZE:
                return "radius"
        
        elif self.shape_type == "capsule":
            # Top, bottom, and radius handles
            top = (self.capsule_x, self.capsule_y)
            bottom = (self.capsule_x, self.capsule_y + self.capsule_height)
            
            top_screen = self._sprite_to_screen(top)
            if math.hypot(screen_pos[0] - top_screen[0], screen_pos[1] - top_screen[1]) <= HANDLE_SIZE:
                return "top"
            
            bottom_screen = self._sprite_to_screen(bottom)
            if math.hypot(screen_pos[0] - bottom_screen[0], screen_pos[1] - bottom_screen[1]) <= HANDLE_SIZE:
                return "bottom"
            
            radius_point = (self.capsule_x + self.capsule_radius, self.capsule_y + self.capsule_height / 2)
            radius_screen = self._sprite_to_screen(radius_point)
            if math.hypot(screen_pos[0] - radius_screen[0], screen_pos[1] - radius_screen[1]) <= HANDLE_SIZE:
                return "radius"
        
        return None
    
    def _drag_handle(self, mouse_pos: Tuple[int, int]) -> None:
        """Drag a handle"""
        sprite_pos = self._screen_to_sprite(mouse_pos)
        sw, sh = self.sprite_surface.get_size()
        
        if self.shape_type == "rectangle":
            if self.dragging_handle == "tl":
                old_right = self.rect_x + self.rect_w
                old_bottom = self.rect_y + self.rect_h
                self.rect_x = max(0, min(sw, sprite_pos[0]))
                self.rect_y = max(0, min(sh, sprite_pos[1]))
                self.rect_w = max(1, old_right - self.rect_x)
                self.rect_h = max(1, old_bottom - self.rect_y)
            elif self.dragging_handle == "tr":
                old_bottom = self.rect_y + self.rect_h
                self.rect_w = max(1, sprite_pos[0] - self.rect_x)
                self.rect_y = max(0, min(sh, sprite_pos[1]))
                self.rect_h = max(1, old_bottom - self.rect_y)
            elif self.dragging_handle == "bl":
                old_right = self.rect_x + self.rect_w
                self.rect_x = max(0, min(sw, sprite_pos[0]))
                self.rect_h = max(1, sprite_pos[1] - self.rect_y)
                self.rect_w = max(1, old_right - self.rect_x)
            elif self.dragging_handle == "br":
                self.rect_w = max(1, sprite_pos[0] - self.rect_x)
                self.rect_h = max(1, sprite_pos[1] - self.rect_y)
        
        elif self.shape_type == "circle":
            if self.dragging_handle == "center":
                self.circle_x = max(0, min(sw, sprite_pos[0]))
                self.circle_y = max(0, min(sh, sprite_pos[1]))
            elif self.dragging_handle == "radius":
                self.circle_radius = max(1, math.hypot(
                    sprite_pos[0] - self.circle_x,
                    sprite_pos[1] - self.circle_y
                ))
        
        elif self.shape_type == "capsule":
            if self.dragging_handle == "top":
                old_bottom = self.capsule_y + self.capsule_height
                self.capsule_y = max(0, min(sh, sprite_pos[1]))
                self.capsule_height = max(1, old_bottom - self.capsule_y)
            elif self.dragging_handle == "bottom":
                self.capsule_height = max(1, sprite_pos[1] - self.capsule_y)
            elif self.dragging_handle == "radius":
                self.capsule_radius = max(1, abs(sprite_pos[0] - self.capsule_x))
    
    def _get_move_icon_pos(self) -> Tuple[int, int]:
        """Get screen position for the move icon at mid-top of the shape"""
        if self.shape_type == "rectangle":
            mid_x = self.rect_x + self.rect_w / 2
            top_y = self.rect_y
            return self._sprite_to_screen((mid_x, top_y))
        elif self.shape_type == "circle":
            return self._sprite_to_screen((self.circle_x, self.circle_y - self.circle_radius))
        elif self.shape_type == "capsule":
            return self._sprite_to_screen((self.capsule_x, self.capsule_y + self.capsule_height / 2))
        elif self.shape_type == "polygon" and len(self.polygon_vertices) >= 3:
            # Top-center of polygon bounding box
            min_y = min(v[1] for v in self.polygon_vertices)
            mid_x = (min(v[0] for v in self.polygon_vertices) + max(v[0] for v in self.polygon_vertices)) / 2
            return self._sprite_to_screen((mid_x, min_y))
        return (0, 0)
    
    def _is_on_move_icon(self, screen_pos: Tuple[int, int]) -> bool:
        """Check if a screen position is on the move icon (16x16 hit area)"""
        icon_pos = self._get_move_icon_pos()
        self._move_icon_pos = icon_pos
        hit_size = 16
        half = hit_size // 2
        return (icon_pos[0] - half <= screen_pos[0] <= icon_pos[0] + half and
                icon_pos[1] - half <= screen_pos[1] <= icon_pos[1] + half)
    
    def _is_inside_shape(self, screen_pos: Tuple[int, int]) -> bool:
        """Check if a screen position is inside the current shape (for hover detection)"""
        if self.shape_type == "rectangle":
            tl = self._sprite_to_screen((self.rect_x, self.rect_y))
            br = self._sprite_to_screen((self.rect_x + self.rect_w, self.rect_y + self.rect_h))
            return (tl[0] <= screen_pos[0] <= br[0] and tl[1] <= screen_pos[1] <= br[1])
        
        elif self.shape_type == "circle":
            center = self._sprite_to_screen((self.circle_x, self.circle_y))
            radius = int(self.circle_radius * self.zoom)
            return math.hypot(screen_pos[0] - center[0], screen_pos[1] - center[1]) <= radius
        
        elif self.shape_type == "capsule":
            top = self._sprite_to_screen((self.capsule_x, self.capsule_y))
            bottom = self._sprite_to_screen((self.capsule_x, self.capsule_y + self.capsule_height))
            radius = int(self.capsule_radius * self.zoom)
            if math.hypot(screen_pos[0] - top[0], screen_pos[1] - top[1]) <= radius:
                return True
            if math.hypot(screen_pos[0] - bottom[0], screen_pos[1] - bottom[1]) <= radius:
                return True
            left = top[0] - radius
            right = top[0] + radius
            return left <= screen_pos[0] <= right and top[1] <= screen_pos[1] <= bottom[1]
        
        elif self.shape_type == "polygon" and len(self.polygon_vertices) >= 3:
            px, py = self._screen_to_sprite(screen_pos)
            n = len(self.polygon_vertices)
            inside = False
            j = n - 1
            for i in range(n):
                vi = self.polygon_vertices[i]
                vj = self.polygon_vertices[j]
                if ((vi[1] > py) != (vj[1] > py)) and (
                    px < (vj[0] - vi[0]) * (py - vi[1]) / (vj[1] - vi[1]) + vi[0]
                ):
                    inside = not inside
                j = i
            return inside
        
        return False
    
    def _save_shape_positions(self) -> None:
        """Store current shape positions for delta calculation"""
        self._drag_start_positions = {
            "rect": (self.rect_x, self.rect_y),
            "circle": (self.circle_x, self.circle_y),
            "capsule": (self.capsule_x, self.capsule_y),
        }
    
    def _apply_shape_delta(self, dx: float, dy: float) -> None:
        """Move shape by delta in sprite-local coordinates"""
        sw, sh = self.sprite_surface.get_size()
        if self.shape_type == "rectangle":
            self.rect_x = max(0, min(sw - self.rect_w, self._drag_start_positions["rect"][0] + dx))
            self.rect_y = max(0, min(sh - self.rect_h, self._drag_start_positions["rect"][1] + dy))
        elif self.shape_type == "circle":
            self.circle_x = max(0, min(sw, self._drag_start_positions["circle"][0] + dx))
            self.circle_y = max(0, min(sh, self._drag_start_positions["circle"][1] + dy))
        elif self.shape_type == "capsule":
            self.capsule_x = max(0, min(sw, self._drag_start_positions["capsule"][0] + dx))
            self.capsule_y = max(0, min(sh - self.capsule_height, self._drag_start_positions["capsule"][1] + dy))
    
    def draw(self, screen: pygame.Surface) -> None:
        """Draw the shape editor"""
        self._ensure_fonts()
        
        clip = screen.get_clip()
        screen.set_clip(self.rect)
        
        # Background
        screen.fill(_COLORS["bg"], self.rect)
        
        # Draw sprite
        sw, sh = self.sprite_surface.get_size()
        scaled_w = int(sw * self.zoom)
        scaled_h = int(sh * self.zoom)
        
        if scaled_w > 0 and scaled_h > 0:
            sprite_x = int(self.rect.x + self.offset_x)
            sprite_y = int(self.rect.y + self.offset_y)
            scaled = pygame.transform.scale(self.sprite_surface, (scaled_w, scaled_h))
            screen.blit(scaled, (sprite_x, sprite_y))
            
            # Draw sprite border
            sprite_rect = Rect(sprite_x, sprite_y, scaled_w, scaled_h)
            pygame.draw.rect(screen, (100, 100, 100), sprite_rect, 1)
        
        # Draw grid
        if self.show_grid:
            self._draw_grid(screen, sw, sh)
        
        # Draw shape
        self._draw_shape(screen)
        
        # Draw move icon at mid-top when hovering over shape body
        if not self._pan_mode and not self.hover_handle:
            mouse = pygame.mouse.get_pos()
            if self.rect.collidepoint(mouse) and self._is_inside_shape(mouse):
                icon_pos = self._get_move_icon_pos()
                icon = icon_manager.get_icon("ToolMove", 16, _COLORS["shape_stroke"])
                screen.blit(icon, (icon_pos[0] - 8, icon_pos[1] - 8))
        
        # Draw status
        self._draw_status(screen)
        
        screen.set_clip(clip)
    
    def _draw_grid(self, screen: pygame.Surface, sw: int, sh: int) -> None:
        """Draw grid overlay"""
        sprite_x = int(self.rect.x + self.offset_x)
        sprite_y = int(self.rect.y + self.offset_y)
        scaled_w = int(sw * self.zoom)
        scaled_h = int(sh * self.zoom)
        
        grid_surf = pygame.Surface((scaled_w, scaled_h), pygame.SRCALPHA)
        
        for x in range(0, sw + 1, self.grid_size):
            sx = int(x * self.zoom)
            pygame.draw.line(grid_surf, (*_COLORS["grid"], 30), (sx, 0), (sx, scaled_h))
        
        for y in range(0, sh + 1, self.grid_size):
            sy = int(y * self.zoom)
            pygame.draw.line(grid_surf, (*_COLORS["grid"], 30), (0, sy), (scaled_w, sy))
        
        screen.blit(grid_surf, (sprite_x, sprite_y))
    
    def _draw_shape(self, screen: pygame.Surface) -> None:
        """Draw the collision shape"""
        if self.shape_type == "rectangle":
            self._draw_rectangle(screen)
        elif self.shape_type == "circle":
            self._draw_circle(screen)
        elif self.shape_type == "capsule":
            self._draw_capsule(screen)
        elif self.shape_type == "polygon":
            self._draw_polygon(screen)
    
    def _draw_rectangle(self, screen: pygame.Surface) -> None:
        """Draw rectangle shape"""
        tl = self._sprite_to_screen((self.rect_x, self.rect_y))
        br = self._sprite_to_screen((self.rect_x + self.rect_w, self.rect_y + self.rect_h))
        
        rect = Rect(tl[0], tl[1], br[0] - tl[0], br[1] - tl[1])
        
        # Fill
        surf = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        surf.fill((*_COLORS["shape_fill"], 80))
        screen.blit(surf, rect.topleft)
        
        # Stroke
        pygame.draw.rect(screen, _COLORS["shape_stroke"], rect, 2)
        
        # Handles
        corners = [
            self._sprite_to_screen((self.rect_x, self.rect_y)),
            self._sprite_to_screen((self.rect_x + self.rect_w, self.rect_y)),
            self._sprite_to_screen((self.rect_x, self.rect_y + self.rect_h)),
            self._sprite_to_screen((self.rect_x + self.rect_w, self.rect_y + self.rect_h)),
        ]
        for corner in corners:
            pygame.draw.circle(screen, _COLORS["handle"], corner, 6)
            pygame.draw.circle(screen, (0, 0, 0), corner, 6, 1)
    
    def _draw_circle(self, screen: pygame.Surface) -> None:
        """Draw circle shape"""
        center = self._sprite_to_screen((self.circle_x, self.circle_y))
        radius = int(self.circle_radius * self.zoom)
        
        # Fill
        surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (*_COLORS["shape_fill"], 80), (radius, radius), radius)
        screen.blit(surf, (center[0] - radius, center[1] - radius))
        
        # Stroke
        pygame.draw.circle(screen, _COLORS["shape_stroke"], center, radius, 2)
        
        # Handles
        pygame.draw.circle(screen, _COLORS["handle"], center, 6)
        pygame.draw.circle(screen, (0, 0, 0), center, 6, 1)
        
        radius_point = self._sprite_to_screen((self.circle_x + self.circle_radius, self.circle_y))
        pygame.draw.circle(screen, _COLORS["handle"], radius_point, 6)
        pygame.draw.circle(screen, (0, 0, 0), radius_point, 6, 1)
    
    def _draw_capsule(self, screen: pygame.Surface) -> None:
        """Draw capsule shape"""
        top = self._sprite_to_screen((self.capsule_x, self.capsule_y))
        bottom = self._sprite_to_screen((self.capsule_x, self.capsule_y + self.capsule_height))
        radius = int(self.capsule_radius * self.zoom)
        
        # Draw capsule (two circles + rectangle)
        pygame.draw.circle(screen, _COLORS["shape_fill"], top, radius)
        pygame.draw.circle(screen, _COLORS["shape_fill"], bottom, radius)
        
        rect = Rect(top[0] - radius, top[1], radius * 2, bottom[1] - top[1])
        pygame.draw.rect(screen, _COLORS["shape_fill"], rect)
        
        # Stroke
        pygame.draw.circle(screen, _COLORS["shape_stroke"], top, radius, 2)
        pygame.draw.circle(screen, _COLORS["shape_stroke"], bottom, radius, 2)
        pygame.draw.line(screen, _COLORS["shape_stroke"], (top[0] - radius, top[1]), (bottom[0] - radius, bottom[1]), 2)
        pygame.draw.line(screen, _COLORS["shape_stroke"], (top[0] + radius, top[1]), (bottom[0] + radius, bottom[1]), 2)
        
        # Handles
        pygame.draw.circle(screen, _COLORS["handle"], top, 6)
        pygame.draw.circle(screen, (0, 0, 0), top, 6, 1)
        pygame.draw.circle(screen, _COLORS["handle"], bottom, 6)
        pygame.draw.circle(screen, (0, 0, 0), bottom, 6, 1)
        
        mid_y = (top[1] + bottom[1]) // 2
        radius_point = (top[0] + radius, mid_y)
        pygame.draw.circle(screen, _COLORS["handle"], radius_point, 6)
        pygame.draw.circle(screen, (0, 0, 0), radius_point, 6, 1)
    
    def _draw_polygon(self, screen: pygame.Surface) -> None:
        """Draw polygon shape"""
        # Draw completed polygon
        if len(self.polygon_vertices) >= 3:
            screen_points = [self._sprite_to_screen(p) for p in self.polygon_vertices]
            pygame.draw.polygon(screen, (*_COLORS["shape_fill"], 80), screen_points)
            pygame.draw.polygon(screen, _COLORS["shape_stroke"], screen_points, 2)
            
            for point in screen_points:
                pygame.draw.circle(screen, _COLORS["handle"], point, 5)
                pygame.draw.circle(screen, (0, 0, 0), point, 5, 1)
        
        # Draw current polygon being drawn
        if self.current_polygon:
            screen_points = [self._sprite_to_screen(p) for p in self.current_polygon]
            if len(screen_points) > 1:
                pygame.draw.lines(screen, (200, 200, 200), False, screen_points, 2)
            
            for i, point in enumerate(screen_points):
                color = (80, 255, 120) if i == 0 else _COLORS["handle"]
                pygame.draw.circle(screen, color, point, 5)
                pygame.draw.circle(screen, (0, 0, 0), point, 5, 1)
    
    def _draw_status(self, screen: pygame.Surface) -> None:
        """Draw status text"""
        lines = []
        
        if self._pan_mode:
            lines.append("PANNING MODE — drag to pan | Space to exit")
        
        lines.append(f"Shape: {self.shape_type.upper()} | Zoom: {self.zoom:.1f}x")
        
        if self.shape_type == "polygon":
            if self.current_polygon:
                lines.append(f"Drawing: {len(self.current_polygon)} vertices (right-click to complete)")
            elif self.polygon_vertices:
                lines.append(f"Polygon: {len(self.polygon_vertices)} vertices")
            else:
                lines.append("Click to add vertices")
        
        lines.append("G: toggle grid | R: reset view | Space: pan mode | Wheel: zoom")
        
        y = self.rect.y + 5
        for line in lines:
            surf = self._font_sm.render(line, True, _COLORS["text"])
            bg_rect = Rect(self.rect.x + 5, y, surf.get_width() + 4, surf.get_height() + 2)
            bg = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 180))
            screen.blit(bg, bg_rect.topleft)
            screen.blit(surf, (self.rect.x + 7, y + 1))
            y += surf.get_height() + 3
