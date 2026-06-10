import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from nodes import Node, NodeRect

if TYPE_CHECKING:
    from editor import Editor


def create_node_id() -> str:
    return str(uuid.uuid4())


SIDECAR_VERSION = 1


class NodeManager:
    def __init__(self, editor: "Editor") -> None:
        self.editor = editor
        self.nodes: Dict[str, Node] = {}
        self.active_node_id: Optional[str] = None
        self.active_group_name: Optional[str] = None
        self.groups: List[str] = []
        self.default_node_type: str = "area"
        self._nodes_dir: Optional[Path] = None

    @property
    def nodes_dir(self) -> Path:
        if self._nodes_dir is None:
            config = getattr(self.editor, "config", {})
            rel = config.get("nodes_path", "nodes")
            self._nodes_dir = self.editor.data_root / rel
        return self._nodes_dir

    def _sidecar_path_for(self, map_path: Path) -> Path:
        return self.nodes_dir / f"{map_path.stem}.nodes.json"

    def load(self, map_path: Path) -> None:
        self.nodes.clear()
        self.groups.clear()
        self.active_node_id = None
        self.active_group_name = None
        sidecar = self._sidecar_path_for(map_path)
        if not sidecar.is_file():
            return
        try:
            raw = json.loads(sidecar.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            self.groups = list(raw.get("groups", []))
            for item in raw.get("nodes", []):
                if isinstance(item, dict):
                    node = Node.from_dict(item)
                    self.nodes[node.node_id] = node
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            import logging
            logging.warning(f"Failed to load nodes from {sidecar}")

    def save(self, map_path: Path) -> None:
        sidecar = self._sidecar_path_for(map_path)
        self.nodes_dir.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {
            "version": SIDECAR_VERSION,
            "groups": self.groups,
            "nodes": [node.to_dict() for node in self.nodes.values()],
        }
        sidecar.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_node(self, node: Node) -> str:
        self.nodes[node.node_id] = node
        return node.node_id

    def remove_node(self, node_id: str) -> None:
        self.nodes.pop(node_id, None)
        if self.active_node_id == node_id:
            self.active_node_id = None

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def get_active_node(self) -> Optional[Node]:
        if self.active_node_id is None:
            return None
        return self.nodes.get(self.active_node_id)

    def set_active_node(self, node_id: Optional[str]) -> None:
        self.active_node_id = node_id
        if node_id is not None:
            self.active_group_name = None

    def set_active_group(self, group_name: Optional[str]) -> None:
        self.active_group_name = group_name
        if group_name is not None:
            self.active_node_id = None

    def get_nodes_for_layer(self, layer_name: str) -> List[Node]:
        return [n for n in self.nodes.values() if n.layer_name == layer_name]

    def create_default_node(self, layer_name: str, node_type: str = "area") -> Node:
        count = len(self.nodes) + 1
        props: Dict[str, Any] = {}
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

    def rename_group(self, old_name: str, new_name: str) -> bool:
        if not new_name or new_name == old_name:
            return False
        if new_name in self.groups:
            return False  # Already exists
        if old_name not in self.groups:
            return False
            
        # Update groups list
        idx = self.groups.index(old_name)
        self.groups[idx] = new_name
        
        # Update child nodes
        for node in self.nodes.values():
            if node.group == old_name:
                node.group = new_name
                
        if self.active_group_name == old_name:
            self.active_group_name = new_name
        return True

    def reorder_node(self, node_id: str, target_node_id: str, before: bool = True) -> None:
        if node_id not in self.nodes or target_node_id not in self.nodes:
            return
        if node_id == target_node_id:
            return
        node = self.nodes[node_id]
        keys = list(self.nodes.keys())
        keys.remove(node_id)
        target_idx = keys.index(target_node_id)
        if not before:
            target_idx += 1
        keys.insert(target_idx, node_id)
        
        # Rebuild dictionary
        new_nodes = {}
        for k in keys:
            new_nodes[k] = self.nodes[k]
        self.nodes = new_nodes
