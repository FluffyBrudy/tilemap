"""Tests for autotile templates: 4x4/5x5 + overlap guard (Phase 1)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import widgets.autotile_template as _template_mod
from widgets.autotile_template import (
    TEMPLATES,
    AutotileTemplateApplier,
    _cardinal_grid_mappings,
)
from widgets.autotiler import AutotileGroup, AutotileRuleDesigner


class _DummyFont:
    def render(self, *args, **kwargs):
        raise AssertionError("render() must not be called in logic tests")


class _DummyFonts:
    def get_font(self, *args, **kwargs):
        return _DummyFont()


# Avoid caching real pygame Font objects in the global font manager:
# other test modules quit/re-init pygame per test, which would invalidate
# cached fonts ("font module quit since font created"). Logic tests never
# draw, so a stub is sufficient.
_template_mod.FONTS = _DummyFonts()


class FakeSurf:
    def __init__(self, w):
        self._w = w

    def get_width(self):
        return self._w


class FakeTS:
    def __init__(self, name="grass"):
        self.path = Path(f"/t/{name}.png")
        self.surface = FakeSurf(6 * 32)
        self.name = name


class FakeSelector:
    def __init__(self, rect=(0, 0, 4 * 32, 4 * 32)):
        self.selected_tile = rect
        self.active_idx = 0
        self.tilesets = [FakeTS()]

    def get_active_tile(self):
        return self.tilesets[0]


class FakeMap:
    tile_size = (32, 32)


class FakeEditor:
    def __init__(self, rect=(0, 0, 4 * 32, 4 * 32)):
        self.tileset_widget = FakeSelector(rect)
        self.tilemap = FakeMap()
        self.width = 800
        self.height = 600
        self.notifications = None


def make_designer(rect=(0, 0, 4 * 32, 4 * 32)):
    ed = FakeEditor(rect)
    d = AutotileRuleDesigner.__new__(AutotileRuleDesigner)
    d.groups = [AutotileGroup("A"), AutotileGroup("B")]
    d.selected_group_idx = 0
    ap = AutotileTemplateApplier(d)
    d.editor = ed
    return d, ap


def template(name):
    return next(t for t in TEMPLATES if t.name == name)


class TestGridMappings:
    def test_4x4_collapses_to_9_patterns(self):
        maps = _cardinal_grid_mappings(4, 4)
        assert len(maps) == 16
        assert len({tuple(sorted(n)) for _, _, n in maps}) == 9

    def test_5x5_collapses_to_9_patterns(self):
        maps = _cardinal_grid_mappings(5, 5)
        assert len(maps) == 25
        assert len({tuple(sorted(n)) for _, _, n in maps}) == 9

    def test_templates_registered(self):
        names = [t.name for t in TEMPLATES]
        assert "Standard 4x4 (Cardinal)" in names
        assert "Standard 5x5 (Cardinal)" in names
        for name in ("Horizontal 4x1", "Vertical 1x4",
                     "Horizontal 5x1", "Vertical 1x5"):
            assert name in names

    def test_3x3_unchanged(self):
        t3 = template("Standard 3x3 (Cardinal)")
        assert len(t3.mappings) == 9

    def test_strips_collapse_to_3_patterns(self):
        for name, n in (("Horizontal 4x1", 4), ("Vertical 1x4", 4),
                        ("Horizontal 5x1", 5), ("Vertical 1x5", 5)):
            t = template(name)
            assert len(t.mappings) == n
            assert len({tuple(sorted(nb)) for _, _, nb in t.mappings}) == 3

    def test_strip_ends_match_3x1_ends(self):
        h3 = {(c, r, tuple(sorted(n))) for c, r, n in
              template("Horizontal 3x1").mappings}
        h4 = {(c, r, tuple(sorted(n))) for c, r, n in
              template("Horizontal 4x1").mappings}
        # first cell and last-cell pattern equal the 3x1 ends
        assert (0, 0, ((1, 0),)) in h4
        assert (3, 0, ((-1, 0),)) in h4
        assert (0, 0, ((1, 0),)) in h3
        assert (2, 0, ((-1, 0),)) in h3


class TestApply:
    def test_apply_4x4_creates_9_rules_16_variants(self):
        d, ap = make_designer()
        res = ap.apply_template(template("Standard 4x4 (Cardinal)"))
        assert res["added"] == 9
        assert res["updated"] == 7
        vids = [v for r in d.groups[0].rules for v in r.variant_ids]
        assert len(vids) == 16
        assert len(set(vids)) == 16

    def test_apply_5x5_creates_9_rules_25_variants(self):
        d, ap = make_designer((0, 0, 5 * 32, 5 * 32))
        # sheet is 6 wide; 5x5 fits
        res = ap.apply_template(template("Standard 5x5 (Cardinal)"))
        assert res["added"] == 9
        vids = [v for r in d.groups[0].rules for v in r.variant_ids]
        assert len(vids) == 25

    def test_partial_selection_applies_subset(self):
        d, ap = make_designer((0, 0, 2 * 32, 2 * 32))
        res = ap.apply_template(template("Standard 4x4 (Cardinal)"))
        assert res["added"] == 4
        vids = [v for r in d.groups[0].rules for v in r.variant_ids]
        assert len(vids) == 4

    def test_apply_4x1_creates_3_rules_4_variants(self):
        d, ap = make_designer((0, 0, 4 * 32, 1 * 32))
        res = ap.apply_template(template("Horizontal 4x1"))
        assert res["added"] == 3
        assert res["updated"] == 1
        vids = [v for r in d.groups[0].rules for v in r.variant_ids]
        assert sorted(vids) == [0, 1, 2, 3]

    def test_apply_1x4_creates_3_rules_4_variants(self):
        d, ap = make_designer((0, 0, 1 * 32, 4 * 32))
        res = ap.apply_template(template("Vertical 1x4"))
        assert res["added"] == 3
        assert res["updated"] == 1
        vids = [v for r in d.groups[0].rules for v in r.variant_ids]
        assert sorted(vids) == [0, 6, 12, 18]

    def test_apply_5x1_creates_3_rules_5_variants(self):
        d, ap = make_designer((0, 0, 5 * 32, 1 * 32))
        res = ap.apply_template(template("Horizontal 5x1"))
        assert res["added"] == 3
        assert res["updated"] == 2
        vids = [v for r in d.groups[0].rules for v in r.variant_ids]
        assert sorted(vids) == [0, 1, 2, 3, 4]

    def test_apply_1x5_creates_3_rules_5_variants(self):
        d, ap = make_designer((0, 0, 1 * 32, 5 * 32))
        res = ap.apply_template(template("Vertical 1x5"))
        assert res["added"] == 3
        assert res["updated"] == 2
        vids = [v for r in d.groups[0].rules for v in r.variant_ids]
        assert sorted(vids) == [0, 6, 12, 18, 24]

    def test_no_selection_errors(self):
        d, ap = make_designer()
        d.editor.tileset_widget.selected_tile = None
        res = ap.apply_template(template("Standard 3x3 (Cardinal)"))
        assert "error" in res


class TestOverlapGuard:
    def _fill_a(self):
        d, ap = make_designer()
        ap.apply_template(template("Standard 4x4 (Cardinal)"))
        d.selected_group_idx = 1
        return d, ap

    def test_plan_detects_nested_overlap(self):
        d, ap = self._fill_a()
        items, collisions, err = ap.plan_template_application(
            template("Standard 4x4 (Cardinal)"))
        assert err == ""
        assert len(items) == 16
        # 3x3 region is bound inside 4x4 -> all 16 overlap
        assert len(collisions) == 16
        assert set(collisions.values()) == {"A"}

    def test_cancel_keeps_target_empty(self):
        d, ap = self._fill_a()
        res = ap.apply_template(
            template("Standard 4x4 (Cardinal)"), collision_choice="cancel")
        assert res.get("cancelled")
        assert d.groups[1].rules == []
        # owner untouched
        assert len(d.groups[0].rules) == 9

    def test_merge_shares_tiles(self):
        d, ap = self._fill_a()
        res = ap.apply_template(
            template("Standard 4x4 (Cardinal)"), collision_choice="merge")
        assert res["added"] == 9
        assert len(d.groups[1].rules) == 9
        # first-wins owner stays A
        assert ap._owner_map(0)[0] == "A"

    def test_move_steals_tiles_and_prunes_emptied(self):
        d, ap = self._fill_a()
        # B already has merged copy; move again after re-adding to A
        ap.apply_template(
            template("Standard 4x4 (Cardinal)"), collision_choice="merge")
        res = ap.apply_template(
            template("Standard 4x4 (Cardinal)"), collision_choice="move")
        assert res["moved"] == 16
        assert all(len(r.variant_ids) > 0 for r in d.groups[1].rules)
        assert d.groups[0].rules == []

    def test_request_apply_opens_pending_on_collision(self):
        d, ap = self._fill_a()
        res = ap.request_apply_template(template("Standard 4x4 (Cardinal)"))
        assert res.get("pending")
        assert ap.pending_collision is not None
        out = ap.resolve_pending_collision("cancel")
        assert out.get("cancelled")
        assert ap.pending_collision is None
        assert d.groups[1].rules == []

    def test_pending_collision_swallows_wheel(self):
        import pygame

        d, ap = self._fill_a()
        ap.request_apply_template(template("Standard 4x4 (Cardinal)"))
        assert ap.pending_collision is not None
        wheel = pygame.event.Event(pygame.MOUSEWHEEL, {"x": 0, "y": 1})
        assert ap.handle_event(wheel) is True
        ap.resolve_pending_collision("cancel")
        assert ap.handle_event(wheel) is False
