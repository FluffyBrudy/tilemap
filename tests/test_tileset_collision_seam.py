"""Seam-exact painting tests (tileset collision).

Proves the defects behind sub-pixel seam lips (the physics runner needs
shared-border vertices to coincide within 0.01px):

F1  Shift axis-lock must survive snapping (click-place AND vertex-drag).
F2  Neighbor border-crossing points must be snap targets (sloped joints).
F3  Saved vertices rounded to 3 decimals; display transform must round,
    not truncate.
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


def _click(painter, monkeypatch, tile_x, tile_y):
    """Drive a left-click at the screen pos of a tile coord."""
    sx = int(0 + 0.0 + tile_x * painter.zoom)
    sy = int(0 + 0.0 + tile_y * painter.zoom)
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (sx, sy))
    ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (sx, sy)})
    painter.handle_event(ev)
    return (sx, sy)


class TestShiftLockSurvivesSnap:
    def test_click_place_horizontal_lock(self, monkeypatch):
        """Shift-drawn horizontal deck segment must keep start.y exactly,
        even with a slanted neighbor edge inside the snap threshold."""
        painter = _make_painter()
        painter.edge_draw_mode = True
        painter._shift_held = True
        painter.current_polygon = [(10.0, 20.0)]
        # slanted ghost edge; projection of the click is (19, 21)
        painter.set_neighbor_polygons({(-1, 0): [[(14.0, 26.0), (26.0, 14.0)]]}, {})
        _click(painter, monkeypatch, 20.0, 22.0)  # dx=10 > dy=2 -> lock y
        assert len(painter.current_polygon) == 2
        placed = painter.current_polygon[1]
        assert placed[0] == pytest.approx(19.0)  # snap still applies on x
        assert placed[1] == pytest.approx(20.0)  # axis lock holds on y

    def test_vertex_drag_horizontal_lock(self, monkeypatch):
        """Shift-dragging a vertex horizontally must keep its y exactly."""
        painter = _make_painter()
        painter.set_polygons([[(10.0, 20.0), (20.0, 20.0), (20.0, 30.0), (10.0, 30.0)]])
        painter.selected_polygon_idx = 0
        painter.selected_vertex_idx = (0, 0)
        painter._dragging_vertex = True
        painter._drag_anchor = (10.0, 20.0)
        painter.edge_draw_mode = True
        painter._shift_held = True
        painter.set_neighbor_polygons({(-1, 0): [[(14.0, 26.0), (26.0, 14.0)]]}, {})
        sx = int(20.0 * painter.zoom)
        sy = int(22.0 * painter.zoom)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (sx, sy))
        ev = pygame.event.Event(pygame.MOUSEMOTION, {"pos": (sx, sy)})
        painter.handle_event(ev)
        moved = painter.polygons[0][0]
        assert moved[0] == pytest.approx(19.0)
        assert moved[1] == pytest.approx(20.0)


class TestBorderCrossingSnap:
    def test_snap_lands_exactly_on_shared_border(self):
        """Clicking near a neighbor edge's border crossing must return the
        crossing itself (x exactly on the border), not a mid-edge float."""
        painter = _make_painter()
        # edge crosses x=0 at y=10.4; vertices far from the click
        painter.set_neighbor_polygons({(-1, 0): [[(-8.0, 4.0), (12.0, 20.0)]]}, {})
        mouse = (int(0.5 * painter.zoom), int(10.5 * painter.zoom))
        snapped = painter._snap_point((0.5, 10.5), mouse)
        assert snapped is not None
        assert snapped[0] == pytest.approx(0.0, abs=1e-9)
        assert snapped[1] == pytest.approx(10.4, abs=1e-9)

    def test_mid_edge_click_not_hijacked(self):
        """A click on the edge but well outside the marker dot keeps the
        edge projection (crossings must not steal nearby edge work)."""
        painter = _make_painter()
        painter.set_neighbor_polygons({(-1, 0): [[(-8.0, 4.0), (12.0, 20.0)]]}, {})
        mouse = (int(3.0 * painter.zoom), int(12.5 * painter.zoom))
        snapped = painter._snap_point((3.0, 12.5), mouse)
        assert snapped is not None
        assert snapped[0] == pytest.approx(2.8536585, abs=1e-6)
        assert snapped != pytest.approx((0.0, 10.4))


class TestSaveAndDisplayHonesty:
    def test_vertices_rounded_on_save(self):
        """14-decimal projection floats must not reach the JSON."""
        from plugins.tileset_collision.models import CollisionPolygon

        poly = CollisionPolygon(
            vertices=[
                (128.0, 76.39803629890734),
                (0.0, 76.18604775816948),
                (0.0, 100.92687726555285),
            ]
        )
        assert poly.to_dict()["vertices"] == [
            (128.0, 76.398),
            (0.0, 76.186),
            (0.0, 100.927),
        ]

    def test_tile_to_screen_rounds(self):
        """Display transform must round, not truncate (else the drawn
        vertex visibly lies about the stored value)."""
        painter = _make_painter()
        assert painter._tile_to_screen((10.9, 10.9)) == (22, 22)
