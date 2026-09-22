"""Neighbor trace / snap / markers tests (tileset collision).

Covers: editor offset math (shared borders coincide, sheet edges and
unpainted tiles contribute nothing), painter vertex/edge snap with
precedence, corner-reach filtering, border-crossing markers (slope
case), toggle gating, and trace draw without errors.
"""

import os


import sys
from pathlib import Path

import pygame
import pytest
from pygame import Rect


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


TW, TH = 32, 32


def _make_painter():
    from plugins.tileset_collision.collision_painter import CollisionPainter

    surf = pygame.Surface((TW, TH), pygame.SRCALPHA)
    surf.fill((50, 50, 50, 255))
    painter = CollisionPainter(Rect(0, 0, 400, 400), surf, (TW, TH))
    painter.zoom = 2.0
    painter.offset_x = 0.0
    painter.offset_y = 0.0
    return painter


def _screen(painter, x, y):
    sx, sy = painter._tile_to_screen((x, y))
    return (sx, sy)


class TestSnap:
    def test_vertex_snap(self):
        painter = _make_painter()
        painter.set_neighbor_polygons({(-1, 0): [[(32.0, 10.0), (32.0, 20.0), (20.0, 20.0)]]}, {})
        mouse = _screen(painter, 31, 11)
        assert painter._snap_to_neighbors((30.0, 12.0), mouse) == (32.0, 10.0)

    def test_threshold_miss(self):
        painter = _make_painter()
        painter.set_neighbor_polygons({(-1, 0): [[(32.0, 10.0), (32.0, 20.0), (20.0, 20.0)]]}, {})
        mouse = _screen(painter, 0, 0)
        assert painter._snap_to_neighbors((1.0, 1.0), mouse) is None

    def test_edge_projection(self):
        painter = _make_painter()
        # vertical neighbor edge at local x=32 spanning y 0..32
        painter.set_neighbor_polygons({(-1, 0): [[(32.0, 0.0), (32.0, 32.0)]]}, {})
        mouse = _screen(painter, 30, 15)
        snapped = painter._snap_to_neighbors((29.0, 15.0), mouse)
        assert snapped is not None
        assert snapped[0] == pytest.approx(32.0)
        assert snapped[1] == pytest.approx(15.0)

    def test_vertex_wins_ties(self):
        painter = _make_painter()
        painter.set_neighbor_polygons({(-1, 0): [[(32.0, 10.0), (32.0, 20.0)]]}, {})
        # mouse exactly on the vertex: vertex and edge both distance 0
        mouse = _screen(painter, 32, 10)
        assert painter._snap_to_neighbors((32.0, 10.0), mouse) == (32.0, 10.0)

    def test_disabled_flag(self):
        painter = _make_painter()
        painter.set_neighbor_polygons({(-1, 0): [[(32.0, 10.0)]]}, {})
        painter.snap_to_neighbors = False
        mouse = _screen(painter, 31, 11)
        assert painter._snap_to_neighbors((31.0, 11.0), mouse) is None
        # falls back to grid behavior (off by default -> identity)
        assert painter._snap_point((31.0, 11.0), mouse) == (31.0, 11.0)

    def test_corner_reach(self):
        painter = _make_painter()
        # diagonal tile's vertex 2px from the shared (0,0) corner: in reach
        painter.set_neighbor_polygons({}, {(-1, -1): [[(-2.0, -2.0), (-2.0, 8.0)]]})
        mouse = _screen(painter, -1, -1)
        assert painter._snap_to_neighbors((-1.0, -1.0), mouse) == (-2.0, -2.0)

    def test_corner_out_of_reach_ignored(self):
        painter = _make_painter()
        # 20px away at zoom 2 = 40 screen px, past the 10px threshold
        painter.set_neighbor_polygons({}, {(-1, -1): [[(-20.0, -20.0)]]})
        mouse = _screen(painter, -19, -19)
        assert painter._snap_to_neighbors((-19.0, -19.0), mouse) is None


