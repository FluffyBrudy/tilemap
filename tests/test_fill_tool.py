"""Tests for the Fill tool (toolbar button + click-to-fill)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pygame
from pygame import Rect

from layers import Layer
from widgets.ui.tool_manager import ToolKind, ToolManager


class FakeNotifications:
    def __init__(self):
        self.messages = []

    def notify(self, text, **kwargs):
        self.messages.append(text)

    def success(self, text, **kwargs):
        self.messages.append(text)


class FakeTilemap:
    tile_size = (32, 32)
    map_size = (10, 10)
    offset = (0, 0)

    def __init__(self):
        self.history = []
        self._layer = Layer("Terrain")
        # 2x2 block of variant 9 + a different neighbor.
        for pos in [(2, 2), (3, 2), (2, 3), (3, 3)]:
            self._layer.tiles[pos] = {"pos": pos, "ttype": 0, "variant": 9}
        self._layer.tiles[(4, 2)] = {"pos": (4, 2), "ttype": 0, "variant": 5}

    def capture_history(self, description=""):
        self.history.append(description)


class FakeManager:
    def __init__(self, layer):
        self._layer = layer

    def get_active_layer(self):
        return self._layer


class FakeSurf:
    def get_width(self):
        return 8 * 32


class FakeTilesetData:
    tile_properties = {}
    surface = FakeSurf()


class FakeEditor:
    node_editing_mode = False
    show_nodes = False
    autotile_mode = False

    def __init__(self):
        self.tool_manager = ToolManager()
        self.tilemap = FakeTilemap()
        self.notifications = FakeNotifications()


def make_grid(editor):
    from widgets.tile_grid import TileGrid

    g = TileGrid.__new__(TileGrid)
    g.editor = editor
    g.rect = Rect(-10000, -10000, 20000, 20000)
    g.hover_cell = (2, 2)
    g.is_panning = False
    g.is_selecting = False
    g.selection_start = None
    g.is_moving = False
    g.move_start_mouse = None
    g._node_drag_state = None

    class NoScroll:
        def handle_event(self, event):
            return False

    g._v_scroll = NoScroll()
    g._h_scroll = NoScroll()
    g._handle_image_layer_event = lambda event: False
    g.get_selected_brush = lambda: (0, FakeTilesetData(), (0, 0, 32, 32))
    return g


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos})


class TestFillClick:
    def test_click_fills_region(self, monkeypatch):
        ed = FakeEditor()
        ed.tool_manager.activate(ToolKind.FILL)
        ed.tilemap.layer_manager = FakeManager(ed.tilemap._layer)
        g = make_grid(ed)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert g.handle_event(click((0, 0))) is True
        layer = ed.tilemap._layer
        for pos in [(2, 2), (3, 2), (2, 3), (3, 3)]:
            assert layer.tiles[pos]["variant"] == 0
        assert layer.tiles[(4, 2)]["variant"] == 5
        assert ed.tilemap.history == ["Flood Fill"]

    def test_click_without_hover_cell_noop(self, monkeypatch):
        ed = FakeEditor()
        ed.tool_manager.activate(ToolKind.FILL)
        ed.tilemap.layer_manager = FakeManager(ed.tilemap._layer)
        g = make_grid(ed)
        g.hover_cell = None
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert g.handle_event(click((0, 0))) is True
        assert ed.tilemap.history == []
        assert ed.tilemap._layer.tiles[(2, 2)]["variant"] == 9

    def test_no_brush_selected_no_crash(self, monkeypatch):
        """Fill with no tileset tile picked must no-op, not AssertionError."""
        ed = FakeEditor()
        ed.tool_manager.activate(ToolKind.FILL)
        ed.tilemap.layer_manager = FakeManager(ed.tilemap._layer)
        g = make_grid(ed)
        g.get_selected_brush = lambda: (None, None, None)
        assert g.flood_fill_at_hover() is False
        assert ed.tilemap.history == []
        assert ed.tilemap._layer.tiles[(2, 2)]["variant"] == 9
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert g.handle_event(click((0, 0))) is True
        assert ed.tilemap.history == []

    def test_drag_motion_does_not_paint(self, monkeypatch):
        ed = FakeEditor()
        ed.tool_manager.activate(ToolKind.FILL)
        ed.tilemap.layer_manager = FakeManager(ed.tilemap._layer)
        g = make_grid(ed)
        g.get_grid_pos = lambda pos: (2, 2)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
        g.handle_event(click((0, 0)))  # fills block with variant 0
        assert ed.tilemap.history == ["Flood Fill"]
        ev = pygame.event.Event(pygame.MOUSEMOTION, {"pos": (0, 0), "rel": (1, 1)})
        g.handle_event(ev)
        # No "Place Tile" entries from drag-paint.
        assert ed.tilemap.history == ["Flood Fill"]
        assert ed.tilemap._layer.tiles[(2, 2)]["variant"] == 0


class TestFloodFillActive:
    def test_menu_entry_toggles_fill_tool(self):
        from editor import Editor

        ed = FakeEditor()
        Editor.flood_fill_active(ed)
        assert ed.tool_manager.is_active(ToolKind.FILL)
        assert ed.notifications.messages
        Editor.flood_fill_active(ed)
        assert not ed.tool_manager.is_active(ToolKind.FILL)
