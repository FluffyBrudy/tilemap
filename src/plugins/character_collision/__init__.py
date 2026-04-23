"""
Character Collision Editor Plugin

Editor for defining collision shapes for character sprites.
Supports rectangle, circle, capsule, and polygon shapes.
"""

from .models import (
    CharacterCollisionData,
    RectangleCollisionData,
    CircleCollisionData,
    CapsuleCollisionData,
    PolygonCollisionData,
)
from .protocols import CollisionShapeType

__all__ = [
    "CharacterCollisionData",
    "RectangleCollisionData",
    "CircleCollisionData",
    "CapsuleCollisionData",
    "PolygonCollisionData",
    "CollisionShapeType",
]
