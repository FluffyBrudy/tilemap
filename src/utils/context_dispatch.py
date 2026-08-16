"""Context-based property event dispatch.

Godot-style "context slots": widgets emit a ``PropertyContext`` describing
what was clicked (right-click on map object, tileset image, tree row, ...);
the dispatcher routes it to the registered opener (shows the PropertyEditor)
or saver (applies the saved properties to the context target).

Same input event everywhere, the context decides the polymorphic handler.
Unregistered kinds no-op cleanly (Qt-style propagation fallback).

Example::

    editor.context_dispatch.open(PropertyContext(ContextKind.TILESET, ts))
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ContextKind(Enum):
    """What was clicked / is being edited."""

    TILESET = auto()       # whole-tileset properties
    TILE_VARIANT = auto()  # per-tile properties (grid tilesets)
    MAP_OBJECT = auto()    # placed object on an object layer
    NODE = auto()          # node (area / particle_emitter / group)
    LAYER = auto()         # layer


@dataclass
class PropertyContext:
    """Context for an open/save property event.

    ``target`` is the typed object the event refers to (TilesetData, Node,
    Layer, ...). ``extra`` carries kind-specific data (e.g. variant_ids).
    """

    kind: ContextKind
    target: Any = None
    extra: dict[str, Any] = field(default_factory=dict)


Opener = Callable[[PropertyContext], None]
Saver = Callable[[PropertyContext, dict[str, Any]], None]


# TODO(dispatcher): temporary shared callback channel. Planned refactor: route
# property open/save through the Editor reference (self.editor) and direct
# widget/manager calls instead of registered openers/savers.
class PropertyContextDispatcher:
    """Routes property open/save events by context kind.

    One registered handler per kind; dispatch is a no-op for unregistered
    kinds so new contexts can be introduced without breaking old ones.
    """

    def __init__(self):
        self._openers: dict[ContextKind, Opener] = {}
        self._savers: dict[ContextKind, Saver] = {}

    def register_opener(self, kind: ContextKind, opener: Opener) -> None:
        self._openers[kind] = opener

    def register_saver(self, kind: ContextKind, saver: Saver) -> None:
        self._savers[kind] = saver

    def open(self, ctx: PropertyContext) -> bool:
        """Show the property editor for the context. Returns True if handled."""
        opener = self._openers.get(ctx.kind)
        if opener is None:
            return False
        opener(ctx)
        return True

    def save(self, ctx: PropertyContext, props: dict[str, Any]) -> bool:
        """Apply saved properties to the context target. Returns True if handled."""
        saver = self._savers.get(ctx.kind)
        if saver is None:
            return False
        saver(ctx, props)
        return True
