"""
Region Selector — Reusable component for drawing/selecting rectangular regions on an image.

Features:
- Drag to create new regions
- Click to select regions
- Drag selected region to move
- Drag handles to resize
- Delete key to remove selected region
- Visual feedback: hover highlights, selection border, size tooltip
"""

from __future__ import annotations

import math
from typing import List, Tuple, Optional, Callable, Dict, Any
from enum import Enum, auto
from dataclasses import dataclass

import pygame
from pygame import Rect, Surface

from widgets.ui.theme import COLORS, SHAPE
from utils.font_manager import font_manager, FontWeight


class ResizeHandle(Enum):
    """Resize handle positions"""

    NONE = auto()
    TOP_LEFT = auto()
    TOP = auto()
    TOP_RIGHT = auto()
    LEFT = auto()
    RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM = auto()
    BOTTOM_RIGHT = auto()


@dataclass
class Region:
    """A rectangular region with ID and optional name"""

    id: str
    rect: Rect
    name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rect": [self.rect.x, self.rect.y, self.rect.width, self.rect.height],
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Region":
        r = data.get("rect", [0, 0, 32, 32])
        return cls(
            id=data.get("id", ""),
            rect=Rect(r[0], r[1], r[2], r[3]),
            name=data.get("name", ""),
        )


