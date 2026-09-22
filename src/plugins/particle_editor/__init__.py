"""
Particle Editor Plugin -- standalone particle authoring surface.

Owns the data layer (curated presets, ``*.particles.json`` library
model) plus the standalone editor (canvas-first UI, transport core).

Editor-owned schema: this package decides what a particle system can
be; ``tilemap-parser`` (separate package) is a tolerant consumer.
"""

from .models import (
    FIELD_QUALITIES,
    QUALITY_DENSITY,
    ParticleLibrary,
    ParticleSystemEntry,
    builtin_library,
    builtin_library_path,
    count_for_coverage,
    diff_keys,
    fill_area,
    identify,
    list_libraries,
    modified_from,
    normalize_config,
    validate_config,
)
from .presets import (
    BLANK_NAME,
    PRESETS,
    find_preset,
    get_preset_config,
    get_preset_names,
    get_presets_by_category,
)

__all__ = [
    "BLANK_NAME",
    "FIELD_QUALITIES",
    "PRESETS",
    "QUALITY_DENSITY",
    "ParticleLibrary",
    "ParticleSystemEntry",
    "builtin_library",
    "builtin_library_path",
    "count_for_coverage",
    "diff_keys",
    "fill_area",
    "find_preset",
    "get_preset_config",
    "get_preset_names",
    "get_presets_by_category",
    "identify",
    "list_libraries",
    "modified_from",
    "normalize_config",
    "validate_config",
]
