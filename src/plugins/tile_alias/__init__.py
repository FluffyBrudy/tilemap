"""Alias Composer Plugin — author tile-pattern brushes (aliases).

Standalone editor: left alias list, center grid canvas (the plot
preview — paint exactly as on the map), bottom tileset strip.
Saves ``*.alias.json`` (see ``aliases.py``); the main editor palette
reloads it by mtime. Tile-only by design.
"""

from .editor import AliasComposerEditor

__all__ = ["AliasComposerEditor"]
