import pygame
from typing import TYPE_CHECKING, Optional, Tuple, cast
from pygame import KEYDOWN, Rect, Surface, K_UP, K_DOWN, K_LEFT, K_RIGHT

from ttypes import TOffset
from ttypes.tilemap import TypeTile, TypeObject

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

    @property
    def tile_size(self):
        return self.editor.tilemap.tile_size

    def screen_to_world(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        wx = pos[0] - self.rect.x + self.scroll_x
        wy = pos[1] - self.rect.y + self.scroll_y
        return wx, wy

    def get_grid_pos(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        wx, wy = self.screen_to_world(pos)
        tile_w, tile_h = self.tile_size
        return int(wx // tile_w), int(wy // tile_h)

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
            if keys[K_DOWN]:
                self.scroll_y += self.scroll_speed

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse_pos = pygame.mouse.get_pos()
        is_hovering = self.rect.collidepoint(mouse_pos)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 2:
                if is_hovering:
                    self.is_panning = True
                    self.pan_start_pos = mouse_pos
                    self.pan_start_scroll = (self.scroll_x, self.scroll_y)
                    return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 2:
                self.is_panning = False
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.is_panning:
                dx = mouse_pos[0] - self.pan_start_pos[0]
                dy = mouse_pos[1] - self.pan_start_pos[1]

                self.scroll_x = self.pan_start_scroll[0] - dx
                self.scroll_y = self.pan_start_scroll[1] - dy
                return True

            if is_hovering:
                self.hover_cell = self.get_grid_pos(mouse_pos)
            else:
                self.hover_cell = None

        buttons = pygame.mouse.get_pressed()

        if (buttons[0] and is_hovering) or (
            event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and is_hovering
        ):
            if not self.is_panning:
                self.place_tile()
                return True

        if (buttons[2] and is_hovering) or (
            event.type == pygame.MOUSEBUTTONDOWN and event.button == 3 and is_hovering
        ):
            if not self.is_panning:
                self.remove_tile()
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

            pixel_x = self.hover_cell[0] * tile_w
            pixel_y = self.hover_cell[1] * tile_h
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
                        "ttype": str(tileset_index),
                        "variant": variant_id,
                    }

                    active_layer.set_tile(target_pos, tile_data)

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
        if not self.hover_cell:
            return

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            return

        if active_layer.layer_type == "object":

            mouse_pos = pygame.mouse.get_pos()
            world_pos = self.screen_to_world(mouse_pos)

            for obj_id, obj in list(active_layer.get_all_objects().items()):
                area = obj["area"]
                obj_x, obj_y = area["x"], area["y"]
                obj_w, obj_h = area["w"], area["h"]

                if (
                    obj_x <= world_pos[0] <= obj_x + obj_w
                    and obj_y <= world_pos[1] <= obj_y + obj_h
                ):
                    active_layer.remove_object(obj_id)
                    break
        else:

            active_layer.remove_tile(self.hover_cell)

    def draw(self, screen: Surface):
        pygame.draw.rect(screen, (20, 20, 20), self.rect)

        clip_rect = self.rect.clip(screen.get_rect())
        prev_clip = screen.get_clip()
        screen.set_clip(clip_rect)

        self.render(screen)

        if self.show_grid:
            self._draw_grid(screen)

        self._draw_preview(screen)

        screen.set_clip(prev_clip)
        pygame.draw.rect(screen, (100, 100, 100), self.rect, 1)

    def _draw_preview(self, screen):
        res = self.get_selected_brush()
        if not res:
            return
        _, tileset_data, src_rect = res
        if not tileset_data or not src_rect:
            return

        active_layer = self.editor.tilemap.layer_manager.get_active_layer()
        if not active_layer:
            return

        tile_w, tile_h = self.tile_size

        if active_layer.layer_type == "object":
            mouse_pos = pygame.mouse.get_pos()
            world_pos = self.screen_to_world(mouse_pos)

            sel_width = src_rect[2]
            sel_height = src_rect[3]

            screen_x = mouse_pos[0]
            screen_y = mouse_pos[1]

            dest_rect = Rect(screen_x, screen_y, sel_width, sel_height)
            pygame.draw.rect(screen, (255, 255, 0), dest_rect, 2)

            try:

                sub_r = Rect(src_rect[0], src_rect[1], sel_width, sel_height)
                tile_surf = tileset_data.surface.subsurface(sub_r)
                tile_surf.set_alpha(128)
                screen.blit(tile_surf, (screen_x, screen_y))
            except ValueError:
                pass
        else:

            if not self.hover_cell:
                return

            sel_w_tiles = src_rect[2] // tile_w
            sel_h_tiles = src_rect[3] // tile_h

            for y_off in range(sel_h_tiles):
                for x_off in range(sel_w_tiles):
                    col = self.hover_cell[0] + x_off
                    row = self.hover_cell[1] + y_off

                    screen_x = self.rect.x - self.scroll_x + (col * tile_w)
                    screen_y = self.rect.y - self.scroll_y + (row * tile_h)

                    dest_rect = Rect(screen_x, screen_y, tile_w, tile_h)

                    pygame.draw.rect(screen, (255, 255, 255), dest_rect, 1)

                    try:
                        tex_x = src_rect[0] + (x_off * tile_w)
                        tex_y = src_rect[1] + (y_off * tile_h)

                        sub_r = Rect(tex_x, tex_y, tile_w, tile_h)

                        tile_surf = tileset_data.surface.subsurface(sub_r)
                        tile_surf.set_alpha(128)
                        screen.blit(tile_surf, dest_rect)
                    except ValueError:
                        pass

    def _draw_grid(self, screen):
        tile_w, tile_h = self.tile_size
        map_w, map_h = self.editor.tilemap.map_size

        start_col = max(0, int(self.scroll_x // tile_w))
        end_col = min(map_w, int((self.scroll_x + self.rect.width) // tile_w) + 1)

        start_row = max(0, int(self.scroll_y // tile_h))
        end_row = min(map_h, int((self.scroll_y + self.rect.height) // tile_h) + 1)

        for col in range(start_col, end_col):
            x = self.rect.x - self.scroll_x + col * tile_w
            pygame.draw.line(
                screen,
                self.grid_color,
                (x, self.rect.y),
                (x, self.rect.y + map_h * tile_h),
            )

        for row in range(start_row, end_row):
            y = self.rect.y - self.scroll_y + row * tile_h
            pygame.draw.line(
                screen,
                self.grid_color,
                (self.rect.x, y),
                (self.rect.x + map_w * tile_w, y),
            )

    def render(self, surface: Surface):
        tilemap = self.editor.tilemap
        if not tilemap.initialized:
            return

        tile_w, tile_h = self.tile_size

        start_col = int(self.scroll_x // tile_w)
        end_col = start_col + (self.rect.width // tile_w) + 2

        start_row = int(self.scroll_y // tile_h)
        end_row = start_row + (self.rect.height // tile_h) + 2

        assert self.editor.tileset_widget is not None
        tileset_map = self.editor.tileset_widget.tileset_map

        rendered_layers = tilemap.layer_manager.get_rendered_layers()

        for layer in rendered_layers:

            if layer.opacity < 1.0:

                layer_surf = pygame.Surface((self.rect.width, self.rect.height))
                layer_surf.fill((20, 20, 20))
                layer_surf.set_colorkey((20, 20, 20))
            else:
                layer_surf = surface

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

                        sheet_cols = sheet_w // tile_w

                        src_x = (variant_id % sheet_cols) * tile_w
                        src_y = (variant_id // sheet_cols) * tile_h
                        src_rect = Rect(src_x, src_y, tile_w, tile_h)

                        dest_x = (x * tile_w) - self.scroll_x + self.rect.x
                        dest_y = (y * tile_h) - self.scroll_y + self.rect.y

                        layer_surf.blit(base_surf, (dest_x, dest_y), area=src_rect)

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

                    sheet_w = base_surf.get_width()
                    sheet_cols = sheet_w // tile_w

                    src_x = (variant_id % sheet_cols) * tile_w
                    src_y = (variant_id // sheet_cols) * tile_h

                    src_rect = Rect(src_x, src_y, obj_w, obj_h)

                    dest_x = obj_x - self.scroll_x + self.rect.x
                    dest_y = obj_y - self.scroll_y + self.rect.y

                    layer_surf.blit(base_surf, (dest_x, dest_y), area=src_rect)

            if layer.opacity < 1.0:
                layer_surf.set_alpha(int(layer.opacity * 255))
                surface.blit(layer_surf, (self.rect.x, self.rect.y))
