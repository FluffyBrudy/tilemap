"""Aggressive integrity tests for tileset identity under mutation.

Regression ground: removing/reordering tilesets used to silently shift
positional ``ttype`` indices, re-pointing painted tiles at wrong sheets,
leaving ghost tree nodes that mis-selected on click, and writing maps
whose stored gids no longer matched ``firstgid[ttype] + variant``.

Every test here would have caught at least one of those failure modes.
"""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

pygame.init()
pygame.font.init()
pygame.display.set_mode((120, 120))

from layers import create_default_layer_manager  # noqa: E402
from tilemap import Tilemap  # noqa: E402
from utils.tileset_ops import (  # noqa: E402
    count_ttype_refs,
    make_placeholder_tileset,
    remap_after_removal,
    remap_rule_indexes,
    validate_ttype_bounds,
)
from widgets.tile_selector import TileSelector, TilesetData  # noqa: E402


@pytest.fixture(autouse=True)
def _ensure_pygame_alive():
    """Other suites call pygame.quit() in teardowns; make this module immune."""
    if not pygame.get_init():
        pygame.init()
    # Force a brand-new window surface: a half-torn-down display makes
    # convert_alpha()/image loading fail with "No convert format".
    pygame.display.quit()
    pygame.display.init()
    pygame.display.set_mode((120, 120))
    if not pygame.font.get_init():
        pygame.font.init()
    try:
        from utils.font_manager import font_manager

        font_manager.clear_cache()  # drop fonts bound to a dead display
    except Exception:
        pass
    yield


# ---------------------------------------------------------------------------
# fakes / builders
# ---------------------------------------------------------------------------


class FakeNotifications:
    def __init__(self):
        self.msgs: list[str] = []

    def notify(self, text, color=(200, 200, 200), duration=3.0):
        self.msgs.append(str(text))

    def has(self, needle: str) -> bool:
        return any(needle in m for m in self.msgs)


class FakeEditor:
    def __init__(self, data_root: Path | None = None):
        self.data_root = data_root
        self.notifications = FakeNotifications()
        self.suggestion_registry = SimpleNamespace(refresh=lambda editor: None)
        self.context_dispatch = SimpleNamespace(
            register_opener=lambda *a, **k: None,
            register_saver=lambda *a, **k: None,
        )
        self.tilemap = Tilemap(self)
        self.autotiler = None
        self.tile_grid_widget = None


def make_sheet(size=(64, 64)) -> pygame.Surface:
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill((10, 20, 30, 255))
    return surf


def add_tileset(sel: TileSelector, name: str, sheet=(64, 64)) -> TilesetData:
    ts = TilesetData(name, Path(f"/tmp/_ti_{name}"), make_sheet(sheet), tileset_type="tile")
    sel.tilesets.append(ts)
    sel.tileset_map[len(sel.tilesets) - 1] = ts
    return ts


def make_selector(n: int = 3, ed: FakeEditor | None = None, sheet=(64, 64)):
    ed = ed or FakeEditor()
    sel = TileSelector(ed, 0, 0, 420, 320)
    for i in range(n):
        add_tileset(sel, f"ts{i}.png", sheet)
    sel._sync_tree()
    ed.tileset_widget = sel
    return sel, ed


def add_layer(ed: FakeEditor, name="L", ltype="tile"):
    ed.tilemap.layer_manager.create_layer(name, ltype)
    return ed.tilemap.layer_manager.layers[-1]


def paint(layer, loc, ttype, variant=0):
    layer.tiles[loc] = {"pos": loc, "ttype": ttype, "variant": variant}


def all_records(ed: FakeEditor):
    for layer in ed.tilemap.layer_manager.layers:
        yield from layer.tiles.values()
        yield from layer.objects.values()


def make_autotiler(rules_spec):
    """rules_spec: list[(path_str, index_or_None)]"""
    rules = [
        SimpleNamespace(tileset_path=p, tileset_index=i) for p, i in rules_spec
    ]
    return SimpleNamespace(groups=[SimpleNamespace(rules=list(rules))], rules=[])


@pytest.fixture()
def sel3():
    sel, ed = make_selector(3)
    return sel, ed


# ---------------------------------------------------------------------------
# pure-ops edge cases
# ---------------------------------------------------------------------------


