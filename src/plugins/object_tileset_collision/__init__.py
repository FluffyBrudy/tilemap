"""
Object Tileset Collision Editor — Collision shape editor for object tilesets.

This editor allows drawing collision polygons on object tilesets by defining
manual regions within the sprite sheet, where each region can have its own
collision shapes.
"""

from .editor import ObjectTilesetCollisionEditor
from .models import ObjectTilesetCollisionLibrary, RegionCollisionData

__all__ = [
    "ObjectTilesetCollisionEditor",
    "RegionCollisionData",
    "ObjectTilesetCollisionLibrary",
]
