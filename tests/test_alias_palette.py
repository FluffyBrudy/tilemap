"""Tests for the alias palette (sidebar tab) and alias paint branch."""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest
from pygame import Rect

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from layers import Layer
from widgets.ui import theme as theme_module


@pytest.fixture(autouse=True)
def _reinit_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield


def write_alias_file(path, tileset="tiles/stone.png", aliases=()):
    path.write_text(json.dumps({
        "version": 1, "tileset": tileset,
        "aliases": [{"name": n, "w": 2, "h": 2,
                     "cells": [[0, 0, v]]} for n, v in aliases]}))


class FakeTileset:
    def __init__(self, name="stone.png"):
        self.path = Path(f"/proj/tiles/{name}")
        self.surface = pygame.Surface((4 * 32, 4 * 32), pygame.SRCALPHA)
        self.surface.fill((40, 50, 60, 255))
        self.tile_properties = {}
        self.tileset_type = "tile"


class FakeNotes:
    def __init__(self):
        self.notes = []
        self.good = []

    def notify(self, msg, *a, **k):
        self.notes.append(msg)

    def success(self, msg, *a, **k):
        self.good.append(msg)


class FakeTilemap:
    initialized = True
    offset = (0, 0)
    map_size = (10, 10)
    tile_size = (32, 32)
    render_scale = 1.0

    def __init__(self, layer):
        self.layer_manager = type(
            "M", (), {"get_active_layer": lambda self: layer})()
        self.history = []

    def capture_history(self, description=""):
        self.history.append(description)


class FakeEditor:
    def __init__(self, aliases_dir, tilesets=None):
        self.data_root = Path("/proj/data")
        self.config = {"aliases_path": "aliases",
                       "alias_scopes": {"Env": ["stone"]}}
        self._aliases_dir = Path(aliases_dir)
        self.tilemap = type("T", (), {"tile_size": (32, 32)})()
        self.tileset_widget = type(
            "W", (), {"tilesets": tilesets or [], "active_idx": 0})()
        self.brush_mode = "tileset"
        self.active_alias = None
        self.notifications = FakeNotes()
        self.composer_launches = 0

    def launch_alias_composer(self):
        self.composer_launches += 1


def make_palette(aliases_dir, tilesets=("stone.png",)):
    from widgets.ui.alias_palette import AliasPalette

    ed = FakeEditor(aliases_dir, [FakeTileset(n) for n in tilesets])
    ed.data_root = Path(aliases_dir).parent
    pal = AliasPalette.__new__(AliasPalette)
    pal.editor = ed
    # bypass __init__ config read: call real init pieces manually
    AliasPalette.__init__(pal, ed, 0, 0, 220, 600)
    return pal, ed


class TestPalette:
    def test_loads_scope_and_arms_on_select(self, tmp_path):
        ad = tmp_path / "aliases"
        ad.mkdir()
        write_alias_file(ad / "stone.alias.json", aliases=[("Wall", 5), ("End", 6)])
        pal, ed = make_palette(ad)
        assert [a.name for _, _, a in pal.filtered] == ["Wall", "End"]
        pal.selected = 1
        assert pal.arm_selected() is True
        assert ed.brush_mode == "alias"
        stem, ref, pattern = ed.active_alias
        assert (stem, pattern.name, pattern.cells) == ("stone", "End", [(0, 0, 6)])

    def test_search_filters(self, tmp_path):
        ad = tmp_path / "aliases"
        ad.mkdir()
        write_alias_file(ad / "stone.alias.json",
                         aliases=[("WallEnd", 1), ("WallMid", 2), ("Rock", 3)])
        pal, _ = make_palette(ad)
        pal.search.text = "wall"
        pal.apply_filter()
        assert [a.name for _, _, a in pal.filtered] == ["WallEnd", "WallMid"]

    def test_empty_dir_no_crash(self, tmp_path):
        pal, _ = make_palette(tmp_path / "aliases")
        # configured scope exists but its file is absent -> empty, no crash
        assert pal.filtered == [] and pal.scope_name == "Env"
        assert pal.arm_selected() is False

    def test_mtime_reload(self, tmp_path):
        ad = tmp_path / "aliases"
        ad.mkdir()
        write_alias_file(ad / "stone.alias.json", aliases=[("A", 1)])
        pal, _ = make_palette(ad)
        assert len(pal.filtered) == 1
        write_alias_file(ad / "stone.alias.json", aliases=[("A", 1), ("B", 2)])
        pal.refresh_items(force=True)
        assert [a.name for _, _, a in pal.filtered] == ["A", "B"]

    def test_missing_tileset_thumb_no_crash(self, tmp_path):
        ad = tmp_path / "aliases"
        ad.mkdir()
        write_alias_file(ad / "stone.alias.json", "tiles/gone.png", [("A", 1)])
        pal, _ = make_palette(ad, tilesets=())
        thumb = pal._thumbnail("stone", "tiles/gone.png", pal.filtered[0][2])
        assert thumb.get_size() == (64, 64)

    def test_mode_radio(self, tmp_path):
        ad = tmp_path / "aliases"
        ad.mkdir()
        pal, ed = make_palette(ad)
        pal.set_brush_mode("alias")
        assert ed.brush_mode == "alias"
        pal.set_brush_mode("tileset")
        assert ed.brush_mode == "tileset" and ed.active_alias is None


