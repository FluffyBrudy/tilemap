"""Tests for collision body-drag and per-tile flip flags."""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest
from pygame import Rect

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def _reinit_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield


def make_painter():
    from plugins.tileset_collision.collision_painter import CollisionPainter

    p = CollisionPainter(Rect(0, 0, 200, 200),
                         pygame.Surface((32, 32)), (32, 32))
    p.zoom = 1.0
    p.offset_x = 0.0
    p.offset_y = 0.0
    return p


TRI = [(4.0, 4.0), (28.0, 4.0), (28.0, 28.0)]


def down(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                              {"button": 1, "pos": pos})


def up(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP,
                              {"button": 1, "pos": pos})


class TestBodyDrag:
    def test_interior_grab_moves_rigidly(self, monkeypatch):
        p = make_painter()
        p.polygons = [list(TRI)]
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (20, 8))
        assert p.handle_event(down((20, 8))) is True
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (24, 12))
        assert p.handle_event(
            pygame.event.Event(pygame.MOUSEMOTION,
                               {"pos": (24, 12), "rel": (4, 4),
                                "buttons": (1, 0, 0)})) is True
        moved = p.polygons[0]
        assert moved == [(8.0, 8.0), (32.0, 8.0), (32.0, 32.0)]
        p.handle_event(up((24, 12)))
        assert p._body_drag_idx is None

    def test_clamped_to_tile(self, monkeypatch):
        p = make_painter()
        p.polygons = [list(TRI)]
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (20, 8))
        p.handle_event(down((20, 8)))
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (190, 190))
        p.handle_event(
            pygame.event.Event(pygame.MOUSEMOTION,
                               {"pos": (190, 190), "rel": (0, 0),
                                "buttons": (1, 0, 0)}))
        for x, y in p.polygons[0]:
            assert 0 <= x <= 32 and 0 <= y <= 32
        # shape preserved: same relative offsets as the original
        moved = p.polygons[0]
        assert (moved[1][0] - moved[0][0], moved[1][1] - moved[0][1]) == (24.0, 0.0)

    def test_click_without_motion_is_select_only(self, monkeypatch):
        p = make_painter()
        p.polygons = [list(TRI)]
        saved = []
        p.on_polygon_modified = lambda idx: saved.append(idx)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (20, 8))
        p.handle_event(down((20, 8)))
        p.handle_event(up((20, 8)))
        assert p.polygons[0] == TRI
        assert saved == []
        assert p.selected_polygon_idx == 0

    def test_escape_restores(self, monkeypatch):
        p = make_painter()
        p.polygons = [list(TRI)]
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (20, 8))
        p.handle_event(down((20, 8)))
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (24, 12))
        p.handle_event(
            pygame.event.Event(pygame.MOUSEMOTION,
                               {"pos": (24, 12), "rel": (4, 4),
                                "buttons": (1, 0, 0)}))
        assert p.polygons[0] != TRI
        p.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}))
        assert p.polygons[0] == TRI
        assert p._body_drag_idx is None

    def test_vertex_grab_still_wins(self, monkeypatch):
        p = make_painter()
        p.polygons = [list(TRI)]
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (4, 4))
        assert p.handle_event(down((4, 4))) is True
        assert p.selected_vertex_idx == (0, 0)
        assert p._body_drag_idx is None


class TestFlipModel:
    def test_round_trip(self):
        from plugins.tileset_collision.models import TileCollisionData

        d = TileCollisionData(tile_id=7, flip_x=True)
        d2 = TileCollisionData.from_dict(d.to_dict())
        assert (d2.flip_x, d2.flip_y) == (True, False)

    def test_legacy_dict_defaults_off(self):
        from plugins.tileset_collision.models import TileCollisionData

        d = TileCollisionData.from_dict({"tile_id": 3, "shapes": []})
        assert (d.flip_x, d.flip_y) == (False, False)

    def test_mirror_math_and_identity(self):
        from plugins.tileset_collision.models import TileCollisionData as T

        def f(p, fx, fy):
            return T.apply_flip(p, (32, 32), fx, fy)

        assert f((28, 4), True, False) == (4, 4)
        assert f((28, 28), False, True) == (28, 4)
        p = (28.0, 30.0)
        assert f(f(p, True, False), True, False) == p
        assert f(f(p, False, True), False, True) == p

    def test_user_triangle_mirrors_sides(self):
        from plugins.tileset_collision.models import TileCollisionData as T

        tri = [(4.0, 4.0), (28.0, 4.0), (28.0, 28.0)]
        mirrored = [T.apply_flip(p, (32, 32), True, False) for p in tri]
        # right angle moves from x=28 (right) to x=4 (left)
        assert mirrored[1] == (4.0, 4.0)
        assert mirrored[2] == (4.0, 28.0)


class TestFlipEditorPaths:
    def _editor(self):
        from plugins.tileset_collision import editor as ed_mod
        from plugins.tileset_collision.models import TilesetCollisionLibrary

        ed = ed_mod.TilesetCollisionEditor.__new__(ed_mod.TilesetCollisionEditor)
        ed._selected_tiles = {5}
        ed._user_cleared_tiles = set()
        ed.library = TilesetCollisionLibrary(tileset_name="t", tile_size=(32, 32))
        ed.painter = type("P", (), {"flip_x": False, "flip_y": False})()
        return ed

    def test_set_flip_creates_and_applies(self):
        ed = self._editor()
        ed._set_flip("x", True)
        assert ed.library.tiles[5].flip_x is True
        assert ed.library.tiles[5].flip_y is False
        assert ed.painter.flip_x is True

    def test_selection_flags_default_off(self):
        ed = self._editor()
        assert ed._selection_flip_flags() == (False, False)
        ed._selected_tiles = set()
        assert ed._selection_flip_flags() == (False, False)

    def test_save_carries_flags(self):
        from plugins.tileset_collision.models import TileCollisionData

        ed = self._editor()
        ed.library.tiles[5] = TileCollisionData(tile_id=5, flip_x=True)
        ed.painter = type("P", (), {
            "get_polygons": lambda self: [[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]],
            "get_one_way_flags": lambda self: [False],
        })()
        ed.consumer = None
        ed._save_tile_collision_for_selection()
        assert ed.library.tiles[5].flip_x is True
