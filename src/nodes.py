from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class NodeRect:
    x: int
    y: int
    w: int
    h: int

    def to_dict(self) -> Dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeRect":
        return cls(
            x=int(data["x"]), y=int(data["y"]), w=int(data["w"]), h=int(data["h"])
        )


@dataclass
class Node:
    node_id: str
    name: str
    node_type: str
    area: NodeRect
    layer_name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    group: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type,
            "area": self.area.to_dict(),
            "layer_name": self.layer_name,
            "properties": dict(self.properties),
            "group": self.group,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        return cls(
            node_id=str(data["node_id"]),
            name=str(data["name"]),
            node_type=str(data.get("node_type", "area")),
            area=NodeRect.from_dict(data["area"]),
            layer_name=str(data.get("layer_name", "")),
            properties=dict(data.get("properties", {})),
            group=data.get("group"),
        )
