import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nodes import Node, NodeRect

if TYPE_CHECKING:
    from editor import Editor


def create_node_id() -> str:
    return str(uuid.uuid4())


SIDECAR_VERSION = 2


class NodeManager:
    def __init__(self, editor: "Editor") -> None:
        self.editor = editor
        self.nodes: dict[str, Node] = {}
        self.active_node_id: str | None = None
        self.active_group_name: str | None = None
        self.groups: list[str] = []
        self.default_node_type: str = "area"
        self._nodes_dir: Path | None = None
        self._active_sidecar: Path | None = None

    @property
    def nodes_dir(self) -> Path:
        if self._nodes_dir is None:
            config = getattr(self.editor, "config", {})
            rel = config.get("nodes_path", "nodes")
            self._nodes_dir = self.editor.data_root / rel
        return self._nodes_dir

    def reset_nodes_dir(self) -> None:
        """Drop the cached dir so the next access re-derives from data_root."""
        self._nodes_dir = None
        self._active_sidecar = None

    def _sidecar_path_for(self, map_path: Path) -> Path:
        return self.nodes_dir / f"{map_path.stem}.nodes.json"

    def load(self, map_path: Path) -> None:
        self.nodes.clear()
        self.groups.clear()
        self.active_node_id = None
        self.active_group_name = None
        self._active_sidecar: Path | None = None
        sidecar = self._sidecar_path_for(map_path)
        if not sidecar.is_file():
            fallback = map_path.parent / f"{map_path.stem}.nodes.json"
            if fallback.is_file():
                sidecar = fallback
            else:
                self._active_sidecar = None
                return
        self._active_sidecar = sidecar
        try:
            raw = json.loads(sidecar.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            version = raw.get("version", 1)
            self.groups = list(raw.get("groups", []))
            rs = self.editor.tilemap.render_scale
            for item in raw.get("nodes", []):
                if isinstance(item, dict):
                    node = Node.from_dict(item)
                    if version >= 2:
                        node.area.x = int(node.area.x * rs)
                        node.area.y = int(node.area.y * rs)
                    self.nodes[node.node_id] = node
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            import logging

            logging.warning(f"Failed to load nodes from {sidecar}")

    def save(self, map_path: Path) -> None:
        # Trust the loaded sidecar only while it IS the canonical one for the
        # requested map.  A diverged pointer (e.g. left over from a sandbox
        # session) must never swallow writes aimed elsewhere: after an export
        # the canonical location wins so the sandbox copy stays frozen.
        fallback = self._sidecar_path_for(map_path)
        active = self._active_sidecar
        sidecar = fallback if (active is None or active != fallback) else active
        self.nodes_dir.mkdir(parents=True, exist_ok=True)
        rs = self.editor.tilemap.render_scale
        orig_areas: dict[str, tuple[int, int]] = {}
        for nid, node in self.nodes.items():
            orig_areas[nid] = (node.area.x, node.area.y)
            node.area.x = int(node.area.x / rs)
            node.area.y = int(node.area.y / rs)
        tmp_sidecar = sidecar.with_name(f".{sidecar.name}.tmp")
        try:
            data: dict[str, Any] = {
                "version": SIDECAR_VERSION,
                "groups": self.groups,
                "nodes": [node.to_dict() for node in self.nodes.values()],
            }
            tmp_sidecar.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp_sidecar.replace(sidecar)
        finally:
            try:
                tmp_sidecar.unlink(missing_ok=True)
            except Exception:
                pass
            for nid, (ox, oy) in orig_areas.items():
                self.nodes[nid].area.x = ox
                self.nodes[nid].area.y = oy

    def add_node(self, node: Node) -> str:
        self.nodes[node.node_id] = node
        return node.node_id

    def remove_node(self, node_id: str) -> None:
        self.nodes.pop(node_id, None)
        if self.active_node_id == node_id:
            self.active_node_id = None

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def get_active_node(self) -> Node | None:
        if self.active_node_id is None:
            return None
        return self.nodes.get(self.active_node_id)

    def set_active_node(self, node_id: str | None) -> None:
        self.active_node_id = node_id
        if node_id is not None:
            self.active_group_name = None

    def set_active_group(self, group_name: str | None) -> None:
        self.active_group_name = group_name
        if group_name is not None:
            self.active_node_id = None

    def get_nodes_for_layer(self, layer_name: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.layer_name == layer_name]

    def create_default_node(self, layer_name: str, node_type: str = "area") -> Node:
        count = len(self.nodes) + 1
        props: dict[str, Any] = {}
        if node_type == "particle_emitter":
            from widgets.particle_system import get_default_config

            props = get_default_config()
            name = f"Emitter {count}"
        else:
            name = f"{node_type.capitalize()} {count}"
        return Node(
            node_id=create_node_id(),
            name=name,
            node_type=node_type,
            area=NodeRect(x=0, y=0, w=64, h=64),
            layer_name=layer_name,
            properties=props,
        )

    def duplicate_node(self, node_id: str) -> str | None:
        """Clone a node (area nudged so the copy is visible)."""
        src = self.nodes.get(node_id)
        if src is None:
            return None
        existing = {n.name for n in self.nodes.values()}
        base = f"{src.name} copy"
        name = base
        counter = 2
        while name in existing:
            name = f"{base} {counter}"
            counter += 1
        clone = Node(
            node_id=create_node_id(),
            name=name,
            node_type=src.node_type,
            area=NodeRect(src.area.x + 16, src.area.y + 16, src.area.w, src.area.h),
            layer_name=src.layer_name,
            properties=dict(src.properties),
            group=src.group,
        )
        keys = list(self.nodes.keys())
        keys.insert(keys.index(node_id) + 1, clone.node_id)
        self.nodes[clone.node_id] = clone
        self.nodes = {k: self.nodes[k] for k in keys}
        self.active_node_id = clone.node_id
        self.active_group_name = None
        return clone.node_id

    def rename_group(self, old_name: str, new_name: str) -> bool:
        if not new_name or new_name == old_name:
            return False
        if new_name in self.groups:
            return False
        if old_name not in self.groups:
            return False

        idx = self.groups.index(old_name)
        self.groups[idx] = new_name

        for node in self.nodes.values():
            if node.group == old_name:
                node.group = new_name

        if self.active_group_name == old_name:
            self.active_group_name = new_name
        return True

    def reorder_node(
        self, node_id: str, target_node_id: str, before: bool = True
    ) -> None:
        if node_id not in self.nodes or target_node_id not in self.nodes:
            return
        if node_id == target_node_id:
            return
        self.nodes[node_id]
        keys = list(self.nodes.keys())
        keys.remove(node_id)
        target_idx = keys.index(target_node_id)
        if not before:
            target_idx += 1
        keys.insert(target_idx, node_id)

        new_nodes = {}
        for k in keys:
            new_nodes[k] = self.nodes[k]
        self.nodes = new_nodes
