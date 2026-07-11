"""
Tests for AnimationLibrary.grid_offset field added in PR.

Covers:
- Default value
- to_dict serializes grid_offset
- from_dict deserializes grid_offset
- from_dict falls back to (0, 0) when key is missing (backward compat)
- save/load round-trip preserves grid_offset
- grid_offset is a tuple (not list) after deserialization
"""

import json
import tempfile
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestAnimationLibraryGridOffset:
    """Tests for the grid_offset field on AnimationLibrary."""

    def test_default_grid_offset_is_zero(self):
        from plugins.sprite_animation.models import AnimationLibrary

        lib = AnimationLibrary()
        assert lib.grid_offset == (0, 0)

    def test_to_dict_includes_grid_offset(self):
        from plugins.sprite_animation.models import AnimationLibrary

        lib = AnimationLibrary(grid_offset=(4, 8))
        d = lib.to_dict()
        assert "grid_offset" in d
        assert d["grid_offset"] == [4, 8]

    def test_to_dict_zero_grid_offset(self):
        from plugins.sprite_animation.models import AnimationLibrary

        lib = AnimationLibrary(grid_offset=(0, 0))
        d = lib.to_dict()
        assert d["grid_offset"] == [0, 0]

    def test_from_dict_reads_grid_offset(self):
        from plugins.sprite_animation.models import AnimationLibrary

        data = {
            "spritesheet_path": None,
            "tile_size": [32, 32],
            "grid_offset": [10, 20],
            "animations": {},
        }
        lib = AnimationLibrary.from_dict(data)
        assert lib.grid_offset == (10, 20)

    def test_from_dict_missing_grid_offset_defaults_to_zero(self):
        """Backward-compat: old JSON files without grid_offset key should load fine."""
        from plugins.sprite_animation.models import AnimationLibrary

        data = {
            "spritesheet_path": None,
            "tile_size": [32, 32],
            "animations": {},
        }
        lib = AnimationLibrary.from_dict(data)
        assert lib.grid_offset == (0, 0)

    def test_from_dict_grid_offset_is_tuple(self):
        """grid_offset should be a tuple after deserialization, not a list."""
        from plugins.sprite_animation.models import AnimationLibrary

        data = {
            "spritesheet_path": None,
            "tile_size": [32, 32],
            "grid_offset": [5, 3],
            "animations": {},
        }
        lib = AnimationLibrary.from_dict(data)
        assert isinstance(lib.grid_offset, tuple)

    def test_save_load_round_trip_preserves_grid_offset(self):
        """save() then load() must preserve a non-zero grid_offset."""
        from plugins.sprite_animation.models import AnimationLibrary

        lib = AnimationLibrary(grid_offset=(7, 13), tile_size=(16, 16))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anim.json"
            lib.save(path)
            loaded = AnimationLibrary.load(path)

        assert loaded.grid_offset == (7, 13)

    def test_save_load_round_trip_zero_grid_offset(self):
        """save() then load() preserves (0, 0) grid_offset."""
        from plugins.sprite_animation.models import AnimationLibrary

        lib = AnimationLibrary(grid_offset=(0, 0))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anim.json"
            lib.save(path)
            loaded = AnimationLibrary.load(path)

        assert loaded.grid_offset == (0, 0)

    def test_to_dict_grid_offset_is_list(self):
        """grid_offset is serialized as a JSON list (not tuple) for JSON compat."""
        from plugins.sprite_animation.models import AnimationLibrary

        lib = AnimationLibrary(grid_offset=(2, 6))
        d = lib.to_dict()
        assert isinstance(d["grid_offset"], list)

    def test_grid_offset_stored_alongside_tile_size(self):
        """Both tile_size and grid_offset appear in the serialized dict."""
        from plugins.sprite_animation.models import AnimationLibrary

        lib = AnimationLibrary(tile_size=(16, 16), grid_offset=(4, 4))
        d = lib.to_dict()
        assert d["tile_size"] == [16, 16]
        assert d["grid_offset"] == [4, 4]

    def test_from_dict_large_grid_offset(self):
        """Arbitrary large values are preserved."""
        from plugins.sprite_animation.models import AnimationLibrary

        data = {
            "spritesheet_path": None,
            "tile_size": [32, 32],
            "grid_offset": [128, 256],
            "animations": {},
        }
        lib = AnimationLibrary.from_dict(data)
        assert lib.grid_offset == (128, 256)

    def test_json_file_contains_grid_offset_key(self):
        """The written JSON file contains the grid_offset key."""
        from plugins.sprite_animation.models import AnimationLibrary

        lib = AnimationLibrary(grid_offset=(3, 9))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "anim.json"
            lib.save(path)
            with open(path) as f:
                raw = json.load(f)

        assert "grid_offset" in raw
        assert raw["grid_offset"] == [3, 9]
