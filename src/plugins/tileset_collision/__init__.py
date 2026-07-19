"""
Tileset Collision Editor Plugin

Godot-like collision painter for tilesets with polygon drawing/erasing capabilities.
"""

from .editor import TilesetCollisionEditor
from .models import CollisionPolygon, TileCollisionData
from .protocols import CollisionDataConsumer, TilesetProvider

__all__ = [
    "TilesetCollisionEditor",
    "CollisionPolygon",
    "TileCollisionData",
    "TilesetProvider",
    "CollisionDataConsumer",
]
