"""
Object Tileset Collision Editor — Redesigned with clear two-phase workflow.

Layout:
    +--------------------------------------------------------------+
    | [Save] [Load] | Define Regions | Paint Collision | [?]    |
    +---------------+--------------------------------+-------------+
    | Regions List  |   Collision Painter (Region)   |  StatusBar  |
    | - Tree (ok)   |                                |             |
    | - Rock (warn) |   [Region image, zoomed]       |  3 shapes   |
    | - Player (?)|                                |  Complete   |
    +---------------+--------------------------------+-------------+
    |           Object Tileset (Region Selector)                   |
    |   [Full image with highlighted regions]                    |
    +------------------------------------------------------------+

Two-Phase Workflow:
1. DEFINE REGIONS: Draw rectangles on tileset to define objects
2. PAINT COLLISION: Select a region, paint collision polygons on it

Status feedback shows what's done and what's missing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

import pygame
from pygame import Rect, Surface

from plugins.tileset_collision.collision_painter import CollisionPainter
from plugins.tileset_collision.models import CollisionPolygon
from utils.error_handler import error_handler
from utils.font_manager import FontWeight, font_manager
from utils.icon_manager import icon_manager
from widgets.input import InlineTextInput
from widgets.ui.button import Button
from widgets.ui.collision_layer_sidebar import CollisionLayerSidebar
from widgets.ui.draw_utils import draw_panel
from widgets.ui.mode_indicator import Mode, ModeIndicator
from widgets.ui.region_selector import Region, RegionSelector
from widgets.ui.splitter import Splitter
from widgets.ui.status_bar import StatusBar
from widgets.ui.theme import COLORS, FONTS, SHAPE

from .models import ObjectTilesetCollisionLibrary, RegionCollisionData


class EditorMode(Enum):
    """Editor workflow modes"""

    DEFINE_REGIONS = auto()
    PAINT_COLLISION = auto()


@dataclass
class RegionStatus:
    """Status information for a region"""

    has_collision: bool = False
    collision_count: int = 0
    is_valid: bool = True


def _render_fit_text(
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    max_width: int,
) -> Surface:
    """Render text constrained to max_width with an ellipsis."""
    if max_width <= 0:
        return font.render("", True, color)

    surf = font.render(text, True, color)
    if surf.get_width() <= max_width:
        return surf

    ellipsis = "..."
    if font.size(ellipsis)[0] > max_width:
        return font.render("", True, color)

    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        candidate = text[:mid].rstrip() + ellipsis
        if font.size(candidate)[0] <= max_width:
            low = mid
        else:
            high = mid - 1

    return font.render(text[:low].rstrip() + ellipsis, True, color)


class ObjectTilesetCollisionEditor:
    """
    Main editor for object tileset collision shapes.

    Features:
    - Two-phase workflow: define regions → paint collision
    - Clear status feedback for each region
    - Inline renaming with unique name generation
    - Help panel with user guide (blocks painting when open)
    """

    def __init__(
        self,
        rect: Rect,
        tileset_surface: Surface | None = None,
    ):
        self.rect = rect
        self.visible = True

        self._tileset_surface = tileset_surface
        self._tileset_name = "Object Tileset"
        self._data_root: Path | None = None
        self._collision_dir: Path | None = None
        self._tileset_path_stem: str | None = None

        self.library = ObjectTilesetCollisionLibrary(tileset_name=self._tileset_name)
        self._current_region_id: str | None = None

        self._mode = EditorMode.DEFINE_REGIONS

        self.toolbar_height = 45
        self.status_bar_width = 180
        self.regions_list_width = 200
        self.tileset_selector_height = 220

        self._splitter = Splitter(orientation="horizontal")
        self._splitter.on_drag = self._on_splitter_drag

        self._update_layout()

        self._init_components()

        self._renaming_region_id: str | None = None
        self._rename_input = InlineTextInput("region_rename", "")

        self._show_help = False
        self._help_scroll = 0
        self._help_content_height = 0

        self._regions_list_scroll = 0
        self._regions_item_height = 50

        self._font = font_manager.get_font(
            FONTS.name, FONTS.size_md, FontWeight.REGULAR
        )
        self._font_sm = font_manager.get_font(
            FONTS.name, FONTS.size_sm, FontWeight.REGULAR
        )

    def _init_components(self) -> None:
        """Initialize UI components"""

        self._toolbar_buttons: list[Button] = []
        self._init_toolbar_buttons()

        self.region_selector = RegionSelector(
            self.tileset_selector_rect,
            self._tileset_surface,
            zoom=1.0,
        )
        self.region_selector.on_region_added = self._on_region_added
        self.region_selector.on_region_removed = self._on_region_removed
        self.region_selector.on_region_modified = self._on_region_modified
        self.region_selector.on_selection_changed = self._on_region_selection_changed

        self.mode_indicator = ModeIndicator(
            Rect(0, 0, 300, 35),
            modes=[
                Mode(
                    id="define",
                    label="Define Regions",
                    description="Draw rectangles to define object regions",
                    can_enter=self._can_enter_define_mode,
                ),
                Mode(
                    id="paint",
                    label="Paint Collision",
                    description="Draw collision shapes for selected region",
                    can_enter=self._can_enter_paint_mode,
                    on_enter=self._on_enter_paint_mode,
                ),
            ],
            active_mode="define",
        )
        self.mode_indicator.on_mode_changed = self._on_mode_changed

        self.status_bar = StatusBar(
            self.status_bar_rect,
            show_icons=True,
        )

        self.layer_sidebar = CollisionLayerSidebar(
            self.rect,
            max_layers=16,
            initial_layer=1,
            initial_mask=0xFFFF,
            on_changed=self._on_layer_mask_changed,
        )

        self.painter = CollisionPainter(
            self.painter_rect,
            None,
            (64, 64),
        )
        self.painter.on_polygon_added = self._on_polygon_added
        self.painter.on_polygon_removed = self._on_polygon_removed
        self.painter.on_polygon_modified = self._on_polygon_modified

    def _init_toolbar_buttons(self) -> None:
        self._toolbar_buttons.clear()
        btn_save = Button(
            Rect(0, 0, 60, 28),
            "Save",
            on_click=self._save_collision,
        )
        btn_load = Button(
            Rect(0, 0, 60, 28),
            "Load",
            on_click=self._load_collision,
        )
        btn_help = Button(
            Rect(0, 0, 28, 28),
            "?",
            on_click=self._toggle_help,
        )
        self._toolbar_buttons.extend([btn_save, btn_load, btn_help])

    def _layout_toolbar_buttons(self) -> None:
        x = self.toolbar_rect.x + 10
        y = self.toolbar_rect.y + 8
        for btn in self._toolbar_buttons:
            if btn.text == "?":
                w, h = 28, 28
            else:
                w, h = 60, 28
            btn.resize(x, y, w, h)
            x += w + 8

    def _on_splitter_drag(self, pos: int) -> None:
        self.tileset_selector_height = max(
            100, min(600, self.rect.bottom - pos)
        )

    def _update_layout(self) -> None:
        """Update all layout rectangles"""

        self.toolbar_rect = Rect(
            self.rect.x, self.rect.y, self.rect.w, self.toolbar_height
        )

        self.status_bar_rect = Rect(
            self.rect.right - self.status_bar_width,
            self.rect.y + self.toolbar_height,
            self.status_bar_width,
            self.rect.h - self.toolbar_height - self.tileset_selector_height,
        )

        self.tileset_selector_rect = Rect(
            self.rect.x,
            self.rect.bottom - self.tileset_selector_height,
            self.rect.w,
            self.tileset_selector_height,
        )

        middle_y = self.rect.y + self.toolbar_height
        middle_h = self.rect.h - self.toolbar_height - self.tileset_selector_height

        self.regions_list_rect = Rect(
            self.rect.x, middle_y, self.regions_list_width, middle_h
        )

        self.painter_rect = Rect(
            self.rect.x + self.regions_list_width,
            middle_y,
            self.rect.w - self.regions_list_width - self.status_bar_width,
            middle_h,
        )

        if hasattr(self, "_toolbar_buttons") and self._toolbar_buttons:
            self._layout_toolbar_buttons()
        if hasattr(self, "region_selector"):
            self.region_selector.resize(self.tileset_selector_rect)
        if hasattr(self, "_splitter"):
            self._splitter.resize(
                self.rect.x, self.tileset_selector_rect.y - 4, self.rect.w, 8
            )
        if hasattr(self, "status_bar"):
            self.status_bar.resize(self.status_bar_rect)
        if hasattr(self, "painter"):
            self.painter.resize(self.painter_rect)
        if hasattr(self, "layer_sidebar"):
            self.layer_sidebar.resize(self.rect)

        if hasattr(self, "mode_indicator"):
            self.mode_indicator.rect = Rect(
                self.rect.x + (self.rect.w - 300) // 2, self.rect.y + 5, 300, 35
            )

    def _can_enter_define_mode(self) -> bool:
        """Check if we can switch to define regions mode"""
        return True

    def _can_enter_paint_mode(self) -> bool:
        """Check if we can switch to paint collision mode"""
        if not self._current_region_id:
            self.status_bar.warning(
                "Select a region first", "Click a region in the list or on the tileset"
            )
            return False
        return True

    def _on_enter_paint_mode(self) -> None:
        """Called when entering paint collision mode"""
        self._update_painter_for_current_region()
        self._update_status()

    def _on_mode_changed(self, old_mode: str, new_mode: str) -> None:
        """Handle mode change"""
        if new_mode == "define":
            self._mode = EditorMode.DEFINE_REGIONS
            self.status_bar.info(
                "Define Regions mode",
                "Draw rectangles on the tileset to create object regions",
            )
        elif new_mode == "paint":
            self._mode = EditorMode.PAINT_COLLISION
            region = self._get_current_region()
            name = region.name if region else "Region"
            self.status_bar.info(
                f"Paint Collision mode: {name}",
                "Click to add vertices, right-click or Enter to complete polygon",
            )

    def _on_region_added(self, region: Region) -> None:
        """Called when a new region is created"""

        collision_data = RegionCollisionData(
            region_id=region.id,
            region_rect=(
                region.rect.x,
                region.rect.y,
                region.rect.width,
                region.rect.height,
            ),
        )
        self.library.regions[region.id] = collision_data

        self.status_bar.success(
            f"Created region: {region.name}",
            f"Size: {region.rect.width}x{region.rect.height}",
        )
        error_handler.capture_info(
            f"Created region {region.id}: {region.name}",
            context="object_collision_editor",
        )

        self._start_rename(region.id)

    def _on_region_removed(self, region_id: str) -> None:
        """Called when a region is removed"""

        if region_id in self.library.regions:
            del self.library.regions[region_id]

        if self._current_region_id == region_id:
            self._current_region_id = None

            if self._mode == EditorMode.PAINT_COLLISION:
                self.mode_indicator.set_active("define")

        self.status_bar.info("Region deleted")
        error_handler.capture_info(
            f"Deleted region {region_id}", context="object_collision_editor"
        )

    def _on_region_modified(self, region: Region) -> None:
        """Called when a region is modified (moved/resized)"""

        if region.id in self.library.regions:
            self.library.regions[region.id].region_rect = (
                region.rect.x,
                region.rect.y,
                region.rect.width,
                region.rect.height,
            )

        if (
            self._current_region_id == region.id
            and self._mode == EditorMode.PAINT_COLLISION
        ):
            self._update_painter_for_current_region()

    def _on_region_selection_changed(self, region_id: str | None) -> None:
        """Called when region selection changes"""
        self._current_region_id = region_id

        if region_id and region_id in self.library.regions:
            data = self.library.regions[region_id]
            layer = data.properties.get("collision_layer", 1)
            mask = data.properties.get("collision_mask", 0xFFFF)
            self.layer_sidebar.set_layer(layer)
            self.layer_sidebar.set_mask(mask)

        if self._mode == EditorMode.PAINT_COLLISION:
            self._update_painter_for_current_region()

        if region_id:
            region = self.region_selector.get_region(region_id)
            if region:
                name = region.name or "Unnamed"
                status = self._get_region_status(region_id)

                if status.has_collision:
                    self.status_bar.success(
                        f"Selected: {name}",
                        f"{status.collision_count} collision shapes",
                    )
                else:
                    self.status_bar.warning(
                        f"Selected: {name}", "No collision defined yet"
                    )
        else:
            self.status_bar.info("No region selected")

    def _get_current_region(self) -> Region | None:
        """Get the currently selected region"""
        if self._current_region_id:
            return self.region_selector.get_region(self._current_region_id)
        return None

    def _get_region_status(self, region_id: str) -> RegionStatus:
        """Get status information for a region"""
        status = RegionStatus()

        if region_id in self.library.regions:
            data = self.library.regions[region_id]
            status.has_collision = len(data.shapes) > 0
            status.collision_count = len(data.shapes)

        return status

    def _on_layer_mask_changed(self, layer: int, mask: int) -> None:
        """Called when collision layer/mask widget changes."""
        if self._current_region_id and self._current_region_id in self.library.regions:
            self.library.regions[self._current_region_id].properties[
                "collision_layer"
            ] = layer
            self.library.regions[self._current_region_id].properties[
                "collision_mask"
            ] = mask

    def _start_rename(self, region_id: str) -> None:
        """Start renaming a region"""
        region = self.region_selector.get_region(region_id)
        if region:
            self._renaming_region_id = region_id
            self._rename_input.text = region.name
            self._rename_input.cursor_pos = len(region.name)
            self._rename_input.is_focused = True

    def _commit_rename(self) -> None:
        """Commit the rename operation"""
        if not self._renaming_region_id:
            return

        new_name = self._rename_input.text.strip()
        if not new_name:
            self._cancel_rename()
            return

        region = self.region_selector.get_region(self._renaming_region_id)
        if region:
            existing_names = {
                r.name
                for r in self.region_selector.regions
                if r.id != self._renaming_region_id
            }
            if new_name in existing_names:
                counter = 2
                base_name = new_name
                while new_name in existing_names:
                    new_name = f"{base_name} {counter}"
                    counter += 1

            region.name = new_name

            if self._renaming_region_id in self.library.regions:
                self.library.regions[self._renaming_region_id].name = new_name

            self.status_bar.success(f"Renamed to: {new_name}")

        self._renaming_region_id = None
        self._rename_input.is_focused = False

    def _cancel_rename(self) -> None:
        """Cancel the rename operation"""
        self._renaming_region_id = None
        self._rename_input.is_focused = False

    def _update_painter_for_current_region(self) -> None:
        """Update collision painter to show current region"""
        region = self._get_current_region()
        if not region or not self._tileset_surface:
            return

        region_surf = self._extract_region_surface(region)

        self.painter.tile_surface = region_surf
        self.painter.tile_size = (region.rect.width, region.rect.height)

        if region.id in self.library.regions:
            data = self.library.regions[region.id]
            polygons = [shape.vertices for shape in data.shapes]
            one_way_flags = [shape.one_way for shape in data.shapes]
            self.painter.set_polygons(polygons, one_way_flags)
        else:
            self.painter.set_polygons([], [])

        self.painter.zoom = 2.0
        tw, th = region.rect.width, region.rect.height
        self.painter.offset_x = (self.painter.rect.w - tw * self.painter.zoom) / 2
        self.painter.offset_y = (self.painter.rect.h - th * self.painter.zoom) / 2

    def _extract_region_surface(self, region: Region) -> Surface:
        """Extract the region's portion of the tileset"""
        surf = Surface((region.rect.width, region.rect.height), pygame.SRCALPHA)
        surf.blit(self._tileset_surface, (0, 0), region.rect)
        return surf

    def _on_polygon_added(self, vertices: list[tuple[float, float]]) -> None:
        """Called when a polygon is added to the painter"""
        error_handler.capture_info(
            f"Polygon added with {len(vertices)} vertices",
            context="object_collision_painter",
        )
        self._save_current_collision_data()
        self._update_status()

    def _on_polygon_removed(self, idx: int) -> None:
        """Called when a polygon is removed"""
        self._save_current_collision_data()
        self._update_status()

    def _on_polygon_modified(self, idx: int) -> None:
        """Called when a polygon is modified"""
        self._save_current_collision_data()

    def _save_current_collision_data(self) -> None:
        """Save current painter polygons to library"""
        if not self._current_region_id:
            return

        polygons = self.painter.get_polygons()
        one_way_flags = self.painter.get_one_way_flags()

        error_handler.capture_info(
            f"Saving collision for region {self._current_region_id}: {len(polygons)} polygons",
            context="object_collision_save",
        )

        shapes = [
            CollisionPolygon(vertices=poly, one_way=one_way)
            for poly, one_way in zip(polygons, one_way_flags, strict=False)
        ]

        region = self._get_current_region()
        if not region:
            return

        if self._current_region_id in self.library.regions:
            self.library.regions[self._current_region_id].shapes = shapes
            self.library.regions[self._current_region_id].name = region.name
            self.library.regions[self._current_region_id].region_rect = (
                region.rect.x,
                region.rect.y,
                region.rect.width,
                region.rect.height,
            )
            print(
                f"[SAVE_CURRENT] Updated existing region {self._current_region_id} with {len(shapes)} shapes"
            )
        else:
            self.library.regions[self._current_region_id] = RegionCollisionData(
                region_id=self._current_region_id,
                region_rect=(
                    region.rect.x,
                    region.rect.y,
                    region.rect.width,
                    region.rect.height,
                ),
                name=region.name,
                shapes=shapes,
            )
            print(
                f"[SAVE_CURRENT] Created new region {self._current_region_id} with {len(shapes)} shapes"
            )

    def _update_status(self) -> None:
        """Update status bar based on current state"""
        if self._mode == EditorMode.DEFINE_REGIONS:
            total = len(self.region_selector.regions)
            if total == 0:
                self.status_bar.info(
                    "Define regions", "Drag on the tileset to create object regions"
                )
            else:
                self.status_bar.info(
                    f"{total} region{'s' if total != 1 else ''} defined",
                    "Select a region and switch to Paint Collision mode",
                )
        elif self._mode == EditorMode.PAINT_COLLISION:
            region = self._get_current_region()
            if region:
                status = self._get_region_status(region.id)
                if status.has_collision:
                    self.status_bar.success(
                        f"{region.name}",
                        f"{status.collision_count} collision shape{'s' if status.collision_count != 1 else ''}",
                    )
                else:
                    self.status_bar.warning(
                        f"{region.name}",
                        "Click to add vertices, right-click or Enter to complete",
                    )

    def _get_collision_dir(self) -> Path:
        """Get the collision directory path."""
        if self._collision_dir:
            return self._collision_dir
        if self._data_root:
            return self._data_root / "collision"
        raise RuntimeError(
            "No collision directory configured. Set collision_dir or data_root."
        )

    def _save_collision(self) -> None:
        """Save collision data to file"""
        if not self._data_root:
            self.status_bar.error("Cannot save", "No data root specified")
            return

        try:
            collision_dir = self._get_collision_dir()
            collision_dir.mkdir(parents=True, exist_ok=True)
            stem = getattr(self, "_tileset_path_stem", self._tileset_name)
            save_path = collision_dir / f"{stem}.object_collision.json"

            if self._mode == EditorMode.PAINT_COLLISION:
                self._save_current_collision_data()

            total_shapes = sum(
                len(data.shapes) for data in self.library.regions.values()
            )
            error_handler.capture_info(
                f"Saving {len(self.library.regions)} regions with {total_shapes} total shapes to {save_path}",
                context="object_collision_save",
            )

            self.library.save(save_path)
            self.status_bar.success("Saved", f"{save_path.name}")
            error_handler.capture_info(
                f"Saved collision data to {save_path}",
                context="object_collision_editor",
            )
        except Exception as e:
            self.status_bar.error("Save failed", str(e))
            error_handler.capture(e, context="object_collision_editor_save")

    def load_from_file(self, path: Path) -> None:
        """Load collision data from a specific file path"""
        try:
            if not path.exists():
                self.status_bar.warning("No saved data", f"File not found: {path.name}")
                return

            self.library = ObjectTilesetCollisionLibrary.load(path)

            regions = []
            for region_id, data in self.library.regions.items():
                r = data.region_rect
                region = Region(
                    id=region_id,
                    rect=Rect(r[0], r[1], r[2], r[3]),
                    name=data.name if data.name else region_id,
                )
                regions.append(region)

            self.region_selector.set_regions(regions)

            if self._mode == EditorMode.PAINT_COLLISION and self._current_region_id:
                self._update_painter_for_current_region()

            self.status_bar.success(
                "Loaded", f"{len(regions)} region{'s' if len(regions) != 1 else ''}"
            )
            error_handler.capture_info(
                f"Loaded collision data from {path}", context="object_collision_editor"
            )
        except Exception as e:
            self.status_bar.error("Load failed", str(e))
            error_handler.capture(e, context="object_collision_editor_load")

    def _load_collision(self) -> None:
        """Load collision data from default file location"""
        if not self._data_root:
            self.status_bar.error("Cannot load", "No data root specified")
            return

        collision_dir = self._get_collision_dir()
        stem = getattr(self, "_tileset_path_stem", self._tileset_name)
        load_path = collision_dir / f"{stem}.object_collision.json"
        self.load_from_file(load_path)

    def _toggle_help(self) -> None:
        """Toggle help panel"""
        self._show_help = not self._show_help
        if self._show_help:
            self._help_scroll = 0

    def _draw_help_panel(self, screen: Surface) -> None:
        """Draw the help panel overlay"""
        if not self._show_help:
            return

        overlay = Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((*COLORS.overlay, 170))
        screen.blit(overlay, (0, 0))

        panel_w = 500
        panel_h = 400
        panel_x = (screen.get_width() - panel_w) // 2
        panel_y = (screen.get_height() - panel_h) // 2
        panel_rect = Rect(panel_x, panel_y, panel_w, panel_h)

        pygame.draw.rect(screen, COLORS.panel, panel_rect, border_radius=SHAPE.radius)
        pygame.draw.rect(
            screen, COLORS.border, panel_rect, 2, border_radius=SHAPE.radius
        )

        title = self._font.render(
            "Object Tileset Collision Editor Help", True, COLORS.text
        )
        screen.blit(title, (panel_x + 15, panel_y + 15))

        close_btn = Rect(panel_rect.right - 35, panel_y + 10, 25, 25)
        pygame.draw.rect(
            screen, COLORS.danger, close_btn, border_radius=SHAPE.radius_sm
        )
        close_icon = icon_manager.get_icon("close", 15, COLORS.text)
        screen.blit(close_icon, close_icon.get_rect(center=close_btn.center))

        help_text = [
            ("Two-Phase Workflow", True),
            ("", False),
            ("1. DEFINE REGIONS:", True),
            ("   • Drag on tileset to create rectangular regions", False),
            ("   • Each region = one object (tree, rock, etc.)", False),
            ("   • Click region to select, drag to move", False),
            ("   • Drag handles to resize", False),
            ("   • F2 or double-click to rename", False),
            ("   • Delete key to remove region", False),
            ("", False),
            ("2. PAINT COLLISION:", True),
            ("   • Select a region and switch mode", False),
            ("   • Left-click to add vertices", False),
            ("   • Right-click or Enter to complete polygon", False),
            ("   • Click near first vertex to close", False),
            ("   • Delete/Backspace to remove selected polygon", False),
            ("   • O key: toggle one-way collision", False),
            ("   • G key: toggle grid", False),
            ("   • S key: toggle snap to grid", False),
            ("", False),
            ("View Controls:", True),
            ("   • +/- or mouse wheel: Zoom in/out", False),
            ("   • Pan button (top-left): Toggle pan mode", False),
            ("   • Space key: Toggle pan mode", False),
            ("   • Middle mouse drag: Pan (always works)", False),
            ("", False),
            ("Status Icons:", True),
            ("   Check icon = Has collision shapes", False),
            ("   Warning icon = No collision defined yet", False),
            ("   ? = Unnamed region", False),
            ("", False),
            ("Shortcuts:", True),
            ("   Ctrl+S = Save  |  Ctrl+L = Load", False),
            ("   ? or I = Toggle help", False),
            ("   Escape = Close help / Cancel operation", False),
        ]

        content_x = panel_x + 20
        content_y = panel_y + 50 - self._help_scroll
        line_height = 18

        clip = screen.get_clip()
        screen.set_clip(Rect(panel_x + 10, panel_y + 45, panel_w - 20, panel_h - 60))

        for text, is_bold in help_text:
            font = self._font if is_bold else self._font_sm
            line = font.render(text, True, COLORS.text if is_bold else COLORS.text_dim)
            screen.blit(line, (content_x, content_y))
            content_y += line_height

        screen.set_clip(clip)

        self._help_content_height = len(help_text) * line_height + 50

        if self._help_content_height > panel_h - 60:
            scrollbar_x = panel_rect.right - 12
            scrollbar_y = panel_y + 50
            scrollbar_h = panel_h - 60

            pygame.draw.rect(
                screen, COLORS.panel_alt, Rect(scrollbar_x, scrollbar_y, 8, scrollbar_h)
            )

            thumb_h = max(
                30, int(scrollbar_h * (panel_h - 60) / self._help_content_height)
            )
            max_scroll = max(0, self._help_content_height - (panel_h - 60))
            thumb_y = (
                scrollbar_y
                + int((self._help_scroll / max_scroll) * (scrollbar_h - thumb_h))
                if max_scroll > 0
                else scrollbar_y
            )

            pygame.draw.rect(
                screen,
                COLORS.accent,
                Rect(scrollbar_x, thumb_y, 8, thumb_h),
                border_radius=4,
            )

    def _handle_help_event(self, event: pygame.event.Event) -> bool:
        """Handle events for help panel"""
        if not self._show_help:
            return False

        mouse = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            panel_w = 500
            panel_h = 400
            panel_x = (pygame.display.get_surface().get_width() - panel_w) // 2
            panel_y = (pygame.display.get_surface().get_height() - panel_h) // 2
            close_btn = Rect(panel_x + panel_w - 35, panel_y + 10, 25, 25)

            if close_btn.collidepoint(mouse):
                self._show_help = False
                return True

            panel_rect = Rect(panel_x, panel_y, panel_w, panel_h)
            if not panel_rect.collidepoint(mouse):
                self._show_help = False
                return True

        if event.type == pygame.MOUSEWHEEL:
            self._help_scroll -= event.y * 20
            max_scroll = max(0, self._help_content_height - 340)
            self._help_scroll = max(0, min(self._help_scroll, max_scroll))
            return True

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._show_help = False
            return True

        return True

    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle input events.
        Event priority: Help > Rename > Region Selector/Mode > Painter
        """
        if not self.visible:
            return False

        if self._show_help:
            return self._handle_help_event(event)

        if self._renaming_region_id is not None:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    self._commit_rename()
                    return True
                if event.key == pygame.K_ESCAPE:
                    self._cancel_rename()
                    return True

            if self._rename_input.handle_event(event, self._font):
                return True

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_i or event.key == pygame.K_SLASH:
                self._toggle_help()
                return True

        if self.mode_indicator.handle_event(event):
            return True

        if self._splitter.handle_event(event):
            if self._splitter._dragging:
                self._update_layout()
            return True

        if self._mode == EditorMode.DEFINE_REGIONS:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
                selected = self.region_selector.get_selected_region()
                if selected:
                    self._start_rename(selected.id)
                    return True

            if self.region_selector.handle_event(event):
                return True

        if self.layer_sidebar.handle_event(event):
            return True
        if self.layer_sidebar.handle_toggle_event(event):
            return True

        if event.type == pygame.KEYDOWN and event.key == pygame.K_l:
            mods = pygame.key.get_mods()
            if not (mods & (pygame.KMOD_CTRL | pygame.KMOD_LMETA)):
                self.layer_sidebar.toggle()
                return True

        if self._mode == EditorMode.PAINT_COLLISION:
            if self.painter.handle_event(event):
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse = pygame.mouse.get_pos()
            if self.regions_list_rect.collidepoint(mouse):
                rel_y = mouse[1] - (
                    self.regions_list_rect.y + 35 - self._regions_list_scroll
                )
                item_height = self._regions_item_height
                if rel_y >= 0:
                    idx = int(rel_y) // item_height
                    if idx < len(self.region_selector.regions):
                        region = self.region_selector.regions[idx]

                        if region.id == self._renaming_region_id:
                            pass
                        else:
                            if self._renaming_region_id is not None:
                                self._commit_rename()
                            self.region_selector.select_region(region.id)
                        return True

        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            for btn in self._toolbar_buttons:
                if btn.handle_event(event):
                    return True

        if event.type == pygame.MOUSEWHEEL:
            mouse = pygame.mouse.get_pos()
            if self.regions_list_rect.collidepoint(mouse):
                self._regions_list_scroll -= event.y * 30
                max_scroll = max(
                    0,
                    len(self.region_selector.regions) * self._regions_item_height
                    - (self.regions_list_rect.height - 35),
                )
                self._regions_list_scroll = max(
                    0, min(self._regions_list_scroll, max_scroll)
                )
                return True

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_CTRL | pygame.KMOD_LMETA)

            if ctrl_held:
                if event.key == pygame.K_s:
                    self._save_collision()
                    return True
                if event.key == pygame.K_l:
                    self._load_collision()
                    return True

        return False

    def draw(self, screen: Surface) -> None:
        """Draw the editor"""
        if not self.visible:
            return

        screen.fill(COLORS.bg)

        self._draw_toolbar(screen)

        self._draw_regions_list(screen)

        if self._mode == EditorMode.PAINT_COLLISION:
            self.painter.draw(screen)
        else:
            self._draw_define_mode_placeholder(screen)

        self.status_bar.draw(screen)

        self.layer_sidebar.draw_toggle_button(screen)

        self.layer_sidebar.draw(screen)

        self.region_selector.draw(screen)

        self._splitter.draw(screen)

        self.mode_indicator.draw(screen)

        self._draw_help_panel(screen)

    def _draw_toolbar(self, screen: Surface) -> None:
        """Draw the toolbar"""
        draw_panel(screen, self.toolbar_rect, COLORS.header, COLORS.border)

        for btn in self._toolbar_buttons:
            btn.draw(screen)

        help_btn = self._toolbar_buttons[-1] if self._toolbar_buttons else None
        help_right = help_btn.rect.x if help_btn else self.toolbar_rect.right

        title_x = self.mode_indicator.rect.right + 20
        title_max_w = help_right - title_x - 10
        title = _render_fit_text(
            self._font,
            f"- {self._tileset_name}",
            COLORS.text_dim,
            title_max_w,
        )
        screen.blit(
            title, (title_x, self.toolbar_rect.centery - title.get_height() // 2)
        )

    def _draw_regions_list(self, screen: Surface) -> None:
        """Draw the regions list panel"""
        draw_panel(screen, self.regions_list_rect, COLORS.panel, COLORS.border)

        header = self._font.render("Regions", True, COLORS.text)
        screen.blit(
            header, (self.regions_list_rect.x + 10, self.regions_list_rect.y + 10)
        )

        y = self.regions_list_rect.y + 35 - self._regions_list_scroll
        item_height = self._regions_item_height

        clip = screen.get_clip()
        screen.set_clip(self.regions_list_rect)

        for region in self.region_selector.regions:
            if y + item_height < self.regions_list_rect.y:
                y += item_height
                continue
            if y > self.regions_list_rect.bottom:
                break

            is_selected = region.id == self._current_region_id
            is_renaming = region.id == self._renaming_region_id

            item_rect = Rect(
                self.regions_list_rect.x + 5,
                y,
                self.regions_list_rect.width - 10,
                item_height,
            )
            if is_selected:
                pygame.draw.rect(
                    screen, COLORS.selected, item_rect, border_radius=SHAPE.radius_sm
                )

            status = self._get_region_status(region.id)
            icon_x = item_rect.x + 8
            icon_y = item_rect.centery - 6

            if status.has_collision:
                icon = icon_manager.get_icon("check", 12, COLORS.success)
            elif region.name and not region.name.startswith("Region "):
                icon = icon_manager.get_icon("warning", 12, COLORS.warning)
            else:
                icon = self._font_sm.render("?", True, COLORS.text_dim)

            screen.blit(icon, (icon_x, icon_y))

            name_x = icon_x + 15
            if is_renaming:
                display_name = self._rename_input.text
                cursor_offset = self._rename_input.cursor_pos
                prefix = display_name[:cursor_offset]
                if (pygame.time.get_ticks() // 500) % 2:
                    display_name = prefix + "|" + display_name[cursor_offset:]
                else:
                    display_name = prefix + " " + display_name[cursor_offset:]

                pygame.draw.rect(
                    screen,
                    (100, 120, 140),
                    Rect(name_x, item_rect.y + 5, item_rect.width - 30, 20),
                    border_radius=2,
                )

                name_surf = _render_fit_text(
                    self._font,
                    display_name,
                    COLORS.text,
                    item_rect.right - name_x - 8,
                )
            else:
                name = region.name or "Unnamed"
                name_surf = _render_fit_text(
                    self._font,
                    name,
                    COLORS.text,
                    item_rect.right - name_x - 8,
                )

            screen.blit(name_surf, (name_x, item_rect.y + 8))

            dim_text = f"{region.rect.width}×{region.rect.height}"
            dim_surf = self._font_sm.render(dim_text, True, COLORS.text_dim)
            screen.blit(dim_surf, (name_x, item_rect.y + 28))

            if status.has_collision:
                count_text = f"{status.collision_count} shapes"
                count_surf = self._font_sm.render(count_text, True, COLORS.success)
                count_x = item_rect.right - count_surf.get_width() - 8
                screen.blit(count_surf, (count_x, item_rect.y + 28))

            y += item_height

        screen.set_clip(clip)

        pygame.draw.line(
            screen,
            COLORS.border,
            (self.regions_list_rect.right - 1, self.regions_list_rect.y),
            (self.regions_list_rect.right - 1, self.regions_list_rect.bottom),
            1,
        )

    def _draw_define_mode_placeholder(self, screen: Surface) -> None:
        """Draw placeholder when in define regions mode"""

        pygame.draw.rect(screen, COLORS.panel_alt, self.painter_rect)

        text_lines = [
            "Define Regions Mode",
            "",
            "Select a region from the list or tileset,",
            "then switch to 'Paint Collision' mode",
            "to draw collision shapes.",
            "",
            "Press ? for help",
        ]

        y = self.painter_rect.centery - (len(text_lines) * 14) // 2
        for line in text_lines:
            color = COLORS.text if line else COLORS.text_dim
            font = self._font if line else self._font_sm
            surf = font.render(line, True, color)
            x = self.painter_rect.centerx - surf.get_width() // 2
            screen.blit(surf, (x, y))
            y += 20 if line else 10

    def resize(self, rect: Rect) -> None:
        """Resize the editor"""
        self.rect = rect
        self._update_layout()

    @classmethod
    def from_path(
        cls,
        tileset_path: Path,
        window_size: tuple[int, int] = (1200, 800),
        data_root: Path = None,
        collision_dir: Path = None,
    ) -> ObjectTilesetCollisionEditor:
        """Create editor from tileset image path"""
        surface = pygame.image.load(tileset_path).convert_alpha()
        rect = Rect(0, 0, window_size[0], window_size[1])
        editor = cls(rect, surface)
        editor._data_root = data_root
        editor._collision_dir = collision_dir
        editor._tileset_path_stem = tileset_path.stem
        editor._tileset_name = tileset_path.stem
        editor.library.tileset_name = tileset_path.stem
        return editor

    def run(self) -> None:
        """Run the editor (for standalone use)"""
        screen = pygame.display.get_surface()
        if screen is None:
            raise RuntimeError("pygame display not initialized")

        clock = pygame.time.Clock()
        running = True

        while running:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE and not self._show_help:
                        running = False

                self.handle_event(event)

            screen.fill(COLORS.bg)
            self.draw(screen)
            pygame.display.flip()
            clock.tick(60)
