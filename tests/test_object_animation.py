"""
Tests for Object Animation support across Tilemap, TileSelector, TileGrid, and PropertyContext.

Covers:
- Object animation persistence and serialization roundtrips
- Object tileset animation configuration (frame_w, frame_h computation)
- Object placement using single frame size for animated object tilesets
- Object animation properties synchronization (anim_* -> obj["animation"])
"""

import os
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from layers import Layer, LayerManager
from ttypes.tilemap import TypeObject
from utils.context_dispatch import (
    ContextKind,
    PropertyContext,
    PropertyContextDispatcher,
)
from utils.property_suggestions import PropertySuggestionRegistry
from utils.serialization import copy_object, serialize_object
from widgets.tile_selector import TileSelector, TilesetData


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


class FakeEditor:
    def __init__(self):
        self.width = 800
        self.height = 600
        self.context_dispatch = PropertyContextDispatcher()
        self.suggestion_registry = PropertySuggestionRegistry()
        self.tileset_widget = None
        self.tilemap = None
        self.node_manager = None
        self.clock = pygame.time.Clock()


class TestObjectAnimationSerialization:
    def test_copy_object_preserves_animation_and_properties(self):
        obj: TypeObject = {
            "area": {"x": 10, "y": 20, "w": 32, "h": 32},
            "ttype": 1,
            "tileset_type": "object",
            "variant": 0,
            "properties": {"tag": "interactable"},
            "animation": {
                "frame_count": 4,
                "frame_duration_ms": 150,
                "speed": 1.5,
                "animation_mode": "random_start_times",
            },
        }

        copied = copy_object(obj)
        assert copied["area"] == {"x": 10, "y": 20, "w": 32, "h": 32}
        assert copied["properties"] == {"tag": "interactable"}
        assert copied["animation"] == {
            "frame_count": 4,
            "frame_duration_ms": 150,
            "speed": 1.5,
            "animation_mode": "random_start_times",
        }
        # Independent references
        copied["animation"]["speed"] = 2.0
        assert obj["animation"]["speed"] == 1.5

        serialized = serialize_object(obj)
        assert serialized["animation"]["frame_count"] == 4

    def test_layer_to_dict_from_dict_preserves_object_animation(self):
        layer = Layer(name="Objects", layer_type="object")
        obj: TypeObject = {
            "area": {"x": 50, "y": 100, "w": 48, "h": 48},
            "ttype": 2,
            "tileset_type": "object",
            "variant": 0,
            "animation": {
                "frame_count": 6,
                "frame_duration_ms": 100,
                "frames": [0, 1, 2, 3, 2, 1],
            },
        }
        obj_id = layer.add_object((50, 100), obj)
        assert obj_id == 1

        data = layer.to_dict()
        assert "1" in data["objects"]
        assert data["objects"]["1"]["animation"]["frame_count"] == 6
        assert data["objects"]["1"]["animation"]["frames"] == [0, 1, 2, 3, 2, 1]

        loaded_layer = Layer.from_dict(data)
        loaded_obj = loaded_layer.get_object(1)
        assert loaded_obj is not None
        assert loaded_obj["animation"]["frame_count"] == 6
        assert loaded_obj["animation"]["frames"] == [0, 1, 2, 3, 2, 1]


    def test_copy_object_deepcopies_frames_list(self):
        obj: TypeObject = {
            "area": {"x": 0, "y": 0, "w": 32, "h": 32},
            "ttype": 0,
            "tileset_type": "object",
            "variant": 0,
            "animation": {
                "frames": [0, 1, 2],
            },
        }
        copied = copy_object(obj)
        copied["animation"]["frames"].append(3)
        assert obj["animation"]["frames"] == [0, 1, 2]
        assert copied["animation"]["frames"] == [0, 1, 2, 3]

    def test_layer_to_dict_from_dict_preserves_layer_properties(self):
        layer = Layer(name="Main", layer_type="tile")
        layer.properties = {"theme": "forest", "ambient_light": 0.8}
        data = layer.to_dict()
        assert data["properties"] == {"theme": "forest", "ambient_light": 0.8}

        restored = Layer.from_dict(data)
        assert restored.properties == {"theme": "forest", "ambient_light": 0.8}


