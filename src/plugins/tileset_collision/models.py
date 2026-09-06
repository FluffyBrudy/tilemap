"""
Data models for tileset collision system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CollisionShapeType(Enum):
    """Types of collision shapes supported"""

    POLYGON = "polygon"
    RECTANGLE = "rectangle"


@dataclass
class CollisionPolygon:
    """Polygon collision shape for a tile"""

    vertices: list[tuple[float, float]] = field(default_factory=list)
    one_way: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "type": "polygon",
            "vertices": self.vertices,
            "one_way": self.one_way,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CollisionPolygon":
        """Create from dictionary"""
        return cls(
            vertices=[tuple(v) for v in data.get("vertices", [])],
            one_way=data.get("one_way", False),
        )

    def is_valid(self) -> bool:
        """Check if polygon has at least 3 vertices"""
        return len(self.vertices) >= 3


@dataclass
class TileCollisionData:
    """Complete collision data for a single tile"""

    tile_id: int
    shapes: list[CollisionPolygon] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    flip_x: bool = False
    flip_y: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "tile_id": self.tile_id,
            "shapes": [s.to_dict() for s in self.shapes],
            "properties": self.properties,
            "flip_x": self.flip_x,
            "flip_y": self.flip_y,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TileCollisionData":
        """Create from dictionary"""
        return cls(
            tile_id=data["tile_id"],
            shapes=[CollisionPolygon.from_dict(s) for s in data.get("shapes", [])],
            properties=data.get("properties", {}),
            flip_x=data.get("flip_x", False),
            flip_y=data.get("flip_y", False),
        )

    @staticmethod
    def apply_flip(point: tuple[float, float], tile_size: tuple[int, int],
                   flip_x: bool, flip_y: bool) -> tuple[float, float]:
        """Mirror a tile-local point (flip-flip is identity)."""
        tw, th = tile_size
        x, y = point
        return ((tw - x) if flip_x else x, (th - y) if flip_y else y)


@dataclass
class TilesetCollisionLibrary:
    """Collection of collision data for all tiles in a tileset"""

    tileset_name: str
    tile_size: tuple[int, int]
    tiles: dict[int, TileCollisionData] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "tileset_name": self.tileset_name,
            "tile_size": self.tile_size,
            "tiles": {str(k): v.to_dict() for k, v in self.tiles.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TilesetCollisionLibrary":
        """Create from dictionary"""
        return cls(
            tileset_name=data["tileset_name"],
            tile_size=tuple(data["tile_size"]),
            tiles={
                int(k): TileCollisionData.from_dict(v)
                for k, v in data.get("tiles", {}).items()
            },
        )

    def save(self, path) -> None:
        """Save to JSON file"""
        import json
        from pathlib import Path

        p = Path(path)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path) -> "TilesetCollisionLibrary":
        """Load from JSON file"""
        import json
        from pathlib import Path

        p = Path(path)
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
