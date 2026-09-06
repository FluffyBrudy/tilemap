"""Tests: layer selector yields Delete/Up/Down to the grid when appropriate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

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

    s.btn_add = NoButton()
    s.btn_remove = NoButton()
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
