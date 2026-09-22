"""Old import path for particle presets. Use plugins.particle_editor instead."""

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
