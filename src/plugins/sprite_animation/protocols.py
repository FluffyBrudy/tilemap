"""
Protocol definitions for duck-typed integration with external systems.

Use these Protocols to integrate the sprite animation editor with any
system that provides spritesheets or consumes animation data — no
inheritance required, just implement the methods.
"""

from __future__ import annotations

from typing import Protocol, Tuple, runtime_checkable

import pygame


@runtime_checkable
class SpriteSheetProvider(Protocol):
    """Anything that can supply a spritesheet surface and grid metadata.

    Examples that satisfy this protocol out of the box:
        - TilesetData from tiles_selector (has surface, path, etc.)
        - Any custom object with these three methods
    """

    def get_surface(self) -> pygame.Surface:
        """Return the full spritesheet surface."""
        ...

    def get_tile_size(self) -> Tuple[int, int]:
        """Return (tile_width, tile_height) in pixels."""
        ...

    def get_name(self) -> str:
        """Human-readable name for display in the UI."""
        ...


@runtime_checkable
class AnimationConsumer(Protocol):
    """Anything that wants to receive completed animation data.

    Hook this up to your game engine, export pipeline, or tilemap
    editor to react when animations are created/modified/deleted.
    """

    def on_animation_saved(self, name: str, data: dict) -> None:
        """Called when an animation is saved or updated.

        Args:
            name: Animation name (e.g. "idle", "walk_right")
            data: Serialized animation dict (see Animation.to_dict(); includes ``fps`` and optional ``metadata``)
        """
        ...

    def on_animation_deleted(self, name: str) -> None:
        """Called when an animation is removed from the library."""
        ...
