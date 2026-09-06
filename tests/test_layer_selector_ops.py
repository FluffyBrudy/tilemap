"""Tests for layer selector ops: focus, history, delete feedback."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pygame
from pygame import Rect

from tilemap import Tilemap
from widgets.input import InlineTextInput
from widgets.layer_selector import LayerSelector


class FakeNotifications:
    def __init__(self):
        self.messages = []

    def notify(self, text, **kwargs):
        self.messages.append(text)

    def success(self, text, **kwargs):
        self.messages.append(text)


class FakeRegistry:
    def refresh(self, editor):
        pass


class NoBtn:
    def handle_event(self, event):
        return False


class FakeEditor:
    def __init__(self):
        self.notifications = FakeNotifications()
        self.suggestion_registry = FakeRegistry()
        self.tile_grid_widget = None
        self.tilemap = Tilemap(self)


def make_selector(editor=None):
    ed = editor or FakeEditor()
    s = LayerSelector.__new__(LayerSelector)
    s.editor = ed
    s.rect = Rect(0, 0, 200, 300)
    s.header_h = 30
    s.item_h = 28
    s.footer_h = 35
    s.header_rect = Rect(0, 0, 200, 30)
    s.list_rect = Rect(0, 30, 200, 300 - 30 - 35)
    s.footer_rect = Rect(0, 300 - 35, 200, 35)
    s.scroll_offset = 0
    s.scroll_speed = 28
    s.dragging_layer_idx = None
    s.drag_start_y = 0
    s.drag_offset_y = 0
    s.hover_idx = None
    s.renaming_layer_idx = None
    s.rename_input = InlineTextInput("layer_rename", "")
    s._adjusting_opacity_idx = None
    s.btn_add = NoBtn()
    s.btn_remove = NoBtn()
    s.btn_replace_image = NoBtn()
    return s


def eye_pos(idx=0):
    # list y=30, item_h=28, width=200 -> eye Rect(170, 32, 10, 10) for idx 0
    return (175, 37 + idx * 28)


def lock_pos(idx=0):
    return (190, 37 + idx * 28)


def click(s, pos, monkeypatch):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos})
    return s.handle_event(ev)


class TestAddLayerFocus:
    def test_new_layer_focused(self):
        ed = FakeEditor()
        tm = ed.tilemap
        assert tm.layer_manager.get_layer_count() == 2  # Terrain + Objects
        s = make_selector(ed)
        s._on_layer_type_selected("tile")
        assert tm.layer_manager.get_layer_count() == 3
        assert tm.layer_manager.active_layer_idx == 2
        assert tm.layer_manager.get_active_layer().name == "Layer 3"

    def test_add_captured_for_undo(self):
        ed = FakeEditor()
        s = make_selector(ed)
        s._on_layer_type_selected("tile")
        assert ed.tilemap.history.can_undo
        ed.tilemap.undo()
        assert ed.tilemap.layer_manager.get_layer_count() == 2


class TestRemoveLayer:
    def test_remove_success_and_undo(self):
        ed = FakeEditor()
        s = make_selector(ed)
        ed.tilemap.layer_manager.set_active_layer(1)
        s._remove_layer()
        assert ed.tilemap.layer_manager.get_layer_count() == 1
        ed.tilemap.undo()
        assert ed.tilemap.layer_manager.get_layer_count() == 2

    def test_last_layer_refuses_with_feedback(self):
        ed = FakeEditor()
        tm = ed.tilemap
        while tm.layer_manager.get_layer_count() > 1:
            tm.layer_manager.delete_layer(0)
        s = make_selector(ed)
        before = len(tm.history.undo_stack)
        s._remove_layer()
        assert tm.layer_manager.get_layer_count() == 1
        assert any("last layer" in m for m in ed.notifications.messages)
        assert len(tm.history.undo_stack) == before


class TestToggleHistory:
    def test_eye_toggle_and_undo(self, monkeypatch):
        ed = FakeEditor()
        s = make_selector(ed)
        assert click(s, eye_pos(), monkeypatch) is True
        assert ed.tilemap.layer_manager.get_layer(0).visible is False
        ed.tilemap.undo()
        assert ed.tilemap.layer_manager.get_layer(0).visible is True

    def test_lock_toggle_and_undo(self, monkeypatch):
        ed = FakeEditor()
        s = make_selector(ed)
        assert click(s, lock_pos(), monkeypatch) is True
        assert ed.tilemap.layer_manager.get_layer(0).locked is True
        ed.tilemap.undo()
        assert ed.tilemap.layer_manager.get_layer(0).locked is False


class TestRenameHistory:
    def test_rename_captured(self):
        ed = FakeEditor()
        s = make_selector(ed)
        s.renaming_layer_idx = 0
        s.rename_input.text = "Ground"
        s._confirm_rename()
        assert ed.tilemap.layer_manager.get_layer(0).name == "Ground"
        ed.tilemap.undo()
        assert ed.tilemap.layer_manager.get_layer(0).name == "Terrain"

    def test_same_name_no_history(self):
        ed = FakeEditor()
        s = make_selector(ed)
        s.renaming_layer_idx = 0
        s.rename_input.text = "Terrain"
        before = len(ed.tilemap.history.undo_stack)
        s._confirm_rename()
        assert len(ed.tilemap.history.undo_stack) == before


class TestReorderHistory:
    def test_drag_reorder_captured(self, monkeypatch):
        ed = FakeEditor()
        s = make_selector(ed)
        mgr = ed.tilemap.layer_manager
        first = mgr.get_layer(0).name
        s.dragging_layer_idx = 0
        pos = (100, 30 + 1 * 28 + 5)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
        ev = pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": pos})
        assert s.handle_event(ev) is True
        assert mgr.get_layer(1).name == first
        mgr_names_after = [layer.name for layer in mgr.layers]
        ed.tilemap.undo()
        assert [layer.name for layer in mgr.layers] != mgr_names_after


class TestPropsHistory:
    def test_save_props_captured(self):
        ed = FakeEditor()
        s = make_selector(ed)
        layer = ed.tilemap.layer_manager.get_layer(0)

        class Ctx:
            target = layer

        s._save_layer_properties(Ctx(), {"tag": "x"})
        assert layer.properties == {"tag": "x"}
        ed.tilemap.undo()
        assert ed.tilemap.layer_manager.get_layer(0).properties == {}


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, {"key": key, "unicode": ""})


class TestListKeys:
    def test_delete_key_removes_active(self, monkeypatch):
        ed = FakeEditor()
        s = make_selector(ed)
        ed.tilemap.layer_manager.set_active_layer(1)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert s.handle_event(key_event(pygame.K_DELETE)) is True
        assert ed.tilemap.layer_manager.get_layer_count() == 1

    def test_up_down_move_active(self, monkeypatch):
        ed = FakeEditor()
        s = make_selector(ed)
        mgr = ed.tilemap.layer_manager
        mgr.create_layer("Extra", layer_type="tile")
        mgr.set_active_layer(1)
        # Up/Down step layers only when hovering the list; off-list the
        # keys yield to the grid.
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (100, 100))
        s.handle_event(key_event(pygame.K_DOWN))
        assert mgr.active_layer_idx == 2
        s.handle_event(key_event(pygame.K_UP))
        s.handle_event(key_event(pygame.K_UP))
        assert mgr.active_layer_idx == 0
        # clamps at bounds
        s.handle_event(key_event(pygame.K_UP))
        assert mgr.active_layer_idx == 0
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert s.handle_event(key_event(pygame.K_DOWN)) is False
        assert mgr.active_layer_idx == 0
