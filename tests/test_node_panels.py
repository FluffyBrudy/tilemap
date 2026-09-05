"""Tests for node panel overlap fix + selector extras."""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pygame
from pygame import Rect

pygame.font.init()

from node_manager import NodeManager
from nodes import Node, NodeRect
from widgets.ui.node_editor import NodeEditor
from widgets.ui.node_selector import NodeSelector


def make_node(name="Area 1", x=0, y=0, group=None):
    return Node(
        node_id=f"id-{name}-{x}-{y}",
        name=name,
        node_type="area",
        area=NodeRect(x=x, y=y, w=64, h=64),
        layer_name="Terrain",
        properties={"a": 1},
        group=group,
    )


class FakeScreen:
    def __init__(self, w=1280, h=800):
        self._w = w
        self._h = h

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h


class FakeGrid:
    def _node_to_screen(self, x, y):
        return (x, y)

    def _node_screen_size(self, w, h):
        return (w, h)


class FakeTilemap:
    def __init__(self):
        self.history = []

    def capture_history(self, description=""):
        self.history.append(description)


class FakeEditor:
    node_editing_mode = True

    def __init__(self, manager, screen=None, selector=None):
        self.node_manager = manager
        self.tile_grid_widget = FakeGrid()
        self.screen = screen or FakeScreen()
        self.tilemap = FakeTilemap()
        if selector is not None:
            self.node_selector = selector


def make_node_editor(manager, rect=(0, 310, 260, 230), screen=None,
                     selector_rect=(0, 65, 260, 240)):
    ed = FakeEditor(manager, screen)
    selector = NodeSelector.__new__(NodeSelector)
    selector.editor = ed
    selector.rect = Rect(*selector_rect)
    ed.node_selector = selector
    d = NodeEditor.__new__(NodeEditor)
    d.editor = ed
    d.rect = Rect(*rect)
    d._dock_x, d._dock_y = rect[0], rect[1]
    return d


class TestPickPosition:
    def test_picks_first_clear_candidate(self):
        avoid = [Rect(0, 0, 100, 100)]
        best = NodeEditor._pick_position(
            [(10, 10), (200, 200)], 50, 50, 800, 600, avoid)
        assert best == (200, 200)

    def test_falls_back_to_first_clamped(self):
        avoid = [Rect(0, 0, 800, 600)]
        best = NodeEditor._pick_position(
            [(10, 10), (200, 200)], 50, 50, 800, 600, avoid)
        assert best == (10, 10)

    def test_empty_candidates_returns_floor(self):
        assert NodeEditor._pick_position([], 50, 50, 800, 600, []) == (10, 10)


class TestReposition:
    def test_left_node_avoids_selector(self):
        mgr = NodeManager(object())
        node = make_node(x=40, y=400)
        mgr.nodes[node.node_id] = node
        mgr.active_node_id = node.node_id
        d = make_node_editor(mgr)
        d.reposition_near_node()
        assert not d.rect.colliderect(Rect(0, 65, 260, 240))
        # node rect itself also avoided
        assert not d.rect.colliderect(Rect(40, 400, 64, 64))

    def test_center_node_uses_first_candidate(self):
        mgr = NodeManager(object())
        node = make_node(x=600, y=400)
        mgr.nodes[node.node_id] = node
        mgr.active_node_id = node.node_id
        d = make_node_editor(mgr)
        d.reposition_near_node()
        assert (d.rect.x, d.rect.y) == (600 + 64 + 24, 400)

    def test_tiny_screen_falls_back_to_dock(self):
        mgr = NodeManager(object())
        node = make_node(x=40, y=100)
        mgr.nodes[node.node_id] = node
        mgr.active_node_id = node.node_id
        d = make_node_editor(mgr, screen=FakeScreen(300, 400))
        d.reposition_near_node()
        assert (d.rect.x, d.rect.y) == (0, 310)

    def test_no_active_node_keeps_position(self):
        mgr = NodeManager(object())
        d = make_node_editor(mgr)
        d.reposition_near_node()
        assert (d.rect.x, d.rect.y) == (0, 310)


