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

from pathlib import Path
from typing import Any, cast

import pygame
from pygame import Rect, Surface

from utils.error_handler import error_handler
from utils.font_manager import FontWeight, font_manager
from widgets.ui.button import Button
from widgets.ui.checkbox import Checkbox
from widgets.ui.draw_utils import draw_panel
from widgets.ui.splitter import Splitter
from widgets.ui.theme import COLORS, FONTS, SHAPE

from .collision_painter import CollisionPainter
from .models import CollisionPolygon, TileCollisionData, TilesetCollisionLibrary
from .protocols import CollisionDataConsumer, TilesetProvider

WP_PADDING_X = 12
WP_PADDING_Y = 38
WP_SECTION_HEIGHT = 28
WP_CHECKBOX_ROW = 30
WP_GRID_ROW = 36
WP_GRID_BTN = 28
WP_GRID_GAP = 68
WP_TITLE_Y = 10


class TilesetCollisionEditor:
    """Main editor for tileset collision shapes."""

    def __init__(
        self,
        rect: Rect,
        tileset_surface: Surface | None = None,
        tile_size: tuple[int, int] = (32, 32),
        *,
        provider: TilesetProvider | None = None,
        consumer: CollisionDataConsumer | None = None,
    ):
        self.rect = rect
        self.consumer = consumer
        self.visible = True
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

        self._clipboard_polygons: list[list[tuple[float, float]]] = []
        self._clipboard_one_way_flags: list[bool] = []
        self._toast_message: str | None = None
        self._toast_timer: float = 0.0
        self._toast_start: int = 0

        self._propagation_groups: dict[str, list[int]] = {}

        self._user_cleared_tiles: set[int] = set()

        self.library = TilesetCollisionLibrary(
            tileset_name=self._tileset_name, tile_size=self._tile_size
        )

        self._selected_tiles: set[int] = {0}

        self._recalc_tile_grid()

        self.toolbar_height = 40
        self.tileset_selector_height = 250
        self.painted_tiles_width = 200
        self.widget_panel_width = 200

        self._splitter = Splitter(orientation="horizontal")
        self._splitter.on_drag = self._on_splitter_drag

        self._update_layout()

        self.tileset_scroll_x = 0
        self.tileset_scroll_y = 0
        self.tileset_zoom = 2.0
        self._tileset_panning = False
        self._tileset_pan_start = (0, 0)
        self._tileset_pan_start_offset = (0, 0)
        self._space_held = False

        self.painted_tiles_scroll = 0
        self.painted_tiles_hover = -1
        self._painted_tiles_focused = False

        self.painter = CollisionPainter(
            self.painter_rect, self._get_tile_surface(0), self._tile_size
        )
        self.painter.on_polygon_added = self._on_polygon_added
        self.painter.on_polygon_removed = self._on_polygon_removed
        self.painter.on_polygon_modified = self._on_polygon_modified

        self._font = font_manager.get_font(
            FONTS.name, FONTS.size_md, FontWeight.REGULAR
        )
        self._font_sm = font_manager.get_font(
            FONTS.name, FONTS.size_sm, FontWeight.REGULAR
        )

        self._setup_toolbar_buttons()
        self._position_toolbar_buttons()

        self._setup_widget_buttons()

        self._load_tile_collision_for_selection()

    def _setup_toolbar_buttons(self) -> None:
        """Setup toolbar buttons"""
        self._toolbar_buttons: list[Button] = []

        buttons_config = [
            ("Save", self._save_collision),
            ("Load", self._load_collision),
            ("Copy", self._copy_collision),
            ("Paste", self._paste_collision),
            ("Clear", self._clear_current),
        ]

        for label, action in buttons_config:
            btn = Button(
                Rect(0, 0, 80, 28),
                label,
                font=self._font,
                on_click=action,
            )
            self._toolbar_buttons.append(btn)

    def _setup_widget_buttons(self) -> None:
        """Setup widget panel buttons"""
        self._chk_one_way = Checkbox(
            Rect(0, 0, 0, 0),
            "One-Way",
            disabled=True,
            on_changed=lambda _: self.painter.toggle_one_way(),
        )
        self._chk_angle = Checkbox(
            Rect(0, 0, 0, 0),
            "Angle Hints",
            on_changed=lambda v: setattr(self.painter, "show_angle_hints", v),
        )
        self._chk_grid = Checkbox(
            Rect(0, 0, 0, 0),
            "Grid",
            checked=True,
            on_changed=lambda v: setattr(self.painter, "show_grid", v),
        )
        self._chk_snap = Checkbox(
            Rect(0, 0, 0, 0),
            "Snap to Grid",
            on_changed=lambda v: setattr(self.painter, "snap_to_grid", v),
        )
        self._chk_flip_x = Checkbox(
            Rect(0, 0, 0, 0),
            "Flip X",
            on_changed=lambda v: self._set_flip("x", v),
        )
        self._chk_flip_y = Checkbox(
            Rect(0, 0, 0, 0),
            "Flip Y",
            on_changed=lambda v: self._set_flip("y", v),
        )

        self._widget_items: list[tuple] = [
            ("section", "POLYGON"),
            ("checkbox", self._chk_one_way),
            ("checkbox", self._chk_angle),
            ("section", "TILE"),
            ("checkbox", self._chk_flip_x),
            ("checkbox", self._chk_flip_y),
            ("section", "DISPLAY"),
            ("checkbox", self._chk_grid),
            ("section", "GRID SNAP"),
            ("grid_dec", None),
            ("grid_val", None),
            ("grid_inc", None),
            ("checkbox", self._chk_snap),
        ]

    def _save_collision(self) -> None:
        """Save collision via toolbar button"""
        collision_dir = self._get_collision_dir()
        collision_dir.mkdir(parents=True, exist_ok=True)
        stem = getattr(self, "_tileset_path_stem", self._tileset_name)
        save_path = collision_dir / f"{stem}.collision.json"
        self.save_to_file(save_path)

    def _load_collision(self) -> None:
        """Load collision via toolbar button"""
        collision_dir = self._get_collision_dir()
        stem = getattr(self, "_tileset_path_stem", self._tileset_name)
        load_path = collision_dir / f"{stem}.collision.json"
        if load_path.exists():
            self.load_from_file(load_path)

    def _get_collision_dir(self) -> Path:
        """Get collision directory path"""
        if self._data_root is None:
            raise RuntimeError(
                "data_root is required. Initialize via from_path() with data_root parameter."
            )
        return self._data_root / "collision"

    def _clear_current(self) -> None:
        """Clear collision for selected tiles via toolbar button"""
        self.clear_current_selection()

    def _copy_collision(self) -> None:
        """Copy collision shapes from current tile to clipboard"""
        polygons = self.painter.get_polygons()
        one_way_flags = self.painter.get_one_way_flags()
        self._clipboard_polygons = [list(p) for p in polygons]
        self._clipboard_one_way_flags = list(one_way_flags)
        count = len(self._clipboard_polygons)
        self._show_toast(f"Copied {count} shape{'s' if count != 1 else ''}")

    def _paste_collision(self) -> None:
        """Paste collision shapes from clipboard to selected tiles"""
        if not self._clipboard_polygons:
            self._show_toast("Clipboard is empty")
            return
        self.painter.set_polygons(
            [list(p) for p in self._clipboard_polygons],
            list(self._clipboard_one_way_flags),
        )
        self._save_tile_collision_for_selection()
        tile_count = len(self._selected_tiles)
        shape_count = len(self._clipboard_polygons)
        self._show_toast(
            f"Pasted {shape_count} shape{'s' if shape_count != 1 else ''} to {tile_count} tile{'s' if tile_count != 1 else ''}"
        )

    def _layout_widget_panel(self) -> None:
        """Pre-compute clickable widget rects (checkbox + grid buttons)"""
        panel = self.widget_panel_rect
        px = panel.x + WP_PADDING_X
        pw = panel.w - WP_PADDING_X * 2
        y = panel.y + WP_PADDING_Y
        for kind, data in self._widget_items:
            if kind == "section":
                y += WP_SECTION_HEIGHT
            elif kind == "checkbox":
                data.rect = Rect(px, y, pw, WP_CHECKBOX_ROW)
                y += WP_CHECKBOX_ROW
            elif kind == "grid_dec":
                self._grid_dec_rect = Rect(px, y, WP_GRID_BTN, WP_GRID_BTN)
            elif kind == "grid_val":
                self._grid_val_rect = Rect(px, y, 0, WP_GRID_BTN)
            elif kind == "grid_inc":
                self._grid_inc_rect = Rect(
                    px + WP_GRID_GAP, y, WP_GRID_BTN, WP_GRID_BTN
                )
                y += WP_GRID_ROW

    def _sync_widget_state(self) -> None:
        """Sync checkbox states from painter attributes before draw"""
        p = self.painter
        self._chk_grid.checked = p.show_grid
        self._chk_snap.checked = p.snap_to_grid
        self._chk_angle.checked = p.show_angle_hints
        self._chk_flip_x.checked = p.flip_x
        self._chk_flip_y.checked = p.flip_y
        sel = p.selected_polygon_idx
        if sel is not None and 0 <= sel < len(p.polygon_one_way):
            self._chk_one_way.checked = p.polygon_one_way[sel]
            self._chk_one_way.disabled = False
        else:
            self._chk_one_way.checked = False
            self._chk_one_way.disabled = True

    def _selection_flip_flags(self) -> tuple[bool, bool]:
        """Flip flags of the first selected tile (defaults off)."""
        if not self._selected_tiles:
            return False, False
        entry = self.library.tiles.get(min(self._selected_tiles))
        if entry is None:
            return False, False
        return entry.flip_x, entry.flip_y

    def _set_flip(self, axis: str, value: bool) -> None:
        """Apply a flip flag to all selected tiles (creates entries)."""
        if not self._selected_tiles:
            return
        for tile_id in self._selected_tiles:
            entry = self.library.tiles.get(tile_id)
            if entry is None:
                entry = TileCollisionData(tile_id=tile_id)
                self.library.tiles[tile_id] = entry
            if axis == "x":
                entry.flip_x = value
            else:
                entry.flip_y = value
        if axis == "x":
            self.painter.flip_x = value
        else:
            self.painter.flip_y = value

    def _handle_widget_button_clicks(self, events: list[pygame.event.Event]) -> None:
        """Handle widget panel button clicks"""
        self._sync_widget_state()
        self._layout_widget_panel()
        painter = self.painter
        pygame.mouse.get_pos()

        for event in events:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = event.pos
                if self._chk_one_way.handle_event(event):
                    continue
                if self._chk_angle.handle_event(event):
                    continue
                if self._chk_flip_x.handle_event(event):
                    continue
                if self._chk_flip_y.handle_event(event):
                    continue
                if self._chk_grid.handle_event(event):
                    continue
                if self._chk_snap.handle_event(event):
                    continue
                if self._grid_dec_rect.collidepoint(pos):
                    painter.grid_size = max(1, painter.grid_size - 1)
                elif self._grid_inc_rect.collidepoint(pos):
                    painter.grid_size = min(64, painter.grid_size + 1)

    def _position_toolbar_buttons(self) -> None:
        """Position toolbar buttons in the toolbar area"""
        if not hasattr(self, "_toolbar_buttons"):
            return

        start_x = self.toolbar_rect.right - (len(self._toolbar_buttons) * 90) - 10
        toolbar_y = self.toolbar_rect.y + (self.toolbar_rect.height - 28) // 2

        for btn in self._toolbar_buttons:
            btn.resize(start_x, toolbar_y, 80, 28)
            start_x += 90

    def _handle_toolbar_button_clicks(self, events: list[pygame.event.Event]) -> None:
        """Handle toolbar button click events"""
        for event in events:
            for btn in self._toolbar_buttons:
                btn.handle_event(event)

    def _draw_widget_panel(self, surface: Surface) -> None:
        """Draw the widget panel on the right side"""
        self._sync_widget_state()
        panel = self.widget_panel_rect
        pygame.draw.rect(surface, COLORS.panel_alt, panel)
        pygame.draw.rect(surface, COLORS.border_soft, panel, 1)

        px = panel.x + WP_PADDING_X
        pw = panel.w - WP_PADDING_X * 2
        y = panel.y + WP_PADDING_Y

        title = self._font.render("Tools", True, COLORS.text)
        surface.blit(title, (px, panel.y + WP_TITLE_Y))

        painter = self.painter
        mouse = pygame.mouse.get_pos()

        for kind, data in self._widget_items:
            if kind == "section":
                lbl = self._font_sm.render(data, True, (140, 140, 160))
                surface.blit(lbl, (px, y + 4))
                sep_y = y + lbl.get_height() + 8
                pygame.draw.line(surface, (50, 50, 55), (px, sep_y), (px + pw, sep_y))
                y += WP_SECTION_HEIGHT

            elif kind == "checkbox":
                data.rect = Rect(px, y, pw, WP_CHECKBOX_ROW)
                data.draw(surface)
                y += WP_CHECKBOX_ROW

            elif kind == "grid_dec":
                r = Rect(px, y, WP_GRID_BTN, WP_GRID_BTN)
                self._grid_dec_rect = r
                hovered = r.collidepoint(mouse)
                bg = COLORS.hover if hovered else COLORS.panel_alt
                pygame.draw.rect(surface, bg, r, border_radius=SHAPE.radius_sm)
                pygame.draw.rect(surface, COLORS.border_soft, r, 1, border_radius=SHAPE.radius_sm)
                lbl = self._font_sm.render("-", True, COLORS.text)
                tx = r.centerx - lbl.get_width() // 2
                ty = r.centery - lbl.get_height() // 2
                surface.blit(lbl, (tx, ty))

            elif kind == "grid_val":
                self._grid_val_rect = Rect(px, y, 0, WP_GRID_BTN)
                val_surf = self._font_sm.render(
                    str(painter.grid_size), True, COLORS.text
                )
                vx = px + WP_GRID_BTN + 8
                vy = y + (WP_GRID_BTN - val_surf.get_height()) // 2
                surface.blit(val_surf, (vx, vy))

            elif kind == "grid_inc":
                r = Rect(px + WP_GRID_GAP, y, WP_GRID_BTN, WP_GRID_BTN)
                self._grid_inc_rect = r
                hovered = r.collidepoint(mouse)
                bg = COLORS.hover if hovered else COLORS.panel_alt
                pygame.draw.rect(surface, bg, r, border_radius=SHAPE.radius_sm)
                pygame.draw.rect(surface, COLORS.border_soft, r, 1, border_radius=SHAPE.radius_sm)
                lbl = self._font_sm.render("+", True, COLORS.text)
                tx = r.centerx - lbl.get_width() // 2
                ty = r.centery - lbl.get_height() // 2
                surface.blit(lbl, (tx, ty))
                y += WP_GRID_ROW

    def _draw_toolbar_buttons(self, surface: Surface) -> None:
        """Draw toolbar buttons"""
        for btn in self._toolbar_buttons:
            btn.draw(surface)

    def _on_splitter_drag(self, pos: int) -> None:
        self.tileset_selector_height = max(100, min(600, self.rect.bottom - pos))

    def _update_layout(self) -> None:
        """Update layout rects based on current sizes"""

        self.toolbar_rect = Rect(
            self.rect.x, self.rect.y, self.rect.w, self.toolbar_height
        )

        self.tileset_selector_rect = Rect(
            self.rect.x,
            self.rect.bottom - self.tileset_selector_height,
            self.rect.w,
            self.tileset_selector_height,
        )

        self._splitter.resize(
            self.rect.x, self.tileset_selector_rect.y - 4, self.rect.w, 8
        )

        middle_y = self.rect.y + self.toolbar_height
        middle_h = self.rect.h - self.toolbar_height - self.tileset_selector_height

        self.painted_tiles_rect = Rect(
            self.rect.x, middle_y, self.painted_tiles_width, middle_h
        )

        self.painter_rect = Rect(
            self.rect.x + self.painted_tiles_width,
            middle_y,
            self.rect.w - self.painted_tiles_width - self.widget_panel_width,
            middle_h,
        )

        self.widget_panel_rect = Rect(
            self.rect.right - self.widget_panel_width,
            middle_y,
            self.widget_panel_width,
            middle_h,
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
        tile_surf.blit(self._tileset_surface, (0, 0), (col * tw, row * th, tw, th))
        return tile_surf

    def _load_tile_collision_for_selection(self) -> None:
        """Load collision data for selected tiles into painter.

        If multiple tiles selected with same collision, show that.
        If different collision, show empty (ready to paint new).
        """
        if not self._selected_tiles:
            self.painter.set_polygons([], [])
            return

        first_tile = min(self._selected_tiles)

        if first_tile in self.library.tiles:
            tile_data = self.library.tiles[first_tile]
            polygons = [shape.vertices for shape in tile_data.shapes]
            one_way_flags = [shape.one_way for shape in tile_data.shapes]
            self.painter.set_polygons(polygons, one_way_flags)
            self.painter.flip_x = tile_data.flip_x
            self.painter.flip_y = tile_data.flip_y
        else:
            self.painter.set_polygons([], [])
            self.painter.flip_x = False
            self.painter.flip_y = False

        self.painter.tile_surface = self._get_tile_surface(first_tile)

    def _save_tile_collision_for_selection(self) -> None:
        """Save current collision data to all selected tiles"""
        polygons = self.painter.get_polygons()
        one_way_flags = self.painter.get_one_way_flags()

        for tile_id in self._selected_tiles:
            if not polygons:
                if tile_id in self.library.tiles:
                    del self.library.tiles[tile_id]
                    if self.consumer:
                        self.consumer.on_collision_deleted(tile_id)

                self._user_cleared_tiles.add(tile_id)
            else:
                self._user_cleared_tiles.discard(tile_id)

                shapes = [
                    CollisionPolygon(vertices=poly, one_way=one_way)
                    for poly, one_way in zip(polygons, one_way_flags, strict=False)
                ]

                prev = self.library.tiles.get(tile_id)
                tile_data = TileCollisionData(
                    tile_id=tile_id,
                    shapes=shapes,
                    flip_x=prev.flip_x if prev else False,
                    flip_y=prev.flip_y if prev else False,
                )
                self.library.tiles[tile_id] = tile_data

                if self.consumer:
                    self.consumer.on_collision_saved(tile_id, tile_data.to_dict())

    def _on_polygon_added(self, vertices: list[tuple[float, float]]) -> None:
        """Callback when polygon is added"""
        self._save_tile_collision_for_selection()

    def _on_polygon_removed(self, idx: int) -> None:
        """Callback when polygon is removed"""
        self._save_tile_collision_for_selection()

    def _on_polygon_modified(self, idx: int) -> None:
        """Callback when polygon is modified"""
        self._save_tile_collision_for_selection()

    def _show_toast(self, message: str, duration: float = 2.5) -> None:
        """Show a temporary status toast on screen"""
        self._toast_message = message
        self._toast_timer = duration * 1000.0
        self._toast_start = pygame.time.get_ticks()

    def _draw_toast(self, screen: Surface) -> None:
        """Draw the toast message with fade-out"""
        if self._toast_message is None:
            return

        elapsed = pygame.time.get_ticks() - self._toast_start
        remaining = self._toast_timer - elapsed
        fade_ms = 500.0
        alpha = (
            255
            if remaining >= fade_ms
            else max(0, min(255, int((remaining / fade_ms) * 255)))
        )
        label = self._font.render(self._toast_message, True, (255, 255, 255))
        padding = 12
        bg_rect = Rect(
            self.rect.centerx - label.get_width() // 2 - padding,
            self.rect.centery - 60,
            label.get_width() + padding * 2,
            label.get_height() + padding,
        )

        bg = pygame.Surface((bg_rect.w, bg_rect.h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, min(200, alpha)))
        pygame.draw.rect(bg, (80, 180, 255, alpha), bg.get_rect(), 1)
        screen.blit(bg, bg_rect)

        label.set_alpha(alpha)
        screen.blit(label, label.get_rect(center=bg_rect.center))

    def clear_current_selection(self) -> None:
        """Clear collision for currently selected tiles"""
        self.painter.set_polygons([], [])
        self._save_tile_collision_for_selection()

    def resize(self, rect: Rect) -> None:
        """Resize the editor"""
        self.rect = rect
        self._update_layout()
        self._position_toolbar_buttons()
        self.painter.resize(self.painter_rect)

    def load_tileset(
        self, surface: Surface, tile_size: tuple[int, int], name: str = "Tileset"
    ) -> None:
        """Load a new tileset"""
        self._tileset_surface = surface
        self._tile_size = tile_size
        self._tileset_name = name
        self._recalc_tile_grid()

        self.library = TilesetCollisionLibrary(tileset_name=name, tile_size=tile_size)

        self._selected_tiles = {0}
        self.painter.tile_surface = self._get_tile_surface(0)
        self.painter.tile_size = tile_size
        self._load_tile_collision_for_selection()

    def load_collision_data(self, data: dict[str, Any]) -> None:
        """Load collision data from dict"""
        try:
            self.library = TilesetCollisionLibrary.from_dict(data)
            self._load_tile_collision_for_selection()
        except Exception as e:
            error_handler.capture(e, context="load_collision_data")

    def save_to_file(self, path: Path) -> None:
        """Save collision data to file, auto-propagating within auto-tile groups."""
        try:
            self._save_tile_collision_for_selection()

            self.library.save(path)
        except Exception as e:
            error_handler.capture(e, context="save_collision_file")

    def _propagate_collision_to_groups(self) -> None:
        """Propagate collision shapes within each auto-tile group.

        If any tile in a propagation group has collision shapes, those shapes
        are copied to all other tiles in the same group that don't already
        have their own collision data.
        """
        if not self._propagation_groups:
            return

        propagated_count = 0
        for _group_id, variant_ids in self._propagation_groups.items():
            source_shapes = None
            for vid in variant_ids:
                tile_data = self.library.tiles.get(vid)
                if tile_data and tile_data.shapes:
                    source_shapes = tile_data.shapes
                    break

            if source_shapes is None:
                continue

            for vid in variant_ids:
                if vid in self._user_cleared_tiles:
                    continue
                existing = self.library.tiles.get(vid)
                if existing is None:
                    self.library.tiles[vid] = TileCollisionData(
                        tile_id=vid,
                        shapes=[
                            CollisionPolygon(
                                vertices=list(s.vertices),
                                one_way=s.one_way,
                            )
                            for s in source_shapes
                        ],
                    )
                    propagated_count += 1

        if propagated_count:
            self._show_toast(
                f"Propagated collision to {propagated_count} auto-tile variants"
            )

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

        mouse = pygame.mouse.get_pos()

        if self._splitter.handle_event(event):
            if self._splitter._dragging:
                self._update_layout()
                self.painter.resize(self.painter_rect)
            return True

        if self.painter.handle_event(event):
            return True

        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self._space_held = True
            return True

        if event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self._space_held = False
            if self._tileset_panning:
                self._tileset_panning = False
            return True

        if self.tileset_selector_rect.collidepoint(mouse):
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 2 or (event.button == 1 and self._space_held):
                    self._tileset_panning = True
                    self._tileset_pan_start = mouse
                    self._tileset_pan_start_offset = (
                        self.tileset_scroll_x,
                        self.tileset_scroll_y,
                    )
                    return True

            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and not self._space_held
            ):
                tile_id = self._get_tile_at_mouse(mouse)
                if tile_id is not None:
                    self._painted_tiles_focused = False

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

            if event.type == pygame.MOUSEWHEEL:
                mods = pygame.key.get_mods()
                if mods & (pygame.KMOD_CTRL | pygame.KMOD_META):
                    self.tileset_zoom *= 1.15 if event.y > 0 else 0.87
                    self.tileset_zoom = max(0.5, min(self.tileset_zoom, 8.0))
                elif mods & pygame.KMOD_SHIFT:
                    scroll_val = event.y if event.y != 0 else event.x
                    self.tileset_scroll_x -= scroll_val * 30
                else:
                    scroll_val = event.y if event.y != 0 else event.x
                    self.tileset_scroll_y -= scroll_val * 30
                self.tileset_scroll_x = max(0, self.tileset_scroll_x)
                self.tileset_scroll_y = max(0, self.tileset_scroll_y)
                return True

        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 2 or event.button == 1:
                if self._tileset_panning:
                    self._tileset_panning = False
                    return True

        if event.type == pygame.MOUSEMOTION and self._tileset_panning:
            dx = mouse[0] - self._tileset_pan_start[0]
            dy = mouse[1] - self._tileset_pan_start[1]
            self.tileset_scroll_x = self._tileset_pan_start_offset[0] - dx
            self.tileset_scroll_y = self._tileset_pan_start_offset[1] - dy
            self.tileset_scroll_x = max(0, self.tileset_scroll_x)
            self.tileset_scroll_y = max(0, self.tileset_scroll_y)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.painted_tiles_rect.collidepoint(mouse):
                self._painted_tiles_focused = True
                painted_tiles = sorted(self.library.tiles.keys())
                rel_y = mouse[1] - self.painted_tiles_rect.y + self.painted_tiles_scroll
                tile_height = 64
                idx = rel_y // tile_height
                if 0 <= idx < len(painted_tiles):
                    tile_id = painted_tiles[idx]
                    self._selected_tiles = {tile_id}
                    self._load_tile_collision_for_selection()
                return True

        if event.type == pygame.MOUSEWHEEL:
            if self.painted_tiles_rect.collidepoint(mouse):
                self.painted_tiles_scroll -= event.y * 30
                self.painted_tiles_scroll = max(0, self.painted_tiles_scroll)
                return True

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA)

            if ctrl:
                if event.key == pygame.K_c:
                    self._copy_collision()
                    return True
                if event.key == pygame.K_v:
                    self._paste_collision()
                    return True

            if event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                if mods & (pygame.KMOD_LSHIFT) or self._painted_tiles_focused:
                    self.clear_current_selection()
                    return True
            elif event.key == pygame.K_h:
                self._recenter_tileset_view()
                return True

        return False

    def _get_tile_at_mouse(self, mouse: tuple[int, int]) -> int | None:
        """Get tile ID at mouse position in tileset selector"""
        if not self.tileset_selector_rect.collidepoint(mouse):
            return None

        tw = int(self._tile_size[0] * self.tileset_zoom)
        th = int(self._tile_size[1] * self.tileset_zoom)

        # Calculate centering offset (same as in _draw_tileset_selector)
        tileset_scr_w = self.tile_cols * tw
        tileset_scr_h = self.tile_rows * th
        center_off_x = max(0, (self.tileset_selector_rect.w - tileset_scr_w) // 2)
        center_off_y = max(0, (self.tileset_selector_rect.h - tileset_scr_h) // 2)

        # Apply centering offset to mouse calculation
        rel_x = mouse[0] - self.tileset_selector_rect.x + self.tileset_scroll_x - center_off_x
        rel_y = mouse[1] - self.tileset_selector_rect.y + self.tileset_scroll_y - center_off_y

        col = rel_x // tw
        row = rel_y // th

        if 0 <= col < self.tile_cols and 0 <= row < self.tile_rows:
            tile_id = row * self.tile_cols + col
            return tile_id

        return None

    def _recenter_tileset_view(self) -> None:
        """Recenter the tileset view to show the whole tileset"""
        if self._tileset_surface is None:
            return

        tw = int(self._tile_size[0] * self.tileset_zoom)
        th = int(self._tile_size[1] * self.tileset_zoom)
        tileset_w = self.tile_cols * tw
        tileset_h = self.tile_rows * th

        if tileset_w < self.tileset_selector_rect.w:
            self.tileset_scroll_x = 0
        else:
            self.tileset_scroll_x = (tileset_w - self.tileset_selector_rect.w) // 2

        if tileset_h < self.tileset_selector_rect.h:
            self.tileset_scroll_y = 0
        else:
            self.tileset_scroll_y = (tileset_h - self.tileset_selector_rect.h) // 2

    def draw(self, screen: Surface) -> None:
        """Draw the editor"""
        if not self.visible:
            return

        self._draw_toolbar(screen)

        self._draw_painted_tiles_list(screen)

        self.painter.draw(screen)

        self._splitter.draw(screen)

        self._draw_tileset_selector(screen)

        self._draw_widget_panel(screen)

        self._draw_toast(screen)

        if self._toast_message is not None:
            elapsed = pygame.time.get_ticks() - self._toast_start
            if elapsed >= self._toast_timer:
                self._toast_message = None

    def _draw_toolbar(self, screen: Surface) -> None:
        """Draw the toolbar"""
        draw_panel(screen, self.toolbar_rect, COLORS.header, COLORS.border)

        selected_str = f"{len(self._selected_tiles)} tile{'s' if len(self._selected_tiles) != 1 else ''} selected"
        title = self._font.render(
            f"Tileset Collision Editor — {self._tileset_name} — {selected_str}",
            True,
            COLORS.text,
        )
        screen.blit(title, (self.toolbar_rect.x + 10, self.toolbar_rect.y + 10))

        if hasattr(self, "_toolbar_buttons"):
            self._draw_toolbar_buttons(screen)

        collision_count = len(self.library.tiles)
        count_text = self._font_sm.render(
            f"{collision_count} painted", True, COLORS.text_dim
        )
        start_x = self.toolbar_rect.right - (len(self._toolbar_buttons) * 90) - 10
        screen.blit(
            count_text,
            (start_x - count_text.get_width() - 15, self.toolbar_rect.y + 12),
        )

    def _draw_painted_tiles_list(self, screen: Surface) -> None:
        """Draw the list of tiles with collision"""
        draw_panel(screen, self.painted_tiles_rect, COLORS.panel, COLORS.border)

        header_text = self._font_sm.render("Painted Tiles", True, COLORS.text)
        screen.blit(
            header_text, (self.painted_tiles_rect.x + 8, self.painted_tiles_rect.y + 8)
        )
        if self._painted_tiles_focused:
            hint = self._font_sm.render("Backspace to clear", True, COLORS.accent)
            screen.blit(
                hint,
                (
                    self.painted_tiles_rect.right - hint.get_width() - 8,
                    self.painted_tiles_rect.y + 8,
                ),
            )

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

            tile_rect = Rect(
                self.painted_tiles_rect.x, y, self.painted_tiles_rect.w, tile_height
            )

            is_selected = tile_id in self._selected_tiles
            bg_color = COLORS.selected if is_selected else COLORS.panel_alt

            pygame.draw.rect(screen, bg_color, tile_rect)
            pygame.draw.rect(screen, COLORS.border_soft, tile_rect, 1)

            tile_surf = self._get_tile_surface(tile_id)
            preview_size = 48
            scale = min(
                preview_size / self._tile_size[0], preview_size / self._tile_size[1]
            )
            scaled_w = int(self._tile_size[0] * scale)
            scaled_h = int(self._tile_size[1] * scale)
            scaled_surf = pygame.transform.scale(tile_surf, (scaled_w, scaled_h))

            preview_x = tile_rect.x + 8
            preview_y = tile_rect.y + (tile_height - scaled_h) // 2
            screen.blit(scaled_surf, (preview_x, preview_y))

            id_text = self._font.render(str(tile_id), True, COLORS.text)
            screen.blit(id_text, (preview_x + scaled_w + 10, tile_rect.y + 8))

            shape_count = len(self.library.tiles[tile_id].shapes)
            coll_text = self._font_sm.render(
                f"{shape_count} shape{'s' if shape_count != 1 else ''}",
                True,
                COLORS.accent,
            )
            screen.blit(coll_text, (preview_x + scaled_w + 10, tile_rect.y + 30))

            y += tile_height

        screen.set_clip(clip)

    def _draw_tileset_selector(self, screen: Surface) -> None:
        """Draw the tileset selector"""
        draw_panel(screen, self.tileset_selector_rect, COLORS.panel_alt, COLORS.border)

        if self._tileset_surface is None:
            return

        clip = screen.get_clip()
        screen.set_clip(self.tileset_selector_rect)

        tw = int(self._tile_size[0] * self.tileset_zoom)
        th = int(self._tile_size[1] * self.tileset_zoom)

        tileset_scr_w = self.tile_cols * tw
        tileset_scr_h = self.tile_rows * th
        center_off_x = max(0, (self.tileset_selector_rect.w - tileset_scr_w) // 2)
        center_off_y = max(0, (self.tileset_selector_rect.h - tileset_scr_h) // 2)

        for row in range(self.tile_rows):
            for col in range(self.tile_cols):
                tile_id = row * self.tile_cols + col

                x = self.tileset_selector_rect.x + col * tw - self.tileset_scroll_x + center_off_x
                y = self.tileset_selector_rect.y + row * th - self.tileset_scroll_y + center_off_y

                if (
                    x + tw < self.tileset_selector_rect.x
                    or x > self.tileset_selector_rect.right
                ):
                    continue
                if (
                    y + th < self.tileset_selector_rect.y
                    or y > self.tileset_selector_rect.bottom
                ):
                    continue

                tile_rect = Rect(x, y, tw, th)

                tile_surf = self._get_tile_surface(tile_id)
                if tw != self._tile_size[0] or th != self._tile_size[1]:
                    tile_surf = pygame.transform.scale(tile_surf, (tw, th))
                screen.blit(tile_surf, (x, y))

                if tile_id in self._selected_tiles:
                    pygame.draw.rect(screen, COLORS.accent, tile_rect, 2)

                if tile_id in self.library.tiles:
                    indicator_rect = Rect(x + tw - 8, y + 2, 6, 6)
                    pygame.draw.circle(screen, COLORS.accent, indicator_rect.center, 3)

                pygame.draw.rect(screen, COLORS.border_soft, tile_rect, 1)

        screen.set_clip(clip)

        zoom_text = self._font_sm.render(
            f"Zoom: {self.tileset_zoom:.1f}x", True, COLORS.text_dim
        )
        screen.blit(
            zoom_text,
            (self.tileset_selector_rect.x + 8, self.tileset_selector_rect.y + 8),
        )

    @classmethod
    def from_path(
        cls,
        tileset_path: Path,
        tile_size: tuple[int, int] = (32, 32),
        window_size: tuple[int, int] = (1200, 800),
        data_root: Path = None,
        propagation_groups: dict[str, list[int]] | None = None,
    ) -> TilesetCollisionEditor:
        """Create editor from tileset image path (for standalone use)"""
        surface = pygame.image.load(tileset_path).convert_alpha()
        rect = Rect(0, 0, window_size[0], window_size[1])
        editor = cls(rect, surface, tile_size)
        editor._data_root = data_root
        editor._tileset_path_stem = tileset_path.stem
        editor._tileset_name = tileset_path.stem
        editor.library.tileset_name = tileset_path.stem
        editor._propagation_groups = propagation_groups or {}
        return editor

    def run(self) -> None:
        """Run standalone editor (for standalone use)"""
        screen = pygame.display.get_surface()
        if screen is None:
            raise RuntimeError("pygame display not initialized")

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
                        stem = getattr(self, "_tileset_path_stem", self._tileset_name)
                        save_path = collision_dir / f"{stem}.collision.json"
                        self.save_to_file(save_path)
                    elif event.key == pygame.K_l and (
                        pygame.key.get_mods() & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA)
                    ):
                        collision_dir = self._get_collision_dir()
                        load_path = (
                            collision_dir
                            / f"{getattr(self, '_tileset_path_stem', self._tileset_name)}.collision.json"
                        )
                        if load_path.exists():
                            self.load_from_file(load_path)
                            print(f"Loaded collision data from {load_path}")

                self.handle_event(event)

            self._handle_toolbar_button_clicks(events)
            self._handle_widget_button_clicks(events)

            screen.fill(COLORS.bg)
            self.draw(screen)
            pygame.display.flip()
            clock.tick(60)