class RegionSelector:
    """
    Component for selecting and editing rectangular regions on an image.

    Similar to Godot's SpriteRegion editor or TexturePacker.
    """

    HANDLE_SIZE = 12
    MIN_REGION_SIZE = 8
    SELECTION_BORDER_WIDTH = 2
    HOVER_ALPHA = 80

    def __init__(
        self,
        rect: Rect,
        image: Optional[Surface] = None,
        zoom: float = 1.0,
    ):
        self.rect = rect
        self.image = image
        self.zoom = zoom

        self.regions: List[Region] = []
        self.selected_id: Optional[str] = None

        self._hover_region_id: Optional[str] = None
        self._hover_handle = ResizeHandle.NONE
        self._dragging = False
        self._drag_start_mouse: Tuple[int, int] = (0, 0)
        self._drag_start_rect: Rect = Rect(0, 0, 0, 0)
        self._creating = False
        self._create_start: Tuple[int, int] = (0, 0)
        self._resizing = False

        self.scroll_x = 0
        self.scroll_y = 0
        self._panning = False
        self._pan_mode = False
        self._pan_start: Tuple[int, int] = (0, 0)
        self._pan_start_scroll: Tuple[int, int] = (0, 0)

        self._font = font_manager.get_font("Arial", 11, FontWeight.REGULAR)
        self._font_sm = font_manager.get_font("Arial", 10, FontWeight.REGULAR)

        self.on_region_added: Optional[Callable[[Region], None]] = None
        self.on_region_removed: Optional[Callable[[str], None]] = None
        self.on_region_modified: Optional[Callable[[Region], None]] = None
        self.on_selection_changed: Optional[Callable[[Optional[str]], None]] = None

    def _image_to_screen(self, x: int, y: int) -> Tuple[int, int]:
        """Convert image coordinates to screen coordinates"""
        return (
            self.rect.x + int(x * self.zoom) - self.scroll_x,
            self.rect.y + int(y * self.zoom) - self.scroll_y,
        )

    def _screen_to_image(self, x: int, y: int) -> Tuple[int, int]:
        """Convert screen coordinates to image coordinates"""
        return (
            int((x - self.rect.x + self.scroll_x) / self.zoom),
            int((y - self.rect.y + self.scroll_y) / self.zoom),
        )

    def _clamp_scroll(self) -> None:
        """Clamp scroll values to keep image visible within viewport"""
        if not self.image:
            self.scroll_x = 0
            self.scroll_y = 0
            return

        img_w = int(self.image.get_width() * self.zoom)
        img_h = int(self.image.get_height() * self.zoom)
        vp_w = self.rect.width
        vp_h = self.rect.height

        if img_w <= vp_w:
            self.scroll_x = 0
        else:
            self.scroll_x = max(0, min(self.scroll_x, img_w - vp_w))

        if img_h <= vp_h:
            self.scroll_y = 0
        else:
            self.scroll_y = max(0, min(self.scroll_y, img_h - vp_h))

    def _get_region_screen_rect(self, region: Region) -> Rect:
        """Get region rect in screen coordinates"""
        x, y = self._image_to_screen(region.rect.x, region.rect.y)
        w = int(region.rect.width * self.zoom)
        h = int(region.rect.height * self.zoom)
        return Rect(x, y, w, h)

    def _get_handle_rects(self, region: Region) -> Dict[ResizeHandle, Rect]:
        """Get resize handle rects in screen coordinates"""
        r = self._get_region_screen_rect(region)
        hs = self.HANDLE_SIZE
        hs2 = hs // 2

        return {
            ResizeHandle.TOP_LEFT: Rect(r.x - hs2, r.y - hs2, hs, hs),
            ResizeHandle.TOP: Rect(r.centerx - hs2, r.y - hs2, hs, hs),
            ResizeHandle.TOP_RIGHT: Rect(r.right - hs2, r.y - hs2, hs, hs),
            ResizeHandle.LEFT: Rect(r.x - hs2, r.centery - hs2, hs, hs),
            ResizeHandle.RIGHT: Rect(r.right - hs2, r.centery - hs2, hs, hs),
            ResizeHandle.BOTTOM_LEFT: Rect(r.x - hs2, r.bottom - hs2, hs, hs),
            ResizeHandle.BOTTOM: Rect(r.centerx - hs2, r.bottom - hs2, hs, hs),
            ResizeHandle.BOTTOM_RIGHT: Rect(r.right - hs2, r.bottom - hs2, hs, hs),
        }

    def _get_handle_at(
        self, screen_pos: Tuple[int, int], region: Region
    ) -> ResizeHandle:
        """Get resize handle at screen position"""
        handles = self._get_handle_rects(region)
        for handle, rect in handles.items():
            if rect.collidepoint(screen_pos):
                return handle
        return ResizeHandle.NONE

    def _find_region_at(self, screen_pos: Tuple[int, int]) -> Optional[str]:
        """Find region ID at screen position (returns topmost)"""

        for region in reversed(self.regions):
            r = self._get_region_screen_rect(region)
            if r.collidepoint(screen_pos):
                return region.id
        return None

    def _generate_id(self) -> str:
        """Generate unique region ID"""
        import uuid

        return f"region_{uuid.uuid4().hex[:8]}"

    def _get_unique_name(self, base: str = "Region") -> str:
        """Generate unique region name"""
        existing = {r.name for r in self.regions}
        if base not in existing:
            return base
        counter = 2
        while f"{base} {counter}" in existing:
            counter += 1
        return f"{base} {counter}"

    def add_region(self, rect: Rect, name: str = "") -> Region:
        """Add a new region"""
        if not name:
            name = self._get_unique_name()

        region = Region(
            id=self._generate_id(),
            rect=rect,
            name=name,
        )
        self.regions.append(region)

        if self.on_region_added:
            self.on_region_added(region)

        return region

    def remove_region(self, region_id: str) -> bool:
        """Remove a region by ID"""
        for i, region in enumerate(self.regions):
            if region.id == region_id:
                self.regions.pop(i)
                if self.selected_id == region_id:
                    self.selected_id = None
                    if self.on_selection_changed:
                        self.on_selection_changed(None)
                if self.on_region_removed:
                    self.on_region_removed(region_id)
                return True
        return False

    def get_region(self, region_id: str) -> Optional[Region]:
        """Get region by ID"""
        for region in self.regions:
            if region.id == region_id:
                return region
        return None

    def get_selected_region(self) -> Optional[Region]:
        """Get currently selected region"""
        if self.selected_id:
            return self.get_region(self.selected_id)
        return None

    def select_region(self, region_id: Optional[str]) -> None:
        """Select a region by ID"""
        if region_id != self.selected_id:
            self.selected_id = region_id
            if self.on_selection_changed:
                self.on_selection_changed(region_id)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle input events.
        Returns True if event was handled (should not propagate).
        """
        mouse = pygame.mouse.get_pos()
        in_bounds = self.rect.collidepoint(mouse)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self._pan_mode = not self._pan_mode
                if not self._pan_mode and self._panning:
                    self._panning = False
                return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if (
                event.button == 1
                and hasattr(self, "_pan_btn_rect")
                and self._pan_btn_rect.collidepoint(mouse)
            ):
                self._pan_mode = not self._pan_mode
                if not self._pan_mode and self._panning:
                    self._panning = False
                return True

            if event.button == 2 or (event.button == 1 and self._pan_mode):
                self._panning = True
                self._pan_start = mouse
                self._pan_start_scroll = (self.scroll_x, self.scroll_y)
                return True

        if event.type == pygame.MOUSEBUTTONUP:
            if (
                event.button == 2 or (event.button == 1 and self._pan_mode)
            ) and self._panning:
                self._panning = False
                return True

        if event.type == pygame.MOUSEMOTION:
            if self._panning:
                dx = mouse[0] - self._pan_start[0]
                dy = mouse[1] - self._pan_start[1]
                self.scroll_x = self._pan_start_scroll[0] - dx
                self.scroll_y = self._pan_start_scroll[1] - dy
                self._clamp_scroll()
                return True

            if in_bounds:
                self._update_hover(mouse)

        if event.type == pygame.MOUSEWHEEL and in_bounds:
            old_zoom = self.zoom
            if event.y > 0:
                self.zoom = min(self.zoom * 1.15, 8.0)
            else:
                self.zoom = max(self.zoom * 0.87, 0.25)

            if self.image:
                img_x = (mouse[0] - self.rect.x + self.scroll_x) / old_zoom
                img_y = (mouse[1] - self.rect.y + self.scroll_y) / old_zoom
                self.scroll_x = int(img_x * self.zoom - (mouse[0] - self.rect.x))
                self.scroll_y = int(img_y * self.zoom - (mouse[1] - self.rect.y))
                self._clamp_scroll()
            return True

        if event.type == pygame.KEYDOWN:
            old_zoom = self.zoom
            if event.key == pygame.K_EQUALS or event.key == pygame.K_KP_PLUS:
                self.zoom = min(self.zoom * 1.15, 8.0)
            elif event.key == pygame.K_MINUS or event.key == pygame.K_KP_MINUS:
                self.zoom = max(self.zoom * 0.87, 0.25)
            else:
                return False

            if self.image:
                cx = self.rect.width // 2
                cy = self.rect.height // 2
                img_x = (cx + self.scroll_x) / old_zoom
                img_y = (cy + self.scroll_y) / old_zoom
                self.scroll_x = int(img_x * self.zoom - cx)
                self.scroll_y = int(img_y * self.zoom - cy)
                self._clamp_scroll()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not in_bounds:
                return False

            selected = self.get_selected_region()
            if selected:
                handle = self._get_handle_at(mouse, selected)
                if handle != ResizeHandle.NONE:
                    self._resizing = True
                    self._hover_handle = handle
                    self._drag_start_mouse = mouse
                    self._drag_start_rect = Rect(selected.rect)
                    return True

            hit_id = self._find_region_at(mouse)
            if hit_id:
                self.select_region(hit_id)
                self._dragging = True
                self._drag_start_mouse = mouse
                region = self.get_region(hit_id)
                if region:
                    self._drag_start_rect = Rect(region.rect)
                return True

            if self.image and self.rect.collidepoint(mouse) and not self._pan_mode:
                img_x, img_y = self._screen_to_image(mouse[0], mouse[1])
                img_w = self.image.get_width()
                img_h = self.image.get_height()
                if 0 <= img_x < img_w and 0 <= img_y < img_h:
                    self._creating = True
                    self._create_start = (img_x, img_y)
                    return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._creating:
                self._creating = False
                img_x, img_y = self._screen_to_image(mouse[0], mouse[1])
                x = min(self._create_start[0], img_x)
                y = min(self._create_start[1], img_y)
                w = abs(img_x - self._create_start[0])
                h = abs(img_y - self._create_start[1])

                if w >= self.MIN_REGION_SIZE and h >= self.MIN_REGION_SIZE:
                    if self.image:
                        img_w = self.image.get_width()
                        img_h = self.image.get_height()
                        x = max(0, min(x, img_w - w))
                        y = max(0, min(y, img_h - h))
                        w = min(w, img_w - x)
                        h = min(h, img_h - y)

                    region = self.add_region(Rect(x, y, w, h))
                    self.select_region(region.id)
                return True

            if self._dragging or self._resizing:
                if self._dragging:
                    self._dragging = False
                    region = self.get_selected_region()
                    if region and self.on_region_modified:
                        self.on_region_modified(region)

                if self._resizing:
                    self._resizing = False
                    self._hover_handle = ResizeHandle.NONE
                    region = self.get_selected_region()
                    if region and self.on_region_modified:
                        self.on_region_modified(region)

                return True

        if event.type == pygame.MOUSEMOTION:
            if self._dragging and self.selected_id:
                region = self.get_region(self.selected_id)
                if region:
                    dx = int((mouse[0] - self._drag_start_mouse[0]) / self.zoom)
                    dy = int((mouse[1] - self._drag_start_mouse[1]) / self.zoom)
                    region.rect.x = self._drag_start_rect.x + dx
                    region.rect.y = self._drag_start_rect.y + dy

                    if self.image:
                        img_w = self.image.get_width()
                        img_h = self.image.get_height()
                        region.rect.x = max(
                            0, min(region.rect.x, img_w - region.rect.width)
                        )
                        region.rect.y = max(
                            0, min(region.rect.y, img_h - region.rect.height)
                        )

                    return True

            if self._resizing and self.selected_id:
                region = self.get_region(self.selected_id)
                if region:
                    dx = int((mouse[0] - self._drag_start_mouse[0]) / self.zoom)
                    dy = int((mouse[1] - self._drag_start_mouse[1]) / self.zoom)

                    new_rect = Rect(self._drag_start_rect)

                    if self._hover_handle in (
                        ResizeHandle.LEFT,
                        ResizeHandle.TOP_LEFT,
                        ResizeHandle.BOTTOM_LEFT,
                    ):
                        new_rect.x += dx
                        new_rect.width -= dx
                    if self._hover_handle in (
                        ResizeHandle.RIGHT,
                        ResizeHandle.TOP_RIGHT,
                        ResizeHandle.BOTTOM_RIGHT,
                    ):
                        new_rect.width += dx
                    if self._hover_handle in (
                        ResizeHandle.TOP,
                        ResizeHandle.TOP_LEFT,
                        ResizeHandle.TOP_RIGHT,
                    ):
                        new_rect.y += dy
                        new_rect.height -= dy
                    if self._hover_handle in (
                        ResizeHandle.BOTTOM,
                        ResizeHandle.BOTTOM_LEFT,
                        ResizeHandle.BOTTOM_RIGHT,
                    ):
                        new_rect.height += dy

                    if (
                        new_rect.width >= self.MIN_REGION_SIZE
                        and new_rect.height >= self.MIN_REGION_SIZE
                    ):
                        if self.image:
                            img_w = self.image.get_width()
                            img_h = self.image.get_height()
                            new_rect.x = max(
                                0, min(new_rect.x, img_w - self.MIN_REGION_SIZE)
                            )
                            new_rect.y = max(
                                0, min(new_rect.y, img_h - self.MIN_REGION_SIZE)
                            )
                            new_rect.width = min(new_rect.width, img_w - new_rect.x)
                            new_rect.height = min(new_rect.height, img_h - new_rect.y)

                        region.rect = new_rect

                    return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                if self.selected_id:
                    self.remove_region(self.selected_id)
                    return True

        return False

    def _update_hover(self, mouse: Tuple[int, int]) -> None:
        """Update hover state based on mouse position"""

        selected = self.get_selected_region()
        if selected:
            handle = self._get_handle_at(mouse, selected)
            if handle != ResizeHandle.NONE:
                self._hover_region_id = selected.id
                self._hover_handle = handle
                return

        self._hover_region_id = self._find_region_at(mouse)
        self._hover_handle = ResizeHandle.NONE

    def draw(self, screen: Surface) -> None:
        """Draw the region selector"""

        pygame.draw.rect(screen, COLORS.panel_alt, self.rect)

        if self.image:
            img_w = int(self.image.get_width() * self.zoom)
            img_h = int(self.image.get_height() * self.zoom)
            img_x = self.rect.x - self.scroll_x
            img_y = self.rect.y - self.scroll_y

            clip = screen.get_clip()
            screen.set_clip(self.rect)

            if img_w > 0 and img_h > 0:
                scaled = pygame.transform.scale(self.image, (img_w, img_h))
                screen.blit(scaled, (img_x, img_y))

            for region in self.regions:
                self._draw_region(screen, region)

            if self._creating:
                self._draw_creation_preview(screen)

            screen.set_clip(clip)

        pygame.draw.rect(screen, COLORS.border, self.rect, 1)

        pan_btn_w, pan_btn_h = 50, 22
        pan_btn_rect = Rect(self.rect.x + 4, self.rect.y + 4, pan_btn_w, pan_btn_h)
        pan_bg = COLORS.accent_active if self._pan_mode else COLORS.panel_alt
        pan_border = COLORS.accent if self._pan_mode else COLORS.border_soft
        pygame.draw.rect(screen, pan_bg, pan_btn_rect, border_radius=3)
        pygame.draw.rect(screen, pan_border, pan_btn_rect, 1, border_radius=3)
        pan_label = self._font_sm.render(
            "Pan" if not self._pan_mode else "PAN",
            True,
            COLORS.text if self._pan_mode else COLORS.text_dim,
        )
        screen.blit(
            pan_label,
            (
                pan_btn_rect.centerx - pan_label.get_width() // 2,
                pan_btn_rect.centery - pan_label.get_height() // 2,
            ),
        )
        self._pan_btn_rect = pan_btn_rect

        zoom_text = self._font_sm.render(
            f"Zoom: {self.zoom:.1f}x", True, COLORS.text_dim
        )
        screen.blit(zoom_text, (pan_btn_rect.right + 8, self.rect.y + 7))

    def _draw_region(self, screen: Surface, region: Region) -> None:
        """Draw a single region"""
        r = self._get_region_screen_rect(region)

        if r.right < self.rect.x or r.x > self.rect.right:
            return
        if r.bottom < self.rect.y or r.y > self.rect.bottom:
            return

        is_selected = region.id == self.selected_id
        is_hovered = region.id == self._hover_region_id

        if is_selected:
            color = (*COLORS.selected, 100)
        elif is_hovered:
            color = (*COLORS.accent, self.HOVER_ALPHA)
        else:
            color = (*COLORS.accent, 40)

        s = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
        s.fill(color)
        screen.blit(s, r.topleft)

        border_color = COLORS.accent if is_selected else COLORS.border_soft
        pygame.draw.rect(
            screen, border_color, r, self.SELECTION_BORDER_WIDTH if is_selected else 1
        )

        if is_selected:
            handles = self._get_handle_rects(region)
            for handle, handle_rect in handles.items():
                is_hovered_handle = handle == self._hover_handle
                color = COLORS.accent_hover if is_hovered_handle else COLORS.accent
                pygame.draw.rect(screen, color, handle_rect)

        name = region.name or region.id[:8]
        label = self._font.render(name, True, COLORS.text)
        label_bg = pygame.Surface(
            (label.get_width() + 4, label.get_height() + 2), pygame.SRCALPHA
        )
        label_bg.fill((0, 0, 0, 180))
        screen.blit(label_bg, (r.x + 2, r.y + 2))
        screen.blit(label, (r.x + 4, r.y + 3))

        dim_text = f"{region.rect.width}x{region.rect.height}"
        dim = self._font_sm.render(dim_text, True, COLORS.text_dim)
        screen.blit(dim, (r.x + 4, r.bottom - dim.get_height() - 2))

    def _draw_creation_preview(self, screen: Surface) -> None:
        """Draw preview of region being created"""
        mouse = pygame.mouse.get_pos()
        img_x, img_y = self._screen_to_image(mouse[0], mouse[1])

        x = min(self._create_start[0], img_x)
        y = min(self._create_start[1], img_y)
        w = abs(img_x - self._create_start[0])
        h = abs(img_y - self._create_start[1])

        if w > 0 and h > 0:
            screen_x, screen_y = self._image_to_screen(x, y)
            screen_w = int(w * self.zoom)
            screen_h = int(h * self.zoom)

            r = Rect(screen_x, screen_y, screen_w, screen_h)
            s = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            s.fill((*COLORS.success, 60))
            screen.blit(s, r.topleft)
            pygame.draw.rect(screen, COLORS.success, r, 2)

    def resize(self, rect: Rect) -> None:
        """Resize the component"""
        self.rect = rect

    def set_image(self, image: Surface) -> None:
        """Set the image to select regions from"""
        self.image = image

    def set_regions(self, regions: List[Region]) -> None:
        """Set all regions at once"""
        self.regions = regions
        self.select_region(None)

    def get_regions(self) -> List[Region]:
        """Get all regions"""
        return list(self.regions)
