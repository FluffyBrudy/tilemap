"""Tests for the line tool (drag line, brush cycling, one history entry)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pygame
from pygame import Rect

from layers import Layer
from widgets.ui.tool_manager import ToolKind, ToolManager


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
    def __init__(self, rect=(0, 0, 2 * 32, 32)):
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


def make_grid(monkeypatch, brush=(0, 0, 2 * 32, 32)):
    from widgets.tile_grid import TileGrid

    layer = Layer("t")
    ed = type("E", (), {})()
    ed.node_editing_mode = False
    ed.show_nodes = False
    ed.autotile_mode = False
    ed.tool_manager = ToolManager()
    ed.tilemap = FakeTilemap(layer)
    ed.notifications = FakeNotes()
    ed.tileset_widget = FakeTilesetWidget(brush)
    ed.dice_brush = False
    g = TileGrid.__new__(TileGrid)
    g.editor = ed
    g.rect = Rect(-10000, -10000, 20000, 20000)
    g.hover_cell = None
    g.line_start = None
    g.line_end = None
    g.invalidate_bounds_cache = lambda: None

    class NoScroll:
        def handle_event(self, event):
            return False

    g._v_scroll = NoScroll()
    g._h_scroll = NoScroll()
    g._handle_image_layer_event = lambda event: False
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
    return g, ed, layer


def stroke(g, x0, y0, x1, y1):
    g.line_start = (x0, y0)
    g.line_end = (x1, y1)
    g._commit_line()


class TestBresenham:
    def test_horizontal(self):
        from widgets.tile_grid import TileGrid

        assert TileGrid.bresenham_line(0, 0, 3, 0) == [(0, 0), (1, 0), (2, 0), (3, 0)]

    def test_vertical(self):
        from widgets.tile_grid import TileGrid

        assert TileGrid.bresenham_line(1, 1, 1, 3) == [(1, 1), (1, 2), (1, 3)]

    def test_single_point(self):
        from widgets.tile_grid import TileGrid

        assert TileGrid.bresenham_line(2, 2, 2, 2) == [(2, 2)]

    def test_diagonal_connected(self):
        from widgets.tile_grid import TileGrid

        cells = TileGrid.bresenham_line(0, 0, 2, 2)
        assert cells[0] == (0, 0) and cells[-1] == (2, 2)
        for (ax, ay), (bx, by) in zip(cells, cells[1:]):
            assert abs(ax - bx) <= 1 and abs(ay - by) <= 1


class TestLineCommit:
    def test_paints_line_once(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        stroke(g, 0, 0, 3, 0)
        assert len(layer.tiles) == 4
        assert ed.tilemap.history == ["Line"]
        assert any("4 tiles" in m for m in ed.notifications.good)

    def test_brush_cycles_along_line(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        stroke(g, 0, 0, 3, 0)
        assert [layer.tiles[(x, 0)]["variant"] for x in range(4)] == [0, 1, 0, 1]

    def test_state_reset(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        stroke(g, 0, 0, 2, 0)
        assert g.line_start is None and g.line_end is None

    def test_no_brush_noop(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        ed.tileset_widget.selected_tile = None
        stroke(g, 0, 0, 2, 0)
        assert layer.tiles == {}
        assert ed.tilemap.history == []

    def test_dice_randomizes_steps(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        ed.dice_brush = True
        stroke(g, 0, 0, 7, 0)
        assert len(layer.tiles) == 8
        got = {t["variant"] for t in layer.tiles.values()}
        assert got <= {0, 1}

    def test_l_key_toggles(self, monkeypatch):
        g, ed, _ = make_grid(monkeypatch)
        monkeypatch.setattr(pygame.key, "get_mods", lambda: 0)
        ev = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_l, "unicode": ""})
        assert g.handle_event(ev) is True
        assert ed.tool_manager.is_active(ToolKind.LINE)

    def test_owner_fallback_without_selection(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        ed.autotile_mode = True
        ed.autotiler = type(
            "A", (), {"groups": [],
                      "selected_group_idx": -1,
                      "variant_to_group": {(0, 0): "Grass", (0, 1): "Grass"}})()
        stroke(g, 0, 0, 1, 0)
        assert layer.tiles[(0, 0)].get("autotile_group") == "Grass"
        assert layer.tiles[(1, 0)].get("autotile_group") == "Grass"
