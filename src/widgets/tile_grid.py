import pygame
from typing import TYPE_CHECKING, Optional, Tuple
from pygame import Rect, Surface, K_UP, K_LEFT, K_RIGHT

from ttypes.tilemap import TypeTile, TypeObject
from widgets.ui.theme import COLORS

if TYPE_CHECKING:
    from editor import Editor


class TileGrid:
    def __init__(self, editor: "Editor", rect: Rect):
        self.editor = editor
        self.rect = rect

        self.scroll_x = 0
        self.scroll_y = 0
        self.scroll_speed = 8

        self.is_panning = False
        self.pan_start_pos = (0, 0)
        self.pan_start_scroll = (0, 0)
        self.hover_cell: Optional[Tuple[int, int]] = None

        self.grid_color = (200, 200, 200)
        self.show_grid = True

        self.eraser_size = 1  # For tiles: in grid units. For objects: in pixels.
        self.zoom_level = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0

        self.font_status = pygame.font.SysFont("Arial", 12)
        self.font_overlay = pygame.font.SysFont("Arial", 24, bold=True)
        self._last_history_capture = 0

        # Continuous adjustment and visual feedback
        self.last_eraser_adj_time = 0
        self.eraser_overlay_timer = 0
        self.adj_delay = 100  # ms between adjustments

        # Selection state
        self.selection_rect = None  # (x1, y1, x2, y2) grid coords, inclusive
        self.selection_start = None  # grid coord where selection drag started
        self.is_selecting = False  # currently dragging to create selection

        # Move state (click inside selection → drag to move)
        self.is_moving = False  # clicked inside selection, ready to drag-move
        self.move_delta = (0, 0)  # current move offset: (grid_dx, grid_dy) for tiles, (px_dx, px_dy) for objects
        self.move_start_mouse = None  # screen pos where move drag started
        self.move_origin_rect = None  # original selection rect before move started
        self._selection_pixel_offset = (0, 0)  # pixel-level offset for object selection display during move

        # Clipboard
        self.clipboard = None  # copied tile/object data

    @property
    def tile_size(self):
        return self.editor.tilemap.tile_size

    @property
    def effective_tile_size(self):
        tw, th = self.editor.tilemap.tile_size
        rs = self.editor.tilemap.render_scale
        return (tw * rs, th * rs)

    def screen_to_world(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        wx = (pos[0] - self.rect.x) / self.zoom_level + self.scroll_x
        wy = (pos[1] - self.rect.y) / self.zoom_level + self.scroll_y
        return int(wx), int(wy)

    def get_grid_pos(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        wx, wy = self.screen_to_world(pos)
        eff_w, eff_h = self.effective_tile_size
        return int(wx // eff_w), int(wy // eff_h)

    def update(self):
        event_blocked = not self.editor.save_input.active
        if self.rect.collidepoint(pygame.mouse.get_pos()) and event_blocked:
            keys = pygame.key.get_pressed()

            if keys[K_LEFT]:
                self.scroll_x -= self.scroll_speed
            if keys[K_RIGHT]:
                self.scroll_x += self.scroll_speed
            if keys[K_UP]:
                self.scroll_y -= self.scroll_speed
            if keys[pygame.K_DOWN]:
                self.scroll_y += self.scroll_speed

            # Continuous Eraser Size Adjustment
            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
            meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)

            if ctrl_held or meta_held:
                current_time = pygame.time.get_ticks()
                if current_time - self.last_eraser_adj_time > self.adj_delay:
                    adj = 0
                    active_layer = self.editor.tilemap.layer_manager.get_active_layer()
                    step = (
                        5 if active_layer and active_layer.layer_type == "object" else 1
                    )

                    if (
                        keys[pygame.K_EQUALS]
                        or keys[pygame.K_PLUS]
                        or keys[pygame.K_KP_PLUS]
                    ):
                        adj = step
                    elif keys[pygame.K_MINUS] or keys[pygame.K_KP_MINUS]:
                        adj = -step

                    if adj != 0:
                        self.eraser_size = max(1, min(100, self.eraser_size + adj))
                        self.last_eraser_adj_time = current_time
                        self.eraser_overlay_timer = 1500  # Show for 1.5 seconds

        self.clamp_view()

    def zoom_by(self, delta: float, center: Optional[Tuple[int, int]] = None):
        old_zoom = self.zoom_level
        self.zoom_level = max(
            self.min_zoom, min(self.max_zoom, self.zoom_level + delta)
        )
        if self.zoom_level == old_zoom:
            return
        if center is None:
            center = pygame.mouse.get_pos()
        wx, wy = self.screen_to_world(center)
        self.scroll_x = wx - (center[0] - self.rect.x) / self.zoom_level
        self.scroll_y = wy - (center[1] - self.rect.y) / self.zoom_level

    def reset_view(self):
        self.zoom_level = 1.0
        self.scroll_x = 0
        self.scroll_y = 0

    def fit_to_map(self):
        eff_w, eff_h = self.effective_tile_size
        world_w = self.editor.tilemap.map_size[0] * eff_w
        world_h = self.editor.tilemap.map_size[1] * eff_h
        if world_w <= 0 or world_h <= 0:
            return
        zoom_x = self.rect.width / world_w
        zoom_y = self.rect.height / world_h
        self.zoom_level = max(self.min_zoom, min(self.max_zoom, min(zoom_x, zoom_y)))
        self.scroll_x = 0
        self.scroll_y = 0

    def clamp_view(self):
        self.zoom_level = max(self.min_zoom, min(self.max_zoom, self.zoom_level))
        eff_w, eff_h = self.effective_tile_size
        world_w = self.editor.tilemap.map_size[0] * eff_w
        world_h = self.editor.tilemap.map_size[1] * eff_h
        view_w = self.rect.width / self.zoom_level
        view_h = self.rect.height / self.zoom_level

        max_scroll_x = max(0, world_w - view_w)
        max_scroll_y = max(0, world_h - view_h)
        self.scroll_x = max(0, min(self.scroll_x, max_scroll_x))
        self.scroll_y = max(0, min(self.scroll_y, max_scroll_y))

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse_pos = pygame.mouse.get_pos()
        is_hovering = self.rect.collidepoint(mouse_pos)
        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()

            ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
            meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)

            if event.key == pygame.K_a and (ctrl_held or meta_held):
                active_layer = self.editor.tilemap.layer_manager.get_active_layer()
                if active_layer and hasattr(self.editor, "autotiler"):
                    rules = getattr(self.editor.autotiler, "rules", [])
                    count = active_layer.autotile_layer(rules)
                    self.editor.tilemap.update_map_size()
                    if count:
                        self.editor.notifications.success(
                            f"Autotile complete: {count} tiles updated"
                        )
                    else:
                        self.editor.notifications.notify(
                            "No tiles updated (Already matched or no groups found)"
                        )
                return True

            if event.key == pygame.K_f:
                if is_hovering and self.hover_cell:
                    res = self.get_selected_brush()
                    if res:
                        self.editor.tilemap.capture_history("Flood Fill")
                        tileset_index, tileset_data, src_rect = res
                        active_layer = (
                            self.editor.tilemap.layer_manager.get_active_layer()
                        )
                        assert tileset_data is not None
                        assert src_rect is not None

                        if active_layer and active_layer.layer_type == "tile":
                            tile_w, tile_h = self.tile_size
                            sheet_cols = tileset_data.surface.get_width() // tile_w
                            variant_id = (src_rect[1] // tile_h * sheet_cols) + (
                                src_rect[0] // tile_w
                            )

                            assert tileset_index is not None
                            new_data: TypeTile = {
                                "ttype": tileset_index,
                                "variant": variant_id,
                                "pos": (0, 0),
                            }
                            active_layer.flood_fill(
                                self.hover_cell, new_data, self.editor.tilemap.map_size
                            )
                            self.editor.tilemap.update_map_size()
                return True

            if event.key == pygame.K_g:
                self.show_grid = not self.show_grid
                return True

            if event.key == pygame.K_q:
                if is_hovering and self.hover_cell:
                    active_layer = self.editor.tilemap.layer_manager.get_active_layer()
                    if active_layer and self.hover_cell in active_layer.tiles:
                        tile = active_layer.tiles[self.hover_cell]
                        gid = self._get_group_for_tile(tile)
                        if gid:
                            self.editor.notifications.notify(
                                f"Group: {gid}", color=(100, 200, 255)
                            )
                        else:
                            self.editor.notifications.notify(
                                "Group: None (No rule matches)", color=(200, 200, 200)
                            )
                    else:
                        self.editor.notifications.notify("No tile at cursor")
                return True

            # Ctrl+C: Copy selection
            if event.key == pygame.K_c and (ctrl_held or meta_held):
                if self.selection_rect:
                    self.copy_selection()
                return True

            # Ctrl+X: Cut selection
            if event.key == pygame.K_x and (ctrl_held or meta_held):
                if self.selection_rect:
                    self.copy_selection()
                    self.editor.tilemap.capture_history("Cut Selection")
                    self.delete_selection()
                return True

            # Ctrl+V: Paste
            if event.key == pygame.K_v and (ctrl_held or meta_held):
                if self.clipboard and is_hovering and self.hover_cell:
                    self.editor.tilemap.capture_history("Paste")
                    self.paste_clipboard(self.hover_cell)
                return True

            # Delete / Backspace: Delete selection
            if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                if self.selection_rect:
                    self.editor.tilemap.capture_history("Delete Selection")
                    self.delete_selection()
                return True

            # Enter: Commit move or deselect
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                if self.is_moving:
                    self.commit_move()
                elif self.selection_rect:
                    self.selection_rect = None
                return True

            # Escape: Cancel move or deselect
            if event.key == pygame.K_ESCAPE:
                if self.is_moving:
                    self.cancel_move()
                elif self.selection_rect:
                    self.selection_rect = None
                return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Middle-click or left-click in pan_mode → start pan
            if event.button == 2 or (event.button == 1 and self.editor.pan_mode):
                if is_hovering:
                    self.is_panning = True
                    self.pan_start_pos = mouse_pos
                    self.pan_start_scroll = (self.scroll_x, self.scroll_y)
                    return True

            # Left-click
            if event.button == 1:
                if self.editor.select_mode:
                    if is_hovering and self.hover_cell:
                        # Click inside existing selection → start move
                        if (
                            self.selection_rect
                            and self._point_in_selection(self.hover_cell)
                        ):
                            self._begin_move(mouse_pos)
                        else:
                            # Start new selection drag
                            self.selection_start = self.hover_cell
                            self.is_selecting = True
                            self.selection_rect = (
                                self.hover_cell[0],
                                self.hover_cell[1],
                                self.hover_cell[0],
                                self.hover_cell[1],
                            )
                    else:
                        # Click outside selection → deselect
                        self.selection_rect = None
                    return True

                if self.editor.eraser_mode:
                    if is_hovering:
                        self.editor.tilemap.capture_history("Erase Tile")
                        self.remove_tile()
                    return True

                # Default: place tile
                if is_hovering and not self.is_panning:
                    self.editor.tilemap.capture_history("Place Tile")
                    self.place_tile()
                    return True

            # Right-click → pick tile (eye-drop)
            if event.button == 3:
                if is_hovering and self.hover_cell:
                    self.pick_tile_at(self.hover_cell)
                return True

        elif event.type == pygame.MOUSEBUTTONUP:
            # Middle-click or left-click in pan_mode → stop pan
            if event.button == 2 or (event.button == 1 and self.editor.pan_mode):
                self.is_panning = False
                return True

            # Left-click release
            if event.button == 1:
                if self.is_selecting:
                    self.is_selecting = False
                    self._finalize_selection()
                    return True
                if self.is_moving:
                    self.commit_move()
                    return True

        elif event.type == pygame.MOUSEMOTION:
            if self.is_panning:
                dx = (mouse_pos[0] - self.pan_start_pos[0]) / self.zoom_level
                dy = (mouse_pos[1] - self.pan_start_pos[1]) / self.zoom_level

                self.scroll_x = self.pan_start_scroll[0] - dx
                self.scroll_y = self.pan_start_scroll[1] - dy
                return True

            if is_hovering:
                self.hover_cell = self.get_grid_pos(mouse_pos)
            else:
                self.hover_cell = None

            # Update selection drag
            if self.is_selecting and self.selection_start and self.hover_cell:
                x1 = min(self.selection_start[0], self.hover_cell[0])
                y1 = min(self.selection_start[1], self.hover_cell[1])
                x2 = max(self.selection_start[0], self.hover_cell[0])
                y2 = max(self.selection_start[1], self.hover_cell[1])
                self.selection_rect = (x1, y1, x2, y2)

            # Update move delta
            if self.is_moving and self.move_start_mouse:
                self._update_move_delta(mouse_pos)

        elif event.type == pygame.MOUSEWHEEL:
            if is_hovering:
                mods = pygame.key.get_mods()
                ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
                meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)
                shift_held = mods & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT)
                if ctrl_held or meta_held:
                    self.zoom_by(event.y * 0.1, pygame.mouse.get_pos())
                elif shift_held:
                    self.scroll_x -= event.y * self.scroll_speed
                else:
                    self.scroll_y -= event.y * self.scroll_speed
                return True

        # Continuous painting/erasing (left-click held, not in select or pan mode)
        buttons = pygame.mouse.get_pressed()
        if (
            not self.editor.pan_mode
            and not self.editor.select_mode
            and not self.is_panning
        ):
            if buttons[0] and is_hovering:
                if self.editor.eraser_mode:
                    self.remove_tile()
                else:
                    self.place_tile()
                return True

        return False

    def get_selected_brush(self):
        ts_widget = self.editor.tileset_widget
        if not ts_widget or ts_widget.active_idx == -1 or not ts_widget.selected_tile:
            return None, None, None

        tileset_index = ts_widget.active_idx

        if tileset_index < 0 or tileset_index >= len(ts_widget.tilesets):
            return None, None, None

        tileset_data = ts_widget.tilesets[tileset_index]
        tile_rect = ts_widget.selected_tile
        return tileset_index, tileset_data, tile_rect

    def place_tile(self):
        res = self.get_selected_brush()
        if not res:
            return

        tileset_index, tileset_data, src_rect = res
        if tileset_index is None or not tileset_data or not src_rect:
            return

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            return

        sheet_width = tileset_data.surface.get_width()
        tile_w, tile_h = self.tile_size
        sheet_cols = sheet_width // tile_w

        if active_layer.layer_type == "object":
            self._place_object_free(
                active_layer,
                tileset_index,
                tileset_data,
                src_rect,
                tile_w,
                tile_h,
                sheet_cols,
                tileset_data.tileset_type,
            )
            # Incremental update for objects
            mouse_pos = pygame.mouse.get_pos()
            world_pos = self.screen_to_world(mouse_pos)
            self.editor.tilemap.incremental_update_map_size(
                world_pos, is_pixel=True, size=(src_rect[2], src_rect[3])
            )
        else:
            if not self.hover_cell:
                return

            self._place_tile_grid(
                active_layer,
                tileset_index,
                tileset_data,
                src_rect,
                tile_w,
                tile_h,
                sheet_cols,
            )
            # Incremental update for tile selection size
            sel_w_tiles = src_rect[2] // tile_w
            sel_h_tiles = src_rect[3] // tile_h
            last_tile_pos = (
                self.hover_cell[0] + sel_w_tiles - 1,
                self.hover_cell[1] + sel_h_tiles - 1,
            )
            self.editor.tilemap.incremental_update_map_size(last_tile_pos)

    def _place_tile_grid(
        self,
        active_layer,
        tileset_index: int,
        tileset_data,
        src_rect: Tuple[int, int, int, int],
        tile_w: int,
        tile_h: int,
        sheet_cols: int,
    ):
        """Place tiles in grid-aligned fashion (tile layer or tile on object layer)."""
        if self.hover_cell is None:
            return

        sel_w_tiles = src_rect[2] // tile_w
        sel_h_tiles = src_rect[3] // tile_h

        start_sx = src_rect[0] // tile_w
        start_sy = src_rect[1] // tile_h

        if active_layer.layer_type == "object":
            mouse_pos = pygame.mouse.get_pos()
            world_x, world_y = self.screen_to_world(mouse_pos)
            pixel_x = world_x
            pixel_y = world_y
            pixel_w = sel_w_tiles * tile_w
            pixel_h = sel_h_tiles * tile_h

            variant_id = (start_sy * sheet_cols) + start_sx

            obj_data: TypeObject = {
                "area": {
                    "x": pixel_x,
                    "y": pixel_y,
                    "w": pixel_w,
                    "h": pixel_h,
                },
                "ttype": int(tileset_index),
                "tileset_type": "tile",
                "variant": variant_id,
            }

            active_layer.add_object((pixel_x, pixel_y), obj_data)
        else:
            for y_off in range(sel_h_tiles):
                for x_off in range(sel_w_tiles):
                    curr_sx = start_sx + x_off
                    curr_sy = start_sy + y_off
                    variant_id = (curr_sy * sheet_cols) + curr_sx

                    map_x = self.hover_cell[0] + x_off
                    map_y = self.hover_cell[1] + y_off
                    target_pos = (map_x, map_y)

                    tile_data: TypeTile = {
                        "pos": target_pos,
                        "ttype": (tileset_index),
                        "variant": variant_id,
                    }

                    # Copy properties from tileset variant if they exist
                    if variant_id in tileset_data.tile_properties:
                        tile_data["properties"] = tileset_data.tile_properties[
                            variant_id
                        ].copy()

                    active_layer.set_tile(target_pos, tile_data)

                    # Localized autotile if mode is enabled
                    if self.editor.autotile_mode and getattr(
                        self.editor, "autotiler", None
                    ):
                        rules = self.editor.autotiler.rules
                        if rules:
                            active_layer.autotile_at_pos(target_pos, rules)

    def _place_object_free(
        self,
        active_layer,
        tileset_index: int,
        tileset_data,
        src_rect: Tuple[int, int, int, int],
        tile_w: int,
        tile_h: int,
        sheet_cols: int,
        tileset_type: str = "object",
    ):
        """Place objects at exact pixel position (free placement).

        For object layers, place the ENTIRE selection as a single entity
        at the exact mouse position, NOT sliced into individual tiles.
        Works with both object and tile tilesets.
        """
        mouse_pos = pygame.mouse.get_pos()
        world_pos = self.screen_to_world(mouse_pos)

        if tileset_type == "object":
            sel_width = tileset_data.surface.get_width()
            sel_height = tileset_data.surface.get_height()
            variant_id = 0
        else:
            sel_width = src_rect[2]
            sel_height = src_rect[3]
            start_sx = src_rect[0]
            start_sy = src_rect[1]
            variant_id = ((start_sy // tile_h) * sheet_cols) + (start_sx // tile_w)

        obj_data: TypeObject = {
            "area": {
                "x": world_pos[0],
                "y": world_pos[1],
                "w": sel_width,
                "h": sel_height,
            },
            "ttype": int(tileset_index),
            "tileset_type": tileset_type,
            "variant": variant_id,
        }

        active_layer.add_object((world_pos[0], world_pos[1]), obj_data)

    def remove_tile(self):
        """Remove tile or object at hover position."""
        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            return

        if active_layer.layer_type == "object":
            mouse_pos = pygame.mouse.get_pos()
            world_pos = self.screen_to_world(mouse_pos)

            # Object layer removal: search in a localized area around mouse
            half_size = self.eraser_size // 2
            erase_rect = Rect(
                world_pos[0] - half_size,
                world_pos[1] - half_size,
                self.eraser_size,
                self.eraser_size,
            )

            for obj_id, obj in list(active_layer.get_all_objects().items()):
                area = obj["area"]
                obj_rect = Rect(area["x"], area["y"], area["w"], area["h"])

                if erase_rect.colliderect(obj_rect):
                    active_layer.remove_object(obj_id)
                    if (
                        self.editor.tilemap.map_size[0]
                        > self.editor.tilemap.initial_map_size[0]
                        or self.editor.tilemap.map_size[1]
                        > self.editor.tilemap.initial_map_size[1]
                    ):
                        self.editor.tilemap.update_map_size()
        else:
            if not self.hover_cell:
                return
            # Tile layer removal: loop over NxN area based on eraser_size
            must_rescan = False
            for dy in range(self.eraser_size):
                for dx in range(self.eraser_size):
                    pos = (self.hover_cell[0] + dx, self.hover_cell[1] + dy)
                    if active_layer.remove_tile(pos):
                        if (
                            pos[0] >= self.editor.tilemap.map_size[0] - 1
                            or pos[1] >= self.editor.tilemap.map_size[1] - 1
                        ):
                            must_rescan = True

                    if self.editor.autotile_mode and getattr(
                        self.editor, "autotiler", None
                    ):
                        rules = self.editor.autotiler.rules
                        if rules:
                            active_layer.autotile_at_pos(pos, rules)

            if must_rescan:
                self.editor.tilemap.update_map_size()

    def pick_tile_at(self, grid_pos: Tuple[int, int]):
        """Pick/eye-drop a tile from the map at the given grid position.

        Switches to the tile's tileset tab and selects the tile in the
        tileset panel.
        """
        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            return

        ts_widget = self.editor.tileset_widget
        if not ts_widget:
            return

        if active_layer.layer_type == "tile":
            tile = active_layer.get_tile(grid_pos)
            if not tile:
                return
            ttype = int(tile["ttype"])
            variant = tile["variant"]
            ts_widget.select_tile_by_variant(ttype, variant)
        elif active_layer.layer_type == "object":
            # Find object under cursor
            mouse_pos = pygame.mouse.get_pos()
            world_pos = self.screen_to_world(mouse_pos)
            for obj_id, obj in active_layer.get_all_objects().items():
                area = obj["area"]
                obj_rect = Rect(area["x"], area["y"], area["w"], area["h"])
                if obj_rect.collidepoint(world_pos):
                    ttype = int(obj["ttype"])
                    variant = obj["variant"]
                    ts_widget.select_tile_by_variant(ttype, variant)
                    return

    def _point_in_selection(self, grid_pos: Tuple[int, int]) -> bool:
        """Check if a grid position is inside the current selection."""
        if not self.selection_rect:
            return False
        x1, y1, x2, y2 = self.selection_rect
        return x1 <= grid_pos[0] <= x2 and y1 <= grid_pos[1] <= y2

    def _finalize_selection(self):
        """Clean up empty selections after drag."""
        if self.selection_rect:
            x1, y1, x2, y2 = self.selection_rect
            if x1 == x2 and y1 == y2:
                self.selection_rect = None

    def copy_selection(self):
        """Copy the current selection to clipboard."""
        if not self.selection_rect:
            return

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            return

        x1, y1, x2, y2 = self.selection_rect
        self.clipboard = {
            "layer_type": active_layer.layer_type,
            "origin": (x1, y1),
            "tiles": {},
            "objects": [],
        }

        if active_layer.layer_type == "tile":
            for gy in range(y1, y2 + 1):
                for gx in range(x1, x2 + 1):
                    tile = active_layer.get_tile((gx, gy))
                    if tile:
                        rel_pos = (gx - x1, gy - y1)
                        self.clipboard["tiles"][rel_pos] = tile.copy()
        elif active_layer.layer_type == "object":
            sel_rect = Rect(
                x1 * self.tile_size[0],
                y1 * self.tile_size[1],
                (x2 - x1 + 1) * self.tile_size[0],
                (y2 - y1 + 1) * self.tile_size[1],
            )
            for obj_id, obj in active_layer.get_all_objects().items():
                area = obj["area"]
                obj_rect = Rect(area["x"], area["y"], area["w"], area["h"])
                if sel_rect.contains(obj_rect):
                    rel_obj = obj.copy()
                    rel_obj["area"] = {
                        "x": area["x"] - sel_rect.x,
                        "y": area["y"] - sel_rect.y,
                        "w": area["w"],
                        "h": area["h"],
                    }
                    self.clipboard["objects"].append(rel_obj)

        count = len(self.clipboard["tiles"]) + len(self.clipboard["objects"])
        if count > 0:
            self.editor.notifications.success(f"Copied {count} items")
        else:
            self.clipboard = None
            self.editor.notifications.notify("Nothing to copy")

    def paste_clipboard(self, target_pos: Tuple[int, int]):
        """Paste clipboard contents at the given grid position."""
        if not self.clipboard:
            return

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            return

        origin = self.clipboard["origin"]

        if (
            self.clipboard["layer_type"] == "tile"
            and active_layer.layer_type == "tile"
        ):
            for rel_pos, tile in self.clipboard["tiles"].items():
                gx = target_pos[0] + rel_pos[0]
                gy = target_pos[1] + rel_pos[1]
                new_tile = tile.copy()
                new_tile["pos"] = (gx, gy)
                active_layer.set_tile((gx, gy), new_tile)
            count = len(self.clipboard["tiles"])
            self.editor.notifications.success(f"Pasted {count} tiles")

        elif (
            self.clipboard["layer_type"] == "object"
            and active_layer.layer_type == "object"
        ):
            target_pixel = (
                target_pos[0] * self.tile_size[0],
                target_pos[1] * self.tile_size[1],
            )
            for obj in self.clipboard["objects"]:
                new_obj = obj.copy()
                new_obj["area"] = {
                    "x": target_pixel[0] + obj["area"]["x"],
                    "y": target_pixel[1] + obj["area"]["y"],
                    "w": obj["area"]["w"],
                    "h": obj["area"]["h"],
                }
                active_layer.add_object(
                    (new_obj["area"]["x"], new_obj["area"]["y"]), new_obj
                )
            count = len(self.clipboard["objects"])
            self.editor.notifications.success(f"Pasted {count} objects")
        else:
            self.editor.notifications.notify(
                "Cannot paste: layer type mismatch"
            )

    def delete_selection(self):
        """Delete all tiles/objects within the selection rectangle."""
        if not self.selection_rect:
            return

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            return

        x1, y1, x2, y2 = self.selection_rect

        if active_layer.layer_type == "tile":
            count = 0
            for gy in range(y1, y2 + 1):
                for gx in range(x1, x2 + 1):
                    if active_layer.remove_tile((gx, gy)):
                        count += 1
            self.editor.notifications.success(f"Deleted {count} tiles")
        elif active_layer.layer_type == "object":
            sel_rect = Rect(
                x1 * self.tile_size[0],
                y1 * self.tile_size[1],
                (x2 - x1 + 1) * self.tile_size[0],
                (y2 - y1 + 1) * self.tile_size[1],
            )
            count = 0
            for obj_id, obj in list(active_layer.get_all_objects().items()):
                area = obj["area"]
                obj_rect = Rect(area["x"], area["y"], area["w"], area["h"])
                if sel_rect.contains(obj_rect):
                    active_layer.remove_object(obj_id)
                    count += 1
            self.editor.notifications.success(f"Deleted {count} objects")

        self.selection_rect = None
        self.editor.tilemap.update_map_size()

    def _begin_move(self, mouse_pos: Tuple[int, int]):
        """Enter move mode: user clicked inside the selection rectangle."""
        self.is_moving = True
        self.move_start_mouse = mouse_pos
        self.move_origin_rect = self.selection_rect
        self.move_delta = (0, 0)

    def _update_move_delta(self, mouse_pos: Tuple[int, int]):
        """Update the move delta based on mouse drag distance."""
        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer or not self.move_origin_rect:
            return

        dx_screen = mouse_pos[0] - self.move_start_mouse[0]
        dy_screen = mouse_pos[1] - self.move_start_mouse[1]

        if active_layer.layer_type == "tile":
            # Grid-snapped movement
            eff_w, eff_h = self.effective_tile_size
            grid_dx = int(dx_screen / (eff_w * self.zoom_level))
            grid_dy = int(dy_screen / (eff_h * self.zoom_level))
            self.move_delta = (grid_dx, grid_dy)
        else:
            # Pixel-precise movement for objects
            world_dx = dx_screen / self.zoom_level
            world_dy = dy_screen / self.zoom_level
            self.move_delta = (int(world_dx), int(world_dy))

    def commit_move(self):
        """Apply the move delta to the actual layer data."""
        if not self.is_moving or not self.move_origin_rect:
            return

        dx, dy = self.move_delta
        if dx == 0 and dy == 0:
            self.is_moving = False
            self.move_start_mouse = None
            self.move_origin_rect = None
            return

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            self.is_moving = False
            self.move_start_mouse = None
            self.move_origin_rect = None
            return

        self.editor.tilemap.capture_history("Move Selection")

        x1, y1, x2, y2 = self.move_origin_rect

        if active_layer.layer_type == "tile":
            # Collect tiles in the selection, remove them, re-add at offset positions
            tiles_to_move = []
            for gy in range(y1, y2 + 1):
                for gx in range(x1, x2 + 1):
                    tile = active_layer.get_tile((gx, gy))
                    if tile:
                        tiles_to_move.append(((gx, gy), tile.copy()))

            # Remove originals
            for pos, _ in tiles_to_move:
                active_layer.remove_tile(pos)

            # Place at new positions
            for (_, _), tile in tiles_to_move:
                new_pos = (tile["pos"][0] + dx, tile["pos"][1] + dy)
                new_tile = tile.copy()
                new_tile["pos"] = new_pos
                active_layer.set_tile(new_pos, new_tile)

            # Update selection rect
            self.selection_rect = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)

        elif active_layer.layer_type == "object":
            # Collect objects fully contained in selection
            sel_rect = Rect(
                x1 * self.tile_size[0],
                y1 * self.tile_size[1],
                (x2 - x1 + 1) * self.tile_size[0],
                (y2 - y1 + 1) * self.tile_size[1],
            )
            objects_to_move = []
            for obj_id, obj in active_layer.get_all_objects().items():
                area = obj["area"]
                obj_rect = Rect(area["x"], area["y"], area["w"], area["h"])
                if sel_rect.contains(obj_rect):
                    objects_to_move.append((obj_id, obj.copy()))

            # Remove originals
            for obj_id, _ in objects_to_move:
                active_layer.remove_object(obj_id)

            # Place at new positions
            for _, obj in objects_to_move:
                new_obj = obj.copy()
                new_obj["area"] = {
                    "x": obj["area"]["x"] + dx,
                    "y": obj["area"]["y"] + dy,
                    "w": obj["area"]["w"],
                    "h": obj["area"]["h"],
                }
                active_layer.add_object(
                    (new_obj["area"]["x"], new_obj["area"]["y"]), new_obj
                )

            # Update selection rect (pixel delta → grid delta, but track pixel offset)
            grid_dx = dx // self.tile_size[0]
            grid_dy = dy // self.tile_size[1]
            self.selection_rect = (x1 + grid_dx, y1 + grid_dy, x2 + grid_dx, y2 + grid_dy)
            self._selection_pixel_offset = (dx % self.tile_size[0], dy % self.tile_size[1])

        self.is_moving = False
        self.move_start_mouse = None
        self.move_origin_rect = None
        self.move_delta = (0, 0)
        self._selection_pixel_offset = (0, 0)
        self.editor.tilemap.update_map_size()

    def cancel_move(self):
        """Cancel the current move, restoring original positions."""
        origin = self.move_origin_rect
        self.is_moving = False
        self.move_start_mouse = None
        self.move_origin_rect = None
        self.move_delta = (0, 0)
        if origin:
            self.selection_rect = origin

    def draw(self, screen: Surface):
        # 1. Background for the whole widget area
        pygame.draw.rect(screen, COLORS.panel, self.rect)

        # 2. Main clipping (full widget area)
        widget_clip = self.rect.clip(screen.get_rect())
        prev_clip = screen.get_clip()

        # 3. Apply widget-level clip
        screen.set_clip(widget_clip)

        tilemap = self.editor.tilemap
        if tilemap.initialized:
            self.render_map(screen)
            if self.show_grid:
                self._draw_grid(screen)
        else:
            # Only print once to avoid console flooding
            if (
                not hasattr(self, "_last_init_warn")
                or pygame.time.get_ticks() - self._last_init_warn > 5000
            ):
                print("DEBUG: Tilemap not initialized, skipping render")
                self._last_init_warn = pygame.time.get_ticks()

        self._draw_preview(screen)
        self._draw_move_preview(screen)
        self._draw_selection_rect(screen)

        # 4. Restore global clip and draw widget-level decorations
        screen.set_clip(prev_clip)
        self._draw_eraser_overlay(screen)
        self._draw_status_bar(screen)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)

    def _draw_preview(self, screen):
        active_layer = self.editor.tilemap.layer_manager.get_active_layer()

        # Eraser preview (when eraser mode is active or during erase)
        if self.editor.eraser_mode and self.hover_cell:
            eff_w, eff_h = self.effective_tile_size
            screen_x = (
                self.hover_cell[0] * eff_w - self.scroll_x
            ) * self.zoom_level + self.rect.x
            screen_y = (
                self.hover_cell[1] * eff_h - self.scroll_y
            ) * self.zoom_level + self.rect.y
            size_w = int(eff_w * self.eraser_size * self.zoom_level)
            size_h = int(eff_h * self.eraser_size * self.zoom_level)
            dest_rect = Rect(screen_x, screen_y, size_w, size_h)
            pygame.draw.rect(screen, (255, 50, 50), dest_rect, 2)
            return

        # Move preview (during drag-move)
        if self.is_moving and self.hover_cell:
            return  # Tiles are already drawn at new positions by _update_move_preview

        res = self.get_selected_brush()
        if not res:
            return
        _, tileset_data, src_rect = res
        if not tileset_data or not src_rect:
            return

        if not active_layer:
            return

        tile_w, tile_h = self.tile_size

        if active_layer.layer_type == "object":
            mouse_pos = pygame.mouse.get_pos()
            world_x, world_y = self.screen_to_world(mouse_pos)
            rs = self.editor.tilemap.render_scale

            sel_width = int(src_rect[2] * rs * self.zoom_level)
            sel_height = int(src_rect[3] * rs * self.zoom_level)

            screen_x = (world_x - self.scroll_x) * self.zoom_level + self.rect.x
            screen_y = (world_y - self.scroll_y) * self.zoom_level + self.rect.y

            dest_rect = Rect(screen_x, screen_y, sel_width, sel_height)
            pygame.draw.rect(screen, (255, 255, 0), dest_rect, 2)

            try:
                sub_r = Rect(src_rect[0], src_rect[1], src_rect[2], src_rect[3])
                tile_surf = tileset_data.surface.subsurface(sub_r)
                if self.zoom_level != 1.0:
                    tile_surf = pygame.transform.scale(
                        tile_surf, (sel_width, sel_height)
                    )
                tile_surf.set_alpha(128)
                screen.blit(tile_surf, (screen_x, screen_y))
            except ValueError:
                pass
        else:
            if not self.hover_cell:
                return

            eff_w, eff_h = self.effective_tile_size

            sel_w_tiles = src_rect[2] // tile_w
            sel_h_tiles = src_rect[3] // tile_h

            for y_off in range(sel_h_tiles):
                for x_off in range(sel_w_tiles):
                    col = self.hover_cell[0] + x_off
                    row = self.hover_cell[1] + y_off

                    screen_x = (
                        col * eff_w - self.scroll_x
                    ) * self.zoom_level + self.rect.x
                    screen_y = (
                        row * eff_h - self.scroll_y
                    ) * self.zoom_level + self.rect.y

                    dest_w = int(eff_w * self.zoom_level)
                    dest_h = int(eff_h * self.zoom_level)
                    dest_rect = Rect(screen_x, screen_y, dest_w, dest_h)

                    pygame.draw.rect(screen, (255, 255, 255), dest_rect, 1)

                    try:
                        tex_x = src_rect[0] + (x_off * tile_w)
                        tex_y = src_rect[1] + (y_off * tile_h)

                        sub_r = Rect(tex_x, tex_y, tile_w, tile_h)

                        tile_surf = tileset_data.surface.subsurface(sub_r)
                        if self.zoom_level != 1.0:
                            tile_surf = pygame.transform.scale(
                                tile_surf, (dest_w, dest_h)
                            )
                        tile_surf.set_alpha(128)
                        screen.blit(tile_surf, dest_rect)
                    except ValueError:
                        pass

    def _draw_grid(self, screen):
        eff_w, eff_h = self.effective_tile_size
        map_w, map_h = self.editor.tilemap.map_size

        # World coordinates of map boundaries
        map_world_w = map_w * eff_w
        map_world_h = map_h * eff_h

        # Screen coordinates of map top-left
        map_screen_x = (0 - self.scroll_x) * self.zoom_level + self.rect.x
        map_screen_y = (0 - self.scroll_y) * self.zoom_level + self.rect.y

        # Screen size of the map
        map_display_w = map_world_w * self.zoom_level
        map_display_h = map_world_h * self.zoom_level

        # Calculate visible range in grid units
        # We divide widget dimensions by zoom to find world distance, then divide by tile size
        visible_world_w = self.rect.width / self.zoom_level
        visible_world_h = self.rect.height / self.zoom_level

        start_col = max(0, int(self.scroll_x // eff_w))
        end_col = min(map_w, int((self.scroll_x + visible_world_w) // eff_w) + 1)

        start_row = max(0, int(self.scroll_y // eff_h))
        end_row = min(map_h, int((self.scroll_y + visible_world_h) // eff_h) + 1)

        # Draw vertical lines (at column positions)
        for col in range(start_col, end_col + 1):
            x = (col * eff_w - self.scroll_x) * self.zoom_level + self.rect.x
            # Line goes from top of map to bottom of map (clipping handled by surface clip)
            pygame.draw.line(
                screen,
                self.grid_color,
                (x, map_screen_y),
                (x, map_screen_y + map_display_h),
            )

        # Draw horizontal lines (at row positions)
        for row in range(start_row, end_row + 1):
            y = (row * eff_h - self.scroll_y) * self.zoom_level + self.rect.y
            # Line goes from left of map to right of map
            pygame.draw.line(
                screen,
                self.grid_color,
                (map_screen_x, y),
                (map_screen_x + map_display_w, y),
            )

    def _draw_status_bar(self, screen):
        bar_h = 25
        bar_rect = Rect(0, self.editor.height - bar_h, self.editor.width, bar_h)
        pygame.draw.rect(screen, COLORS.header, bar_rect)
        pygame.draw.line(
            screen, COLORS.border_soft, (0, bar_rect.y), (self.editor.width, bar_rect.y)
        )

        pygame.font.SysFont("Arial", 12)

        mouse_pos = pygame.mouse.get_pos()
        world_pos = self.screen_to_world(mouse_pos)
        grid_pos = self.get_grid_pos(mouse_pos)

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        layer_name = active_layer.name if active_layer else "None"

        tileset_name = "-"
        if self.editor.tileset_widget and self.editor.tileset_widget.active_idx != -1:
            ts = self.editor.tileset_widget.tilesets[
                self.editor.tileset_widget.active_idx
            ]
            tileset_name = ts.name

        can_undo = self.editor.tilemap.history.can_undo
        can_redo = self.editor.tilemap.history.can_redo
        zoom_pct = int(self.zoom_level * 100)
        parts = [
            f"World {world_pos}",
            f"Grid {grid_pos}",
            f"Zoom {zoom_pct}%",
            f"Layer {layer_name}",
            f"Tileset {tileset_name}",
        ]
        if self.editor.select_mode:
            if self.is_moving:
                parts.append("Tool: Moving")
            else:
                parts.append("Tool: Select")
        elif self.editor.eraser_mode:
            parts.append("Tool: Eraser")
        elif self.editor.pan_mode:
            parts.append("Tool: Pan")
        else:
            parts.append("Tool: Paint")
        parts.append(f"Auto {'On' if self.editor.autotile_mode else 'Off'}")
        if self.eraser_size > 1:
            parts.append(f"Eraser {self.eraser_size}")
        if self.selection_rect:
            x1, y1, x2, y2 = self.selection_rect
            parts.append(f"Sel {x2-x1+1}x{y2-y1+1}")
        if self.clipboard:
            ct = len(self.clipboard.get("tiles", {})) + len(
                self.clipboard.get("objects", [])
            )
            parts.append(f"Clip {ct}")
        parts.append(
            f"Undo {'Y' if can_undo else 'N'} / Redo {'Y' if can_redo else 'N'}"
        )
        status_text = " | ".join(parts)
        txt = self.font_status.render(status_text, True, (200, 200, 200))
        screen.blit(txt, (10, bar_rect.y + 5))

    def render_map(self, surface: Surface):
        tilemap = self.editor.tilemap
        if not tilemap.initialized:
            return

        tile_w, tile_h = self.tile_size
        rs = tilemap.render_scale
        eff_w = tile_w * rs
        eff_h = tile_h * rs

        map_w, map_h = tilemap.map_size

        # visible world bounds (in effective world space)
        visible_world_w = self.rect.width / self.zoom_level
        visible_world_h = self.rect.height / self.zoom_level

        start_col = max(0, int(self.scroll_x // eff_w))
        end_col = min(map_w, int((self.scroll_x + visible_world_w) // eff_w) + 1)

        start_row = max(0, int(self.scroll_y // eff_h))
        end_row = min(map_h, int((self.scroll_y + visible_world_h) // eff_h) + 1)

        assert self.editor.tileset_widget is not None
        tileset_map = self.editor.tileset_widget.tileset_map

        rendered_layers = tilemap.layer_manager.get_rendered_layers()

        for layer in rendered_layers:
            if layer.opacity < 1.0:
                # Create a temporary surface for the layer to handle opacity properly
                layer_surf = pygame.Surface(
                    (self.rect.width, self.rect.height), pygame.SRCALPHA
                )
                # Use a coordinate system relative to the widget for blitting inside the layer_surf
                draw_offset_x = -self.rect.x
                draw_offset_y = -self.rect.y
            else:
                layer_surf = surface
                draw_offset_x = 0
                draw_offset_y = 0

            if layer.layer_type == "tile":
                for x in range(start_col, end_col):
                    for y in range(start_row, end_row):
                        location = (x, y)

                        tile = layer.get_tile(location)
                        if not tile:
                            continue

                        ttype = int(tile["ttype"])

                        if ttype not in tileset_map:
                            continue

                        tileset_data = tileset_map[ttype]
                        base_surf = tileset_data.surface

                        variant_id = tile["variant"]
                        sheet_w = base_surf.get_width()

                        # Source rect always uses logical tile size
                        sheet_cols = sheet_w // tile_w
                        src_x = (variant_id % sheet_cols) * tile_w
                        src_y = (variant_id // sheet_cols) * tile_h
                        src_rect = Rect(src_x, src_y, tile_w, tile_h)

                        # Dest position uses effective (scaled) tile size
                        dest_x = (
                            (x * eff_w - self.scroll_x) * self.zoom_level
                            + self.rect.x
                            + draw_offset_x
                        )
                        dest_y = (
                            (y * eff_h - self.scroll_y) * self.zoom_level
                            + self.rect.y
                            + draw_offset_y
                        )

                        # Scale if zoomed or render_scaled
                        if self.zoom_level != 1.0 or rs != 1.0:
                            scaled_w = int(eff_w * self.zoom_level)
                            scaled_h = int(eff_h * self.zoom_level)
                            if base_surf.get_rect().contains(src_rect):
                                sub = base_surf.subsurface(src_rect)
                                scaled_sub = pygame.transform.scale(
                                    sub, (scaled_w, scaled_h)
                                )
                                layer_surf.blit(scaled_sub, (dest_x, dest_y))
                        else:
                            if base_surf.get_rect().contains(src_rect):
                                layer_surf.blit(
                                    base_surf, (dest_x, dest_y), area=src_rect
                                )

            elif layer.layer_type == "object":
                for obj_id, obj in layer.get_all_objects().items():
                    ttype = obj["ttype"]

                    if ttype not in tileset_map:
                        continue

                    tileset_data = tileset_map[ttype]
                    base_surf = tileset_data.surface

                    variant_id = obj["variant"]
                    area = obj["area"]
                    obj_x, obj_y = area["x"], area["y"]
                    obj_w, obj_h = area["w"], area["h"]
                    if tileset_data.tileset_type == "object":
                        src_rect = Rect(0, 0, obj_w, obj_h)
                    else:
                        sheet_w = base_surf.get_width()
                        sheet_cols = sheet_w // tile_w
                        src_x = (variant_id % sheet_cols) * tile_w
                        src_y = (variant_id // sheet_cols) * tile_h
                        src_rect = Rect(src_x, src_y, obj_w, obj_h)

                    dest_x = (
                        (obj_x - self.scroll_x) * self.zoom_level
                        + self.rect.x
                        + draw_offset_x
                    )
                    dest_y = (
                        (obj_y - self.scroll_y) * self.zoom_level
                        + self.rect.y
                        + draw_offset_y
                    )

                    if self.zoom_level != 1.0 or rs != 1.0:
                        scaled_w = int(obj_w * rs * self.zoom_level)
                        scaled_h = int(obj_h * rs * self.zoom_level)
                        if base_surf.get_rect().contains(src_rect):
                            sub = base_surf.subsurface(src_rect)
                            scaled_sub = pygame.transform.scale(
                                sub, (scaled_w, scaled_h)
                            )
                            layer_surf.blit(scaled_sub, (dest_x, dest_y))
                    else:
                        if base_surf.get_rect().contains(src_rect):
                            layer_surf.blit(base_surf, (dest_x, dest_y), area=src_rect)

            if layer.opacity < 1.0:
                layer_surf.set_alpha(int(layer.opacity * 255))
                surface.blit(layer_surf, (self.rect.x, self.rect.y))

    def _draw_eraser_overlay(self, screen):
        if self.eraser_overlay_timer <= 0:
            return

        dt = self.editor.clock.get_time()
        self.eraser_overlay_timer -= dt

        alpha = min(255, self.eraser_overlay_timer // 2)
        if alpha <= 0:
            return

        text = f"Eraser Size: {self.eraser_size}"
        surf = self.font_overlay.render(text, True, (255, 255, 255))
        surf.set_alpha(alpha)

        # Draw background bubble
        rect = surf.get_rect(center=(self.rect.centerx, self.rect.bottom - 100))
        bg_rect = rect.inflate(20, 10)
        bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, alpha // 2), bg.get_rect(), border_radius=10)

        screen.blit(bg, bg_rect)
        screen.blit(surf, rect)

    def _draw_selection_rect(self, screen):
        """Draw the selection rectangle overlay on the map."""
        if not self.selection_rect:
            return

        eff_w, eff_h = self.effective_tile_size
        rs = self.editor.tilemap.render_scale
        x1, y1, x2, y2 = self.selection_rect
        px_off, py_off = 0, 0  # sub-tile pixel offset (objects only)

        # During move, offset the selection rect by move_delta
        if self.is_moving:
            dx, dy = self.move_delta
            active_layer = self.editor.tilemap.layer_manager.get_active_layer()
            if active_layer and active_layer.layer_type == "tile":
                x1 += dx
                y1 += dy
                x2 += dx
                y2 += dy
            else:
                # Object layer: use grid delta for grid-based offset
                grid_dx = dx // self.tile_size[0]
                grid_dy = dy // self.tile_size[1]
                x1 += grid_dx
                y1 += grid_dy
                x2 += grid_dx
                y2 += grid_dy
                # Apply sub-tile pixel offset for display (scaled by render_scale)
                px_off = (dx % self.tile_size[0]) * rs
                py_off = (dy % self.tile_size[1]) * rs

        # Convert grid coords to screen coords
        sx = (x1 * eff_w - self.scroll_x) * self.zoom_level + self.rect.x + px_off * self.zoom_level
        sy = (y1 * eff_h - self.scroll_y) * self.zoom_level + self.rect.y + py_off * self.zoom_level
        sw = (x2 - x1 + 1) * eff_w * self.zoom_level
        sh = (y2 - y1 + 1) * eff_h * self.zoom_level

        sel_rect = Rect(int(sx), int(sy), int(sw), int(sh))

        # Semi-transparent fill
        fill_surf = pygame.Surface((int(sw), int(sh)), pygame.SRCALPHA)
        fill_surf.fill((100, 180, 255, 40))
        screen.blit(fill_surf, (int(sx), int(sy)))

        # Dashed border (draw segments)
        border_color = (100, 180, 255) if not self.is_moving else (255, 200, 50)
        dash_len = 6
        gap_len = 4

        # Top and bottom edges
        for edge_y in [sel_rect.top, sel_rect.bottom - 1]:
            x = sel_rect.left
            while x < sel_rect.right:
                end = min(x + dash_len, sel_rect.right)
                pygame.draw.line(screen, border_color, (x, edge_y), (end, edge_y), 2)
                x += dash_len + gap_len

        # Left and right edges
        for edge_x in [sel_rect.left, sel_rect.right - 1]:
            y = sel_rect.top
            while y < sel_rect.bottom:
                end = min(y + dash_len, sel_rect.bottom)
                pygame.draw.line(screen, border_color, (edge_x, y), (edge_x, end), 2)
                y += dash_len + gap_len

    def _draw_move_preview(self, screen):
        """Draw semi-transparent preview of selected content at the move offset position.

        This renders the tiles/objects at their proposed new position WITHOUT
        modifying the actual layer data. The layer is only modified on commit_move().
        """
        if not self.is_moving or not self.move_origin_rect or not self.selection_rect:
            return

        dx, dy = self.move_delta
        if dx == 0 and dy == 0:
            return

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            return

        tilemap = self.editor.tilemap
        tile_w, tile_h = self.tile_size
        rs = tilemap.render_scale
        eff_w = tile_w * rs
        eff_h = tile_h * rs

        ox1, oy1, ox2, oy2 = self.move_origin_rect

        # Create a temporary surface for the preview
        preview_surf = pygame.Surface(
            (self.rect.width, self.rect.height), pygame.SRCALPHA
        )

        assert self.editor.tileset_widget is not None
        tileset_map = self.editor.tileset_widget.tileset_map

        if active_layer.layer_type == "tile":
            for gy in range(oy1, oy2 + 1):
                for gx in range(ox1, ox2 + 1):
                    tile = active_layer.get_tile((gx, gy))
                    if not tile:
                        continue

                    ttype = int(tile["ttype"])
                    if ttype not in tileset_map:
                        continue

                    tileset_data = tileset_map[ttype]
                    base_surf = tileset_data.surface
                    variant_id = tile["variant"]
                    sheet_w = base_surf.get_width()
                    sheet_cols = sheet_w // tile_w
                    src_x = (variant_id % sheet_cols) * tile_w
                    src_y = (variant_id // sheet_cols) * tile_h
                    src_rect = Rect(src_x, src_y, tile_w, tile_h)

                    # New position with delta offset
                    new_gx = gx + dx
                    new_gy = gy + dy
                    dest_x = (
                        (new_gx * eff_w - self.scroll_x) * self.zoom_level
                        + self.rect.x
                    )
                    dest_y = (
                        (new_gy * eff_h - self.scroll_y) * self.zoom_level
                        + self.rect.y
                    )

                    if self.zoom_level != 1.0 or rs != 1.0:
                        scaled_w = int(eff_w * self.zoom_level)
                        scaled_h = int(eff_h * self.zoom_level)
                        if base_surf.get_rect().contains(src_rect):
                            sub = base_surf.subsurface(src_rect)
                            scaled_sub = pygame.transform.scale(sub, (scaled_w, scaled_h))
                            scaled_sub.set_alpha(160)
                            preview_surf.blit(scaled_sub, (dest_x, dest_y))
                    else:
                        if base_surf.get_rect().contains(src_rect):
                            tile_copy = base_surf.subsurface(src_rect).copy()
                            tile_copy.set_alpha(160)
                            preview_surf.blit(tile_copy, (dest_x, dest_y))

        elif active_layer.layer_type == "object":
            sel_rect = Rect(
                ox1 * self.tile_size[0],
                oy1 * self.tile_size[1],
                (ox2 - ox1 + 1) * self.tile_size[0],
                (oy2 - oy1 + 1) * self.tile_size[1],
            )
            for obj_id, obj in active_layer.get_all_objects().items():
                area = obj["area"]
                obj_rect = Rect(area["x"], area["y"], area["w"], area["h"])
                if not sel_rect.contains(obj_rect):
                    continue

                ttype = obj["ttype"]
                if ttype not in tileset_map:
                    continue

                tileset_data = tileset_map[ttype]
                base_surf = tileset_data.surface
                variant_id = obj["variant"]
                obj_w, obj_h = area["w"], area["h"]

                if tileset_data.tileset_type == "object":
                    src_rect = Rect(0, 0, obj_w, obj_h)
                else:
                    sheet_w = base_surf.get_width()
                    sheet_cols = sheet_w // tile_w
                    src_x = (variant_id % sheet_cols) * tile_w
                    src_y = (variant_id // sheet_cols) * tile_h
                    src_rect = Rect(src_x, src_y, obj_w, obj_h)

                new_x = area["x"] + dx
                new_y = area["y"] + dy
                dest_x = (
                    (new_x - self.scroll_x) * self.zoom_level
                    + self.rect.x
                )
                dest_y = (
                    (new_y - self.scroll_y) * self.zoom_level
                    + self.rect.y
                )

                if self.zoom_level != 1.0 or rs != 1.0:
                    scaled_w = int(obj_w * rs * self.zoom_level)
                    scaled_h = int(obj_h * rs * self.zoom_level)
                    if base_surf.get_rect().contains(src_rect):
                        sub = base_surf.subsurface(src_rect)
                        scaled_sub = pygame.transform.scale(sub, (scaled_w, scaled_h))
                        scaled_sub.set_alpha(160)
                        preview_surf.blit(scaled_sub, (dest_x, dest_y))
                else:
                    if base_surf.get_rect().contains(src_rect):
                        tile_copy = base_surf.subsurface(src_rect).copy()
                        tile_copy.set_alpha(160)
                        preview_surf.blit(tile_copy, (dest_x, dest_y))

        # Blit the preview onto the screen
        screen.blit(preview_surf, (0, 0))

    def _get_group_for_tile(self, tile: TypeTile) -> Optional[str]:
        if not hasattr(self.editor, "autotiler"):
            return None

        ttype = tile["ttype"]
        variant = tile["variant"]

        # Check all rules in the designer
        for group in self.editor.autotiler.groups:
            for rule in group.rules:
                if rule.tileset_index == ttype and variant in rule.variant_ids:
                    return group.name
        return None