class TestNudge:
    def test_dragged_onto_list_nudges_right(self):
        mgr = NodeManager(object())
        d = make_node_editor(mgr, rect=(50, 100, 260, 230))
        d._nudge_out_of_sidebar()
        assert not d.rect.colliderect(Rect(0, 65, 260, 240))
        assert d.rect.x == 260 + 10

    def test_no_overlap_no_move(self):
        mgr = NodeManager(object())
        d = make_node_editor(mgr, rect=(300, 400, 260, 230))
        d._nudge_out_of_sidebar()
        assert (d.rect.x, d.rect.y) == (300, 400)


class TestDuplicateNode:
    def test_clone_fields_and_active(self):
        mgr = NodeManager(object())
        node = make_node("Base", x=10, y=20, group="G")
        mgr.groups.append("G")
        mgr.nodes[node.node_id] = node
        mgr.active_node_id = node.node_id
        new_id = mgr.duplicate_node(node.node_id)
        assert new_id is not None and new_id != node.node_id
        clone = mgr.nodes[new_id]
        assert clone.name == "Base copy"
        assert (clone.area.x, clone.area.y) == (26, 36)
        assert (clone.area.w, clone.area.h) == (64, 64)
        assert clone.properties == {"a": 1}
        assert clone.properties is not node.properties
        assert clone.group == "G"
        assert clone.layer_name == "Terrain"
        assert mgr.active_node_id == new_id
        # order: directly after original
        assert list(mgr.nodes).index(new_id) == list(mgr.nodes).index(node.node_id) + 1

    def test_unique_names_on_repeat(self):
        mgr = NodeManager(object())
        node = make_node("Base")
        mgr.nodes[node.node_id] = node
        mgr.duplicate_node(node.node_id)
        second = mgr.duplicate_node(node.node_id)
        assert mgr.nodes[second].name == "Base copy 2"

    def test_unknown_id_returns_none(self):
        mgr = NodeManager(object())
        assert mgr.duplicate_node("nope") is None


def make_selector(manager):
    ed = FakeEditor(manager)
    s = NodeSelector.__new__(NodeSelector)
    s.editor = ed
    s.rect = Rect(0, 65, 260, 240)
    s.search_text = ""
    s.scroll_offset = 0
    s.item_h = 28
    s.header_h = 32
    s.collapsed_groups = set()
    s._filtered_rows = []
    return s


class TestCollapseAll:
    def test_toggle_collapses_and_expands(self):
        mgr = NodeManager(object())
        mgr.groups = ["G1", "G2"]
        mgr.nodes["a"] = make_node("A", group="G1")
        s = make_selector(mgr)
        assert s._all_collapsed() is False
        s._toggle_collapse_all()
        assert s._all_collapsed() is True
        # node rows hidden when collapsed
        assert all(r["type"] == "group" for r in s._filtered_rows)
        s._toggle_collapse_all()
        assert s._all_collapsed() is False
        assert any(r["type"] == "node" for r in s._filtered_rows)

    def test_toggle_rect_inside_header(self):
        mgr = NodeManager(object())
        s = make_selector(mgr)
        r = s._collapse_toggle_rect()
        assert Rect(0, 65, 260, 240).contains(r)
        assert r.y < 65 + 32


class TestSelectorDuplicate:
    def test_duplicate_rebuilds_and_histories(self):
        mgr = NodeManager(object())
        node = make_node("Base")
        mgr.nodes[node.node_id] = node
        s = make_selector(mgr)
        s._duplicate_node(node.node_id)
        assert len(mgr.nodes) == 2
        assert s.editor.tilemap.history == ["Duplicate Node"]
        assert any(r["type"] == "node" for r in s._filtered_rows)


