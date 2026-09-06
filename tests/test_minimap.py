"""Tests for the corner minimap (bake, viewport, navigate, dirty)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest
from pygame import Rect

import widgets.minimap as _minimap_mod

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class _DummyFont:
    def render(self, *args, **kwargs):
        return pygame.Surface((8, 8))


class _DummyFonts:
    def get_small_font(self, *args, **kwargs):
        return _DummyFont()


# The shared font manager caches real Font objects, which die when any
# suite module quits pygame (same reason test_autotile_templates stubs
# FONTS). Logic/draw tests never need real glyphs.
_minimap_mod.FONTS = _DummyFonts()


@pytest.fixture(autouse=True)
def _reinit_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield


class FakeTileset:
    def __init__(self, path="/t/a.png"):
        self.path = path
        self.surface = pygame.Surface((8 * 32, 8 * 32))


class FakeLayer:
    layer_type = "tile"

    def __init__(self, tiles):
        self.tiles = dict(tiles)


class FakeManager:
    def __init__(self, layers):
        self._layers = layers

    def get_rendered_layers(self):
        return list(self._layers)


class FakeGrid:
    def __init__(self):
        self.rect = Rect(0, 40, 800, 560)
        self.scroll_x = 0
        self.scroll_y = 0
        self.zoom_level = 1.0
        self.clamped = 0

    def clamp_scroll(self):
        self.clamped += 1
        self.scroll_x = max(0, self.scroll_x)
        self.scroll_y = max(0, self.scroll_y)


class FakeTilemap:
    initialized = True
    tile_size = (32, 32)
    map_size = (10, 8)
    offset = (0, 0)
    render_scale = 1.0

    def __init__(self, layers):
        self.layer_manager = FakeManager(layers)


def tile(pos, variant=0, ttype=0):
    return {"pos": pos, "ttype": ttype, "variant": variant}


def make_mm(layer_tiles, grid=None):
    from widgets.minimap import MinimapWidget

    layer = FakeLayer(layer_tiles)
    ed = type("E", (), {})()
    ed.tilemap = FakeTilemap([layer])
    ed.tileset_widget = type(
        "W", (), {"tilesets": [FakeTileset()],
                  "tileset_map": {0: FakeTileset()}})()
    ed.tile_grid_widget = grid or FakeGrid()
    mm = MinimapWidget(ed)
    return mm, ed


class TestLayout:
    def test_panel_aspect_and_corner(self):
        mm, _ = make_mm({})
        panel = mm._panel_rect()
        # map 10x8 -> aspect 0.8 -> 200x160 at grid bottom-right
        assert panel.width == 200
        assert panel.height == 160
        assert panel.right == 800 - 10
        assert panel.bottom == 600 - 10

    def test_toggle_rect_inside_panel(self):
        mm, _ = make_mm({})
        panel = mm._panel_rect()
        assert panel.contains(mm._toggle_rect(panel))


class TestBake:
    def test_bake_sets_cache_and_clears_dirty(self):
        mm, _ = make_mm({(0, 0): tile((0, 0)), (9, 7): tile((9, 7))})
        screen = pygame.Surface((800, 600))
        mm.draw(screen)
        assert mm.cache is not None
        assert mm.dirty is False

    def test_unknown_tileset_skipped(self):
        mm, _ = make_mm({(0, 0): tile((0, 0), ttype=5)})
        mm.draw(pygame.Surface((800, 600)))
        assert mm.cache is not None

    def test_empty_map_no_crash(self):
        mm, ed = make_mm({})
        ed.tilemap.initialized = False
        mm.draw(pygame.Surface((800, 600)))
        assert mm.cache is None

    def test_mutation_marks_rebuild(self):
        mm, ed = make_mm({(0, 0): tile((0, 0))})
        mm.draw(pygame.Surface((800, 600)))
        assert mm.dirty is False
        mm.mark_dirty()
        assert mm.dirty is True
        mm.draw(pygame.Surface((800, 600)))
        assert mm.dirty is False

    def test_structural_change_rebuilds(self):
        mm, ed = make_mm({})
        mm.draw(pygame.Surface((800, 600)))
        ed.tilemap.map_size = (12, 8)
        mm.draw(pygame.Surface((800, 600)))
        assert mm.dirty is False
        assert mm.cache is not None


class TestViewport:
    def test_viewport_rect_math(self):
        mm, _ = make_mm({(0, 0): tile((0, 0))})
        mm.draw(pygame.Surface((800, 600)))
        vp = mm._viewport_rect()
        # full map 320x256 baked to 200x160 (scale 0.625);
        # view 800x560 world px -> 500x350 panel px at origin
        assert vp is not None
        assert (vp.x, vp.y) == mm.origin
        assert abs(vp.width - 500) < 2
        assert abs(vp.height - 350) < 2

    def test_viewport_follows_scroll(self):
        mm, ed = make_mm({(0, 0): tile((0, 0))})
        mm.draw(pygame.Surface((800, 600)))
        ed.tile_grid_widget.scroll_x = 64
        vp = mm._viewport_rect()
        assert abs(vp.x - (mm.origin[0] + 64 * mm.scale)) < 1


class TestNavigate:
    def _click(self, mm, pos):
        return mm.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                               {"button": 1, "pos": pos}))

    def test_click_centers_view(self):
        mm, ed = make_mm({(0, 0): tile((0, 0))})
        mm.draw(pygame.Surface((800, 600)))
        panel = mm._panel_rect()
        assert self._click(mm, panel.center) is True
        grid = ed.tile_grid_widget
        # center of map in world px ~= (160, 128); view 800x560 clamps to 0
        assert grid.clamped == 1
        assert grid.scroll_x == 0 and grid.scroll_y == 0

    def test_click_outside_ignored(self):
        mm, _ = make_mm({})
        assert self._click(mm, (5, 5)) is False

    def test_drag_pans_and_releases(self):
        mm, ed = make_mm({(0, 0): tile((0, 0))})
        mm.draw(pygame.Surface((800, 600)))
        panel = mm._panel_rect()
        assert self._click(mm, (panel.x + 10, panel.y + 10)) is True
        move = pygame.event.Event(pygame.MOUSEMOTION,
                                  {"pos": (panel.x + 30, panel.y + 10),
                                   "rel": (20, 0), "buttons": (1, 0, 0)})
        assert mm.handle_event(move) is True
        up = pygame.event.Event(pygame.MOUSEBUTTONUP,
                                {"button": 1, "pos": (panel.x + 30, panel.y + 10)})
        assert mm.handle_event(up) is True
        assert mm.handle_event(up) is False

    def test_collapse_toggle(self):
        mm, _ = make_mm({})
        panel = mm._panel_rect()
        toggle = mm._toggle_rect(panel)
        ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                {"button": 1, "pos": toggle.center})
        assert mm.handle_event(ev) is True
        assert mm.collapsed is True
        screen = pygame.Surface((800, 600))
        mm.draw(screen)  # collapsed: border + toggle only, no crash

    def test_collapsed_ignores_panel_clicks(self):
        mm, _ = make_mm({})
        mm.collapsed = True
        panel = mm._panel_rect()
        ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                {"button": 1, "pos": (panel.x + 50, panel.y + 50)})
        assert mm.handle_event(ev) is False


class TestDirtyHook:
    def test_invalidate_marks_minimap(self):
        from widgets.tile_grid import TileGrid

        mm, ed = make_mm({})
        g = TileGrid.__new__(TileGrid)
        g.editor = ed
        ed.minimap = mm
        g._cached_bounds = (0, 0, 1, 1)
        mm.dirty = False
        g.invalidate_bounds_cache()
        assert g._cached_bounds is None
        assert mm.dirty is True
