"""Regression coverage for one-image-per-layer map layers."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from layers import Layer


def test_image_layer_round_trip_and_rejects_content():
    layer = Layer(
        "Backdrop",
        layer_type="image",
        image_path="art/background.png",
        image_rect={"x": -16, "y": 8, "w": 640, "h": 480},
    )
    layer.set_tile((1, 2), {"pos": (1, 2), "ttype": 0, "variant": 0})
    assert layer.add_object((0, 0), {}) == -1
    assert layer.tiles == {}
    assert layer.objects == {}

    restored = Layer.from_dict(layer.to_dict())
    assert restored.layer_type == "image"
    assert restored.image_path == "art/background.png"
    assert restored.image_rect == {"x": -16, "y": 8, "w": 640, "h": 480}


def test_image_layer_ignores_malformed_tile_and_object_payloads():
    layer = Layer.from_dict(
        {
            "name": "Backdrop",
            "type": "image",
            "image_path": "background.png",
            "image_rect": {"x": 0, "y": 0, "w": 32, "h": 32},
            "tiles": {"(1, 2)": {"ttype": 0, "variant": 0}},
            "objects": {"1": {"ttype": 0}},
        }
    )
    assert layer.tiles == {}
    assert layer.objects == {}


def test_save_map_serializes_image_path_relative_to_map(tmp_path):
    from tilemap import Tilemap

    image_path = tmp_path / "assets" / "background.png"
    image_path.parent.mkdir()
    image_path.touch()

    class FakeTilesetWidget:
        tilesets = []
        tileset_map = {}

        def load_object_tileset_companions(self):
            return None

    class FakeTileGrid:
        zoom_level = 1.0
        scroll_x = 0
        scroll_y = 0

        def invalidate_bounds_cache(self):
            pass

    class FakeEditor:
        tileset_widget = FakeTilesetWidget()
        tile_grid_widget = FakeTileGrid()
        autotiler = None
        regex_automap_designer = None
        base_path = tmp_path
        data_root = tmp_path

    tilemap = Tilemap(FakeEditor())
    tilemap.init_size((16, 16), (10, 10))
    layer = tilemap.layer_manager.create_layer("Backdrop", "image")
    layer.image_path = str(image_path)
    layer.image_rect = {"x": 0, "y": 0, "w": 160, "h": 160}

    map_path = tmp_path / "maps" / "example.json"
    assert tilemap.save_map(map_path)
    payload = json.loads(map_path.read_text())
    saved_layer = payload["data"]["layers"][-1]
    assert saved_layer["image_path"] == "../assets/background.png"
    assert saved_layer["image_rect"] == {"x": 0, "y": 0, "w": 160, "h": 160}

    restored = Tilemap(FakeEditor())
    restored.apply_map_payload(map_path, payload)
    restored_layer = restored.layer_manager.layers[-1]
    assert restored_layer.image_path == str(image_path.resolve())
    assert restored_layer.image_rect == {"x": 0, "y": 0, "w": 160, "h": 160}