class TestObjectAnimationPropertiesSync:
    def test_open_object_properties_exposes_anim_keys(self):
        editor = FakeEditor()
        selector = TileSelector(editor, x=0, y=0, w=400, h=600)
        surf = pygame.Surface((128, 32))
        ts = TilesetData("torch_sheet", Path("torch.png"), surf, tileset_type="object")
        selector.tilesets.append(ts)
        selector.tileset_map[0] = ts

        obj: TypeObject = {
            "area": {"x": 0, "y": 0, "w": 32, "h": 32},
            "ttype": 0,
            "tileset_type": "object",
            "variant": 0,
            "properties": {"name": "Torch A"},
            "animation": {
                "frame_count": 4,
                "frame_duration_ms": 120,
                "speed": 1.0,
            },
        }

        ctx = PropertyContext(
            ContextKind.MAP_OBJECT,
            obj,
            {"obj_id": 0, "layer_name": "Objects", "tileset_name": ts.name},
        )
        selector.editor.context_dispatch.open(ctx)

        pe = selector.editor.property_editor
        assert pe is not None
        assert pe.properties["name"] == "Torch A"
        assert pe.properties["anim_frame_count"] == 4
        assert pe.properties["anim_frame_duration_ms"] == 120
        assert pe.properties["anim_speed"] == 1.0

    def test_save_object_properties_syncs_anim_keys_to_animation_dict(self):
        editor = FakeEditor()
        selector = TileSelector(editor, x=0, y=0, w=400, h=600)
        surf = pygame.Surface((128, 32))
        ts = TilesetData("torch_sheet", Path("torch.png"), surf, tileset_type="object")
        selector.tilesets.append(ts)
        selector.tileset_map[0] = ts

        obj: TypeObject = {
            "area": {"x": 0, "y": 0, "w": 32, "h": 32},
            "ttype": 0,
            "tileset_type": "object",
            "variant": 0,
            "animation": {
                "speed": 1.0,
                "frame_count": 4,
            },
        }

        ctx = PropertyContext(
            ContextKind.MAP_OBJECT,
            obj,
            {"obj_id": 0, "layer_name": "Objects", "tileset_name": ts.name},
        )
        selector.editor.context_dispatch.open(ctx)

        selector.editor.context_dispatch.save(
            ctx,
            {
                "interactable": True,
                "anim_speed": 1.75,
                "anim_frame_count": 4,
                "anim_random_phase": True,
            },
        )

        assert obj["properties"] == {"interactable": True}
        assert obj["animation"] == {
            "speed": 1.75,
            "frame_count": 4,
            "random_phase": True,
        }

    def test_save_object_properties_replaces_and_deletes_empty_animation(self):
        editor = FakeEditor()
        selector = TileSelector(editor, x=0, y=0, w=400, h=600)
        obj: TypeObject = {
            "area": {"x": 0, "y": 0, "w": 32, "h": 32},
            "ttype": 0,
            "tileset_type": "object",
            "variant": 0,
            "animation": {"speed": 1.0, "frame_count": 4},
        }

        ctx = PropertyContext(ContextKind.MAP_OBJECT, obj, {"obj_id": 0})
        # Simulate open to track generated keys
        selector.editor.context_dispatch.open(ctx)
        # Save without any animation keys
        selector.editor.context_dispatch.save(ctx, {"tag": "prop"})
        assert obj["properties"] == {"tag": "prop"}
        assert "animation" not in obj

    def test_save_object_properties_preserves_legitimate_anim_named_properties(self):
        editor = FakeEditor()
        selector = TileSelector(editor, x=0, y=0, w=400, h=600)
        obj: TypeObject = {
            "area": {"x": 0, "y": 0, "w": 32, "h": 32},
            "ttype": 0,
            "tileset_type": "object",
            "variant": 0,
            "properties": {"anim_speed": 5.0, "normal_prop": "hello"},
        }

        ctx = PropertyContext(ContextKind.MAP_OBJECT, obj, {"obj_id": 0})
        selector.editor.context_dispatch.open(ctx)
        selector.editor.context_dispatch.save(ctx, {"anim_speed": 6.0, "normal_prop": "hello"})
        assert obj["properties"] == {"anim_speed": 6.0, "normal_prop": "hello"}
        assert "animation" not in obj


class TestObjectTilesetLoadDimensions:
    def test_animated_object_tileset_computes_frame_dimensions(self):
        editor = FakeEditor()
        selector = TileSelector(editor, x=0, y=0, w=400, h=600)

        # 128x32 image with 4 frames -> each frame is 32x32
        surf = pygame.Surface((128, 32))
        path = Path("coin_spin.png")
        anim_config = {
            "frame_count": 4,
            "frame_duration_ms": 100,
            "loop": True,
            "animation_mode": "default",
            "frame_w": 32,
            "frame_h": 32,
        }

        ts = TilesetData(path.name, path, surf, tileset_type="object")
        ts.animation = anim_config
        selector.tilesets.append(ts)
        selector.tileset_map[0] = ts

        selector._on_tree_selection([ts.uid])
        assert selector.selected_tile == (0, 0, 32, 32)

    def test_missing_one_dimension_falls_back_cleanly(self):
        editor = FakeEditor()
        selector = TileSelector(editor, x=0, y=0, w=400, h=600)

        surf = pygame.Surface((128, 32))
        path = Path("coin_spin.png")
        # Only frame_w without frame_h
        anim_config = {
            "frame_count": 4,
            "frame_w": 32,
        }

        ts = TilesetData(path.name, path, surf, tileset_type="object")
        ts.animation = anim_config
        selector.tilesets.append(ts)
        selector.tileset_map[0] = ts

        # Should fall back to 128//4 = 32 width without KeyError
        selector._on_tree_selection([ts.uid])
        assert selector.selected_tile == (0, 0, 32, 32)
