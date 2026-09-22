"""Unit tests for ToolManager: the single source of truth for active tool.

Exclusivity, toggle, and previous-tool restore live here — not repeated
per toolbar button. Click journeys live in e2e/test_toolbar_flow.py.
"""

from widgets.ui.tool_manager import ToolKind, ToolManager


def test_starts_with_no_active_tool():
    assert ToolManager().active is None


def test_toggle_activates_and_repeated_toggle_clears():
    mgr = ToolManager()
    mgr.toggle(ToolKind.SELECT)
    assert mgr.is_active(ToolKind.SELECT)
    mgr.toggle(ToolKind.SELECT)
    assert mgr.active is None


def test_toggle_restores_previous_tool():
    mgr = ToolManager()
    mgr.toggle(ToolKind.SELECT)
    mgr.toggle(ToolKind.ERASER)
    assert mgr.is_active(ToolKind.ERASER)
    mgr.toggle(ToolKind.ERASER)
    assert mgr.is_active(ToolKind.SELECT)


def test_only_one_tool_active_at_once():
    mgr = ToolManager()
    mgr.toggle(ToolKind.SELECT)
    mgr.toggle(ToolKind.PAN)
    assert mgr.is_active(ToolKind.PAN)
    assert not mgr.is_active(ToolKind.SELECT)
    assert not mgr.is_active(ToolKind.ERASER)


def test_activate_and_deactivate():
    mgr = ToolManager()
    mgr.activate(ToolKind.FILL)
    assert mgr.is_active(ToolKind.FILL)
    mgr.deactivate()
    assert mgr.active is None


def test_restore_previous_returns_and_clears():
    mgr = ToolManager()
    mgr.toggle(ToolKind.PAN)
    mgr.toggle(ToolKind.SELECT)
    assert mgr.restore_previous() is ToolKind.PAN
    assert mgr.is_active(ToolKind.PAN)
    assert mgr.restore_previous() is None
