from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import pygame
from pygame import Rect, Surface

from utils.icon_manager import icon_manager

from ..input import InlineTextInput
from ..widget_base import WidgetBase
from .draw_utils import truncate_text
from .theme import COLORS, FONTS


class DropZone(Enum):
    ABOVE = auto()
    INSIDE = auto()
    BELOW = auto()


@dataclass
class TreeNode:
    id: str
    label: str
    is_folder: bool = False
    collapsed: bool = False
    icon_key: str | None = None
    data: Any = None

    children: list[TreeNode] = field(default_factory=list)
    parent: TreeNode | None = field(default=None, repr=False)

    def add_child(self, child: TreeNode):
        if child.parent:
            child.parent.remove_child(child)
        child.parent = self
        self.children.append(child)

    def insert_child(self, index: int, child: TreeNode):
        if child.parent:
            child.parent.remove_child(child)
        child.parent = self
        self.children.insert(index, child)

    def remove_child(self, child: TreeNode):
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def is_descendant_of(self, ancestor: TreeNode) -> bool:
        current = self.parent
        while current:
            if current == ancestor:
                return True
            current = current.parent
        return False


class TreeWidget(WidgetBase):
    class State(Enum):
        IDLE = auto()
        PRESSED = auto()
        DRAGGING = auto()

    def __init__(self, rect):
        super().__init__(rect, padding=0)

        self.roots: list[TreeNode] = []
        self._flat_cache: list[dict[str, Any]] = []
        self._cache_valid = False

        self.selected_ids: set[str] = set()
        self._hover_id: str | None = None

        self._state = self.State.IDLE
        self._drag_start_pos = (0, 0)
        self._drag_current_pos = (0, 0)
        self._drag_threshold = 5
        self._dragging_nodes: list[TreeNode] = []
        self._drop_target_node: TreeNode | None = None
        self._drop_target_zone: DropZone | None = None

        self.item_height = 28
        self.indent_width = 20
        self.arrow_width = 18
        self.scroll_y = 0
        self._last_drop_time = 0.0

        self.font = FONTS.get_medium_font()

        self.on_selection_changed: Callable[[list[str]], None] | None = None
        self.on_item_activated: Callable[[str], None] | None = None
        self.on_item_context: Callable[[str], None] | None = None
        self.on_structure_changed: Callable[[], None] | None = None
        self.on_rename_committed: Callable[[str, str], None] | None = None
        self.on_delete_requested: Callable[[list[str]], None] | None = None

        self._rename_id: str | None = None
        self._rename_input: InlineTextInput | None = None
        self._hovered_truncated: str | None = None

    def set_data(self, roots: list[TreeNode]):
        seen = set()
        clean_roots = []
        for node in roots:
            if node.id not in seen:
                seen.add(node.id)
                clean_roots.append(node)
            else:
                node.parent = None
                node.children = []

        self.roots = clean_roots
        self._invalidate_cache()

    def _invalidate_cache(self):
        self._cache_valid = False
        if self.on_structure_changed:
            self.on_structure_changed()

    def find_node(self, node_id: str) -> TreeNode | None:
        def search(nodes):
            for n in nodes:
                if n.id == node_id:
                    return n
                res = search(n.children)
                if res:
                    return res
            return None

        return search(self.roots)

    # -- inline rename -----------------------------------------------------
    def begin_rename(self, node_id: str) -> bool:
        """Start inline editing of a node's label. Returns False if unknown."""
        node = self.find_node(node_id)
        if node is None:
            return False
        self._rename_id = node_id
        self._rename_input = InlineTextInput("tree_rename", node.label)
        self._rename_input.cursor_pos = len(node.label)
        self._rename_input.select_all()
        self._rename_input.is_focused = True
        return True

    def cancel_rename(self) -> None:
        self._rename_id = None
        self._rename_input = None

    def _commit_rename(self) -> None:
        node = self.find_node(self._rename_id) if self._rename_id else None
        new_label = (self._rename_input.text or "").strip() if self._rename_input else ""
        if node is not None and new_label and new_label != node.label:
            node.label = new_label
            if self.on_rename_committed:
                self.on_rename_committed(node.id, new_label)
            self._invalidate_cache()
        self.cancel_rename()

    def _get_depth(self, node: TreeNode) -> int:
        depth = 0
        curr = node.parent
        while curr:
            depth += 1
            curr = curr.parent
        return depth

    def _build_flat_cache(self):
        self._flat_cache = []

        def walk(nodes, depth):
            for node in nodes:
                self._flat_cache.append({"node": node, "depth": depth})
                if node.is_folder and not node.collapsed:
                    walk(node.children, depth + 1)

        walk(self.roots, 0)
        self._cache_valid = True

    def _hit_test(self, pos: tuple[int, int]) -> tuple[TreeNode | None, DropZone | None]:
        if not self._cache_valid:
            self._build_flat_cache()
        if not self.rect.collidepoint(pos):
            return None, None

        rel_y = pos[1] - self.rect.y + self.scroll_y
        idx = int(rel_y // self.item_height)

        if 0 <= idx < len(self._flat_cache):
            node = self._flat_cache[idx]["node"]
            local_y = rel_y - (idx * self.item_height)

            if local_y < self.item_height * 0.25:
                return node, DropZone.ABOVE
            if local_y > self.item_height * 0.75:
                return node, DropZone.BELOW
            if node.is_folder:
                return node, DropZone.INSIDE
            return node, DropZone.BELOW
        return None, None

    def _is_valid_drop(self, target_node: TreeNode | None, zone: DropZone) -> bool:
        if not target_node:
            return True

        for drag_node in self._dragging_nodes:
            if drag_node == target_node:
                return False
            if target_node.is_descendant_of(drag_node):
                return False
            if zone == DropZone.INSIDE and not target_node.is_folder:
                return False
        return True

    def _execute_drop(self):
        if not self._dragging_nodes:
            return

        def _remove_node(node: TreeNode):
            if node.parent:
                node.parent.remove_child(node)
            else:
                while node in self.roots:
                    self.roots.remove(node)

        if not self._drop_target_node and self._drop_target_zone is None:
            for node in self._dragging_nodes:
                _remove_node(node)
                self.roots.append(node)
                node.parent = None
            self._invalidate_cache()
            return

        target = self._drop_target_node
        zone = self._drop_target_zone

        if not target:
            return

        for node in self._dragging_nodes:
            _remove_node(node)

        if zone == DropZone.INSIDE:
            for node in self._dragging_nodes:
                target.add_child(node)
        else:
            parent = target.parent
            siblings = parent.children if parent else self.roots

            try:
                base_idx = siblings.index(target)
            except ValueError:
                base_idx = len(siblings)

            offset = 0
            for node in self._dragging_nodes:
                insert_idx = base_idx + offset + (1 if zone == DropZone.BELOW else 0)
                if parent:
                    parent.insert_child(insert_idx, node)
                else:
                    self.roots.insert(insert_idx, node)
                offset += 1

        self._invalidate_cache()

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse = event.pos if hasattr(event, "pos") else pygame.mouse.get_pos()
        in_bounds = self.rect.collidepoint(mouse)

        if event.type == pygame.MOUSEWHEEL and in_bounds:
            max_scroll = max(0, len(self._flat_cache) * self.item_height - self.rect.height)
            self.scroll_y = max(0, min(self.scroll_y - event.y * 30, max_scroll))
            return True

        if event.type == pygame.KEYDOWN:
            if self._rename_id is not None:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._commit_rename()
                elif event.key == pygame.K_ESCAPE:
                    self.cancel_rename()
                else:
                    self._rename_input.handle_event(event, self.font)
                return True

            if self._state == self.State.DRAGGING and event.key == pygame.K_ESCAPE:
                self._state = self.State.IDLE
                self._dragging_nodes = []
                return True

            if (
                event.key in (pygame.K_DELETE, pygame.K_BACKSPACE)
                and self.selected_ids
                and self.on_delete_requested
            ):
                self.on_delete_requested(sorted(self.selected_ids))
                return True
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._rename_id is not None:
                self._commit_rename()
                return True
            if not in_bounds:
                return False

            now = pygame.time.get_ticks()
            if now - self._last_drop_time < 200:
                self._state = self.State.IDLE
                return True

            node, zone = self._hit_test(mouse)

            if node:
                depth = self._get_depth(node)
                arrow_x = self.rect.x + depth * self.indent_width

                if node.is_folder and (arrow_x <= mouse[0] <= arrow_x + self.arrow_width):
                    node.collapsed = not node.collapsed
                    self._invalidate_cache()
                    return True

                mods = pygame.key.get_mods()
                ctrl = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)
                shift = mods & pygame.KMOD_SHIFT

                if ctrl:
                    if node.id in self.selected_ids:
                        self.selected_ids.remove(node.id)
                    else:
                        self.selected_ids.add(node.id)
                elif shift and self.selected_ids:
                    self.selected_ids.add(node.id)
                else:
                    if node.id not in self.selected_ids:
                        self.selected_ids = {node.id}

                if self.on_selection_changed:
                    self.on_selection_changed(list(self.selected_ids))

                self._state = self.State.PRESSED
                self._drag_start_pos = mouse
                self._dragging_nodes = [self.find_node(nid) for nid in self.selected_ids if self.find_node(nid)]
            else:
                self.selected_ids.clear()
                if self.on_selection_changed:
                    self.on_selection_changed([])
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self._rename_id is not None:
                self._commit_rename()
                return True
            if not in_bounds:
                return False
            node, _ = self._hit_test(mouse)
            if node:
                if node.id not in self.selected_ids:
                    self.selected_ids = {node.id}
                    if self.on_selection_changed:
                        self.on_selection_changed(list(self.selected_ids))
                if self.on_item_context:
                    self.on_item_context(node.id)
            return node is not None

        if event.type == pygame.MOUSEMOTION:
            self._drag_current_pos = mouse

            if self._state == self.State.PRESSED:
                dx = abs(mouse[0] - self._drag_start_pos[0])
                dy = abs(mouse[1] - self._drag_start_pos[1])
                if dx > self._drag_threshold or dy > self._drag_threshold:
                    self._state = self.State.DRAGGING

            if self._state == self.State.DRAGGING:
                node, zone = self._hit_test(mouse)
                if self._is_valid_drop(node, zone):
                    self._drop_target_node = node
                    self._drop_target_zone = zone
                else:
                    self._drop_target_node = None
                    self._drop_target_zone = None

                max_scroll = max(0, len(self._flat_cache) * self.item_height - self.rect.height)
                if mouse[1] < self.rect.y + 30:
                    self.scroll_y = max(0, self.scroll_y - 5)
                elif mouse[1] > self.rect.bottom - 30:
                    self.scroll_y = min(max_scroll, self.scroll_y + 5)
                return True

            if in_bounds:
                node, _ = self._hit_test(mouse)
                self._hover_id = node.id if node else None
            else:
                self._hover_id = None
            return False

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            consumed = self._state != self.State.IDLE

            if self._state == self.State.DRAGGING:
                self._execute_drop()
                self._last_drop_time = pygame.time.get_ticks()
            elif self._state == self.State.PRESSED:
                node, _ = self._hit_test(mouse)
                if node and self.on_item_activated:
                    self.on_item_activated(node.id)
                self._last_drop_time = pygame.time.get_ticks()

            self._state = self.State.IDLE
            self._dragging_nodes = []
            self._drop_target_node = None
            self._drop_target_zone = None
            return consumed
        return None

    def draw(self, screen: Surface) -> None:
        self.draw_base(screen)
        if not self._cache_valid:
            self._build_flat_cache()

        self._hovered_truncated = None
        clip = screen.get_clip()
        screen.set_clip(self.rect)

        for i, item in enumerate(self._flat_cache):
            node = item["node"]
            depth = item["depth"]

            y = self.rect.y + i * self.item_height - self.scroll_y
            if y + self.item_height < self.rect.y or y > self.rect.bottom:
                continue

            row_rect = Rect(self.rect.x, y, self.rect.width, self.item_height)
            is_selected = node.id in self.selected_ids
            is_hover = node.id == self._hover_id

            if is_selected:
                pygame.draw.rect(screen, COLORS.selected, row_rect)
            elif is_hover:
                pygame.draw.rect(screen, COLORS.hover, row_rect)

            x = self.rect.x + depth * self.indent_width

            if node.is_folder:
                arrow_key = "fold_down_arrow" if not node.collapsed else "unfold_right_arrow"
                arrow_icon = icon_manager.get_icon(arrow_key, 12, COLORS.text_dim)
                arrow_y = y + (self.item_height - 12) // 2
                screen.blit(arrow_icon, (x + 2, arrow_y))

            icon_x = x + self.arrow_width
            if node.is_folder:
                folder_icon = icon_manager.get_icon("folder", 16, COLORS.text)
                icon_y = y + (self.item_height - 16) // 2
                screen.blit(folder_icon, (icon_x, icon_y))
            elif node.icon_key:
                icon = icon_manager.get_icon(node.icon_key, 16, COLORS.text)
                icon_y = y + (self.item_height - 16) // 2
                screen.blit(icon, (icon_x, icon_y))
            else:
                icon_x -= 4

            label_x = icon_x + 20
            if node.id == self._rename_id and self._rename_input is not None:
                self._draw_rename_editor(screen, row_rect, label_x)
            else:
                lbl_color = COLORS.text_on_accent if is_selected else COLORS.text
                max_w = max(0, row_rect.right - label_x - 8)
                display, was_truncated = truncate_text(node.label, self.font, max_w)
                if is_hover and was_truncated:
                    self._hovered_truncated = node.label
                label_surf = self.font.render(display, True, lbl_color)
                label_y = y + (self.item_height - label_surf.get_height()) // 2
                screen.blit(label_surf, (label_x, label_y))

        if self._state == self.State.DRAGGING and self._drop_target_node:
            target_idx = next((i for i, it in enumerate(self._flat_cache) if it["node"] == self._drop_target_node), -1)
            if target_idx != -1:
                y = self.rect.y + target_idx * self.item_height - self.scroll_y
                if self._drop_target_zone == DropZone.INSIDE:
                    drop_rect = Rect(self.rect.x, y, self.rect.width, self.item_height)
                    s = pygame.Surface((drop_rect.width, drop_rect.height), pygame.SRCALPHA)
                    s.fill((*COLORS.accent, 40))
                    screen.blit(s, drop_rect)
                else:
                    line_y = y if self._drop_target_zone == DropZone.ABOVE else y + self.item_height
                    pygame.draw.line(screen, COLORS.accent, (self.rect.x, line_y), (self.rect.right, line_y), 2)
        elif self._state == self.State.DRAGGING and not self._drop_target_node:
            pygame.draw.line(screen, COLORS.accent, (self.rect.x, self.rect.y), (self.rect.right, self.rect.y), 2)

        total_h = len(self._flat_cache) * self.item_height
        if total_h > self.rect.height:
            scroll_pct = self.scroll_y / (total_h - self.rect.height)
            bar_h = max(20, self.rect.height * (self.rect.height / total_h))
            bar_y = self.rect.y + scroll_pct * (self.rect.height - bar_h)
            pygame.draw.rect(screen, COLORS.border, Rect(self.rect.right - 6, bar_y, 4, bar_h), border_radius=2)

        if self._state == self.State.DRAGGING and self._dragging_nodes:
            count = len(self._dragging_nodes)
            w, h = 180, 36
            ghost = pygame.Surface((w, h), pygame.SRCALPHA)
            ghost.fill((*COLORS.accent, 200))
            pygame.draw.rect(ghost, COLORS.text, (0, 0, w, h), 2)

            if count > 1:
                pygame.draw.rect(ghost, (*COLORS.accent, 100), (4, 4, w, h), 2)
                pygame.draw.rect(ghost, (*COLORS.accent, 50), (8, 8, w, h), 2)
                label = f"{count} items"
            else:
                raw = self._dragging_nodes[0].label
                label, _ = truncate_text(raw, self.font, w - 24)

            txt = self.font.render(label, True, COLORS.text_on_accent)
            ghost.blit(txt, (12, (h - txt.get_height()) // 2))
            screen.blit(ghost, (self._drag_current_pos[0] + 15, self._drag_current_pos[1] + 15))

        screen.set_clip(clip)

    def _draw_rename_editor(self, screen: Surface, row_rect: Rect, label_x: float) -> None:
        inp = self._rename_input
        box = Rect(
            int(label_x),
            row_rect.y + 3,
            int(self.rect.right - label_x - 8),
            self.item_height - 6,
        )
        pygame.draw.rect(screen, COLORS.panel, box)
        pygame.draw.rect(screen, COLORS.accent if inp.is_focused else COLORS.border, box, 1)

        clip = screen.get_clip()
        screen.set_clip(box)
        txt = self.font.render(inp.text, True, COLORS.text)
        screen.blit(txt, (box.x + 4, box.y + (box.height - txt.get_height()) // 2))
        cursor_x = box.x + 4 + self.font.size(inp.text[: inp.cursor_pos])[0]
        if pygame.time.get_ticks() // 500 % 2 == 0 and cursor_x < box.right - 2:
            pygame.draw.line(screen, COLORS.text, (cursor_x, box.y + 2), (cursor_x, box.bottom - 3), 1)
        screen.set_clip(clip)
