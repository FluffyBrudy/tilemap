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
        self._pan_start = (0, 0)
        self._pan_start_offset = (0.0, 0.0)
        
        # Settings
        self.show_grid = True
        self.grid_size = 8
        
        # Fonts
        self._font: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None
        
        # Center the sprite
        self._center_view()
    
    def _center_view(self) -> None:
        """Center the sprite in the viewport"""
        sw, sh = self.sprite_surface.get_size()
        self.offset_x = (self.rect.w - sw * self.zoom) / 2
        self.offset_y = (self.rect.h - sh * self.zoom) / 2
    
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
    
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle input events"""
        mouse = pygame.mouse.get_pos()
        
        if not self.rect.collidepoint(mouse) and event.type not in (
            pygame.MOUSEBUTTONUP,
            pygame.MOUSEMOTION,
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
            
            # Update hover state
            if self.rect.collidepoint(mouse):
                self.hover_handle = self._find_handle_at(mouse)
            
            # Drag handle
            if self.dragging_handle:
                self._drag_handle(mouse)
                return True
        
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
                # Check if clicking on handle
                handle = self._find_handle_at(mouse)
                if handle:
                    self.dragging_handle = handle
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
            if event.key == pygame.K_g:
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
                self.rect_x = max(0, min(sw, sprite_pos[0]))
                self.rect_y = max(0, min(sh, sprite_pos[1]))
            elif self.dragging_handle == "tr":
                self.rect_w = max(1, sprite_pos[0] - self.rect_x)
                self.rect_y = max(0, min(sh, sprite_pos[1]))
            elif self.dragging_handle == "bl":
                self.rect_x = max(0, min(sw, sprite_pos[0]))
                self.rect_h = max(1, sprite_pos[1] - self.rect_y)
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
                self.capsule_y = max(0, min(sh, sprite_pos[1]))
            elif self.dragging_handle == "bottom":
                self.capsule_height = max(1, sprite_pos[1] - self.capsule_y)
            elif self.dragging_handle == "radius":
                self.capsule_radius = max(1, abs(sprite_pos[0] - self.capsule_x))
    
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
        lines.append(f"Shape: {self.shape_type.upper()} | Zoom: {self.zoom:.1f}x")
        
        if self.shape_type == "polygon":
            if self.current_polygon:
                lines.append(f"Drawing: {len(self.current_polygon)} vertices (right-click to complete)")
            elif self.polygon_vertices:
                lines.append(f"Polygon: {len(self.polygon_vertices)} vertices")
            else:
                lines.append("Click to add vertices")
        
        lines.append("G: toggle grid | R: reset view | Mouse wheel: zoom")
        
        y = self.rect.y + 5
        for line in lines:
            surf = self._font_sm.render(line, True, _COLORS["text"])
            bg_rect = Rect(self.rect.x + 5, y, surf.get_width() + 4, surf.get_height() + 2)
            bg = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 180))
            screen.blit(bg, bg_rect.topleft)
            screen.blit(surf, (self.rect.x + 7, y + 1))
            y += surf.get_height() + 3
