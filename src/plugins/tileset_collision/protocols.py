"""
Protocol definitions for tileset collision system.

Use these Protocols to integrate the collision editor with any
tileset system — no inheritance required, just implement the methods.
"""

from __future__ import annotations

from typing import Protocol, Tuple, runtime_checkable, Dict, Any

import pygame


@runtime_checkable
class TilesetProvider(Protocol):
    """Anything that can supply a tileset surface and grid metadata.

    Examples that satisfy this protocol:
        - TilesetData from tile_selector (has surface, path, etc.)
        - Any custom object with these methods
    """

    def get_surface(self) -> pygame.Surface:
        """Return the full tileset surface."""
        ...

    def get_tile_size(self) -> Tuple[int, int]:
        """Return (tile_width, tile_height) in pixels."""
        ...

    def get_name(self) -> str:
        """Human-readable name for display in the UI."""
        ...


@runtime_checkable
class CollisionDataConsumer(Protocol):
    """Anything that wants to receive collision data updates.

    Hook this up to your tilemap editor to react when collision
    shapes are created/modified/deleted.
    """

    def on_collision_saved(self, tile_id: int, data: Dict[str, Any]) -> None:
        """Called when collision data for a tile is saved or updated.

        Args:
            tile_id: Tile variant ID (index in tileset)
            data: Serialized collision data dict
        """
        ...

    def on_collision_deleted(self, tile_id: int) -> None:
        """Called when collision data for a tile is removed."""
        ...
