"""Tests for rectangle fill (drag region, tile brush, one history entry)."""

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


def make_grid(monkeypatch, layer=None, brush=(0, 0, 2 * 32, 32)):
    from widgets.tile_grid import TileGrid

    layer = layer if layer is not None else Layer("t")
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
    g.is_panning = False
    g.is_selecting = False
    g.selection_start = None
    g.is_moving = False
    g.move_start_mouse = None
    g._node_drag_state = None
    g.rect_fill_start = None
    g.rect_fill_rect = None

    class NoScroll:
        def handle_event(self, event):
            return False

    g._v_scroll = NoScroll()
    g._h_scroll = NoScroll()
    g._handle_image_layer_event = lambda event: False
    g.invalidate_bounds_cache = lambda: None
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
    return g, ed, layer


def drag(g, x1, y1, x2, y2):
    g.rect_fill_start = (x1, y1)
    g.rect_fill_rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
    g._commit_rect_fill()


class TestRectFill:
    def test_fills_dragged_region_once(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        drag(g, 1, 1, 3, 2)
        assert len(layer.tiles) == 6
        assert ed.tilemap.history == ["Rect Fill"]
        assert any("6 tiles" in m for m in ed.notifications.good)

    def test_brush_tiles_across_rect(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        drag(g, 0, 0, 3, 1)
        assert layer.tiles[(0, 0)]["variant"] == 0
        assert layer.tiles[(1, 0)]["variant"] == 1
        assert layer.tiles[(2, 0)]["variant"] == 0
        assert layer.tiles[(3, 1)]["variant"] == 1

    def test_reverse_drag_normalized(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        g.rect_fill_start = (3, 2)
        g.rect_fill_rect = (1, 1, 3, 2)
        g._commit_rect_fill()
        assert len(layer.tiles) == 6

    def test_single_cell_click(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        drag(g, 2, 2, 2, 2)
        assert len(layer.tiles) == 1
        assert layer.tiles[(2, 2)]["variant"] == 0

    def test_clipped_to_map_bounds(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        drag(g, 8, 8, 12, 12)
        assert set(layer.tiles) == {(8, 8), (8, 9), (9, 8), (9, 9)}

    def test_no_brush_noop_resets(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        ed.tileset_widget.selected_tile = None
        drag(g, 0, 0, 2, 2)
        assert layer.tiles == {}
        assert ed.tilemap.history == []
        assert g.rect_fill_start is None

    def test_non_tile_layer_noop(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        layer.layer_type = "object"
        drag(g, 0, 0, 2, 2)
        assert layer.tiles == {}
        assert ed.tilemap.history == []

    def test_dice_scatters_within_pool(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        ed.dice_brush = True
        drag(g, 0, 0, 3, 3)
        assert len(layer.tiles) == 16
        got = {t["variant"] for t in layer.tiles.values()}
        assert got <= {0, 1}

    def test_group_stamped_when_autotile(self, monkeypatch):
        from widgets.autotiler import AutotileGroup

        g, ed, layer = make_grid(monkeypatch)
        ed.autotile_mode = True
        ed.autotiler = type(
            "A", (), {"groups": [AutotileGroup("W")],
                      "selected_group_idx": 0})()
        drag(g, 0, 0, 1, 1)
        assert all(t.get("autotile_group") == "W"
                   for t in layer.tiles.values())

    def test_owner_fallback_without_selection(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        ed.autotile_mode = True
        ed.autotiler = type(
            "A", (), {"groups": [],
                      "selected_group_idx": -1,
                      "variant_to_group": {(0, 0): "Grass", (0, 1): "Grass"}})()
        drag(g, 0, 0, 1, 0)
        assert layer.tiles[(0, 0)].get("autotile_group") == "Grass"
        assert layer.tiles[(1, 0)].get("autotile_group") == "Grass"


class TestRectFillKeys:
    def test_r_toggles_rect_fill(self, monkeypatch):
        g, ed, _ = make_grid(monkeypatch)
        monkeypatch.setattr(pygame.key, "get_mods", lambda: 0)
        ev = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_r, "unicode": ""})
        assert g.handle_event(ev) is True
        assert ed.tool_manager.is_active(ToolKind.RECT_FILL)

    def test_e_toggles_eraser(self, monkeypatch):
        g, ed, _ = make_grid(monkeypatch)
        monkeypatch.setattr(pygame.key, "get_mods", lambda: 0)
        ev = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_e, "unicode": ""})
        assert g.handle_event(ev) is True
        assert ed.tool_manager.is_active(ToolKind.ERASER)
