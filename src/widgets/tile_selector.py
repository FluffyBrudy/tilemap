from pathlib import Path
from typing import TYPE_CHECKING, Any

import pygame
from pygame import Rect

from utils.context_dispatch import ContextKind, PropertyContext
from utils.error_handler import error_handler
from utils.tileset_hierarchy import (
    FolderEntry,
    ItemEntry,
    TilesetHierarchy,
    load_hierarchy,
    relative_path,
    save_hierarchy,
)
from utils.validation import is_image_multipleof
from widgets.ui.button import Button
from widgets.ui.property_editor import PropertyEditor
from widgets.ui.theme import COLORS, FONTS
from widgets.ui.tree_widget import TreeNode, TreeWidget
from widgets.widget_base import WidgetBase

if TYPE_CHECKING:
    from editor import Editor


class TilesetData:
    _next_uid: int = 0

    def __init__(self, name: str, path: Path, surface: pygame.Surface, tileset_type: str = "tile"):
        self.uid: str = f"ts_{TilesetData._next_uid}"
        TilesetData._next_uid += 1
        self.name = name
        self.path = path
        self.surface = surface
        self.tileset_type = tileset_type
        self.offset = [0, 0]
        self.properties: dict[str, Any] = {}

        self.tile_properties: dict[int, dict[str, Any]] = {}
        self.object_collision_path: Path | None = None
        self.object_collision_data: dict[str, Any] | None = None
        self.animation: dict | None = None


