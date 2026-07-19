"""
Data models for character collision system.
"""

from dataclasses import dataclass, field
from typing import Any

from .protocols import CollisionShapeType


@dataclass
class CollisionInfo:
    """Information about a collision between two shapes"""

    collided: bool
    normal: tuple[float, float] = (0.0, 0.0)
    penetration: float = 0.0
    contact_point: tuple[float, float] = (0.0, 0.0)
    other_shape_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "collided": self.collided,
            "normal": self.normal,
            "penetration": self.penetration,
            "contact_point": self.contact_point,
            "other_shape_id": self.other_shape_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollisionInfo":
        """Create from dictionary"""
        return cls(
            collided=data.get("collided", False),
            normal=tuple(data.get("normal", (0.0, 0.0))),
            penetration=data.get("penetration", 0.0),
            contact_point=tuple(data.get("contact_point", (0.0, 0.0))),
            other_shape_id=data.get("other_shape_id"),
        )


@dataclass
class RectangleCollisionData:
    """Rectangle collision shape data"""

    width: float
    height: float
    offset: tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "rectangle",
            "width": self.width,
            "height": self.height,
            "offset": self.offset,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RectangleCollisionData":
        return cls(
            width=data["width"],
            height=data["height"],
            offset=tuple(data.get("offset", (0.0, 0.0))),
        )


@dataclass
class CircleCollisionData:
    """Circle collision shape data"""

    radius: float
    offset: tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "circle", "radius": self.radius, "offset": self.offset}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CircleCollisionData":
        return cls(radius=data["radius"], offset=tuple(data.get("offset", (0.0, 0.0))))


@dataclass
class CapsuleCollisionData:
    """Capsule collision shape data"""

    radius: float
    height: float
    offset: tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "capsule",
            "radius": self.radius,
            "height": self.height,
            "offset": self.offset,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapsuleCollisionData":
        return cls(
            radius=data["radius"],
            height=data["height"],
            offset=tuple(data.get("offset", (0.0, 0.0))),
        )


@dataclass
class PolygonCollisionData:
    """Polygon collision shape data"""

    vertices: list[tuple[float, float]]
    offset: tuple[float, float] = (0.0, 0.0)

    def to_dict(self) -> dict[str, Any]:
        return {"type": "polygon", "vertices": self.vertices, "offset": self.offset}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PolygonCollisionData":
        return cls(
            vertices=[tuple(v) for v in data["vertices"]],
            offset=tuple(data.get("offset", (0.0, 0.0))),
        )


@dataclass
class CharacterCollisionData:
    """Complete collision data for a character"""

    name: str
    shape: RectangleCollisionData | CircleCollisionData | CapsuleCollisionData | PolygonCollisionData
    image_path: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        d: dict[str, Any] = {
            "name": self.name,
            "shape": self.shape.to_dict(),
            "properties": self.properties,
        }
        if self.image_path:
            d["image_path"] = self.image_path
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterCollisionData":
        """Create from dictionary"""
        shape_data = data["shape"]
        shape_type = shape_data["type"]

        if shape_type == "rectangle":
            shape = RectangleCollisionData.from_dict(shape_data)
        elif shape_type == "circle":
            shape = CircleCollisionData.from_dict(shape_data)
        elif shape_type == "capsule":
            shape = CapsuleCollisionData.from_dict(shape_data)
        elif shape_type == "polygon":
            shape = PolygonCollisionData.from_dict(shape_data)
        else:
            raise ValueError(f"Unknown shape type: {shape_type}")

        return cls(
            name=data["name"],
            shape=shape,
            image_path=data.get("image_path"),
            properties=data.get("properties", {}),
        )


CollisionShapeType = CollisionShapeType
