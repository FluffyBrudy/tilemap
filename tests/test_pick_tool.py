"""Tests for the Pick tool (toolbar button + click-to-pick)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pygame
from pygame import Rect

from layers import Layer
from widgets.ui.tool_manager import ToolKind, ToolManager


class FakeTilesetWidget:
    def __init__(self):
        self.picked = []

    def select_tile_by_variant(self, ttype, variant):
        self.picked.append((ttype, variant))


class FakeTilemap:
    def __init__(self):
        self.history = []
        self._layer = Layer("Terrain")
        self._layer.tiles[(2, 2)] = {"pos": (2, 2), "ttype": 1, "variant": 7}

    def capture_history(self, description=""):
        self.history.append(description)


class FakeManager:
    def __init__(self, layer):
        self._layer = layer

    def get_active_layer(self):
        return self._layer


class FakeEditor:
    node_editing_mode = False
    show_nodes = False

    def __init__(self):
        self.tool_manager = ToolManager()
        self.tilemap = FakeTilemap()
        self.tileset_widget = FakeTilesetWidget()


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
    return g


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos})


class TestPickClick:
    def test_click_picks_tile_variant(self, monkeypatch):
        ed = FakeEditor()
        ed.tool_manager.activate(ToolKind.PICK)
        ed.tilemap.layer_manager = FakeManager(ed.tilemap._layer)
        g = make_grid(ed)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert g.handle_event(click((0, 0))) is True
        assert ed.tileset_widget.picked == [(1, 7)]

    def test_click_empty_cell_picks_nothing(self, monkeypatch):
        ed = FakeEditor()
        ed.tool_manager.activate(ToolKind.PICK)
        ed.tilemap.layer_manager = FakeManager(ed.tilemap._layer)
        g = make_grid(ed)
        g.hover_cell = (8, 8)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert g.handle_event(click((0, 0))) is True
        assert ed.tileset_widget.picked == []

    def test_pick_does_not_modify_map(self, monkeypatch):
        ed = FakeEditor()
        ed.tool_manager.activate(ToolKind.PICK)
        ed.tilemap.layer_manager = FakeManager(ed.tilemap._layer)
        g = make_grid(ed)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        g.handle_event(click((0, 0)))
        assert ed.tilemap._layer.tiles[(2, 2)] == {
            "pos": (2, 2), "ttype": 1, "variant": 7}
        assert ed.tilemap.history == []

    def test_drag_motion_does_not_paint(self, monkeypatch):
        ed = FakeEditor()
        ed.tool_manager.activate(ToolKind.PICK)
        ed.tilemap.layer_manager = FakeManager(ed.tilemap._layer)
        g = make_grid(ed)
        g.get_grid_pos = lambda pos: (2, 2)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (True, False, False))
        ev = pygame.event.Event(pygame.MOUSEMOTION, {"pos": (0, 0), "rel": (1, 1)})
        g.handle_event(ev)
        assert ed.tilemap.history == []
