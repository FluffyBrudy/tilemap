import pygame
from pygame import Surface, Rect, Color
from typing import TYPE_CHECKING, List, Tuple, Set, Optional
import time

if TYPE_CHECKING:
    from editor import Editor

WINDOW_BG = (40, 44, 52)
PANEL_BG = (33, 37, 43)
BORDER_COLOR = (24, 26, 31)
HEADER_COLOR = (44, 132, 250)
TEXT_COLOR = (220, 220, 220)
HIGHLIGHT_COLOR = (65, 70, 80)
GRID_ACTIVE = (152, 195, 121)
GRID_INACTIVE = (60, 64, 72)
GRID_CENTER = (97, 175, 239)


class AutotileRule:
    def __init__(
        self,
        name: str,
        neighbors: Set[Tuple[int, int]],
        tileset_path: str,
        variant_ids: List[int],
        surface_subsurface: Surface = None,
    ):
        self.name = name
        self.neighbors = neighbors
        self.tileset_path = tileset_path
        self.variant_ids = variant_ids
        self.preview_surf = surface_subsurface

    def to_dict(self):
        return {
            "name": self.name,
            "neighbors": [list(p) for p in self.neighbors],
            "tileset_path": self.tileset_path,
            "variant_ids": self.variant_ids,
        }


