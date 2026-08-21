import time
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
from pygame import Rect, Surface

from constants import BASE_PATH
from utils.error_handler import error_handler
from utils.icon_manager import icon_manager

from .autotile_template import AutotileTemplateApplier
from .input import InlineTextInput
from .ui.theme import COLORS, FONTS

if TYPE_CHECKING:
    from editor import Editor

WINDOW_BG = (40, 44, 52)
PANEL_BG = (33, 37, 43)
BORDER_COLOR = (24, 26, 31)
GRID_ACTIVE = (152, 195, 121)
GRID_INACTIVE = (60, 64, 72)
GRID_CENTER = (97, 175, 239)


class AutotileRule:
    def __init__(
        self,
        name: str,
        neighbors: set[tuple[int, int]],
        tileset_path: str = "",
        variant_ids: list[int] | None = None,
        surface_subsurface: Surface | None = None,
        tileset_index: int | None = None,
        group_id: str | None = None,
    ):
        self.name = name
        self.neighbors = neighbors

        self.tileset_path = tileset_path

        self.tileset_index = tileset_index
        self.variant_ids = variant_ids or []
        self.preview_surf: Surface | None = surface_subsurface
        self.group_id = group_id or name

    @staticmethod
    def from_dict(data: dict):
        neighbors = {tuple(n) for n in data["neighbors"]}
        return AutotileRule(
            name=data["name"],
            neighbors=neighbors,
            tileset_path=data.get("tileset_path", ""),
            variant_ids=data.get("variant_ids", [data.get("variant_id", 0)]),
            surface_subsurface=None,
            tileset_index=data.get("tileset_index"),
            group_id=data.get("group_id"),
        )

    def to_dict(self):
        return {
            "name": self.name,
            "neighbors": [list(p) for p in self.neighbors],
            "tileset_path": self.tileset_path,
            "tileset_index": self.tileset_index,
            "variant_ids": self.variant_ids,
            "group_id": self.group_id,
        }


class AutotileGroup:
    def __init__(self, name: str, rules: list[AutotileRule] | None = None):
        self.name = name
        self.rules = rules or []

    def to_dict(self):
        return {
            "name": self.name,
            "rules": [r.to_dict() for r in self.rules],
        }

    @staticmethod
    def from_dict(data: dict):
        return AutotileGroup(
            name=data["name"],
            rules=[AutotileRule.from_dict(r) for r in data.get("rules", [])],
        )


