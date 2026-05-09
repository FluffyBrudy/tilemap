"""
Tileset Collision Editor — Godot-like collision shape editor for tilesets.

New Layout (Godot-style):
    +----------------------------------------------------+
    | Toolbar: [Save] [Load] [Clear Current]            |
    +---------------+------------------------------------+
    | Painted Tiles |     Collision Painter              |
    | (side list)   |     (polygon drawing area)         |
    |               |                                    |
    +---------------+------------------------------------+
    |          Tileset Selector (resizable)             |
    |          (scrollable, zoomable, click to select)  |
    +----------------------------------------------------+
"""

from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any, Set, cast
from pathlib import Path

import pygame
from pygame import Rect, Surface

from .models import CollisionPolygon, TileCollisionData, TilesetCollisionLibrary
from .collision_painter import CollisionPainter
from .protocols import TilesetProvider, CollisionDataConsumer
from utils.font_manager import font_manager, FontWeight
from utils.icon_manager import icon_manager
from utils.error_handler import error_handler, error_context
from widgets.ui.theme import COLORS, FONTS
from widgets.ui.draw_utils import draw_panel, draw_button


class TilesetCollisionEditor:
    """Main editor for tileset collision shapes."""

    def __init__(
        self,
        rect: Rect,
        tileset_surface: Optional[Surface] = None,
        tile_size: Tuple[int, int] = (32, 32),
        *,
        provider: Optional[TilesetProvider] = None,
        consumer: Optional[CollisionDataConsumer] = None,
    ):
        self.rect = rect
        self.consumer = consumer
        self.visible = True

        # Resolve tileset from provider or direct arg
        if provider is not None:
            self._provider = provider
            self._tileset_surface = provider.get_surface()
            self._tile_size = provider.get_tile_size()
            self._tileset_name = provider.get_name()
        elif tileset_surface is not None:
            self._provider = None
            self._tileset_surface = tileset_surface
            self._tile_size = tile_size
            self._tileset_name = "Tileset"
        else:
            self._provider = None
            self._tileset_surface = cast(Surface, None)
            self._tile_size = tile_size
            self._tileset_name = "No Tileset"

        # Collision library
        self.library = TilesetCollisionLibrary(
            tileset_name=self._tileset_name,
            tile_size=self._tile_size
        )
        
        # Selected tiles (can select multiple from tileset selector)
        self._selected_tiles: Set[int] = {0}
        
        # Calculate tile grid
        self._recalc_tile_grid()

        # UI layout
        self.toolbar_height = 40
        self.tileset_selector_height = 250  # Resizable
        self.painted_tiles_width = 200
        self._resizing_selector = False
        self._resize_start_y = 0
        self._resize_start_height = 0

        self._update_layout()

        # Tileset selector state
        self.tileset_scroll_x = 0
        self.tileset_scroll_y = 0
        self.tileset_zoom = 2.0
        self._tileset_panning = False
        self._tileset_pan_start = (0, 0)
        self._tileset_pan_start_offset = (0, 0)
        self._space_held = False

        # Painted tiles list state
        self.painted_tiles_scroll = 0
        self.painted_tiles_hover = -1

        # Collision painter
        self.painter = CollisionPainter(
            self.painter_rect,
            self._get_tile_surface(0),
            self._tile_size
        )
        self.painter.on_polygon_added = self._on_polygon_added
        self.painter.on_polygon_removed = self._on_polygon_removed
        self.painter.on_polygon_modified = self._on_polygon_modified

        # Fonts
        self._font = font_manager.get_font(FONTS.name, FONTS.size_md, FontWeight.REGULAR)
        self._font_sm = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)

        # Toolbar buttons
        self._setup_toolbar_buttons()

        # Load collision data for first tile
        self._load_tile_collision_for_selection()

    def _setup_toolbar_buttons(self) -> None:
        """Setup simple pygame toolbar buttons"""
        self._toolbar_buttons: List[Dict[str, Any]] = []

        buttons_config = [
            {"label": "Save", "action": self._save_collision},
            {"label": "Load", "action": self._load_collision},
            {"label": "Clear", "action": self._clear_current},
        ]

        for i, config in enumerate(buttons_config):
            self._toolbar_buttons.append({
                "label": config["label"],
                "action": config["action"],
                "rect": Rect(0, 0, 80, 28),
                "hovered": False,
            })

    def _save_collision(self) -> None:
        """Save collision via toolbar button"""
        collision_dir = self._get_collision_dir()
        collision_dir.mkdir(parents=True, exist_ok=True)
        stem = getattr(self, '_tileset_path_stem', self._tileset_name)
        save_path = collision_dir / f"{stem}.collision.json"
        self.save_to_file(save_path)

    def _load_collision(self) -> None:
        """Load collision via toolbar button"""
        collision_dir = self._get_collision_dir()
        stem = getattr(self, '_tileset_path_stem', self._tileset_name)
        load_path = collision_dir / f"{stem}.collision.json"
        if load_path.exists():
            self.load_from_file(load_path)

    def _get_collision_dir(self) -> Path:
        """Get collision directory path"""
        if self._data_root is None:
            raise RuntimeError("data_root is required. Initialize via from_path() with data_root parameter.")
        return self._data_root / "collision"

    def _clear_current(self) -> None:
        """Clear collision for selected tiles via toolbar button"""
        self.clear_current_selection()

    def _position_toolbar_buttons(self) -> None:
        """Position toolbar buttons in the toolbar area"""
        if not hasattr(self, '_toolbar_buttons'):
            return

        start_x = self.toolbar_rect.right - (len(self._toolbar_buttons) * 90) - 10
        toolbar_y = self.toolbar_rect.y + (self.toolbar_rect.height - 28) // 2

        for button in self._toolbar_buttons:
            button["rect"].x = start_x
            button["rect"].y = toolbar_y
            start_x += 90

    def _handle_toolbar_button_clicks(self, events: List[pygame.event.Event]) -> None:
        """Handle toolbar button click events"""
        mouse_pos = pygame.mouse.get_pos()

        for button in self._toolbar_buttons:
            was_hovered = button["hovered"]
            button["hovered"] = button["rect"].collidepoint(mouse_pos)

            for event in events:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if button["rect"].collidepoint(mouse_pos):
                        button["action"]()

    def _draw_toolbar_buttons(self, surface: Surface) -> None:
        """Draw toolbar buttons"""
        for button in self._toolbar_buttons:
            label_surf = self._font.render(button["label"], True, COLORS.text)
            draw_button(surface, button["rect"], label_surf, hover=button["hovered"])

    def _update_layout(self) -> None:
        """Update layout rects based on current sizes"""
        # Toolbar at top
        self.toolbar_rect = Rect(
            self.rect.x,
            self.rect.y,
            self.rect.w,
            self.toolbar_height
        )

        # Tileset selector at bottom
        self.tileset_selector_rect = Rect(
            self.rect.x,
            self.rect.bottom - self.tileset_selector_height,
            self.rect.w,
            self.tileset_selector_height
        )

        # Resize handle above tileset selector
        self.resize_handle_rect = Rect(
            self.rect.x,
            self.tileset_selector_rect.y - 4,
            self.rect.w,
            8
        )

        # Middle area (painter + painted tiles list)
        middle_y = self.rect.y + self.toolbar_height
        middle_h = self.rect.h - self.toolbar_height - self.tileset_selector_height

        self.painted_tiles_rect = Rect(
            self.rect.x,
            middle_y,
            self.painted_tiles_width,
            middle_h
        )

        self.painter_rect = Rect(
            self.rect.x + self.painted_tiles_width,
            middle_y,
            self.rect.w - self.painted_tiles_width,
            middle_h
        )

    def _recalc_tile_grid(self) -> None:
        """Calculate tile grid dimensions"""
        if self._tileset_surface is None:
            self.tile_cols = 0
            self.tile_rows = 0
            self.total_tiles = 0
            return

        tw, th = self._tile_size
        self.tile_cols = self._tileset_surface.get_width() // tw
        self.tile_rows = self._tileset_surface.get_height() // th
        self.total_tiles = self.tile_cols * self.tile_rows

    def _get_tile_surface(self, tile_id: int) -> Surface:
        """Extract a single tile surface from the tileset"""
        if self._tileset_surface is None:
            return pygame.Surface(self._tile_size)

        tw, th = self._tile_size
        col = tile_id % self.tile_cols
        row = tile_id // self.tile_cols

        tile_surf = pygame.Surface(self._tile_size, pygame.SRCALPHA)
        tile_surf.blit(
            self._tileset_surface,
            (0, 0),
            (col * tw, row * th, tw, th)
        )
        return tile_surf

    def _load_tile_collision_for_selection(self) -> None:
        """Load collision data for selected tiles into painter.
        
        If multiple tiles selected with same collision, show that.
        If different collision, show empty (ready to paint new).
        """
        if not self._selected_tiles:
            self.painter.set_polygons([], [])
            return

        # Get first selected tile's collision
        first_tile = min(self._selected_tiles)
        
        if first_tile in self.library.tiles:
            tile_data = self.library.tiles[first_tile]
            polygons = [shape.vertices for shape in tile_data.shapes]
            one_way_flags = [shape.one_way for shape in tile_data.shapes]
            self.painter.set_polygons(polygons, one_way_flags)
        else:
            self.painter.set_polygons([], [])
        
        # Update painter tile surface to show first selected
        self.painter.tile_surface = self._get_tile_surface(first_tile)

    def _save_tile_collision_for_selection(self) -> None:
        """Save current collision data to all selected tiles"""
        polygons = self.painter.get_polygons()
        one_way_flags = self.painter.get_one_way_flags()

        for tile_id in self._selected_tiles:
            if not polygons:
                # Remove tile data if no polygons
                if tile_id in self.library.tiles:
                    del self.library.tiles[tile_id]
                    if self.consumer:
                        self.consumer.on_collision_deleted(tile_id)
            else:
                # Create collision shapes
                shapes = [
                    CollisionPolygon(vertices=poly, one_way=one_way)
                    for poly, one_way in zip(polygons, one_way_flags)
                ]

                # Save to library
                tile_data = TileCollisionData(tile_id=tile_id, shapes=shapes)
                self.library.tiles[tile_id] = tile_data

                if self.consumer:
                    self.consumer.on_collision_saved(tile_id, tile_data.to_dict())

    def _on_polygon_added(self, vertices: List[Tuple[float, float]]) -> None:
        """Callback when polygon is added"""
        self._save_tile_collision_for_selection()

    def _on_polygon_removed(self, idx: int) -> None:
        """Callback when polygon is removed"""
        self._save_tile_collision_for_selection()

    def _on_polygon_modified(self, idx: int) -> None:
        """Callback when polygon is modified"""
        self._save_tile_collision_for_selection()

    def clear_current_selection(self) -> None:
        """Clear collision for currently selected tiles"""
        self.painter.set_polygons([], [])
        self._save_tile_collision_for_selection()

    def resize(self, rect: Rect) -> None:
        """Resize the editor"""
        self.rect = rect
        self._update_layout()
        self.painter.resize(self.painter_rect)

    def load_tileset(self, surface: Surface, tile_size: Tuple[int, int], name: str = "Tileset") -> None:
        """Load a new tileset"""
        self._tileset_surface = surface
        self._tile_size = tile_size
        self._tileset_name = name
        self._recalc_tile_grid()

        # Reset library
        self.library = TilesetCollisionLibrary(
            tileset_name=name,
            tile_size=tile_size
        )

        # Reset selection
        self._selected_tiles = {0}
        self.painter.tile_surface = self._get_tile_surface(0)
        self.painter.tile_size = tile_size
        self._load_tile_collision_for_selection()

    def load_collision_data(self, data: Dict[str, Any]) -> None:
        """Load collision data from dict"""
        try:
            self.library = TilesetCollisionLibrary.from_dict(data)
            self._load_tile_collision_for_selection()
        except Exception as e:
            error_handler.capture(e, context="load_collision_data")

    def save_to_file(self, path: Path) -> None:
        """Save collision data to file"""
        try:
            self._save_tile_collision_for_selection()
            self.library.save(path)
        except Exception as e:
            error_handler.capture(e, context="save_collision_file")

    def load_from_file(self, path: Path) -> None:
        """Load collision data from file"""
        try:
            self.library = TilesetCollisionLibrary.load(path)
            self._load_tile_collision_for_selection()
        except Exception as e:
            error_handler.capture(e, context="load_collision_file")

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle input events"""
        if not self.visible:
            return False

        # Let painter handle events first
        if self.painter.handle_event(event):
            return True

        mouse = pygame.mouse.get_pos()

        # Resize handle
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.resize_handle_rect.collidepoint(mouse):
                self._resizing_selector = True
                self._resize_start_y = mouse[1]
                self._resize_start_height = self.tileset_selector_height
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._resizing_selector:
                self._resizing_selector = False
                return True

        if event.type == pygame.MOUSEMOTION:
            if self._resizing_selector:
                dy = self._resize_start_y - mouse[1]
                new_height = max(100, min(600, self._resize_start_height + dy))
                self.tileset_selector_height = new_height
                self._update_layout()
                self.painter.resize(self.painter_rect)
                return True

        # Track space key for panning
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self._space_held = True
                return True
        
        if event.type == pygame.KEYUP:
            if event.key == pygame.K_SPACE:
                self._space_held = False
                if self._tileset_panning:
                    self._tileset_panning = False
                return True

        # Tileset selector interaction
        if self.tileset_selector_rect.collidepoint(mouse):
            # Middle mouse OR Space+Left mouse to pan
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 2 or (event.button == 1 and self._space_held):
                    self._tileset_panning = True
                    self._tileset_pan_start = mouse
                    self._tileset_pan_start_offset = (self.tileset_scroll_x, self.tileset_scroll_y)
                    return True

            # Left click to select tile (only if not panning)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self._space_held:
                tile_id = self._get_tile_at_mouse(mouse)
                if tile_id is not None:
                    # Ctrl/Cmd for multi-select
                    mods = pygame.key.get_mods()
                    if mods & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA):
                        if tile_id in self._selected_tiles:
                            self._selected_tiles.discard(tile_id)
                        else:
                            self._selected_tiles.add(tile_id)
                    else:
                        self._selected_tiles = {tile_id}
                    
                    self._load_tile_collision_for_selection()
                    return True

            # Mouse wheel to zoom
            if event.type == pygame.MOUSEWHEEL:
                self.tileset_zoom *= 1.15 if event.y > 0 else 0.87
                self.tileset_zoom = max(0.5, min(self.tileset_zoom, 8.0))
                return True

        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 2 or event.button == 1:
                if self._tileset_panning:
                    self._tileset_panning = False
                    return True

        if event.type == pygame.MOUSEMOTION:
            if self._tileset_panning:
                dx = mouse[0] - self._tileset_pan_start[0]
                dy = mouse[1] - self._tileset_pan_start[1]
                self.tileset_scroll_x = self._tileset_pan_start_offset[0] - dx
                self.tileset_scroll_y = self._tileset_pan_start_offset[1] - dy
                self.tileset_scroll_x = max(0, self.tileset_scroll_x)
                self.tileset_scroll_y = max(0, self.tileset_scroll_y)
                return True

        # Painted tiles list interaction
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.painted_tiles_rect.collidepoint(mouse):
                painted_tiles = sorted(self.library.tiles.keys())
                rel_y = mouse[1] - self.painted_tiles_rect.y + self.painted_tiles_scroll
                tile_height = 64
                idx = rel_y // tile_height
                if 0 <= idx < len(painted_tiles):
                    tile_id = painted_tiles[idx]
                    self._selected_tiles = {tile_id}
                    self._load_tile_collision_for_selection()
                return True

        # Painted tiles list scrolling
        if event.type == pygame.MOUSEWHEEL:
            if self.painted_tiles_rect.collidepoint(mouse):
                self.painted_tiles_scroll -= event.y * 30
                self.painted_tiles_scroll = max(0, self.painted_tiles_scroll)
                return True

        # Keyboard shortcuts
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                if pygame.key.get_mods() & (pygame.KMOD_LSHIFT):
                    # Shift+Delete: clear current selection
                    self.clear_current_selection()
                    return True
            elif event.key == pygame.K_h:
                # H: Recenter tileset view
                self._recenter_tileset_view()
                return True

        return False

    def _get_tile_at_mouse(self, mouse: Tuple[int, int]) -> Optional[int]:
        """Get tile ID at mouse position in tileset selector"""
        if not self.tileset_selector_rect.collidepoint(mouse):
            return None

        rel_x = mouse[0] - self.tileset_selector_rect.x + self.tileset_scroll_x
        rel_y = mouse[1] - self.tileset_selector_rect.y + self.tileset_scroll_y

        tw = int(self._tile_size[0] * self.tileset_zoom)
        th = int(self._tile_size[1] * self.tileset_zoom)

        col = rel_x // tw
        row = rel_y // th

        if 0 <= col < self.tile_cols and 0 <= row < self.tile_rows:
            return row * self.tile_cols + col

        return None

    def _recenter_tileset_view(self) -> None:
        """Recenter the tileset view to show the whole tileset"""
        if self._tileset_surface is None:
            return
        
        # Calculate tileset dimensions at current zoom
        tw = int(self._tile_size[0] * self.tileset_zoom)
        th = int(self._tile_size[1] * self.tileset_zoom)
        tileset_w = self.tile_cols * tw
        tileset_h = self.tile_rows * th
        
        # Center horizontally
        if tileset_w < self.tileset_selector_rect.w:
            self.tileset_scroll_x = 0
        else:
            self.tileset_scroll_x = (tileset_w - self.tileset_selector_rect.w) // 2
        
        # Center vertically
        if tileset_h < self.tileset_selector_rect.h:
            self.tileset_scroll_y = 0
        else:
            self.tileset_scroll_y = (tileset_h - self.tileset_selector_rect.h) // 2

    def draw(self, screen: Surface) -> None:
        """Draw the editor"""
        if not self.visible:
            return

        # Draw toolbar
        self._draw_toolbar(screen)

        # Draw painted tiles list
        self._draw_painted_tiles_list(screen)

        # Draw painter
        self.painter.draw(screen)

        # Draw resize handle
        self._draw_resize_handle(screen)

        # Draw tileset selector
        self._draw_tileset_selector(screen)

    def _draw_toolbar(self, screen: Surface) -> None:
        """Draw the toolbar"""
        draw_panel(screen, self.toolbar_rect, COLORS.header, COLORS.border)

        # Title
        selected_str = f"{len(self._selected_tiles)} tile{'s' if len(self._selected_tiles) != 1 else ''} selected"
        title = self._font.render(
            f"Tileset Collision Editor — {self._tileset_name} — {selected_str}",
            True,
            COLORS.text
        )
        screen.blit(title, (self.toolbar_rect.x + 10, self.toolbar_rect.y + 10))

        # Collision count
        collision_count = len(self.library.tiles)
        count_text = self._font_sm.render(
            f"{collision_count} painted",
            True,
            COLORS.text_dim
        )
        screen.blit(count_text, (self.toolbar_rect.right - count_text.get_width() - 10, self.toolbar_rect.y + 12))

        # Draw toolbar buttons
        if hasattr(self, '_toolbar_buttons'):
            self._draw_toolbar_buttons(screen)

    def _draw_painted_tiles_list(self, screen: Surface) -> None:
        """Draw the list of tiles with collision"""
        draw_panel(screen, self.painted_tiles_rect, COLORS.panel, COLORS.border)

        # Header
        header_text = self._font_sm.render("Painted Tiles", True, COLORS.text)
        screen.blit(header_text, (self.painted_tiles_rect.x + 8, self.painted_tiles_rect.y + 8))

        clip = screen.get_clip()
        screen.set_clip(self.painted_tiles_rect)

        painted_tiles = sorted(self.library.tiles.keys())
        tile_height = 64
        y = self.painted_tiles_rect.y + 30 - self.painted_tiles_scroll

        for tile_id in painted_tiles:
            if y + tile_height < self.painted_tiles_rect.y:
                y += tile_height
                continue
            if y > self.painted_tiles_rect.bottom:
                break

            tile_rect = Rect(self.painted_tiles_rect.x, y, self.painted_tiles_rect.w, tile_height)

            # Background
            is_selected = (tile_id in self._selected_tiles)
            bg_color = COLORS.selected if is_selected else COLORS.panel_alt

            pygame.draw.rect(screen, bg_color, tile_rect)
            pygame.draw.rect(screen, COLORS.border_soft, tile_rect, 1)

            # Tile preview
            tile_surf = self._get_tile_surface(tile_id)
            preview_size = 48
            scale = min(preview_size / self._tile_size[0], preview_size / self._tile_size[1])
            scaled_w = int(self._tile_size[0] * scale)
            scaled_h = int(self._tile_size[1] * scale)
            scaled_surf = pygame.transform.scale(tile_surf, (scaled_w, scaled_h))

            preview_x = tile_rect.x + 8
            preview_y = tile_rect.y + (tile_height - scaled_h) // 2
            screen.blit(scaled_surf, (preview_x, preview_y))

            # Tile ID
            id_text = self._font.render(str(tile_id), True, COLORS.text)
            screen.blit(id_text, (preview_x + scaled_w + 10, tile_rect.y + 8))

            # Shape count
            shape_count = len(self.library.tiles[tile_id].shapes)
            coll_text = self._font_sm.render(
                f"{shape_count} shape{'s' if shape_count != 1 else ''}",
                True,
                COLORS.accent
            )
            screen.blit(coll_text, (preview_x + scaled_w + 10, tile_rect.y + 30))

            y += tile_height

        screen.set_clip(clip)

    def _draw_resize_handle(self, screen: Surface) -> None:
        """Draw the resize handle"""
        mouse = pygame.mouse.get_pos()
        is_hover = self.resize_handle_rect.collidepoint(mouse) or self._resizing_selector
        
        color = COLORS.accent if is_hover else COLORS.border_soft
        pygame.draw.rect(screen, color, self.resize_handle_rect)
        
        # Draw grip lines
        center_y = self.resize_handle_rect.centery
        for i in range(-1, 2):
            y = center_y + i * 2
            pygame.draw.line(screen, COLORS.text_dim, 
                           (self.resize_handle_rect.x + 10, y),
                           (self.resize_handle_rect.right - 10, y))

    def _draw_tileset_selector(self, screen: Surface) -> None:
        """Draw the tileset selector"""
        draw_panel(screen, self.tileset_selector_rect, COLORS.panel_alt, COLORS.border)

        if self._tileset_surface is None:
            return

        clip = screen.get_clip()
        screen.set_clip(self.tileset_selector_rect)

        tw = int(self._tile_size[0] * self.tileset_zoom)
        th = int(self._tile_size[1] * self.tileset_zoom)

        # Draw tiles
        for row in range(self.tile_rows):
            for col in range(self.tile_cols):
                tile_id = row * self.tile_cols + col
                
                x = self.tileset_selector_rect.x + col * tw - self.tileset_scroll_x
                y = self.tileset_selector_rect.y + row * th - self.tileset_scroll_y

                # Skip if outside visible area
                if x + tw < self.tileset_selector_rect.x or x > self.tileset_selector_rect.right:
                    continue
                if y + th < self.tileset_selector_rect.y or y > self.tileset_selector_rect.bottom:
                    continue

                tile_rect = Rect(x, y, tw, th)

                # Draw tile
                tile_surf = self._get_tile_surface(tile_id)
                if tw != self._tile_size[0] or th != self._tile_size[1]:
                    tile_surf = pygame.transform.scale(tile_surf, (tw, th))
                screen.blit(tile_surf, (x, y))

                # Highlight selected tiles
                if tile_id in self._selected_tiles:
                    pygame.draw.rect(screen, COLORS.accent, tile_rect, 2)

                # Highlight painted tiles
                if tile_id in self.library.tiles:
                    # Draw small indicator in corner
                    indicator_rect = Rect(x + tw - 8, y + 2, 6, 6)
                    pygame.draw.circle(screen, COLORS.accent, indicator_rect.center, 3)

                # Grid
                pygame.draw.rect(screen, COLORS.border_soft, tile_rect, 1)

        screen.set_clip(clip)

        # Draw zoom indicator
        zoom_text = self._font_sm.render(f"Zoom: {self.tileset_zoom:.1f}x", True, COLORS.text_dim)
        screen.blit(zoom_text, (self.tileset_selector_rect.x + 8, self.tileset_selector_rect.y + 8))

    @classmethod
    def from_path(
        cls,
        tileset_path: Path,
        tile_size: Tuple[int, int] = (32, 32),
        window_size: Tuple[int, int] = (1200, 800),
        data_root: Path = None,
    ) -> "TilesetCollisionEditor":
        """Create editor from tileset image path (for standalone use)"""
        surface = pygame.image.load(tileset_path).convert_alpha()
        rect = Rect(0, 0, window_size[0], window_size[1])
        editor = cls(rect, surface, tile_size)
        editor._data_root = data_root
        editor._tileset_path_stem = tileset_path.stem
        editor._tileset_name = tileset_path.stem  # Use actual filename, not "Tileset"
        editor.library.tileset_name = tileset_path.stem
        return editor

    def run(self) -> None:
        """Run standalone editor (for standalone use)"""
        screen = pygame.display.get_surface()
        if screen is None:
            raise RuntimeError("pygame display not initialized")

        # Position thorpy toolbar
        self._position_toolbar_buttons()

        clock = pygame.time.Clock()
        running = True

        while running:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_s and (
                        pygame.key.get_mods() & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA)
                    ):
                        collision_dir = self._get_collision_dir()
                        collision_dir.mkdir(parents=True, exist_ok=True)
                        stem = getattr(self, '_tileset_path_stem', self._tileset_name)
                        save_path = collision_dir / f"{stem}.collision.json"
                        self.save_to_file(save_path)
                    elif event.key == pygame.K_l and (
                        pygame.key.get_mods() & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA)
                    ):
                        collision_dir = self._get_collision_dir()
                        load_path = collision_dir / f"{getattr(self, '_tileset_path_stem', self._tileset_name)}.collision.json"
                        if load_path.exists():
                            self.load_from_file(load_path)
                            print(f"Loaded collision data from {load_path}")

                self.handle_event(event)

            # Handle toolbar button clicks
            self._handle_toolbar_button_clicks(events)

            screen.fill((20, 20, 20))
            self.draw(screen)
            pygame.display.flip()
            clock.tick(60)
