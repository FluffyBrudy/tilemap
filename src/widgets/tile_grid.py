import pygame
from typing import TYPE_CHECKING, Optional, Tuple, cast
from pygame import KEYDOWN, Rect, Surface, K_UP, K_DOWN, K_LEFT, K_RIGHT

from ttypes import TOffset
from ttypes.tilemap import TypeTile

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
        tileset_data = ts_widget.tilesets[tileset_index]
        tile_rect = ts_widget.selected_tile
        return tileset_index, tileset_data, tile_rect

    def place_tile(self):
        if not self.hover_cell:
            return

        res = self.get_selected_brush()
        if not res:
            return

        tileset_index, tileset_data, src_rect = res
        if tileset_index is None or not tileset_data or not src_rect:
            return

        sheet_width = tileset_data.surface.get_width()
        tile_w, tile_h = self.tile_size
        sheet_cols = sheet_width // tile_w

        sel_w_tiles = src_rect[2] // tile_w
        sel_h_tiles = src_rect[3] // tile_h

        start_sx = src_rect[0] // tile_w
        start_sy = src_rect[1] // tile_h

        for y_off in range(sel_h_tiles):
            for x_off in range(sel_w_tiles):
                curr_sx = start_sx + x_off
                curr_sy = start_sy + y_off
                variant_id = (curr_sy * sheet_cols) + curr_sx

                map_x = self.hover_cell[0] + x_off
                map_y = self.hover_cell[1] + y_off
                target_pos = (map_x, map_y)

                tile_data = {
                    "pos": target_pos,
                    "ttype": int(tileset_index),
                    "variant": variant_id,
                }

                self.editor.tilemap.ongrid_tiles[target_pos] = cast(TypeTile, tile_data)

    def remove_tile(self):
        if self.hover_cell and self.hover_cell in self.editor.tilemap.ongrid_tiles:
            del self.editor.tilemap.ongrid_tiles[self.hover_cell]

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
        if not self.hover_cell:
            return

        res = self.get_selected_brush()
        if not res:
            return
        _, tileset_data, src_rect = res
        if not tileset_data or not src_rect:
            return

        tile_w, tile_h = self.tile_size

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

        for x in range(start_col, end_col):
            for y in range(start_row, end_row):
                location = (x, y)

                if location in tilemap.ongrid_tiles:
                    tile = tilemap.ongrid_tiles[location]
                    ttype = tile["ttype"]

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

                    surface.blit(base_surf, (dest_x, dest_y), area=src_rect)
