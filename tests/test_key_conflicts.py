"""Regression tests: bare tool keys must not swallow Ctrl/Cmd combos."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pygame
from pygame import Rect

from layers import Layer


class FakeNotes:
    def __init__(self):
        self.messages = []

    def notify(self, text, **kwargs):
        self.messages.append(text)

    def success(self, text, **kwargs):
        self.messages.append(text)


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


def make_grid(monkeypatch):
    from widgets.tile_grid import TileGrid
    from widgets.ui.tool_manager import ToolKind, ToolManager

    layer = Layer("t")
    ed = type("E", (), {})()
    ed.node_editing_mode = False
    ed.show_nodes = False
    ed.tool_manager = ToolManager()
    ed.tilemap = FakeTilemap(layer)
    ed.notifications = FakeNotes()
    g = TileGrid.__new__(TileGrid)
    g.editor = ed
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
    g.invalidate_bounds_cache = lambda: None
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
    monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (0, 0, 0))
    return g, ed, layer


def key_event(key, mods=0):
    return pygame.event.Event(pygame.KEYDOWN, {"key": key, "unicode": ""})


class TestCmdVPaste:
    def test_cmd_v_pastes_not_selects(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        from widgets.ui.tool_manager import ToolKind

        g.clipboard = {
            "layer_type": "tile",
            "origin": (0, 0),
            "tiles": {(0, 0): {"pos": (0, 0), "ttype": 0, "variant": 7}},
            "objects": [],
        }
        monkeypatch.setattr(pygame.key, "get_mods",
                            lambda: pygame.KMOD_LCTRL)
        assert g.handle_event(key_event(pygame.K_v)) is True
        assert not ed.tool_manager.is_active(ToolKind.SELECT)
        assert layer.tiles[(2, 2)]["variant"] == 7
        assert ed.tilemap.history == ["Paste"]

    def test_meta_v_pastes(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        from widgets.ui.tool_manager import ToolKind

        g.clipboard = {
            "layer_type": "tile",
            "origin": (0, 0),
            "tiles": {(0, 0): {"pos": (0, 0), "ttype": 0, "variant": 7}},
            "objects": [],
        }
        monkeypatch.setattr(pygame.key, "get_mods",
                            lambda: pygame.KMOD_LMETA)
        assert g.handle_event(key_event(pygame.K_v)) is True
        assert not ed.tool_manager.is_active(ToolKind.SELECT)
        assert layer.tiles[(2, 2)]["variant"] == 7

    def test_bare_v_still_toggles_select(self, monkeypatch):
        g, ed, _ = make_grid(monkeypatch)
        from widgets.ui.tool_manager import ToolKind

        monkeypatch.setattr(pygame.key, "get_mods", lambda: 0)
        assert g.handle_event(key_event(pygame.K_v)) is True
        assert ed.tool_manager.is_active(ToolKind.SELECT)

    def test_shift_v_still_toggles_select(self, monkeypatch):
        g, ed, _ = make_grid(monkeypatch)
        from widgets.ui.tool_manager import ToolKind

        monkeypatch.setattr(pygame.key, "get_mods",
                            lambda: pygame.KMOD_SHIFT)
        assert g.handle_event(key_event(pygame.K_v)) is True
        assert ed.tool_manager.is_active(ToolKind.SELECT)


class TestOtherCombosPassThrough:
    def test_ctrl_b_does_not_deactivate(self, monkeypatch):
        g, ed, _ = make_grid(monkeypatch)
        from widgets.ui.tool_manager import ToolKind

        ed.tool_manager.toggle(ToolKind.SELECT)
        monkeypatch.setattr(pygame.key, "get_mods",
                            lambda: pygame.KMOD_LCTRL)
        assert g.handle_event(key_event(pygame.K_b)) is False
        assert ed.tool_manager.is_active(ToolKind.SELECT)

    def test_ctrl_f_does_not_fill(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        monkeypatch.setattr(pygame.key, "get_mods",
                            lambda: pygame.KMOD_LCTRL)
        assert g.handle_event(key_event(pygame.K_f)) is False
        assert layer.tiles == {}


class FakeLayerEntry:
    def __init__(self, name):
        self.name = name


class TestTabCyclesLayers:
    def _grid(self, monkeypatch, count=3, active=0):
        g, ed, _ = make_grid(monkeypatch)
        layers = [FakeLayerEntry(f"L{i}") for i in range(count)]
        mgr = type("M", (), {})()
        mgr.active_layer_idx = active
        mgr.get_layer_count = lambda: count
        mgr.set_active_layer = lambda i: setattr(mgr, "active_layer_idx", i)
        mgr.get_layer = lambda i: layers[i]
        mgr.get_active_layer = lambda: None
        ed.tilemap.layer_manager = mgr
        return g, ed, mgr

    def test_tab_advances_and_notifies(self, monkeypatch):
        g, ed, mgr = self._grid(monkeypatch)
        monkeypatch.setattr(pygame.key, "get_mods", lambda: 0)
        assert g.handle_event(key_event(pygame.K_TAB)) is True
        assert mgr.active_layer_idx == 1
        assert any("L1" in m and "2/3" in m for m in ed.notifications.messages)

    def test_tab_wraps_around(self, monkeypatch):
        g, ed, mgr = self._grid(monkeypatch, active=2)
        monkeypatch.setattr(pygame.key, "get_mods", lambda: 0)
        g.handle_event(key_event(pygame.K_TAB))
        assert mgr.active_layer_idx == 0

    def test_shift_tab_goes_back(self, monkeypatch):
        g, ed, mgr = self._grid(monkeypatch, active=1)
        monkeypatch.setattr(pygame.key, "get_mods", lambda: pygame.KMOD_LSHIFT)
        assert g.handle_event(key_event(pygame.K_TAB)) is True
        assert mgr.active_layer_idx == 0

    def test_ctrl_tab_ignored(self, monkeypatch):
        g, ed, mgr = self._grid(monkeypatch)
        monkeypatch.setattr(pygame.key, "get_mods", lambda: pygame.KMOD_LCTRL)
        assert g.handle_event(key_event(pygame.K_TAB)) is False
        assert mgr.active_layer_idx == 0