class TestPureOps:
    def test_count_and_remap_include_objects_and_skip_junk(self):
        ed = FakeEditor()
        lm = ed.tilemap.layer_manager
        lm.create_layer("t", "tile")
        lm.create_layer("o", "object")
        lt, lo = lm.layers[0], lm.layers[1]
        paint(lt, (0, 0), 2)
        lt.objects[1] = {"area": {}, "ttype": 3}
        lo.objects[2] = {"area": {}, "ttype": 2}
        lo.tiles[(9, 9)] = "not-a-dict"  # junk must be ignored

        assert count_ttype_refs(lm, 2) == 2
        assert count_ttype_refs(lm, 99) == 0

        changed = remap_after_removal(lm, 0)
        # two ttype==2 records drop to 1, plus the ttype==3 drops to 2
        assert changed == 3
        assert lt.tiles[(0, 0)]["ttype"] == 1
        assert lt.objects[1]["ttype"] == 2  # 3 -> 2
        assert lo.objects[2]["ttype"] == 1

    def test_validate_bounds_reports_both_kinds(self):
        ed = FakeEditor()
        lm = ed.tilemap.layer_manager
        lm.create_layer("t", "tile")
        lay = lm.layers[0]
        paint(lay, (0, 0), 5)
        lay.objects[7] = {"area": {}, "ttype": -1}

        problems = validate_ttype_bounds(lm, 3)
        assert len(problems) == 2
        assert any("tile (0, 0)" in p and "ttype 5" in p for p in problems)
        assert any("object #7" in p and "ttype -1" in p for p in problems)

    def test_validate_bounds_empty_world_ok(self):
        assert validate_ttype_bounds(create_default_layer_manager(), 3) == []

    def test_rule_remap_down_and_path_fallback(self):
        auto = make_autotiler([("/a.png", 0), ("/b.png", 1), ("/c.png", 2)])
        r0, r1, r2 = auto.groups[0].rules

        fixed = remap_rule_indexes(auto, 1, [SimpleNamespace(path=Path("/a.png")), SimpleNamespace(path=Path("/c.png"))])

        assert fixed == 2
        assert r0.tileset_index == 0  # untouched (< removed)
        # r1 pointed AT removed slot -> falls back to its persisted path,
        # which no longer resolves -> None
        assert r1.tileset_index is None
        assert r2.tileset_index == 1  # shifted down

    def test_rule_remap_resolves_by_stem_after_reorder(self):
        auto = make_autotiler([("/x/b.png", 0)])
        (r,) = auto.groups[0].rules
        remap_rule_indexes(auto, 0, [SimpleNamespace(path=Path("/elsewhere/b.png"))])
        assert r.tileset_index == 0  # stem match wins over missing exact path

    def test_placeholder_builder(self):
        ph = make_placeholder_tileset("/nope/gone.png", (16, 16))
        assert ph.surface.get_size() == (16, 16)
        assert ph.name.startswith("gone.png")
        assert "(missing)" in ph.name
        assert ph.properties.get("placeholder") is True
        # exactly one tile so variant math stays in bounds
        assert ph.surface.get_width() == 16 and ph.surface.get_height() == 16


# ---------------------------------------------------------------------------
# removal behaviour (the core regressions)
# ---------------------------------------------------------------------------


