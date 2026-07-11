"""
Data models for object tileset collision system.
"""

from typing import List, Tuple, Dict, Any
from dataclasses import dataclass, field

from plugins.tileset_collision.models import CollisionPolygon


@dataclass
class RegionCollisionData:
    """Complete collision data for a single region in an object tileset"""

    region_id: str
    region_rect: Tuple[int, int, int, int]
    name: str = ""
    shapes: List[CollisionPolygon] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "region_id": self.region_id,
            "region_rect": list(self.region_rect),
            "name": self.name,
            "shapes": [s.to_dict() for s in self.shapes],
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegionCollisionData":
        return cls(
            region_id=data["region_id"],
            region_rect=tuple(data["region_rect"]),
            name=data.get("name", ""),
            shapes=[CollisionPolygon.from_dict(s) for s in data.get("shapes", [])],
            properties=data.get("properties", {}),
        )


@dataclass
class ObjectTilesetCollisionLibrary:
    """Collection of collision data for all regions in an object tileset"""

    tileset_name: str
    regions: Dict[str, RegionCollisionData] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tileset_name": self.tileset_name,
            "regions": {k: v.to_dict() for k, v in self.regions.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObjectTilesetCollisionLibrary":
        return cls(
            tileset_name=data["tileset_name"],
            regions={
                k: RegionCollisionData.from_dict(v)
                for k, v in data.get("regions", {}).items()
            },
        )

    def save(self, path) -> None:
        import json
        from pathlib import Path

        p = Path(path)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path) -> "ObjectTilesetCollisionLibrary":
        import json
        from pathlib import Path

        p = Path(path)
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
