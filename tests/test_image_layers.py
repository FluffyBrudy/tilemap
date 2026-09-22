"""Regression coverage for one-image-per-layer map layers."""

import json
import sys
from pathlib import Path


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


def _bg_layer():
    return Layer(
        "Backdrop",
        layer_type="image",
        image_path="art/background.png",
        image_rect={"x": 0, "y": 0, "w": 640, "h": 480},
    )


class TestImagePlacements:
    def test_legacy_files_have_no_placement_keys(self):
        d = _bg_layer().to_dict()
        assert "image_placements" not in d
        assert "next_placement_id" not in d

    def test_first_duplicate_seeds_from_image_rect(self):
        layer = _bg_layer()
        pid = layer.add_placement({"x": 640, "y": 0, "w": 640, "h": 480})
        assert pid == 2  # seed copy took pid 1
        assert [p.pid for p in layer.image_placements] == [1, 2]
        assert (layer.image_placements[0].x, layer.image_placements[0].w) == (0, 640)

    def test_pids_never_reused_after_delete(self):
        layer = _bg_layer()
        a = layer.add_placement({"x": 1, "y": 0, "w": 10, "h": 10})
        b = layer.add_placement({"x": 2, "y": 0, "w": 10, "h": 10})
        assert layer.remove_placement(a) is True
        c = layer.add_placement({"x": 3, "y": 0, "w": 10, "h": 10})
        assert (a, b, c) == (2, 3, 4)
        assert layer.get_placement(a) is None

    def test_round_trip_and_malformed_entries_dropped(self):
        layer = _bg_layer()
        layer.add_placement({"x": 640, "y": 0, "w": 640, "h": 480})
        d = layer.to_dict()
        assert d["next_placement_id"] == 3
        restored = Layer.from_dict(d)
        assert [p.pid for p in restored.image_placements] == [1, 2]
        assert restored.next_placement_id == 3
        # New pid continues past restored max, never collides.
        assert restored.add_placement({"x": 0, "y": 0, "w": 8, "h": 8}) == 3

        bad = Layer.from_dict(
            {
                "name": "B", "type": "image",
                "image_placements": [{"pid": "x"}, {"x": 1}, {"pid": 7, "x": 1, "y": 2, "w": 3, "h": 4}],
                "next_placement_id": "nope",
            }
        )
        assert [p.pid for p in bad.image_placements] == [7]
        assert bad.next_placement_id == 8

    def test_reorder_changes_paint_order(self):
        layer = _bg_layer()
        layer.add_placement({"x": 1, "y": 0, "w": 10, "h": 10})
        layer.add_placement({"x": 2, "y": 0, "w": 10, "h": 10})
        assert layer.reorder_placement(3, 0) is True
        assert [p.pid for p in layer.image_placements] == [3, 1, 2]
        assert layer.reorder_placement(99, 0) is False

    def test_locked_layer_refuses_placement_edits(self):
        layer = _bg_layer()
        layer.locked = True
        assert layer.add_placement({"x": 0, "y": 0, "w": 8, "h": 8}) == -1
        assert layer.remove_placement(1) is False


def test_save_load_round_trips_placements(tmp_path):
    from tilemap import Tilemap

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

    image_path = tmp_path / "assets" / "bg.png"
    image_path.parent.mkdir()
    image_path.touch()

    tilemap = Tilemap(FakeEditor())
    tilemap.init_size((16, 16), (10, 10))
    layer = tilemap.layer_manager.create_layer("Backdrop", "image")
    layer.image_path = str(image_path)
    layer.image_rect = {"x": 0, "y": 0, "w": 160, "h": 160}
    pid = layer.add_placement({"x": 160, "y": 0, "w": 160, "h": 160})
    assert pid == 2

    map_path = tmp_path / "maps" / "example.json"
    assert tilemap.save_map(map_path)
    payload = json.loads(map_path.read_text())
    saved_layer = payload["data"]["layers"][-1]
    assert saved_layer["image_placements"] == [
        {"pid": 1, "x": 0, "y": 0, "w": 160, "h": 160, "mode": "stretch"},
        {"pid": 2, "x": 160, "y": 0, "w": 160, "h": 160, "mode": "stretch"},
    ]
    assert saved_layer["next_placement_id"] == 3

    restored = Tilemap(FakeEditor())
    restored.apply_map_payload(map_path, payload)
    restored_layer = restored.layer_manager.layers[-1]
    assert [p.pid for p in restored_layer.image_placements] == [1, 2]
    assert restored_layer.next_placement_id == 3
    assert restored_layer.add_placement({"x": 0, "y": 0, "w": 8, "h": 8}) == 3