class TestRemoval:
    def test_remove_unreferenced_middle_remaps_and_syncs_tree(self, sel3):
        sel, ed = sel3
        _, b, c = sel.tilesets
        lay = add_layer(ed)
        paint(lay, (0, 0), 2, variant=3)  # C-tile
        paint(lay, (1, 0), 0, variant=1)  # A-tile untouched by B removal

        sel.active_idx = 1  # remove B (middle, unreferenced)
        sel.remove_tileset()

        assert [t.name for t in sel.tilesets] == ["ts0.png", "ts2.png"]
        assert sel.tileset_map == {0: sel.tilesets[0], 1: sel.tilesets[1]}
        # C shifted 2 -> 1 everywhere; A untouched
        assert lay.tiles[(0, 0)]["ttype"] == 1
        assert lay.tiles[(1, 0)]["ttype"] == 0
        # ghost node gone from the tree
        assert sel._tree.find_node(b.uid) is None
        assert sel._tree.find_node(c.uid) is not None
        assert ed.notifications.has("Removed tileset 'ts1.png'")
        assert sel.active_idx == 1

    def test_remove_referenced_is_blocked(self, sel3):
        sel, ed = sel3
        before_sets = list(sel.tilesets)
        before_tree_ids = {n.id for n in sel._walk_all(sel._tree.roots)}
        lay = add_layer(ed)
        paint(lay, (0, 0), 1)

        sel.active_idx = 1
        sel.remove_tileset()

        assert sel.tilesets == before_sets
        assert {n.id for n in sel._walk_all(sel._tree.roots)} == before_tree_ids
        assert ed.notifications.has("Cannot remove")
        assert ed.notifications.has("1 painted")

    def test_remove_first_shift_survivor_indices__user_regression(self, sel3):
        """The reported bug: dropping an unused lower-index set corrupted
        every higher-index (primary) tileset's meaning."""
        sel, ed = sel3
        lay = add_layer(ed)
        paint(lay, (0, 0), 1)
        paint(lay, (5, 5), 2)

        sel.active_idx = 0  # ts0 unpainted
        sel.remove_tileset()

        assert len(sel.tilesets) == 2
        assert lay.tiles[(0, 0)]["ttype"] == 0  # was 1
        assert lay.tiles[(5, 5)]["ttype"] == 1  # was 2
        assert count_ttype_refs(ed.tilemap.layer_manager, 99) == 0
        # every surviving record still resolves inside the new range
        assert validate_ttype_bounds(ed.tilemap.layer_manager, len(sel.tilesets)) == []

    @pytest.mark.parametrize("start", [3, 2, 1])
    def test_remove_boundaries_down_to_empty(self, start):
        sel, ed = make_selector(start)
        while sel.tilesets:
            sel.active_idx = len(sel.tilesets) - 1
            expected_name = sel.tilesets[-1].name
            sel.remove_tileset()
            assert ed.notifications.has(f"Removed tileset '{expected_name}'")
            if sel.tilesets:
                assert sel.active_idx == len(sel.tilesets) - 1
                assert len(sel.tileset_map) == len(sel.tilesets)

        assert sel.tilesets == []
        assert sel.tileset_map == {}
        assert sel.active_idx == -1
        assert not [n for n in sel._walk_all(sel._tree.roots) if not n.is_folder]

    def test_remove_with_no_selection_is_safe(self, sel3):
        sel, ed = sel3
        sel.active_idx = -1
        sel.remove_tileset()  # must not raise / mutate
        assert len(sel.tilesets) == 3

    def test_ghost_click_never_selects_wrong_set(self, sel3):
        sel, _ = sel3
        a, b, c = sel.tilesets
        sel.active_idx = 1
        sel.remove_tileset()

        # stale consumer still holding B's uid must resolve to None...
        assert sel._ts_node(b.uid) is None
        # ...and selecting survivors by uid picks the right object
        assert sel._ts_node(a.uid) is a
        assert sel._ts_node(c.uid) is c
        sel._on_tree_selection([c.uid])
        assert sel.tilesets[sel.active_idx] is c


# ---------------------------------------------------------------------------
# save gate
# ---------------------------------------------------------------------------


class TestSaveGate:
    def test_save_roundtrip_gid_invariant(self, tmp_path):
        ed = FakeEditor(data_root=tmp_path)
        sel, _ = make_selector(3, ed=ed)
        lay = add_layer(ed, "base")
        paint(lay, (0, 0), 0, variant=0)
        paint(lay, (1, 0), 1, variant=2)
        paint(lay, (2, 0), 2, variant=3)

        out = tmp_path / "m.json"
        ed.tilemap.save_map(out)

        assert out.exists(), "clean world must produce a file"
        data = json.loads(out.read_text())
        res = data["resources"]["tilesets"]
        tfg = []
        acc = 0
        for ts in res:
            tfg.append(acc)
            acc += ts["tile_count"]
        for layer in data["data"]["layers"]:
            for rec in layer["tiles"].values():
                assert rec["gid"] == tfg[rec["ttype"]] + rec["variant"]

    def test_save_aborts_and_leaves_disk_untouched_on_bad_ttype(self, tmp_path):
        ed = FakeEditor(data_root=tmp_path)
        sel, _ = make_selector(3, ed=ed)
        lay = add_layer(ed)
        paint(lay, (0, 0), 9)  # out of range

        out = tmp_path / "m.json"
        ed.tilemap.save_map(out)

        assert not out.exists()
        assert ed.notifications.has("Save aborted")
        assert ed.notifications.has("ttype 9")


# ---------------------------------------------------------------------------
# load path: missing file keeps index space
# ---------------------------------------------------------------------------


