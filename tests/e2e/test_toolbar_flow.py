"""E2E journeys for the main toolbar: click tools, watch modes follow."""

import pytest
from test_toolbar_tools import _find_button, click_button, make_toolbar

from widgets.ui.tool_manager import ToolKind

pytestmark = pytest.mark.e2e

TOOL_KINDS = {
    "pan": ToolKind.PAN,
    "select": ToolKind.SELECT,
    "eraser": ToolKind.ERASER,
    "fill": ToolKind.FILL,
    "rect_fill": ToolKind.RECT_FILL,
    "line": ToolKind.LINE,
    "pick": ToolKind.PICK,
}


@pytest.mark.parametrize("key, kind", sorted(TOOL_KINDS.items()))
def test_tool_toggle_journey(key, kind):
    tb = make_toolbar()
    click_button(tb, key)
    assert tb.editor.tool_manager.is_active(kind)
    tb._update_active_states()
    assert _find_button(tb, key).active is True
    click_button(tb, key)
    assert not tb.editor.tool_manager.is_active(kind)


@pytest.mark.parametrize(
    "first, second",
    [("select", "eraser"), ("eraser", "pan"), ("fill", "pick"), ("pick", "fill")],
)
def test_tool_switch_journey(first, second):
    tb = make_toolbar()
    click_button(tb, first)
    click_button(tb, second)
    assert tb.editor.tool_manager.is_active(TOOL_KINDS[second])
    assert not tb.editor.tool_manager.is_active(TOOL_KINDS[first])


def test_edit_nodes_journey():
    tb = make_toolbar()
    click_button(tb, "edit_nodes")
    assert tb.editor.node_editing_mode is True
    assert tb.editor.show_nodes is False
    tb._update_active_states()
    assert _find_button(tb, "edit_nodes").active is True
    click_button(tb, "edit_nodes")
    assert tb.editor.node_editing_mode is False
