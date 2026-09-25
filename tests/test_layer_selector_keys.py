"""Tests: layer selector yields Delete/Up/Down to the grid when appropriate."""

import sys
from pathlib import Path


import pygame
from pygame import Rect


class FakeManager:
    def __init__(self):
        self.active_layer_idx = 0
        self.removed = []

    def get_layer_count(self):
        return 3

    def get_layer(self, idx):
        return object()

    def set_active_layer(self, idx):
        self.active_layer_idx = idx


def make_selector(monkeypatch, grid_selection=None, mouse_pos=(0, 0)):
    from widgets.layer_selector import LayerSelector

    ed = type("E", (), {})()
    ed.tilemap = type("T", (), {"layer_manager": FakeManager()})()
    ed.tile_grid_widget = type(
        "G", (), {"selection_rect": grid_selection})()
    s = LayerSelector.__new__(LayerSelector)
    s.editor = ed
    s.list_rect = Rect(500, 0, 200, 400)
    s.renaming_layer_idx = None
    s.removed = []
    s._remove_layer = lambda: s.removed.append(True)

    class NoButton:
        def handle_event(self, event):
            return False

        def draw(self, screen):
            return None

    s.btn_add = NoButton()
    s.btn_remove = NoButton()
    s.btn_duplicate = NoButton()
    s.btn_replace_image = NoButton()
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: mouse_pos)
    return s


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, {"key": key, "unicode": ""})


class TestDeleteYield:
    def test_delete_with_grid_selection_yields(self, monkeypatch):
        s = make_selector(monkeypatch, grid_selection=(0, 0, 2, 2))
        assert s.handle_event(key_event(pygame.K_DELETE)) is False
        assert s.removed == []

    def test_backspace_with_grid_selection_yields(self, monkeypatch):
        s = make_selector(monkeypatch, grid_selection=(0, 0, 2, 2))
        assert s.handle_event(key_event(pygame.K_BACKSPACE)) is False
        assert s.removed == []

    def test_delete_without_selection_removes(self, monkeypatch):
        s = make_selector(monkeypatch, grid_selection=None)
        assert s.handle_event(key_event(pygame.K_DELETE)) is True
        assert s.removed == [True]

    def test_delete_without_grid_widget_removes(self, monkeypatch):
        s = make_selector(monkeypatch, grid_selection=None)
        s.editor.tile_grid_widget = None
        assert s.handle_event(key_event(pygame.K_DELETE)) is True
        assert s.removed == [True]


class TestArrowHover:
    def test_up_over_list_steps(self, monkeypatch):
        s = make_selector(monkeypatch, mouse_pos=(550, 50))
        s.editor.tilemap.layer_manager.active_layer_idx = 1
        assert s.handle_event(key_event(pygame.K_UP)) is True
        assert s.editor.tilemap.layer_manager.active_layer_idx == 0

    def test_up_off_list_yields(self, monkeypatch):
        s = make_selector(monkeypatch, mouse_pos=(10, 10))
        s.editor.tilemap.layer_manager.active_layer_idx = 1
        assert s.handle_event(key_event(pygame.K_UP)) is False
        assert s.editor.tilemap.layer_manager.active_layer_idx == 1

    def test_down_over_list_steps(self, monkeypatch):
        s = make_selector(monkeypatch, mouse_pos=(550, 50))
        assert s.handle_event(key_event(pygame.K_DOWN)) is True
        assert s.editor.tilemap.layer_manager.active_layer_idx == 1

    def test_down_off_list_yields(self, monkeypatch):
        s = make_selector(monkeypatch, mouse_pos=(10, 10))
        assert s.handle_event(key_event(pygame.K_DOWN)) is False
        assert s.editor.tilemap.layer_manager.active_layer_idx == 0


class FakeFont:
    def __init__(self, px_per_char=6):
        self._px = px_per_char

    def size(self, text):
        return (len(text) * self._px, 12)


class TestFitText:
    def test_short_passthrough(self):
        from widgets.layer_selector import fit_text

        assert fit_text(FakeFont(), "abc", 100) == "abc"

    def test_truncates_with_ellipsis(self):
        from widgets.layer_selector import fit_text

        out = fit_text(FakeFont(), "a_very_long_layer_name", 60)
        assert out.endswith("..")
        assert len(out) * 6 <= 60

    def test_zero_width_empty(self):
        from widgets.layer_selector import fit_text

        assert fit_text(FakeFont(), "abc", 0) == ""
        assert fit_text(FakeFont(), "abc", -5) == ""

    def test_nothing_fits_empty(self):
        from widgets.layer_selector import fit_text

        assert fit_text(FakeFont(), "abc", 6) == ""

    def test_name_budget_keeps_clear_of_pct(self):
        item_x, bar_x = 0, 200
        name_max_w = (bar_x - 36) - (item_x + 22)
        from widgets.layer_selector import fit_text

        out = fit_text(FakeFont(), "x" * 100, name_max_w)
        assert len(out) * 6 <= name_max_w