def make_grid(monkeypatch, tilesets=("stone.png",)):
    from widgets.tile_grid import TileGrid
    from widgets.ui.tool_manager import ToolManager

    layer = Layer("t")
    ed = FakeEditor("/tmp", [FakeTileset(n) for n in tilesets])
    ed.tilemap = FakeTilemap(layer)
    ed.autotile_mode = False
    ed.node_editing_mode = False
    ed.show_nodes = False
    ed.tool_manager = ToolManager()
    g = TileGrid.__new__(TileGrid)
    g.editor = ed
    g.rect = Rect(-10000, -10000, 20000, 20000)
    g.hover_cell = (2, 3)
    g.invalidate_bounds_cache = lambda: None
    g.is_panning = False

    class NoScroll:
        def handle_event(self, event):
            return False

    g._v_scroll = NoScroll()
    g._h_scroll = NoScroll()
    g._handle_image_layer_event = lambda event: False
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
    return g, ed, layer


class TestAliasPaint:
    def test_plots_pattern_at_hover(self, monkeypatch):
        from aliases import AliasPattern

        g, ed, layer = make_grid(monkeypatch)
        ed.brush_mode = "alias"
        ed.active_alias = ("stone", "tiles/stone.png",
                           AliasPattern(name="W", w=2, h=2,
                                        cells=[(0, 0, 5), (1, 1, 6)]))
        g.place_tile()
        assert layer.tiles[(2, 3)]["variant"] == 5
        assert layer.tiles[(3, 4)]["variant"] == 6
        assert layer.tiles[(2, 3)]["ttype"] == 0
        # plotting itself captures nothing; the stroke entry comes
        # from the mousedown event path (single entry per stroke)
        assert ed.tilemap.history == []
        assert any("W" in m for m in ed.notifications.good)

    def test_stroke_captures_once(self, monkeypatch):
        from aliases import AliasPattern
        from widgets.ui.tool_manager import ToolKind

        g, ed, layer = make_grid(monkeypatch)
        ed.brush_mode = "alias"
        ed.active_alias = ("stone", "tiles/stone.png",
                           AliasPattern(name="W", w=1, h=1,
                                        cells=[(0, 0, 5)]))
        g.hover_cell = (1, 1)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        down = pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                  {"button": 1, "pos": (0, 0)})
        assert g.handle_event(down) is True
        assert ed.tilemap.history == ["Paint Alias"]
        # held-button motion plots without new history entries
        g.place_tile()
        g.place_tile()
        assert ed.tilemap.history == ["Paint Alias"]
        assert not ed.tool_manager.is_active(ToolKind.RECT_FILL)

    def test_missing_tileset_notifies_no_crash(self, monkeypatch):
        from aliases import AliasPattern

        g, ed, layer = make_grid(monkeypatch, tilesets=("other.png",))
        ed.brush_mode = "alias"
        ed.active_alias = ("stone", "tiles/stone.png",
                           AliasPattern(name="W", w=1, h=1, cells=[(0, 0, 5)]))
        g.place_tile()
        assert layer.tiles == {}
        assert any("alias" in m.lower() for m in ed.notifications.notes)

    def test_rect_fill_blocked_in_alias_mode(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        ed.brush_mode = "alias"
        g.rect_fill_start = (0, 0)
        g.rect_fill_rect = (0, 0, 1, 1)
        g._commit_rect_fill()
        assert layer.tiles == {}
        assert any("single plot" in m for m in ed.notifications.notes)

    def test_line_blocked_in_alias_mode(self, monkeypatch):
        g, ed, layer = make_grid(monkeypatch)
        ed.brush_mode = "alias"
        g.line_start = (0, 0)
        g.line_end = (1, 0)
        g._commit_line()
        assert layer.tiles == {}


class TestCreateAliasFromSelection:
    def _grid(self, monkeypatch, tmp_path, tilesets=("stone.png", "grass.png")):
        from widgets.tile_grid import TileGrid

        layer = Layer("t")
        ed = FakeEditor(str(tmp_path), [FakeTileset(n) for n in tilesets])
        ed.data_root = tmp_path
        ed.config = {"aliases_path": "aliases"}
        ed.base_path = tmp_path
        ed.tilemap = FakeTilemap(layer)
        ed.autotile_mode = False
        ed.registered = []
        ed.register_alias_source = lambda stem: ed.registered.append(stem)
        refreshed = []
        ed.alias_palette = type(
            "P", (), {"refresh_items": lambda self, force=False: refreshed.append(1)})()
        ed._refreshed = refreshed
        g = TileGrid.__new__(TileGrid)
        g.editor = ed
        g.rect = Rect(-10000, -10000, 20000, 20000)
        g.hover_cell = (0, 0)
        g.selection_rect = None
        g.invalidate_bounds_cache = lambda: None
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        return g, ed, layer

    def _tile(self, ttype, variant):
        return {"pos": (0, 0), "ttype": ttype, "variant": variant}

    def test_creates_and_registers(self, monkeypatch, tmp_path):
        import json as _json

        g, ed, layer = self._grid(monkeypatch, tmp_path)
        layer.set_tile((1, 1), self._tile(0, 5))
        layer.set_tile((2, 1), self._tile(0, 6))
        g.selection_rect = (1, 1, 2, 1)
        assert g.create_alias_from_selection() is True
        saved = _json.loads((tmp_path / "aliases" / "stone.alias.json").read_text())
        assert saved["tileset"].endswith("stone.png")
        assert saved["aliases"][0]["cells"] == [[0, 0, 5], [1, 0, 6]]
        assert ed.registered == ["stone"]
        assert ed._refreshed == [1]
        assert any("Alias" in m for m in ed.notifications.good)

    def test_multi_tileset_rejected(self, monkeypatch, tmp_path):
        g, ed, layer = self._grid(monkeypatch, tmp_path)
        layer.set_tile((0, 0), self._tile(0, 1))
        layer.set_tile((1, 0), self._tile(1, 2))
        g.selection_rect = (0, 0, 1, 0)
        assert g.create_alias_from_selection() is False
        assert any("multiple tilesets" in m for m in ed.notifications.notes)
        assert not (tmp_path / "aliases").exists()

    def test_empty_selection_rejected(self, monkeypatch, tmp_path):
        g, ed, layer = self._grid(monkeypatch, tmp_path)
        assert g.create_alias_from_selection() is False
        g.selection_rect = (4, 4, 5, 5)
        assert g.create_alias_from_selection() is False
        assert any("empty" in m.lower() for m in ed.notifications.notes)

    def test_name_unique_within_file(self, monkeypatch, tmp_path):
        import json as _json

        g, ed, layer = self._grid(monkeypatch, tmp_path)
        layer.set_tile((0, 0), self._tile(0, 1))
        g.selection_rect = (0, 0, 0, 0)
        assert g.create_alias_from_selection() is True
        assert g.create_alias_from_selection() is True
        saved = _json.loads((tmp_path / "aliases" / "stone.alias.json").read_text())
        assert [a["name"] for a in saved["aliases"]] == ["Alias 1", "Alias 2"]


class TestThemeAndDraw:
    def test_all_colors_attrs_exist(self):
        import re

        files = [
            Path("src/widgets/ui/alias_palette.py"),
            Path("src/plugins/tile_alias/editor.py"),
        ]
        names = set()
        for f in files:
            names |= set(re.findall(r"COLORS\.([A-Za-z_0-9]+)",
                                    (Path(__file__).parent.parent / f).read_text()))
        assert names, "no COLORS uses found (guard broken)"
        missing = [n for n in sorted(names) if not hasattr(theme_module.COLORS, n)]
        assert missing == [], f"unknown theme colors: {missing}"

    def test_palette_draw_no_exception(self, tmp_path):
        ad = tmp_path / "aliases"
        ad.mkdir()
        write_alias_file(ad / "stone.alias.json", aliases=[("Wall", 5)])
        pal, _ = make_palette(ad)
        pal.draw(pygame.display.get_surface())

    def test_palette_draw_empty_no_exception(self, tmp_path):
        pal, _ = make_palette(tmp_path / "aliases")
        pal.draw(pygame.display.get_surface())


class TestScopeFeedback:
    def _palette(self, tmp_path, scopes):
        ad = tmp_path / "aliases"
        ad.mkdir(exist_ok=True)
        write_alias_file(ad / "stone.alias.json", aliases=[("Wall", 5)])
        write_alias_file(ad / "grass.alias.json", aliases=[("Blade", 1)])
        pal, ed = make_palette(ad)
        ed.config = {"aliases_path": "aliases", "alias_scopes": scopes}
        pal.reload_scope_list()
        return pal, ed

    def test_single_scope_click_explains(self, tmp_path):
        pal, ed = self._palette(tmp_path, {"Env": ["stone"]})
        assert pal.scope_name == "Env"
        pal.cycle_scope()
        assert pal.scope_name == "Env"
        assert any("Only one scope" in m for m in ed.notifications.notes)

    def test_multi_scope_cycles_with_feedback(self, tmp_path):
        pal, ed = self._palette(tmp_path, {"Env": ["stone"], "Out": ["grass"]})
        assert pal.scope_name == "Env"
        pal.cycle_scope()
        assert pal.scope_name == "Out"
        assert [a.name for _, _, a in pal.filtered] == ["Blade"]
        assert any("Scope: Out" in m for m in ed.notifications.good)

    def test_no_files_reported(self, tmp_path):
        pal, ed = make_palette(tmp_path / "aliases")
        ed.config = {"aliases_path": "aliases", "alias_scopes": {}}
        pal.reload_scope_list()
        pal.cycle_scope()
        assert any("No alias files" in m for m in ed.notifications.notes)


class TestPaletteHelp:
    def test_toggle_draw_and_esc(self, tmp_path, monkeypatch):
        import pygame as pg

        ad = tmp_path / "aliases"
        ad.mkdir()
        write_alias_file(ad / "stone.alias.json", aliases=[("Wall", 5)])
        pal, _ = make_palette(ad)
        assert pal.show_help is False
        pal.toggle_help()
        pal.draw(pg.display.get_surface())
        monkeypatch.setattr(pg.mouse, "get_pos", lambda: (0, 0))
        assert pal.handle_event(pg.event.Event(
            pg.KEYDOWN, {"key": pg.K_ESCAPE})) is True
        assert pal.show_help is False

    def test_buttons_have_tooltips(self, tmp_path):
        pal, _ = make_palette(tmp_path / "aliases")
        for btn in (pal.btn_tileset, pal.btn_alias, pal.btn_scope,
                    pal.btn_composer, pal.btn_help):
            assert getattr(btn, "tooltip_text", ""), btn.text


class TestWheelAndThrottle:
    def test_legacy_buttons_scroll(self, tmp_path, monkeypatch):
        import pygame as pg

        ad = tmp_path / "aliases"
        ad.mkdir()
        write_alias_file(ad / "stone.alias.json",
                         aliases=[(f"A{i}", i) for i in range(12)])
        pal, _ = make_palette(ad)
        grid = pal._grid_rect()
        pos = (grid.x + 10, grid.y + 10)
        monkeypatch.setattr(pg.mouse, "get_pos", lambda: pos)
        assert pal.handle_event(pg.event.Event(
            pg.MOUSEBUTTONDOWN, {"button": 5, "pos": pos})) is True
        assert pal.scroll > 0
        assert pal.handle_event(pg.event.Event(
            pg.MOUSEBUTTONDOWN, {"button": 4, "pos": pos})) is True
        assert pal.scroll == 0

    def test_throttle_skips_rescan(self, tmp_path, monkeypatch):
        import json as _json

        import pygame as pg

        ad = tmp_path / "aliases"
        ad.mkdir()
        write_alias_file(ad / "stone.alias.json", aliases=[("A", 1)])
        pal, _ = make_palette(ad)
        pal.refresh_items(force=True)
        base = pg.time.get_ticks()
        (ad / "stone.alias.json").write_text(_json.dumps({
            "version": 1, "tileset": "t.png",
            "aliases": [{"name": "A", "w": 1, "h": 1, "cells": [[0, 0, 1]]},
                        {"name": "B", "w": 1, "h": 1, "cells": [[0, 0, 2]]}]}))
        monkeypatch.setattr(pg.time, "get_ticks", lambda: base + 100)
        pal.refresh_items()
        assert [a.name for _, _, a in pal.filtered] == ["A"]
        monkeypatch.setattr(pg.time, "get_ticks", lambda: base + 600)
        pal.refresh_items()
        assert [a.name for _, _, a in pal.filtered] == ["A", "B"]
