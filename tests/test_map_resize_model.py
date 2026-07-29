import json
import sys
import tempfile
from pathlib import Path

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestMapResizeModel:
    def test_signed_int_input_allows_negative_values(self):
        from widgets.input import SignedIntInput

        rect = pygame.Rect(0, 0, 120, 40)
        input_box = SignedIntInput(rect, "Offset X", "offset_x", default_val="-3")

        assert input_box.get_value() == -3
        assert input_box.get_int_value() == -3

    def test_tilemap_resize_and_save_round_trip_preserve_offset(self):
        from tilemap import Tilemap

        class FakeTileGrid:
            zoom_level = 1.0
            scroll_x = 0
            scroll_y = 0

        class FakeEditor:
            tile_grid_widget = FakeTileGrid()
            tileset_widget = None
            autotiler = None
            base_path = None
            data_root = None
            regex_automap_designer = None

        tm = Tilemap(FakeEditor())
        tm.init_size((16, 16), (10, 10))
        tm.resize((-4, 3), (12, 9))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.json"
            tm.save_map(path)
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)

        assert "initial_map_size" not in payload["meta"]
        assert payload["meta"]["offset"] == "-4;3"
        assert tm.offset == (-4, 3)
