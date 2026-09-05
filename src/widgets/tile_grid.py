from typing import TYPE_CHECKING

import pygame
from pygame import K_LEFT, K_RIGHT, K_UP, Rect, Surface

from nodes import NodeRect
from ttypes.tilemap import TypeObject, TypeTile
from utils.context_dispatch import ContextKind, PropertyContext
from widgets.particle_system import MAX_DT, ParticlePreview
from widgets.ui.drag_tracker import DragTracker
from widgets.ui.theme import COLORS, FONTS
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

        self.grid_color = COLORS.border_soft
        self.show_grid = True
        self.show_map_boundary = True

        self.eraser_size = 1
        self.zoom_level = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0

        self.font_status = FONTS.get_font(12)
        self.font_overlay = FONTS.get_bold_font(24)
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

        self._image_drag_state: str | None = None
        self._image_drag_handle: str | None = None
        self._image_original_rect: dict[str, int] | None = None
        self._image_drag_start: tuple[float, float] | None = None
        self._image_history_pending = False
        self._image_cache: dict[str, Surface | None] = {}
        self._scaled_image_cache: dict[tuple[int, tuple[int, int], str | None], Surface] = {}

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
        ox, oy = tm.offset
        mw, mh = tm.map_size

        world_min_x = ox * eff_w
        world_max_x = (ox + mw) * eff_w
        world_min_y = oy * eff_h
        world_max_y = (oy + mh) * eff_h

        self._cached_bounds = (world_min_x, world_max_x, world_min_y, world_max_y)
        return self._cached_bounds

    def invalidate_bounds_cache(self):
        """Invalidate the cached bounds when tiles, objects, or layers change."""
        self._cached_bounds = None

    def invalidate_image_cache(self, _layer=None) -> None:
        """Drop decoded image surfaces after a layer image is replaced."""
        self._image_cache.clear()
        self._scaled_image_cache.clear()

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
        """Center the map in the viewport using the fixed map bounds."""
        eff_w, eff_h = self.effective_tile_size
        tm = self.editor.tilemap
        ox, oy = tm.offset
        map_w, map_h = tm.map_size
        world_min_x = ox * eff_w
        world_max_x = (ox + map_w) * eff_w
        world_min_y = oy * eff_h
        world_max_y = (oy + map_h) * eff_h
        world_w = max(1, world_max_x - world_min_x)
        world_h = max(1, world_max_y - world_min_y)
        if world_w <= 0 or world_h <= 0:
            return
        view_w = self.rect.width / self.zoom_level
        view_h = self.rect.height / self.zoom_level
        self.scroll_x = world_min_x + world_w / 2 - view_w / 2
        self.scroll_y = world_min_y + world_h / 2 - view_h / 2

    def reset_view(self):
        self.zoom_level = 1.0
        self.center_on_map()

    def fit_to_map(self):
        eff_w, eff_h = self.effective_tile_size
        tm = self.editor.tilemap
        ox, oy = tm.offset
        map_w, map_h = tm.map_size
        world_min_x = ox * eff_w
        world_max_x = (ox + map_w) * eff_w
        world_min_y = oy * eff_h
        world_max_y = (oy + map_h) * eff_h
        world_w = max(1, world_max_x - world_min_x)
        world_h = max(1, world_max_y - world_min_y)
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

        if self._handle_image_layer_event(event):
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
                    if count:
                        self.editor.notifications.success(f"Autotile complete: {count} tiles updated")
                    else:
                        self.editor.notifications.notify("No tiles updated (Already matched or no groups found)")
                return True

            if event.key == pygame.K_f:
                if is_hovering and self.hover_cell:
                    self.flood_fill_at_hover()
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

                if self.editor.tool_manager.is_active(ToolKind.FILL):
                    if is_hovering and self.hover_cell:
                        self.flood_fill_at_hover()
                    return True

                if is_hovering and not self.is_panning:
                    self.editor.tilemap.capture_history("Place Tile")
                    self.place_tile()
                    return True

            if event.button == 3:
                if is_hovering and self.hover_cell and not self._open_object_properties_if_hit(mouse_pos):
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
            and not self.editor.tool_manager.is_active(ToolKind.FILL)
            and not self.is_panning
        ) and buttons[0] and is_hovering:
            if self.editor.tool_manager.is_active(ToolKind.ERASER):
                self.remove_tile()
            else:
                self.place_tile()
            return True

        return False

    def _tileset_map(self) -> dict:
        """Tileset index -> data map, empty when no tileset widget is live."""
        ts_widget = getattr(self.editor, "tileset_widget", None)
        if ts_widget is None:
            return {}
        return getattr(ts_widget, "tileset_map", {})

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

        if active_layer.layer_type == "image":
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
            autotile_ok = self.editor.autotile_mode and getattr(self.editor, "autotiler", None)
            vg_map: dict = {}
            selected_group: str | None = None
            if autotile_ok:
                vg_map = self.editor.autotiler.variant_to_group
                groups = getattr(self.editor.autotiler, "groups", [])
                gidx = getattr(self.editor.autotiler, "selected_group_idx", -1)
                if 0 <= gidx < len(groups):
                    selected_group = groups[gidx].name

            reassigned: dict[str, int] = {}
            for y_off in range(sel_h_tiles):
                for x_off in range(sel_w_tiles):
                    curr_sx = start_sx + x_off
                    curr_sy = start_sy + y_off
                    variant_id = (curr_sy * sheet_cols) + curr_sx

                    map_x = self.hover_cell[0] + x_off
                    map_y = self.hover_cell[1] + y_off
                    target_pos = (map_x, map_y)

                    tm = self.editor.tilemap
                    ox, oy = tm.offset
                    mw, mh = tm.map_size
                    if not (ox <= map_x < ox + mw and oy <= map_y < oy + mh):
                        continue

                    tile_data: TypeTile = {
                        "pos": target_pos,
                        "ttype": (tileset_index),
                        "variant": variant_id,
                    }

                    if variant_id in tileset_data.tile_properties:
                        tile_data["properties"] = tileset_data.tile_properties[variant_id].copy()

                    if autotile_ok:
                        # Prefer the selected group so a second ruleset reusing
                        # the same tiles can actually be painted; fall back to
                        # the first-group-wins owner map when nothing selected.
                        owner = vg_map.get((tileset_index, variant_id))
                        if selected_group:
                            tile_data["autotile_group"] = selected_group
                            if owner and owner != selected_group:
                                reassigned[owner] = reassigned.get(owner, 0) + 1
                        elif owner:
                            tile_data["autotile_group"] = owner

                    active_layer.set_tile(target_pos, tile_data)

                    if autotile_ok:
                        rules = self.editor.autotiler.rules
                        if rules:
                            active_layer.autotile_at_pos(target_pos, rules)

            if autotile_ok and reassigned:
                total = sum(reassigned.values())
                detail = ", ".join(
                    f"{n} from '{o}'" for o, n in sorted(reassigned.items()))
                notifications = getattr(self.editor, "notifications", None)
                if notifications is not None:
                    try:
                        notifications.notify(
                            f"Reassigned {total} tile(s) to "
                            f"'{selected_group}' ({detail})")
                    except Exception:
                        pass

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
            if (
                tileset_data.animation
                and "frame_w" in tileset_data.animation
                and "frame_h" in tileset_data.animation
            ):
                sel_width = tileset_data.animation["frame_w"]
                sel_height = tileset_data.animation["frame_h"]
            elif (
                tileset_data.animation
                and tileset_data.animation.get("frame_count", 1) > 1
                and tileset_data.surface.get_width() % tileset_data.animation["frame_count"] == 0
            ):
                fc = tileset_data.animation["frame_count"]
                sel_width = tileset_data.surface.get_width() // fc
                sel_height = tileset_data.surface.get_height()
            else:
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

    def flood_fill_at_hover(self) -> bool:
        """Flood fill at the hover cell with the selected brush.

        Shared by the F key and the Fill tool. Returns True if a fill ran.
        """
        if not self.hover_cell:
            return False
        res = self.get_selected_brush()
        if not res:
            return False
        tileset_index, tileset_data, src_rect = res
        if tileset_index is None or not tileset_data or not src_rect:
            # No brush selected (e.g. Fill clicked before picking a tile):
            # no-op instead of crashing on the asserts below.
            return False
        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer or active_layer.layer_type != "tile":
            return False
        self.editor.tilemap.capture_history("Flood Fill")
        tile_w, tile_h = self.tile_size
        sheet_cols = tileset_data.surface.get_width() // tile_w
        variant_id = (src_rect[1] // tile_h * sheet_cols) + (src_rect[0] // tile_w)

        new_data: TypeTile = {
            "ttype": tileset_index,
            "variant": variant_id,
            "pos": (0, 0),
        }
        if self.editor.autotile_mode and getattr(self.editor, "autotiler", None):
            autotiler = self.editor.autotiler
            stamp: str | None = None
            groups = getattr(autotiler, "groups", [])
            gidx = getattr(autotiler, "selected_group_idx", -1)
            if 0 <= gidx < len(groups):
                stamp = groups[gidx].name
            if stamp is None:
                try:
                    stamp = autotiler.variant_to_group.get(
                        (tileset_index, variant_id))
                except Exception:
                    stamp = None
            if stamp:
                new_data["autotile_group"] = stamp
        active_layer.flood_fill(
            self.hover_cell,
            new_data,
            self.editor.tilemap.map_size,
            offset=self.editor.tilemap.offset,
        )
        return True

    def remove_tile(self):
        """Remove tile or object at hover position."""
        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            return

        if active_layer.layer_type == "image":
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
            self.invalidate_bounds_cache()
        else:
            if not self.hover_cell:
                return

            for dy in range(self.eraser_size):
                for dx in range(self.eraser_size):
                    pos = (self.hover_cell[0] + dx, self.hover_cell[1] + dy)
                    active_layer.remove_tile(pos)

                    if self.editor.autotile_mode and getattr(self.editor, "autotiler", None):
                        rules = self.editor.autotiler.rules
                        if rules:
                            active_layer.autotile_at_pos(pos, rules)

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
            rs = self.editor.tilemap.render_scale
            pick_pos = (int(world_pos[0] / rs), int(world_pos[1] / rs)) if rs else world_pos
            for _obj_id, obj in reversed(list(active_layer.get_all_objects().items())):
                area = obj["area"]
                obj_rect = Rect(area["x"], area["y"], area["w"], area["h"])
                if obj_rect.collidepoint(pick_pos):
                    ttype = int(obj["ttype"])
                    variant = obj["variant"]
                    ts_widget.select_tile_by_variant(ttype, variant)
                    return

    def _open_object_properties_if_hit(self, mouse_pos: tuple[int, int]) -> bool:
        """Open the placed object's own properties under the cursor.

        Returns True when an object was hit (event consumed), False otherwise
        so the caller can fall back to the eyedropper behavior.
        """
        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer or active_layer.layer_type != "object":
            return False

        ts_widget = self.editor.tileset_widget
        if not ts_widget:
            return False

        world_pos = self.screen_to_world(mouse_pos)
        rs = self.editor.tilemap.render_scale
        pick_pos = (int(world_pos[0] / rs), int(world_pos[1] / rs)) if rs else world_pos

        for obj_id, obj in reversed(list(active_layer.get_all_objects().items())):
            area = obj["area"]
            obj_rect = Rect(area["x"], area["y"], area["w"], area["h"])
            if obj_rect.collidepoint(pick_pos):
                ts = ts_widget.get_tileset_by_index(int(obj["ttype"]))
                self.editor.context_dispatch.open(
                    PropertyContext(
                        ContextKind.MAP_OBJECT,
                        obj,
                        {
                            "obj_id": obj_id,
                            "layer_name": active_layer.name,
                            "tileset_name": ts.name if ts else None,
                        },
                    )
                )
                return True
        return False

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

            ox, oy = self.editor.tilemap.offset
            map_screen_x = (ox * eff_w - self.scroll_x) * self.zoom_level + self.rect.x
            map_screen_y = (oy * eff_h - self.scroll_y) * self.zoom_level + self.rect.y
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
                if self.show_map_boundary:
                    self._draw_map_boundary(screen)
            else:
                if not hasattr(self, "_last_init_warn") or pygame.time.get_ticks() - self._last_init_warn > 5000:
                    print("DEBUG: Tilemap not initialized, skipping render")
                    self._last_init_warn = pygame.time.get_ticks()

            self._draw_preview(screen)
            self._draw_move_preview(screen)
            self._draw_selection_rect(screen)
            self._draw_active_image_layer_selection(screen)
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
                pygame.draw.rect(screen, COLORS.danger, Rect(sx, sy, sw, sh), 2)
                return
            if self.hover_cell:
                eff_w, eff_h = self.effective_tile_size
                screen_x = (self.hover_cell[0] * eff_w - self.scroll_x) * self.zoom_level + self.rect.x
                screen_y = (self.hover_cell[1] * eff_h - self.scroll_y) * self.zoom_level + self.rect.y
                size_w = int(eff_w * self.eraser_size * self.zoom_level)
                size_h = int(eff_h * self.eraser_size * self.zoom_level)
                dest_rect = Rect(screen_x, screen_y, size_w, size_h)
                pygame.draw.rect(screen, COLORS.danger, dest_rect, 2)
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
            pygame.draw.rect(screen, COLORS.warning, dest_rect, 2)

            try:
                sub_x, sub_y, sub_w, sub_h = src_rect[0], src_rect[1], src_rect[2], src_rect[3]
                if tileset_data.animation:
                    anim = tileset_data.animation
                    duration = anim.get("frame_duration_ms", 200)
                    fc = anim.get("frame_count", 1)
                    if duration > 0 and fc > 1:
                        frame_idx = int(pygame.time.get_ticks() / duration) % fc
                        if tileset_data.tileset_type == "object":
                            sheet_w = tileset_data.surface.get_width()
                            cols = max(1, sheet_w // sub_w) if sub_w > 0 else 1
                            sub_x = (frame_idx % cols) * sub_w
                            sub_y = (frame_idx // cols) * sub_h
                        else:
                            stride = anim.get("frame_stride", 1)
                            sheet_cols = max(1, tileset_data.surface.get_width() // tile_w) if tile_w > 0 else 1
                            var = ((sub_y // tile_h) * sheet_cols) + (sub_x // tile_w)
                            var += frame_idx * stride
                            sub_x = (var % sheet_cols) * tile_w
                            sub_y = (var // sheet_cols) * tile_h

                sub_r = Rect(sub_x, sub_y, sub_w, sub_h)
                if tileset_data.surface.get_rect().contains(sub_r):
                    tile_surf = tileset_data.surface.subsurface(sub_r)
                    if self.zoom_level != 1.0 or rs != 1.0:
                        tile_surf = pygame.transform.scale(tile_surf, (sel_width, sel_height))
                    tile_surf.set_alpha(128)
                    screen.blit(tile_surf, (screen_x, screen_y))
            except (ValueError, pygame.error):
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
        ox, oy = self.editor.tilemap.offset
        map_w, map_h = self.editor.tilemap.map_size

        boundary = Rect(
            self.rect.x + (ox * eff_w - self.scroll_x) * self.zoom_level,
            self.rect.y + (oy * eff_h - self.scroll_y) * self.zoom_level,
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

        # Draw grid coordinates at corners if zoom is reasonable
        if self.zoom_level >= 0.5:
            font_size = max(10, int(12 * self.zoom_level))
            coord_font = FONTS.get_font(font_size)
            coord_color = (100, 200, 255)
            bg_color = (0, 0, 0, 180)

            # Top-left corner
            if self.rect.collidepoint(boundary.topleft):
                coord_text = f"({ox}, {oy})"
                text_surf = coord_font.render(coord_text, True, coord_color)
                bg_surf = pygame.Surface(
                    (text_surf.get_width() + 4, text_surf.get_height() + 2),
                    pygame.SRCALPHA,
                )
                bg_surf.fill(bg_color)
                text_pos = (boundary.left + 4, boundary.top + 4)
                screen.blit(bg_surf, text_pos)
                screen.blit(text_surf, (text_pos[0] + 2, text_pos[1] + 1))

            # Bottom-right corner
            end_x = ox + map_w
            end_y = oy + map_h
            br_point = (boundary.right, boundary.bottom)
            if self.rect.collidepoint(br_point):
                coord_text = f"({end_x}, {end_y})"
                text_surf = coord_font.render(coord_text, True, coord_color)
                bg_surf = pygame.Surface(
                    (text_surf.get_width() + 4, text_surf.get_height() + 2),
                    pygame.SRCALPHA,
                )
                bg_surf.fill(bg_color)
                text_pos = (
                    boundary.right - text_surf.get_width() - 6,
                    boundary.bottom - text_surf.get_height() - 6,
                )
                screen.blit(bg_surf, text_pos)
                screen.blit(text_surf, (text_pos[0] + 2, text_pos[1] + 1))


    def _draw_status_bar(self, screen):
        bar_h = 25
        bar_rect = Rect(0, self.editor.height - bar_h, self.editor.width, bar_h)
        pygame.draw.rect(screen, COLORS.header, bar_rect)
        pygame.draw.line(screen, COLORS.border_soft, (0, bar_rect.y), (self.editor.width, bar_rect.y))

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
        elif self.editor.tool_manager.is_active(ToolKind.FILL):
            parts.append("Tool: Fill")
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
        txt = self.font_status.render(status_text, True, COLORS.text_dim)
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

        tileset_map = self._tileset_map()

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

            if layer.layer_type == "image":
                self._render_image_layer(layer_surf, layer, draw_offset_x, draw_offset_y)

            elif layer.layer_type == "tile":
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

                    anim = obj.get("animation") or tileset_data.animation
                    frame_idx = 0
                    if anim and anim.get("enabled", True):
                        duration = anim.get("frame_duration_ms", 200)
                        speed = float(anim.get("speed", 1.0))
                        if speed > 0:
                            duration = max(1, int(duration / speed))
                        frame_count = int(anim.get("frame_count", 1))
                        if duration > 0 and frame_count > 1:
                            frame_ms = pygame.time.get_ticks()
                            frame_idx = int(frame_ms / duration) % frame_count
                            if anim.get("animation_mode") == "random_start_times" or anim.get("random_phase"):
                                phase = hash((obj_x, obj_y, ttype, str(_obj_id))) % frame_count
                                frame_idx = (frame_idx + phase) % frame_count

                            custom_frames = anim.get("frames")
                            if isinstance(custom_frames, list) and len(custom_frames) > 0:
                                try:
                                    frame_idx = int(custom_frames[frame_idx % len(custom_frames)])
                                except (ValueError, TypeError):
                                    pass

                    if tileset_data.tileset_type == "object":
                        sheet_w = base_surf.get_width()
                        cols = max(1, sheet_w // obj_w) if obj_w > 0 else 1
                        src_x = (frame_idx % cols) * obj_w
                        src_y = (frame_idx // cols) * obj_h
                        src_rect = Rect(src_x, src_y, obj_w, obj_h)
                    else:
                        sheet_w = base_surf.get_width()
                        sheet_cols = max(1, sheet_w // tile_w) if tile_w > 0 else 1
                        stride = anim.get("frame_stride", 1) if anim else 1
                        eff_var = variant_id + (frame_idx * stride)
                        src_x = (eff_var % sheet_cols) * tile_w
                        src_y = (eff_var // sheet_cols) * tile_h
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

    def _get_image_surface(self, image_path: str | None) -> Surface | None:
        if not image_path:
            return None
        if image_path not in self._image_cache:
            try:
                self._image_cache[image_path] = pygame.image.load(image_path).convert_alpha()
            except (pygame.error, OSError):
                self._image_cache[image_path] = None
        return self._image_cache[image_path]

    def _image_screen_rect(self, image_rect: dict[str, int]) -> Rect:
        rs = self.editor.tilemap.render_scale
        sx = (image_rect["x"] * rs - self.scroll_x) * self.zoom_level + self.rect.x
        sy = (image_rect["y"] * rs - self.scroll_y) * self.zoom_level + self.rect.y
        sw = image_rect["w"] * rs * self.zoom_level
        sh = image_rect["h"] * rs * self.zoom_level
        return Rect(int(sx), int(sy), max(1, int(sw)), max(1, int(sh)))

    def _render_image_layer(self, layer_surf: Surface, layer, draw_offset_x: int, draw_offset_y: int) -> None:
        image_rect = layer.image_rect
        if not image_rect:
            return
        try:
            rect = self._image_screen_rect(image_rect)
        except (KeyError, TypeError):
            return
        rect.move_ip(draw_offset_x, draw_offset_y)
        image = self._get_image_surface(layer.image_path)
        if image is None:
            pygame.draw.rect(layer_surf, COLORS.danger, rect, 2)
            pygame.draw.line(layer_surf, COLORS.danger, rect.topleft, rect.bottomright, 2)
            pygame.draw.line(layer_surf, COLORS.danger, rect.topright, rect.bottomleft, 2)
            label = self.font_status.render("Missing image", True, COLORS.danger)
            layer_surf.blit(label, (rect.x + 4, rect.y + 4))
            return

        if image.get_size() == rect.size:
            layer_surf.blit(image, rect)
        else:
            cache_key = (id(layer), rect.size, layer.image_path)
            scaled = self._scaled_image_cache.get(cache_key)
            if scaled is None or scaled.get_size() != rect.size:
                scaled = pygame.transform.scale(image, rect.size)
                # invalidate old sizes for this layer to avoid unbounded growth
                # keep at most one scaled entry per layer (latest size)
                for k in list(self._scaled_image_cache.keys()):
                    if k[0] == id(layer):
                        self._scaled_image_cache.pop(k, None)
                self._scaled_image_cache[cache_key] = scaled
            layer_surf.blit(scaled, rect)

    def _active_image_layer(self):
        layer = self.editor.tilemap.layer_manager.get_active_layer()
        if (
            layer
            and layer.layer_type == "image"
            and isinstance(layer.image_rect, dict)
            and all(k in layer.image_rect for k in ("x", "y", "w", "h"))
        ):
            return layer
        return None

    def _draw_active_image_layer_selection(self, screen: Surface) -> None:
        layer = self._active_image_layer()
        if not layer or not self.editor.tool_manager.is_active(ToolKind.SELECT):
            return
        try:
            rect = self._image_screen_rect(layer.image_rect)
        except (KeyError, TypeError):
            return
        color = COLORS.accent if not layer.locked else COLORS.text_muted
        pygame.draw.rect(screen, color, rect, max(1, int(2 * self.zoom_level)))
        if not layer.locked:
            self._draw_image_handles(screen, rect, color)

    def _draw_image_handles(self, screen: Surface, rect: Rect, color) -> None:
        hsize = max(4, int(6 * self.zoom_level))
        for px, py in self._image_handle_points(rect):
            handle_rect = Rect(px - hsize, py - hsize, hsize * 2, hsize * 2)
            pygame.draw.rect(screen, COLORS.text, handle_rect)
            pygame.draw.rect(screen, color, handle_rect, 1)

    @staticmethod
    def _image_handle_points(rect: Rect) -> list[tuple[int, int]]:
        return [
            (rect.left, rect.top), (rect.centerx, rect.top), (rect.right, rect.top),
            (rect.left, rect.centery), (rect.right, rect.centery),
            (rect.left, rect.bottom), (rect.centerx, rect.bottom),
            (rect.right, rect.bottom),
        ]

    def _get_image_handle_at(self, image_rect: dict[str, int], screen_pos) -> str | None:
        rect = self._image_screen_rect(image_rect)
        hs = max(4, int(6 * self.zoom_level))
        d = hs * 2
        handles = {
            "tl": Rect(rect.left - hs, rect.top - hs, d, d),
            "t": Rect(rect.centerx - hs, rect.top - hs, d, d),
            "tr": Rect(rect.right - hs, rect.top - hs, d, d),
            "l": Rect(rect.left - hs, rect.centery - hs, d, d),
            "r": Rect(rect.right - hs, rect.centery - hs, d, d),
            "bl": Rect(rect.left - hs, rect.bottom - hs, d, d),
            "b": Rect(rect.centerx - hs, rect.bottom - hs, d, d),
            "br": Rect(rect.right - hs, rect.bottom - hs, d, d),
        }
        for name, handle_rect in handles.items():
            if handle_rect.collidepoint(screen_pos):
                return name
        return None

    def _screen_to_image_world(self, screen_pos) -> tuple[float, float]:
        wx, wy = self._screen_to_world_float(screen_pos)
        rs = self.editor.tilemap.render_scale
        return (wx / rs, wy / rs) if rs else (wx, wy)

    def _clear_image_drag(self, restore: bool = False) -> None:
        layer = self._active_image_layer()
        if restore and layer and self._image_original_rect:
            layer.image_rect = dict(self._image_original_rect)
        self._image_drag_state = None
        self._image_drag_handle = None
        self._image_original_rect = None
        self._image_drag_start = None
        self._image_history_pending = False

    def _finish_image_drag(self) -> None:
        self._clear_image_drag()

    def _update_image_resize(self, layer, point: tuple[float, float]) -> None:
        original = self._image_original_rect
        handle = self._image_drag_handle
        if not original or not handle:
            return
        min_size = 8
        left, top = original["x"], original["y"]
        right = left + original["w"]
        bottom = top + original["h"]
        px, py = int(point[0]), int(point[1])
        if "l" in handle:
            left = min(px, right - min_size)
        if "r" in handle:
            right = max(px, left + min_size)
        if "t" in handle:
            top = min(py, bottom - min_size)
        if "b" in handle:
            bottom = max(py, top + min_size)
        layer.image_rect = {"x": left, "y": top, "w": right - left, "h": bottom - top}

    def _handle_image_layer_event(self, event: pygame.event.Event) -> bool:
        layer = self._active_image_layer()
        if not layer:
            return False
        mouse_pos = pygame.mouse.get_pos()
        is_hovering = self.rect.collidepoint(mouse_pos)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and self._image_drag_state:
                self._clear_image_drag(restore=True)
                return True
            if event.key in (pygame.K_f, pygame.K_q, pygame.K_DELETE, pygame.K_BACKSPACE):
                return True
            mods = pygame.key.get_mods()
            if event.key in (pygame.K_a, pygame.K_c, pygame.K_x, pygame.K_v) and (
                mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL | pygame.KMOD_LMETA | pygame.KMOD_RMETA)
            ):
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and is_hovering:
            if self._is_pan_event(event):
                return False
            if self.editor.tool_manager.is_active(ToolKind.SELECT):
                if layer.locked:
                    return True
                try:
                    handle = self._get_image_handle_at(layer.image_rect, mouse_pos)
                    rect = self._image_screen_rect(layer.image_rect)
                except (KeyError, TypeError):
                    return True
                if handle or rect.collidepoint(mouse_pos):
                    self._image_drag_state = "resizing" if handle else "moving"
                    self._image_drag_handle = handle
                    self._image_original_rect = dict(layer.image_rect)
                    self._image_drag_start = self._screen_to_image_world(mouse_pos)
                return True
            if not self.editor.tool_manager.is_active(ToolKind.SELECT):
                self.editor.notifications.notify(
                    "Image layers are edited with Select and Replace Image…",
                    duration=2.0,
                )
                return True

        if event.type == pygame.MOUSEMOTION and self._image_drag_state:
            if not self._image_history_pending:
                self.editor.tilemap.capture_history("Edit Image Layer")
                self._image_history_pending = True
            if self._image_drag_state == "moving" and self._image_original_rect and self._image_drag_start:
                px, py = self._screen_to_image_world(mouse_pos)
                sx, sy = self._image_drag_start
                layer.image_rect = {
                    **self._image_original_rect,
                    "x": int(self._image_original_rect["x"] + px - sx),
                    "y": int(self._image_original_rect["y"] + py - sy),
                }
            elif self._image_drag_state == "resizing":
                self._update_image_resize(layer, self._screen_to_image_world(mouse_pos))
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._image_drag_state:
            self._finish_image_drag()
            return True

        return event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and is_hovering

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
        if not visible:
            # Viewer closed: no ghost rects on the canvas.
            return
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

        tileset_map = self._tileset_map()

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
