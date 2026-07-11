"""
Protocol definitions for object tileset collision system.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Dict, Any

import pygame


@runtime_checkable
class ObjectTilesetProvider(Protocol):
    """Anything that can supply an object tileset surface and metadata."""

    def get_surface(self) -> pygame.Surface:
        """Return the full object tileset surface."""
        ...

    def get_name(self) -> str:
        """Human-readable name for display in the UI."""
        ...


@runtime_checkable
class ObjectTilesetCollisionConsumer(Protocol):
    """Anything that wants to receive collision data updates."""

    def on_region_collision_saved(self, region_id: str, data: Dict[str, Any]) -> None:
        """Called when collision data for a region is saved or updated.

        Args:
            region_id: Region identifier
            data: Serialized collision data dict
        """
        ...

    def on_region_collision_deleted(self, region_id: str) -> None:
        """Called when collision data for a region is removed."""
        ...
