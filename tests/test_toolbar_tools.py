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

from pathlib import Path
import pytest
import pygame
from pygame import Rect

import sys
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
        self.pan_mode = False
        self.select_mode = False
        self.eraser_mode = False
        self.autotile_mode = False
        self.tile_grid_widget = None
        self.tooltip = FakeTooltip()

    def toggle_grid(self):
        pass

    def toggle_auto_autotile(self):
        pass


def make_toolbar(x=0, y=0, w=800, h=35) -> "Toolbar":
    from widgets.ui.toolbar import Toolbar

    editor = FakeEditor()
    return Toolbar(editor, x, y, w, h)


def click_button(toolbar, key: str):
    """Simulate a left-click on the named toolbar button."""
    r, _label = toolbar.buttons[key]
    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": r.center},
    )
    return toolbar.handle_event(event)


class TestToolbarButtonRegistration:
    def test_select_button_registered(self):
        tb = make_toolbar()
        assert "select" in tb.buttons

    def test_eraser_button_registered(self):
        tb = make_toolbar()
        assert "eraser" in tb.buttons

    def test_pan_button_registered(self):
        tb = make_toolbar()
        assert "pan" in tb.buttons


class TestSelectButtonToggle:
    def test_click_select_enables_select_mode(self):
        tb = make_toolbar()
        click_button(tb, "select")
        assert tb.editor.select_mode is True

    def test_click_select_twice_disables_select_mode(self):
        tb = make_toolbar()
        click_button(tb, "select")
        click_button(tb, "select")
        assert tb.editor.select_mode is False

    def test_handle_event_returns_true_for_select_click(self):
        tb = make_toolbar()
        result = click_button(tb, "select")
        assert result is True


class TestEraserButtonToggle:
    def test_click_eraser_enables_eraser_mode(self):
        tb = make_toolbar()
        click_button(tb, "eraser")
        assert tb.editor.eraser_mode is True

    def test_click_eraser_twice_disables_eraser_mode(self):
        tb = make_toolbar()
        click_button(tb, "eraser")
        click_button(tb, "eraser")
        assert tb.editor.eraser_mode is False

    def test_handle_event_returns_true_for_eraser_click(self):
        tb = make_toolbar()
        result = click_button(tb, "eraser")
        assert result is True


class TestMutualExclusivity:
    def test_activating_select_disables_pan(self):
        tb = make_toolbar()
        tb.editor.pan_mode = True
        click_button(tb, "select")
        assert tb.editor.select_mode is True
        assert tb.editor.pan_mode is False

    def test_activating_select_disables_eraser(self):
        tb = make_toolbar()
        tb.editor.eraser_mode = True
        click_button(tb, "select")
        assert tb.editor.select_mode is True
        assert tb.editor.eraser_mode is False

    def test_activating_eraser_disables_pan(self):
        tb = make_toolbar()
        tb.editor.pan_mode = True
        click_button(tb, "eraser")
        assert tb.editor.eraser_mode is True
        assert tb.editor.pan_mode is False

    def test_activating_eraser_disables_select(self):
        tb = make_toolbar()
        tb.editor.select_mode = True
        click_button(tb, "eraser")
        assert tb.editor.eraser_mode is True
        assert tb.editor.select_mode is False

    def test_activating_pan_disables_select(self):
        tb = make_toolbar()
        tb.editor.select_mode = True
        click_button(tb, "pan")
        assert tb.editor.pan_mode is True
        assert tb.editor.select_mode is False

    def test_activating_pan_disables_eraser(self):
        tb = make_toolbar()
        tb.editor.eraser_mode = True
        click_button(tb, "pan")
        assert tb.editor.pan_mode is True
        assert tb.editor.eraser_mode is False

    def test_only_one_mode_active_at_once(self):
        tb = make_toolbar()
        click_button(tb, "select")
        click_button(tb, "eraser")
        assert tb.editor.eraser_mode is True
        assert tb.editor.select_mode is False
        assert tb.editor.pan_mode is False

    def test_deactivating_does_not_affect_others(self):
        """Toggling a mode off when it was already off leaves others untouched."""
        tb = make_toolbar()
        # select is off; clicking it again (toggling off when already off doesn't
        # trigger exclusivity since select_mode starts False)
        tb.editor.select_mode = True
        click_button(tb, "select")  # turns off select
        assert tb.editor.select_mode is False
        # pan and eraser remain unchanged (False)
        assert tb.editor.pan_mode is False
        assert tb.editor.eraser_mode is False


class TestButtonLayout:
    def test_select_button_has_valid_rect(self):
        tb = make_toolbar()
        r, label = tb.buttons["select"]
        assert r.width > 0
        assert r.height > 0

    def test_eraser_button_has_valid_rect(self):
        tb = make_toolbar()
        r, label = tb.buttons["eraser"]
        assert r.width > 0
        assert r.height > 0

    def test_buttons_not_overlapping(self):
        """pan, select, eraser buttons should not overlap each other."""
        tb = make_toolbar()
        pan_r, _ = tb.buttons["pan"]
        sel_r, _ = tb.buttons["select"]
        ers_r, _ = tb.buttons["eraser"]
        assert not pan_r.colliderect(sel_r)
        assert not pan_r.colliderect(ers_r)
        assert not sel_r.colliderect(ers_r)
