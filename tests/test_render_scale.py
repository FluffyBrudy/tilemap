import json
import tempfile
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestRenderScaleModel:
    def test_default_is_1_0(self):
        from tilemap import Tilemap

        class FakeEditor:
            pass

        tm = Tilemap(FakeEditor())
        assert tm.render_scale == 1.0

    def test_can_set_value(self):
        from tilemap import Tilemap

        class FakeEditor:
            pass

        tm = Tilemap(FakeEditor())
        tm.render_scale = 2.5
        assert tm.render_scale == 2.5

    def test_init_size_accepts_render_scale(self):
        from tilemap import Tilemap

        class FakeEditor:
            pass

        tm = Tilemap(FakeEditor())
        tm.init_size((16, 16), (10, 10), render_scale=3.0)
        assert tm.render_scale == 3.0

    def test_init_size_defaults_to_1_0(self):
        from tilemap import Tilemap

        class FakeEditor:
            pass

        tm = Tilemap(FakeEditor())
        tm.render_scale = 2.0
        tm.init_size((16, 16), (10, 10))
        assert tm.render_scale == 1.0

    def test_save_includes_render_scale_in_meta(self):
        from tilemap import Tilemap

        class FakeTilesetWidget:
            tilesets = []

        class FakeTileGrid:
            zoom_level = 1.0
            scroll_x = 0
            scroll_y = 0

            def invalidate_bounds_cache(self):
                pass

        class FakeEditor:
            tileset_widget = FakeTilesetWidget()
            tile_grid_widget = FakeTileGrid()
            base_path = None
            data_root = None

        tm = Tilemap(FakeEditor())
        tm.init_size((16, 16), (10, 10))
        tm.render_scale = 2.0

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            tm.save_map(path)
            with open(path) as f:
                data = json.load(f)
            assert data["meta"]["render_scale"] == 2.0

    def test_load_restores_render_scale(self):
        from tilemap import Tilemap

        payload = {
            "meta": {
                "tile_size": "16;16",
                "map_size": "10;10",
                "initial_map_size": "10;10",
                "render_scale": 4.0,
                "version": "1.1",
            },
            "resources": {"tilesets": []},
            "project_state": {"rules": [], "groups": []},
            "data": {"ongrid": {}, "layers": []},
        }

        class FakeEditor:
            tile_grid_widget = None
            tileset_widget = None
            autotiler = None
            regex_automap_designer = None

        tm = Tilemap(FakeEditor())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            tm.apply_map_payload(path, payload)
            assert tm.render_scale == 4.0

    def test_load_defaults_to_1_0_when_missing(self):
        from tilemap import Tilemap

        payload = {
            "meta": {
                "tile_size": "16;16",
                "map_size": "10;10",
                "initial_map_size": "10;10",
                "version": "1.1",
            },
            "resources": {"tilesets": []},
            "project_state": {"rules": [], "groups": []},
            "data": {"ongrid": {}, "layers": []},
        }

        class FakeEditor:
            tile_grid_widget = None
            tileset_widget = None
            autotiler = None
            regex_automap_designer = None

        tm = Tilemap(FakeEditor())
        tm.render_scale = 99.0
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            tm.apply_map_payload(path, payload)
            assert tm.render_scale == 1.0

    def test_save_load_round_trip(self):
        from tilemap import Tilemap

        class FakeTilesetWidget:
            tilesets = []
            tileset_map = {}

            def load_tileset_from_path(self, *args, **kwargs):
                pass

            def load_object_tileset_companions(self):
                pass

        class FakeTileGrid:
            zoom_level = 1.0
            scroll_x = 0
            scroll_y = 0

            def clamp_view(self):
                pass

            def invalidate_bounds_cache(self):
                pass

        class FakeEditor:
            tileset_widget = FakeTilesetWidget()
            tile_grid_widget = FakeTileGrid()
            base_path = None
            data_root = None
            autotiler = None
            regex_automap_designer = None

        tm = Tilemap(FakeEditor())
        tm.init_size((8, 8), (20, 20))
        tm.render_scale = 3.0

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roundtrip.json"
            tm.save_map(path)
            with open(path) as f:
                data = json.load(f)

            tm2 = Tilemap(FakeEditor())
            tm2.apply_map_payload(path, data)
            assert tm2.render_scale == 3.0
