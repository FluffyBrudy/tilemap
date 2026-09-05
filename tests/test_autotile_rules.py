"""Tests for autotile rule delete-confirm + duplicate (A5)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pygame import Rect

from widgets.autotiler import AutotileGroup, AutotileRule, AutotileRuleDesigner


def make_rule(name, neighbors=frozenset(), variants=(0,)):
    return AutotileRule(
        name=name,
        neighbors=set(neighbors),
        tileset_path="/t/g.png",
        variant_ids=list(variants),
        tileset_index=0,
        group_id="G",
    )


class FakeEditor:
    def __init__(self, confirm=None):
        self.confirm_dialog = confirm
        self.notifications = None


def make_designer(confirm=None, rules=None):
    d = AutotileRuleDesigner.__new__(AutotileRuleDesigner)
    d.groups = [AutotileGroup("G", rules if rules is not None else
                              [make_rule("R1", {(0, -1)}, (3,))])]
    d.selected_group_idx = 0
    d.selected_rule_index = 0
    d.scroll_offset = 0
    d.max_visible_rules = 6
    d.group_menu_visible = False
    d.group_menu_idx = None
    d.current_neighbors = set()
    d.current_variant_ids = []
    d.current_tileset_path = ""
    d.current_tileset_index = None
    d.current_preview_surfs = []
    d._last_editor_selection = (None, (0, 0, 0, 0))
    d.editor = FakeEditor(confirm)
    return d


class FakeConfirm:
    def __init__(self):
        self.shown = []

    def show(self, title, message, on_confirm, on_cancel):
        self.shown.append((title, message))
        on_confirm()


class TestDuplicate:
    def test_copies_fields_with_unique_name(self):
        d = make_designer()
        assert d._duplicate_current_rule() is True
        names = [r.name for r in d.groups[0].rules]
        assert names == ["R1", "R1 copy"]
        clone = d.groups[0].rules[1]
        assert clone.neighbors == {(0, -1)}
        assert clone.variant_ids == [3]
        assert clone.tileset_index == 0
        assert clone.group_id == "G"
        # selection follows the clone and editor shows it
        assert d.selected_rule_index == 1
        assert d.current_neighbors == {(0, -1)}
        assert d.current_variant_ids == [3]

    def test_repeat_duplicate_numbered(self):
        d = make_designer()
        d._duplicate_current_rule()
        d.selected_rule_index = 0  # duplicate the original again
        d._duplicate_current_rule()
        names = [r.name for r in d.groups[0].rules]
        assert sorted(names) == ["R1", "R1 copy", "R1 copy 2"]

    def test_no_selection_noop(self):
        d = make_designer()
        d.selected_rule_index = -1
        assert d._duplicate_current_rule() is False
        assert [r.name for r in d.groups[0].rules] == ["R1"]

    def test_bad_group_noop(self):
        d = make_designer()
        d.selected_group_idx = 5
        assert d._duplicate_current_rule() is False


class TestDeleteConfirm:
    def test_dialog_confirms_before_delete(self):
        confirm = FakeConfirm()
        d = make_designer(confirm)
        d._delete_current_rule()
        assert len(confirm.shown) == 1
        assert "R1" in confirm.shown[0][1]
        assert [r.name for r in d.groups[0].rules] == []

    def test_no_dialog_deletes_directly(self):
        d = make_designer()
        d._delete_current_rule()
        assert [r.name for r in d.groups[0].rules] == []

    def test_cancel_keeps_rule(self):
        class Cancel:
            def show(self, title, message, on_confirm, on_cancel):
                on_cancel()

        d = make_designer(Cancel())
        d._delete_current_rule()
        assert [r.name for r in d.groups[0].rules] == ["R1"]

    def test_delete_key_routes_to_rule_confirm(self):
        # Method-level parity with the Delete-key branch: rule selected ->
        # rule confirm, not group delete.
        confirm = FakeConfirm()
        d = make_designer(confirm)
        d._delete_current_rule()
        assert [g.name for g in d.groups] == ["G"]
        assert d.groups[0].rules == []


class TestButtonLayout:
    def test_dup_between_save_and_delete(self):
        d = AutotileRuleDesigner.__new__(AutotileRuleDesigner)
        d.rect = Rect(100, 100, 600, 500)
        d.header_height = 30
        d._update_layout()
        assert d.save_btn_rect.right <= d.dup_btn_rect.x
        assert d.dup_btn_rect.right <= d.delete_btn_rect.x
        assert d.edit_area.contains(d.save_btn_rect)
        assert d.edit_area.contains(d.dup_btn_rect)
        assert d.edit_area.contains(d.delete_btn_rect)