class AutotileRuleDesigner:
    def __init__(self, editor: "Editor", x: int, y: int):
        self.editor = editor
        self.rect = Rect(x, y, 600, 500)
        self.header_height = 30

        self.visible = False
        self.is_dragging = False
        self.drag_offset = (0, 0)

        self.groups: list[AutotileGroup] = [AutotileGroup("Default")]
        self.selected_group_idx: int = 0
        self.selected_rule_index: int = -1

        self.renaming_group_idx: int | None = None
        self.rename_input = InlineTextInput("group_rename", "")

        self.scroll_offset: int = 0
        self.max_visible_rules: int = 6
        self.scroll_bar_rect: Rect | None = None
        self.is_scrollbar_dragging: bool = False

        self.current_neighbors: set[tuple[int, int]] = set()

        self.current_variant_ids: list[int] = []

        self.current_tileset_path: str = ""
        self.current_tileset_index: int | None = None

        self.current_preview_surfs: list[Surface] = []

        self._last_editor_selection: tuple[str | None, tuple[int, int, int, int]] = (
            None,
            (0, 0, 0, 0),
        )

        self.grid_cols = 3
        self.grid_rows = 3
        self.cell_size = 32

        self.font = FONTS.get_font(12)
        self.title_font = FONTS.get_bold_font(14)

        self.template_manager = AutotileTemplateApplier(self)

        self._update_layout()

    def _update_layout(self):
        self.close_btn_rect = Rect(
            self.rect.right - 30, self.rect.y, 30, self.header_height
        )
        body_y = self.rect.y + self.header_height
        body_h = self.rect.height - self.header_height
        sidebar_w = 200
        self.list_area = Rect(self.rect.x, body_y, sidebar_w, body_h)

        button_h = 30
        group_content_h = (body_h // 2) - button_h
        rule_content_h = (body_h // 2) - button_h

        self.group_list_area = Rect(self.rect.x, body_y, sidebar_w, group_content_h)
        self.rule_list_area = Rect(
            self.rect.x, body_y + body_h // 2, sidebar_w, rule_content_h
        )

        self.edit_area = Rect(
            self.rect.x + sidebar_w, body_y, self.rect.width - sidebar_w, body_h
        )

        btn_y = self.edit_area.bottom - 40
        btn_w = 80
        cx = self.edit_area.centerx
        self.save_btn_rect = Rect(cx - btn_w - 5, btn_y, btn_w, 30)
        self.delete_btn_rect = Rect(cx + 5, btn_y, btn_w, 30)

        self.new_group_btn_rect = Rect(
            self.group_list_area.x + 10,
            self.group_list_area.bottom + 5,
            self.group_list_area.width - 20,
            25,
        )
        self.new_rule_btn_rect = Rect(
            self.rule_list_area.x + 10,
            self.rule_list_area.bottom + 5,
            self.rule_list_area.width - 20,
            25,
        )

        self.external_btn_rect = Rect(
            self.edit_area.right - 100,
            self.edit_area.y + 5,
            90,
            25,
        )
        self.template_btn_rect = Rect(
            self.edit_area.right - 100,
            self.edit_area.y + 35,
            90,
            25,
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
        self._last_editor_selection = (None, (0, 0, 0, 0))
        self._update_preview_from_selector()

    def hide(self):
        self.visible = False
        self.is_dragging = False

        if hasattr(self.editor, "tileset_widget"):
            assert self.editor.tileset_widget is not None
            self.editor.tileset_widget.set_rule_hints(set())

    def _push_hints_to_selector(self):
        selector = getattr(self.editor, "tileset_widget", None)
        if not selector:
            return

        active_ts = selector.get_active_tile()
        if not active_ts:
            selector.set_rule_hints(set())
            return
        current_path = str(active_ts.path)
        current_index = selector.active_idx

        hints = set()

        for group in self.groups:
            for rule in group.rules:
                if rule.tileset_index is not None:
                    if rule.tileset_index == current_index:
                        for vid in rule.variant_ids:
                            hints.add(vid)
                else:
                    if rule.tileset_path == current_path:
                        for vid in rule.variant_ids:
                            hints.add(vid)

        selector.set_rule_hints(hints)

    @property
    def rules(self):
        """Flat list of rules across all groups (for backward compatibility)."""
        all_rules = []
        for g in self.groups:
            all_rules.extend(g.rules)
        return all_rules

    @property
    def variant_to_group(self):
        """Map (tileset_index, variant_id) -> group_id from all rules."""
        mapping = {}
        for g in self.groups:
            for rule in g.rules:
                ts_idx = rule.tileset_index
                for vid in rule.variant_ids:
                    key = (ts_idx, vid)
                    if key not in mapping:
                        mapping[key] = g.name
        return mapping

    def handle_event(self, event) -> bool:
        if not self.visible:
            return False

        if self.template_manager.handle_event(event):
            return True

        if self._handle_scroll_event(event):
            return True

        if self._handle_group_rename(event):
            return True

        mouse_pos = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()

        self._update_preview_from_selector()

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.hide()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                header_rect = Rect(
                    self.rect.x, self.rect.y, self.rect.width, self.header_height
                )
                if self.close_btn_rect.collidepoint(mouse_pos):
                    self.hide()
                    return True
                if header_rect.collidepoint(mouse_pos):
                    self.is_dragging = True
                    self.drag_offset = (
                        mouse_pos[0] - self.rect.x,
                        mouse_pos[1] - self.rect.y,
                    )
                    return True

                if self.new_group_btn_rect.collidepoint(mouse_pos):
                    self._create_new_group_with_focus()
                    return True

                if self.new_rule_btn_rect.collidepoint(mouse_pos):
                    self._reset_selection()
                    return True

                if self.group_list_area.collidepoint(mouse_pos):
                    self._handle_group_list_click(mouse_pos)
                    return True

                if self.rule_list_area.collidepoint(mouse_pos):
                    self._handle_rule_list_click(mouse_pos)
                    return True

                if self.edit_area.collidepoint(mouse_pos):
                    if self.save_btn_rect.collidepoint(mouse_pos):
                        self._save_current_rule()
                    elif self.delete_btn_rect.collidepoint(mouse_pos):
                        self._delete_current_rule()
                    elif self.external_btn_rect.collidepoint(mouse_pos):
                        self._launch_external_viewer()
                    elif self.template_btn_rect.collidepoint(mouse_pos):
                        self.template_manager.show_at(mouse_pos)
                    else:
                        self._handle_grid_click(mouse_pos)
                    return True

        elif event.type == pygame.MOUSEBUTTONUP:
            self.is_dragging = False

        elif event.type == pygame.MOUSEMOTION and self.is_dragging:
            self.rect.x = mouse_pos[0] - self.drag_offset[0]
            self.rect.y = mouse_pos[1] - self.drag_offset[1]
            self._update_layout()
            return True

        return self.rect.collidepoint(mouse_pos) or self.is_dragging

    def _sync_last_editor_state(self):
        tile_selector = getattr(self.editor, "tileset_widget", None)
        if tile_selector and tile_selector.selected_tile:
            ts = tile_selector.get_active_tile()
            if ts:
                self._last_editor_selection = (
                    str(ts.path),
                    tile_selector.selected_tile,
                )

                self.current_tileset_index = tile_selector.active_idx

    def _update_preview_from_selector(self):
        tile_selector = getattr(self.editor, "tileset_widget", None)
        if tile_selector and tile_selector.selected_tile:
            ts = tile_selector.get_active_tile()
            if ts:
                current_rect = tile_selector.selected_tile
                current_path = str(ts.path)

                current_state = (current_path, current_rect)
                if current_state != self._last_editor_selection:
                    print(
                        f"DEBUG: Preview updated - path={current_path}, active_idx={tile_selector.active_idx}"
                    )
                    self._last_editor_selection = current_state

                    self.current_tileset_path = current_path
                    self.current_tileset_index = tile_selector.active_idx
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
                            except Exception as e:
                                error_handler.capture(e, context="autotiler_preview")
                    print(f"DEBUG: Variants loaded: {self.current_variant_ids}")

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

    def _handle_group_list_click(self, mouse_pos):
        start_y = self.group_list_area.y + 25
        item_h = 25
        for i, _group in enumerate(self.groups):
            item_rect = Rect(
                self.group_list_area.x + 5,
                start_y + i * item_h,
                self.group_list_area.width - 10,
                item_h,
            )
            if item_rect.collidepoint(mouse_pos):
                self.selected_group_idx = i
                self.selected_rule_index = -1
                self.scroll_offset = 0
                return

    def _handle_rule_list_click(self, mouse_pos):
        if self.selected_group_idx == -1:
            return

        group = self.groups[self.selected_group_idx]
        start_y = self.rule_list_area.y + 25
        item_h = 25

        list_content_area = Rect(
            self.rule_list_area.x,
            self.rule_list_area.y + 25,
            self.rule_list_area.width,
            self.rule_list_area.height - 25,
        )

        if not list_content_area.collidepoint(mouse_pos):
            return

        visible_start = self.scroll_offset
        visible_end = min(visible_start + self.max_visible_rules, len(group.rules))

        for i in range(visible_start, visible_end):
            rule = group.rules[i]
            display_index = i - visible_start
            item_rect = Rect(
                self.rule_list_area.x + 5,
                start_y + display_index * item_h,
                self.rule_list_area.width - 10,
                item_h,
            )
            if item_rect.collidepoint(mouse_pos):
                self.selected_rule_index = i
                self._load_rule_to_editor(rule)
                break

    def _load_rule_to_editor(self, rule: AutotileRule):
        self.current_neighbors = set(rule.neighbors)
        self.current_variant_ids = list(rule.variant_ids)

        self.current_tileset_path = rule.tileset_path
        self.current_tileset_index = rule.tileset_index

        self.current_preview_surfs = []

        if rule.variant_ids and self.current_tileset_index is not None:
            ts_widget = getattr(self.editor, "tileset_widget", None)
            if ts_widget and 0 <= self.current_tileset_index < len(ts_widget.tilesets):
                ts = ts_widget.tilesets[self.current_tileset_index]
                tile_w, tile_h = self.editor.tilemap.tile_size
                sheet_cols = ts.surface.get_width() // tile_w

                for vid in rule.variant_ids:
                    tx = (vid % sheet_cols) * tile_w
                    ty = (vid // sheet_cols) * tile_h
                    try:
                        sub_rect = Rect(tx, ty, tile_w, tile_h)
                        sub = ts.surface.subsurface(sub_rect).copy()
                        self.current_preview_surfs.append(sub)
                    except Exception as e:
                        error_handler.capture(e, context="autotiler_preview")

        elif rule.preview_surf:
            self.current_preview_surfs.append(rule.preview_surf)

        self._sync_last_editor_state()

    def _reset_selection(self):
        self.selected_rule_index = -1
        self.current_neighbors = set()
        self.current_variant_ids = []
        self.current_preview_surfs = []

        self._last_editor_selection = (None, (0, 0, 0, 0))

        self._sync_last_editor_state()

        self._update_preview_from_selector()

    def _get_next_rule_name(self, base_name: str) -> str:
        import re

        match = re.search(r"(.*?)(\d+)$", base_name)
        if match:
            prefix = match.group(1)
            number = int(match.group(2))
            return f"{prefix}{number + 1}"
        return f"{base_name} 2"

    def _save_current_rule(self):
        self._update_preview_from_selector()

        print("\nDEBUG: _save_current_rule called")

        tile_selector = getattr(self.editor, "tileset_widget", None)
        if (
            not self.current_tileset_path or self.current_tileset_index is None
        ) and tile_selector:
            ts = tile_selector.get_active_tile()
            if ts:
                self.current_tileset_path = str(ts.path)
                self.current_tileset_index = tile_selector.active_idx

        if not self.current_tileset_path or not self.current_variant_ids:
            print("DEBUG: Can't save rule - missing tileset or variants")
            return

        if self.selected_group_idx == -1:
            print("DEBUG: Can't save rule - no group selected")
            return

        preview = self.current_preview_surfs[0] if self.current_preview_surfs else None
        current_group = self.groups[self.selected_group_idx]

        if self.selected_rule_index >= 0:
            rule = current_group.rules[self.selected_rule_index]
            rule.neighbors = set(self.current_neighbors)
            rule.variant_ids = list(self.current_variant_ids)
            rule.preview_surf = preview
            rule.tileset_path = self.current_tileset_path
            rule.tileset_index = getattr(self, "current_tileset_index", None)
            rule.group_id = current_group.name
            print(f"Rule updated: {rule.name} in Group {current_group.name}")
        else:
            base_name = f"Rule {len(current_group.rules) + 1}"
            while any(r.name == base_name for r in current_group.rules):
                base_name = self._get_next_rule_name(base_name)

            new_rule = AutotileRule(
                base_name,
                set(self.current_neighbors),
                self.current_tileset_path,
                list(self.current_variant_ids),
                preview,
                tileset_index=getattr(self, "current_tileset_index", None),
                group_id=current_group.name,
            )
            current_group.rules.append(new_rule)
            self.selected_rule_index = len(current_group.rules) - 1
            print(f"New rule created: {new_rule.name} in Group {current_group.name}")

        self._reset_selection()

        print(f"Total rules now: {len(self.rules)}")
        for r in self.rules:
            print(f"  - {r.name}: neighbors={r.neighbors}, variants={r.variant_ids}")

    def _delete_current_rule(self):
        if self.selected_group_idx != -1 and 0 <= self.selected_rule_index < len(
            self.groups[self.selected_group_idx].rules
        ):
            self.groups[self.selected_group_idx].rules.pop(self.selected_rule_index)
            self._reset_selection()

            group = self.groups[self.selected_group_idx]
            max_scroll = max(0, len(group.rules) - self.max_visible_rules)
            self.scroll_offset = min(self.scroll_offset, max_scroll)
        elif self.selected_group_idx != -1 and self.selected_rule_index == -1:
            if len(self.groups) > 1:
                self.groups.pop(self.selected_group_idx)
                self.selected_group_idx = 0
                self.selected_rule_index = -1
                self.scroll_offset = 0

    def _launch_external_viewer(self):
        import tempfile

        from utils.standalone import launch_standalone

        project_path = self.editor.tilemap.active_project_path

        if not project_path:
            temp_dir = Path(tempfile.gettempdir()) / "tilemap_cache"
            temp_dir.mkdir(parents=True, exist_ok=True)
            project_path = temp_dir / "current_session.json"
            self.editor.tilemap.active_project_path = project_path
            self.editor.tilemap.save_map()
        else:
            try:
                self.editor.tilemap.save_map()
            except Exception as e:
                print(f"Warning: Could not auto-save project for viewer: {e}")

        try:
            launch_standalone(
                "standalone_automap",
                [str(project_path)],
                cwd=BASE_PATH,
            )
            print(f"Launched external automap viewer linked to: {project_path.name}")
        except Exception as e:
            print(f"Failed to launch external viewer: {e}")

    def draw(self, screen: Surface):
        if not self.visible:
            return

        self._push_hints_to_selector()

        pygame.draw.rect(screen, WINDOW_BG, self.rect)
        pygame.draw.rect(screen, BORDER_COLOR, self.rect, 1)

        pygame.draw.rect(
            screen,
            COLORS.accent,
            Rect(self.rect.x, self.rect.y, self.rect.width, self.header_height),
        )
        title = self.title_font.render("Autotile Designer", True, COLORS.text)
        screen.blit(title, (self.rect.x + 10, self.rect.y + 5))

        pygame.draw.rect(screen, COLORS.danger, self.close_btn_rect)
        x_lbl = self.title_font.render("X", True, COLORS.text)
        screen.blit(x_lbl, (self.close_btn_rect.x + 10, self.close_btn_rect.y + 5))

        pygame.draw.rect(screen, PANEL_BG, self.list_area)

        self._draw_rule_list(screen)
        self._draw_grid_editor(screen)

        self.template_manager.draw(screen)

    def _draw_rule_list(self, screen):

        pygame.draw.rect(screen, COLORS.header, self.group_list_area)
        pygame.draw.rect(screen, COLORS.border, self.group_list_area, 1)

        lbl_groups = self.title_font.render(
            "Groups (F2: Rename)", True, COLORS.accent_hover
        )
        screen.blit(
            lbl_groups, (self.group_list_area.x + 5, self.group_list_area.y + 5)
        )

        start_y = self.group_list_area.y + 25
        item_h = 25
        for i, group in enumerate(self.groups):
            r = Rect(
                self.group_list_area.x + 5,
                start_y + i * item_h,
                self.group_list_area.width - 10,
                item_h,
            )

            if i == self.selected_group_idx:
                pygame.draw.rect(screen, COLORS.hover, r, border_radius=3)

            if i == self.renaming_group_idx:
                pygame.draw.rect(screen, COLORS.selected, r, border_radius=3)

            name = group.name
            if i == self.renaming_group_idx:
                display_name = self.rename_input.text
                cursor_offset = self.rename_input.cursor_pos
                prefix = display_name[:cursor_offset]
                if (pygame.time.get_ticks() // 500) % 2:
                    name = prefix + "|" + display_name[cursor_offset:]
                else:
                    name = prefix + " " + display_name[cursor_offset:]

            d_name = name if len(name) < 22 else name[:19] + ".."
            on_blue = i == self.renaming_group_idx or i == self.selected_group_idx
            g_color = COLORS.text_on_accent if on_blue else COLORS.text
            screen.blit(self.font.render(d_name, True, g_color), (r.x + 5, r.y + 5))

        pygame.draw.rect(
            screen, COLORS.success, self.new_group_btn_rect, border_radius=4
        )
        gntxt = self.font.render("+ New Group", True, COLORS.text)
        screen.blit(
            gntxt, (self.new_group_btn_rect.x + 10, self.new_group_btn_rect.y + 5)
        )

        pygame.draw.rect(screen, PANEL_BG, self.rule_list_area)
        pygame.draw.rect(screen, COLORS.border, self.rule_list_area, 1)

        lbl_rules = self.title_font.render("Rules", True, COLORS.accent_hover)
        screen.blit(lbl_rules, (self.rule_list_area.x + 5, self.rule_list_area.y + 5))

        self._draw_scrollable_rule_list(screen)

        pygame.draw.rect(
            screen, COLORS.accent, self.new_rule_btn_rect, border_radius=4
        )
        rntxt = self.font.render("+ New Rule", True, COLORS.text)
        screen.blit(
            rntxt, (self.new_rule_btn_rect.x + 10, self.new_rule_btn_rect.y + 5)
        )

    def _draw_scrollable_rule_list(self, screen: Surface) -> None:
        """Draw rules with scroll indicators and scrollbar - with clipping to prevent overflow"""
        if self.selected_group_idx == -1:
            return

        group = self.groups[self.selected_group_idx]
        total_rules = len(group.rules)

        max_scroll = max(0, total_rules - self.max_visible_rules)

        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

        list_clip = Rect(
            self.rule_list_area.x,
            self.rule_list_area.y + 25,
            self.rule_list_area.width,
            self.rule_list_area.height - 25,
        )
        old_clip = screen.get_clip()
        screen.set_clip(list_clip)

        visible_start = self.scroll_offset
        visible_end = min(visible_start + self.max_visible_rules, total_rules)

        start_y_r = self.rule_list_area.y + 25
        item_h = 25

        for i in range(visible_start, visible_end):
            rule = group.rules[i]
            display_index = i - visible_start
            y_pos = start_y_r + display_index * item_h

            r = Rect(
                self.rule_list_area.x + 5, y_pos, self.rule_list_area.width - 10, item_h
            )

            if i == self.selected_rule_index:
                pygame.draw.rect(screen, COLORS.hover, r, border_radius=3)

            d_name = rule.name if len(rule.name) < 20 else rule.name[:17] + ".."
            screen.blit(self.font.render(d_name, True, COLORS.text), (r.x + 5, r.y + 5))

        screen.set_clip(old_clip)

        if total_rules > self.max_visible_rules:
            if self.scroll_offset > 0:
                arrow_surf = icon_manager.get_icon("arrow-down", 14, (150, 200, 255))
                arrow_surf = pygame.transform.rotate(arrow_surf, 180)
                screen.blit(
                    arrow_surf,
                    (self.rule_list_area.right - 20, self.rule_list_area.y + 5),
                )

            if self.scroll_offset < max_scroll:
                arrow_surf = icon_manager.get_icon("arrow-down", 14, (150, 200, 255))
                screen.blit(
                    arrow_surf,
                    (self.rule_list_area.right - 20, self.rule_list_area.bottom - 20),
                )

            scrollbar_height = 60
            track_height = self.rule_list_area.height - 50
            scroll_ratio = self.scroll_offset / max_scroll if max_scroll > 0 else 0

            scrollbar_y = (
                self.rule_list_area.y
                + 25
                + int(scroll_ratio * (track_height - scrollbar_height))
            )

            self.scroll_bar_rect = Rect(
                self.rule_list_area.right - 15, scrollbar_y, 10, scrollbar_height
            )

            pygame.draw.rect(
                screen, (100, 100, 120), self.scroll_bar_rect, border_radius=5
            )
        else:
            self.scroll_bar_rect = None

    def _handle_scroll_event(self, event) -> bool:
        """Handle mouse wheel and scrollbar dragging"""
        if self.selected_group_idx == -1:
            return False

        group = self.groups[self.selected_group_idx]
        total_rules = len(group.rules)
        max_scroll = max(0, total_rules - self.max_visible_rules)

        if event.type == pygame.MOUSEWHEEL:
            if self.rule_list_area.collidepoint(pygame.mouse.get_pos()):
                scroll_delta = -event.y
                old_offset = self.scroll_offset
                self.scroll_offset = max(
                    0, min(self.scroll_offset + scroll_delta, max_scroll)
                )
                return old_offset != self.scroll_offset

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.scroll_bar_rect and self.scroll_bar_rect.collidepoint(
                    event.pos
                ):
                    self.is_scrollbar_dragging = True
                    return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.is_scrollbar_dragging:
                self.is_scrollbar_dragging = False
                return True

        elif event.type == pygame.MOUSEMOTION and self.is_scrollbar_dragging:
            relative_y = event.pos[1] - self.rule_list_area.y - 25
            track_height = self.rule_list_area.height - 50

            if track_height > 0:
                scroll_ratio = max(0, min(1, relative_y / track_height))
                self.scroll_offset = int(scroll_ratio * max_scroll)
                self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

            return True

        return False

    def _handle_group_rename(self, event) -> bool:
        """Handle F2 key and inline text editing for group names"""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F2 and self.selected_group_idx >= 0:
                self.renaming_group_idx = self.selected_group_idx
                self.rename_input.text = self.groups[self.selected_group_idx].name
                self.rename_input.cursor_pos = len(self.rename_input.text)
                self.rename_input.is_focused = True
                return True

            if self.renaming_group_idx is not None:
                if event.key == pygame.K_RETURN:
                    group = self.groups[self.renaming_group_idx]
                    old_name = group.name
                    new_name = self.rename_input.text.strip()

                    if new_name and new_name != old_name:
                        existing_names = {
                            g.name
                            for i, g in enumerate(self.groups)
                            if i != self.renaming_group_idx
                        }
                        if new_name in existing_names:
                            counter = 2
                            base_name = new_name
                            while new_name in existing_names:
                                new_name = f"{base_name} {counter}"
                                counter += 1

                        group.name = new_name

                        for rule in group.rules:
                            rule.group_id = new_name

                    self.renaming_group_idx = None
                    self.rename_input.is_focused = False
                    return True

                if event.key == pygame.K_ESCAPE:
                    self.renaming_group_idx = None
                    self.rename_input.is_focused = False
                    return True

                if self.rename_input.handle_event(event, self.font):
                    return True

        return False

    def _create_new_group_with_focus(self) -> None:
        """Create new group and immediately enter rename mode"""

        new_group_name = f"Group {len(self.groups) + 1}"

        new_group = AutotileGroup(new_group_name)
        self.groups.append(new_group)

        self.selected_group_idx = len(self.groups) - 1
        self.selected_rule_index = -1

        self.renaming_group_idx = self.selected_group_idx
        self.rename_input.text = new_group_name
        self.rename_input.cursor_pos = len(new_group_name)
        self.rename_input.is_focused = True

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
                pygame.draw.rect(screen, COLORS.panel_alt, cell, 1)

        pygame.draw.rect(screen, COLORS.success, self.save_btn_rect, border_radius=4)
        s_lbl = self.font.render("Save", True, COLORS.text)
        screen.blit(s_lbl, (self.save_btn_rect.x + 25, self.save_btn_rect.y + 8))

        if self.selected_rule_index != -1:
            pygame.draw.rect(
                screen, (180, 70, 70), self.delete_btn_rect, border_radius=4
            )
            d_lbl = self.font.render("Del", True, COLORS.text)
            screen.blit(
                d_lbl, (self.delete_btn_rect.x + 25, self.delete_btn_rect.y + 8)
            )

        pygame.draw.rect(
            screen, (100, 100, 150), self.external_btn_rect, border_radius=4
        )
        ext_lbl = self.font.render("External View", True, COLORS.text)
        screen.blit(
            ext_lbl, (self.external_btn_rect.x + 8, self.external_btn_rect.y + 5)
        )

        if self.current_variant_ids:
            pygame.draw.rect(
                screen, (60, 120, 120), self.template_btn_rect, border_radius=4
            )
            tmpl_lbl = self.font.render("Templates", True, COLORS.text)
            screen.blit(
                tmpl_lbl, (self.template_btn_rect.x + 18, self.template_btn_rect.y + 5)
            )
