"""
Protocol definitions for character collision system.

Use these Protocols to integrate the collision system with any
game engine or character system — no inheritance required, just implement the methods.
"""

from __future__ import annotations

from typing import Protocol, Tuple, runtime_checkable, List, Optional
from enum import Enum


class CollisionShapeType(Enum):
    """Types of collision shapes supported by the system"""
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    CAPSULE = "capsule"
    POLYGON = "polygon"


class CollisionInfo:
    """Information about a collision between two shapes"""
    def __init__(
        self,
        collided: bool,
        normal: Tuple[float, float] = (0.0, 0.0),
        penetration: float = 0.0,
        contact_point: Tuple[float, float] = (0.0, 0.0),
        other_shape_id: Optional[str] = None
    ):
        self.collided = collided
        self.normal = normal
        self.penetration = penetration
        self.contact_point = contact_point
        self.other_shape_id = other_shape_id


@runtime_checkable
class CollisionShape(Protocol):
    """Abstract collision shape that any character can implement.
    
    This is the core interface that all collision objects must provide.
    The character collision system works with any object that implements this protocol.
    """
    
    def get_shape_type(self) -> CollisionShapeType:
        """Return the type of collision shape."""
        ...
    
    def get_bounds(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Return bounding box as ((min_x, min_y), (max_x, max_y))."""
        ...
    
    def get_position(self) -> Tuple[float, float]:
        """Return current world position."""
        ...
    
    def set_position(self, position: Tuple[float, float]) -> None:
        """Set world position."""
        ...
    
    def check_collision_with_shape(self, other: 'CollisionShape') -> CollisionInfo:
        """Check collision with another shape and return collision info."""
        ...
    
    def move_and_collide(self, offset: Tuple[float, float]) -> CollisionInfo:
        """Attempt to move by offset and return collision info."""
        ...


@runtime_checkable
class RectangleShape(CollisionShape, Protocol):
    """Rectangle collision shape with width and height."""
    
    def get_size(self) -> Tuple[float, float]:
        """Return (width, height)."""
        ...


@runtime_checkable
class CircleShape(CollisionShape, Protocol):
    """Circle collision shape with radius."""
    
    def get_radius(self) -> float:
        """Return circle radius."""
        ...


@runtime_checkable
class CapsuleShape(CollisionShape, Protocol):
    """Capsule collision shape with radius and height."""
    
    def get_radius(self) -> float:
        """Return capsule radius."""
        ...
    
    def get_height(self) -> float:
        """Return capsule height (excluding end caps)."""
        ...


@runtime_checkable
class PolygonShape(CollisionShape, Protocol):
    """Polygon collision shape with vertices."""
    
    def get_vertices(self) -> List[Tuple[float, float]]:
        """Return list of vertices in local space."""
        ...


@runtime_checkable
class CharacterCollider(Protocol):
    """Any object that wants to participate in character collision.
    
    Characters implement this to provide their collision shape and receive collision callbacks.
    """
    
    def get_collision_shape(self) -> CollisionShape:
        """Return the character's collision shape."""
        ...
    
    def get_character_id(self) -> str:
        """Return unique identifier for this character."""
        ...
    
    def on_collision_enter(self, collision_info: CollisionInfo) -> None:
        """Called when character enters a collision."""
        ...
    
    def on_collision_exit(self, other_id: str) -> None:
        """Called when character exits a collision."""
        ...


@runtime_checkable
class TilemapCollisionProvider(Protocol):
    """Provider for tilemap collision data.
    
    The character collision system queries this to check collisions with tilemap tiles.
    """
    
    def get_tile_collision_shapes_at(self, x: int, y: int) -> List[CollisionShape]:
        """Return collision shapes for tiles at the given tile coordinates."""
        ...
    
    def get_tiles_in_bounds(self, bounds: Tuple[Tuple[float, float], Tuple[float, float]]) -> List[Tuple[int, int]]:
        """Return list of tile positions within the given bounds."""
        ...
    
    def world_to_tile(self, world_pos: Tuple[float, float]) -> Tuple[int, int]:
        """Convert world coordinates to tile coordinates."""
        ...


@runtime_checkable
class CollisionWorldConsumer(Protocol):
    """Anything that wants to receive collision world updates.
    
    Hook this up to your game engine to react when collision events occur.
    """
    
    def on_collision_detected(self, char1_id: str, char2_id: str, collision_info: CollisionInfo) -> None:
        """Called when a collision between two characters is detected."""
        ...
    
    def on_tile_collision_detected(self, char_id: str, tile_pos: Tuple[int, int], collision_info: CollisionInfo) -> None:
        """Called when a character collides with a tile."""
        ...