class TestLoadPlaceholder:
    def _payload(self, missing_png: Path, real_png: Path):
        return {
            "meta": {
                "tile_size": "8;8",
                "map_size": "4;4",
                "offset": "0;0",
                "render_scale": 1.0,
                "version": "1.1",
            },
            "resources": {
                "tilesets": [
                    {"path": str(missing_png), "type": "tile", "tile_count": 4, "firstgid": 0},
                    {"path": str(real_png), "type": "tile", "tile_count": 4, "firstgid": 4},
                ]
            },
            "project_state": {"rules": []},
            "data": {"ongrid": {}, "layers": []},
        }

    def test_missing_file_becomes_placeholder_slot(self, tmp_path):
        ed = FakeEditor(data_root=tmp_path)
        sel, _ = make_selector(0, ed=ed)

        real = tmp_path / "real.png"
        pygame.image.save(make_sheet((16, 16)), str(real))
        ghost = tmp_path / "ghost.png"  # never created

        ed.tilemap.apply_map_payload(tmp_path / "p.json", self._payload(ghost, real))

        assert len(sel.tilesets) == 2, "slot count must be preserved"
        first, second = sel.tilesets
        assert "(missing)" in first.name
        assert first.path == ghost
        assert second.path == real
        assert sel.tileset_map[0] is first and sel.tileset_map[1] is second


# ---------------------------------------------------------------------------
# drag/reorder invariance
# ---------------------------------------------------------------------------


class TestReorderInvariance:
    def test_tree_drag_does_not_touch_tileset_order(self, sel3):
        sel, _ = sel3
        order_before = [t.uid for t in sel.tilesets]

        tree = sel._tree
        node_c = tree.find_node(sel.tilesets[2].uid)
        node_a = tree.find_node(sel.tilesets[0].uid)
        tree.roots.remove(node_c)
        tree.roots.insert(tree.roots.index(node_a), node_c)
        tree.set_data(tree.roots)

        assert [t.uid for t in sel.tilesets] == order_before
        # visual order changed, data order did not
        visual = [n.id for n in tree.roots if not n.is_folder]
        assert visual[0] == sel.tilesets[2].uid

    def test_save_output_identical_across_pure_visual_reorder(self, tmp_path):
        ed = FakeEditor(data_root=tmp_path)
        sel, _ = make_selector(3, ed=ed)
        lay = add_layer(ed)
        paint(lay, (0, 0), 2, variant=1)

        out = tmp_path / "m.json"
        ed.tilemap.save_map(out)
        first = out.read_text()

        tree = sel._tree
        node_c = tree.find_node(sel.tilesets[2].uid)
        tree.roots.remove(node_c)
        tree.roots.append(node_c)
        tree.set_data(tree.roots)

        out.unlink()
        ed.tilemap.save_map(out)
        assert out.read_text() == first


# ---------------------------------------------------------------------------
# full-stack fuzz: random removal sequences keep the invariant
# ---------------------------------------------------------------------------


class TestFuzzInvariant:
    def test_randomized_remove_cycles_preserve_integrity(self, tmp_path):
        import random

        rng = random.Random(1337)
        for trial in range(25):
            ed = FakeEditor(data_root=tmp_path / f"t{trial}")
            ed.data_root.mkdir(parents=True, exist_ok=True)
            n = rng.randint(1, 5)
            sel, _ = make_selector(n, ed=ed)
            lay = add_layer(ed, "fuzz")

            live = list(range(n))
            painted = {}
            for i in range(rng.randint(0, 12)):
                idx = rng.choice(live) if live else 0
                painted[(i % 8, i % 6)] = idx
                paint(lay, (i % 8, i % 6), idx, variant=rng.randint(0, 3))

            # attempt random removals; referenced ones must be blocked
            for _ in range(rng.randint(1, n)):
                if not live:
                    break
                victim = rng.randrange(len(live))
                refs_any = any(v == victim for v in painted.values())
                used_names = {sel.tilesets[v].name for v in set(painted.values())}
                sel.active_idx = victim
                sel.remove_tileset()
                if refs_any and sel.tilesets[victim].name in used_names:
                    # blocked -> index space unchanged
                    pass
                else:
                    live = [i if i < victim else i - 1 for i in live if i != victim]
                    painted = {
                        k: (v if v < victim else v - 1) for k, v in painted.items()
                    }

                problems = validate_ttype_bounds(
                    ed.tilemap.layer_manager, len(sel.tilesets)
                )
                assert problems == [], f"trial {trial}: {problems[:3]}"
                assert len(sel.tileset_map) == len(sel.tilesets)
                assert sel._tree.find_node is not None
