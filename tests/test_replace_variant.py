"""Tests for Replace Variant (picked source -> brush target, layer-wide)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pygame
from pygame import Rect

from layers import Layer


class FakeNotes:
    def __init__(self):
        self.notes = []
        self.good = []

    def notify(self, msg, *a, **k):
        self.notes.append(msg)

    def success(self, msg, *a, **k):
        self.good.append(msg)


class FakeSurface:
    def __init__(self, w=8 * 32):
        self._w = w

    def get_width(self):
        return self._w


class FakeTilesetData:
    tile_properties = {}

    def __init__(self, w=8 * 32):
        self.surface = FakeSurface(w)


class FakeTilesetWidget:
    def __init__(self, rect=(3 * 32, 0, 32, 32)):
        self.active_idx = 0
        self.tilesets = [FakeTilesetData()]
        self.selected_tile = rect


class FakeTilemap:
    offset = (0, 0)
    map_size = (10, 10)
    tile_size = (32, 32)

    def __init__(self, layer):
        self.layer_manager = type(
            "M", (), {"get_active_layer": lambda self: layer})()
        self.history = []

    def capture_history(self, description=""):
        self.history.append(description)


def make_grid(monkeypatch, tiles, brush=(3 * 32, 0, 32, 32), picked=(0, 1)):
    from widgets.tile_grid import TileGrid

    layer = Layer("t")
    for pos, variant in tiles.items():
        layer.tiles[pos] = {"pos": pos, "ttype": 0, "variant": variant}
    ed = type("E", (), {})()
    ed.node_editing_mode = False
    ed.show_nodes = False
    ed.autotile_mode = False
    ed.tool_manager = None
    ed.tilemap = FakeTilemap(layer)
    ed.notifications = FakeNotes()
    ed.tileset_widget = FakeTilesetWidget(brush)
    ed.last_picked = picked
    ed.autotiler = None
    g = TileGrid.__new__(TileGrid)
    g.editor = ed
    g.rect = Rect(-10000, -10000, 20000, 20000)
    g.hover_cell = None
    g.invalidate_bounds_cache = lambda: None
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
    return g, ed, layer


class TestReplace:
    def test_swaps_matching_only(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch, {(0, 0): 1, (1, 0): 2, (2, 0): 1})
        assert g.replace_variant() == 2
        assert layer.tiles[(0, 0)]["variant"] == 3
        assert layer.tiles[(1, 0)]["variant"] == 2
        assert layer.tiles[(2, 0)]["variant"] == 3
        assert ed.tilemap.history == ["Replace Variant"]
        assert any("2 tiles" in m for m in ed.notifications.good)

    def test_no_source_notifies(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch, {(0, 0): 1}, picked=None)
        assert g.replace_variant() == 0
        assert any("Pick a source" in m for m in ed.notifications.notes)
        assert ed.tilemap.history == []

    def test_cross_tileset_refused(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch, {(0, 0): 1}, picked=(2, 1))
        assert g.replace_variant() == 0
        assert any("one tileset" in m for m in ed.notifications.notes)
        assert layer.tiles[(0, 0)]["variant"] == 1

    def test_match_noop(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch, {(0, 0): 1}, picked=(0, 3))
        assert g.replace_variant() == 0
        assert any("match" in m for m in ed.notifications.notes)

    def test_no_matches_reports(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch, {(0, 0): 9})
        assert g.replace_variant() == 0
        assert any("no matching" in m for m in ed.notifications.notes)
        assert ed.tilemap.history == ["Replace Variant"]

    def test_group_stamped_when_selected(self, monkeypatch):
        from widgets.autotiler import AutotileGroup

        g, ed, layer = make_grid(monkeypatch, {(0, 0): 1})
        ed.autotile_mode = True
        ed.autotiler = type(
            "A", (), {"groups": [AutotileGroup("W")], "selected_group_idx": 0,
                      "variant_to_group": {}})()
        assert g.replace_variant() == 1
        assert layer.tiles[(0, 0)]["autotile_group"] == "W"

    def test_pick_remembers_source(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch, {(4, 4): 5})
        ed.last_picked = None

        class PickingWidget(FakeTilesetWidget):
            def select_tile_by_variant(self, ttype, variant):
                ed.last_picked = None  # prove grid sets it, not the widget

        ed.tileset_widget = PickingWidget()
        g.pick_tile_at((4, 4))
        assert ed.last_picked == (0, 5)
