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

        d = TileCollisionData(tile_id=7)
        d2 = TileCollisionData.from_dict(d.to_dict())
        assert (d2.tile_id, d2.shapes) == (7, [])

    def test_no_flag_keys_in_json(self):
        from plugins.tileset_collision.models import TileCollisionData

        d = TileCollisionData(tile_id=7)
        assert "flip_x" not in d.to_dict()
        assert "flip_y" not in d.to_dict()

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


class TestMirrorAction:
    def _editor(self):
        from plugins.tileset_collision import editor as ed_mod
        from plugins.tileset_collision.models import TilesetCollisionLibrary

        ed = ed_mod.TilesetCollisionEditor.__new__(ed_mod.TilesetCollisionEditor)
        ed._selected_tiles = {5}
        ed._user_cleared_tiles = set()
        ed._tile_size = (32, 32)
        ed.library = TilesetCollisionLibrary(tileset_name="t", tile_size=(32, 32))
        ed.toasts = []
        ed._show_toast = lambda msg, duration=2.5: ed.toasts.append(msg)
        ed.consumer = None
        ed._get_tile_surface = lambda tid: pygame.Surface((32, 32))
        ed.painter = type("P", (), {
            "set_polygons": lambda self, polys, flags=None: setattr(
                self, "polys", [list(p) for p in polys]),
            "get_polygons": lambda self: [list(p) for p in getattr(self, "polys", [])],
            "get_one_way_flags": lambda self: [False] * len(getattr(self, "polys", [])),
        })()
        return ed

    def _tile_with(self, ed, verts):
        from plugins.tileset_collision.models import CollisionPolygon, TileCollisionData

        ed.library.tiles[5] = TileCollisionData(
            tile_id=5, shapes=[CollisionPolygon(vertices=list(verts))])

    def test_mirror_x_rewrites_vertices(self):
        ed = self._editor()
        self._tile_with(ed, [(4.0, 4.0), (28.0, 4.0), (28.0, 28.0)])
        ed._mirror_selection("x")
        got = ed.library.tiles[5].shapes[0].vertices
        assert got == [(28.0, 4.0), (4.0, 4.0), (4.0, 28.0)]
        assert any("Mirrored X" in m for m in ed.toasts)

    def test_double_mirror_restores(self):
        ed = self._editor()
        self._tile_with(ed, [(4.0, 4.0), (28.0, 4.0), (28.0, 28.0)])
        ed._mirror_selection("x")
        ed._mirror_selection("x")
        got = ed.library.tiles[5].shapes[0].vertices
        for (gx, gy), (ex, ey) in zip(got, [(4.0, 4.0), (28.0, 4.0), (28.0, 28.0)]):
            assert abs(gx - ex) < 1e-9 and abs(gy - ey) < 1e-9

    def test_mirror_y(self):
        ed = self._editor()
        self._tile_with(ed, [(4.0, 4.0), (28.0, 4.0), (28.0, 28.0)])
        ed._mirror_selection("y")
        got = ed.library.tiles[5].shapes[0].vertices
        assert got == [(4.0, 28.0), (28.0, 28.0), (28.0, 4.0)]

    def test_mirror_no_shapes_notifies(self):
        ed = self._editor()
        ed._mirror_selection("x")
        assert any("Nothing to mirror" in m for m in ed.toasts)
        assert 5 not in ed.library.tiles

    def test_mirror_no_selection_notifies(self):
        ed = self._editor()
        ed._selected_tiles = set()
        ed._mirror_selection("x")
        assert any("Select a tile" in m for m in ed.toasts)
