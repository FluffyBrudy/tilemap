"""
Sprite Animation Editor Plugin
===============================
A Godot-like sprite animation editor that works standalone or as a plugin.

Standalone usage:
    from plugins.sprite_animation import SpriteAnimationEditor
    editor = SpriteAnimationEditor.from_surface(surface, tile_size=(32, 32))
    editor.run()

Plugin usage:
    editor = SpriteAnimationEditor(rect, surface=surface, tile_size=(32, 32))
    # Call handle_event(event) and draw(screen) in your game loop

Protocol-based integration:
    class MyProvider:
        def get_surface(self) -> pygame.Surface: ...
        def get_tile_size(self) -> Tuple[int, int]: ...
        def get_name(self) -> str: ...

    editor = SpriteAnimationEditor(rect, provider=my_provider)
"""

from .protocols import SpriteSheetProvider, AnimationConsumer
from .models import AnimationFrame, Animation, AnimationLibrary, AnimationMarker
from .editor import SpriteAnimationEditor

__all__ = [
    "SpriteAnimationEditor",
    "SpriteSheetProvider",
    "AnimationConsumer",
    "AnimationFrame",
    "Animation",
    "AnimationLibrary",
    "AnimationMarker",
]
