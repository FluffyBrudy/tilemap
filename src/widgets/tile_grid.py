from typing import TYPE_CHECKING

import pygame
from pygame import K_LEFT, K_RIGHT, K_UP, Rect, Surface

from nodes import NodeRect
from ttypes.tilemap import TypeObject, TypeTile
from widgets.particle_system import MAX_DT, ParticlePreview
from widgets.ui.drag_tracker import DragTracker
from widgets.ui.theme import COLORS
from widgets.ui.tool_manager import ToolKind

if TYPE_CHECKING:
    from editor import Editor


class TileGrid:
    def __init__(self, editor: "Editor", rect: Rect):
        self.editor = editor
        self.rect = rect

        self.scroll_x = 0
        self.scroll_y = 0
        self.scroll_speed = 40

        from widgets.ui.scrollbar import Scrollbar

        self._h_scroll = Scrollbar("horizontal", on_scroll=self._on_h_scroll)
        self._v_scroll = Scrollbar("vertical", on_scroll=self._on_v_scroll)

        self.is_panning = False
        self.pan_start_pos = (0, 0)
        self.pan_start_scroll = (0, 0)
        self.hover_cell: tuple[int, int] | None = None

        self.grid_color = COLORS.text_muted
        self.show_grid = True

        self.eraser_size = 1
        self.zoom_level = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0

        self.font_status = pygame.font.SysFont("Arial", 12)
        self.font_overlay = pygame.font.SysFont("Arial", 24, bold=True)
        self._last_history_capture = 0

        self.last_eraser_adj_time = 0
        self.eraser_overlay_timer = 0
        self.adj_delay = 100

        self.selection_rect = None
        self.selection_start = None
        self.is_selecting = False

        self.is_moving = False
        self.move_delta = (0, 0)
        self.move_start_mouse = None
        self.move_origin_rect = None
        self._selection_pixel_offset = (0, 0)
        self._object_move_origins: dict[int, dict] = {}

        self.clipboard = None

        self._node_drag_state: str | None = None
        self._node_drag_handle: str | None = None
        self._node_original_rect = None
        self._node_drag_tracker = DragTracker()

        self._particle_previews: dict[str, ParticlePreview] = {}
        self._last_preview_time: float = 0.0
        self._last_active_node_id: str | None = None

        self._cached_bounds: tuple[int, int, int, int] | None = None

    @property
    def tile_size(self):
        return self.editor.tilemap.tile_size

    @property
    def effective_tile_size(self):
        tw, th = self.editor.tilemap.tile_size
        rs = self.editor.tilemap.render_scale
        return (tw * rs, th * rs)

    def _is_pan_event(self, event) -> bool:
        return event.button == 2 or (event.button == 1 and self.editor.tool_manager.is_active(ToolKind.PAN))

    def screen_to_world(self, pos: tuple[int, int]) -> tuple[int, int]:
        wx = (pos[0] - self.rect.x) / self.zoom_level + self.scroll_x
        wy = (pos[1] - self.rect.y) / self.zoom_level + self.scroll_y
        return int(wx), int(wy)

    def get_grid_pos(self, pos: tuple[int, int]) -> tuple[int, int]:
        wx, wy = self.screen_to_world(pos)
        eff_w, eff_h = self.effective_tile_size
        return int(wx // eff_w), int(wy // eff_h)

    def _get_map_bounds(self) -> tuple[int, int, int, int]:
        if self._cached_bounds is not None:
            return self._cached_bounds

        tm = self.editor.tilemap
        eff_w, eff_h = self.effective_tile_size
        map_w, map_h = tm.map_size

        min_col = 0
        max_col = map_w
        min_row = 0
        max_row = map_h

        for layer in tm.layer_manager.layers:
            if layer.tiles:
                for pos in layer.tiles:
                    min_col = min(min_col, pos[0])
                    max_col = max(max_col, pos[0] + 1)
                    min_row = min(min_row, pos[1])
                    max_row = max(max_row, pos[1] + 1)

            if layer.objects:
                for obj in layer.objects.values():
                    area = obj["area"]
                    grid_l = int(area["x"] // tm.tile_size[0])
                    grid_r = -(-int(area["x"] + area["w"]) // tm.tile_size[0])
                    grid_t = int(area["y"] // tm.tile_size[1])
                    grid_b = -(-int(area["y"] + area["h"]) // tm.tile_size[1])
                    min_col = min(min_col, grid_l)
                    max_col = max(max_col, grid_r)
                    min_row = min(min_row, grid_t)
                    max_row = max(max_row, grid_b)

        self._cached_bounds = (
            min_col * eff_w,
            max_col * eff_w,
            min_row * eff_h,
            max_row * eff_h,
        )
        return self._cached_bounds

    def invalidate_bounds_cache(self):
        """Invalidate the cached bounds when tiles, objects, or layers change."""
        self._cached_bounds = None

    def _on_h_scroll(self, val: float):
        world_min_x, _, _, _ = self._get_map_bounds()
        self.scroll_x = val + world_min_x
        self.clamp_scroll()
        self._update_scrollbar_ranges()

    def _on_v_scroll(self, val: float):
        _, _, world_min_y, _ = self._get_map_bounds()
        self.scroll_y = val + world_min_y
        self.clamp_scroll()
        self._update_scrollbar_ranges()

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

            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
            meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)

            if ctrl_held or meta_held:
                current_time = pygame.time.get_ticks()
                if current_time - self.last_eraser_adj_time > self.adj_delay:
                    adj = 0

                    if keys[pygame.K_EQUALS] or keys[pygame.K_PLUS] or keys[pygame.K_KP_PLUS]:
                        adj = 1
                    elif keys[pygame.K_MINUS] or keys[pygame.K_KP_MINUS]:
                        adj = -1

                    if adj != 0:
                        self.eraser_size = max(1, min(100, self.eraser_size + adj))
                        self.last_eraser_adj_time = current_time
                        self.eraser_overlay_timer = 1500

        self.clamp_scroll()
        self._update_scrollbar_ranges()
        try:
            self._update_particle_previews()
        except Exception:
            import traceback

            traceback.print_exc()

    def _view_metrics(self):
        tm = self.editor.tilemap
        eff_w, eff_h = self.effective_tile_size
        map_w, map_h = tm.map_size
        mww = map_w * eff_w
        mwh = map_h * eff_h
        vww = self.rect.width / self.zoom_level
        vwh = self.rect.height / self.zoom_level
        return mww, mwh, vww, vwh

    def clamp_scroll(self):
        if not self.editor.tilemap.initialized:
            return
        mww, mwh, vww, vwh = self._view_metrics()
        world_min_x, world_max_x, world_min_y, world_max_y = self._get_map_bounds()

        min_x = world_min_x - vww
        max_x = world_max_x
        self.scroll_x = max(min_x, min(self.scroll_x, max_x))

        min_y = world_min_y - vwh
        max_y = world_max_y
        self.scroll_y = max(min_y, min(self.scroll_y, max_y))

    def _update_scrollbar_ranges(self):
        if not self.editor.tilemap.initialized:
            return
        sw = 12
        bw = 12
        self._v_scroll.rect = Rect(self.rect.right - sw, self.rect.y, sw, self.rect.h - bw)
        self._h_scroll.rect = Rect(self.rect.x, self.rect.bottom - bw, self.rect.width - sw, bw)
        mww, mwh, vww, vwh = self._view_metrics()
        world_min_x, world_max_x, world_min_y, world_max_y = self._get_map_bounds()

        span_x = max(vww, world_max_x - world_min_x)
        span_y = max(vwh, world_max_y - world_min_y)

        self._h_scroll.set_range(span_x, vww, self.scroll_x - world_min_x)
        self._v_scroll.set_range(span_y, vwh, self.scroll_y - world_min_y)

    def zoom_by(self, delta: float, center: tuple[int, int] | None = None):
        old_zoom = self.zoom_level
        new_zoom = max(self.min_zoom, min(self.max_zoom, old_zoom + delta))
        if new_zoom == old_zoom:
            return
        if center is None:
            center = pygame.mouse.get_pos()
        wx = (center[0] - self.rect.x) / old_zoom + self.scroll_x
        wy = (center[1] - self.rect.y) / old_zoom + self.scroll_y
        self.zoom_level = new_zoom
        self.scroll_x = wx - (center[0] - self.rect.x) / new_zoom
        self.scroll_y = wy - (center[1] - self.rect.y) / new_zoom

    def center_on_map(self):
        """Center the map in the viewport (unbounded scroll: map can be anywhere)."""
        eff_w, eff_h = self.effective_tile_size
        world_w = self.editor.tilemap.map_size[0] * eff_w
        world_h = self.editor.tilemap.map_size[1] * eff_h
        if world_w <= 0 or world_h <= 0:
            return
        view_w = self.rect.width / self.zoom_level
        view_h = self.rect.height / self.zoom_level
        self.scroll_x = world_w / 2 - view_w / 2
        self.scroll_y = world_h / 2 - view_h / 2

    def reset_view(self):
        self.zoom_level = 1.0
        self.center_on_map()

    def fit_to_map(self):
        eff_w, eff_h = self.effective_tile_size
        world_w = self.editor.tilemap.map_size[0] * eff_w
        world_h = self.editor.tilemap.map_size[1] * eff_h
        if world_w <= 0 or world_h <= 0:
            return
        zoom_x = self.rect.width / world_w
        zoom_y = self.rect.height / world_h
        self.zoom_level = max(self.min_zoom, min(self.max_zoom, min(zoom_x, zoom_y)))
        self.center_on_map()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._v_scroll.handle_event(event) or self._h_scroll.handle_event(event):
            return True
        if self.editor.node_editing_mode:
            return self._handle_node_event(event)

        if self.editor.show_nodes and self._handle_show_node_event(event):
            return True

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
                        self.editor.notifications.success(f"Autotile complete: {count} tiles updated")
                    else:
                        self.editor.notifications.notify("No tiles updated (Already matched or no groups found)")
                return True

            if event.key == pygame.K_f:
                if is_hovering and self.hover_cell:
                    res = self.get_selected_brush()
                    if res:
                        self.editor.tilemap.capture_history("Flood Fill")
                        tileset_index, tileset_data, src_rect = res
                        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
                        assert tileset_data is not None
                        assert src_rect is not None

                        if active_layer and active_layer.layer_type == "tile":
                            tile_w, tile_h = self.tile_size
                            sheet_cols = tileset_data.surface.get_width() // tile_w
                            variant_id = (src_rect[1] // tile_h * sheet_cols) + (src_rect[0] // tile_w)

                            assert tileset_index is not None
                            new_data: TypeTile = {
                                "ttype": tileset_index,
                                "variant": variant_id,
                                "pos": (0, 0),
                            }
                            active_layer.flood_fill(self.hover_cell, new_data, self.editor.tilemap.map_size)
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
                            self.editor.notifications.notify(f"Group: {gid}", color=(100, 200, 255))
                        else:
                            self.editor.notifications.notify("Group: None (No rule matches)", color=(200, 200, 200))
                    else:
                        self.editor.notifications.notify("No tile at cursor")
                return True

            if event.key == pygame.K_c and (ctrl_held or meta_held):
                if self.selection_rect:
                    self.copy_selection()
                return True

            if event.key == pygame.K_x and (ctrl_held or meta_held):
                if self.selection_rect:
                    self.copy_selection()
                    self.editor.tilemap.capture_history("Cut Selection")
                    self.delete_selection()
                return True

            if event.key == pygame.K_v and (ctrl_held or meta_held):
                if self.clipboard and is_hovering and self.hover_cell:
                    self.editor.tilemap.capture_history("Paste")
                    self.paste_clipboard(self.hover_cell)
                return True

            if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
                if self.selection_rect:
                    self.editor.tilemap.capture_history("Delete Selection")
                    self.delete_selection()
                return True

            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                if self.is_moving:
                    self.commit_move()
                elif self.selection_rect:
                    self.selection_rect = None
                return True

            if event.key == pygame.K_ESCAPE:
                if self.is_moving:
                    self.cancel_move()
                elif self.selection_rect:
                    self.selection_rect = None
                return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if self._is_pan_event(event) and is_hovering:
                self.is_panning = True
                self.pan_start_pos = mouse_pos
                self.pan_start_scroll = (self.scroll_x, self.scroll_y)
                return True

            if event.button == 1:
                if self.editor.tool_manager.is_active(ToolKind.SELECT):
                    if is_hovering:
                        if self.hover_cell:
                            if self.selection_rect and self._point_in_selection(self.hover_cell):
                                self._begin_move(mouse_pos)
                            else:
                                if self.editor.show_nodes:
                                    nm = getattr(self.editor, "node_manager", None)
                                    if nm and nm.nodes:
                                        node = self._get_node_at_screen(nm, mouse_pos)
                                        if node:
                                            nm.set_active_node(node.node_id)
                                            self._start_node_drag(mouse_pos, node)
                                            return True
                                        nm.set_active_node(None)

                                self.selection_start = self.hover_cell
                                self.is_selecting = True
                                self.selection_rect = (
                                    self.hover_cell[0],
                                    self.hover_cell[1],
                                    self.hover_cell[0],
                                    self.hover_cell[1],
                                )
                        else:
                            self.selection_rect = None
                    else:
                        self.selection_rect = None
                    return True

                if self.editor.tool_manager.is_active(ToolKind.ERASER):
                    if is_hovering:
                        self.editor.tilemap.capture_history("Erase Tile")
                        self.remove_tile()
                    return True

                if is_hovering and not self.is_panning:
                    self.editor.tilemap.capture_history("Place Tile")
                    self.place_tile()
                    return True

            if event.button == 3:
                if is_hovering and self.hover_cell:
                    self.pick_tile_at(self.hover_cell)
                return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if self._is_pan_event(event):
                self.is_panning = False
                return True

            if event.button == 1:
                if self._node_drag_state is not None:
                    self._clear_node_drag()
                    return True
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

            if self._node_drag_state is not None and is_hovering:
                if self._update_node_drag(mouse_pos):
                    return True

            if is_hovering:
                self.hover_cell = self.get_grid_pos(mouse_pos)
            else:
                self.hover_cell = None

            if self.is_selecting and self.selection_start and self.hover_cell:
                x1 = min(self.selection_start[0], self.hover_cell[0])
                y1 = min(self.selection_start[1], self.hover_cell[1])
                x2 = max(self.selection_start[0], self.hover_cell[0])
                y2 = max(self.selection_start[1], self.hover_cell[1])
                self.selection_rect = (x1, y1, x2, y2)

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
                    scroll_val = event.y if event.y != 0 else event.x
                    self.scroll_x -= scroll_val * self.scroll_speed
                else:
                    self.scroll_x -= event.x * self.scroll_speed
                    self.scroll_y -= event.y * self.scroll_speed
                self.clamp_scroll()
                self._update_scrollbar_ranges()
                return True

        buttons = pygame.mouse.get_pressed()
        if (
            not self.editor.tool_manager.is_active(ToolKind.PAN)
            and not self.editor.tool_manager.is_active(ToolKind.SELECT)
            and not self.is_panning
        ) and buttons[0] and is_hovering:
            if self.editor.tool_manager.is_active(ToolKind.ERASER):
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
        if not self.editor.tilemap.initialized:
            return
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

            mouse_pos = pygame.mouse.get_pos()
            world_pos = self.screen_to_world(mouse_pos)
            self.editor.tilemap.incremental_update_map_size(world_pos, is_pixel=True, size=(src_rect[2], src_rect[3]))
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

            sel_w_tiles = src_rect[2] // tile_w
            sel_h_tiles = src_rect[3] // tile_h
            last_tile_pos = (
                self.hover_cell[0] + sel_w_tiles - 1,
                self.hover_cell[1] + sel_h_tiles - 1,
            )
            self.editor.tilemap.incremental_update_map_size(last_tile_pos)

        self.invalidate_bounds_cache()

    def _place_tile_grid(
        self,
        active_layer,
        tileset_index: int,
        tileset_data,
        src_rect: tuple[int, int, int, int],
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
            rs = self.editor.tilemap.render_scale
            pixel_x = int(world_x / rs) if rs else world_x
            pixel_y = int(world_y / rs) if rs else world_y
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
            vg_map: dict = {}
            autotile_ok = self.editor.autotile_mode and getattr(self.editor, "autotiler", None)
            if autotile_ok:
                vg_map = self.editor.autotiler.variant_to_group

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

                    if variant_id in tileset_data.tile_properties:
                        tile_data["properties"] = tileset_data.tile_properties[variant_id].copy()

                    if autotile_ok:
                        auto_group = vg_map.get((tileset_index, variant_id))
                        if auto_group:
                            tile_data["autotile_group"] = auto_group
                        elif self.editor.autotiler.groups:
                            gidx = self.editor.autotiler.selected_group_idx
                            if 0 <= gidx < len(self.editor.autotiler.groups):
                                tile_data["autotile_group"] = self.editor.autotiler.groups[gidx].name

                    active_layer.set_tile(target_pos, tile_data)

                    if autotile_ok:
                        rules = self.editor.autotiler.rules
                        if rules:
                            active_layer.autotile_at_pos(target_pos, rules)

    def _place_object_free(
        self,
        active_layer,
        tileset_index: int,
        tileset_data,
        src_rect: tuple[int, int, int, int],
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
        rs = self.editor.tilemap.render_scale

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
                "x": int(world_pos[0] / rs) if rs else world_pos[0],
                "y": int(world_pos[1] / rs) if rs else world_pos[1],
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
            rs = self.editor.tilemap.render_scale

            tile_w, tile_h = self.tile_size
            erase_w = tile_w * self.eraser_size
            erase_h = tile_h * self.eraser_size
            erase_rect = Rect(
                int(world_pos[0] / rs) - erase_w // 2 if rs else world_pos[0] - erase_w // 2,
                int(world_pos[1] / rs) - erase_h // 2 if rs else world_pos[1] - erase_h // 2,
                erase_w,
                erase_h,
            )

            for obj_id, obj in list(active_layer.get_all_objects().items()):
                area = obj["area"]
                obj_rect = Rect(area["x"], area["y"], area["w"], area["h"])

                if erase_rect.colliderect(obj_rect):
                    active_layer.remove_object(obj_id)
                    if (
                        self.editor.tilemap.map_size[0] > self.editor.tilemap.initial_map_size[0]
                        or self.editor.tilemap.map_size[1] > self.editor.tilemap.initial_map_size[1]
                    ):
                        self.editor.tilemap.update_map_size()
            self.invalidate_bounds_cache()
        else:
            if not self.hover_cell:
                return

            must_rescan = False
            for dy in range(self.eraser_size):
                for dx in range(self.eraser_size):
                    pos = (self.hover_cell[0] + dx, self.hover_cell[1] + dy)
                    if active_layer.remove_tile(pos) and (
                        pos[0] >= self.editor.tilemap.map_size[0] - 1
                        or pos[1] >= self.editor.tilemap.map_size[1] - 1
                    ):
                        must_rescan = True

                    if self.editor.autotile_mode and getattr(self.editor, "autotiler", None):
                        rules = self.editor.autotiler.rules
                        if rules:
                            active_layer.autotile_at_pos(pos, rules)

            if must_rescan:
                self.editor.tilemap.update_map_size()
            self.invalidate_bounds_cache()

    def pick_tile_at(self, grid_pos: tuple[int, int]):
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
            mouse_pos = pygame.mouse.get_pos()
            world_pos = self.screen_to_world(mouse_pos)
            for _obj_id, obj in active_layer.get_all_objects().items():
                area = obj["area"]
                obj_rect = Rect(area["x"], area["y"], area["w"], area["h"])
                if obj_rect.collidepoint(world_pos):
                    ttype = int(obj["ttype"])
                    variant = obj["variant"]
                    ts_widget.select_tile_by_variant(ttype, variant)
                    return

    def _point_in_selection(self, grid_pos: tuple[int, int]) -> bool:
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
            tile_w, tile_h = self.tile_size
            sel_rect = Rect(
                x1 * tile_w,
                y1 * tile_h,
                (x2 - x1 + 1) * tile_w,
                (y2 - y1 + 1) * tile_h,
            )
            for _obj_id, obj in active_layer.get_all_objects().items():
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

    def paste_clipboard(self, target_pos: tuple[int, int]):
        """Paste clipboard contents at the given grid position."""
        if not self.clipboard:
            return

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            return

        self.clipboard["origin"]

        if self.clipboard["layer_type"] == "tile" and active_layer.layer_type == "tile":
            for rel_pos, tile in self.clipboard["tiles"].items():
                gx = target_pos[0] + rel_pos[0]
                gy = target_pos[1] + rel_pos[1]
                new_tile = tile.copy()
                new_tile["pos"] = (gx, gy)
                active_layer.set_tile((gx, gy), new_tile)
            count = len(self.clipboard["tiles"])
            self.editor.notifications.success(f"Pasted {count} tiles")
            self.editor.tilemap.update_map_size()
            self.invalidate_bounds_cache()

        elif self.clipboard["layer_type"] == "object" and active_layer.layer_type == "object":
            tile_w, tile_h = self.tile_size
            target_pixel = (
                target_pos[0] * tile_w,
                target_pos[1] * tile_h,
            )
            for obj in self.clipboard["objects"]:
                new_obj = obj.copy()
                new_obj["area"] = {
                    "x": target_pixel[0] + obj["area"]["x"],
                    "y": target_pixel[1] + obj["area"]["y"],
                    "w": obj["area"]["w"],
                    "h": obj["area"]["h"],
                }
                active_layer.add_object((new_obj["area"]["x"], new_obj["area"]["y"]), new_obj)
            count = len(self.clipboard["objects"])
            self.editor.notifications.success(f"Pasted {count} objects")
            self.editor.tilemap.update_map_size()
            self.invalidate_bounds_cache()
        else:
            self.editor.notifications.notify("Cannot paste: layer type mismatch")

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
            tile_w, tile_h = self.tile_size
            sel_rect = Rect(
                x1 * tile_w,
                y1 * tile_h,
                (x2 - x1 + 1) * tile_w,
                (y2 - y1 + 1) * tile_h,
            )
            count = 0
            for obj_id, obj in list(active_layer.get_all_objects().items()):
                area = obj["area"]
                obj_rect = Rect(area["x"], area["y"], area["w"], area["h"])
                if sel_rect.colliderect(obj_rect):
                    active_layer.remove_object(obj_id)
                    count += 1
            self.editor.notifications.success(f"Deleted {count} objects")

        self.selection_rect = None
        self.editor.tilemap.update_map_size()
        self.invalidate_bounds_cache()

    def _begin_move(self, mouse_pos: tuple[int, int]):
        """Enter move mode: user clicked inside the selection rectangle."""
        self.is_moving = True
        self.move_start_mouse = mouse_pos
        self.move_origin_rect = self.selection_rect
        self.move_delta = (0, 0)

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if active_layer and active_layer.layer_type == "object" and self.move_origin_rect:
            self._object_move_origins.clear()
            x1, y1, x2, y2 = self.move_origin_rect
            tile_w, tile_h = self.tile_size
            sel_rect = Rect(
                x1 * tile_w,
                y1 * tile_h,
                (x2 - x1 + 1) * tile_w,
                (y2 - y1 + 1) * tile_h,
            )
            for obj_id, obj in active_layer.get_all_objects().items():
                obj_rect = Rect(
                    obj["area"]["x"],
                    obj["area"]["y"],
                    obj["area"]["w"],
                    obj["area"]["h"],
                )
                if sel_rect.colliderect(obj_rect):
                    self._object_move_origins[obj_id] = {
                        "x": obj["area"]["x"],
                        "y": obj["area"]["y"],
                        "w": obj["area"]["w"],
                        "h": obj["area"]["h"],
                    }

    def _update_move_delta(self, mouse_pos: tuple[int, int]):
        """Update the move delta based on mouse drag distance."""
        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer or not self.move_origin_rect:
            return

        dx_screen = mouse_pos[0] - self.move_start_mouse[0]
        dy_screen = mouse_pos[1] - self.move_start_mouse[1]

        if active_layer.layer_type == "tile":
            eff_w, eff_h = self.effective_tile_size
            grid_dx = int(dx_screen / (eff_w * self.zoom_level))
            grid_dy = int(dy_screen / (eff_h * self.zoom_level))
            self.move_delta = (grid_dx, grid_dy)
        else:
            world_dx = dx_screen / self.zoom_level
            world_dy = dy_screen / self.zoom_level
            rs = self.editor.tilemap.render_scale
            if rs:
                world_dx = int(world_dx / rs)
                world_dy = int(world_dy / rs)
            else:
                world_dx = int(world_dx)
                world_dy = int(world_dy)
            self.move_delta = (world_dx, world_dy)

            for obj_id, orig in list(self._object_move_origins.items()):
                if obj_id in active_layer.objects:
                    obj = active_layer.objects[obj_id]
                    obj["area"]["x"] = orig["x"] + world_dx
                    obj["area"]["y"] = orig["y"] + world_dy

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
            tiles_to_move = []
            for gy in range(y1, y2 + 1):
                for gx in range(x1, x2 + 1):
                    tile = active_layer.get_tile((gx, gy))
                    if tile:
                        tiles_to_move.append(((gx, gy), tile.copy()))

            for pos, _ in tiles_to_move:
                active_layer.remove_tile(pos)

            for (_, _), tile in tiles_to_move:
                new_pos = (tile["pos"][0] + dx, tile["pos"][1] + dy)
                new_tile = tile.copy()
                new_tile["pos"] = new_pos
                active_layer.set_tile(new_pos, new_tile)

            self.selection_rect = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
            self._selection_pixel_offset = (0, 0)

        elif active_layer.layer_type == "object":
            self._object_move_origins.clear()
            tile_w, tile_h = self.tile_size
            grid_dx = int(dx // tile_w) if tile_w else 0
            grid_dy = int(dy // tile_h) if tile_h else 0
            self.selection_rect = (
                x1 + grid_dx,
                y1 + grid_dy,
                x2 + grid_dx,
                y2 + grid_dy,
            )
            self._selection_pixel_offset = (
                dx - grid_dx * tile_w,
                dy - grid_dy * tile_h,
            )
        else:
            self._selection_pixel_offset = (0, 0)

        self.is_moving = False
        self.move_start_mouse = None
        self.move_origin_rect = None
        self.move_delta = (0, 0)
        self.editor.tilemap.update_map_size()
        self.invalidate_bounds_cache()

    def cancel_move(self):
        """Cancel the current move, restoring original positions."""
        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if active_layer and active_layer.layer_type == "object" and self._object_move_origins:
            for obj_id, orig in self._object_move_origins.items():
                if obj_id in active_layer.objects:
                    obj = active_layer.objects[obj_id]
                    obj["area"]["x"] = orig["x"]
                    obj["area"]["y"] = orig["y"]
                    obj["area"]["w"] = orig["w"]
                    obj["area"]["h"] = orig["h"]
            self._object_move_origins.clear()

        origin = self.move_origin_rect
        self.is_moving = False
        self.move_start_mouse = None
        self.move_origin_rect = None
        self.move_delta = (0, 0)
        if origin:
            self.selection_rect = origin

    def _draw_background(self, screen):
        """Draw infinite plane (solid dark) and map area (panel + accent border)."""
        try:
            if self.rect.width <= 0 or self.rect.height <= 0:
                return
            eff_w, eff_h = self.effective_tile_size
            map_w, map_h = self.editor.tilemap.map_size
            if eff_w <= 0 or eff_h <= 0 or map_w <= 0 or map_h <= 0:
                pygame.draw.rect(screen, COLORS.panel, self.rect)
                return

            pygame.draw.rect(screen, COLORS.panel_alt, self.rect)

            map_screen_x = (0 - self.scroll_x) * self.zoom_level + self.rect.x
            map_screen_y = (0 - self.scroll_y) * self.zoom_level + self.rect.y
            map_display_w = map_w * eff_w * self.zoom_level
            map_display_h = map_h * eff_h * self.zoom_level
            if map_display_w <= 0 or map_display_h <= 0:
                return
            map_rect = Rect(
                int(map_screen_x),
                int(map_screen_y),
                int(map_display_w),
                int(map_display_h),
            )

            visible = map_rect.clip(self.rect)
            if visible.width > 0 and visible.height > 0:
                pygame.draw.rect(screen, COLORS.panel, visible)
                pygame.draw.rect(screen, COLORS.accent, visible, 3)
        except Exception:
            pygame.draw.rect(screen, COLORS.panel, self.rect)

    def draw(self, screen: Surface):
        prev_clip = screen.get_clip()
        try:
            tilemap = self.editor.tilemap

            if tilemap.initialized:
                self._draw_background(screen)
            else:
                pygame.draw.rect(screen, COLORS.panel, self.rect)

            widget_clip = self.rect.clip(screen.get_rect())

            screen.set_clip(widget_clip)

            if tilemap.initialized:
                self.render_map(screen)
                if self.show_grid:
                    self._draw_grid(screen)
                self._draw_map_boundary(screen)
            else:
                if not hasattr(self, "_last_init_warn") or pygame.time.get_ticks() - self._last_init_warn > 5000:
                    print("DEBUG: Tilemap not initialized, skipping render")
                    self._last_init_warn = pygame.time.get_ticks()

            self._draw_preview(screen)
            self._draw_move_preview(screen)
            self._draw_selection_rect(screen)
            self._draw_nodes(screen)

            screen.set_clip(prev_clip)
            self._draw_eraser_overlay(screen)
            self._draw_status_bar(screen)
            if tilemap.initialized:
                self._v_scroll.draw(screen)
                self._h_scroll.draw(screen)
            pygame.draw.rect(screen, COLORS.border, self.rect, 1)
        except Exception:
            import traceback

            traceback.print_exc()
            pygame.draw.rect(screen, COLORS.panel, self.rect)
        finally:
            screen.set_clip(prev_clip)

    def _draw_preview(self, screen):
        active_layer = self.editor.tilemap.layer_manager.get_active_layer()

        if self.editor.tool_manager.is_active(ToolKind.ERASER):
            if active_layer and active_layer.layer_type == "object" and self.rect.collidepoint(pygame.mouse.get_pos()):
                mouse_pos = pygame.mouse.get_pos()
                wx, wy = self.screen_to_world(mouse_pos)
                tile_w, tile_h = self.tile_size
                erase_w = tile_w * self.eraser_size
                erase_h = tile_h * self.eraser_size
                sx = int((wx - erase_w / 2 - self.scroll_x) * self.zoom_level + self.rect.x)
                sy = int((wy - erase_h / 2 - self.scroll_y) * self.zoom_level + self.rect.y)
                sw = int(erase_w * self.zoom_level)
                sh = int(erase_h * self.zoom_level)
                pygame.draw.rect(screen, (255, 50, 50), Rect(sx, sy, sw, sh), 2)
                return
            if self.hover_cell:
                eff_w, eff_h = self.effective_tile_size
                screen_x = (self.hover_cell[0] * eff_w - self.scroll_x) * self.zoom_level + self.rect.x
                screen_y = (self.hover_cell[1] * eff_h - self.scroll_y) * self.zoom_level + self.rect.y
                size_w = int(eff_w * self.eraser_size * self.zoom_level)
                size_h = int(eff_h * self.eraser_size * self.zoom_level)
                dest_rect = Rect(screen_x, screen_y, size_w, size_h)
                pygame.draw.rect(screen, (255, 50, 50), dest_rect, 2)
                return

        if self.is_moving and self.hover_cell:
            return

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
                    tile_surf = pygame.transform.scale(tile_surf, (sel_width, sel_height))
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

                    screen_x = (col * eff_w - self.scroll_x) * self.zoom_level + self.rect.x
                    screen_y = (row * eff_h - self.scroll_y) * self.zoom_level + self.rect.y

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
                            tile_surf = pygame.transform.scale(tile_surf, (dest_w, dest_h))
                        tile_surf.set_alpha(128)
                        screen.blit(tile_surf, dest_rect)
                    except ValueError:
                        pass

    def _draw_grid(self, screen):
        eff_w, eff_h = self.effective_tile_size
        map_w, map_h = self.editor.tilemap.map_size

        map_world_w = map_w * eff_w
        map_world_h = map_h * eff_h

        (0 - self.scroll_x) * self.zoom_level + self.rect.x
        (0 - self.scroll_y) * self.zoom_level + self.rect.y

        map_world_w * self.zoom_level
        map_world_h * self.zoom_level

        visible_world_w = self.rect.width / self.zoom_level
        visible_world_h = self.rect.height / self.zoom_level

        start_col = int(self.scroll_x // eff_w)
        end_col = int((self.scroll_x + visible_world_w) // eff_w) + 1

        start_row = int(self.scroll_y // eff_h)
        end_row = int((self.scroll_y + visible_world_h) // eff_h) + 1

        for col in range(start_col, end_col + 1):
            x = (col * eff_w - self.scroll_x) * self.zoom_level + self.rect.x

            pygame.draw.line(
                screen,
                self.grid_color,
                (x, self.rect.y),
                (x, self.rect.bottom),
            )

        for row in range(start_row, end_row + 1):
            y = (row * eff_h - self.scroll_y) * self.zoom_level + self.rect.y
            pygame.draw.line(
                screen,
                self.grid_color,
                (self.rect.x, y),
                (self.rect.right, y),
            )

    def _draw_map_boundary(self, screen):
        eff_w, eff_h = self.effective_tile_size
        map_w, map_h = self.editor.tilemap.map_size

        boundary = Rect(
            self.rect.x + (-self.scroll_x) * self.zoom_level,
            self.rect.y + (-self.scroll_y) * self.zoom_level,
            map_w * eff_w * self.zoom_level,
            map_h * eff_h * self.zoom_level,
        )

        border_color = (100, 150, 255)
        border_width = max(2, int(3 * self.zoom_level))

        edges = (
            (
                self.rect.top <= boundary.top <= self.rect.bottom,
                (max(boundary.left, self.rect.left), boundary.top),
                (min(boundary.right, self.rect.right), boundary.top),
            ),
            (
                self.rect.top <= boundary.bottom <= self.rect.bottom,
                (max(boundary.left, self.rect.left), boundary.bottom),
                (min(boundary.right, self.rect.right), boundary.bottom),
            ),
            (
                self.rect.left <= boundary.left <= self.rect.right,
                (boundary.left, max(boundary.top, self.rect.top)),
                (boundary.left, min(boundary.bottom, self.rect.bottom)),
            ),
            (
                self.rect.left <= boundary.right <= self.rect.right,
                (boundary.right, max(boundary.top, self.rect.top)),
                (boundary.right, min(boundary.bottom, self.rect.bottom)),
            ),
        )

        for visible, start, end in edges:
            if visible:
                pygame.draw.line(screen, border_color, start, end, border_width)

    def _draw_status_bar(self, screen):
        bar_h = 25
        bar_rect = Rect(0, self.editor.height - bar_h, self.editor.width, bar_h)
        pygame.draw.rect(screen, COLORS.header, bar_rect)
        pygame.draw.line(screen, COLORS.border_soft, (0, bar_rect.y), (self.editor.width, bar_rect.y))

        pygame.font.SysFont("Arial", 12)

        mouse_pos = pygame.mouse.get_pos()
        world_pos = self.screen_to_world(mouse_pos)
        grid_pos = self.get_grid_pos(mouse_pos)

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        layer_name = active_layer.name if active_layer else "None"

        tileset_name = "-"
        if self.editor.tileset_widget and self.editor.tileset_widget.active_idx != -1:
            ts = self.editor.tileset_widget.tilesets[self.editor.tileset_widget.active_idx]
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
        if self.editor.tool_manager.is_active(ToolKind.SELECT):
            if self.is_moving:
                parts.append("Tool: Moving")
            else:
                parts.append("Tool: Select")
        elif self.editor.tool_manager.is_active(ToolKind.ERASER):
            parts.append("Tool: Eraser")
        elif self.editor.tool_manager.is_active(ToolKind.PAN):
            parts.append("Tool: Pan")
        else:
            parts.append("Tool: Paint")
        parts.append(f"Auto {'On' if self.editor.autotile_mode else 'Off'}")
        if self.eraser_size > 1:
            parts.append(f"Eraser {self.eraser_size}")
        if self.selection_rect:
            x1, y1, x2, y2 = self.selection_rect
            parts.append(f"Sel {x2 - x1 + 1}x{y2 - y1 + 1}")
        if self.clipboard:
            ct = len(self.clipboard.get("tiles", {})) + len(self.clipboard.get("objects", []))
            parts.append(f"Clip {ct}")
        parts.append(f"Undo {'Y' if can_undo else 'N'} / Redo {'Y' if can_redo else 'N'}")
        status_text = " | ".join(parts)
        txt = self.font_status.render(status_text, True, COLORS.text)
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

        visible_world_w = self.rect.width / self.zoom_level
        visible_world_h = self.rect.height / self.zoom_level

        start_col = int(self.scroll_x // eff_w)
        end_col = int((self.scroll_x + visible_world_w) // eff_w) + 1

        start_row = int(self.scroll_y // eff_h)
        end_row = int((self.scroll_y + visible_world_h) // eff_h) + 1

        assert self.editor.tileset_widget is not None
        tileset_map = self.editor.tileset_widget.tileset_map

        rendered_layers = tilemap.layer_manager.get_rendered_layers()

        for layer in rendered_layers:
            if layer.opacity < 1.0:
                layer_surf = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)

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
                        if tileset_data.animation:
                            anim = tileset_data.animation
                            duration = anim.get("frame_duration_ms", 0)
                            frame_count = anim.get("frame_count", 1)
                            if duration > 0 and frame_count > 0:
                                frame_ms = pygame.time.get_ticks()
                                frame_idx = int(frame_ms / duration) % frame_count
                                if anim.get("animation_mode") == "random_start_times":
                                    phase = hash((x, y, ttype)) % frame_count
                                    frame_idx = (frame_idx + phase) % frame_count
                                variant_id += frame_idx * anim.get("frame_stride", 1)

                        sheet_w = base_surf.get_width()

                        sheet_cols = sheet_w // tile_w
                        src_x = (variant_id % sheet_cols) * tile_w
                        src_y = (variant_id // sheet_cols) * tile_h
                        src_rect = Rect(src_x, src_y, tile_w, tile_h)

                        dest_x = (x * eff_w - self.scroll_x) * self.zoom_level + self.rect.x + draw_offset_x
                        dest_y = (y * eff_h - self.scroll_y) * self.zoom_level + self.rect.y + draw_offset_y

                        if self.zoom_level != 1.0 or rs != 1.0:
                            scaled_w = int(eff_w * self.zoom_level)
                            scaled_h = int(eff_h * self.zoom_level)
                            if base_surf.get_rect().contains(src_rect):
                                sub = base_surf.subsurface(src_rect)
                                scaled_sub = pygame.transform.scale(sub, (scaled_w, scaled_h))
                                layer_surf.blit(scaled_sub, (dest_x, dest_y))
                        else:
                            if base_surf.get_rect().contains(src_rect):
                                layer_surf.blit(base_surf, (dest_x, dest_y), area=src_rect)

            elif layer.layer_type == "object":
                for _obj_id, obj in layer.get_all_objects().items():
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

                    dest_x = (obj_x * rs - self.scroll_x) * self.zoom_level + self.rect.x + draw_offset_x
                    dest_y = (obj_y * rs - self.scroll_y) * self.zoom_level + self.rect.y + draw_offset_y

                    if self.zoom_level != 1.0 or rs != 1.0:
                        scaled_w = int(obj_w * rs * self.zoom_level)
                        scaled_h = int(obj_h * rs * self.zoom_level)
                        if base_surf.get_rect().contains(src_rect):
                            sub = base_surf.subsurface(src_rect)
                            scaled_sub = pygame.transform.scale(sub, (scaled_w, scaled_h))
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
        px_off, py_off = 0, 0

        if self.is_moving:
            dx, dy = self.move_delta
            active_layer = self.editor.tilemap.layer_manager.get_active_layer()
            if active_layer and active_layer.layer_type == "tile":
                x1 += dx
                y1 += dy
                x2 += dx
                y2 += dy
            else:
                tile_w, tile_h = self.tile_size
                grid_dx = int(dx // tile_w) if tile_w else 0
                grid_dy = int(dy // tile_h) if tile_h else 0
                x1 += grid_dx
                y1 += grid_dy
                x2 += grid_dx
                y2 += grid_dy

                px_off = int(dx - grid_dx * tile_w) * rs
                py_off = int(dy - grid_dy * tile_h) * rs

        sx = (x1 * eff_w - self.scroll_x) * self.zoom_level + self.rect.x + px_off * self.zoom_level
        sy = (y1 * eff_h - self.scroll_y) * self.zoom_level + self.rect.y + py_off * self.zoom_level
        sw = (x2 - x1 + 1) * eff_w * self.zoom_level
        sh = (y2 - y1 + 1) * eff_h * self.zoom_level

        sel_rect = Rect(int(sx), int(sy), int(sw), int(sh))

        if not self.is_selecting:
            fill_surf = pygame.Surface((int(sw), int(sh)), pygame.SRCALPHA)
            fill_surf.fill((100, 180, 255, 40))
            screen.blit(fill_surf, (int(sx), int(sy)))

        border_color = (100, 180, 255) if not self.is_moving else (255, 200, 50)
        dash_len = 6
        gap_len = 4

        for edge_y in [sel_rect.top, sel_rect.bottom - 1]:
            x = sel_rect.left
            while x < sel_rect.right:
                end = min(x + dash_len, sel_rect.right)
                pygame.draw.line(screen, border_color, (x, edge_y), (end, edge_y), 2)
                x += dash_len + gap_len

        for edge_x in [sel_rect.left, sel_rect.right - 1]:
            y = sel_rect.top
            while y < sel_rect.bottom:
                end = min(y + dash_len, sel_rect.bottom)
                pygame.draw.line(screen, border_color, (edge_x, y), (edge_x, end), 2)
                y += dash_len + gap_len

    def _node_to_screen(self, nx: int, ny: int) -> tuple[int, int]:
        sx = (nx - self.scroll_x) * self.zoom_level + self.rect.x
        sy = (ny - self.scroll_y) * self.zoom_level + self.rect.y
        return int(sx), int(sy)

    def _node_screen_size(self, nw: int, nh: int) -> tuple[int, int]:
        rs = self.editor.tilemap.render_scale
        return int(nw * rs * self.zoom_level), int(nh * rs * self.zoom_level)

    def _draw_nodes(self, screen):
        nm = getattr(self.editor, "node_manager", None)
        if not nm or not nm.nodes:
            return

        editing = self.editor.node_editing_mode
        showing = self.editor.show_nodes

        node_type_colors = {
            "area": (80, 220, 120),
            "spawn": (80, 140, 240),
            "portal": (180, 80, 220),
            "npc": (240, 140, 60),
            "checkpoint": (60, 200, 200),
            "item": (220, 200, 60),
            "particle_emitter": (240, 140, 200),
        }

        visible = editing or showing
        active = nm.get_active_node() if visible else None
        for node in nm.nodes.values():
            sx, sy = self._node_to_screen(node.area.x, node.area.y)
            sw, sh = self._node_screen_size(node.area.w, node.area.h)

            if not self.rect.colliderect(Rect(sx, sy, sw, sh)):
                continue

            is_active = visible and active is not None and active.node_id == node.node_id
            if editing:
                alpha = 180 if is_active else 80
            elif showing:
                alpha = 140 if is_active else 70
            else:
                alpha = 40

            color = node_type_colors.get(node.node_type, (80, 220, 120))

            fill = pygame.Surface((sw, sh), pygame.SRCALPHA)
            fill.fill((*color, alpha // 2))
            screen.blit(fill, (sx, sy))

            border_color = (*color, alpha)
            pygame.draw.rect(
                screen,
                border_color,
                Rect(sx, sy, sw, sh),
                max(1, int(2 * self.zoom_level)),
            )

            if visible:
                label = self.font_status.render(node.name, True, (255, 255, 255))
                label_bg = pygame.Surface((label.get_width() + 4, label.get_height() + 2), pygame.SRCALPHA)
                label_bg.fill((0, 0, 0, 160))
                screen.blit(label_bg, (sx, sy - label.get_height() - 2))
                screen.blit(label, (sx + 2, sy - label.get_height() - 1))

            if is_active and editing:
                self._draw_node_handles(screen, Rect(sx, sy, sw, sh), color)

        self._draw_particle_previews(screen)

    def _update_particle_previews(self):
        now = pygame.time.get_ticks()
        dt = min((now - self._last_preview_time) / 1000.0, MAX_DT) if self._last_preview_time > 0 else 0.016
        self._last_preview_time = now

        nm = getattr(self.editor, "node_manager", None)
        if not nm or not self.editor.node_editing_mode:
            self._particle_previews.clear()
            self._last_active_node_id = None
            return

        active = nm.get_active_node()
        active_id = active.node_id if active else None

        if active_id and active.node_type == "particle_emitter":
            if active_id not in self._particle_previews:
                self._particle_previews[active_id] = ParticlePreview(dict(active.properties))
            preview = self._particle_previews[active_id]
            rs = self.editor.tilemap.render_scale
            preview.update(dt, active.area.x, active.area.y, active.area.w * rs, active.area.h * rs)
            self._last_active_node_id = active_id
        else:
            self._particle_previews.clear()
            self._last_active_node_id = None

    def _draw_particle_previews(self, screen):
        if not self.editor.node_editing_mode:
            return
        nm = getattr(self.editor, "node_manager", None)
        if not nm:
            return
        active = nm.get_active_node()
        if not active or active.node_type != "particle_emitter":
            return
        preview = self._particle_previews.get(active.node_id)
        if preview:
            preview.draw(screen, self.scroll_x, self.scroll_y, self.zoom_level, self.rect)

    def reset_particle_preview(self, node_id: str, config: dict) -> None:
        pv = self._particle_previews.get(node_id)
        if pv:
            pv.reset(dict(config))
        else:
            self._particle_previews[node_id] = ParticlePreview(dict(config))

    def _draw_node_handles(self, screen, rect: Rect, border_color: tuple[int, int, int] = (80, 220, 80)):
        hs = 6
        hsize = max(4, int(hs * self.zoom_level))
        positions = [
            (rect.left, rect.top),
            (rect.centerx, rect.top),
            (rect.right, rect.top),
            (rect.left, rect.centery),
            (rect.right, rect.centery),
            (rect.left, rect.bottom),
            (rect.centerx, rect.bottom),
            (rect.right, rect.bottom),
        ]
        for px, py in positions:
            hr = Rect(px - hsize, py - hsize, hsize * 2, hsize * 2)
            pygame.draw.rect(screen, (255, 255, 255), hr)
            pygame.draw.rect(screen, border_color, hr, 1)

    def _get_node_handle_at(self, node, screen_pos) -> str | None:
        sx, sy = self._node_to_screen(node.area.x, node.area.y)
        sw, sh = self._node_screen_size(node.area.w, node.area.h)
        r = Rect(sx, sy, sw, sh)
        hs = max(4, int(6 * self.zoom_level))
        d = hs * 2
        handles = {
            "tl": Rect(r.left - hs, r.top - hs, d, d),
            "t": Rect(r.centerx - hs, r.top - hs, d, d),
            "tr": Rect(r.right - hs, r.top - hs, d, d),
            "l": Rect(r.left - hs, r.centery - hs, d, d),
            "r": Rect(r.right - hs, r.centery - hs, d, d),
            "bl": Rect(r.left - hs, r.bottom - hs, d, d),
            "b": Rect(r.centerx - hs, r.bottom - hs, d, d),
            "br": Rect(r.right - hs, r.bottom - hs, d, d),
        }
        sp = pygame.Vector2(screen_pos)
        for name, hrect in handles.items():
            if hrect.collidepoint(sp):
                return name
        return None

    def _get_node_at_screen(self, nm, mouse_pos):
        for node in nm.nodes.values():
            sx, sy = self._node_to_screen(node.area.x, node.area.y)
            sw, sh = self._node_screen_size(node.area.w, node.area.h)
            if Rect(sx, sy, sw, sh).collidepoint(mouse_pos):
                return node
        return None

    def _screen_to_world_float(self, pos):
        wx = (pos[0] - self.rect.x) / self.zoom_level + self.scroll_x
        wy = (pos[1] - self.rect.y) / self.zoom_level + self.scroll_y
        return wx, wy

    def _start_node_drag(self, mouse_pos, node):
        self._node_drag_state = "moving"
        self._node_drag_tracker.begin(
            mouse_pos,
            self.zoom_level,
            self.scroll_x,
            self.scroll_y,
            self.rect.x,
            self.rect.y,
        )
        self._node_original_rect = NodeRect(
            node.area.x,
            node.area.y,
            node.area.w,
            node.area.h,
        )

    def _update_node_drag(self, mouse_pos) -> bool:
        nm = getattr(self.editor, "node_manager", None)
        if not nm:
            return False
        active = nm.get_active_node()
        if not active or not self._node_original_rect or self._node_drag_state != "moving":
            return False
        orig = self._node_original_rect
        dx, dy = self._node_drag_tracker.update(
            mouse_pos,
            self.zoom_level,
            self.scroll_x,
            self.scroll_y,
            self.rect.x,
            self.rect.y,
        )
        active.area.x = int(orig.x + dx)
        active.area.y = int(orig.y + dy)
        return True

    def _clear_node_drag(self):
        self._node_drag_state = None
        self._node_drag_handle = None
        self._node_original_rect = None
        self._node_drag_tracker.reset()

    def _handle_show_node_event(self, event) -> bool:
        nm = getattr(self.editor, "node_manager", None)
        if not nm or not nm.nodes:
            return False

        mouse_pos = pygame.mouse.get_pos()
        is_hover = self.rect.collidepoint(mouse_pos)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and is_hover:
                active = nm.get_active_node()

                if active:
                    sw, sh = self._node_screen_size(active.area.w, active.area.h)
                    sx, sy = self._node_to_screen(active.area.x, active.area.y)
                    if Rect(sx, sy, sw, sh).collidepoint(mouse_pos):
                        self._start_node_drag(mouse_pos, active)
                        return True

                    for node in nm.nodes.values():
                        if node.node_id == active.node_id:
                            continue
                        nsx, nsy = self._node_to_screen(node.area.x, node.area.y)
                        nsw, nsh = self._node_screen_size(node.area.w, node.area.h)
                        if Rect(nsx, nsy, nsw, nsh).collidepoint(mouse_pos):
                            nm.set_active_node(node.node_id)
                            return True
                else:
                    for node in nm.nodes.values():
                        nsx, nsy = self._node_to_screen(node.area.x, node.area.y)
                        nsw, nsh = self._node_screen_size(node.area.w, node.area.h)
                        if Rect(nsx, nsy, nsw, nsh).collidepoint(mouse_pos):
                            nm.set_active_node(node.node_id)
                            return True

                    nm.set_active_node(None)
                return False

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self._node_drag_state is not None:
                self._clear_node_drag()
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self._node_drag_state is not None and is_hover:
                self._update_node_drag(mouse_pos)
                return True

        return False

    def _handle_node_event(self, event) -> bool:
        nm = getattr(self.editor, "node_manager", None)
        if not nm:
            return False

        mouse_pos = pygame.mouse.get_pos()
        is_hover = self.rect.collidepoint(mouse_pos)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and is_hover:
                wx, wy = self.screen_to_world(mouse_pos)
                active = nm.get_active_node()

                if active:
                    handle = self._get_node_handle_at(active, mouse_pos)
                    if handle:
                        self._node_drag_state = "resizing"
                        self._node_drag_handle = handle
                        self._node_original_rect = NodeRect(
                            active.area.x,
                            active.area.y,
                            active.area.w,
                            active.area.h,
                        )
                        return True

                    sw, sh = self._node_screen_size(active.area.w, active.area.h)
                    sx, sy = self._node_to_screen(active.area.x, active.area.y)
                    body = Rect(sx, sy, sw, sh)
                    if body.collidepoint(mouse_pos):
                        self._start_node_drag(mouse_pos, active)
                        return True

                    for node in nm.nodes.values():
                        if node.node_id == active.node_id:
                            continue
                        nsx, nsy = self._node_to_screen(node.area.x, node.area.y)
                        nsw, nsh = self._node_screen_size(node.area.w, node.area.h)
                        if Rect(nsx, nsy, nsw, nsh).collidepoint(mouse_pos):
                            nm.set_active_node(node.node_id)
                            return True

                else:
                    for node in nm.nodes.values():
                        nsx, nsy = self._node_to_screen(node.area.x, node.area.y)
                        nsw, nsh = self._node_screen_size(node.area.w, node.area.h)
                        if Rect(nsx, nsy, nsw, nsh).collidepoint(mouse_pos):
                            nm.set_active_node(node.node_id)
                            return True

                    self.editor.tilemap.capture_history("Add Node")
                    layer = self.editor.tilemap.layer_manager.get_active_layer()
                    layer_name = layer.name if layer else "Default"
                    node = nm.create_default_node(layer_name, node_type=nm.default_node_type)
                    node.area.x = wx - 32
                    node.area.y = wy - 32
                    nm.add_node(node)
                    nm.set_active_node(node.node_id)
                    self._start_node_drag(mouse_pos, node)
                return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self._node_drag_state is not None:
                self._clear_node_drag()
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self._node_drag_state is not None and is_hover:
                if self._node_drag_state == "moving":
                    self._update_node_drag(mouse_pos)
                    return True

                if self._node_drag_state == "resizing":
                    active = nm.get_active_node()
                    if active and self._node_original_rect:
                        orig = self._node_original_rect
                        wx, wy = self._screen_to_world_float(mouse_pos)
                        h = self._node_drag_handle
                        rs = self.editor.tilemap.render_scale

                        if h == "tl":
                            old_r = orig.x + orig.w * rs
                            old_b = orig.y + orig.h * rs
                            nx = int(min(wx, old_r - 8 * rs))
                            ny = int(min(wy, old_b - 8 * rs))
                            active.area.x = nx
                            active.area.y = ny
                            active.area.w = max(8, int((old_r - nx) / rs))
                            active.area.h = max(8, int((old_b - ny) / rs))
                        elif h == "tr":
                            old_b = orig.y + orig.h * rs
                            nw = max(8, int((wx - orig.x) / rs))
                            ny = int(min(wy, old_b - 8 * rs))
                            active.area.w = nw
                            active.area.y = ny
                            active.area.h = max(8, int((old_b - ny) / rs))
                        elif h == "bl":
                            old_r = orig.x + orig.w * rs
                            nx = int(min(wx, old_r - 8 * rs))
                            nh = max(8, int((wy - orig.y) / rs))
                            active.area.x = nx
                            active.area.w = max(8, int((old_r - nx) / rs))
                            active.area.h = nh
                        elif h == "br":
                            active.area.w = max(8, int((wx - orig.x) / rs))
                            active.area.h = max(8, int((wy - orig.y) / rs))
                        elif h == "l":
                            old_r = orig.x + orig.w * rs
                            nx = int(min(wx, old_r - 8 * rs))
                            active.area.x = nx
                            active.area.w = max(8, int((old_r - nx) / rs))
                        elif h == "r":
                            active.area.w = max(8, int((wx - orig.x) / rs))
                        elif h == "t":
                            old_b = orig.y + orig.h * rs
                            ny = int(min(wy, old_b - 8 * rs))
                            active.area.y = ny
                            active.area.h = max(8, int((old_b - ny) / rs))
                        elif h == "b":
                            active.area.h = max(8, int((wy - orig.y) / rs))
                return True

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                nm.set_active_node(None)
                self._clear_node_drag()
                return True
            if event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
                active = nm.get_active_node()
                if active:
                    self.editor.tilemap.capture_history("Remove Node")
                    nm.remove_node(active.node_id)
                return True

        return False

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

        preview_surf = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)

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

                    new_gx = gx + dx
                    new_gy = gy + dy
                    dest_x = (new_gx * eff_w - self.scroll_x) * self.zoom_level
                    dest_y = (new_gy * eff_h - self.scroll_y) * self.zoom_level

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
            return

        screen.blit(preview_surf, self.rect.topleft)

    def _get_group_for_tile(self, tile: TypeTile) -> str | None:
        if not hasattr(self.editor, "autotiler"):
            return None

        ttype = tile["ttype"]
        variant = tile["variant"]

        for group in self.editor.autotiler.groups:
            for rule in group.rules:
                if rule.tileset_index == ttype and variant in rule.variant_ids:
                    return group.name
        return None
