import pygame
import os
import json
from pygame import Surface, Rect, Color
from typing import TYPE_CHECKING, List, Tuple, Set, Optional
import time
from .autotile_template import AutotileTemplateApplier

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
        tileset_path: str = "",
        variant_ids: Optional[List[int]] = None,
        surface_subsurface: Optional[Surface] = None,
        tileset_index: Optional[int] = None,
        group_id: Optional[str] = None,
    ):
        self.name = name
        self.neighbors = neighbors

        self.tileset_path = tileset_path

        self.tileset_index = tileset_index
        self.variant_ids = variant_ids or []
        self.preview_surf: Optional[Surface] = surface_subsurface
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
            tileset_index=data.get("tileset_index", None),
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
    def __init__(self, name: str, rules: List[AutotileRule] = None):
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
        self.rect = Rect(x, y, 600, 450)
        self.header_height = 30

        self.visible = False
        self.is_dragging = False
        self.drag_offset = (0, 0)

        self.groups: List[AutotileGroup] = [AutotileGroup("Default")]
        self.selected_group_idx: int = 0
        self.selected_rule_index: int = -1

        self.renaming_group_idx: Optional[int] = None
        self.rename_text: str = ""

        # Scroll state management
        self.scroll_offset: int = 0
        self.max_visible_rules: int = 10
        self.scroll_bar_rect: Optional[Rect] = None
        self.is_scrollbar_dragging: bool = False

        self.current_neighbors: Set[Tuple[int, int]] = set()

        self.current_variant_ids: List[int] = []

        self.current_tileset_path: str = ""
        self.current_tileset_index: Optional[int] = None

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
        self.group_list_area = Rect(self.rect.x, body_y, sidebar_w, body_h // 2)
        self.rule_list_area = Rect(self.rect.x, body_y + body_h // 2, sidebar_w, body_h // 2)

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
            self.group_list_area.bottom - 30,
            self.group_list_area.width - 20,
            25,
        )
        self.new_rule_btn_rect = Rect(
            self.rule_list_area.x + 10,
            self.rule_list_area.bottom - 30,
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
        # Collect hints from ALL rules in ALL groups
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

    def handle_event(self, event) -> bool:
        if not self.visible:
            return False

        if self.template_manager.handle_event(event):
            return True

        # Handle scroll events
        if self._handle_scroll_event(event):
            return True
        
        # Handle group rename events
        if self._handle_group_rename(event):
            return True

        mouse_pos = pygame.mouse.get_pos()
        self._update_preview_from_selector()

        if event.type == pygame.KEYDOWN:
            pass  # Rename handling moved to _handle_group_rename

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

                if self.group_list_area.collidepoint(mouse_pos):
                    self._handle_group_list_click(mouse_pos)
                    return True
                
                if self.rule_list_area.collidepoint(mouse_pos):
                    self._handle_rule_list_click(mouse_pos)
                    return True

                if self.save_btn_rect.collidepoint(mouse_pos):
                    self._save_current_rule()
                    return True
                if self.save_btn_rect.inflate(0, 40).collidepoint(mouse_pos): # Catch nearby if needed
                    pass
                
                if self.new_group_btn_rect.collidepoint(mouse_pos):
                    self._create_new_group_with_focus()
                    return True
                    
                if self.new_rule_btn_rect.collidepoint(mouse_pos):
                    self._reset_selection()
                    return True

                if self.edit_area.collidepoint(mouse_pos):
                    if self._handle_grid_click(mouse_pos):
                        return True

                if self.delete_btn_rect.collidepoint(mouse_pos):
                    self._delete_current_rule()
                    return True
                if self.external_btn_rect.collidepoint(mouse_pos):
                    self._launch_external_viewer()
                    return True
                if self.template_btn_rect.collidepoint(mouse_pos):
                    self.template_manager.show_at(mouse_pos)
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
                            except:
                                pass
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
        start_y = self.group_list_area.y + 10
        item_h = 25
        for i, group in enumerate(self.groups):
            item_rect = Rect(
                self.group_list_area.x + 5,
                start_y + i * item_h,
                self.group_list_area.width - 10,
                item_h,
            )
            if item_rect.collidepoint(mouse_pos):
                self.selected_group_idx = i
                self.selected_rule_index = -1
                return

    def _handle_rule_list_click(self, mouse_pos):
        if self.new_rule_btn_rect.collidepoint(mouse_pos):
            self._reset_selection()
            return

        if self.selected_group_idx == -1:
            return

        group = self.groups[self.selected_group_idx]
        start_y = self.rule_list_area.y + 10
        item_h = 25
        for i, rule in enumerate(group.rules):
            item_rect = Rect(
                self.rule_list_area.x + 5,
                start_y + i * item_h,
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
                    except:
                        pass

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
        
        # Try to find a trailing number
        match = re.search(r'(.*?)(\d+)$', base_name)
        if match:
            prefix = match.group(1)
            number = int(match.group(2))
            return f"{prefix}{number + 1}"
        else:
            return f"{base_name} 2"

    def _save_current_rule(self):
        self._update_preview_from_selector()

        print(f"\nDEBUG: _save_current_rule called")

        tile_selector = getattr(self.editor, "tileset_widget", None)
        if (
            not self.current_tileset_path or self.current_tileset_index is None
        ) and tile_selector:
            ts = tile_selector.get_active_tile()
            if ts:
                self.current_tileset_path = str(ts.path)
                self.current_tileset_index = tile_selector.active_idx

        if not self.current_tileset_path or not self.current_variant_ids:
            print(f"DEBUG: Can't save rule - missing tileset or variants")
            return

        if self.selected_group_idx == -1:
            print("DEBUG: Can't save rule - no group selected")
            return

        preview = self.current_preview_surfs[0] if self.current_preview_surfs else None
        current_group = self.groups[self.selected_group_idx]

        # If index is >= 0, we update existing. Otherwise we create new.
        if self.selected_rule_index >= 0:
            rule = current_group.rules[self.selected_rule_index]
            rule.neighbors = set(self.current_neighbors)
            rule.variant_ids = list(self.current_variant_ids)
            rule.preview_surf = preview
            rule.tileset_path = self.current_tileset_path
            rule.tileset_index = getattr(self, "current_tileset_index", None)
            rule.group_id = current_group.name # Update group_id in rule too
            print(f"Rule updated: {rule.name} in Group {current_group.name}")
        else:
            # Determine unique name
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
                group_id=current_group.name
            )
            current_group.rules.append(new_rule)
            self.selected_rule_index = len(current_group.rules) - 1
            print(f"New rule created: {new_rule.name} in Group {current_group.name}")

        # After saving, always reset to ready-state for a new rule
        self._reset_selection()

        print(f"Total rules now: {len(self.rules)}")
        for r in self.rules:
            print(f"  - {r.name}: neighbors={r.neighbors}, variants={r.variant_ids}")

    def _delete_current_rule(self):
        if self.selected_group_idx != -1 and 0 <= self.selected_rule_index < len(self.groups[self.selected_group_idx].rules):
            self.groups[self.selected_group_idx].rules.pop(self.selected_rule_index)
            self._reset_selection()

            # Clamp scroll offset after deletion
            group = self.groups[self.selected_group_idx]
            max_scroll = max(0, len(group.rules) - self.max_visible_rules)
            self.scroll_offset = min(self.scroll_offset, max_scroll)
        elif self.selected_group_idx != -1 and self.selected_rule_index == -1:
            # Delete Group
            if len(self.groups) > 1:
                self.groups.pop(self.selected_group_idx)
                self.selected_group_idx = 0
                self.selected_rule_index = -1
                self.scroll_offset = 0  # Reset scroll when switching groups

    def _launch_external_viewer(self):
        import subprocess
        import sys
        
        from constants import BASE_PATH
        
        # Determine path to the standalone script
        script_path = os.path.join(os.path.dirname(__file__), "..", "standalone_automap.py")
        
        # Determine which project file to tell the viewer to look at
        project_path = self.editor.tilemap.active_project_path
        
        # If no project is active or it hasn't been saved yet, 
        # save a temporary snapshot so the viewer can read current rules
        if not project_path:
            temp_dir = BASE_PATH / "data" / "cache"
            temp_dir.mkdir(parents=True, exist_ok=True)
            project_path = temp_dir / "current_session.json"
            try:
                self.editor.tilemap.save_map(str(project_path.relative_to(BASE_PATH / "data")))
            except Exception as e:
                # Fallback if relative path calculation fails
                self.editor.tilemap.active_project_path = project_path
                self.editor.tilemap.save_map()
        else:
            # Even if we have a project path, we should save current changes 
            # so the external viewer sees the latest rules
            try:
                self.editor.tilemap.save_map()
            except Exception as e:
                print(f"Warning: Could not auto-save project for viewer: {e}")
                
        try:
            # Popen spawns it as a separate independent process
            subprocess.Popen([sys.executable, script_path, str(project_path)])
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
        
        self.template_manager.draw(screen) # Draw template manager if visible

    def _draw_rule_list(self, screen):
        # 1. Groups List
        pygame.draw.rect(screen, (70, 70, 75), self.group_list_area)
        pygame.draw.rect(screen, (100, 100, 105), self.group_list_area, 1)
        
        lbl_groups = self.title_font.render("Groups (F2: Rename)", True, (150, 150, 255))
        screen.blit(lbl_groups, (self.group_list_area.x + 5, self.group_list_area.y + 5))

        start_y = self.group_list_area.y + 25
        item_h = 25
        for i, group in enumerate(self.groups):
            r = Rect(self.group_list_area.x + 5, start_y + i * item_h, self.group_list_area.width - 10, item_h)
            
            # Highlight selected group
            if i == self.selected_group_idx:
                pygame.draw.rect(screen, HIGHLIGHT_COLOR, r, border_radius=3)
            
            # Show rename mode with different background
            if i == self.renaming_group_idx:
                pygame.draw.rect(screen, (100, 120, 140), r, border_radius=3)
            
            name = group.name
            if i == self.renaming_group_idx:
                name = self.rename_text + "_"
            
            d_name = name if len(name) < 22 else name[:19] + ".."
            screen.blit(self.font.render(d_name, True, TEXT_COLOR), (r.x + 5, r.y + 5))

        pygame.draw.rect(screen, (80, 120, 80), self.new_group_btn_rect, border_radius=4)
        gntxt = self.font.render("+ New Group", True, TEXT_COLOR)
        screen.blit(gntxt, (self.new_group_btn_rect.x + 10, self.new_group_btn_rect.y + 5))

        # 2. Rules List (for selected group)
        pygame.draw.rect(screen, PANEL_BG, self.rule_list_area)
        pygame.draw.rect(screen, (80, 80, 85), self.rule_list_area, 1)
        
        lbl_rules = self.title_font.render("Rules", True, (150, 150, 255))
        screen.blit(lbl_rules, (self.rule_list_area.x + 5, self.rule_list_area.y + 5))

        # Use scrollable rule list
        self._draw_scrollable_rule_list(screen)

        pygame.draw.rect(screen, (70, 130, 180), self.new_rule_btn_rect, border_radius=4)
        rntxt = self.font.render("+ New Rule", True, TEXT_COLOR)
        screen.blit(rntxt, (self.new_rule_btn_rect.x + 10, self.new_rule_btn_rect.y + 5))
    def _draw_scrollable_rule_list(self, screen: Surface) -> None:
        """Draw rules with scroll indicators and scrollbar"""
        if self.selected_group_idx == -1:
            return

        group = self.groups[self.selected_group_idx]
        total_rules = len(group.rules)

        # Calculate max scroll value
        max_scroll = max(0, total_rules - self.max_visible_rules)

        # Clamp scroll offset to valid range
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

        # Calculate visible range
        visible_start = self.scroll_offset
        visible_end = min(visible_start + self.max_visible_rules, total_rules)

        # Draw visible rules
        start_y_r = self.rule_list_area.y + 25
        item_h = 25

        for i in range(visible_start, visible_end):
            rule = group.rules[i]
            display_index = i - visible_start
            y_pos = start_y_r + display_index * item_h

            r = Rect(
                self.rule_list_area.x + 5,
                y_pos,
                self.rule_list_area.width - 10,
                item_h
            )

            if i == self.selected_rule_index:
                pygame.draw.rect(screen, HIGHLIGHT_COLOR, r, border_radius=3)

            d_name = rule.name if len(rule.name) < 20 else rule.name[:17] + ".."
            screen.blit(self.font.render(d_name, True, TEXT_COLOR), (r.x + 5, r.y + 5))

        # Draw scroll indicators and scrollbar if needed
        if total_rules > self.max_visible_rules:
            # Draw upward arrow when not at top
            if self.scroll_offset > 0:
                arrow_up = "▲"
                arrow_surf = self.font.render(arrow_up, True, (150, 200, 255))
                screen.blit(arrow_surf, (self.rule_list_area.right - 20, self.rule_list_area.y + 5))
            
            # Draw downward arrow when not at bottom
            if self.scroll_offset < max_scroll:
                arrow_down = "▼"
                arrow_surf = self.font.render(arrow_down, True, (150, 200, 255))
                screen.blit(arrow_surf, (self.rule_list_area.right - 20, self.rule_list_area.bottom - 35))
            
            # Draw scrollbar
            scrollbar_height = 60
            track_height = self.rule_list_area.height - 70  # Leave space for header and button
            scroll_ratio = self.scroll_offset / max_scroll if max_scroll > 0 else 0

            scrollbar_y = self.rule_list_area.y + 25 + int(scroll_ratio * (track_height - scrollbar_height))

            self.scroll_bar_rect = Rect(
                self.rule_list_area.right - 15,
                scrollbar_y,
                10,
                scrollbar_height
            )

            pygame.draw.rect(screen, (100, 100, 120), self.scroll_bar_rect, border_radius=5)
        else:
            # Hide scrollbar when all rules are visible
            self.scroll_bar_rect = None
    def _handle_scroll_event(self, event) -> bool:
        """Handle mouse wheel and scrollbar dragging"""
        if self.selected_group_idx == -1:
            return False

        group = self.groups[self.selected_group_idx]
        total_rules = len(group.rules)
        max_scroll = max(0, total_rules - self.max_visible_rules)

        if event.type == pygame.MOUSEWHEEL:
            # Handle mouse wheel scrolling
            if self.rule_list_area.collidepoint(pygame.mouse.get_pos()):
                scroll_delta = -event.y  # Negative for natural scrolling
                old_offset = self.scroll_offset
                self.scroll_offset = max(0, min(self.scroll_offset + scroll_delta, max_scroll))
                return old_offset != self.scroll_offset

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.scroll_bar_rect and self.scroll_bar_rect.collidepoint(event.pos):
                    self.is_scrollbar_dragging = True
                    return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.is_scrollbar_dragging:
                self.is_scrollbar_dragging = False
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.is_scrollbar_dragging:
                # Calculate scroll position from mouse Y
                relative_y = event.pos[1] - self.rule_list_area.y - 25
                track_height = self.rule_list_area.height - 70

                if track_height > 0:
                    scroll_ratio = max(0, min(1, relative_y / track_height))
                    self.scroll_offset = int(scroll_ratio * max_scroll)
                    self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

                return True

        return False
    def _handle_group_rename(self, event) -> bool:
        """Handle F2 key and inline text editing for group names"""
        if event.type == pygame.KEYDOWN:
            # F2 to start renaming selected group
            if event.key == pygame.K_F2 and self.selected_group_idx >= 0:
                self.renaming_group_idx = self.selected_group_idx
                self.rename_text = self.groups[self.selected_group_idx].name
                return True

            # Handle text input during rename
            if self.renaming_group_idx is not None:
                if event.key == pygame.K_RETURN:
                    # Confirm rename
                    group = self.groups[self.renaming_group_idx]
                    old_name = group.name
                    new_name = self.rename_text.strip()

                    # Handle duplicate names by appending numeric suffix
                    if new_name and new_name != old_name:
                        # Check if name already exists
                        existing_names = {g.name for i, g in enumerate(self.groups) if i != self.renaming_group_idx}
                        if new_name in existing_names:
                            # Find a unique name by appending numbers
                            counter = 2
                            base_name = new_name
                            while new_name in existing_names:
                                new_name = f"{base_name} {counter}"
                                counter += 1

                        group.name = new_name

                        # Update all rules in this group
                        for rule in group.rules:
                            rule.group_id = new_name

                    self.renaming_group_idx = None
                    return True

                elif event.key == pygame.K_ESCAPE:
                    # Cancel rename
                    self.renaming_group_idx = None
                    return True

                elif event.key == pygame.K_BACKSPACE:
                    # Delete character
                    self.rename_text = self.rename_text[:-1]
                    return True

                else:
                    # Add character
                    if event.unicode.isprintable():
                        self.rename_text += event.unicode
                    return True

        return False
    def _create_new_group_with_focus(self) -> None:
        """Create new group and immediately enter rename mode"""
        # Generate default name
        new_group_name = f"Group {len(self.groups) + 1}"

        # Create new group
        new_group = AutotileGroup(new_group_name)
        self.groups.append(new_group)

        # Select the new group
        self.selected_group_idx = len(self.groups) - 1
        self.selected_rule_index = -1

        # Immediately enter rename mode
        self.renaming_group_idx = self.selected_group_idx
        self.rename_text = new_group_name


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

        # External button
        pygame.draw.rect(screen, (100, 100, 150), self.external_btn_rect, border_radius=4)
        ext_lbl = self.font.render("External View", True, Color("white"))
        screen.blit(ext_lbl, (self.external_btn_rect.x + 8, self.external_btn_rect.y + 5))
        
        # Template button (only show if selection exists)
        if self.current_variant_ids:
            pygame.draw.rect(screen, (60, 120, 120), self.template_btn_rect, border_radius=4)
            tmpl_lbl = self.font.render("Templates", True, Color("white"))
            screen.blit(tmpl_lbl, (self.template_btn_rect.x + 18, self.template_btn_rect.y + 5))
