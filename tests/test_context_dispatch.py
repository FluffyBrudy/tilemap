"""
Tests for context-based property event dispatch.

Covers:
- PropertyContext defaults
- Opener registration + dispatch
- Saver registration + dispatch
- Unregistered kinds no-op safely
- Registration replaces previous handlers
- PropertyEditor: Return saves via context dispatch and closes
- PropertyEditor: Return while editing a value commits then saves
- PropertyEditor: Escape cancels without saving
- PropertyEditor: no Save button anymore
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.context_dispatch import (
    ContextKind,
    PropertyContext,
    PropertyContextDispatcher,
)
from utils.property_suggestions import PropertySuggestionRegistry
from widgets.ui.property_editor import PropertyEditor


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


class FakeNotifications:
    def __init__(self):
        self.messages = []

    def notify(self, text, **kwargs):
        self.messages.append(text)


class FakeEditor:
    def __init__(self):
        self.width = 800
        self.height = 600
        self.context_dispatch = PropertyContextDispatcher()
        self.suggestion_registry = PropertySuggestionRegistry()
        self.notifications = FakeNotifications()
        self.tileset_widget = None
        self.tilemap = None
        self.node_manager = None


class TestPropertyContext:
    def test_defaults(self):
        ctx = PropertyContext(ContextKind.TILESET)
        assert ctx.kind == ContextKind.TILESET
        assert ctx.target is None
        assert ctx.extra == {}

    def test_extra_is_independent_per_instance(self):
        a = PropertyContext(ContextKind.TILE_VARIANT, extra={"variant_ids": [1]})
        b = PropertyContext(ContextKind.TILE_VARIANT)
        assert a.extra == {"variant_ids": [1]}
        assert b.extra == {}


class TestPropertyContextDispatcher:
    def test_open_routes_to_registered_opener(self):
        dispatcher = PropertyContextDispatcher()
        calls = []
        ctx = PropertyContext(ContextKind.LAYER, target="layer1")

        dispatcher.register_opener(ContextKind.LAYER, lambda c: calls.append(c))
        handled = dispatcher.open(ctx)

        assert handled is True
        assert calls == [ctx]

    def test_save_routes_to_registered_saver(self):
        dispatcher = PropertyContextDispatcher()
        calls = []
        ctx = PropertyContext(ContextKind.NODE, target="node1")
        props = {"hp": 10}

        dispatcher.register_saver(ContextKind.NODE, lambda c, p: calls.append((c, p)))
        handled = dispatcher.save(ctx, props)

        assert handled is True
        assert calls == [(ctx, props)]

    def test_unregistered_kind_noop(self):
        dispatcher = PropertyContextDispatcher()
        ctx = PropertyContext(ContextKind.TILESET, target=object())

        assert dispatcher.open(ctx) is False
        assert dispatcher.save(ctx, {"a": 1}) is False

    def test_register_replaces_previous_handler(self):
        dispatcher = PropertyContextDispatcher()
        first = []
        second = []
        ctx = PropertyContext(ContextKind.LAYER)

        dispatcher.register_opener(ContextKind.LAYER, lambda c: first.append(c))
        dispatcher.register_opener(ContextKind.LAYER, lambda c: second.append(c))
        dispatcher.open(ctx)

        assert first == []
        assert second == [ctx]


class TestPropertyEditorContextSave:
    def _make_editor_with_saver(self, kind=ContextKind.TILESET):
        editor = FakeEditor()
        saved = []
        target = object()

        def saver(ctx, props):
            saved.append((ctx, props))

        editor.context_dispatch.register_saver(kind, saver)
        ctx = PropertyContext(kind, target)
        pe = PropertyEditor(editor, "Test Props", {"a": 1, "b": "x"}, context=ctx)
        return editor, pe, saved, target

    def test_return_saves_and_closes(self):
        _editor, pe, saved, target = self._make_editor_with_saver()
        assert pe.active

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        assert pe.handle_event(event) is True

        assert len(saved) == 1
        assert saved[0][0].target is target
        assert saved[0][1] == {"a": 1, "b": "x"}
        assert pe.active is False

    def test_return_while_editing_value_commits_and_saves(self):
        _editor, pe, saved, _target = self._make_editor_with_saver()
        pe.selected_key = "a"
        pe.editing_value = True
        pe.input_text = "42"

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        assert pe.handle_event(event) is True

        assert len(saved) == 1
        assert saved[0][1] == {"a": 42, "b": "x"}
        assert pe.active is False

    def test_return_after_new_key_commits_then_saves(self):
        _editor, pe, saved, _ = self._make_editor_with_saver()
        pe.is_entering_new_key = True
        pe.new_key_input = "new_key"

        first = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        assert pe.handle_event(first) is True
        assert "new_key" in pe.properties
        assert pe.editing_value is True
        assert pe.active is True
        assert saved == []

        second = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        assert pe.handle_event(second) is True
        assert len(saved) == 1
        assert pe.active is False

    def test_escape_cancels_without_saving(self):
        _editor, pe, saved, _ = self._make_editor_with_saver()

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        assert pe.handle_event(event) is True

        assert saved == []
        assert pe.active is False

    def test_no_save_button(self):
        _editor, pe, _, _ = self._make_editor_with_saver()
        assert not hasattr(pe, "btn_save")

    def test_save_without_handler_keeps_dialog_open(self):
        editor = FakeEditor()
        ctx = PropertyContext(ContextKind.TILESET, target=object())
        pe = PropertyEditor(editor, "Test Props", {"a": 1}, context=ctx)
        assert pe.active

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        assert pe.handle_event(event) is True

        assert pe.active is True
        assert pe.properties == {"a": 1}
        assert any("no property handler" in m.lower() for m in editor.notifications.messages)


class TestPropertyEditorRemove:
    def _make_editor_with_saver(self, props=None):
        editor = FakeEditor()
        saved = []
        target = object()

        def saver(ctx, props):
            saved.append((ctx, props))

        editor.context_dispatch.register_saver(ContextKind.TILESET, saver)
        ctx = PropertyContext(ContextKind.TILESET, target)
        pe = PropertyEditor(editor, "Test Props", props or {"a": 1, "b": "x"}, context=ctx)
        return editor, pe, saved, target

    def test_remove_button_disabled_without_selection(self):
        _editor, pe, _, _ = self._make_editor_with_saver()
        pe._update_remove_enabled()
        assert pe.btn_remove.enabled is False

    def test_remove_enabled_when_property_selected(self):
        _editor, pe, _, _ = self._make_editor_with_saver()
        pe.selected_key = "a"
        pe._update_remove_enabled()
        assert pe.btn_remove.enabled is True

    def test_remove_deletes_selected_property(self):
        _editor, pe, _, _ = self._make_editor_with_saver()
        pe.selected_key = "a"
        pe._on_remove_click()
        assert pe.properties == {"b": "x"}
        assert pe.selected_key is None
        assert pe.editing_value is False

    def test_remove_without_selection_is_noop(self):
        _editor, pe, _, _ = self._make_editor_with_saver()
        pe._on_remove_click()
        assert pe.properties == {"a": 1, "b": "x"}

    def test_remove_while_entering_new_key_is_noop(self):
        _editor, pe, _, _ = self._make_editor_with_saver()
        pe.is_entering_new_key = True
        pe.selected_key = None
        pe._on_remove_click()
        assert pe.properties == {"a": 1, "b": "x"}

    def test_remove_then_return_saves_remaining_props(self):
        _editor, pe, saved, _ = self._make_editor_with_saver()
        pe.selected_key = "a"
        pe._on_remove_click()

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        assert pe.handle_event(event) is True

        assert saved[0][1] == {"b": "x"}
        assert pe.active is False

    def test_remove_after_return_save_reappears_disabled(self):
        _editor, pe, _, _ = self._make_editor_with_saver()
        pe.selected_key = "a"
        pe._on_remove_click()
        pe._update_remove_enabled()
        assert pe.btn_remove.enabled is False

    def test_short_title_not_truncated(self):
        _editor, pe, _, _ = self._make_editor_with_saver()
        pe.font_title = pygame.font.Font(None, 16)
        pe.title = "Short"
        display, truncated = pe._title_display()
        assert display == "Short"
        assert truncated is False

    def test_long_title_truncated_with_ellipsis(self):
        _editor, pe, _, _ = self._make_editor_with_saver()
        pe.font_title = pygame.font.Font(None, 16)
        pe.title = "Object Properties: Objects #1234567890 (some_really_long_tileset_name.png)"
        display, truncated = pe._title_display()
        assert truncated is True
        assert display.endswith("...")
        assert len(display) < len(pe.title)
        assert pe.rect.right - (pe.rect.x + 20) - 20 >= pe.font_title.size(display)[0]
