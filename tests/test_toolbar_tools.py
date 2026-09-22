"""Unit tests for the main toolbar: registration, layout, tooltips.

Click journeys live in e2e/test_toolbar_flow.py. Tool state semantics
live in test_tool_manager.py. This file pins what exists and where it
sits - never behavior sequences.
"""

import pygame
import pytest

from widgets.ui.tool_manager import ToolKind, ToolManager
from widgets.ui.toolbar import Toolbar


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


EXPECTED_KEYS = [
    "pan",
    "select",
    "eraser",
    "fill",
    "rect_fill",
    "line",
    "pick",
    "dice",
    "grid",
    "auto",
    "edit_nodes",
    "particles",
    "zoom_out",
    "zoom_in",
    "reset",
    "fit",
]


def test_all_expected_buttons_registered_and_no_removed_ones():
    tb = make_toolbar()
    keys = {getattr(b, "tool_key", b.icon_key) for b in tb._buttons}
    assert set(EXPECTED_KEYS) <= keys
    assert "nodes" not in keys  # pencil button is the single node entry point


def test_all_buttons_have_valid_rects():
    tb = make_toolbar()
    for key in EXPECTED_KEYS:
        r = _find_button(tb, key).rect
        assert r.width > 0 and r.height > 0, key


def test_no_buttons_overlap():
    tb = make_toolbar()
    rects = [(key, _find_button(tb, key).rect) for key in EXPECTED_KEYS]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            assert not rects[i][1].colliderect(rects[j][1]), (
                rects[i][0],
                rects[j][0],
            )


TOOL_TIPS = {
    "select": "(V)",
    "eraser": "(E",
    "rect_fill": "; R",
    "pick": "(I",
    "edit_nodes": "Ctrl+Shift+N",
    "pan": "Ctrl+Space",
}


@pytest.mark.parametrize("key, fragment", sorted(TOOL_TIPS.items()))
def test_tooltips_mention_shortcuts(key, fragment):
    assert fragment in _find_button(make_toolbar(), key).tooltip_text


def test_fill_icon_bundled_and_nonempty():
    from utils.icon_manager import icon_manager

    assert icon_manager.has_icon("fill")
    surf = icon_manager.get_icon("fill", 20, (255, 255, 255))
    opaque = sum(
        1 for x in range(4, 16) for y in range(4, 16) if surf.get_at((x, y))[3] > 0
    )
    assert opaque > 10


def test_tool_manager_starts_clean():
    tb = make_toolbar()
    assert not any(tb.editor.tool_manager.is_active(kind) for kind in ToolKind)