class TestDeleteImageCopyYield:
    def test_delete_with_image_copy_selection_yields(self, monkeypatch):
        s = make_selector(monkeypatch, grid_selection=None)
        s.editor.tile_grid_widget = type(
            "G", (), {
                "selection_rect": None,
                "has_image_selection": lambda self: True,
            })()
        assert s.handle_event(key_event(pygame.K_DELETE)) is False
        assert s.removed == []

    def test_backspace_with_image_copy_selection_yields(self, monkeypatch):
        s = make_selector(monkeypatch, grid_selection=None)
        s.editor.tile_grid_widget = type(
            "G", (), {
                "selection_rect": None,
                "has_image_selection": lambda self: True,
            })()
        assert s.handle_event(key_event(pygame.K_BACKSPACE)) is False
        assert s.removed == []

    def test_delete_without_image_selection_removes(self, monkeypatch):
        s = make_selector(monkeypatch, grid_selection=None)
        s.editor.tile_grid_widget = type(
            "G", (), {
                "selection_rect": None,
                "has_image_selection": lambda self: False,
            })()
        assert s.handle_event(key_event(pygame.K_DELETE)) is True
        assert s.removed == [True]


class TestImageSelectionLayerScope:
    def _grid_on(self, active_layer, pid=3, pid_layer=None):
        from types import SimpleNamespace

        from widgets.tile_grid import TileGrid

        g = TileGrid.__new__(TileGrid)
        g._image_placement_pid = pid
        g._image_placement_layer = pid_layer
        mgr = SimpleNamespace(get_active_layer=lambda: active_layer)
        g.editor = SimpleNamespace(tilemap=SimpleNamespace(layer_manager=mgr))
        return g

    def _image_layer(self, pids):
        from types import SimpleNamespace

        return SimpleNamespace(
            layer_type="image",
            image_rect={"x": 0, "y": 0, "w": 64, "h": 64},
            get_placement=lambda pid: (
                SimpleNamespace(pid=pid) if pid in pids else None
            ),
        )

    def test_stale_pick_on_twin_layer_clears(self):
        layer_a = self._image_layer({3})
        layer_b = self._image_layer({3})  # duplicate shares pid values
        g = self._grid_on(layer_b, pid=3, pid_layer=layer_a)
        assert g.has_image_selection() is False
        assert g._image_placement_pid is None

    def test_pick_on_active_layer_survives(self):
        layer_a = self._image_layer({3})
        g = self._grid_on(layer_a, pid=3, pid_layer=layer_a)
        assert g.has_image_selection() is True
        assert g._image_placement_pid == 3

    def test_missing_pid_clears(self):
        layer_a = self._image_layer(set())
        g = self._grid_on(layer_a, pid=3, pid_layer=layer_a)
        assert g.has_image_selection() is False
        assert g._image_placement_pid is None


class TestImageCopyDeleteJourney:
    """End to end: sidebar yields Backspace, grid removes one copy only."""

    def _image_layer(self):
        from layers import Layer

        return Layer(
            name="bg",
            layer_type="image",
            image_path="bg.png",
            image_rect={"x": 0, "y": 0, "w": 64, "h": 64},
            image_placements=[
                {"pid": 1, "x": 0, "y": 0, "w": 32, "h": 32},
                {"pid": 2, "x": 32, "y": 0, "w": 32, "h": 32},
            ],
        )

    def _grid(self, layer, pid):
        from types import SimpleNamespace

        from widgets.tile_grid import TileGrid

        g = TileGrid.__new__(TileGrid)
        g._image_placement_pid = pid
        g._image_placement_layer = layer
        g.rect = Rect(0, 0, 800, 600)
        g.selection_rect = None
        history = []
        mgr = SimpleNamespace(get_active_layer=lambda: layer)
        g.editor = SimpleNamespace(
            tilemap=SimpleNamespace(
                layer_manager=mgr,
                capture_history=lambda msg: history.append(msg),
            )
        )
        return g, history

    def test_backspace_removes_only_picked_copy(self, monkeypatch):
        from widgets.layer_selector import LayerSelector

        layer = self._image_layer()
        grid, history = self._grid(layer, pid=2)
        assert len(layer.image_placements) == 2

        # sidebar sees the grid's image selection and yields
        sel = LayerSelector.__new__(LayerSelector)
        sel.editor = grid.editor
        sel.editor.tile_grid_widget = grid
        sel.renaming_layer_idx = None
        sel.removed = []
        sel._remove_layer = lambda: sel.removed.append(True)
        assert sel.removed == []
        assert grid.has_image_selection() is True

        # grid consumes Backspace with a single-copy removal
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (10, 10))
        assert grid._handle_image_layer_event(
            key_event(pygame.K_BACKSPACE)
        ) is True
        assert [p.pid for p in layer.image_placements] == [1]
        assert history == ["Remove Image Copy"]
        assert sel.removed == []

    def test_backspace_without_pick_preserves_copies(self, monkeypatch):
        layer = self._image_layer()
        grid, _ = self._grid(layer, pid=None)
        grid._image_placement_layer = None
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (10, 10))
        assert grid._handle_image_layer_event(
            key_event(pygame.K_BACKSPACE)
        ) is True
        assert [p.pid for p in layer.image_placements] == [1, 2]