class TileSelector(WidgetBase):
    TREE_W = 140
    TREE_W_MIN = 100
    TREE_W_MAX = 320
    DIVIDER_W = 6

    def __init__(self, editor: "Editor", x: int, y: int, w: int, h: int):
        super().__init__(Rect(x, y, w, h))
        self.editor = editor
        self.tilesets: list[TilesetData] = []
        self.tileset_map: dict[int, TilesetData] = {}

        self._tree_w = self.TREE_W
        self._tree_dragging = False
        self._tree = TreeWidget(Rect(x, y, self._tree_w, h - 28))
        self._tree.on_selection_changed = self._on_tree_selection
        self._tree.on_item_activated = self._on_tree_activate
        self._tree.on_item_context = self._on_tree_context
        self._tree.on_structure_changed = self._on_tree_structure_changed
        self._tree.on_rename_committed = self._on_node_renamed
        self._tree.on_delete_requested = self._on_tree_delete_requested

        self._folder_btn = Button(
            Rect(x, h - 26, self._tree_w, 24),
            "+ Folder",
            font=FONTS.get_small_font(),
            on_click=self._add_folder,
        )

        self.view_rect = Rect(x + self._tree_w, y, w - self._tree_w, h)
        self.is_panning = False
        self.pan_start = (0, 0)
        self.pan_start_offset = (0, 0)

        self.is_selecting = False
        self.selection_start_grid: tuple[int, int] | None = None
        self.hover_pos: tuple[int, int] | None = None
        self.selected_tile: tuple[int, int, int, int] | None = None

        self.active_idx = -1
        self.rule_hints: set[int] = set()
        self._folder_id_counter = 0

        self._hierarchy: TilesetHierarchy | None = None
        self._placement: dict[str, str] = {}
        data_root = getattr(self.editor, "data_root", None)
        if data_root is not None:
            loaded = load_hierarchy(Path(data_root))
            if loaded is not None:
                self._hierarchy = loaded
                self._placement = loaded.placement_map()

        self._pending_tileset_queue: list[tuple[Path, pygame.Surface]] = []
        self._queue_timer_active = False

        self.zoom: float = 1.0
        self.font = FONTS.get_medium_font()

        self._register_context_handlers()

    def _register_context_handlers(self):
        d = self.editor.context_dispatch
        d.register_opener(ContextKind.TILESET, self._open_tileset_properties)
        d.register_saver(ContextKind.TILESET, self._save_tileset_properties)
        d.register_opener(ContextKind.TILE_VARIANT, self._open_tile_variant_properties)
        d.register_saver(ContextKind.TILE_VARIANT, self._save_tile_properties_multi)
        d.register_opener(ContextKind.MAP_OBJECT, self._open_object_properties)
        d.register_saver(ContextKind.MAP_OBJECT, self._save_object_properties)

    def _add_folder(self) -> None:
        self._folder_id_counter += 1
        folder = TreeNode(
            id=self._next_folder_id(),
            label=f"Folder {self._folder_id_counter}",
            is_folder=True,
        )
        self._tree.roots.append(folder)
        self._tree.set_data(self._tree.roots)
        self._tree.selected_ids = {folder.id}
        self._save_hierarchy()
        self._tree.begin_rename(folder.id)

    def _ts_node(self, node_id: str) -> TilesetData | None:
        # Identity first: node ids are TilesetData.uid values, which stay
        # stable across index shifts.  The legacy node.data index is only
        # a fallback -- trusting it after a removal silently selected a
        # *different* surviving tileset.
        for ts in self.tilesets:
            if ts.uid == node_id:
                return ts
        node = self._tree.find_node(node_id)
        if node and isinstance(node.data, int) and 0 <= node.data < len(self.tilesets):
            return self.tilesets[node.data]
        return None

    def _frame_aware_object_selected_tile(self, ts) -> tuple[int, int, int, int]:
        """Return frame-sized selected_tile for object tilesets, full surface otherwise."""
        if ts.tileset_type == "object":
            if ts.animation and "frame_w" in ts.animation and "frame_h" in ts.animation:
                return (0, 0, ts.animation["frame_w"], ts.animation["frame_h"])
            elif (
                ts.animation
                and ts.animation.get("frame_count", 1) > 1
                and ts.surface.get_width() % ts.animation["frame_count"] == 0
            ):
                fw = ts.surface.get_width() // ts.animation["frame_count"]
                return (0, 0, fw, ts.surface.get_height())
        return (0, 0, ts.surface.get_width(), ts.surface.get_height())

    def _on_tree_selection(self, selected_ids: list[str]) -> None:
        if not selected_ids:
            return
        ts = self._ts_node(selected_ids[0])
        if ts is None:
            return
        self.active_idx = self.tilesets.index(ts)
        if ts.tileset_type == "object":
            self.selected_tile = self._frame_aware_object_selected_tile(ts)
        else:
            self.selected_tile = None
        self.rule_hints.clear()

    def _on_tree_activate(self, item_id: str) -> None:
        self._on_tree_selection([item_id])

    def _on_tree_context(self, item_id: str) -> None:
        ts = self._ts_node(item_id)
        if ts is None:
            return
        self.editor.context_dispatch.open(PropertyContext(ContextKind.TILESET, ts))

    def _open_tileset_properties(self, ctx: PropertyContext) -> None:
        ts = ctx.target
        self.editor.property_editor = PropertyEditor(
            self.editor,
            f"Tileset Properties: {ts.name}",
            ts.properties,
            context=ctx,
        )

    def _open_tile_variant_properties(self, ctx: PropertyContext) -> None:
        ts = ctx.target
        variant_ids = ctx.extra.get("variant_ids", [])
        if not variant_ids:
            return
        variant_id = variant_ids[0]
        self.editor.property_editor = PropertyEditor(
            self.editor,
            f"Tile Properties: {ts.name} (ID: {variant_id})",
            ts.tile_properties.get(variant_id, {}),
            context=ctx,
        )

    def _open_object_properties(self, ctx: PropertyContext) -> None:
        obj = ctx.target
        if obj is None:
            return
        title = f"Object Properties: {ctx.extra.get('layer_name', '')} #{ctx.extra.get('obj_id', '?')}"
        ts_name = ctx.extra.get("tileset_name")
        if ts_name:
            title = f"{title} ({ts_name})"
        props = dict(obj.get("properties", {}))
        generated_anim_keys = set()
        anim_editor_map: dict[str, str] = {}
        if "animation" in obj and isinstance(obj["animation"], dict):
            for k, v in obj["animation"].items():
                gen_key = f"anim_{k}"
                base_key = gen_key
                counter = 0
                while gen_key in props:
                    counter += 1
                    gen_key = f"{base_key}_{counter}"
                props[gen_key] = v
                generated_anim_keys.add(gen_key)
                anim_editor_map[gen_key] = k
        ctx.extra["generated_anim_keys"] = generated_anim_keys
        ctx.extra["anim_editor_map"] = anim_editor_map
        self.editor.property_editor = PropertyEditor(
            self.editor,
            title,
            props,
            context=ctx,
        )

    def _save_object_properties(self, ctx: PropertyContext, props: dict) -> None:
        obj = ctx.target
        if obj is None:
            return
        orig_props = obj.get("properties", {})
        generated_anim_keys = ctx.extra.get("generated_anim_keys")
        anim_editor_map = ctx.extra.get("anim_editor_map")
        if generated_anim_keys is None:
            generated_anim_keys = (
                {f"anim_{k}" for k in obj.get("animation", {})} if isinstance(obj.get("animation"), dict) else set()
            )
        if anim_editor_map is None:
            anim_editor_map = {k: k[5:] for k in generated_anim_keys}
        # known ObjectAnimation fields for newly added anim_* keys
        known_anim_keys = {
            "frame_count",
            "frame_duration_ms",
            "speed",
            "loop",
            "animation_mode",
            "random_phase",
            "frames",
        }
        obj_props = {}
        anim_overrides = {}
        for k, v in props.items():
            if k in anim_editor_map:
                anim_key = anim_editor_map[k]
                anim_overrides[anim_key] = v
            elif k in generated_anim_keys:
                anim_key = k[5:]
                anim_overrides[anim_key] = v
            elif k.startswith("anim_") and k[5:] in known_anim_keys and k not in orig_props:
                # newly added valid animation key (e.g., anim_random_phase) -> animation
                anim_key = k[5:]
                anim_overrides[anim_key] = v
            else:
                obj_props[k] = v
        obj["properties"] = obj_props
        if anim_overrides:
            obj["animation"] = anim_overrides
        elif "animation" in obj:
            del obj["animation"]
        self.editor.suggestion_registry.refresh(self.editor)

    def _on_tree_structure_changed(self) -> None:
        self._save_hierarchy()

    def _on_node_renamed(self, node_id: str, new_label: str) -> None:
        self._save_hierarchy()

    def _data_root(self) -> Path | None:
        root = getattr(self.editor, "data_root", None)
        return Path(root) if root else None

    def _next_folder_id(self) -> str:
        nums = []
        for n in self._walk_all(self._tree.roots):
            if n.is_folder and n.id.startswith("f_"):
                try:
                    nums.append(int(n.id.split("_", 1)[1]))
                except ValueError:
                    continue
        return f"f_{max(nums, default=0) + 1}"

    def _ensure_folder_nodes(self) -> tuple[dict[str, TreeNode], list[TreeNode]]:
        """Create TreeNodes for every folder defined in the hierarchy file.

        Returns (nodes by id, newly created root-level nodes). Callers must
        merge the new roots into the list they pass to ``set_data``.
        """
        if self._hierarchy is None:
            return {}, []
        existing = {n.id: n for n in self._walk_all(self._tree.roots) if n.is_folder}
        nodes: dict[str, TreeNode] = {}
        new_roots: list[TreeNode] = []

        def attach(node: TreeNode, parent_id: str | None) -> None:
            parent_node = nodes.get(parent_id) if parent_id else None
            if parent_node is not None:
                parent_node.add_child(node)
            else:
                new_roots.append(node)

        pending = list(self._hierarchy.folders)
        while pending:
            progressed = False
            for f in list(pending):
                if f.parent is not None and f.parent not in nodes and any(p.id == f.parent for p in pending):
                    continue
                node = existing.get(f.id)
                if node is None:
                    node = TreeNode(id=f.id, label=f.name or "Folder", is_folder=True)
                    attach(node, f.parent)
                pending.remove(f)
                nodes[f.id] = node
                progressed = True
            if not progressed:
                for f in pending:
                    node = existing.get(f.id)
                    if node is None:
                        node = TreeNode(id=f.id, label=f.name or "Folder", is_folder=True)
                        attach(node, None)
                    nodes[f.id] = node
                break
        return nodes, new_roots

    def _sync_tree(self) -> None:
        uid_to_idx = {ts.uid: i for i, ts in enumerate(self.tilesets)}

        def walk(nodes):
            kept: list[TreeNode] = []
            for n in nodes:
                if n.is_folder:
                    n.children = walk(n.children)
                    kept.append(n)
                elif n.id in uid_to_idx:
                    n.data = uid_to_idx[n.id]
                    n.label = self.tilesets[uid_to_idx[n.id]].name
                    kept.append(n)
            return kept

        roots = walk(self._tree.roots)
        existing = {n.id for n in self._walk_all(roots) if not n.is_folder}

        folder_nodes, new_folder_roots = self._ensure_folder_nodes()
        roots.extend(new_folder_roots)
        data_root = self._data_root()

        for ts in self.tilesets:
            if ts.uid in existing:
                continue
            node = TreeNode(
                id=ts.uid,
                label=ts.name,
                icon_key="miniobj" if ts.tileset_type == "object" else "tileset",
                data=uid_to_idx[ts.uid],
            )
            target_folder = None
            if data_root is not None:
                rel = relative_path(ts.path, data_root)
                target_folder = self._placement.get(rel)
            if target_folder and target_folder in folder_nodes:
                folder_nodes[target_folder].add_child(node)
            else:
                roots.append(node)

        self._tree.set_data(roots)

    def _single_selected_folder(self) -> TreeNode | None:
        if len(self._tree.selected_ids) != 1:
            return None
        node = self._tree.find_node(next(iter(self._tree.selected_ids)))
        return node if node and node.is_folder else None

    def _save_hierarchy(self) -> None:
        data_root = self._data_root()
        if data_root is None:
            return
        hier = TilesetHierarchy()

        def walk(nodes: list[TreeNode], parent_id: str | None) -> None:
            for n in nodes:
                if n.is_folder:
                    hier.folders.append(FolderEntry(id=n.id, name=n.label, parent=parent_id))
                    walk(n.children, n.id)
                else:
                    ts = self._ts_node(n.id)
                    if ts is None:
                        continue
                    hier.items.append(ItemEntry(path=relative_path(ts.path, data_root), folder=parent_id))

        walk(self._tree.roots, None)
        save_hierarchy(data_root, hier)

    def _on_tree_delete_requested(self, ids: list[str]) -> None:
        changed = False
        for nid in ids:
            node = self._tree.find_node(nid)
            if node is None or not node.is_folder:
                continue
            parent = node.parent
            siblings = parent.children if parent else self._tree.roots
            idx = siblings.index(node)
            for child in list(node.children):
                node.remove_child(child)
                siblings.insert(idx, child)
                child.parent = parent
                idx += 1
            if parent is not None:
                parent.remove_child(node)
            else:
                while node in self._tree.roots:
                    self._tree.roots.remove(node)
            changed = True
        if changed:
            self._tree.set_data(self._tree.roots)
            self._save_hierarchy()

    def _walk_all(self, nodes: list[TreeNode]) -> list[TreeNode]:
        result: list[TreeNode] = []
        for n in nodes:
            result.append(n)
            result.extend(self._walk_all(n.children))
        return result

    def _on_tileset_type_cancel(self):
        if hasattr(self, "_pending_tileset_path"):
            delattr(self, "_pending_tileset_path")
        if hasattr(self, "_pending_tileset_surf"):
            delattr(self, "_pending_tileset_surf")
        if self._pending_tileset_queue:
            self._start_tileset_queue()

    def _divider_rect(self) -> Rect:
        return Rect(self.rect.x + self._tree_w - self.DIVIDER_W // 2, self.rect.y, self.DIVIDER_W, self.rect.height)

    def resize(self, x: int, y: int, w: int, h: int):
        super().resize(x, y, w, h)
        tw = max(self.TREE_W_MIN, min(self._tree_w, self.TREE_W_MAX, w - 80))
        self._tree_w = tw
        self._tree.resize(x, y, tw, h - 28)
        self._folder_btn.resize(x, y + h - 26, tw, 24)
        self.view_rect = Rect(x + tw, y, w - tw, h)

    def set_rule_hints(self, hints: set[int]):
        self.rule_hints = hints

    def handle_event(self, event: pygame.event.Event) -> bool:

        if event.type == pygame.USEREVENT + 1 and self._queue_timer_active:
            print("DEBUG: Timer triggered, continuing queue")
            self._queue_timer_active = False
            self._start_tileset_queue()
            return True

        mouse_pos = getattr(event, "pos", None) or pygame.mouse.get_pos()

        # divider drag (must be before tree so it takes precedence)
        divider = self._divider_rect()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and divider.collidepoint(mouse_pos):
            self._tree_dragging = True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._tree_dragging:
            self._tree_dragging = False
            return True
        if event.type == pygame.MOUSEMOTION and self._tree_dragging:
            new_w = mouse_pos[0] - self.rect.x
            new_w = max(self.TREE_W_MIN, min(new_w, self.TREE_W_MAX, self.rect.w - 80))
            if new_w != self._tree_w:
                self._tree_w = new_w
                self._tree.resize(self.rect.x, self.rect.y, self._tree_w, self.rect.h - 28)
                self._folder_btn.resize(self.rect.x, self.rect.y + self.rect.h - 26, self._tree_w, 24)
                self.view_rect = Rect(self.rect.x + self._tree_w, self.rect.y, self.rect.w - self._tree_w, self.rect.h)
            return True
        if event.type == pygame.MOUSEMOTION and not self._tree_dragging:
            if divider.collidepoint(mouse_pos):
                try:
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_SIZEWE)
                except Exception:
                    pass
            # let tree handle hover internally; don't return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
            folder = self._single_selected_folder()
            if folder is not None and self._tree.begin_rename(folder.id):
                return True

        if self._tree.handle_event(event):
            return True

        if self._folder_btn.handle_event(event):
            return True

        if event.type == pygame.MOUSEWHEEL:
            if self.view_rect.collidepoint(mouse_pos) and self.active_idx != -1:
                mods = pygame.key.get_mods()
                ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
                meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)
                shift_held = mods & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT)
                ts = self.tilesets[self.active_idx]
                if ctrl_held or meta_held:
                    old_zoom = self.zoom
                    self.zoom = max(0.25, min(self.zoom * (1.0 + event.y * 0.15), 8.0))
                    mx, my = pygame.mouse.get_pos()
                    img_x = self.view_rect.x + ts.offset[0]
                    img_y = self.view_rect.y + ts.offset[1]
                    img_rel_x = (mx - img_x) / old_zoom
                    img_rel_y = (my - img_y) / old_zoom
                    ts.offset[0] = int(mx - self.view_rect.x - img_rel_x * self.zoom)
                    ts.offset[1] = int(my - self.view_rect.y - img_rel_y * self.zoom)
                elif shift_held:
                    ts.offset[0] += event.y * 20
                else:
                    ts.offset[1] += event.y * 20
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            if self.view_rect.collidepoint(mouse_pos) and self.active_idx != -1:
                ts = self.tilesets[self.active_idx]
                if ts.tileset_type == "object":
                    self.editor.context_dispatch.open(PropertyContext(ContextKind.TILESET, ts))
                    return True
                if self.selected_tile:
                    sx, sy, sw, sh = self.selected_tile
                    img_x = self.view_rect.x + ts.offset[0]
                    img_y = self.view_rect.y + ts.offset[1]
                    sel_rect = Rect(
                        int(img_x + sx * self.zoom),
                        int(img_y + sy * self.zoom),
                        int(sw * self.zoom),
                        int(sh * self.zoom),
                    )

                    if sel_rect.collidepoint(mouse_pos):
                        variant_ids = self._get_selected_variant_ids(ts)
                        if not variant_ids:
                            return True

                        self.editor.context_dispatch.open(
                            PropertyContext(
                                ContextKind.TILE_VARIANT,
                                ts,
                                {"variant_ids": variant_ids},
                            )
                        )
                        return True

                self.is_panning = True
                self.pan_start = mouse_pos
                self.pan_start_offset = tuple(ts.offset)
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self.is_panning = False
            return True
        elif event.type == pygame.MOUSEMOTION and self.is_panning and self.active_idx != -1:
            dx = mouse_pos[0] - self.pan_start[0]
            dy = mouse_pos[1] - self.pan_start[1]
            ts = self.tilesets[self.active_idx]
            ts.offset[0] = self.pan_start_offset[0] + dx
            ts.offset[1] = self.pan_start_offset[1] + dy
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.view_rect.collidepoint(mouse_pos) and self.active_idx != -1:
                if self.hover_pos:
                    ts = self.tilesets[self.active_idx]
                    if ts.tileset_type == "object":
                        self.selected_tile = self._frame_aware_object_selected_tile(ts)
                    else:
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
                rel_x = (mouse_pos[0] - img_x) / self.zoom
                rel_y = (mouse_pos[1] - img_y) / self.zoom
                if ts.tileset_type == "object":
                    if 0 <= rel_x < ts.surface.get_width() and 0 <= rel_y < ts.surface.get_height():
                        self.hover_pos = (0, 0)
                    else:
                        self.hover_pos = None
                    self.is_selecting = False
                    self.selection_start_grid = None
                    return True

                if 0 <= rel_x < ts.surface.get_width() and 0 <= rel_y < ts.surface.get_height():
                    tw, th = self.editor.tilemap.tile_size
                    col = int(rel_x // tw)
                    row = int(rel_y // th)
                    self.hover_pos = (col, row)

                    if self.is_selecting and self.selection_start_grid:
                        self.update_selection_rect(self.hover_pos)
                else:
                    self.hover_pos = None

        elif event.type == pygame.KEYDOWN and event.key == pygame.K_e:
            if self.hover_pos is None:
                return False
            if self.selected_tile and self.active_idx != -1:
                self._export_selected_as_png_dialog()
                return True

        return False

    def update_selection_rect(self, current_grid: tuple[int, int]):
        if not self.selection_start_grid:
            return
        start_col, start_row = self.selection_start_grid
        curr_col, curr_row = current_grid

        min_col, max_col = min(start_col, curr_col), max(start_col, curr_col)
        min_row, max_row = min(start_row, curr_row), max(start_row, curr_row)
        tw, th = self.editor.tilemap.tile_size

        self.selected_tile = (
            min_col * tw,
            min_row * th,
            (max_col - min_col + 1) * tw,
            (max_row - min_row + 1) * th,
        )

    def request_add_tileset(self):
        self.editor.open_file_manager(
            on_select=self.on_files_selected,
            initial_dir=getattr(self.editor, "data_root", Path.cwd()),
            allowed_exts=[".png", ".jpg"],
            multi_select=True,
        )

    def on_files_selected(self, paths):
        print(f"DEBUG: on_files_selected called with {len(paths) if isinstance(paths, (list, tuple)) else 1} file(s)")
        if isinstance(paths, Path):
            self.on_file_selected(paths)
            return
        if isinstance(paths, (list, tuple, set)):
            for p in paths:
                if isinstance(p, Path):
                    self.on_file_selected(p, enqueue_only=True)
                elif isinstance(p, str):
                    self.on_file_selected(Path(p), enqueue_only=True)
            print(f"DEBUG: Queue size after adding: {len(self._pending_tileset_queue)}")
            if self._pending_tileset_queue:
                self._start_tileset_queue()
        else:
            return

    def on_file_selected(self, path: Path, enqueue_only: bool = False):
        if path.exists():
            try:
                surf = pygame.image.load(path).convert_alpha()
                self._pending_tileset_queue.append((path, surf))
                if not enqueue_only:
                    self._start_tileset_queue()
            except Exception as e:
                error_msg = f"Error loading image {path}: {e}"
                error_handler.capture(Exception(error_msg), context="load_tileset_image")
                import logging

                logging.error(error_msg, exc_info=True)
        else:
            error_msg = f"File does not exist: {path}"
            error_handler.capture(Exception(error_msg), context="load_tileset_missing")
            import logging

            logging.error(error_msg)

    def _start_tileset_queue(self):
        if not self._pending_tileset_queue:
            print("DEBUG: Queue is empty, nothing to process")
            return
        print(f"DEBUG: Starting queue processing, {len(self._pending_tileset_queue)} items remaining")
        self._pending_tileset_path, self._pending_tileset_surf = self._pending_tileset_queue.pop(0)
        print(f"DEBUG: Processing tileset: {self._pending_tileset_path}")
        tw, th = self.editor.tilemap.tile_size
        sheet_cols = self._pending_tileset_surf.get_width() // tw
        sheet_rows = self._pending_tileset_surf.get_height() // th
        self.editor.tileset_type_dialog.set_sheet_dimensions(sheet_cols, sheet_rows)
        self.editor.tileset_type_dialog.show(
            on_confirm=self._on_tileset_type_selected,
            on_cancel=self._on_tileset_type_cancel,
        )

    def load_tileset_from_path(
        self,
        path: Path,
        tileset_type: str,
        properties: dict = None,
        tile_properties: dict = None,
        animation: dict | None = None,
    ):
        if tile_properties is None:
            tile_properties = {}
        if properties is None:
            properties = {}
        if path.exists():
            try:
                surf = pygame.image.load(path).convert_alpha()
                tileset_data = TilesetData(path.name, path, surf, tileset_type=tileset_type)
                tileset_data.properties = properties
                tileset_data.tile_properties = {int(k): v for k, v in tile_properties.items()}
                tileset_data.animation = animation
                self._load_collision_data_for_tileset(tileset_data)

                self.tilesets.append(tileset_data)
                self.tileset_map[len(self.tilesets) - 1] = tileset_data
                self._sync_tree()
                self._tree.selected_ids = {tileset_data.uid}
                if tileset_type == "object":
                    self.selected_tile = self._frame_aware_object_selected_tile(tileset_data)
                self.editor.suggestion_registry.refresh(self.editor)
            except Exception as e:
                error_handler.capture(e, context="load_tileset_surface")

    def _on_tileset_type_selected(self, tileset_type: str):
        if not hasattr(self, "_pending_tileset_path"):
            return

        surf = self._pending_tileset_surf

        if tileset_type == "tile" and not is_image_multipleof(surf.get_size(), self.editor.tilemap.tile_size):
            w, h = surf.get_size()
            tw, th = self.editor.tilemap.tile_size
            self.editor.confirm_dialog.show(
                title="Tileset Size Warning",
                message=f"Image size ({w}x{h}) is not an exact multiple of tile size ({tw}x{th}). "
                f"Some pixels at the edges will be ignored. Proceed?",
                on_confirm=lambda: self._commit_tileset_load(tileset_type),
                on_cancel=self._on_tileset_type_cancel,
            )
            return

        self._commit_tileset_load(tileset_type)

    def _commit_tileset_load(self, tileset_type: str):
        import math

        path = self._pending_tileset_path
        surf = self._pending_tileset_surf

        tileset_data = TilesetData(path.name, path, surf, tileset_type=tileset_type)
        animation = self.editor.tileset_type_dialog.get_animation_config()
        if animation:
            frame_count = animation.get("frame_count", 0)
            if frame_count <= 0:
                animation = None
            elif tileset_type == "object":
                if surf.get_width() % frame_count == 0:
                    animation["frame_w"] = surf.get_width() // frame_count
                    animation["frame_h"] = surf.get_height()
                elif surf.get_height() % frame_count == 0:
                    animation["frame_w"] = surf.get_width()
                    animation["frame_h"] = surf.get_height() // frame_count
                else:
                    animation["frame_w"] = (
                        surf.get_width() // frame_count if surf.get_width() >= frame_count else surf.get_width()
                    )
                    animation["frame_h"] = surf.get_height()
            else:
                tw, th = self.editor.tilemap.tile_size
                if tw <= 0 or th <= 0:
                    animation = None
                else:
                    sheet_cols = surf.get_width() // tw
                    sheet_rows = surf.get_height() // th
                    if sheet_cols == 0 or sheet_rows == 0:
                        animation = None
                    elif sheet_cols % frame_count == 0:
                        animation["frame_stride"] = sheet_cols // frame_count
                    elif sheet_rows % frame_count == 0:
                        animation["frame_stride"] = (sheet_rows // frame_count) * sheet_cols
                    else:
                        total = sheet_cols * sheet_rows
                        animation["frame_stride"] = math.ceil(total / frame_count)
        tileset_data.animation = animation
        self._load_collision_data_for_tileset(tileset_data)
        self.tilesets.append(tileset_data)
        self.active_idx = len(self.tilesets) - 1
        self.tileset_map[self.active_idx] = tileset_data

        if tileset_type == "object":
            self.selected_tile = self._frame_aware_object_selected_tile(tileset_data)

        self._sync_tree()
        self._tree.selected_ids = {tileset_data.uid}

        self.editor.suggestion_registry.refresh(self.editor)
        delattr(self, "_pending_tileset_path")
        delattr(self, "_pending_tileset_surf")
        if self._pending_tileset_queue:
            pygame.time.set_timer(pygame.USEREVENT + 1, 100, 1)
            self._queue_timer_active = True

    def _load_collision_data_for_tileset(self, tileset_data: TilesetData) -> None:
        if tileset_data.tileset_type != "object":
            return

        collision_path = self._object_collision_path_for(tileset_data.path)
        tileset_data.object_collision_path = collision_path

        if not collision_path.exists():
            tileset_data.object_collision_data = None
            return

        try:
            from plugins.object_tileset_collision.models import (
                ObjectTilesetCollisionLibrary,
            )

            library = ObjectTilesetCollisionLibrary.load(collision_path)
            tileset_data.object_collision_data = library.to_dict()
            print(f"Loaded object collision data: {collision_path}")
        except Exception as e:
            tileset_data.object_collision_data = None
            error_handler.capture(e, context="load_object_tileset_collision")

    def _object_collision_path_for(self, tileset_path: Path) -> Path:
        data_root = getattr(self.editor, "data_root", None)
        if data_root is None:
            return tileset_path.with_suffix(".object_collision.json")

        config = getattr(self.editor, "config", {}) or {}
        collision_dir_name = config.get("collision_paths", {}).get(
            "object_tileset",
            "collision",
        )
        return Path(data_root) / collision_dir_name / f"{tileset_path.stem}.object_collision.json"

    def load_object_tileset_companions(self) -> None:
        previous_active_idx = self.active_idx
        previous_selected_tile = self.selected_tile

        existing = {(ts.path.resolve(), ts.tileset_type) for ts in self.tilesets if ts.path.exists()}

        for ts in list(self.tilesets):
            if ts.tileset_type != "tile":
                continue

            try:
                resolved_path = ts.path.resolve()
            except OSError:
                continue

            if (resolved_path, "object") in existing:
                continue

            collision_path = self._object_collision_path_for(ts.path)
            if not collision_path.exists():
                continue

            print(f"Auto-loading object tileset companion from collision sidecar: {collision_path}")
            self.load_tileset_from_path(ts.path, "object")
            existing.add((resolved_path, "object"))

        if 0 <= previous_active_idx < len(self.tilesets):
            self.active_idx = previous_active_idx
            self.selected_tile = previous_selected_tile

    def remove_tileset(self):
        if not (0 <= self.active_idx < len(self.tilesets)):
            self.editor.notifications.notify("No tileset selected", duration=2.5)
            return

        removed_idx = self.active_idx
        removed_ts = self.tilesets[removed_idx]

        # Hard gate: never orphan painted tiles.  Removing a referenced
        # tileset would silently re-point every later index at the wrong
        # sheet once saved.
        from utils.tileset_ops import count_ttype_refs, remap_after_removal, remap_rule_indexes

        refs = count_ttype_refs(self.editor.tilemap.layer_manager, removed_idx)
        if refs:
            self.editor.notifications.notify(
                f"Cannot remove '{removed_ts.name}': {refs} painted tile(s)/object(s) use it",
                color=(255, 120, 120),
                duration=5.0,
            )
            return

        self.tilesets.pop(removed_idx)

        self.tileset_map.clear()
        for i, ts in enumerate(self.tilesets):
            self.tileset_map[i] = ts

        # Keep every surviving reference pointing at the same sheet.
        remap_after_removal(self.editor.tilemap.layer_manager, removed_idx)
        autotiler = getattr(self.editor, "autotiler", None)
        if autotiler is not None:
            remap_rule_indexes(autotiler, removed_idx, self.tilesets)

        self.active_idx = max(0, len(self.tilesets) - 1)
        if not self.tilesets:
            self.active_idx = -1

        # Always resync: skipping this left a ghost node whose stale data
        # index resolved clicks to a *different* surviving tileset.
        self.rule_hints.clear()
        self._sync_tree()

        self.editor.suggestion_registry.refresh(self.editor)
        self.editor.notifications.notify(f"Removed tileset '{removed_ts.name}'", duration=2.5)

        # The deprecated regex automap designer keeps raw tileset indices in
        # its saved rules and is intentionally not remapped (slated for
        # removal) — warn instead of silently re-pointing its rules.
        designer = getattr(self.editor, "regex_automap_designer", None)
        if designer is not None and getattr(designer, "pattern_rules", None):
            self.editor.notifications.notify(
                "Regex Automap is deprecated: saved rules reference the removed tileset and are now stale",
                color=(255, 165, 0),
                duration=6.0,
            )

    def open_collision_editor(self):
        if self.active_idx == -1 or self.active_idx >= len(self.tilesets):
            self.editor.notifications.notify("No tileset selected")
            return

        ts = self.tilesets[self.active_idx]

        self.editor.launch_collision_editor(ts.tileset_type)

    def _save_tileset_properties(self, ctx: PropertyContext, props: dict):
        ts = ctx.target
        ts.properties = props
        self.editor.suggestion_registry.refresh(self.editor)
        print(f"Saved properties for tileset: {ts.name}")

    def _save_tile_properties(self, ts: TilesetData, variant_id: int, props: dict):
        ts.tile_properties[variant_id] = props
        print(f"Saved properties for tile {variant_id} in tileset: {ts.name}")

    def _save_tile_properties_multi(self, ctx: PropertyContext, props: dict):
        ts = ctx.target
        variant_ids = ctx.extra.get("variant_ids", [])
        for vid in variant_ids:
            ts.tile_properties[vid] = props.copy()
        self.editor.suggestion_registry.refresh(self.editor)
        if len(variant_ids) == 1:
            print(f"Saved properties for tile {variant_ids[0]} in tileset: {ts.name}")
        else:
            print(f"Saved properties for {len(variant_ids)} tiles in tileset: {ts.name}")

    def _get_selected_variant_ids(self, ts: TilesetData) -> list[int]:
        if not self.selected_tile:
            return []
        sx, sy, sw, sh = self.selected_tile
        tw, th = self.editor.tilemap.tile_size
        cols = ts.surface.get_width() // tw
        start_col = sx // tw
        start_row = sy // th
        sel_w_tiles = max(1, sw // tw)
        sel_h_tiles = max(1, sh // th)
        variant_ids: list[int] = []
        for row in range(start_row, start_row + sel_h_tiles):
            for col in range(start_col, start_col + sel_w_tiles):
                variant_ids.append((row * cols) + col)
        return variant_ids

    def get_active_tile(self):
        if self.active_idx == -1:
            return None
        return self.tilesets[self.active_idx]

    def get_tileset_by_index(self, index: int) -> TilesetData | None:
        if index < 0 or index >= len(self.tilesets):
            return None
        return self.tilesets[index]

    def select_tile_by_variant(self, tileset_index: int, variant_id: int) -> bool:
        if tileset_index < 0 or tileset_index >= len(self.tilesets):
            return False

        ts = self.tilesets[tileset_index]
        if ts.tileset_type == "object":
            self.active_idx = tileset_index
            self.selected_tile = self._frame_aware_object_selected_tile(ts)
            return True

        tw, th = self.editor.tilemap.tile_size
        if tw <= 0 or th <= 0:
            return False

        sheet_w = ts.surface.get_width()
        cols = sheet_w // tw
        if cols <= 0:
            return False

        col = variant_id % cols
        row = variant_id // cols

        if col * tw >= sheet_w or row * th >= ts.surface.get_height():
            return False

        self.active_idx = tileset_index
        self.selected_tile = (col * tw, row * th, tw, th)
        return True

    def _export_selected_as_png_dialog(self):
        if not self.selected_tile or self.active_idx == -1:
            return
        ts = self.tilesets[self.active_idx]
        default = Path(ts.name).stem + "_extracted.png"
        self.editor.open_file_manager(
            on_save=self._on_export_selected_path,
            allowed_exts=[".png"],
            mode="save",
            default_name=default,
        )

    def _on_export_selected_path(self, path: Path):
        try:
            sx, sy, sw, sh = self.selected_tile
            ts = self.tilesets[self.active_idx]
            extracted = ts.surface.subsurface(Rect(sx, sy, sw, sh)).copy()
            pygame.image.save(extracted, str(path))
        except Exception as e:
            error_handler.capture(e, context="export_selected_png")

    def draw(self, screen: pygame.Surface):
        self.draw_base(screen)

        tree_bg = Rect(self.rect.x, self.rect.y, self._tree_w, self.rect.height)
        pygame.draw.rect(screen, COLORS.panel_alt, tree_bg)
        div_x = tree_bg.right
        div_color = COLORS.accent if self._tree_dragging else COLORS.border
        div_w = 2 if self._tree_dragging else 1
        pygame.draw.line(screen, div_color, (div_x, tree_bg.top), (div_x, tree_bg.bottom), div_w)
        # hover highlight
        if not self._tree_dragging:
            mx, my = pygame.mouse.get_pos()
            if self._divider_rect().collidepoint((mx, my)):
                pygame.draw.line(screen, COLORS.text_dim, (div_x, tree_bg.top), (div_x, tree_bg.bottom), 1)

        self._tree.draw(screen)
        self._folder_btn.draw(screen)

        self.draw_view_area(screen)

        # tooltip for truncated tree names
        truncated = getattr(self._tree, "_hovered_truncated", None)
        if truncated:
            mx, my = pygame.mouse.get_pos()
            try:
                self.editor.tooltip.show(truncated, (mx + 10, my + 10))
            except Exception:
                pass

    def draw_view_area(self, screen: pygame.Surface):
        pygame.draw.rect(screen, COLORS.panel_alt, self.view_rect)
        if self.active_idx == -1 or self.active_idx >= len(self.tilesets):
            return

        ts = self.tilesets[self.active_idx]
        clip = screen.get_clip()
        screen.set_clip(self.view_rect)

        img_x = self.view_rect.x + ts.offset[0]
        img_y = self.view_rect.y + ts.offset[1]

        self.draw_tileset_image(screen, ts, img_x, img_y, self.zoom)

        self._draw_object_collision_regions(screen, ts, img_x, img_y)

        self._draw_rule_hints(screen, ts, img_x, img_y)

        self.draw_hover(screen, ts, img_x, img_y)
        self.draw_selection(screen, img_x, img_y)

        screen.set_clip(clip)

    def _draw_rule_hints(self, screen, ts, img_x, img_y):
        if not self.rule_hints:
            return

        tw, th = self.editor.tilemap.tile_size
        sheet_w = ts.surface.get_width()
        cols = sheet_w // tw

        ztw = int(tw * self.zoom)
        zth = int(th * self.zoom)

        for vid in self.rule_hints:
            col = vid % cols
            row = vid // cols

            x = int(img_x + col * tw * self.zoom)
            y = int(img_y + row * th * self.zoom)

            if (
                x > self.view_rect.right
                or x + ztw < self.view_rect.x
                or y > self.view_rect.bottom
                or y + zth < self.view_rect.y
            ):
                continue

            points = [(x, y), (x + 10, y), (x, y + 10)]
            pygame.draw.polygon(screen, (0, 255, 255), points)

            pygame.draw.rect(screen, (0, 255, 255), Rect(x, y, ztw, zth), 1)

    def draw_tileset_image(self, screen, ts: TilesetData, img_x: int, img_y: int, zoom: float = 1.0):
        if zoom != 1.0:
            w = int(ts.surface.get_width() * zoom)
            h = int(ts.surface.get_height() * zoom)
            scaled = pygame.transform.smoothscale(ts.surface, (w, h))
            screen.blit(scaled, (img_x, img_y))
        else:
            screen.blit(ts.surface, (img_x, img_y))

    def _draw_object_collision_regions(
        self,
        screen: pygame.Surface,
        ts: TilesetData,
        img_x: int,
        img_y: int,
    ) -> None:
        if ts.tileset_type != "object" or not ts.object_collision_data:
            return

        regions = ts.object_collision_data.get("regions", {})
        if not isinstance(regions, dict):
            return

        for region_data in regions.values():
            if not isinstance(region_data, dict):
                continue
            rect_data = region_data.get("region_rect")
            if not isinstance(rect_data, (list, tuple)) or len(rect_data) != 4:
                continue

            rx, ry, rw, rh = (int(v) for v in rect_data)
            region_rect = Rect(
                int(img_x + rx * self.zoom),
                int(img_y + ry * self.zoom),
                int(rw * self.zoom),
                int(rh * self.zoom),
            )
            if not self.view_rect.colliderect(region_rect):
                continue

            shapes = region_data.get("shapes", [])
            color = COLORS.success if shapes else COLORS.warning
            pygame.draw.rect(screen, color, region_rect, 2)

            name = str(region_data.get("name") or region_data.get("region_id") or "")
            if name:
                max_label_w = max(0, region_rect.width - 10)
                display_name = name
                while display_name and self.font.size(display_name)[0] > max_label_w:
                    display_name = display_name[:-1].rstrip()
                if display_name != name and max_label_w > self.font.size("...")[0]:
                    while display_name and self.font.size(display_name + "...")[0] > max_label_w:
                        display_name = display_name[:-1].rstrip()
                    display_name += "..."
                label = self.font.render(display_name, True, COLORS.text)
                label_bg = Rect(
                    region_rect.x + 2,
                    region_rect.y + 2,
                    label.get_width() + 6,
                    label.get_height() + 4,
                )
                if label_bg.width > 0:
                    pygame.draw.rect(screen, COLORS.panel, label_bg)
                    screen.blit(label, (label_bg.x + 3, label_bg.y + 2))

    def draw_hover(self, screen, ts: TilesetData, img_x: int, img_y: int):
        if self.hover_pos is None:
            return
        if ts.tileset_type == "object":
            return
        tw, th = self.editor.tilemap.tile_size
        col, row = self.hover_pos
        ztw = int(tw * self.zoom)
        zth = int(th * self.zoom)
        hover_rect = Rect(int(img_x + col * tw * self.zoom), int(img_y + row * th * self.zoom), ztw, zth)
        pygame.draw.rect(screen, COLORS.warning, hover_rect, 2)

    def draw_selection(self, screen, img_x: int, img_y: int):
        if not self.selected_tile:
            return
        sx, sy, sw, sh = self.selected_tile
        sel_rect = Rect(
            int(img_x + sx * self.zoom),
            int(img_y + sy * self.zoom),
            int(sw * self.zoom),
            int(sh * self.zoom),
        )
        pygame.draw.rect(screen, COLORS.success, sel_rect, 2)
