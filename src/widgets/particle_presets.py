"""Deprecated shim over ``plugins.particle_editor.presets``.

Phase A of the particle rework curates the legacy ~66-preset table down
to 11 essentials + Blank, owned by the new plugin package. This module
keeps its public API (``PRESETS``, ``get_preset_names``,
``find_preset``, ``get_preset_config``, ``get_presets_by_category``)
so existing importers (e.g. ``widgets.ui.node_editor``) keep working.
New code must import from ``plugins.particle_editor`` directly.
"""

from __future__ import annotations

from plugins.particle_editor.presets import (
    BLANK_NAME,
    PRESETS,
    find_preset,
    get_preset_config,
    get_preset_names,
    get_presets_by_category,
)

ParticlePreset = dict[str, object]
PresetEntry = dict[str, object]

__all__ = [
    "BLANK_NAME",
    "PRESETS",
    "ParticlePreset",
    "PresetEntry",
    "find_preset",
    "get_preset_config",
    "get_preset_names",
    "get_presets_by_category",
]
