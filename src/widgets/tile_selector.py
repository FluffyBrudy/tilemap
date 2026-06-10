import pygame
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Set, Any
from pathlib import Path
from pygame import Rect, Surface

from utils.validation import is_image_multipleof
from utils.error_handler import error_handler
from widgets.ui.property_editor import PropertyEditor
from widgets.ui.theme import COLORS, FONTS, SHAPE
from widgets.ui.tileset_type_dialog import TilesetTypeDialog
from utils.font_manager import font_manager, FontWeight, FontStyle

if TYPE_CHECKING:
    from editor import Editor


class TilesetData:
    def __init__(
        self, name: str, path: Path, surface: pygame.Surface, tileset_type: str = "tile"
    ):
        self.name = name
        self.path = path
        self.surface = surface
        self.tileset_type = tileset_type
        self.offset = [0, 0]
        self.properties: Dict[str, Any] = {}
        # Map of variant_id (int) to property dict
        self.tile_properties: Dict[int, Dict[str, Any]] = {}
        self.object_collision_path: Optional[Path] = None
        self.object_collision_data: Optional[Dict[str, Any]] = None
        self.animation: Optional[dict] = None


class TileSelector:
    def __init__(self, editor: "Editor", x: int, y: int, w: int, h: int):
        self.editor = editor
        self.rect = Rect(x, y, w, h)
        self.tilesets: List[TilesetData] = []

        self.tileset_map: Dict[int, TilesetData] = {}
        self.active_idx = -1

        self.top_bar_h = 30
        self.btm_bar_h = 40
        self.view_rect = Rect(
            x, y + self.top_bar_h, w, h - self.top_bar_h - self.btm_bar_h
        )
        self.tab_scroll_x = 0
        arrow_h = self.top_bar_h - 4
        arrow_y = y + (self.top_bar_h - arrow_h) // 2
        self._tab_arrow_left = Rect(x + 2, arrow_y, 18, arrow_h)
        self._tab_arrow_right = Rect(x + w - 20, arrow_y, 18, arrow_h)
        self.is_panning = False
        self.pan_start = (0, 0)
        self.pan_start_offset = (0, 0)

        self.is_selecting = False
        self.selection_start_grid: Optional[Tuple[int, int]] = None
        self.hover_pos: Optional[Tuple[int, int]] = None
        self.selected_tile: Optional[Tuple[int, int, int, int]] = None

        self.rule_hints: Set[int] = set()
        self._pending_tileset_queue: List[Tuple[Path, pygame.Surface]] = []
        self._queue_timer_active = False

        self.zoom: float = 1.0

        btn_y = y + h - 35
        self.btn_export = Rect(x + w - 140, btn_y, 30, 30)
        self.btn_collision = Rect(x + w - 105, btn_y, 30, 30)
        self.btn_add = Rect(x + w - 70, btn_y, 30, 30)
        self.btn_rem = Rect(x + w - 35, btn_y, 30, 30)
        self.font = font_manager.get_font(FONTS.name, FONTS.size_md, FontWeight.REGULAR)

    def _on_tileset_type_cancel(self):
        if hasattr(self, "_pending_tileset_path"):
            delattr(self, "_pending_tileset_path")
        if hasattr(self, "_pending_tileset_surf"):
            delattr(self, "_pending_tileset_surf")
        if self._pending_tileset_queue:
            self._start_tileset_queue()

    def resize(self, x: int, y: int, w: int, h: int):
        self.rect = Rect(x, y, w, h)
        self.view_rect = Rect(
            x, y + self.top_bar_h, w, h - self.top_bar_h - self.btm_bar_h
        )
        btn_y = y + h - 35
        self.btn_export = Rect(x + w - 140, btn_y, 30, 30)
        self.btn_collision = Rect(x + w - 105, btn_y, 30, 30)
        self.btn_add = Rect(x + w - 70, btn_y, 30, 30)
        self.btn_rem = Rect(x + w - 35, btn_y, 30, 30)
        arrow_h = self.top_bar_h - 4
        arrow_y = y + (self.top_bar_h - arrow_h) // 2
        self._tab_arrow_left = Rect(x + 2, arrow_y, 18, arrow_h)
        self._tab_arrow_right = Rect(x + w - 20, arrow_y, 18, arrow_h)

    def set_rule_hints(self, hints: Set[int]):
        self.rule_hints = hints

    def handle_event(self, event: pygame.event.Event) -> bool:
        # Handle timer for queue processing
        if event.type == pygame.USEREVENT + 1 and self._queue_timer_active:
            print("DEBUG: Timer triggered, continuing queue")
            self._queue_timer_active = False
            self._start_tileset_queue()
            return True

        mouse_pos = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.view_rect.collidepoint(mouse_pos) and self.active_idx != -1:
                # Check if right click on selected tile to open properties
                if self.selected_tile:
                    sx, sy, sw, sh = self.selected_tile
                    ts = self.tilesets[self.active_idx]
                    if ts.tileset_type == "object":
                        return True
                    img_x = self.view_rect.x + ts.offset[0]
                    img_y = self.view_rect.y + ts.offset[1]
                    sel_rect = Rect(img_x + sx, img_y + sy, sw, sh)

                    if sel_rect.collidepoint(mouse_pos):
                        variant_ids = self._get_selected_variant_ids(ts)
                        if not variant_ids:
                            return True
                        # Use top-left tile of selection as reference for properties if multi-tile
                        variant_id = variant_ids[0]

                        self.editor.property_editor = PropertyEditor(
                            self.editor,
                            f"Tile Properties: {ts.name} (ID: {variant_id})",
                            ts.tile_properties.get(variant_id, {}),
                            on_save=lambda props: self._save_tile_properties_multi(
                                ts, variant_ids, props
                            ),
                            on_close=lambda: None,
                            shrink_value_font=True,
                        )
                        return True

                self.is_panning = True
                self.pan_start = mouse_pos
                self.pan_start_offset = tuple(self.tilesets[self.active_idx].offset)
                return True

            # Check for right-click on tabs for tileset properties
            if self.rect.collidepoint(mouse_pos) and mouse_pos[1] < self.view_rect.top:
                tab_idx = self._get_tab_at_pos(mouse_pos)
                if tab_idx is not None:
                    ts = self.tilesets[tab_idx]
                    self.editor.property_editor = PropertyEditor(
                        self.editor,
                        f"Tileset Properties: {ts.name}",
                        ts.properties,
                        on_save=lambda props: self._save_tileset_properties(ts, props),
                        on_close=lambda: None,
                    )
                    return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self.is_panning = False
            return True
        elif (
            event.type == pygame.MOUSEMOTION
            and self.is_panning
            and self.active_idx != -1
        ):
            dx = mouse_pos[0] - self.pan_start[0]
            dy = mouse_pos[1] - self.pan_start[1]
            ts = self.tilesets[self.active_idx]
            ts.offset[0] = self.pan_start_offset[0] + dx
            ts.offset[1] = self.pan_start_offset[1] + dy
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.btn_export.collidepoint(mouse_pos):
                self._export_selected_as_png_dialog()
                return True
            if self.btn_collision.collidepoint(mouse_pos):
                self.open_collision_editor()
                return True
            if self.btn_add.collidepoint(mouse_pos):
                self.request_add_tileset()
                return True
            if self.btn_rem.collidepoint(mouse_pos):
                self.remove_tileset()
                return True

            if self.rect.collidepoint(mouse_pos) and mouse_pos[1] < self.view_rect.top:
                # Check arrow buttons first
                if self._tab_arrow_left.collidepoint(mouse_pos):
                    self._scroll_tabs(100)
                    return True
                if self._tab_arrow_right.collidepoint(mouse_pos):
                    self._scroll_tabs(-100)
                    return True
                self.check_tab_click(mouse_pos)
                return True

            if self.view_rect.collidepoint(mouse_pos) and self.active_idx != -1:
                if self.hover_pos:
                    ts = self.tilesets[self.active_idx]
                    if ts.tileset_type == "object":
                        self.selected_tile = (
                            0,
                            0,
                            ts.surface.get_width(),
                            ts.surface.get_height(),
                        )
                    else:
                        self.is_selecting = True
                        self.selection_start_grid = self.hover_pos
                        self.update_selection_rect(self.hover_pos)
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_selecting:
                self.is_selecting = False
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.view_rect.collidepoint(mouse_pos) and self.active_idx != -1:
                ts = self.tilesets[self.active_idx]
                img_x = self.view_rect.x + ts.offset[0]
                img_y = self.view_rect.y + ts.offset[1]

                rel_x = (mouse_pos[0] - img_x) / self.zoom
                rel_y = (mouse_pos[1] - img_y) / self.zoom

                if (
                    0 <= rel_x < ts.surface.get_width()
                    and 0 <= rel_y < ts.surface.get_height()
                ):
                    tw, th = self.editor.tilemap.tile_size
                    col = int(rel_x // tw)
                    row = int(rel_y // th)
                    self.hover_pos = (col, row)

                    if self.is_selecting and self.selection_start_grid:
                        self.update_selection_rect(self.hover_pos)
                else:
                    self.hover_pos = None
        elif event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(mouse_pos) and mouse_pos[1] < self.view_rect.top:
                self._scroll_tabs(event.y * 30)
                return True
            if self.view_rect.collidepoint(mouse_pos) and self.active_idx != -1:
                mods = pygame.key.get_mods()
                shift_held = mods & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT)
                ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
                meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)
                ts = self.tilesets[self.active_idx]
                if ctrl_held or meta_held:
                    old_zoom = self.zoom
                    self.zoom = max(0.25, min(self.zoom * (1.0 + event.y * 0.15), 8.0))
                    # Zoom toward mouse
                    mx, my = pygame.mouse.get_pos()
                    img_x = self.view_rect.x + ts.offset[0]
                    img_y = self.view_rect.y + ts.offset[1]
                    img_rel_x = (mx - img_x) / old_zoom
                    img_rel_y = (my - img_y) / old_zoom
                    ts.offset[0] = int(mx - self.view_rect.x - img_rel_x * self.zoom)
                    ts.offset[1] = int(my - self.view_rect.y - img_rel_y * self.zoom)
                elif shift_held:
                    ts.offset[0] += event.y * 20
                else:
                    ts.offset[1] += event.y * 20
                return True

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_e:
            if self.selected_tile and self.active_idx != -1:
                self._export_selected_as_png_dialog()
                return True

        return False

    def update_selection_rect(self, current_grid: Tuple[int, int]):
        if not self.selection_start_grid:
            return
        start_col, start_row = self.selection_start_grid
        curr_col, curr_row = current_grid

        min_col, max_col = min(start_col, curr_col), max(start_col, curr_col)
        min_row, max_row = min(start_row, curr_row), max(start_row, curr_row)
        tw, th = self.editor.tilemap.tile_size

        self.selected_tile = (
            min_col * tw,
            min_row * th,
            (max_col - min_col + 1) * tw,
            (max_row - min_row + 1) * th,
        )

    def request_add_tileset(self):
        self.editor.open_file_manager(
            on_select=self.on_files_selected,
            initial_dir=getattr(self.editor, "data_root", Path.cwd()),
            allowed_exts=[".png", ".jpg"],
            multi_select=True,
        )

    def on_files_selected(self, paths):
        print(
            f"DEBUG: on_files_selected called with {len(paths) if isinstance(paths, (list, tuple)) else 1} file(s)"
        )
        if isinstance(paths, Path):
            self.on_file_selected(paths)
            return
        if isinstance(paths, (list, tuple, set)):
            for p in paths:
                if isinstance(p, Path):
                    self.on_file_selected(p, enqueue_only=True)
                elif isinstance(p, str):
                    self.on_file_selected(Path(p), enqueue_only=True)
            print(f"DEBUG: Queue size after adding: {len(self._pending_tileset_queue)}")
            if self._pending_tileset_queue:
                self._start_tileset_queue()
        else:
            return

    def on_file_selected(self, path: Path, enqueue_only: bool = False):
        if path.exists():
            try:
                surf = pygame.image.load(path).convert_alpha()
                self._pending_tileset_queue.append((path, surf))
                if not enqueue_only:
                    self._start_tileset_queue()
            except Exception as e:
                error_msg = f"Error loading image {path}: {e}"
                error_handler.capture(
                    Exception(error_msg), context="load_tileset_image"
                )
                import logging

                logging.error(error_msg, exc_info=True)
        else:
            error_msg = f"File does not exist: {path}"
            error_handler.capture(Exception(error_msg), context="load_tileset_missing")
            import logging

            logging.error(error_msg)

    def _start_tileset_queue(self):
        if not self._pending_tileset_queue:
            print("DEBUG: Queue is empty, nothing to process")
            return
        print(
            f"DEBUG: Starting queue processing, {len(self._pending_tileset_queue)} items remaining"
        )
        self._pending_tileset_path, self._pending_tileset_surf = (
            self._pending_tileset_queue.pop(0)
        )
        print(f"DEBUG: Processing tileset: {self._pending_tileset_path}")
        tw, th = self.editor.tilemap.tile_size
        sheet_cols = self._pending_tileset_surf.get_width() // tw
        sheet_rows = self._pending_tileset_surf.get_height() // th
        self.editor.tileset_type_dialog.set_sheet_dimensions(sheet_cols, sheet_rows)
        self.editor.tileset_type_dialog.show(
            on_confirm=self._on_tileset_type_selected,
            on_cancel=self._on_tileset_type_cancel,
        )

    def load_tileset_from_path(
        self,
        path: Path,
        tileset_type: str,
        properties: dict = {},
        tile_properties: dict = {},
        animation: Optional[dict] = None,
    ):
        """Load tileset from path without showing dialog (used when loading maps).

        Args:
            path: Path to the tileset image file
            tileset_type: Type of tileset ("tile" or "object") - already known from saved map
            properties: Custom properties for the tileset
            tile_properties: Custom properties for individual tiles in the tileset (variant_id str -> dict)
            animation: Animation config dict (frame_count, frame_duration_ms, frame_stride, loop, animation_mode)
        """
        if path.exists():
            try:
                surf = pygame.image.load(path).convert_alpha()
                tileset_data = TilesetData(
                    path.name, path, surf, tileset_type=tileset_type
                )
                tileset_data.properties = properties
                tileset_data.tile_properties = {
                    int(k): v for k, v in tile_properties.items()
                }
                tileset_data.animation = animation
                self._load_collision_data_for_tileset(tileset_data)

                self.tilesets.append(tileset_data)
                self.active_idx = len(self.tilesets) - 1
                self.tileset_map[self.active_idx] = tileset_data
                if tileset_type == "object":
                    self.selected_tile = (0, 0, surf.get_width(), surf.get_height())
            except Exception as e:
                error_handler.capture(e, context="load_tileset_surface")

    def _on_tileset_type_selected(self, tileset_type: str):
        """Callback when user selects tileset type from dialog."""
        if not hasattr(self, "_pending_tileset_path"):
            return

        surf = self._pending_tileset_surf

        if tileset_type == "tile" and not is_image_multipleof(
            surf.get_size(), self.editor.tilemap.tile_size
        ):
            w, h = surf.get_size()
            tw, th = self.editor.tilemap.tile_size
            self.editor.confirm_dialog.show(
                title="Tileset Size Warning",
                message=f"Image size ({w}x{h}) is not an exact multiple of tile size ({tw}x{th}). "
                f"Some pixels at the edges will be ignored. Proceed?",
                on_confirm=lambda: self._commit_tileset_load(tileset_type),
                on_cancel=self._on_tileset_type_cancel,
            )
            return

        self._commit_tileset_load(tileset_type)

    def _commit_tileset_load(self, tileset_type: str):
        import math

        path = self._pending_tileset_path
        surf = self._pending_tileset_surf

        tileset_data = TilesetData(path.name, path, surf, tileset_type=tileset_type)
        animation = self.editor.tileset_type_dialog.get_animation_config()
        if animation:
            tw, th = self.editor.tilemap.tile_size
            if tw <= 0 or th <= 0:
                animation = None
            else:
                frame_count = animation.get("frame_count", 0)
                if frame_count <= 0:
                    animation = None
                else:
                    sheet_cols = surf.get_width() // tw
                    sheet_rows = surf.get_height() // th
                    if sheet_cols == 0 or sheet_rows == 0:
                        animation = None
                    elif sheet_cols % frame_count == 0:
                        animation["frame_stride"] = sheet_cols // frame_count
                    elif sheet_rows % frame_count == 0:
                        animation["frame_stride"] = (sheet_rows // frame_count) * sheet_cols
                    else:
                        total = sheet_cols * sheet_rows
                        animation["frame_stride"] = math.ceil(total / frame_count)
        tileset_data.animation = animation
        self._load_collision_data_for_tileset(tileset_data)
        self.tilesets.append(tileset_data)
        self.active_idx = len(self.tilesets) - 1
        self.tileset_map[self.active_idx] = tileset_data

        if tileset_type == "object":
            self.selected_tile = (0, 0, surf.get_width(), surf.get_height())
        else:
            self.selected_tile = None

        delattr(self, "_pending_tileset_path")
        delattr(self, "_pending_tileset_surf")
        if self._pending_tileset_queue:
            pygame.time.set_timer(pygame.USEREVENT + 1, 100, 1)
            self._queue_timer_active = True

    def _load_collision_data_for_tileset(self, tileset_data: TilesetData) -> None:
        """Attach existing collision data for tilesets that have sidecar files."""
        if tileset_data.tileset_type != "object":
            return

        collision_path = self._object_collision_path_for(tileset_data.path)
        tileset_data.object_collision_path = collision_path

        if not collision_path.exists():
            tileset_data.object_collision_data = None
            return

        try:
            from plugins.object_tileset_collision.models import (
                ObjectTilesetCollisionLibrary,
            )

            library = ObjectTilesetCollisionLibrary.load(collision_path)
            tileset_data.object_collision_data = library.to_dict()
            print(f"Loaded object collision data: {collision_path}")
        except Exception as e:
            tileset_data.object_collision_data = None
            error_handler.capture(e, context="load_object_tileset_collision")

    def _object_collision_path_for(self, tileset_path: Path) -> Path:
        data_root = getattr(self.editor, "data_root", None)
        if data_root is None:
            return tileset_path.with_suffix(".object_collision.json")

        config = getattr(self.editor, "config", {}) or {}
        collision_dir_name = config.get("collision_paths", {}).get(
            "object_tileset",
            "collision",
        )
        return (
            Path(data_root)
            / collision_dir_name
            / f"{tileset_path.stem}.object_collision.json"
        )

    def load_object_tileset_companions(self) -> None:
        """Auto-add object tileset tabs for tile images with object collision data."""
        previous_active_idx = self.active_idx
        previous_selected_tile = self.selected_tile

        existing = {
            (ts.path.resolve(), ts.tileset_type)
            for ts in self.tilesets
            if ts.path.exists()
        }

        for ts in list(self.tilesets):
            if ts.tileset_type != "tile":
                continue

            try:
                resolved_path = ts.path.resolve()
            except OSError:
                continue

            if (resolved_path, "object") in existing:
                continue

            collision_path = self._object_collision_path_for(ts.path)
            if not collision_path.exists():
                continue

            print(
                "Auto-loading object tileset companion from collision sidecar: "
                f"{collision_path}"
            )
            self.load_tileset_from_path(ts.path, "object")
            existing.add((resolved_path, "object"))

        if 0 <= previous_active_idx < len(self.tilesets):
            self.active_idx = previous_active_idx
            self.selected_tile = previous_selected_tile

    def remove_tileset(self):
        if 0 <= self.active_idx < len(self.tilesets):
            self.tilesets.pop(self.active_idx)

            self.tileset_map.clear()
            for i, ts in enumerate(self.tilesets):
                self.tileset_map[i] = ts
            self.active_idx = max(0, len(self.tilesets) - 1)
            if not self.tilesets:
                self.active_idx = -1
            self.selected_tile = None
            self.rule_hints.clear()

    def open_collision_editor(self):
        """Open collision editor for the active tileset"""
        if self.active_idx == -1 or self.active_idx >= len(self.tilesets):
            self.editor.notifications.notify("No tileset selected")
            return

        ts = self.tilesets[self.active_idx]

        # Launch collision editor as subprocess (routes based on tileset type)
        self.editor.launch_collision_editor(ts.tileset_type)

    def check_tab_click(self, pos):
        idx = self._get_tab_at_pos(pos)
        if idx is not None:
            self.active_idx = int(idx)
            ts = self.tilesets[self.active_idx]
            if ts.tileset_type == "object":
                self.selected_tile = (
                    0,
                    0,
                    ts.surface.get_width(),
                    ts.surface.get_height(),
                )
            else:
                self.selected_tile = None
            self.rule_hints.clear()

    def _get_tab_at_pos(self, pos) -> Optional[int]:
        if not self.tilesets:
            return None
        tab_w = 100
        idx = (pos[0] - self.rect.x + self.tab_scroll_x) // tab_w
        if 0 <= idx < len(self.tilesets):
            return int(idx)
        return None

    def _save_tileset_properties(self, ts: TilesetData, props: dict):
        ts.properties = props
        print(f"Saved properties for tileset: {ts.name}")

    def _save_tile_properties(self, ts: TilesetData, variant_id: int, props: dict):
        ts.tile_properties[variant_id] = props
        print(f"Saved properties for tile {variant_id} in tileset: {ts.name}")

    def _save_tile_properties_multi(
        self, ts: TilesetData, variant_ids: List[int], props: dict
    ):
        for vid in variant_ids:
            ts.tile_properties[vid] = props.copy()
        if len(variant_ids) == 1:
            print(f"Saved properties for tile {variant_ids[0]} in tileset: {ts.name}")
        else:
            print(
                f"Saved properties for {len(variant_ids)} tiles in tileset: {ts.name}"
            )

    def _get_selected_variant_ids(self, ts: TilesetData) -> List[int]:
        if not self.selected_tile:
            return []
        sx, sy, sw, sh = self.selected_tile
        tw, th = self.editor.tilemap.tile_size
        cols = ts.surface.get_width() // tw
        start_col = sx // tw
        start_row = sy // th
        sel_w_tiles = max(1, sw // tw)
        sel_h_tiles = max(1, sh // th)
        variant_ids: List[int] = []
        for row in range(start_row, start_row + sel_h_tiles):
            for col in range(start_col, start_col + sel_w_tiles):
                variant_ids.append((row * cols) + col)
        return variant_ids

    def get_active_tile(self):
        if self.active_idx == -1:
            return None
        return self.tilesets[self.active_idx]

    def select_tile_by_variant(self, tileset_index: int, variant_id: int) -> bool:
        """Select a specific tile in the tileset panel by tileset index and variant ID.

        Switches to the specified tileset tab and selects the tile region
        corresponding to the variant ID.

        Returns True if the selection was successful.
        """
        if tileset_index < 0 or tileset_index >= len(self.tilesets):
            return False

        ts = self.tilesets[tileset_index]
        if ts.tileset_type == "object":
            # For object tilesets, select the whole image
            self.active_idx = tileset_index
            self.selected_tile = (0, 0, ts.surface.get_width(), ts.surface.get_height())
            return True

        tw, th = self.editor.tilemap.tile_size
        if tw <= 0 or th <= 0:
            return False

        sheet_w = ts.surface.get_width()
        cols = sheet_w // tw
        if cols <= 0:
            return False

        col = variant_id % cols
        row = variant_id // cols

        # Verify the variant is within the tileset bounds
        if col * tw >= sheet_w or row * th >= ts.surface.get_height():
            return False

        self.active_idx = tileset_index
        self.selected_tile = (col * tw, row * th, tw, th)
        return True

    def _export_selected_as_png_dialog(self):
        if not self.selected_tile or self.active_idx == -1:
            return
        ts = self.tilesets[self.active_idx]
        default = Path(ts.name).stem + "_extracted.png"
        self.editor.open_file_manager(
            on_save=self._on_export_selected_path,
            allowed_exts=[".png"],
            mode="save",
            default_name=default,
        )

    def _on_export_selected_path(self, path: Path):
        try:
            sx, sy, sw, sh = self.selected_tile
            ts = self.tilesets[self.active_idx]
            extracted = ts.surface.subsurface(Rect(sx, sy, sw, sh)).copy()
            pygame.image.save(extracted, str(path))
        except Exception as e:
            error_handler.capture(e, context="export_selected_png")

    def draw(self, screen: pygame.Surface):
        self.draw_background(screen)
        self.draw_view_area(screen)
        self.draw_buttons(screen)
        self.draw_tabs(screen)

    def draw_background(self, screen: pygame.Surface):
        pygame.draw.rect(screen, COLORS.panel, self.rect)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)

    def draw_view_area(self, screen: pygame.Surface):
        pygame.draw.rect(screen, COLORS.panel_alt, self.view_rect)
        if self.active_idx == -1 or self.active_idx >= len(self.tilesets):
            return

        ts = self.tilesets[self.active_idx]
        clip = screen.get_clip()
        screen.set_clip(self.view_rect)

        img_x = self.view_rect.x + ts.offset[0]
        img_y = self.view_rect.y + ts.offset[1]

        self.draw_tileset_image(screen, ts, img_x, img_y, self.zoom)

        self._draw_object_collision_regions(screen, ts, img_x, img_y)

        self._draw_rule_hints(screen, ts, img_x, img_y)

        self.draw_hover(screen, ts, img_x, img_y)
        self.draw_selection(screen, img_x, img_y)

        screen.set_clip(clip)
        self.draw_tileset_name(screen, ts)

    def _draw_rule_hints(self, screen, ts, img_x, img_y):
        if not self.rule_hints:
            return

        tw, th = self.editor.tilemap.tile_size
        sheet_w = ts.surface.get_width()
        cols = sheet_w // tw

        ztw = int(tw * self.zoom)
        zth = int(th * self.zoom)

        for vid in self.rule_hints:
            col = vid % cols
            row = vid // cols

            x = img_x + col * ztw
            y = img_y + row * zth

            if (
                x > self.view_rect.right
                or x + ztw < self.view_rect.x
                or y > self.view_rect.bottom
                or y + zth < self.view_rect.y
            ):
                continue

            points = [(x, y), (x + 10, y), (x, y + 10)]
            pygame.draw.polygon(screen, (0, 255, 255), points)

            pygame.draw.rect(screen, (0, 255, 255), Rect(x, y, ztw, zth), 1)

    def draw_tileset_image(self, screen, ts: TilesetData, img_x: int, img_y: int, zoom: float = 1.0):
        if zoom != 1.0:
            w = int(ts.surface.get_width() * zoom)
            h = int(ts.surface.get_height() * zoom)
            scaled = pygame.transform.smoothscale(ts.surface, (w, h))
            screen.blit(scaled, (img_x, img_y))
        else:
            screen.blit(ts.surface, (img_x, img_y))

    def _draw_object_collision_regions(
        self,
        screen: pygame.Surface,
        ts: TilesetData,
        img_x: int,
        img_y: int,
    ) -> None:
        if ts.tileset_type != "object" or not ts.object_collision_data:
            return

        regions = ts.object_collision_data.get("regions", {})
        if not isinstance(regions, dict):
            return

        for region_data in regions.values():
            if not isinstance(region_data, dict):
                continue
            rect_data = region_data.get("region_rect")
            if not isinstance(rect_data, (list, tuple)) or len(rect_data) != 4:
                continue

            rx, ry, rw, rh = (int(v) for v in rect_data)
            region_rect = Rect(
                int(img_x + rx * self.zoom),
                int(img_y + ry * self.zoom),
                int(rw * self.zoom),
                int(rh * self.zoom),
            )
            if not self.view_rect.colliderect(region_rect):
                continue

            shapes = region_data.get("shapes", [])
            color = COLORS.success if shapes else COLORS.warning
            pygame.draw.rect(screen, color, region_rect, 2)

            name = str(region_data.get("name") or region_data.get("region_id") or "")
            if name:
                max_label_w = max(0, region_rect.width - 10)
                display_name = name
                while display_name and self.font.size(display_name)[0] > max_label_w:
                    display_name = display_name[:-1].rstrip()
                if display_name != name and max_label_w > self.font.size("...")[0]:
                    while (
                        display_name
                        and self.font.size(display_name + "...")[0] > max_label_w
                    ):
                        display_name = display_name[:-1].rstrip()
                    display_name += "..."
                label = self.font.render(display_name, True, COLORS.text)
                label_bg = Rect(
                    region_rect.x + 2,
                    region_rect.y + 2,
                    label.get_width() + 6,
                    label.get_height() + 4,
                )
                if label_bg.width > 0:
                    pygame.draw.rect(screen, COLORS.panel, label_bg)
                    screen.blit(label, (label_bg.x + 3, label_bg.y + 2))

    def draw_hover(self, screen, ts: TilesetData, img_x: int, img_y: int):
        if self.hover_pos is None:
            return
        tw, th = self.editor.tilemap.tile_size
        col, row = self.hover_pos
        ztw = int(tw * self.zoom)
        zth = int(th * self.zoom)
        hover_rect = Rect(img_x + col * ztw, img_y + row * zth, ztw, zth)
        pygame.draw.rect(screen, COLORS.warning, hover_rect, 2)

    def draw_selection(self, screen, img_x: int, img_y: int):
        if not self.selected_tile:
            return
        sx, sy, sw, sh = self.selected_tile
        sel_rect = Rect(
            int(img_x + sx * self.zoom),
            int(img_y + sy * self.zoom),
            int(sw * self.zoom),
            int(sh * self.zoom),
        )
        pygame.draw.rect(screen, COLORS.success, sel_rect, 2)

    def draw_tileset_name(self, screen, ts: TilesetData):
        name_surf = self.font.render(f"{ts.name}", True, COLORS.text)
        screen.blit(name_surf, (self.rect.x + 5, self.rect.bottom - 30))

    def draw_buttons(self, screen):
        # Export selection as PNG button
        pygame.draw.rect(
            screen, COLORS.header, self.btn_export, border_radius=SHAPE.radius_sm
        )
        screen.blit(
            self.font.render("E", True, COLORS.text),
            (self.btn_export.x + 9, self.btn_export.y + 5),
        )

        # Collision editor button
        pygame.draw.rect(
            screen, COLORS.header, self.btn_collision, border_radius=SHAPE.radius_sm
        )
        screen.blit(
            self.font.render("C", True, COLORS.text),
            (self.btn_collision.x + 9, self.btn_collision.y + 5),
        )
        
        pygame.draw.rect(
            screen, COLORS.header, self.btn_add, border_radius=SHAPE.radius_sm
        )
        pygame.draw.rect(
            screen, COLORS.header, self.btn_rem, border_radius=SHAPE.radius_sm
        )
        screen.blit(
            self.font.render("+", True, COLORS.text),
            (self.btn_add.x + 10, self.btn_add.y + 5),
        )
        screen.blit(
            self.font.render("-", True, COLORS.text),
            (self.btn_rem.x + 10, self.btn_rem.y + 5),
        )
        mx, my = pygame.mouse.get_pos()
        if self.btn_export.collidepoint(mx, my):
            self.editor.tooltip.show("E: Export selection as PNG", (mx + 10, my + 10))
        elif self.btn_collision.collidepoint(mx, my):
            self.editor.tooltip.show("Edit Collision Shapes", (mx + 10, my + 10))
        elif self.btn_add.collidepoint(mx, my):
            self.editor.tooltip.show("Add Tileset", (mx + 10, my + 10))
        elif self.btn_rem.collidepoint(mx, my):
            self.editor.tooltip.show("Remove Tileset", (mx + 10, my + 10))

    def draw_tabs(self, screen: Surface):
        if not self.tilesets:
            return
        clip = screen.get_clip()
        tab_area = Rect(self.rect.x, self.rect.y, self.rect.width, self.top_bar_h)
        screen.set_clip(tab_area)

        pygame.draw.rect(screen, COLORS.header, tab_area)

        tab_w = 100
        total_w = tab_w * len(self.tilesets)
        has_overflow = total_w > self.rect.width
        if has_overflow:
            self.tab_scroll_x = max(
                0, min(self.tab_scroll_x, total_w - self.rect.width)
            )
        else:
            self.tab_scroll_x = 0

        for i, ts in enumerate(self.tilesets):
            r = Rect(
                self.rect.x + i * tab_w - self.tab_scroll_x,
                self.rect.y,
                tab_w,
                self.top_bar_h,
            )
            if r.right < self.rect.x or r.x > self.rect.right:
                continue
            is_active = i == self.active_idx
            col = COLORS.selected if is_active else COLORS.header
            pygame.draw.rect(screen, col, r)
            if not is_active:
                pygame.draw.line(screen, COLORS.border, r.bottomleft, r.bottomright, 1)
            t = ts.name[:8] + ".." if len(ts.name) > 10 else ts.name
            screen.blit(self.font.render(t, True, COLORS.text), (r.x + 5, r.y + 5))

        mx, my = pygame.mouse.get_pos()
        show_arrows = has_overflow and tab_area.collidepoint(mx, my)

        if show_arrows:
            for arrow_rect, label in [
                (self._tab_arrow_left, "<"),
                (self._tab_arrow_right, ">"),
            ]:
                pygame.draw.rect(screen, COLORS.selected, arrow_rect)
                pygame.draw.rect(screen, COLORS.border, arrow_rect, 1)
                arrow_surf = self.font.render(label, True, COLORS.text)
                arrow_rect_text = arrow_surf.get_rect(center=arrow_rect.center)
                screen.blit(arrow_surf, arrow_rect_text)

            bar_w = max(30, int(self.rect.width * (self.rect.width / total_w)))
            bar_x = self.rect.x + int(
                (self.tab_scroll_x / (total_w - self.rect.width))
                * (self.rect.width - bar_w)
            )
            bar_rect = Rect(bar_x, self.rect.y + self.top_bar_h - 4, bar_w, 3)
            pygame.draw.rect(screen, COLORS.border_soft, bar_rect, border_radius=2)

        # Tooltip for tab name
        if tab_area.collidepoint(mx, my) and not (
            show_arrows and (
                self._tab_arrow_left.collidepoint(mx, my) or
                self._tab_arrow_right.collidepoint(mx, my)
            )
        ):
            idx = self._get_tab_at_pos((mx, my))
            if idx is not None and 0 <= idx < len(self.tilesets):
                self.editor.tooltip.show(
                    self.tilesets[idx].name, (mx + 10, my + 10)
                )

        screen.set_clip(clip)

    def _scroll_tabs(self, delta: float):
        if not self.tilesets:
            return
        tab_w = 100
        total_w = tab_w * len(self.tilesets)
        if total_w <= self.rect.width:
            self.tab_scroll_x = 0
            return
        self.tab_scroll_x = max(
            0, min(self.tab_scroll_x - delta, total_w - self.rect.width)
        )
