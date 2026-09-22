"""Temp UI logic test for autotile group scroll overflow (headless)."""

from pygame import Rect

from widgets.autotiler import AutotileGroup, AutotileRuleDesigner
from widgets.ui.scrollbar import Scrollbar


def make_bare_designer(n_groups=15, area_h=205):
    d = AutotileRuleDesigner.__new__(AutotileRuleDesigner)
    d.groups = [AutotileGroup(f"G{i}") for i in range(n_groups)]
    d.selected_group_idx = 0
    d.selected_rule_index = -1
    d.scroll_offset = 0
    d.max_visible_rules = 6
    d.group_item_h = 25
    d.rule_item_h = 25
    d.group_scroll_px = 0.0
    d.rule_scroll_px = 0.0
    d._group_bar = Scrollbar("vertical", on_scroll=d._on_group_scroll.__get__(d))
    d._rule_bar = Scrollbar("vertical", on_scroll=d._on_rule_scroll.__get__(d))
    d.group_list_area = Rect(0, 30, 200, area_h)
    d.rule_list_area = Rect(0, 30 + area_h + 30, 200, area_h)
    d.group_menu_visible = False
    return d


class TestGroupScrollOverflow:
    def test_bar_appears_when_many_groups(self):
        d = make_bare_designer(15)
        d._sync_list_scrollbars()
        assert d._group_bar.content_size > d._group_bar.view_size
        assert d._group_bar.content_size == 15 * 25
        assert d._group_bar.view_size == 205 - 25

    def test_no_bar_when_few_groups(self):
        d = make_bare_designer(3)
        d._sync_list_scrollbars()
        assert d._group_bar.content_size <= d._group_bar.view_size

    def test_last_group_reachable_via_scroll(self):
        d = make_bare_designer(15)
        d._sync_list_scrollbars()
        d._ensure_group_visible(14)
        top = 14 * 25 - d.group_scroll_px
        assert 0 <= top < d._group_view_h()
        start_y = d.group_list_area.y + 25
        y = start_y + top + 5
        assert d._group_index_at_pos((10, int(y))) == 14

    def test_click_selects_scrolled_group(self):
        d = make_bare_designer(15)
        d._sync_list_scrollbars()
        d._ensure_group_visible(14)
        start_y = d.group_list_area.y + 25
        y = start_y + (14 * 25 - d.group_scroll_px) + 5
        d._handle_group_list_click((10, int(y)))
        assert d.selected_group_idx == 14

    def test_delete_keeps_selection_visible(self):
        d = make_bare_designer(15)
        d._sync_list_scrollbars()
        d.selected_group_idx = 14
        d._ensure_group_visible(14)
        assert d._confirm_delete_group(14) is True
        assert d.selected_group_idx == 13
        top = 13 * 25 - d.group_scroll_px
        assert 0 <= top < d._group_view_h()