class AutotileRuleDesigner:
    def __init__(self, editor: "Editor", x: int, y: int):
        self.editor = editor
        self.rect = Rect(x, y, 600, 450)
        self.header_height = 30

        self.visible = False
        self.is_dragging = False
        self.drag_offset = (0, 0)

        self.rules: List[AutotileRule] = []
        self.selected_rule_index: int = -1

        self.current_neighbors: Set[Tuple[int, int]] = set()

        self.current_variant_ids: List[int] = []

        self.current_tileset_path: str = ""

        self.current_preview_surfs: List[Surface] = []

        self._last_editor_selection: Tuple[Optional[str], Tuple[int, int, int, int]] = (
            None,
            (0, 0, 0, 0),
        )

        self.grid_cols = 3
        self.grid_rows = 3
        self.cell_size = 32

        self.font = pygame.font.SysFont("Arial", 12)
        self.title_font = pygame.font.SysFont("Arial", 14, bold=True)

        self._update_layout()

    def _update_layout(self):
        self.close_btn_rect = Rect(
            self.rect.right - 30, self.rect.y, 30, self.header_height
        )
        body_y = self.rect.y + self.header_height
        body_h = self.rect.height - self.header_height
        sidebar_w = 200

        self.list_area = Rect(self.rect.x, body_y, sidebar_w, body_h)
        self.edit_area = Rect(
            self.rect.x + sidebar_w, body_y, self.rect.width - sidebar_w, body_h
        )

        btn_y = self.edit_area.bottom - 40
        btn_w = 80
        cx = self.edit_area.centerx
        self.save_btn_rect = Rect(cx - btn_w - 5, btn_y, btn_w, 30)
        self.delete_btn_rect = Rect(cx + 5, btn_y, btn_w, 30)
        self.new_btn_rect = Rect(
            self.list_area.x + 10,
            self.list_area.bottom - 40,
            self.list_area.width - 20,
            30,
        )

    def _get_grid_start_pos(self):
        center_x = self.edit_area.centerx
        center_y = self.edit_area.y + 150
        total_w = self.grid_cols * self.cell_size
        total_h = self.grid_rows * self.cell_size
        start_x = center_x - total_w // 2
        start_y = center_y - total_h // 2
        return start_x, start_y

    def show(self):
        self.visible = True
        self._sync_last_editor_state()

    def hide(self):
        self.visible = False
        self.is_dragging = False

    def handle_event(self, event) -> bool:
        if not self.visible:
            return False

        mouse_pos = pygame.mouse.get_pos()
        self._update_preview_from_selector()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                header_rect = Rect(
                    self.rect.x, self.rect.y, self.rect.width, self.header_height
                )
                if self.close_btn_rect.collidepoint(mouse_pos):
                    self.hide()
                    return True
                elif header_rect.collidepoint(mouse_pos):
                    self.is_dragging = True
                    self.drag_offset = (
                        mouse_pos[0] - self.rect.x,
                        mouse_pos[1] - self.rect.y,
                    )
                    return True

                if self.list_area.collidepoint(mouse_pos):
                    self._handle_list_click(mouse_pos)
                    return True
                if self.edit_area.collidepoint(mouse_pos):
                    if self._handle_grid_click(mouse_pos):
                        return True

                if self.save_btn_rect.collidepoint(mouse_pos):
                    self._save_current_rule()
                    return True
                if self.new_btn_rect.collidepoint(mouse_pos):
                    self._reset_selection()
                    return True
                if self.delete_btn_rect.collidepoint(mouse_pos):
                    self._delete_current_rule()
                    return True

        elif event.type == pygame.MOUSEBUTTONUP:
            self.is_dragging = False

        elif event.type == pygame.MOUSEMOTION:
            if self.is_dragging:
                self.rect.x = mouse_pos[0] - self.drag_offset[0]
                self.rect.y = mouse_pos[1] - self.drag_offset[1]
                self._update_layout()
                return True

        if not self.rect.collidepoint(mouse_pos) and not self.is_dragging:
            return False

        return True

    def _sync_last_editor_state(self):
        tile_selector = getattr(self.editor, "tileset_widget", None)
        if tile_selector and tile_selector.selected_tile:
            ts = tile_selector.get_active_tile()
            if ts:
                self._last_editor_selection = (
                    str(ts.path),
                    tile_selector.selected_tile,
                )

    def _update_preview_from_selector(self):
        """
        Calculates all variant IDs inside the selection rectangle.
        """
        tile_selector = getattr(self.editor, "tileset_widget", None)
        if tile_selector and tile_selector.selected_tile:
            ts = tile_selector.get_active_tile()
            if ts:
                current_rect = tile_selector.selected_tile
                current_path = str(ts.path)

                current_state = (current_path, current_rect)
                if current_state != self._last_editor_selection:
                    self._last_editor_selection = current_state

                    self.current_tileset_path = current_path
                    self.current_variant_ids = []
                    self.current_preview_surfs = []

                    tile_w, tile_h = self.editor.tilemap.tile_size
                    sheet_cols = ts.surface.get_width() // tile_w

                    rx, ry, rw, rh = current_rect

                    cols_sel = rw // tile_w
                    rows_sel = rh // tile_h

                    start_cx = rx // tile_w
                    start_cy = ry // tile_h

                    for r in range(rows_sel):
                        for c in range(cols_sel):
                            abs_c = start_cx + c
                            abs_r = start_cy + r
                            vid = (abs_r * sheet_cols) + abs_c
                            self.current_variant_ids.append(vid)

                            sub_rect = Rect(
                                abs_c * tile_w, abs_r * tile_h, tile_w, tile_h
                            )
                            try:
                                sub = ts.surface.subsurface(sub_rect).copy()
                                self.current_preview_surfs.append(sub)
                            except:
                                pass

    def _handle_grid_click(self, mouse_pos):
        start_x, start_y = self._get_grid_start_pos()
        rel_x = mouse_pos[0] - start_x
        rel_y = mouse_pos[1] - start_y
        total_w = self.grid_cols * self.cell_size
        total_h = self.grid_rows * self.cell_size

        if 0 <= rel_x < total_w and 0 <= rel_y < total_h:
            col = rel_x // self.cell_size
            row = rel_y // self.cell_size
            center_c = self.grid_cols // 2
            center_r = self.grid_rows // 2
            ox = col - center_c
            oy = row - center_r

            if ox == 0 and oy == 0:
                return False

            if (ox, oy) in self.current_neighbors:
                self.current_neighbors.remove((ox, oy))
            else:
                self.current_neighbors.add((ox, oy))
            return True
        return False

    def _handle_list_click(self, mouse_pos):
        if self.new_btn_rect.collidepoint(mouse_pos):
            self._reset_selection()
            return

        start_y = self.list_area.y + 10
        item_h = 25
        for i, rule in enumerate(self.rules):
            item_rect = Rect(
                self.list_area.x + 5,
                start_y + i * item_h,
                self.list_area.width - 10,
                item_h,
            )
            if item_rect.collidepoint(mouse_pos):
                self.selected_rule_index = i
                self._load_rule_to_editor(rule)
                break

    def _load_rule_to_editor(self, rule: AutotileRule):
        self.current_neighbors = set(rule.neighbors)
        self.current_variant_ids = rule.variant_ids
        self.current_tileset_path = rule.tileset_path

        self.current_preview_surfs = []

        if rule.preview_surf:
            self.current_preview_surfs.append(rule.preview_surf)

        self._sync_last_editor_state()

    def _reset_selection(self):
        self.selected_rule_index = -1
        self.current_neighbors = set()
        self._sync_last_editor_state()

    def _save_current_rule(self):
        if not self.current_tileset_path or not self.current_variant_ids:
            return

        preview = self.current_preview_surfs[0] if self.current_preview_surfs else None

        name = f"Rule {len(self.rules) + 1}"

        if len(self.current_variant_ids) > 1:
            name += f" ({len(self.current_variant_ids)} vars)"

        if self.selected_rule_index >= 0:
            r = self.rules[self.selected_rule_index]
            r.neighbors = set(self.current_neighbors)
            r.variant_ids = list(self.current_variant_ids)
            r.tileset_path = self.current_tileset_path
            r.preview_surf = preview
        else:
            new_rule = AutotileRule(
                name,
                set(self.current_neighbors),
                self.current_tileset_path,
                list(self.current_variant_ids),
                preview,
            )
            self.rules.append(new_rule)
            self.selected_rule_index = len(self.rules) - 1

        for rule in self.rules:
            print(rule.to_dict())

    def _delete_current_rule(self):
        if 0 <= self.selected_rule_index < len(self.rules):
            self.rules.pop(self.selected_rule_index)
            self._reset_selection()

    def draw(self, screen: Surface):
        if not self.visible:
            return

        pygame.draw.rect(screen, WINDOW_BG, self.rect)
        pygame.draw.rect(screen, BORDER_COLOR, self.rect, 1)

        pygame.draw.rect(
            screen,
            HEADER_COLOR,
            Rect(self.rect.x, self.rect.y, self.rect.width, self.header_height),
        )
        title = self.title_font.render("Autotile Designer", True, Color("white"))
        screen.blit(title, (self.rect.x + 10, self.rect.y + 5))

        pygame.draw.rect(screen, (200, 60, 60), self.close_btn_rect)
        x_lbl = self.title_font.render("X", True, Color("white"))
        screen.blit(x_lbl, (self.close_btn_rect.x + 10, self.close_btn_rect.y + 5))

        pygame.draw.rect(screen, PANEL_BG, self.list_area)

        self._draw_rule_list(screen)
        self._draw_grid_editor(screen)

    def _draw_rule_list(self, screen):
        pygame.draw.rect(
            screen,
            (70, 130, 180) if self.selected_rule_index == -1 else (60, 60, 60),
            self.new_btn_rect,
            border_radius=4,
        )
        txt = self.font.render("New Rule", True, TEXT_COLOR)
        screen.blit(txt, (self.new_btn_rect.x + 10, self.new_btn_rect.y + 8))

        start_y = self.list_area.y + 10
        item_h = 25
        for i, rule in enumerate(self.rules):
            r = Rect(
                self.list_area.x + 5,
                start_y + i * item_h,
                self.list_area.width - 10,
                item_h,
            )
            if i == self.selected_rule_index:
                pygame.draw.rect(screen, HIGHLIGHT_COLOR, r, border_radius=3)

            d_name = rule.name if len(rule.name) < 20 else rule.name[:17] + ".."
            screen.blit(self.font.render(d_name, True, TEXT_COLOR), (r.x + 5, r.y + 5))

    def _draw_grid_editor(self, screen):
        center_x = self.edit_area.centerx

        if self.current_preview_surfs:
            idx = 0
            if len(self.current_preview_surfs) > 1:
                idx = int(time.time() * 2) % len(self.current_preview_surfs)

            p_surf = self.current_preview_surfs[idx]
            scaled = pygame.transform.scale(p_surf, (64, 64))
            screen.blit(scaled, (center_x - 32, self.edit_area.y + 40))

            if len(self.current_preview_surfs) > 1:
                count_txt = self.font.render(
                    f"x{len(self.current_preview_surfs)}", True, (255, 255, 0)
                )
                screen.blit(count_txt, (center_x + 35, self.edit_area.y + 85))

        start_x, start_y = self._get_grid_start_pos()
        center_c = self.grid_cols // 2
        center_r = self.grid_rows // 2

        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                cx = start_x + c * self.cell_size
                cy = start_y + r * self.cell_size
                cell = Rect(cx, cy, self.cell_size, self.cell_size)

                ox = c - center_c
                oy = r - center_r

                color = GRID_INACTIVE
                if ox == 0 and oy == 0:
                    color = GRID_CENTER
                elif (ox, oy) in self.current_neighbors:
                    color = GRID_ACTIVE

                pygame.draw.rect(screen, color, cell)
                pygame.draw.rect(screen, (30, 30, 30), cell, 1)

        pygame.draw.rect(screen, (70, 180, 70), self.save_btn_rect, border_radius=4)
        s_lbl = self.font.render("Save", True, Color("white"))
        screen.blit(s_lbl, (self.save_btn_rect.x + 25, self.save_btn_rect.y + 8))

        if self.selected_rule_index != -1:
            pygame.draw.rect(
                screen, (180, 70, 70), self.delete_btn_rect, border_radius=4
            )
            d_lbl = self.font.render("Del", True, Color("white"))
            screen.blit(
                d_lbl, (self.delete_btn_rect.x + 25, self.delete_btn_rect.y + 8)
            )
