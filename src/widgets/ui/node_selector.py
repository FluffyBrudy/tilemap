from typing import TYPE_CHECKING

import pygame
from pygame import Rect

if TYPE_CHECKING:
    from editor import Editor
from utils.font_manager import FontWeight, font_manager
from widgets.ui.draw_utils import draw_panel
from widgets.ui.theme import COLORS, FONTS, SHAPE


class NodeSelector:
    NODE_TYPE_COLORS: dict[str, tuple[int, int, int]] = {
        "area": (80, 220, 120),
        "spawn": (80, 140, 240),
        "portal": (180, 80, 220),
        "npc": (240, 140, 60),
        "checkpoint": (60, 200, 200),
        "item": (220, 200, 60),
        "particle_emitter": (240, 140, 200),
    }

    def __init__(self, editor: "Editor", x: int, y: int, w: int = 260, h: int = 240):
        self.editor = editor
        self.rect = Rect(x, y, w, h)

        self.font = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)
        self.font_bold = font_manager.get_font(
            FONTS.name, FONTS.size_sm, FontWeight.BOLD
        )
        self.font_mini = font_manager.get_font(
            FONTS.name, FONTS.size_sm - 1, FontWeight.REGULAR
        )

        self.search_text = ""
        self.scroll_offset = 0
        self.item_h = 28
        self.header_h = 32
        self.input_h = 26

        self.hover_idx: int | None = None
        self.delete_hover: bool = False
        self.dup_hover: bool = False
        self.collapse_all_hover: bool = False
        self.arrow_hover: bool = False
        self.add_btn_hover: bool = False
        self._add_dropdown_hover_idx: int | None = None

        self.dragged_item_idx: int | None = None
        self.dragged_item_y_offset: int = 0
        self.drag_start_y: int = 0
        self.is_dragging: bool = False

        self._node_types: list[tuple[str, str, tuple[int, int, int]]] = [
            ("area", "Area Zone", (80, 220, 120)),
            ("group", "Group / Folder", (220, 180, 80)),
            ("particle_emitter", "Particle Emitter", (240, 140, 200)),
        ]
        self._add_dropdown_open: bool = False

        self.collapsed_groups = set()
        self._filtered_rows: list[dict] = []
        self._rebuild_filter()

    def resize(self, x: int, y: int, w: int):
        self.rect = Rect(x, y, w, self.rect.height)

    def _rebuild_filter(self) -> list[dict]:
        mgr = self.editor.node_manager
        query = self.search_text.lower()

        grouped_nodes = {g: [] for g in mgr.groups}
        ungrouped_nodes = []

        for node in mgr.nodes.values():
            if query and query not in node.name.lower():
                continue
            if node.group in grouped_nodes:
                grouped_nodes[node.group].append(node)
            else:
                ungrouped_nodes.append(node)

        self._filtered_rows = []

        for g in mgr.groups:
            if query and len(grouped_nodes[g]) == 0:
                continue
            self._filtered_rows.append(
                {"type": "group", "name": g, "nodes_count": len(grouped_nodes[g])}
            )
            if g not in self.collapsed_groups:
                for node in grouped_nodes[g]:
                    self._filtered_rows.append(
                        {"type": "node", "node_id": node.node_id, "indent": True}
                    )

        for node in ungrouped_nodes:
            self._filtered_rows.append(
                {"type": "node", "node_id": node.node_id, "indent": False}
            )

        return self._filtered_rows

    @property
    def visible(self) -> bool:
        return self.editor.node_editing_mode

    def _collapse_toggle_rect(self) -> Rect:
        return Rect(self.rect.right - 32, self.rect.y + 4, 26, 24)

    def _all_collapsed(self) -> bool:
        mgr = self.editor.node_manager
        return bool(mgr.groups) and all(
            g in self.collapsed_groups for g in mgr.groups
        )

    def _toggle_collapse_all(self):
        mgr = self.editor.node_manager
        if self._all_collapsed():
            self.collapsed_groups.clear()
        else:
            self.collapsed_groups.update(mgr.groups)
        self._rebuild_filter()

    def _duplicate_node(self, node_id: str):
        mgr = self.editor.node_manager
        if mgr.duplicate_node(node_id) is not None:
            self._rebuild_filter()
            self.editor.tilemap.capture_history("Duplicate Node")

    def _add_button_rect(self) -> Rect:
        add_h = 28
        return Rect(
            self.rect.x + 6, self.rect.y + self.header_h, self.rect.width - 12, add_h
        )

    def _add_dropdown_items(self) -> list[tuple[str, str, tuple[int, int, int], Rect]]:
        btn = self._add_button_rect()
        items = []
        y = btn.bottom + 2
        item_h = 26
        for t_name, t_label, t_color in self._node_types:
            items.append((t_name, t_label, t_color, Rect(btn.x, y, btn.width, item_h)))
            y += item_h
        return items

    def _search_rect(self) -> Rect:
        top = self._add_button_rect().bottom + 6
        return Rect(self.rect.x + 6, top, self.rect.width - 12, self.input_h)

    @staticmethod
    def _row_action_rects(item_rect: Rect) -> tuple[Rect, Rect]:
        """Duplicate/delete hit rects for a row (shared by hover/click/draw)."""
        dup_rect = Rect(item_rect.right - 48, item_rect.y + 2, 20, 24)
        del_rect = Rect(item_rect.right - 24, item_rect.y + 2, 20, 24)
        return dup_rect, del_rect

    def _list_rect(self) -> Rect:
        top = self._search_rect().bottom + 6
        return Rect(
            self.rect.x + 2, top, self.rect.width - 4, self.rect.bottom - top - 6
        )

    def _draw_folder_icon(self, screen, x, y, color):
        pygame.draw.rect(
            screen,
            color,
            Rect(x, y, 5, 2),
            border_top_left_radius=1,
            border_top_right_radius=1,
        )
        pygame.draw.rect(screen, color, Rect(x, y + 2, 12, 8), border_radius=1)

    def _draw_arrow(self, screen, x, y, collapsed: bool, color):
        if collapsed:
            points = [(x, y), (x + 5, y + 4), (x, y + 8)]
        else:
            points = [(x, y + 1), (x + 8, y + 1), (x + 4, y + 6)]
        pygame.draw.polygon(screen, color, points)

    def _handle_drag_drop(self, drag_idx: int, drop_idx: int):
        mgr = self.editor.node_manager
        rows = self._filtered_rows
        if not (0 <= drag_idx < len(rows)):
            return

        drag_row = rows[drag_idx]

        if not (0 <= drop_idx < len(rows)):
            if drag_row["type"] == "node":
                node_id = drag_row["node_id"]
                node = mgr.get_node(node_id)
                if node:
                    node.group = None
            self._rebuild_filter()
            self.editor.tilemap.capture_history("Ungroup Node")
            return

        drop_row = rows[drop_idx]

        if drag_row["type"] == "group":
            drag_group_name = drag_row["name"]

            target_group_name = None
            if drop_row["type"] == "group":
                target_group_name = drop_row["name"]
            elif drop_row["type"] == "node":
                target_node = mgr.get_node(drop_row["node_id"])
                if target_node:
                    target_group_name = target_node.group

            if drag_group_name in mgr.groups:
                mgr.groups.remove(drag_group_name)
                if target_group_name in mgr.groups:
                    target_idx = mgr.groups.index(target_group_name)
                    if drop_idx > drag_idx:
                        target_idx += 1
                    mgr.groups.insert(max(0, target_idx), drag_group_name)
                else:
                    mgr.groups.append(drag_group_name)

        elif drag_row["type"] == "node":
            node_id = drag_row["node_id"]
            node = mgr.get_node(node_id)
            if not node:
                return

            if drop_row["type"] == "group":
                target_group = drop_row["name"]
                node.group = target_group

                first_node_id = None
                for n in mgr.nodes.values():
                    if n.group == target_group and n.node_id != node_id:
                        first_node_id = n.node_id
                        break
                if first_node_id:
                    mgr.reorder_node(node_id, first_node_id, before=True)

            elif drop_row["type"] == "node":
                target_node_id = drop_row["node_id"]
                target_node = mgr.get_node(target_node_id)
                if target_node:
                    node.group = target_node.group
                    before = drop_idx < drag_idx
                    mgr.reorder_node(node_id, target_node_id, before=before)

        self._rebuild_filter()
        self.editor.tilemap.capture_history("Reorder Node")

    def _create_item(self, item_type: str):
        mgr = self.editor.node_manager
        if item_type == "group":
            new_group = f"Group {len(mgr.groups) + 1}"
            mgr.groups.append(new_group)
            mgr.set_active_group(new_group)
            self.editor.tilemap.capture_history("Add Group")
        else:
            layer = self.editor.tilemap.layer_manager.get_active_layer()
            layer_name = layer.name if layer else "Default"
            node = mgr.create_default_node(layer_name, node_type=item_type)
            grid = self.editor.tile_grid_widget
            if grid and hasattr(grid, "rect"):
                cx = int(grid.scroll_x + (grid.rect.width / grid.zoom_level) / 2)
                cy = int(grid.scroll_y + (grid.rect.height / grid.zoom_level) / 2)
                node.area.x = cx - 32
                node.area.y = cy - 32
            if mgr.active_group_name and item_type != "group":
                node.group = mgr.active_group_name
            mgr.add_node(node)
            mgr.set_active_node(node.node_id)
            mgr.default_node_type = item_type
            self.editor.tilemap.capture_history("Add Node")
        self._rebuild_filter()

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        mouse_pos = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEMOTION:
            if self.dragged_item_idx is not None:
                if abs(mouse_pos[1] - self.drag_start_y) > 4:
                    self.is_dragging = True
                return True

            if not self.rect.collidepoint(mouse_pos):
                self.hover_idx = None
                self.delete_hover = False
                self.dup_hover = False
                self.collapse_all_hover = False
                self.arrow_hover = False
                self.add_btn_hover = False
                self._add_dropdown_hover_idx = None
                return False

            self.collapse_all_hover = self._collapse_toggle_rect().collidepoint(
                mouse_pos
            )

            add_btn = self._add_button_rect()
            self.add_btn_hover = add_btn.collidepoint(mouse_pos)

            if self._add_dropdown_open:
                dropdown_items = self._add_dropdown_items()
                self._add_dropdown_hover_idx = None
                for idx, (t_name, _t_label, _t_color, r) in enumerate(dropdown_items):
                    if r.collidepoint(mouse_pos):
                        self._add_dropdown_hover_idx = idx
                        break
            else:
                self._add_dropdown_hover_idx = None

            list_rect = self._list_rect()
            if list_rect.collidepoint(mouse_pos) and not self._add_dropdown_open:
                rel_y = mouse_pos[1] - list_rect.y + self.scroll_offset
                idx = rel_y // self.item_h
                rows = self._filtered_rows
                if 0 <= idx < len(rows):
                    self.hover_idx = idx
                    y_pos = list_rect.y - self.scroll_offset + idx * self.item_h
                    item_rect = Rect(list_rect.x, y_pos, list_rect.width, self.item_h)

                    dup_rect, del_rect = self._row_action_rects(item_rect)
                    self.delete_hover = del_rect.collidepoint(mouse_pos)
                    self.dup_hover = dup_rect.collidepoint(mouse_pos)

                    if rows[idx]["type"] == "group":
                        arrow_rect = Rect(item_rect.x + 4, item_rect.y + 8, 12, 12)
                        self.arrow_hover = arrow_rect.collidepoint(mouse_pos)
                    else:
                        self.arrow_hover = False
                else:
                    self.hover_idx = None
                    self.delete_hover = False
                    self.dup_hover = False
                    self.arrow_hover = False
            else:
                self.hover_idx = None
                self.delete_hover = False
                self.dup_hover = False
                self.arrow_hover = False
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if not self.rect.collidepoint(mouse_pos):
                if self._add_dropdown_open:
                    self._add_dropdown_open = False
                    return True
                return False

            if event.button == 1:
                if self._collapse_toggle_rect().collidepoint(mouse_pos):
                    self._toggle_collapse_all()
                    return True

                if self._add_dropdown_open:
                    dropdown_items = self._add_dropdown_items()
                    for idx, (t_name, _t_label, _t_color, r) in enumerate(dropdown_items):
                        if r.collidepoint(mouse_pos):
                            self._create_item(t_name)
                            self._add_dropdown_open = False
                            return True
                    self._add_dropdown_open = False
                    return True

                add_btn = self._add_button_rect()
                if add_btn.collidepoint(mouse_pos):
                    self._add_dropdown_open = not self._add_dropdown_open
                    return True

                search_rect = self._search_rect()
                if search_rect.collidepoint(mouse_pos):
                    return True

                list_rect = self._list_rect()
                if list_rect.collidepoint(mouse_pos):
                    rel_y = mouse_pos[1] - list_rect.y + self.scroll_offset
                    idx = rel_y // self.item_h
                    rows = self._filtered_rows
                    if 0 <= idx < len(rows):
                        row = rows[idx]
                        mgr = self.editor.node_manager
                        y_pos = list_rect.y - self.scroll_offset + idx * self.item_h
                        item_rect = Rect(
                            list_rect.x, y_pos, list_rect.width, self.item_h
                        )
                        dup_rect, del_rect = self._row_action_rects(item_rect)

                        if dup_rect.collidepoint(mouse_pos):
                            if row["type"] == "node":
                                self._duplicate_node(row["node_id"])
                            self.hover_idx = None
                            self.delete_hover = False
                            self.dup_hover = False
                            return True

                        if del_rect.collidepoint(mouse_pos):
                            if row["type"] == "group":
                                group_name = row["name"]
                                if group_name in mgr.groups:
                                    mgr.groups.remove(group_name)
                                for node in mgr.nodes.values():
                                    if node.group == group_name:
                                        node.group = None
                                if mgr.active_group_name == group_name:
                                    mgr.active_group_name = None
                                self.editor.tilemap.capture_history("Delete Group")
                            else:
                                mgr.remove_node(row["node_id"])
                                self.editor.tilemap.capture_history("Delete Node")
                            self._rebuild_filter()
                            self.hover_idx = None
                            self.delete_hover = False
                            self.dup_hover = False
                            return True

                        if row["type"] == "group":
                            arrow_rect = Rect(item_rect.x + 4, item_rect.y + 8, 12, 12)
                            if arrow_rect.collidepoint(mouse_pos):
                                group_name = row["name"]
                                if group_name in self.collapsed_groups:
                                    self.collapsed_groups.remove(group_name)
                                else:
                                    self.collapsed_groups.add(group_name)
                                self._rebuild_filter()
                                return True

                        if row["type"] == "group":
                            mgr.set_active_group(row["name"])
                        else:
                            mgr.set_active_node(row["node_id"])

                        self.dragged_item_idx = idx
                        self.drag_start_y = mouse_pos[1]
                        self.dragged_item_y_offset = mouse_pos[1] - y_pos
                        self.is_dragging = False

                    return True
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragged_item_idx is not None:
                if self.is_dragging:
                    list_rect = self._list_rect()
                    rel_y = mouse_pos[1] - list_rect.y + self.scroll_offset
                    drop_idx = rel_y // self.item_h

                    if not self.rect.collidepoint(mouse_pos):
                        drop_idx = -1
                    self._handle_drag_drop(self.dragged_item_idx, drop_idx)

                self.dragged_item_idx = None
                self.is_dragging = False
                return True

        if event.type == pygame.KEYDOWN:
            if (
                self.editor.node_editor
                and self.editor.node_editor.visible
                and self.editor.node_editor.editing_field
            ):
                return False
            if event.key == pygame.K_ESCAPE:
                if self._add_dropdown_open:
                    self._add_dropdown_open = False
                else:
                    self.editor.node_editing_mode = False
                return True
            mods = pygame.key.get_mods()
            if mods & (
                pygame.KMOD_LCTRL
                | pygame.KMOD_RCTRL
                | pygame.KMOD_LMETA
                | pygame.KMOD_RMETA
            ):
                if event.key == pygame.K_d:
                    mgr = self.editor.node_manager
                    if mgr.active_node_id is not None:
                        self._duplicate_node(mgr.active_node_id)
                    return True
            if event.key == pygame.K_BACKSPACE:
                self.search_text = self.search_text[:-1]
                self._rebuild_filter()
                return True
            if event.key == pygame.K_RETURN:
                rows = self._filtered_rows
                if rows:
                    mgr = self.editor.node_manager
                    if rows[0]["type"] == "group":
                        mgr.set_active_group(rows[0]["name"])
                    else:
                        mgr.set_active_node(rows[0]["node_id"])
                return True
            if event.unicode and event.unicode.isprintable():
                self.search_text += event.unicode
                self._rebuild_filter()
                return True
            # Anything else (function keys, arrows, Delete, Ctrl+combos)
            # belongs to the editor dispatch chain, not the search field.
            return False

        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(mouse_pos):
                list_rect = self._list_rect()
                max_scroll = max(
                    0, len(self._filtered_rows) * self.item_h - list_rect.height
                )
                self.scroll_offset = max(
                    0, min(max_scroll, self.scroll_offset - event.y * self.item_h)
                )
                return True

        return False

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return

        draw_panel(
            screen,
            self.rect,
            bg=COLORS.panel,
            border=COLORS.border,
            radius=SHAPE.radius_sm,
        )

        header = self.font_bold.render(
            f"Nodes ({len(self.editor.node_manager.nodes)})", True, COLORS.text
        )
        screen.blit(header, (self.rect.x + 8, self.rect.y + 6))

        toggle_rect = self._collapse_toggle_rect()
        toggle_bg = COLORS.hover if self.collapse_all_hover else COLORS.panel_alt
        pygame.draw.rect(screen, toggle_bg, toggle_rect, border_radius=SHAPE.radius_sm)
        pygame.draw.rect(
            screen, COLORS.border_soft, toggle_rect, 1, border_radius=SHAPE.radius_sm
        )
        toggle_lbl = self.font_bold.render(
            "+" if self._all_collapsed() else "-", True, COLORS.text
        )
        screen.blit(toggle_lbl, toggle_lbl.get_rect(center=toggle_rect.center))

        add_btn = self._add_button_rect()
        btn_bg = COLORS.accent if self.add_btn_hover else COLORS.panel_alt
        pygame.draw.rect(screen, btn_bg, add_btn, border_radius=SHAPE.radius_sm)
        pygame.draw.rect(
            screen, COLORS.border_soft, add_btn, 1, border_radius=SHAPE.radius_sm
        )
        btn_label = self.font.render("+ Add Node", True, COLORS.text)
        screen.blit(btn_label, btn_label.get_rect(center=add_btn.center))

        search_rect = self._search_rect()
        pygame.draw.rect(
            screen, COLORS.panel_alt, search_rect, border_radius=SHAPE.radius_sm
        )
        pygame.draw.rect(
            screen, COLORS.border_soft, search_rect, 1, border_radius=SHAPE.radius_sm
        )

        display = self.search_text if self.search_text else "Search..."
        color = COLORS.text if self.search_text else COLORS.text_dim
        txt = self.font.render(display, True, color)
        screen.blit(txt, (search_rect.x + 6, search_rect.y + 5))

        list_rect = self._list_rect()
        clip = screen.get_clip()
        screen.set_clip(list_rect)

        item_y = list_rect.y - self.scroll_offset
        mgr = self.editor.node_manager

        for i, row in enumerate(self._filtered_rows):
            if self.is_dragging and self.dragged_item_idx == i:
                y_pos = item_y + i * self.item_h
                if y_pos + self.item_h >= list_rect.y and y_pos <= list_rect.bottom:
                    placeholder_rect = Rect(
                        list_rect.x, y_pos, list_rect.width, self.item_h
                    )

                    pygame.draw.rect(
                        screen,
                        COLORS.hover,
                        placeholder_rect,
                        1,
                        border_radius=SHAPE.radius_sm,
                    )
                continue

            y_pos = item_y + i * self.item_h
            if y_pos + self.item_h < list_rect.y or y_pos > list_rect.bottom:
                continue

            item_rect = Rect(list_rect.x, y_pos, list_rect.width, self.item_h)
            is_hover = self.hover_idx == i

            if row["type"] == "group":
                is_active = mgr.active_group_name == row["name"]
                bg = (
                    COLORS.accent_active
                    if is_active
                    else (COLORS.hover if is_hover else COLORS.panel)
                )
                pygame.draw.rect(screen, bg, item_rect, border_radius=SHAPE.radius_sm)

                collapsed = row["name"] in self.collapsed_groups
                arrow_color = (
                    COLORS.text if self.arrow_hover and is_hover else COLORS.text_dim
                )
                self._draw_arrow(
                    screen, item_rect.x + 4, item_rect.y + 10, collapsed, arrow_color
                )

                folder_color = (220, 180, 80)
                self._draw_folder_icon(
                    screen, item_rect.x + 16, item_rect.y + 9, folder_color
                )

                lbl_text = f"{row['name']} ({row['nodes_count']})"
                lbl_color = COLORS.text_on_accent if is_active else COLORS.text
                lbl = self.font.render(lbl_text, True, lbl_color)
                screen.blit(lbl, (item_rect.x + 32, item_rect.y + 6))

            else:
                node = mgr.get_node(row["node_id"])
                if node is None:
                    continue

                is_active = mgr.active_node_id == row["node_id"]
                bg = (
                    COLORS.accent_active
                    if is_active
                    else (COLORS.hover if is_hover else COLORS.panel)
                )
                pygame.draw.rect(screen, bg, item_rect, border_radius=SHAPE.radius_sm)

                indent_offset = 16 if row["indent"] else 0
                bullet_color = self.NODE_TYPE_COLORS.get(node.node_type, (80, 220, 120))
                pygame.draw.circle(
                    screen,
                    bullet_color,
                    (item_rect.x + indent_offset + 10, item_rect.centery),
                    4,
                )

                lbl_color = COLORS.text_on_accent if is_active else COLORS.text
                lbl = self.font.render(node.name, True, lbl_color)
                screen.blit(lbl, (item_rect.x + indent_offset + 20, item_rect.y + 6))

            if is_hover:
                dup_rect, _ = self._row_action_rects(item_rect)
                dup_color = COLORS.text if self.dup_hover else COLORS.text_dim
                bx = dup_rect.centerx - 4
                by = dup_rect.centery - 4
                back = Rect(bx + 3, by - 1, 7, 7)
                front = Rect(bx, by + 2, 7, 7)
                pygame.draw.rect(screen, COLORS.panel, back)
                pygame.draw.rect(screen, dup_color, back, 1)
                pygame.draw.rect(screen, COLORS.panel, front)
                pygame.draw.rect(screen, dup_color, front, 1)

                _, del_rect = self._row_action_rects(item_rect)
                del_color = COLORS.danger if self.delete_hover else COLORS.text_dim
                del_txt = self.font_bold.render("×", True, del_color)
                screen.blit(del_txt, del_txt.get_rect(center=del_rect.center))

        screen.set_clip(clip)

        if self.is_dragging and self.dragged_item_idx is not None:
            drag_row = self._filtered_rows[self.dragged_item_idx]
            mouse_pos = pygame.mouse.get_pos()
            preview_y = mouse_pos[1] - self.dragged_item_y_offset
            preview_rect = Rect(list_rect.x, preview_y, list_rect.width, self.item_h)

            drag_surf = pygame.Surface(
                (preview_rect.width, preview_rect.height), pygame.SRCALPHA
            )

            drag_surf.fill((*COLORS.accent_active, 180))
            screen.blit(drag_surf, preview_rect)
            pygame.draw.rect(
                screen, COLORS.text, preview_rect, 1, border_radius=SHAPE.radius_sm
            )

            if drag_row["type"] == "group":
                self._draw_folder_icon(
                    screen, preview_rect.x + 16, preview_rect.y + 9, (220, 180, 80)
                )
                lbl_text = f"{drag_row['name']} ({drag_row['nodes_count']})"
            else:
                node = mgr.get_node(drag_row["node_id"])
                lbl_text = node.name if node else "Node"
                bullet_color = (
                    self.NODE_TYPE_COLORS.get(node.node_type, (80, 220, 120))
                    if node
                    else (80, 220, 120)
                )
                pygame.draw.circle(
                    screen, bullet_color, (preview_rect.x + 10, preview_rect.centery), 4
                )

            txt_lbl = self.font.render(lbl_text, True, (255, 255, 255))
            screen.blit(
                txt_lbl,
                (
                    preview_rect.x + 32
                    if drag_row["type"] == "group"
                    else preview_rect.x + 20,
                    preview_rect.y + 6,
                ),
            )

        if self._add_dropdown_open:
            dropdown_items = self._add_dropdown_items()

            r_first = dropdown_items[0][3]
            r_last = dropdown_items[-1][3]
            overlay_rect = Rect(
                r_first.x, r_first.y, r_first.width, r_last.bottom - r_first.top
            )

            draw_panel(
                screen,
                overlay_rect,
                bg=COLORS.panel_alt,
                border=COLORS.border,
                radius=SHAPE.radius_sm,
            )

            for idx, (t_name, t_label, t_color, r) in enumerate(dropdown_items):
                opt_hover = self._add_dropdown_hover_idx == idx
                if opt_hover:
                    pygame.draw.rect(
                        screen, COLORS.hover, r, border_radius=SHAPE.radius_sm
                    )

                if t_name == "group":
                    self._draw_folder_icon(screen, r.x + 6, r.y + 8, t_color)
                else:
                    pygame.draw.circle(screen, t_color, (r.x + 10, r.centery), 4)

                opt_lbl = self.font.render(t_label, True, COLORS.text)
                screen.blit(opt_lbl, (r.x + 20, r.y + 5))
