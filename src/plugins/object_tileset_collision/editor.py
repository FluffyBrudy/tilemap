"""
Object Tileset Collision Editor — Redesigned with clear two-phase workflow.

Layout:
    +--------------------------------------------------------------+
    | [Save] [Load] | Define Regions | Paint Collision | [?]    |
    +---------------+--------------------------------+-------------+
    | Regions List  |   Collision Painter (Region)   |  StatusBar  |
    | - Tree (✓)    |                                |             |
    | - Rock (⚠)    |   [Region image, zoomed]       |  3 shapes   |
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

from typing import Optional, Tuple, List, Dict, Any, Set
from pathlib import Path
from enum import Enum, auto
from dataclasses import dataclass

import pygame
from pygame import Rect, Surface

from plugins.tileset_collision.collision_painter import CollisionPainter
from plugins.tileset_collision.models import CollisionPolygon
from .models import RegionCollisionData, ObjectTilesetCollisionLibrary
from widgets.ui.region_selector import RegionSelector, Region
from widgets.ui.status_bar import StatusBar, StatusType
from widgets.ui.mode_indicator import ModeIndicator, Mode
from widgets.ui.draw_utils import draw_panel, draw_button
from widgets.ui.theme import COLORS, FONTS, SHAPE
from widgets.input import InlineTextInput
from utils.font_manager import font_manager, FontWeight
from utils.icon_manager import icon_manager
from utils.error_handler import error_handler


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
        tileset_surface: Optional[Surface] = None,
    ):
        self.rect = rect
        self.visible = True

        self._tileset_surface = tileset_surface
        self._tileset_name = "Object Tileset"
        self._data_root: Optional[Path] = None

        # Data model
        self.library = ObjectTilesetCollisionLibrary(tileset_name=self._tileset_name)
        self._current_region_id: Optional[str] = None
        
        # Mode
        self._mode = EditorMode.DEFINE_REGIONS

        # UI Layout
        self.toolbar_height = 45
        self.status_bar_width = 180
        self.regions_list_width = 200
        self.tileset_selector_height = 220

        self._update_layout()

        # Components
        self._init_components()
        
        # Rename state
        self._renaming_region_id: Optional[str] = None
        self._rename_input = InlineTextInput("region_rename", "")
        
        # Help panel state
        self._show_help = False
        self._help_scroll = 0
        self._help_content_height = 0
        
        # Fonts
        self._font = font_manager.get_font(FONTS.name, FONTS.size_md, FontWeight.REGULAR)
        self._font_sm = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)

    def _init_components(self) -> None:
        """Initialize UI components"""
        # Region selector (bottom panel)
        self.region_selector = RegionSelector(
            self.tileset_selector_rect,
            self._tileset_surface,
            zoom=1.0,
        )
        self.region_selector.on_region_added = self._on_region_added
        self.region_selector.on_region_removed = self._on_region_removed
        self.region_selector.on_region_modified = self._on_region_modified
        self.region_selector.on_selection_changed = self._on_region_selection_changed

        # Mode indicator (toolbar)
        self.mode_indicator = ModeIndicator(
            Rect(0, 0, 300, 35),  # Position set in _update_layout
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

        # Status bar (right side of middle area)
        self.status_bar = StatusBar(
            self.status_bar_rect,
            show_icons=True,
        )

        # Collision painter (middle area)
        self.painter = CollisionPainter(
            self.painter_rect,
            None,  # Will set when region selected
            (64, 64),  # Default, will update per region
        )
        self.painter.on_polygon_added = self._on_polygon_added
        self.painter.on_polygon_removed = self._on_polygon_removed
        self.painter.on_polygon_modified = self._on_polygon_modified

    def _update_layout(self) -> None:
        """Update all layout rectangles"""
        # Toolbar at top
        self.toolbar_rect = Rect(
            self.rect.x, self.rect.y,
            self.rect.w, self.toolbar_height
        )
        
        # Status bar on right
        self.status_bar_rect = Rect(
            self.rect.right - self.status_bar_width,
            self.rect.y + self.toolbar_height,
            self.status_bar_width,
            self.rect.h - self.toolbar_height - self.tileset_selector_height
        )
        
        # Tileset selector at bottom
        self.tileset_selector_rect = Rect(
            self.rect.x,
            self.rect.bottom - self.tileset_selector_height,
            self.rect.w,
            self.tileset_selector_height
        )
        
        # Middle area (regions list + painter)
        middle_y = self.rect.y + self.toolbar_height
        middle_h = self.rect.h - self.toolbar_height - self.tileset_selector_height
        
        self.regions_list_rect = Rect(
            self.rect.x, middle_y,
            self.regions_list_width, middle_h
        )
        
        self.painter_rect = Rect(
            self.rect.x + self.regions_list_width, middle_y,
            self.rect.w - self.regions_list_width - self.status_bar_width, middle_h
        )

        # Update component rects
        if hasattr(self, 'region_selector'):
            self.region_selector.resize(self.tileset_selector_rect)
        if hasattr(self, 'status_bar'):
            self.status_bar.resize(self.status_bar_rect)
        if hasattr(self, 'painter'):
            self.painter.resize(self.painter_rect)
        
        # Mode indicator position (in toolbar, centered)
        if hasattr(self, 'mode_indicator'):
            self.mode_indicator.rect = Rect(
                self.rect.x + (self.rect.w - 300) // 2,
                self.rect.y + 5,
                300, 35
            )

    # === Mode Management ===

    def _can_enter_define_mode(self) -> bool:
        """Check if we can switch to define regions mode"""
        return True

    def _can_enter_paint_mode(self) -> bool:
        """Check if we can switch to paint collision mode"""
        if not self._current_region_id:
            self.status_bar.warning("Select a region first", "Click a region in the list or on the tileset")
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
            self.status_bar.info("Define Regions mode", "Draw rectangles on the tileset to create object regions")
        elif new_mode == "paint":
            self._mode = EditorMode.PAINT_COLLISION
            region = self._get_current_region()
            name = region.name if region else "Region"
            self.status_bar.info(f"Paint Collision mode: {name}", "Click to add vertices, right-click or Enter to complete polygon")

    # === Region Management ===

    def _on_region_added(self, region: Region) -> None:
        """Called when a new region is created"""
        # Create collision data entry
        collision_data = RegionCollisionData(
            region_id=region.id,
            region_rect=(region.rect.x, region.rect.y, region.rect.width, region.rect.height),
        )
        self.library.regions[region.id] = collision_data
        
        self.status_bar.success(f"Created region: {region.name}", f"Size: {region.rect.width}x{region.rect.height}")
        error_handler.capture_info(f"Created region {region.id}: {region.name}", context="object_collision_editor")
        
        # Auto-enter rename mode for new regions
        self._start_rename(region.id)

    def _on_region_removed(self, region_id: str) -> None:
        """Called when a region is removed"""
        # Remove from library
        if region_id in self.library.regions:
            del self.library.regions[region_id]
        
        if self._current_region_id == region_id:
            self._current_region_id = None
            # Switch back to define mode if we were in paint mode
            if self._mode == EditorMode.PAINT_COLLISION:
                self.mode_indicator.set_active("define")
        
        self.status_bar.info("Region deleted")
        error_handler.capture_info(f"Deleted region {region_id}", context="object_collision_editor")

    def _on_region_modified(self, region: Region) -> None:
        """Called when a region is modified (moved/resized)"""
        # Update collision data rect
        if region.id in self.library.regions:
            self.library.regions[region.id].region_rect = (
                region.rect.x, region.rect.y,
                region.rect.width, region.rect.height
            )
        
        # If this is the current region, update painter
        if self._current_region_id == region.id and self._mode == EditorMode.PAINT_COLLISION:
            self._update_painter_for_current_region()

    def _on_region_selection_changed(self, region_id: Optional[str]) -> None:
        """Called when region selection changes"""
        self._current_region_id = region_id
        
        # Update painter to show selected region
        if self._mode == EditorMode.PAINT_COLLISION:
            self._update_painter_for_current_region()
        
        if region_id:
            region = self.region_selector.get_region(region_id)
            if region:
                name = region.name or "Unnamed"
                status = self._get_region_status(region_id)
                
                if status.has_collision:
                    self.status_bar.success(f"Selected: {name}", f"{status.collision_count} collision shapes")
                else:
                    self.status_bar.warning(f"Selected: {name}", "No collision defined yet")
        else:
            self.status_bar.info("No region selected")

    def _get_current_region(self) -> Optional[Region]:
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

    # === Rename Functionality ===

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
            # Ensure unique name
            existing_names = {
                r.name for r in self.region_selector.regions
                if r.id != self._renaming_region_id
            }
            if new_name in existing_names:
                counter = 2
                base_name = new_name
                while new_name in existing_names:
                    new_name = f"{base_name} {counter}"
                    counter += 1
            
            region.name = new_name
            
            # Sync to library
            if self._renaming_region_id in self.library.regions:
                self.library.regions[self._renaming_region_id].name = new_name
            
            self.status_bar.success(f"Renamed to: {new_name}")
        
        self._renaming_region_id = None
        self._rename_input.is_focused = False

    def _cancel_rename(self) -> None:
        """Cancel the rename operation"""
        self._renaming_region_id = None
        self._rename_input.is_focused = False

    # === Collision Painting ===

    def _update_painter_for_current_region(self) -> None:
        """Update collision painter to show current region"""
        region = self._get_current_region()
        if not region or not self._tileset_surface:
            return
        
        # Extract region surface from tileset
        region_surf = self._extract_region_surface(region)
        
        # Update painter
        self.painter.tile_surface = region_surf
        self.painter.tile_size = (region.rect.width, region.rect.height)
        
        # Load existing collision data
        if region.id in self.library.regions:
            data = self.library.regions[region.id]
            polygons = [shape.vertices for shape in data.shapes]
            one_way_flags = [shape.one_way for shape in data.shapes]
            self.painter.set_polygons(polygons, one_way_flags)
        else:
            self.painter.set_polygons([], [])
        
        # Center view
        self.painter.zoom = 2.0
        tw, th = region.rect.width, region.rect.height
        self.painter.offset_x = (self.painter.rect.w - tw * self.painter.zoom) / 2
        self.painter.offset_y = (self.painter.rect.h - th * self.painter.zoom) / 2

    def _extract_region_surface(self, region: Region) -> Surface:
        """Extract the region's portion of the tileset"""
        surf = Surface((region.rect.width, region.rect.height), pygame.SRCALPHA)
        surf.blit(
            self._tileset_surface,
            (0, 0),
            region.rect
        )
        return surf

    def _on_polygon_added(self, vertices: List[Tuple[float, float]]) -> None:
        """Called when a polygon is added to the painter"""
        print(f"[POLYGON_ADDED] {len(vertices)} vertices")
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
            print("[SAVE_CURRENT] No current region selected")
            return
        
        polygons = self.painter.get_polygons()
        one_way_flags = self.painter.get_one_way_flags()
        
        print(f"[SAVE_CURRENT] Region {self._current_region_id}: {len(polygons)} polygons from painter")
        
        shapes = [
            CollisionPolygon(vertices=poly, one_way=one_way)
            for poly, one_way in zip(polygons, one_way_flags)
        ]
        
        region = self._get_current_region()
        if not region:
            print("[SAVE_CURRENT] Could not get current region")
            return
        
        if self._current_region_id in self.library.regions:
            self.library.regions[self._current_region_id].shapes = shapes
            self.library.regions[self._current_region_id].name = region.name
            self.library.regions[self._current_region_id].region_rect = (
                region.rect.x, region.rect.y, region.rect.width, region.rect.height
            )
            print(f"[SAVE_CURRENT] Updated existing region {self._current_region_id} with {len(shapes)} shapes")
        else:
            self.library.regions[self._current_region_id] = RegionCollisionData(
                region_id=self._current_region_id,
                region_rect=(region.rect.x, region.rect.y, region.rect.width, region.rect.height),
                name=region.name,
                shapes=shapes,
            )
            print(f"[SAVE_CURRENT] Created new region {self._current_region_id} with {len(shapes)} shapes")

    def _update_status(self) -> None:
        """Update status bar based on current state"""
        if self._mode == EditorMode.DEFINE_REGIONS:
            total = len(self.region_selector.regions)
            if total == 0:
                self.status_bar.info("Define regions", "Drag on the tileset to create object regions")
            else:
                self.status_bar.info(f"{total} region{'s' if total != 1 else ''} defined", "Select a region and switch to Paint Collision mode")
        elif self._mode == EditorMode.PAINT_COLLISION:
            region = self._get_current_region()
            if region:
                status = self._get_region_status(region.id)
                if status.has_collision:
                    self.status_bar.success(f"{region.name}", f"{status.collision_count} collision shape{'s' if status.collision_count != 1 else ''}")
                else:
                    self.status_bar.warning(f"{region.name}", "Click to add vertices, right-click or Enter to complete")

    # === Toolbar Actions ===

    def _save_collision(self) -> None:
        """Save collision data to file"""
        if not self._data_root:
            self.status_bar.error("Cannot save", "No data root specified")
            return
        
        try:
            collision_dir = self._data_root / "collision"
            collision_dir.mkdir(parents=True, exist_ok=True)
            save_path = collision_dir / f"{self._tileset_name}.object_collision.json"
            
            # Sync current painter data
            if self._mode == EditorMode.PAINT_COLLISION:
                self._save_current_collision_data()
            
            # Debug: Print what we're saving
            total_shapes = sum(len(data.shapes) for data in self.library.regions.values())
            print(f"[SAVE] Saving {len(self.library.regions)} regions with {total_shapes} total shapes to {save_path}")
            for region_id, data in self.library.regions.items():
                print(f"  - {region_id} ({data.name}): {len(data.shapes)} shapes")
            
            self.library.save(save_path)
            self.status_bar.success("Saved", f"{save_path.name}")
            error_handler.capture_info(f"Saved collision data to {save_path}", context="object_collision_editor")
        except Exception as e:
            self.status_bar.error("Save failed", str(e))
            error_handler.capture(e, context="object_collision_editor_save")
            print(f"[SAVE ERROR] {e}")

    def load_from_file(self, path: Path) -> None:
        """Load collision data from a specific file path"""
        try:
            if not path.exists():
                self.status_bar.warning("No saved data", f"File not found: {path.name}")
                return
            
            self.library = ObjectTilesetCollisionLibrary.load(path)
            
            # Convert library regions to selector regions
            regions = []
            for region_id, data in self.library.regions.items():
                r = data.region_rect
                region = Region(
                    id=region_id,
                    rect=Rect(r[0], r[1], r[2], r[3]),
                    name=data.name if data.name else region_id,  # Use saved name or fallback to ID
                )
                regions.append(region)
            
            self.region_selector.set_regions(regions)
            
            # If we're in paint mode and have a current region, update the painter
            if self._mode == EditorMode.PAINT_COLLISION and self._current_region_id:
                self._update_painter_for_current_region()
            
            self.status_bar.success("Loaded", f"{len(regions)} region{'s' if len(regions) != 1 else ''}")
            error_handler.capture_info(f"Loaded collision data from {path}", context="object_collision_editor")
        except Exception as e:
            self.status_bar.error("Load failed", str(e))
            error_handler.capture(e, context="object_collision_editor_load")

    def _load_collision(self) -> None:
        """Load collision data from default file location"""
        if not self._data_root:
            self.status_bar.error("Cannot load", "No data root specified")
            return
        
        collision_dir = self._data_root / "collision"
        load_path = collision_dir / f"{self._tileset_name}.object_collision.json"
        self.load_from_file(load_path)

    def _toggle_help(self) -> None:
        """Toggle help panel"""
        self._show_help = not self._show_help
        if self._show_help:
            self._help_scroll = 0

    # === Help Panel ===

    def _draw_help_panel(self, screen: Surface) -> None:
        """Draw the help panel overlay"""
        if not self._show_help:
            return
        
        # Dim background
        overlay = Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
        # Panel dimensions
        panel_w = 500
        panel_h = 400
        panel_x = (screen.get_width() - panel_w) // 2
        panel_y = (screen.get_height() - panel_h) // 2
        panel_rect = Rect(panel_x, panel_y, panel_w, panel_h)
        
        # Panel background
        pygame.draw.rect(screen, COLORS.panel, panel_rect, border_radius=SHAPE.radius)
        pygame.draw.rect(screen, COLORS.border, panel_rect, 2, border_radius=SHAPE.radius)
        
        # Title
        title = self._font.render("Object Collision Editor Help", True, COLORS.text)
        screen.blit(title, (panel_x + 15, panel_y + 15))
        
        # Close button
        close_btn = Rect(panel_rect.right - 35, panel_y + 10, 25, 25)
        pygame.draw.rect(screen, COLORS.danger, close_btn, border_radius=SHAPE.radius_sm)
        close_text = self._font.render("×", True, COLORS.text)
        screen.blit(close_text, (close_btn.centerx - close_text.get_width() // 2, close_btn.centery - close_text.get_height() // 2))
        
        # Content
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
            ("   ✓ = Has collision shapes", False),
            ("   ⚠ = No collision defined yet", False),
            ("   ? = Unnamed region", False),
            ("", False),
            ("Shortcuts:", True),
            ("   Ctrl+S = Save  |  Ctrl+L = Load", False),
            ("   ? or I = Toggle help", False),
            ("   Escape = Close help / Cancel operation", False),
        ]
        
        # Draw content with scrolling
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
        
        # Store content height for scrolling
        self._help_content_height = len(help_text) * line_height + 50
        
        # Draw scrollbar if needed
        if self._help_content_height > panel_h - 60:
            scrollbar_x = panel_rect.right - 12
            scrollbar_y = panel_y + 50
            scrollbar_h = panel_h - 60
            
            # Background
            pygame.draw.rect(screen, COLORS.panel_alt, Rect(scrollbar_x, scrollbar_y, 8, scrollbar_h))
            
            # Thumb
            thumb_h = max(30, int(scrollbar_h * (panel_h - 60) / self._help_content_height))
            max_scroll = max(0, self._help_content_height - (panel_h - 60))
            thumb_y = scrollbar_y + int((self._help_scroll / max_scroll) * (scrollbar_h - thumb_h)) if max_scroll > 0 else scrollbar_y
            
            pygame.draw.rect(screen, COLORS.accent, Rect(scrollbar_x, thumb_y, 8, thumb_h), border_radius=4)

    def _handle_help_event(self, event: pygame.event.Event) -> bool:
        """Handle events for help panel"""
        if not self._show_help:
            return False
        
        mouse = pygame.mouse.get_pos()
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Close button
            panel_w = 500
            panel_h = 400
            panel_x = (pygame.display.get_surface().get_width() - panel_w) // 2
            panel_y = (pygame.display.get_surface().get_height() - panel_h) // 2
            close_btn = Rect(panel_x + panel_w - 35, panel_y + 10, 25, 25)
            
            if close_btn.collidepoint(mouse):
                self._show_help = False
                return True
            
            # Click outside to close
            panel_rect = Rect(panel_x, panel_y, panel_w, panel_h)
            if not panel_rect.collidepoint(mouse):
                self._show_help = False
                return True
        
        if event.type == pygame.MOUSEWHEEL:
            self._help_scroll -= event.y * 20
            max_scroll = max(0, self._help_content_height - 340)
            self._help_scroll = max(0, min(self._help_scroll, max_scroll))
            return True
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._show_help = False
                return True
        
        return True  # Block all other events when help is open

    # === Event Handling ===

    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Handle input events.
        Event priority: Help > Rename > Region Selector/Mode > Painter
        """
        if not self.visible:
            return False
        
        # Priority 1: Help panel (blocks everything)
        if self._show_help:
            return self._handle_help_event(event)
        
        # Priority 2: Rename input
        if self._renaming_region_id is not None:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    self._commit_rename()
                    return True
                elif event.key == pygame.K_ESCAPE:
                    self._cancel_rename()
                    return True
            
            if self._rename_input.handle_event(event, self._font):
                return True
        
        # Priority 3: Help toggle (I or ? key)
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_i or event.key == pygame.K_SLASH:
                self._toggle_help()
                return True
        
        # Priority 4: Mode indicator
        if self.mode_indicator.handle_event(event):
            return True
        
        # Priority 5: Region selector (define regions mode)
        if self._mode == EditorMode.DEFINE_REGIONS:
            # Handle F2 for rename
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F2:
                    selected = self.region_selector.get_selected_region()
                    if selected:
                        self._start_rename(selected.id)
                        return True
            
            if self.region_selector.handle_event(event):
                return True
        
        # Priority 6: Collision painter (paint collision mode)
        if self._mode == EditorMode.PAINT_COLLISION:
            if self.painter.handle_event(event):
                return True
        
        # Priority 7: Regions list click (when not in rename mode)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse = pygame.mouse.get_pos()
            if self.regions_list_rect.collidepoint(mouse):
                # Calculate which region was clicked
                list_y = mouse[1] - (self.regions_list_rect.y + 35)
                item_height = 50
                if list_y >= 0:
                    idx = list_y // item_height
                    if idx < len(self.region_selector.regions):
                        region = self.region_selector.regions[idx]
                        # Check if clicking same region (might be renaming)
                        if region.id == self._renaming_region_id:
                            pass  # Let rename continue
                        else:
                            # Cancel any active rename and select new region
                            if self._renaming_region_id is not None:
                                self._commit_rename()
                            self.region_selector.select_region(region.id)
                        return True
        
        # Priority 8: Toolbar buttons
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse = pygame.mouse.get_pos()
            
            # Save button (left side of toolbar)
            save_btn_rect = Rect(self.toolbar_rect.x + 10, self.toolbar_rect.y + 8, 60, 28)
            if save_btn_rect.collidepoint(mouse):
                self._save_collision()
                return True
            
            # Load button
            load_btn_rect = Rect(save_btn_rect.right + 8, self.toolbar_rect.y + 8, 60, 28)
            if load_btn_rect.collidepoint(mouse):
                self._load_collision()
                return True
            
            # Help button (right side)
            help_btn_rect = Rect(self.toolbar_rect.right - 38, self.toolbar_rect.y + 8, 28, 28)
            if help_btn_rect.collidepoint(mouse):
                self._toggle_help()
                return True
        
        # Keyboard shortcuts
        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_CTRL | pygame.KMOD_LMETA)
            
            if ctrl_held:
                if event.key == pygame.K_s:
                    self._save_collision()
                    return True
                elif event.key == pygame.K_l:
                    self._load_collision()
                    return True
        
        return False

    # === Drawing ===

    def draw(self, screen: Surface) -> None:
        """Draw the editor"""
        if not self.visible:
            return
        
        # Clear background
        screen.fill((20, 20, 20))
        
        # Draw toolbar
        self._draw_toolbar(screen)
        
        # Draw regions list
        self._draw_regions_list(screen)
        
        # Draw collision painter or mode-specific content
        if self._mode == EditorMode.PAINT_COLLISION:
            self.painter.draw(screen)
        else:
            self._draw_define_mode_placeholder(screen)
        
        # Draw status bar
        self.status_bar.draw(screen)
        
        # Draw region selector (bottom)
        self.region_selector.draw(screen)
        
        # Draw mode indicator
        self.mode_indicator.draw(screen)
        
        # Draw help panel if open (on top of everything)
        self._draw_help_panel(screen)

    def _draw_toolbar(self, screen: Surface) -> None:
        """Draw the toolbar"""
        draw_panel(screen, self.toolbar_rect, COLORS.header, COLORS.border)
        
        mouse = pygame.mouse.get_pos()
        
        # Save button
        save_btn_rect = Rect(self.toolbar_rect.x + 10, self.toolbar_rect.y + 8, 60, 28)
        save_hover = save_btn_rect.collidepoint(mouse)
        save_label = self._font.render("Save", True, COLORS.text)
        from widgets.ui.draw_utils import draw_button
        draw_button(screen, save_btn_rect, save_label, hover=save_hover)
        
        # Load button
        load_btn_rect = Rect(save_btn_rect.right + 8, self.toolbar_rect.y + 8, 60, 28)
        load_hover = load_btn_rect.collidepoint(mouse)
        load_label = self._font.render("Load", True, COLORS.text)
        draw_button(screen, load_btn_rect, load_label, hover=load_hover)
        
        # Title (centered, after mode indicator)
        title = self._font.render(f"— {self._tileset_name}", True, COLORS.text_dim)
        title_x = self.mode_indicator.rect.right + 20
        screen.blit(title, (title_x, self.toolbar_rect.centery - title.get_height() // 2))
        
        # Help button (info icon)
        help_btn_rect = Rect(self.toolbar_rect.right - 38, self.toolbar_rect.y + 8, 28, 28)
        help_hover = help_btn_rect.collidepoint(mouse)
        help_icon = icon_manager.get_icon("info", 20, COLORS.text if not help_hover else COLORS.accent)
        pygame.draw.rect(screen, COLORS.panel_alt if help_hover else COLORS.panel, help_btn_rect, border_radius=SHAPE.radius_sm)
        pygame.draw.rect(screen, COLORS.border_soft, help_btn_rect, 1, border_radius=SHAPE.radius_sm)
        screen.blit(help_icon, (help_btn_rect.centerx - 10, help_btn_rect.centery - 10))

    def _draw_regions_list(self, screen: Surface) -> None:
        """Draw the regions list panel"""
        draw_panel(screen, self.regions_list_rect, COLORS.panel, COLORS.border)
        
        # Header
        header = self._font.render("Regions", True, COLORS.text)
        screen.blit(header, (self.regions_list_rect.x + 10, self.regions_list_rect.y + 10))
        
        # List regions
        y = self.regions_list_rect.y + 35
        item_height = 50
        
        clip = screen.get_clip()
        screen.set_clip(self.regions_list_rect)
        
        for region in self.region_selector.regions:
            is_selected = region.id == self._current_region_id
            is_renaming = region.id == self._renaming_region_id
            
            # Background
            item_rect = Rect(self.regions_list_rect.x + 5, y, self.regions_list_rect.width - 10, item_height)
            if is_selected:
                pygame.draw.rect(screen, COLORS.selected, item_rect, border_radius=SHAPE.radius_sm)
            
            # Status icon
            status = self._get_region_status(region.id)
            icon_x = item_rect.x + 8
            icon_y = item_rect.centery - 6
            
            if status.has_collision:
                icon = self._font_sm.render("✓", True, COLORS.success)
            elif region.name and not region.name.startswith("Region "):
                icon = self._font_sm.render("⚠", True, COLORS.warning)
            else:
                icon = self._font_sm.render("?", True, COLORS.text_dim)
            
            screen.blit(icon, (icon_x, icon_y))
            
            # Name
            name_x = icon_x + 15
            if is_renaming:
                # Draw rename input
                display_name = self._rename_input.text
                cursor_offset = self._rename_input.cursor_pos
                prefix = display_name[:cursor_offset]
                if (pygame.time.get_ticks() // 500) % 2:
                    display_name = prefix + "|" + display_name[cursor_offset:]
                else:
                    display_name = prefix + " " + display_name[cursor_offset:]
                
                # Highlight background
                pygame.draw.rect(screen, (100, 120, 140), 
                    Rect(name_x, item_rect.y + 5, item_rect.width - 30, 20), border_radius=2)
                
                name_surf = self._font.render(display_name, True, COLORS.text)
            else:
                name = region.name or "Unnamed"
                name_surf = self._font.render(name, True, COLORS.text)
            
            screen.blit(name_surf, (name_x, item_rect.y + 8))
            
            # Dimensions
            dim_text = f"{region.rect.width}×{region.rect.height}"
            dim_surf = self._font_sm.render(dim_text, True, COLORS.text_dim)
            screen.blit(dim_surf, (name_x, item_rect.y + 28))
            
            # Collision count
            if status.has_collision:
                count_text = f"{status.collision_count} shapes"
                count_surf = self._font_sm.render(count_text, True, COLORS.success)
                count_x = item_rect.right - count_surf.get_width() - 8
                screen.blit(count_surf, (count_x, item_rect.y + 28))
            
            y += item_height
        
        screen.set_clip(clip)
        
        # Border line
        pygame.draw.line(screen, COLORS.border,
            (self.regions_list_rect.right - 1, self.regions_list_rect.y),
            (self.regions_list_rect.right - 1, self.regions_list_rect.bottom), 1)

    def _draw_define_mode_placeholder(self, screen: Surface) -> None:
        """Draw placeholder when in define regions mode"""
        # Background
        pygame.draw.rect(screen, COLORS.panel_alt, self.painter_rect)
        
        # Center text
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

    # === Resize ===

    def resize(self, rect: Rect) -> None:
        """Resize the editor"""
        self.rect = rect
        self._update_layout()

    # === Factory Method ===

    @classmethod
    def from_path(
        cls,
        tileset_path: Path,
        window_size: Tuple[int, int] = (1200, 800),
        data_root: Path = None,
    ) -> "ObjectTilesetCollisionEditor":
        """Create editor from tileset image path"""
        surface = pygame.image.load(tileset_path).convert_alpha()
        rect = Rect(0, 0, window_size[0], window_size[1])
        editor = cls(rect, surface)
        editor._data_root = data_root
        editor._tileset_name = tileset_path.stem
        editor.library.tileset_name = tileset_path.stem
        return editor

    # === Main Loop ===

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

            screen.fill((20, 20, 20))
            self.draw(screen)
            pygame.display.flip()
            clock.tick(60)