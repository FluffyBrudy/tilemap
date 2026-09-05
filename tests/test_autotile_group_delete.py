"""Tests for autotile group delete menu/button (Phase 2)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from widgets.autotiler import AutotileGroup, AutotileRuleDesigner


class FakeEditor:
    width = 800
    height = 600
    notifications = None


def make_designer(names=("A", "B", "C")):
    d = AutotileRuleDesigner.__new__(AutotileRuleDesigner)
    d.groups = [AutotileGroup(n) for n in names]
    d.selected_group_idx = 1
    d.selected_rule_index = -1
    d.scroll_offset = 0
    d.max_visible_rules = 6
    d.group_menu_visible = False
    d.group_menu_idx = None
    d.group_menu_options = ("Rename (F2)", "Delete group")
    d.editor = FakeEditor()
    return d


class TestConfirmDelete:
    def test_deletes_and_reselects(self):
        d = make_designer()
        assert d._confirm_delete_group(1) is True
        assert [g.name for g in d.groups] == ["A", "C"]
        assert d.selected_group_idx == 0
        assert d.selected_rule_index == -1

    def test_cannot_delete_last_group(self):
        d = make_designer(("Solo",))
        assert d._confirm_delete_group(0) is False
        assert [g.name for g in d.groups] == ["Solo"]

    def test_request_guards_last_group(self):
        d = make_designer(("Solo",))
        d._request_delete_group(0)  # no confirm_dialog -> direct, guarded
        assert [g.name for g in d.groups] == ["Solo"]

    def test_request_without_dialog_deletes_directly(self):
        d = make_designer()
        d._request_delete_group(2)
        assert [g.name for g in d.groups] == ["A", "B"]

    def test_request_uses_confirm_dialog_when_available(self):
        d = make_designer()
        shown = {}

        class FakeConfirm:
            def show(self, title, message, on_confirm, on_cancel):
                shown["title"] = title
                shown["message"] = message
                on_confirm()

        d.editor = type(
            "E", (), {"width": 800, "height": 600, "notifications": None,
                      "confirm_dialog": FakeConfirm()}
        )()
        d._request_delete_group(0)
        assert "A" in shown["message"]
        assert [g.name for g in d.groups] == ["B", "C"]

    def test_delete_current_rule_delegates_for_group(self):
        d = make_designer()
        d.selected_rule_index = -1
        d.selected_group_idx = 0
        d._delete_current_rule()  # no dialog -> direct delete of A
        assert [g.name for g in d.groups] == ["B", "C"]

    def test_menu_open_close(self):
        d = make_designer()
        d._open_group_menu(2, (50, 100))
        assert d.group_menu_visible is True
        assert d.group_menu_idx == 2
        assert d.group_menu_rect.width == 170
        d._close_group_menu()
        assert d.group_menu_visible is False
        assert d.group_menu_idx is None
