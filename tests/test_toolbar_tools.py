"""
Tests for Toolbar select/eraser tool buttons added in PR.

Covers:
- "select" and "eraser" buttons are registered
- Clicking "select" toggles select_mode on/off
- Clicking "eraser" toggles eraser_mode on/off
- Clicking "pan" toggles pan_mode on/off
- Mutual exclusivity: activating one mode deactivates the others
- Tooltip text for new buttons
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

import pygame
import pytest

from widgets.ui.tool_manager import ToolKind, ToolManager
from widgets.ui.toolbar import Toolbar

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


class FakeTooltip:
    def show(self, text, pos):
        self.last_text = text
        self.last_pos = pos


class FakeEditor:
    def __init__(self):
        self.tool_manager = ToolManager()
        self.autotile_mode = False
        self.tile_grid_widget = None
        self.tooltip = FakeTooltip()
        self.show_nodes = False
        self.node_editing_mode = False

    def toggle_grid(self):
        pass

    def toggle_auto_autotile(self):
        pass

    def toggle_node_editing(self):
        self.node_editing_mode = not self.node_editing_mode
        if self.node_editing_mode:
            self.show_nodes = False
            self.tool_manager.deactivate()

    def toggle_show_nodes(self):
        self.show_nodes = not self.show_nodes
        if self.show_nodes:
            self.node_editing_mode = False


def make_toolbar(x=0, y=0, w=800, h=35) -> "Toolbar":

    editor = FakeEditor()
    return Toolbar(editor, x, y, w, h)


def _find_button(toolbar, key: str):
    for btn in toolbar._buttons:
        if getattr(btn, "tool_key", btn.icon_key) == key:
            return btn
    return None


def click_button(toolbar, key: str):
    """Simulate a left-click on the named toolbar button."""
    btn = _find_button(toolbar, key)
    assert btn is not None, f"Button '{key}' not found"
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": btn.rect.center},
    )
    return toolbar.handle_event(event)


class TestToolbarButtonRegistration:
    def test_select_button_registered(self):
        tb = make_toolbar()
        assert _find_button(tb, "select") is not None

    def test_eraser_button_registered(self):
        tb = make_toolbar()
        assert _find_button(tb, "eraser") is not None

    def test_pan_button_registered(self):
        tb = make_toolbar()
        assert _find_button(tb, "pan") is not None


class TestSelectButtonToggle:
    def test_click_select_enables_select_mode(self):
        tb = make_toolbar()
        click_button(tb, "select")
        assert tb.editor.tool_manager.is_active(ToolKind.SELECT)

    def test_click_select_twice_disables_select_mode(self):
        tb = make_toolbar()
        click_button(tb, "select")
        click_button(tb, "select")
        assert not tb.editor.tool_manager.is_active(ToolKind.SELECT)

    def test_handle_event_returns_true_for_select_click(self):
        tb = make_toolbar()
        result = click_button(tb, "select")
        assert result is True


class TestEraserButtonToggle:
    def test_click_eraser_enables_eraser_mode(self):
        tb = make_toolbar()
        click_button(tb, "eraser")
        assert tb.editor.tool_manager.is_active(ToolKind.ERASER)

    def test_click_eraser_twice_disables_eraser_mode(self):
        tb = make_toolbar()
        click_button(tb, "eraser")
        click_button(tb, "eraser")
        assert not tb.editor.tool_manager.is_active(ToolKind.ERASER)

    def test_handle_event_returns_true_for_eraser_click(self):
        tb = make_toolbar()
        result = click_button(tb, "eraser")
        assert result is True


class TestMutualExclusivity:
    def test_activating_select_disables_pan(self):
        tb = make_toolbar()
        tb.editor.tool_manager.activate(ToolKind.PAN)
        click_button(tb, "select")
        assert tb.editor.tool_manager.is_active(ToolKind.SELECT)
        assert not tb.editor.tool_manager.is_active(ToolKind.PAN)

    def test_activating_select_disables_eraser(self):
        tb = make_toolbar()
        tb.editor.tool_manager.activate(ToolKind.ERASER)
        click_button(tb, "select")
        assert tb.editor.tool_manager.is_active(ToolKind.SELECT)
        assert not tb.editor.tool_manager.is_active(ToolKind.ERASER)

    def test_activating_eraser_disables_pan(self):
        tb = make_toolbar()
        tb.editor.tool_manager.activate(ToolKind.PAN)
        click_button(tb, "eraser")
        assert tb.editor.tool_manager.is_active(ToolKind.ERASER)
        assert not tb.editor.tool_manager.is_active(ToolKind.PAN)

    def test_activating_eraser_disables_select(self):
        tb = make_toolbar()
        tb.editor.tool_manager.activate(ToolKind.SELECT)
        click_button(tb, "eraser")
        assert tb.editor.tool_manager.is_active(ToolKind.ERASER)
        assert not tb.editor.tool_manager.is_active(ToolKind.SELECT)

    def test_activating_pan_disables_select(self):
        tb = make_toolbar()
        tb.editor.tool_manager.activate(ToolKind.SELECT)
        click_button(tb, "pan")
        assert tb.editor.tool_manager.is_active(ToolKind.PAN)
        assert not tb.editor.tool_manager.is_active(ToolKind.SELECT)

    def test_activating_pan_disables_eraser(self):
        tb = make_toolbar()
        tb.editor.tool_manager.activate(ToolKind.ERASER)
        click_button(tb, "pan")
        assert tb.editor.tool_manager.is_active(ToolKind.PAN)
        assert not tb.editor.tool_manager.is_active(ToolKind.ERASER)

    def test_only_one_mode_active_at_once(self):
        tb = make_toolbar()
        click_button(tb, "select")
        click_button(tb, "eraser")
        assert tb.editor.tool_manager.is_active(ToolKind.ERASER)
        assert not tb.editor.tool_manager.is_active(ToolKind.SELECT)
        assert not tb.editor.tool_manager.is_active(ToolKind.PAN)

    def test_deactivating_does_not_affect_others(self):
        """Toggling a mode off when it was already off leaves others untouched."""
        tb = make_toolbar()
        tb.editor.tool_manager.activate(ToolKind.SELECT)
        click_button(tb, "select")  # toggle off
        assert not tb.editor.tool_manager.is_active(ToolKind.SELECT)
        assert not tb.editor.tool_manager.is_active(ToolKind.PAN)
        assert not tb.editor.tool_manager.is_active(ToolKind.ERASER)


class TestButtonLayout:
    def test_select_button_has_valid_rect(self):
        tb = make_toolbar()
        r = _find_button(tb, "select").rect
        assert r.width > 0
        assert r.height > 0

    def test_eraser_button_has_valid_rect(self):
        tb = make_toolbar()
        r = _find_button(tb, "eraser").rect
        assert r.width > 0
        assert r.height > 0

    def test_buttons_not_overlapping(self):
        """pan, select, eraser buttons should not overlap each other."""
        tb = make_toolbar()
        pan_r = _find_button(tb, "pan").rect
        sel_r = _find_button(tb, "select").rect
        ers_r = _find_button(tb, "eraser").rect
        assert not pan_r.colliderect(sel_r)
        assert not pan_r.colliderect(ers_r)
        assert not sel_r.colliderect(ers_r)


class TestEditNodesButton:
    def test_edit_nodes_button_registered(self):
        tb = make_toolbar()
        assert _find_button(tb, "edit_nodes") is not None

    def test_click_edit_nodes_enters_editing(self):
        tb = make_toolbar()
        click_button(tb, "edit_nodes")
        assert tb.editor.node_editing_mode is True
        assert tb.editor.show_nodes is False

    def test_click_edit_nodes_twice_exits_editing(self):
        tb = make_toolbar()
        click_button(tb, "edit_nodes")
        click_button(tb, "edit_nodes")
        assert tb.editor.node_editing_mode is False

    def test_edit_nodes_active_state_follows_mode(self):
        tb = make_toolbar()
        tb._update_active_states()
        assert _find_button(tb, "edit_nodes").active is False
        click_button(tb, "edit_nodes")
        tb._update_active_states()
        assert _find_button(tb, "edit_nodes").active is True

    def test_edit_nodes_tooltip_mentions_shortcut(self):
        tb = make_toolbar()
        btn = _find_button(tb, "edit_nodes")
        assert "Ctrl+Shift+N" in btn.tooltip_text

    def test_overlay_button_removed_overlay_lives_in_view(self):
        tb = make_toolbar()
        assert _find_button(tb, "nodes") is None
        # pencil button is now the single node entry point
        assert _find_button(tb, "edit_nodes") is not None

    def test_edit_nodes_does_not_overlap_neighbors(self):
        tb = make_toolbar()
        edit_r = _find_button(tb, "edit_nodes").rect
        auto_r = _find_button(tb, "auto").rect
        zoom_out_r = _find_button(tb, "zoom_out").rect
        assert not edit_r.colliderect(auto_r)
        assert not edit_r.colliderect(zoom_out_r)


class TestFillButton:
    def test_fill_button_registered(self):
        tb = make_toolbar()
        assert _find_button(tb, "fill") is not None

    def test_click_fill_activates_fill_tool(self):
        tb = make_toolbar()
        click_button(tb, "fill")
        assert tb.editor.tool_manager.is_active(ToolKind.FILL)

    def test_click_fill_twice_deactivates(self):
        tb = make_toolbar()
        click_button(tb, "fill")
        click_button(tb, "fill")
        assert not tb.editor.tool_manager.is_active(ToolKind.FILL)

    def test_fill_active_state_follows_tool(self):
        tb = make_toolbar()
        tb._update_active_states()
        assert _find_button(tb, "fill").active is False
        click_button(tb, "fill")
        tb._update_active_states()
        assert _find_button(tb, "fill").active is True

    def test_fill_deactivates_when_eraser_picked(self):
        tb = make_toolbar()
        click_button(tb, "fill")
        click_button(tb, "eraser")
        assert tb.editor.tool_manager.is_active(ToolKind.ERASER)
        assert not tb.editor.tool_manager.is_active(ToolKind.FILL)

    def test_fill_does_not_overlap_neighbors(self):
        tb = make_toolbar()
        fill_r = _find_button(tb, "fill").rect
        ers_r = _find_button(tb, "eraser").rect
        grid_r = _find_button(tb, "grid").rect
        assert not fill_r.colliderect(ers_r)
        assert not fill_r.colliderect(grid_r)

    def test_fill_icon_bundled_and_nonempty(self):
        from utils.icon_manager import icon_manager

        assert icon_manager.has_icon("fill")
        surf = icon_manager.get_icon("fill", 20, (255, 255, 255))
        opaque = sum(
            1
            for x in range(4, 16)
            for y in range(4, 16)
            if surf.get_at((x, y))[3] > 0
        )
        assert opaque > 10


class TestPickButton:
    def test_pick_button_registered(self):
        tb = make_toolbar()
        assert _find_button(tb, "pick") is not None

    def test_click_pick_activates_pick_tool(self):
        tb = make_toolbar()
        click_button(tb, "pick")
        assert tb.editor.tool_manager.is_active(ToolKind.PICK)

    def test_click_pick_twice_deactivates(self):
        tb = make_toolbar()
        click_button(tb, "pick")
        click_button(tb, "pick")
        assert not tb.editor.tool_manager.is_active(ToolKind.PICK)

    def test_pick_active_state_follows_tool(self):
        tb = make_toolbar()
        tb._update_active_states()
        assert _find_button(tb, "pick").active is False
        click_button(tb, "pick")
        tb._update_active_states()
        assert _find_button(tb, "pick").active is True

    def test_pick_deactivates_when_fill_picked(self):
        tb = make_toolbar()
        click_button(tb, "pick")
        click_button(tb, "fill")
        assert tb.editor.tool_manager.is_active(ToolKind.FILL)
        assert not tb.editor.tool_manager.is_active(ToolKind.PICK)

    def test_pick_does_not_overlap_neighbors(self):
        tb = make_toolbar()
        pick_r = _find_button(tb, "pick").rect
        fill_r = _find_button(tb, "fill").rect
        grid_r = _find_button(tb, "grid").rect
        assert not pick_r.colliderect(fill_r)
        assert not pick_r.colliderect(grid_r)

    def test_pick_icon_bundled_and_nonempty(self):
        from utils.icon_manager import icon_manager

        assert icon_manager.has_icon("pick")
        surf = icon_manager.get_icon("pick", 20, (255, 255, 255))
        opaque = sum(
            1
            for x in range(4, 16)
            for y in range(4, 16)
            if surf.get_at((x, y))[3] > 0
        )
        assert opaque > 10


class TestToolTooltips:
    def test_select_shows_key(self):
        assert "(V)" in _find_button(make_toolbar(), "select").tooltip_text

    def test_eraser_shows_key_and_size_hint(self):
        tip = _find_button(make_toolbar(), "eraser").tooltip_text
        assert "(E" in tip and "Ctrl" in tip

    def test_rect_fill_button_present(self):
        tip = _find_button(make_toolbar(), "rect_fill").tooltip_text
        assert "(R" in tip or "; R" in tip

    def test_pick_shows_key(self):
        assert "(I" in _find_button(make_toolbar(), "pick").tooltip_text