class TestBorderCrossings:
    def test_slope_crossing(self):
        painter = _make_painter()
        # neighbor edge (-8,4)->(4,12) crosses x=0 at y=4+8*2/3
        crossings = painter._segment_border_crossings((-8.0, 4.0), (4.0, 12.0))
        assert len(crossings) == 1
        assert crossings[0][0] == pytest.approx(0.0)
        assert crossings[0][1] == pytest.approx(28.0 / 3.0)

    def test_no_crossing_inside(self):
        painter = _make_painter()
        assert painter._segment_border_crossings((4.0, 4.0), (10.0, 10.0)) == []

    def test_draw_neighbors_no_crash(self):
        painter = _make_painter()
        painter.set_neighbor_polygons(
            {(-1, 0): [[(32.0, 4.0), (20.0, 12.0), (32.0, 20.0)]],
             (0, 1): [[(4.0, 32.0), (12.0, 20.0)]]},
            {(-1, -1): [[(-2.0, -2.0)]]},
        )
        screen = pygame.Surface((400, 400))
        painter._draw_neighbors(screen)  # must not raise

    def test_hidden_when_toggled_off(self, monkeypatch):
        painter = _make_painter()
        painter.set_neighbor_polygons({(-1, 0): [[(32.0, 10.0)]]}, {})
        painter.show_neighbors = False
        drawn = []
        monkeypatch.setattr(pygame.draw, "circle",
                            lambda *a, **k: drawn.append(a) or None)
        screen = pygame.Surface((400, 400))
        painter._draw_neighbors(screen)
        assert drawn == []


def _make_editor():
    from plugins.tileset_collision.editor import TilesetCollisionEditor
    from plugins.tileset_collision.models import CollisionPolygon, TileCollisionData

    sheet = pygame.Surface((96, 64), pygame.SRCALPHA)  # 3x2 tiles of 32
    sheet.fill((60, 60, 60, 255))
    ed = TilesetCollisionEditor(Rect(0, 0, 1200, 800), sheet, (32, 32))
    # tile 3 (col 0, row 1): slope edge touching its right border at y=12
    ed.library.tiles[3] = TileCollisionData(
        tile_id=3,
        shapes=[CollisionPolygon(vertices=[(20.0, 4.0), (32.0, 12.0), (20.0, 20.0)])],
    )
    return ed


class TestEditorSupply:
    def test_shared_border_coincides(self):
        ed = _make_editor()
        # tile 4 (col 1, row 1) opens with tile 3 as its LEFT neighbor:
        # neighbor-local (32, 12) lands on local (0, 12), the shared edge
        ed._selected_tiles = {4}
        ed._load_tile_collision_for_selection()
        assert (-1, 0) in ed.painter.neighbor_polys
        poly = ed.painter.neighbor_polys[(-1, 0)][0]
        assert (-12.0, 4.0) in poly  # 20 - 32
        assert (0.0, 12.0) in poly  # 32 - 32, on the shared border
        # the touching endpoint is reported as the connecting point
        crossings = ed.painter._segment_border_crossings((-12.0, 4.0), (0.0, 12.0))
        assert len(crossings) == 1
        assert crossings[0] == pytest.approx((0.0, 12.0))

    def test_sheet_edges_contribute_nothing(self):
        ed = _make_editor()
        ed._selected_tiles = {0}  # top-left corner: no left/up neighbors exist
        ed._load_tile_collision_for_selection()
        assert (-1, 0) not in ed.painter.neighbor_polys
        assert (0, -1) not in ed.painter.neighbor_polys

    def test_unpainted_neighbors_skipped(self):
        ed = _make_editor()
        ed._selected_tiles = {5}  # neighbors unpainted
        ed._load_tile_collision_for_selection()
        assert ed.painter.neighbor_polys == {}
        assert ed.painter.neighbor_corners == {}

    def test_toggles_flip_painter_flags(self, monkeypatch):
        ed = _make_editor()
        ed._layout_widget_panel()
        assert ed.painter.show_neighbors is True
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: ed._chk_trace.rect.center)
        ed._chk_trace.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": ed._chk_trace.rect.center}))
        assert ed.painter.show_neighbors is False
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: ed._chk_nsnap.rect.center)
        ed._chk_nsnap.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": ed._chk_nsnap.rect.center}))
        assert ed.painter.snap_to_neighbors is False
