import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.serialization import deserialize_point, serialize_point


def test_serialize_point_fractional():
    # Retain fractional coordinates
    assert serialize_point((12.75, 4.5)) == "12.75;4.5"
    assert serialize_point((12, 4)) == "12;4"
    assert (
        serialize_point((12.0, 4.0)) == "12;4"
    )  # whole floats should be formatted as int


def test_deserialize_point_fractional_round_trip():
    # Round-trip check
    p_str = "12.75;4.5"
    parsed = deserialize_point(p_str)
    assert parsed == (12.75, 4.5)

    # Integers should remain int
    assert deserialize_point("12;4") == (12, 4)
    # Different separators
    assert deserialize_point("12.75,4.5") == (12.75, 4.5)
    assert deserialize_point("12.75 4.5") == (12.75, 4.5)


def test_deserialize_point_strict_regex_fullmatch():
    # re.fullmatch validation: reject malformed prefixes/suffixes
    with pytest.raises(ValueError):
        deserialize_point("abc 12;4")
    with pytest.raises(ValueError):
        deserialize_point("12;4 def")
    with pytest.raises(ValueError):
        deserialize_point("12;;4")


def test_tile_grid_map_bounds_calculation():
    import pygame

    pygame.font.init()

    # Mock classes to test tile_grid bounds calculation
    class FakeTilemap:
        tile_size = (32, 32)
        map_size = (50, 50)
        initialized = True
        render_scale = 1.0

        class FakeLayerManager:
            class FakeLayer:
                def __init__(self, tiles, objects, layer_type="tile"):
                    self.tiles = tiles
                    self.objects = objects
                    self.layer_type = layer_type
                    self.name = "Layer"
                    self.visible = True
                    self.locked = False
                    self.opacity = 1.0
                    self.properties = {}

            def __init__(self, layers):
                self.layers = layers

        def __init__(self, layers):
            self.layer_manager = self.FakeLayerManager(layers)

    class FakeEditor:
        def __init__(self, layers):
            self.tilemap = FakeTilemap(layers)
            self.tileset_widget = None

    from pygame import Rect

    from widgets.tile_grid import TileGrid

    # Test empty layers boundary (should match initial map size 0 to 50 * 32 = 1600)
    editor = FakeEditor([])
    grid = TileGrid(editor, Rect(0, 0, 800, 600))
    bounds = grid._get_map_bounds()
    assert bounds == (0, 1600, 0, 1600)

    # Test layers with negative tiles
    layer1 = FakeTilemap.FakeLayerManager.FakeLayer(
        tiles={(-5, -2): {}, (10, 20): {}}, objects={}
    )
    editor = FakeEditor([layer1])
    grid = TileGrid(editor, Rect(0, 0, 800, 600))
    bounds = grid._get_map_bounds()
    # min_col = -5 -> -160, max_col = 50 -> 1600
    # min_row = -2 -> -64, max_row = 50 -> 1600
    assert bounds == (-160, 1600, -64, 1600)