class TestDrawNodesVisibility:
    def _grid(self, editing, showing):
        from widgets.tile_grid import TileGrid

        # Prior test modules quit pygame in fixtures; re-init locally.
        pygame.init()
        pygame.display.set_mode((1, 1))
        mgr = NodeManager(object())
        node = make_node("A", x=10, y=20)
        mgr.nodes[node.node_id] = node
        ed = FakeEditor(mgr)
        ed.node_editing_mode = editing
        ed.show_nodes = showing
        g = TileGrid.__new__(TileGrid)
        g.editor = ed
        g.rect = Rect(0, 0, 800, 600)
        g.zoom_level = 1.0
        g._node_to_screen = lambda x, y: (x, y)
        g._node_screen_size = lambda w, h: (w, h)
        g.font_status = pygame.font.Font(None, 12)
        return g

    def _blank(self):
        screen = pygame.Surface((800, 600))
        screen.fill((7, 7, 7))
        return screen

    def test_closed_viewer_draws_no_ghost_rects(self):
        g = self._grid(False, False)
        screen = self._blank()
        g._draw_nodes(screen)
        assert screen.get_at((11, 21))[:3] == (7, 7, 7)
        assert screen.get_at((40, 50))[:3] == (7, 7, 7)

    def test_editing_draws_rect(self):
        g = self._grid(True, False)
        screen = self._blank()
        g._draw_nodes(screen)
        assert screen.get_at((11, 21))[:3] != (7, 7, 7)

    def test_overlay_draws_rect(self):
        g = self._grid(False, True)
        screen = self._blank()
        g._draw_nodes(screen)
        assert screen.get_at((11, 21))[:3] != (7, 7, 7)


def make_layout_editor(node=None, group=None, rect=(0, 310, 260, 230)):
    mgr = NodeManager(object())
    if node is not None:
        mgr.nodes[node.node_id] = node
        mgr.active_node_id = node.node_id
    if group is not None:
        mgr.groups.append(group)
        mgr.set_active_group(group)
    ed = FakeEditor(mgr)
    d = NodeEditor.__new__(NodeEditor)
    d.editor = ed
    d.rect = Rect(*rect)
    d._dock_x, d._dock_y = rect[0], rect[1]
    return d


def particle_node():
    return Node(
        node_id="emit-1",
        name="Emitter 1",
        node_type="particle_emitter",
        area=NodeRect(x=0, y=0, w=64, h=64),
        layer_name="Terrain",
        properties={},
    )


class TestEditorLayout:
    def test_plain_panel_fits_content(self):
        d = make_layout_editor(make_node("A"))
        assert len(d._buttons()) == 1
        assert d._preset_rect() is None
        assert d._content_height() == 244

    def test_particle_panel_has_gaps_and_fits(self):
        d = make_layout_editor(particle_node())
        pr = d._preset_rect()
        btns = d._buttons()
        assert pr is not None and len(btns) == 2
        assert btns[0][0].y - pr.bottom >= NodeEditor.SECTION_GAP
        assert btns[1][0].y - btns[0][0].bottom >= NodeEditor.BUTTON_GAP
        lowest = max([r[2].bottom for r in d._get_field_rects()]
                     + [pr.bottom] + [b[0].bottom for b in btns])
        assert d._content_height() == lowest - d.rect.y + NodeEditor.BOTTOM_PAD

    def test_no_rect_overlaps(self):
        for node in (make_node("A"), particle_node()):
            d = make_layout_editor(node)
            pr = d._preset_rect()
            rects = ([r[2] for r in d._get_field_rects()]
                     + ([pr] if pr else [])
                     + [b[0] for b in d._buttons()])
            for i in range(len(rects)):
                for j in range(i + 1, len(rects)):
                    assert not rects[i].colliderect(rects[j])

    def test_group_mode_is_compact_single_field(self):
        d = make_layout_editor(group="G")
        assert len(d._get_field_rects()) == 1
        assert d._buttons() == []
        assert d._content_height() < 100


class TestAssertHardening:
    def test_hide_with_no_tileset_widget(self):
        from widgets.autotiler import AutotileRuleDesigner

        d = AutotileRuleDesigner.__new__(AutotileRuleDesigner)
        d.editor = FakeEditor(NodeManager(object()))
        d.editor.tileset_widget = None
        d.visible = True
        d.is_dragging = True
        d.hide()  # must not raise
        assert d.visible is False
        assert d.is_dragging is False

    def test_tileset_map_empty_without_widget(self):
        from widgets.tile_grid import TileGrid

        g = TileGrid.__new__(TileGrid)
        g.editor = FakeEditor(NodeManager(object()))
        g.editor.tileset_widget = None
        assert g._tileset_map() == {}

    def test_tileset_map_delegates_to_widget(self):
        from widgets.tile_grid import TileGrid

        g = TileGrid.__new__(TileGrid)
        sentinel = {(0,): "ts"}
        g.editor = FakeEditor(NodeManager(object()))
        g.editor.tileset_widget = type("W", (), {"tileset_map": sentinel})()
        assert g._tileset_map() is sentinel
