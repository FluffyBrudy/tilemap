"""Tests for Edit-menu clipboard entries."""

import os
import sys
import types
from pathlib import Path

import pygame
import pytest

import widgets.ui.menubar as _menubar_mod
from utils.font_manager import font_manager

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

pygame.init()
pygame.display.set_mode((1, 1))


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    font_manager.clear_cache()  # drop fonts bound to a dead display
    yield


class FakeGrid:
    def __init__(self):
        self.selection_rect = None
        self.clipboard = None
        self.hover_cell = None
        self.calls = []

    def copy_selection(self):
        self.calls.append("copy")

    def delete_selection(self):
        self.calls.append("delete")

    def paste_clipboard(self, pos):
        self.calls.append(("paste", pos))


class FakeTilemap:
    def __init__(self):
        self.history = []

    def capture_history(self, description=""):
        self.history.append(description)


def make_editor():
    from editor import Editor

    ed = types.SimpleNamespace(tile_grid_widget=None, tilemap=FakeTilemap())
    ed.edit_copy = types.MethodType(Editor.edit_copy, ed)
    ed.edit_cut = types.MethodType(Editor.edit_cut, ed)
    ed.edit_paste = types.MethodType(Editor.edit_paste, ed)
    ed.edit_delete = types.MethodType(Editor.edit_delete, ed)
    return ed


class TestDelegates:
    def test_copy_needs_selection(self):
        ed = make_editor()
        grid = FakeGrid()
        ed.tile_grid_widget = grid
        ed.edit_copy()
        assert grid.calls == []
        grid.selection_rect = (0, 0, 1, 1)
        ed.edit_copy()
        assert grid.calls == ["copy"]
        assert ed.tilemap.history == []

    def test_cut_copies_histories_deletes(self):
        ed = make_editor()
        grid = FakeGrid()
        grid.selection_rect = (0, 0, 1, 1)
        ed.tile_grid_widget = grid
        ed.edit_cut()
        assert grid.calls == ["copy", "delete"]
        assert ed.tilemap.history == ["Cut Selection"]

    def test_cut_without_selection_noop(self):
        ed = make_editor()
        grid = FakeGrid()
        ed.tile_grid_widget = grid
        ed.edit_cut()
        assert grid.calls == []
        assert ed.tilemap.history == []

    def test_paste_needs_clipboard_and_hover(self):
        ed = make_editor()
        grid = FakeGrid()
        ed.tile_grid_widget = grid
        ed.edit_paste()
        assert grid.calls == []
        grid.clipboard = {"tiles": {}}
        ed.edit_paste()
        assert grid.calls == []
        grid.hover_cell = (3, 4)
        ed.edit_paste()
        assert grid.calls == [("paste", (3, 4))]
        assert ed.tilemap.history == ["Paste"]

    def test_delete_needs_selection(self):
        ed = make_editor()
        grid = FakeGrid()
        ed.tile_grid_widget = grid
        ed.edit_delete()
        assert grid.calls == []
        grid.selection_rect = (0, 0, 2, 2)
        ed.edit_delete()
        assert grid.calls == ["delete"]
        assert ed.tilemap.history == ["Delete Selection"]

    def test_no_grid_noop(self):
        ed = make_editor()
        ed.edit_copy()
        ed.edit_cut()
        ed.edit_paste()
        ed.edit_delete()
        assert ed.tilemap.history == []


class TestEditMenu:
    def _edit_menu(self, ed=None):
        ed = ed or make_editor()
        ed.open_map_setup = lambda: None
        ed.perform_load = lambda: None
        ed.perform_quick_save = lambda: None
        ed.open_save_as_dialog = lambda: None
        ed.open_map_properties = lambda: None
        ed.open_resize_map_dialog = lambda: None
        ed.exit_editor = lambda: None
        ed.undo = lambda: None
        ed.redo = lambda: None
        ed.toggle_grid = lambda: None
        ed.toggle_map_boundary = lambda: None
        ed.toggle_show_nodes = lambda: None
        ed.toggle_node_editing = lambda: None
        ed.toggle_auto_autotile = lambda: None
        ed.toggle_autotiler = lambda: None
        ed.toggle_regex_automap = lambda: None
        ed.launch_animation_editor = lambda: None
        ed.launch_sprite_editor = lambda: None
        ed.launch_character_collision_editor = lambda: None
        ed.autotile_active = lambda: None
        ed.flood_fill_active = lambda: None
        ed.export_selection_as_png = lambda: None
        ed.launch_external_automap = lambda: None
        ed.show_nodes = False
        ed.node_editing_mode = False
        ed.autotile_mode = False
        from widgets.ui.tool_manager import ToolManager

        ed.tool_manager = ToolManager()
        return next(
            m for m in _menubar_mod.MenuBar(ed, 800).menus if m.label == "Edit"
        )

    def test_clipboard_entries_present(self):
        labels = {
            a.label: a
            for a in self._edit_menu().actions
            if hasattr(a, "label")
        }
        assert labels["Copy"].shortcut == "Ctrl+C"
        assert labels["Cut"].shortcut == "Ctrl+X"
        assert labels["Paste"].shortcut == "Ctrl+V"
        assert labels["Delete Selection"].shortcut == "Del"

    def test_menu_copy_invokes_delegate(self):
        ed = make_editor()
        grid = FakeGrid()
        grid.selection_rect = (1, 1, 2, 2)
        ed.tile_grid_widget = grid
        menu = self._edit_menu(ed)
        actions = {a.label: a for a in menu.actions if hasattr(a, "label")}
        actions["Copy"].callback()
        assert grid.calls == ["copy"]

    def test_menu_paste_pastes_at_hover(self):
        ed = make_editor()
        grid = FakeGrid()
        grid.clipboard = {"tiles": {}}
        grid.hover_cell = (5, 5)
        ed.tile_grid_widget = grid
        menu = self._edit_menu(ed)
        actions = {a.label: a for a in menu.actions if hasattr(a, "label")}
        actions["Paste"].callback()
        assert grid.calls == [("paste", (5, 5))]
        assert ed.tilemap.history == ["Paste"]
