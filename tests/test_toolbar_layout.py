"""ToolbarLayout engine unit tests.

Covers: left-to-right assignment, right anchoring, whole-group
collapse order, overflow rows/callbacks, separator elision, pinned
entries, segmented overflow entries, reflow idempotence.
"""

import os


import sys
from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest
from pygame import Rect


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


def _widget(width=28, height=28):
    return SimpleNamespace(rect=Rect(0, 0, width, height))


def _layout():
    from widgets.ui.toolbar_layout import ToolbarLayout

    return ToolbarLayout(gap=4, sep_w=10, margin=6)


class TestBasicFlow:
    def test_assigns_left_to_right(self):
        layout = _layout()
        a, b = _widget(), _widget()
        layout.add_widget(a, 28, group="file", priority=50)
        layout.add_widget(b, 28, group="file", priority=50)
        assert layout.reflow(Rect(0, 0, 800, 44), 8, 28) is None
        assert (a.rect.x, a.rect.y) == (6, 8)
        assert b.rect.x == 6 + 28 + 4
        assert getattr(a, "visible", True) is True

    def test_separator_between_groups(self):
        layout = _layout()
        layout.add_widget(_widget(), 28, group="file", priority=50)
        layout.add_separator(group="edit", priority=40)
        layout.add_widget(_widget(), 28, group="edit", priority=40)
        layout.reflow(Rect(0, 0, 800, 44), 8, 28)
        assert len(layout.separators) == 1
        sx, sy = layout.separators[0]
        assert sx == 6 + 28 + 4 + 5  # cursor + sep_w//2
        assert sy == 8 + 28 // 2

    def test_no_leading_separator(self):
        layout = _layout()
        layout.add_separator(group="file", priority=50)
        layout.add_widget(_widget(), 28, group="file", priority=50)
        layout.reflow(Rect(0, 0, 800, 44), 8, 28)
        assert layout.separators == []


class TestRightAnchor:
    def test_right_block_at_edge(self):
        layout = _layout()
        layout.add_widget(_widget(), 28, group="file", priority=50)
        export = _widget(52)
        layout.add_widget(export, 52, group="export", priority=1000,
                          right=True, collapsible=False)
        layout.reflow(Rect(0, 0, 800, 44), 8, 28)
        assert export.rect.right == 800 - 6

    def test_left_flow_never_runs_under_right(self):
        layout = _layout()
        for _ in range(30):
            layout.add_widget(_widget(), 28, group="view", priority=10)
        export = _widget(52)
        layout.add_widget(export, 52, group="export", priority=1000,
                          right=True, collapsible=False)
        overflow = layout.reflow(Rect(0, 0, 800, 44), 8, 28)
        assert overflow is not None
        assert overflow.right <= export.rect.x - 4


class TestCollapse:
    def _crowded(self, width=300):
        layout = _layout()
        widgets = {}
        for group, priority in [("view", 10), ("tools", 20), ("modes", 30)]:
            w = _widget(60 if group == "modes" else 28)
            layout.add_widget(w, 60 if group == "modes" else 28,
                              group=group, priority=priority,
                              label=group, on_activate=lambda: None)
            widgets[group] = w
            layout.add_separator(group=group, priority=priority)
        return layout, widgets

    def test_lowest_priority_collapses_first(self):
        layout, widgets = self._crowded()
        layout.reflow(Rect(0, 0, 175, 44), 8, 28)
        assert getattr(widgets["view"], "visible", True) is False
        assert getattr(widgets["tools"], "visible", True) is True

    def test_hidden_exposed_with_callbacks(self):
        layout, _ = self._crowded()
        layout.reflow(Rect(0, 0, 100, 44), 8, 28)
        rows = layout.overflow_rows()
        assert rows
        fired: list[str] = []
        layout2 = _layout()
        w = _widget()
        layout2.add_widget(w, 28, group="view", priority=10,
                           label="Zoom", on_activate=lambda: fired.append("zoom"))
        layout2.reflow(Rect(0, 0, 30, 44), 8, 28)
        layout2.overflow_rows()[0].on_activate()
        assert fired == ["zoom"]

    def test_separator_dropped_with_group(self):
        layout, _ = self._crowded()
        layout.reflow(Rect(0, 0, 100, 44), 8, 28)
        # every recorded separator sits between two visible widgets:
        # it must lie strictly inside the laid-out span
        if layout.separators:
            xs = [x for x, _ in layout.separators]
            assert min(xs) > 6

    def test_pinned_entries_survive(self):
        layout = _layout()
        pinned = _widget()
        layout.add_widget(pinned, 28, group="file", priority=50, collapsible=False)
        for _ in range(20):
            layout.add_widget(_widget(), 28, group="view", priority=10)
        layout.reflow(Rect(0, 0, 120, 44), 8, 28)
        assert getattr(pinned, "visible", True) is True

    def test_segmented_expands_per_option(self):
        layout = _layout()
        seg = _widget(216)
        calls: list[str] = []
        layout.add_segmented(
            seg, 216, group="modes", priority=30,
            overflow_entries=[("Grid", lambda: calls.append("grid")),
                              ("Free", lambda: calls.append("free"))],
        )
        layout.add_widget(_widget(), 28, group="view", priority=10)
        layout.reflow(Rect(0, 0, 120, 44), 8, 28)
        labels = [r.label for r in layout.overflow_rows()]
        assert "Grid" in labels and "Free" in labels

    def test_widening_restores(self):
        layout, widgets = self._crowded()
        layout.reflow(Rect(0, 0, 100, 44), 8, 28)
        assert layout.hidden
        assert layout.reflow(Rect(0, 0, 1200, 44), 8, 28) is None
        assert layout.hidden == []
        for w in widgets.values():
            assert getattr(w, "visible", True) is True

    def test_reflow_idempotent(self):
        layout, _ = self._crowded()
        first = layout.reflow(Rect(0, 0, 250, 44), 8, 28)
        before = [(e.widget.rect.x if e.widget else None) for e in layout.entries]
        second = layout.reflow(Rect(0, 0, 250, 44), 8, 28)
        after = [(e.widget.rect.x if e.widget else None) for e in layout.entries]
        assert before == after
        assert (first is None) == (second is None)
