"""Tests for node state in undo/redo history."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from node_manager import NodeManager
from nodes import Node, NodeRect
from tilemap import Tilemap


def make_node(name, group=None):
    return Node(
        node_id=f"id-{name}",
        name=name,
        node_type="area",
        area=NodeRect(x=10, y=20, w=64, h=64),
        layer_name="Terrain",
        properties={"k": name},
        group=group,
    )


class FakeSelector:
    def __init__(self):
        self.rebuilds = 0

    def _rebuild_filter(self):
        self.rebuilds += 1


class FakeEditor:
    def __init__(self):
        self.node_manager = NodeManager(object())
        self.node_selector = FakeSelector()
        # NOTE: no `autotiler` attr at all (real editor always has one;
        # setting it to None trips an unrelated hasattr guard).


def make_tilemap():
    ed = FakeEditor()
    tm = Tilemap(ed)
    return ed, tm


class TestNodeUndoRedo:
    def test_add_node_undo_redo(self):
        ed, tm = make_tilemap()
        a = make_node("A")
        ed.node_manager.nodes[a.node_id] = a
        tm.capture_history("Add A")
        b = make_node("B")
        ed.node_manager.nodes[b.node_id] = b
        assert set(ed.node_manager.nodes) == {a.node_id, b.node_id}

        tm.undo()
        assert set(ed.node_manager.nodes) == {a.node_id}
        assert ed.node_selector.rebuilds >= 1

        tm.redo()
        assert set(ed.node_manager.nodes) == {a.node_id, b.node_id}

    def test_remove_node_undo_restores(self):
        ed, tm = make_tilemap()
        a = make_node("A")
        ed.node_manager.nodes[a.node_id] = a
        tm.capture_history("before delete")
        ed.node_manager.remove_node(a.node_id)
        assert ed.node_manager.nodes == {}
        tm.undo()
        assert set(ed.node_manager.nodes) == {a.node_id}
        assert ed.node_manager.nodes[a.node_id].properties == {"k": "A"}

    def test_groups_and_actives_restored(self):
        ed, tm = make_tilemap()
        mgr = ed.node_manager
        mgr.groups = ["G"]
        a = make_node("A", group="G")
        mgr.nodes[a.node_id] = a
        mgr.active_node_id = a.node_id
        tm.capture_history("grouped")

        mgr.groups.append("H")
        mgr.active_node_id = None
        mgr.active_group_name = "H"
        tm.undo()
        assert mgr.groups == ["G"]
        assert mgr.active_node_id == a.node_id
        assert mgr.active_group_name is None

    def test_stale_active_cleared(self):
        ed, tm = make_tilemap()
        a = make_node("A")
        ed.node_manager.nodes[a.node_id] = a
        ed.node_manager.active_node_id = "ghost"
        tm.capture_history("stale")
        ed.node_manager.active_node_id = None
        tm.undo()
        assert ed.node_manager.active_node_id is None

    def test_no_manager_tolerated(self):
        ed = FakeEditor()
        ed.node_manager = None
        ed.node_selector = None
        tm = Tilemap(ed)
        tm.capture_history("x")  # must not raise
        assert tm.history.can_undo
        tm.undo()
        tm.redo()


class TestAssertHardening:
    def test_get_nearest_tiles_malformed_input(self):
        ed = FakeEditor()
        tm = Tilemap(ed)
        assert tm.get_nearest_tiles(()) == ()
        assert tm.get_nearest_tiles((1, 2, 3)) == ()

    def test_load_rules_without_tileset_widget(self):
        ed = FakeEditor()
        # No tileset_widget attr at all: previews can't resolve, but rules
        # must still load instead of raising.
        assert not hasattr(ed, "tileset_widget")
        ed.node_manager = None
        ed.node_selector = None

        class FakeDesigner:
            def __init__(self):
                self.groups = []
                self.selected_group_idx = 0
                self.selected_rule_index = -1

        ed.autotiler = FakeDesigner()
        ed.tile_grid_widget = None
        tm = Tilemap(ed)
        payload = {
            "meta": {
                "tile_size": "32;32",
                "map_size": "10;10",
                "offset": "0;0",
                "render_scale": 1.0,
            },
            "resources": {"tilesets": []},
            "project_state": {
                "groups": [
                    {
                        "name": "G",
                        "rules": [
                            {
                                "name": "R1",
                                "neighbors": [[0, -1]],
                                "tileset_path": "",
                                "tileset_index": 0,
                                "variant_ids": [3],
                                "group_id": "G",
                            }
                        ],
                    }
                ]
            },
            "data": {},
        }
        tm.apply_map_payload(Path("/tmp/x.json"), payload)
        assert [g.name for g in ed.autotiler.groups] == ["G"]
        assert ed.autotiler.groups[0].rules[0].variant_ids == [3]
