import pygame
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
from pathlib import Path
from pygame import Rect, Surface

from utils.validation import is_image_multipleof

if TYPE_CHECKING:
    from editor import Editor


class TilesetData:
    def __init__(self, name: str, path: Path, surface: pygame.Surface):
        self.name = name
        self.path = path
        self.surface = surface
        self.offset = [0, 0]


class TileSelector:
    def __init__(self, editor: "Editor", x: int, y: int, w: int, h: int):
        self.editor = editor
        self.rect = Rect(x, y, w, h)

        self.tilesets: List[TilesetData] = []
        self.tileset_map: Dict[str, TilesetData] = {}
        self.active_idx = -1

        self.top_bar_h = 30
        self.btm_bar_h = 40
        self.view_rect = Rect(
            x, y + self.top_bar_h, w, h - self.top_bar_h - self.btm_bar_h
        )

        self.is_panning = False
        self.pan_start = (0, 0)
        self.pan_start_offset = (0, 0)

        self.is_selecting = False
        self.selection_start_grid: Optional[Tuple[int, int]] = None
        self.hover_pos: Optional[Tuple[int, int]] = None

        self.selected_tile: Optional[Tuple[int, int, int, int]] = None

        btn_y = y + h - 35
        self.btn_add = Rect(x + w - 70, btn_y, 30, 30)
        self.btn_rem = Rect(x + w - 35, btn_y, 30, 30)
        self.font = pygame.font.SysFont("Arial", 16)

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse_pos = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.view_rect.collidepoint(mouse_pos) and self.active_idx != -1:
                self.is_panning = True
                self.pan_start = mouse_pos
                self.pan_start_offset = tuple(self.tilesets[self.active_idx].offset)
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
            if self.btn_add.collidepoint(mouse_pos):
                self.request_add_tileset()
                return True
            if self.btn_rem.collidepoint(mouse_pos):
                self.remove_tileset()
                return True

            if self.rect.collidepoint(mouse_pos) and mouse_pos[1] < self.view_rect.top:
                self.check_tab_click(mouse_pos)
                return True

            if self.view_rect.collidepoint(mouse_pos) and self.active_idx != -1:
                if self.hover_pos:
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

                rel_x = mouse_pos[0] - img_x
                rel_y = mouse_pos[1] - img_y

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

        return False

    def update_selection_rect(self, current_grid: Tuple[int, int]):
        """Calculates the rectangle based on start click and current drag pos."""
        if not self.selection_start_grid:
            return

        start_col, start_row = self.selection_start_grid
        curr_col, curr_row = current_grid

        min_col = min(start_col, curr_col)
        max_col = max(start_col, curr_col)
        min_row = min(start_row, curr_row)
        max_row = max(start_row, curr_row)

        tw, th = self.editor.tilemap.tile_size

        w = (max_col - min_col + 1) * tw
        h = (max_row - min_row + 1) * th

        self.selected_tile = (min_col * tw, min_row * th, w, h)

    def request_add_tileset(self):
        self.editor.open_file_manager(
            on_select=self.on_file_selected,
            initial_dir=Path.cwd(),
            allowed_exts=[".png", ".jpg"],
        )

    def on_file_selected(self, path: Path):
        if path.exists():
            try:
                surf = pygame.image.load(path).convert_alpha()
                if is_image_multipleof(surf.get_size(), self.editor.tilemap.tile_size):
                    tileset_data = TilesetData(path.name, path, surf)
                    self.tilesets.append(tileset_data)
                    self.active_idx = len(self.tilesets) - 1
                    self.tileset_map[str(path)] = tileset_data
                else:
                    raise ValueError("Tileset isnt multiple of tile size")
            except Exception as e:
                print(f"Error loading image: {e}")

    def remove_tileset(self):
        if 0 <= self.active_idx < len(self.tilesets):
            data = self.tilesets.pop(self.active_idx)
            self.tileset_map.pop(str(data.path))
            self.active_idx = max(0, len(self.tilesets) - 1)
            if not self.tilesets:
                self.active_idx = -1
            self.selected_tile = None

    def check_tab_click(self, pos):
        if not self.tilesets:
            return
        tab_w = min(100, self.rect.width // len(self.tilesets))
        idx = (pos[0] - self.rect.x) // tab_w
        if 0 <= idx < len(self.tilesets):
            self.active_idx = int(idx)
            self.selected_tile = None

    def get_active_tile(self):
        if self.active_idx == -1:
            return None
        return self.tilesets[self.active_idx]

    def draw(self, screen: pygame.Surface):
        self.draw_background(screen)
        self.draw_view_area(screen)
        self.draw_buttons(screen)
        self.draw_tabs(screen)

    def draw_background(self, screen: pygame.Surface):
        pygame.draw.rect(screen, (40, 40, 40), self.rect)
        pygame.draw.rect(screen, (100, 100, 100), self.rect, 1)

    def draw_view_area(self, screen: pygame.Surface):
        pygame.draw.rect(screen, (20, 20, 20), self.view_rect)

        if self.active_idx == -1:
            return

        ts = self.tilesets[self.active_idx]

        clip = screen.get_clip()
        screen.set_clip(self.view_rect)

        img_x = self.view_rect.x + ts.offset[0]
        img_y = self.view_rect.y + ts.offset[1]

        self.draw_tileset_image(screen, ts, img_x, img_y)
        self.draw_hover(screen, ts, img_x, img_y)
        self.draw_selection(screen, img_x, img_y)

        screen.set_clip(clip)

        self.draw_tileset_name(screen, ts)

    def draw_tileset_image(self, screen, ts: TilesetData, img_x: int, img_y: int):
        screen.blit(ts.surface, (img_x, img_y))

    def draw_hover(self, screen, ts: TilesetData, img_x: int, img_y: int):
        if self.hover_pos is None:
            return

        tw, th = self.editor.tilemap.tile_size
        col, row = self.hover_pos
        hover_rect = Rect(img_x + col * tw, img_y + row * th, tw, th)
        pygame.draw.rect(screen, (255, 255, 0), hover_rect, 2)

    def draw_selection(self, screen, img_x: int, img_y: int):
        if not self.selected_tile:
            return
        sx, sy, sw, sh = self.selected_tile
        sel_rect = Rect(img_x + sx, img_y + sy, sw, sh)
        pygame.draw.rect(screen, (0, 255, 0), sel_rect, 2)

    def draw_tileset_name(self, screen, ts: TilesetData):
        name_surf = self.font.render(f"{ts.name}", True, (200, 200, 200))
        screen.blit(name_surf, (self.rect.x + 5, self.rect.bottom - 30))

    def draw_buttons(self, screen):
        pygame.draw.rect(screen, (60, 60, 60), self.btn_add)
        pygame.draw.rect(screen, (60, 60, 60), self.btn_rem)
        screen.blit(
            self.font.render("+", True, (255, 255, 255)),
            (self.btn_add.x + 10, self.btn_add.y + 5),
        )
        screen.blit(
            self.font.render("-", True, (255, 255, 255)),
            (self.btn_rem.x + 10, self.btn_rem.y + 5),
        )

    def draw_tabs(self, screen: Surface):
        if not self.tilesets:
            return
        tab_w = min(100, self.rect.width // len(self.tilesets))
        for i, ts in enumerate(self.tilesets):
            r = Rect(self.rect.x + i * tab_w, self.rect.y, tab_w, self.top_bar_h)
            col = (60, 60, 80) if i == self.active_idx else (40, 40, 40)
            pygame.draw.rect(screen, col, r)
            pygame.draw.rect(screen, (100, 100, 100), r, 1)

            t = ts.name[:8] + ".." if len(ts.name) > 10 else ts.name
            screen.blit(self.font.render(t, True, (200, 200, 200)), (r.x + 5, r.y + 5))
