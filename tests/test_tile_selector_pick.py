"""
Tests for TileSelector.select_tile_by_variant() added in PR.

Covers:
- Returns False for out-of-range tileset index
- Object tileset: selects whole image, returns True
- Tile tileset: correct (x, y, w, h) selection for variant 0
- Tile tileset: correct position for arbitrary variant (row/col calculation)
- Returns False when tile_size is zero
- Returns False when variant is out of bounds
- Sets active_idx to the requested tileset index
- Returns False for negative tileset index
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

import pygame
import pytest
from pygame import Rect

from widgets.tile_selector import TileSelector

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


def _make_surface(w: int, h: int, color=(100, 100, 200)) -> pygame.Surface:
    surf = pygame.Surface((w, h))
    surf.fill(color)
    return surf


class FakeTilemap:
    def __init__(self, tile_size=(32, 32)):
        self.tile_size = tile_size


class FakeEditor:
    def __init__(self, tile_size=(32, 32)):
        self.tilemap = FakeTilemap(tile_size)


def _make_selector(tile_size=(32, 32)) -> "TileSelector":

    editor = FakeEditor(tile_size=tile_size)
    ts = TileSelector(editor, x=0, y=0, w=400, h=600)
    return ts


def _add_tile_tileset(selector, surface) -> int:
    from widgets.tile_selector import TilesetData

    idx = len(selector.tilesets)
    td = TilesetData(
        name=f"ts{idx}",
        path=Path(f"fake{idx}.png"),
        surface=surface,
        tileset_type="tile",
    )
    selector.tilesets.append(td)
    selector.tileset_map[idx] = td
    return idx


def _add_object_tileset(selector, surface) -> int:
    from widgets.tile_selector import TilesetData

    idx = len(selector.tilesets)
    td = TilesetData(
        name=f"obj{idx}",
        path=Path(f"obj{idx}.png"),
        surface=surface,
        tileset_type="object",
    )
    selector.tilesets.append(td)
    selector.tileset_map[idx] = td
    return idx


class TestSelectTileByVariantBoundsChecks:
    def test_returns_false_for_negative_index(self):
        sel = _make_selector()
        _add_tile_tileset(sel, _make_surface(128, 64))
        assert sel.select_tile_by_variant(-1, 0) is False

    def test_returns_false_for_index_too_large(self):
        sel = _make_selector()
        _add_tile_tileset(sel, _make_surface(128, 64))
        assert sel.select_tile_by_variant(5, 0) is False

    def test_returns_false_for_empty_tilesets(self):
        sel = _make_selector()
        assert sel.select_tile_by_variant(0, 0) is False

    def test_returns_false_for_zero_tile_size(self):
        sel = _make_selector(tile_size=(0, 0))
        _add_tile_tileset(sel, _make_surface(128, 64))
        assert sel.select_tile_by_variant(0, 0) is False

    def test_returns_false_for_out_of_bounds_variant(self):
        """Variant beyond the sheet bounds should return False."""
        # 128x64 sheet with 32x32 tiles → 4 cols × 2 rows = 8 tiles (ids 0–7)
        sel = _make_selector(tile_size=(32, 32))
        _add_tile_tileset(sel, _make_surface(128, 64))
        # variant 8 would be row 2 → y=64 which equals height, out of bounds
        assert sel.select_tile_by_variant(0, 8) is False


class TestSelectTileByVariantTileTileset:
    def test_variant_0_selects_top_left_tile(self):
        sel = _make_selector(tile_size=(32, 32))
        idx = _add_tile_tileset(sel, _make_surface(128, 64))
        result = sel.select_tile_by_variant(idx, 0)
        assert result is True
        assert sel.selected_tile == (0, 0, 32, 32)

    def test_variant_1_selects_second_column(self):
        sel = _make_selector(tile_size=(32, 32))
        idx = _add_tile_tileset(sel, _make_surface(128, 64))
        result = sel.select_tile_by_variant(idx, 1)
        assert result is True
        assert sel.selected_tile == (32, 0, 32, 32)

    def test_variant_4_selects_first_col_second_row(self):
        """128px wide / 32px = 4 cols; variant 4 → col 0, row 1."""
        sel = _make_selector(tile_size=(32, 32))
        idx = _add_tile_tileset(sel, _make_surface(128, 64))
        result = sel.select_tile_by_variant(idx, 4)
        assert result is True
        assert sel.selected_tile == (0, 32, 32, 32)

    def test_variant_7_selects_last_tile(self):
        """128x64 sheet, 32x32 tiles → 4 cols, 2 rows; variant 7 = col 3, row 1."""
        sel = _make_selector(tile_size=(32, 32))
        idx = _add_tile_tileset(sel, _make_surface(128, 64))
        result = sel.select_tile_by_variant(idx, 7)
        assert result is True
        assert sel.selected_tile == (96, 32, 32, 32)

    def test_sets_active_idx(self):
        sel = _make_selector(tile_size=(32, 32))
        idx = _add_tile_tileset(sel, _make_surface(128, 64))
        sel.select_tile_by_variant(idx, 0)
        assert sel.active_idx == idx

    def test_switches_to_correct_tileset_index(self):
        """When multiple tilesets exist, active_idx must be updated to requested one."""
        sel = _make_selector(tile_size=(32, 32))
        _add_tile_tileset(sel, _make_surface(128, 64))  # idx 0
        idx1 = _add_tile_tileset(sel, _make_surface(64, 64))  # idx 1
        sel.select_tile_by_variant(idx1, 0)
        assert sel.active_idx == idx1

    def test_16x16_tile_size_variant_calculation(self):
        """Smaller tile sizes should also produce correct column/row."""
        # 64px wide / 16px = 4 cols; variant 5 → col 1, row 1
        sel = _make_selector(tile_size=(16, 16))
        idx = _add_tile_tileset(sel, _make_surface(64, 64))
        result = sel.select_tile_by_variant(idx, 5)
        assert result is True
        assert sel.selected_tile == (16, 16, 16, 16)


class TestSelectTileByVariantObjectTileset:
    def test_object_tileset_selects_whole_surface(self):
        sel = _make_selector()
        surf = _make_surface(80, 96)
        idx = _add_object_tileset(sel, surf)
        result = sel.select_tile_by_variant(idx, 0)
        assert result is True
        assert sel.selected_tile == (0, 0, 80, 96)

    def test_object_tileset_sets_active_idx(self):
        sel = _make_selector()
        surf = _make_surface(80, 96)
        idx = _add_object_tileset(sel, surf)
        sel.select_tile_by_variant(idx, 42)  # variant_id ignored for objects
        assert sel.active_idx == idx

    def test_object_tileset_returns_true(self):
        sel = _make_selector()
        idx = _add_object_tileset(sel, _make_surface(32, 32))
        assert sel.select_tile_by_variant(idx, 99) is True
