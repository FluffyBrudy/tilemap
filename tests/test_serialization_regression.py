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
        offset = (0, 0)
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

    # Test with offset (0, 0) and map_size (50, 50) -> bounds from 0 to 50*32 = 1600
    editor = FakeEditor([])
    grid = TileGrid(editor, Rect(0, 0, 800, 600))
    bounds = grid._get_map_bounds()
    assert bounds == (0, 1600, 0, 1600)

    # Test with negative offset - the bounds are now based on offset, not tile content
    # offset (0, 0) with map_size (50, 50) still gives (0, 1600, 0, 1600)
    # Individual tiles outside the boundary are now clamped during placement
    layer1 = FakeTilemap.FakeLayerManager.FakeLayer(
        tiles={(-5, -2): {}, (10, 20): {}}, objects={}
    )
    editor = FakeEditor([layer1])
    grid = TileGrid(editor, Rect(0, 0, 800, 600))
    bounds = grid._get_map_bounds()
    # With the new fixed-bounds model, bounds are offset-based, not tile-based
    # offset=(0,0), map_size=(50,50) -> (0, 1600, 0, 1600)
    assert bounds == (0, 1600, 0, 1600)

    # Test with non-zero offset (-4, 3) and map_size (50, 50)
    # world_min_x = -4 * 32 = -128
    # world_max_x = (-4 + 50) * 32 = 1472
    # world_min_y = 3 * 32 = 96
    # world_max_y = (3 + 50) * 32 = 1696
    editor2 = FakeEditor([])
    editor2.tilemap.offset = (-4, 3)
    grid2 = TileGrid(editor2, Rect(0, 0, 800, 600))
    bounds2 = grid2._get_map_bounds()
    assert bounds2 == (-128, 1472, 96, 1696)
