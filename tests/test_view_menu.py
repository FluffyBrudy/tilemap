"""Tests for View-menu declutter checkboxes."""

import os
import sys
import types
from pathlib import Path

import pygame
import pytest

import widgets.ui.menubar as _menubar_mod
from utils.font_manager import font_manager
from widgets.ui.tool_manager import ToolKind, ToolManager

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


def make_editor():
    from editor import Editor

    ed = types.SimpleNamespace(
        show_nodes=False,
        node_editing_mode=False,
        autotile_mode=False,
        tile_grid_widget=None,
        tool_manager=ToolManager(),
        open_map_setup=lambda: None,
        perform_load=lambda: None,
        perform_quick_save=lambda: None,
        open_save_as_dialog=lambda: None,
        open_map_properties=lambda: None,
        open_resize_map_dialog=lambda: None,
        exit_editor=lambda: None,
        undo=lambda: None,
        redo=lambda: None,
        toggle_grid=lambda: None,
        toggle_map_boundary=lambda: None,
        toggle_autotiler=lambda: None,
        toggle_regex_automap=lambda: None,
        launch_animation_editor=lambda: None,
        launch_sprite_editor=lambda: None,
        launch_character_collision_editor=lambda: None,
        autotile_active=lambda: None,
        flood_fill_active=lambda: None,
        rect_fill_active=lambda: None,
        line_tool_active=lambda: None,
        replace_variant_active=lambda: None,
        export_selection_as_png=lambda: None,
        launch_external_automap=lambda: None,
    )
    # Bind the real toggle logic for fidelity.
    ed.toggle_show_nodes = types.MethodType(Editor.toggle_show_nodes, ed)
    ed.toggle_node_editing = types.MethodType(Editor.toggle_node_editing, ed)
    # Real auto-autotile toggle needs notifications+menubar; bind for
    # identity only (tests never invoke it, checks read the flag).
    ed.toggle_auto_autotile = types.MethodType(Editor.toggle_auto_autotile, ed)
    # Clipboard delegates only touch tile_grid_widget/tilemap.
    ed.edit_copy = types.MethodType(Editor.edit_copy, ed)
    ed.edit_cut = types.MethodType(Editor.edit_cut, ed)
    ed.edit_paste = types.MethodType(Editor.edit_paste, ed)
    ed.edit_delete = types.MethodType(Editor.edit_delete, ed)
    return ed


def make_bar(ed=None):
    return _menubar_mod.MenuBar(ed or make_editor(), 800)


def view_menu(bar):
    return next(m for m in bar.menus if m.label == "View")


def tools_menu(bar):
    return next(m for m in bar.menus if m.label == "Tools")


def action(menu, label):
    return next(a for a in menu.actions if getattr(a, "label", "") == label)


class TestViewCheckboxes:
    def test_five_checkbox_items(self):
        labels = [a.label for a in view_menu(make_bar()).actions]
        assert labels == [
            "Toggle Grid",
            "Toggle Map Boundary",
            "Node Overlay",
            "Node Editing",
            "Auto-Autotile",
        ]

    def test_all_view_items_have_live_checks(self):
        for act in view_menu(make_bar()).actions:
            assert act.is_checked is not None
            assert isinstance(act.is_checked(), bool)

    def test_node_overlay_toggle(self):
        ed = make_editor()
        bar = make_bar(ed)
        act = action(view_menu(bar), "Node Overlay")
        assert act.is_checked() is False
        act.callback()
        assert ed.show_nodes is True
        assert act.is_checked() is True

    def test_overlay_on_kills_editing(self):
        ed = make_editor()
        ed.node_editing_mode = True
        bar = make_bar(ed)
        action(view_menu(bar), "Node Overlay").callback()
        assert ed.show_nodes is True
        assert ed.node_editing_mode is False

    def test_node_editing_toggle_and_shortcut(self):
        ed = make_editor()
        bar = make_bar(ed)
        act = action(view_menu(bar), "Node Editing")
        assert act.shortcut == "Ctrl+Shift+N"
        act.callback()
        assert ed.node_editing_mode is True
        assert ed.show_nodes is False
        assert act.is_checked() is True

    def test_auto_autotile_check_reflects_state(self):
        from editor import Editor

        ed = make_editor()
        bar = make_bar(ed)
        act = action(view_menu(bar), "Auto-Autotile")
        assert act.callback.__func__ is Editor.toggle_auto_autotile
        assert act.is_checked() is False
        ed.autotile_mode = True
        assert act.is_checked() is True


class TestToolsMenu:
    def test_auto_autotile_moved_out(self):
        labels = [a.label for a in tools_menu(make_bar()).actions]
        assert "Toggle Auto-Autotile" not in labels
        assert "Flood Fill Tool" in labels

    def test_flood_fill_check_follows_tool(self):
        ed = make_editor()
        bar = make_bar(ed)
        act = action(tools_menu(bar), "Flood Fill Tool")
        assert act.is_checked() is False
        ed.tool_manager.activate(ToolKind.FILL)
        assert act.is_checked() is True
