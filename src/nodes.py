from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeRect:
    x: int
    y: int
    w: int
    h: int

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeRect:
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
    properties: dict[str, Any] = field(default_factory=dict)
    group: str | None = None

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> Node:
        return cls(
            node_id=str(data["node_id"]),
            name=str(data["name"]),
            node_type=str(data.get("node_type", "area")),
            area=NodeRect.from_dict(data["area"]),
            layer_name=str(data.get("layer_name", "")),
            properties=dict(data.get("properties", {})),
            group=data.get("group"),
        )
