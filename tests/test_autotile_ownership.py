"""Tests for autotile ownership disambiguation (Phase 3)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pygame
from pygame import Rect

pygame.display.set_mode((1, 1))

from layers import Layer
from widgets.autotiler import AutotileGroup, AutotileRule


def make_rule(name, neighbors, variant_ids, ts_idx=0, group_id=None):
    return AutotileRule(
        name=name,
        neighbors=set(neighbors),
        tileset_path="",
        variant_ids=list(variant_ids),
        tileset_index=ts_idx,
        group_id=group_id or name,
    )


def tile(pos, ttype=0, variant=0, group=None):
    d = {"pos": pos, "ttype": ttype, "variant": variant}
    if group is not None:
        d["autotile_group"] = group
    return d


class TestFirstWins:
    def test_overlapping_variant_resolves_to_first_group(self):
        layer = Layer("t")
        # Both groups claim (0, 0); no stamp -> legacy lookup decides.
        a = make_rule("a", set(), [0], group_id="A")
        b = make_rule("b", set(), [0], group_id="B")
        layer.tiles[(1, 1)] = tile((1, 1), variant=0)
        layer._autotile_tiles([a, b], [(1, 1)])
        assert layer._autotile_cache["variant_to_group"][(0, 0)] == "A"
        assert layer.tiles[(1, 1)].get("autotile_group") == "A"

    def test_stamp_still_beats_lookup(self):
        layer = Layer("t")
        a = make_rule("a", set(), [0], group_id="A")
        b = make_rule("b", set(), [1], group_id="B")
        layer.tiles[(1, 1)] = tile((1, 1), variant=1, group="B")
        layer._autotile_tiles([a, b], [(1, 1)])
        assert layer.tiles[(1, 1)].get("autotile_group") == "B"


class TestPerGroupOffsets:
    def test_diagonal_group_does_not_break_cardinal_group(self):
        layer = Layer("t")
        solo = make_rule("solo", set(), [1], group_id="A")
        top = make_rule("top", {(0, -1)}, [2], group_id="A")
        diag = make_rule("diag", {(-1, -1)}, [9], group_id="B")
        rules = [solo, top, diag]
        # (5,5) is an A member; diagonal neighbour (4,4) is also A.
        # B cares about (-1,-1) but A must ignore it and match solo.
        layer.tiles[(5, 5)] = tile((5, 5), variant=1)
        layer.tiles[(4, 4)] = tile((4, 4), variant=1)
        changes = layer._autotile_tiles(rules, [(5, 5)])
        assert changes == 0
        assert layer.tiles[(5, 5)].get("autotile_group") == "A"

    def test_cache_hash_covers_neighbors(self):
        layer = Layer("t")
        r = make_rule("r", set(), [1], group_id="A")
        layer.tiles[(0, 0)] = tile((0, 0), variant=1)
        layer._autotile_tiles([r], [(0, 0)])
        old_hash = layer._autotile_cache["rules_hash"]
        r.neighbors = {(0, -1)}
        layer._autotile_tiles([r], [(0, 0)])
        assert layer._autotile_cache["rules_hash"] != old_hash


class FakeNotifications:
    def __init__(self):
        self.messages = []

    def notify(self, text, **kwargs):
        self.messages.append(text)

    def success(self, text, **kwargs):
        self.messages.append(text)


class FakeAutotiler:
    def __init__(self, groups, selected=0, owners=None):
        self.groups = groups
        self.selected_group_idx = selected
        self._owners = owners or {}
        self.rules = [r for g in groups for r in g.rules]

    @property
    def variant_to_group(self):
        return dict(self._owners)


class FakeTilemap:
    offset = (0, 0)
    map_size = (10, 10)
    tile_size = (32, 32)


class FakeEditor:
    node_editing_mode = False
    show_nodes = False

    def __init__(self, autotiler):
        self.autotile_mode = True
        self.autotiler = autotiler
        self.tilemap = FakeTilemap()
        self.notifications = FakeNotifications()


class FakeTilesetData:
    tile_properties = {}


def make_grid(editor):
    from widgets.tile_grid import TileGrid

    g = TileGrid.__new__(TileGrid)
    g.editor = editor
    g.hover_cell = (2, 2)
    return g


class TestPaintPrefersSelected:
    def test_reassigns_owned_variant_to_selected(self):
        groups = [AutotileGroup("New")]
        autotiler = FakeAutotiler(groups, selected=0, owners={(0, 5): "Old"})
        editor = FakeEditor(autotiler)
        grid = make_grid(editor)
        layer = Layer("t")
        # src x = 5 tiles -> variant 5, owned by Old.
        grid._place_tile_grid(layer, 0, FakeTilesetData(),
                              (5 * 32, 0, 32, 32), 32, 32, 8)
        placed = layer.tiles[(2, 2)]
        assert placed["autotile_group"] == "New"
        assert any("Old" in m and "New" in m for m in editor.notifications.messages)

    def test_fresh_variant_stamped_selected_without_notice(self):
        groups = [AutotileGroup("New")]
        autotiler = FakeAutotiler(groups, selected=0, owners={})
        editor = FakeEditor(autotiler)
        grid = make_grid(editor)
        layer = Layer("t")
        grid._place_tile_grid(layer, 0, FakeTilesetData(),
                              (0, 0, 32, 32), 32, 32, 8)
        assert layer.tiles[(2, 2)]["autotile_group"] == "New"
        assert editor.notifications.messages == []

    def test_flood_fill_stamps_selected_group(self, monkeypatch):
        groups = [AutotileGroup("New")]
        autotiler = FakeAutotiler(groups, selected=0, owners={(0, 5): "Old"})
        editor = FakeEditor(autotiler)
        layer = Layer("t")
        layer.tiles[(2, 2)] = tile((2, 2), variant=9)
        tilemap = FakeTilemap()
        tilemap.capture_history = lambda *a, **k: None
        editor.tilemap = tilemap
        manager = type("M", (), {"get_active_layer": lambda self: layer})()
        tilemap.layer_manager = manager

        grid = make_grid(editor)
        grid.rect = Rect(-10000, -10000, 20000, 20000)

        class NoScroll:
            def handle_event(self, event):
                return False

        grid._v_scroll = NoScroll()
        grid._h_scroll = NoScroll()
        grid._handle_image_layer_event = lambda event: False
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))

        class Surf:
            def get_width(self):
                return 8 * 32

        data = FakeTilesetData()
        data.surface = Surf()
        grid.get_selected_brush = lambda: (0, data, (5 * 32, 0, 32, 32))

        class Ev:
            type = pygame.KEYDOWN
            key = pygame.K_f

        assert grid.handle_event(Ev()) is True
        assert layer.tiles[(2, 2)]["autotile_group"] == "New"


class TestRenameMigration:
    def test_rename_migrates_tile_stamps(self):
        from widgets.autotiler import AutotileRuleDesigner

        layer = Layer("t")
        layer.tiles[(0, 0)] = tile((0, 0), variant=1, group="Old")
        manager = type("M", (), {"layers": [layer]})()
        tilemap = type("T", (), {"layer_manager": manager})()
        editor = type("E", (), {"tilemap": tilemap})()
        d = AutotileRuleDesigner.__new__(AutotileRuleDesigner)
        d.editor = editor
        assert d._migrate_tile_stamps("Old", "New") == 1
        assert layer.tiles[(0, 0)]["autotile_group"] == "New"
