"""Tests for the hierarchical autotile classifier (distance-2 subcases).

Covers:
- Template apply populates subcase leaves (5x5 -> 25 singleton leaves)
- Round-trip: an exact motif mass classifies back to its own vids
- Run-length resolution (start/middle/end pieces on longer runs)
- Backoff: unseen shapes degrade to legacy random-among-variants
- Idempotence (re-autotile is a no-op once exact)
- Backward compat (subcase-less rules behave as before)
- Rule persistence round-trip + Move pruning of subcases
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from layers import Layer
from widgets.autotile_template import (
    TEMPLATES,
    AutotileTemplateApplier,
    motif_dist2,
)
from widgets.autotiler import AutotileGroup, AutotileRule, AutotileRuleDesigner

# ---------------------------------------------------------------------------
# Designer harness (mirrors test_autotile_templates.py, 6-wide sheet)

class FakeSurf:
    def __init__(self, w):
        self._w = w

    def get_width(self):
        return self._w


class FakeTS:
    def __init__(self, name="blob"):
        self.path = Path(f"/t/{name}.png")
        self.surface = FakeSurf(6 * 32)
        self.name = name


class FakeSelector:
    def __init__(self, rect):
        self.selected_tile = rect
        self.active_idx = 0
        self.tilesets = [FakeTS()]

    def get_active_tile(self):
        return self.tilesets[0]


class FakeMap:
    tile_size = (32, 32)


class FakeEditor:
    def __init__(self, rect):
        self.tileset_widget = FakeSelector(rect)
        self.tilemap = FakeMap()
        self.width = 800
        self.height = 600
        self.notifications = None


def make_designer(rect):
    ed = FakeEditor(rect)
    d = AutotileRuleDesigner.__new__(AutotileRuleDesigner)
    d.groups = [AutotileGroup("A"), AutotileGroup("B")]
    d.selected_group_idx = 0
    ap = AutotileTemplateApplier(d)
    d.editor = ed
    return d, ap


def template(name):
    for t in TEMPLATES:
        if t.name == name:
            return t
    raise AssertionError(f"missing template {name}")


def apply_5x5():
    d, ap = make_designer((0, 0, 5 * 32, 5 * 32))
    res = ap.apply_template(template("Standard 5x5 (Cardinal)"))
    assert "error" not in res
    return d.groups[0].rules


# ---------------------------------------------------------------------------
# Layer harness

def make_rule(name, neighbors, variant_ids=None, tileset_index=0,
              group_id=None, subcases=None):
    return AutotileRule(
        name=name,
        neighbors=set(neighbors),
        tileset_path="",
        variant_ids=variant_ids or [0],
        tileset_index=tileset_index,
        group_id=group_id or name,
        subcases=subcases,
    )


def tile(pos, ttype=0, variant=0, autotile_group="A"):
    d = {"pos": pos, "ttype": ttype, "variant": variant}
    if autotile_group is not None:
        d["autotile_group"] = autotile_group
    return d


def motif_layer(w, h, ox=0, oy=0, variant=99):
    layer = Layer("t")
    for y in range(h):
        for x in range(w):
            layer.tiles[(ox + x, oy + y)] = tile((ox + x, oy + y), variant=variant)
    return layer


# Sheet geometry of the harness: 6-wide sheet, motif at (0,0).
def vid(c, r):
    return r * 6 + c


# ===================================================================
class TestMotifSignatures:
    def test_dist2_splits_every_collapse_group(self):
        from collections import defaultdict

        from widgets.autotile_template import _cardinal_grid_mappings

        cells = _cardinal_grid_mappings(5, 5)
        filled = {(c, r) for c, r, _ in cells}
        by_card = defaultdict(list)
        for c, r, neighbors in cells:
            by_card[frozenset(neighbors)].append((c, r))
        for members in by_card.values():
            sigs = {motif_dist2(filled, c, r) for c, r in members}
            assert len(sigs) == len(members)

    def test_corner_is_singleton(self):
        filled = {(c, r) for c in range(5) for r in range(5)}
        assert motif_dist2(filled, 0, 0) == frozenset({(1, 0), (0, 1)})

    def test_edge_middle_has_both_continuations(self):
        filled = {(c, r) for c in range(5) for r in range(5)}
        assert motif_dist2(filled, 2, 0) == frozenset({(-1, 0), (1, 0), (0, 1)})

    def test_edge_start_has_one_continuation(self):
        filled = {(c, r) for c in range(5) for r in range(5)}
        assert motif_dist2(filled, 1, 0) == frozenset({(1, 0), (0, 1)})


# ===================================================================
class TestApplyPopulatesSubcases:
    def test_nine_rules_twenty_five_leaves(self):
        rules = apply_5x5()
        assert len(rules) == 9
        total_leaves = sum(len(r.subcases) for r in rules)
        assert total_leaves == 25
        for r in rules:
            for leaf in r.subcases.values():
                assert len(leaf) == 1

    def test_variant_ids_still_collapsed(self):
        rules = apply_5x5()
        full = [r for r in rules if r.neighbors == {(-1, 0), (1, 0), (0, -1), (0, 1)}]
        assert len(full) == 1
        assert len(full[0].variant_ids) == 9

    def test_second_apply_is_stable(self):
        d, ap = make_designer((0, 0, 5 * 32, 5 * 32))
        ap.apply_template(template("Standard 5x5 (Cardinal)"))
        before = {r.name: (list(r.variant_ids), dict(r.subcases))
                  for r in d.groups[0].rules}
        ap.apply_template(template("Standard 5x5 (Cardinal)"))
        after = {r.name: (list(r.variant_ids), dict(r.subcases))
                 for r in d.groups[0].rules}
        assert before == after


# ===================================================================
class TestRoundTrip:
    def test_exact_motif_resolves_to_own_vids(self):
        rules = apply_5x5()
        layer = motif_layer(5, 5)
        changed = layer.autotile_layer(rules)
        assert changed == 25
        for y in range(5):
            for x in range(5):
                assert layer.tiles[(x, y)]["variant"] == vid(x, y), (x, y)

    def test_round_trip_is_idempotent(self):
        rules = apply_5x5()
        layer = motif_layer(5, 5)
        layer.autotile_layer(rules)
        assert layer.autotile_layer(rules) == 0

    def test_offset_motif(self):
        rules = apply_5x5()
        layer = motif_layer(5, 5, ox=10, oy=7)
        layer.autotile_layer(rules)
        for y in range(5):
            for x in range(5):
                assert layer.tiles[(10 + x, 7 + y)]["variant"] == vid(x, y)


# ===================================================================
class TestRunLength:
    def _wide_block(self, w):
        rules = apply_5x5()
        layer = motif_layer(w, 3)
        layer.autotile_layer(rules)
        return layer

    def test_longer_top_edge_uses_start_middle_end(self):
        layer = self._wide_block(7)
        # corners
        assert layer.tiles[(0, 0)]["variant"] == vid(0, 0)
        assert layer.tiles[(6, 0)]["variant"] == vid(4, 0)
        # start / middle / end pieces of the top edge
        assert layer.tiles[(1, 0)]["variant"] == vid(1, 0)
        assert layer.tiles[(3, 0)]["variant"] == vid(2, 0)
        assert layer.tiles[(5, 0)]["variant"] == vid(3, 0)

    def test_longer_left_edge_uses_start_middle_end(self):
        rules = apply_5x5()
        layer = motif_layer(3, 7)
        layer.autotile_layer(rules)
        assert layer.tiles[(0, 0)]["variant"] == vid(0, 0)
        assert layer.tiles[(0, 1)]["variant"] == vid(0, 1)
        assert layer.tiles[(0, 3)]["variant"] == vid(0, 2)
        assert layer.tiles[(0, 5)]["variant"] == vid(0, 3)
        assert layer.tiles[(0, 6)]["variant"] == vid(0, 4)

    def test_interior_of_wide_mass_resolves(self):
        layer = self._wide_block(7)
        # deep interior tiles share the motif-center leaf only where the
        # 3x3 thickness signature matches; all must be in the interior set
        interior_vids = {vid(c, r) for c in range(1, 4) for r in range(1, 4)}
        assert layer.tiles[(3, 1)]["variant"] in interior_vids


# ===================================================================
class TestBackoff:
    def test_unseen_shape_falls_back_to_rule_set(self):
        rules = apply_5x5()
        # 3-wide wall top middle: edge pattern {L,R,D} with no
        # distance-2 continuation either side -- no motif subcase covers it.
        layer = Layer("t")
        for x in range(3):
            for y in range(2):
                layer.tiles[(x, y)] = tile((x, y))
        layer.autotile_layer(rules)
        top_rule = [r for r in rules if r.neighbors == {(-1, 0), (1, 0), (0, 1)}][0]
        assert layer.tiles[(1, 0)]["variant"] in top_rule.variant_ids

    def test_subcase_less_rule_random_as_before(self):
        rule = make_rule("edge", {(-1, 0), (1, 0), (0, 1)}, [10, 11, 12],
                         group_id="A")
        layer = Layer("t")
        layer.tiles[(1, 0)] = tile((1, 0), variant=99)
        layer.tiles[(0, 0)] = tile((0, 0), variant=10)
        layer.tiles[(2, 0)] = tile((2, 0), variant=10)
        layer.tiles[(1, 1)] = tile((1, 1), variant=10)
        layer.autotile_layer([rule])
        assert layer.tiles[(1, 0)]["variant"] in (10, 11, 12)

    def test_stable_variant_kept_without_subcases(self):
        rule = make_rule("edge", {(-1, 0), (1, 0), (0, 1)}, [10, 11, 12],
                         group_id="A")
        layer = Layer("t")
        layer.tiles[(1, 0)] = tile((1, 0), variant=11)
        layer.tiles[(0, 0)] = tile((0, 0), variant=10)
        layer.tiles[(2, 0)] = tile((2, 0), variant=10)
        layer.tiles[(1, 1)] = tile((1, 1), variant=10)
        assert layer.autotile_layer([rule]) == 0
        assert layer.tiles[(1, 0)]["variant"] == 11


# ===================================================================
class TestPersistenceAndMove:
    def test_rule_round_trip(self):
        rules = apply_5x5()
        for r in rules:
            r2 = AutotileRule.from_dict(r.to_dict())
            assert r2.subcases == r.subcases
            assert r2.variant_ids == r.variant_ids
            assert r2.neighbors == r.neighbors

    def test_legacy_dict_loads_empty(self):
        r = AutotileRule.from_dict({"name": "O", "neighbors": [], "variant_ids": [5]})
        assert r.subcases == {}
        assert r.leaf_for(set()) is None

    def test_move_prunes_subcase_vids(self):
        d, ap = make_designer((0, 0, 5 * 32, 5 * 32))
        ap.apply_template(template("Standard 5x5 (Cardinal)"))
        d.selected_group_idx = 1
        res = ap.apply_template(
            template("Standard 5x5 (Cardinal)"), collision_choice="move")
        assert res["moved"] == 25
        for r in d.groups[0].rules:
            assert r.variant_ids == []
            assert r.subcases == {}
        for r in d.groups[1].rules:
            for leaf in r.subcases.values():
                assert leaf
                assert all(v in r.variant_ids for v in leaf)


# ===================================================================
class TestLeafLookup:
    def test_leaf_for_normalizes(self):
        r = make_rule("e", {(1, 0)}, [1, 2],
                      subcases=[{"dist2": [[1, 0]], "variant_ids": [2]}])
        assert r.leaf_for({(1, 0)}) == [2]
        assert r.leaf_for([(1, 0)]) == [2]
        assert r.leaf_for(set()) is None
        assert r.leaf_for(None) is None
