"""TileGrid float-shimmer regression tests.

Covers:
- adjacent cell rects butt exactly (no 1px gaps/overlaps) across a
  zoom x pan sweep, and cell edges coincide with grid lines.
- picking math floors (correct cell left/above the origin).
- Godot-style zoom ladder lands on exact stops; free zoom path kept.
- dense-grid step skips lines when cells shrink below ~4px.
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


class FakeTilemap:
    tile_size = (32, 32)
    render_scale = 1.0
    map_size = (20, 15)
    offset = (0, 0)
    initialized = True


class FakeEditor:
    def __init__(self):
        self.tilemap = FakeTilemap()


def make_grid():
    from widgets.tile_grid import TileGrid

    return TileGrid(FakeEditor(), Rect(0, 0, 800, 600))


ZOOMS = [0.1, 0.33, 0.5, 0.75, 1.0, 1.12, 1.25, 1.37, 1.5, 2.0, 3.0]
PANS = [(0.0, 0.0), (13.7, -7.3), (-40.2, 25.9), (0.5, 0.5)]


class TestCellTiling:
    @pytest.mark.parametrize("zoom", ZOOMS)
    @pytest.mark.parametrize("pan", PANS)
    def test_cells_butt_exactly(self, zoom, pan):
        grid = make_grid()
        grid.zoom_level = zoom
        grid.scroll_x, grid.scroll_y = pan
        for col in range(9):
            left = grid.cell_screen_rect(col, 0)
            right = grid.cell_screen_rect(col + 1, 0)
            assert left.right == right.x
        for row in range(9):
            top = grid.cell_screen_rect(0, row)
            bottom = grid.cell_screen_rect(0, row + 1)
            assert top.bottom == bottom.y

    @pytest.mark.parametrize("zoom", ZOOMS)
    @pytest.mark.parametrize("pan", PANS)
    def test_cell_edges_match_grid_lines(self, zoom, pan):
        grid = make_grid()
        grid.zoom_level = zoom
        grid.scroll_x, grid.scroll_y = pan
        for col in range(10):
            assert grid.cell_screen_rect(col, 0).x == grid.grid_line_x(col)
            assert grid.cell_screen_rect(col, 0).right == grid.grid_line_x(col + 1)
        for row in range(10):
            assert grid.cell_screen_rect(0, row).y == grid.grid_line_y(row)
            assert grid.cell_screen_rect(0, row).bottom == grid.grid_line_y(row + 1)

    def test_cell_size_matches_rounded_zoom(self):
        grid = make_grid()
        grid.zoom_level = 1.37
        rect = grid.cell_screen_rect(0, 0)
        assert (rect.w, rect.h) == (round(32 * 1.37), round(32 * 1.37))


class TestPickingMath:
    def test_screen_to_world_floors_negatives(self):
        grid = make_grid()
        grid.scroll_x = -5.5
        grid.scroll_y = -5.5
        assert grid.screen_to_world((0, 0)) == (-6, -6)

    def test_grid_pos_left_of_origin(self):
        grid = make_grid()
        grid.scroll_x = -5.5
        grid.scroll_y = -5.5
        assert grid.get_grid_pos((0, 0)) == (-1, -1)

    def test_grid_pos_round_trip(self):
        grid = make_grid()
        grid.zoom_level = 1.37
        grid.scroll_x, grid.scroll_y = (13.7, -7.3)
        for col, row in [(0, 0), (3, 5), (10, 2)]:
            rect = grid.cell_screen_rect(col, row)
            assert grid.get_grid_pos(rect.center) == (col, row)


class TestZoomLadder:
    def test_octave_lands_exact(self):
        grid = make_grid()
        grid.zoom_level = 1.0
        grid.zoom_by_steps(12, center=(400, 300))
        assert grid.zoom_level == pytest.approx(2.0)
        grid.zoom_by_steps(-12, center=(400, 300))
        assert grid.zoom_level == pytest.approx(1.0)

    def test_repeated_single_steps_reach_powers_of_two(self):
        grid = make_grid()
        grid.zoom_level = 1.0
        for _ in range(12):
            grid.zoom_by_steps(1, center=(400, 300))
        assert grid.zoom_level == pytest.approx(2.0)

    def test_free_zoom_path_kept(self):
        grid = make_grid()
        grid.zoom_level = 1.0
        grid.zoom_by(0.1, center=(400, 300))
        assert grid.zoom_level == pytest.approx(1.1)

    def test_ladder_clamps_to_bounds(self):
        grid = make_grid()
        grid.zoom_level = 1.0
        grid.zoom_by_steps(1000, center=(400, 300))
        assert grid.zoom_level == grid.max_zoom
        grid.zoom_by_steps(-1000, center=(400, 300))
        assert grid.zoom_level == grid.min_zoom

    def test_zoom_anchors_cursor(self):
        grid = make_grid()
        grid.zoom_level = 1.0
        before = grid.screen_to_world((400, 300))
        grid.zoom_by_steps(6, center=(400, 300))
        assert grid.screen_to_world((400, 300)) == before


class TestWorldRectHelpers:
    def test_cell_rect_delegates_to_world_rect(self):
        grid = make_grid()
        grid.zoom_level = 1.37
        grid.scroll_x, grid.scroll_y = (13.7, -7.3)
        for col, row in [(0, 0), (3, 5), (10, 2)]:
            eff_w, eff_h = (32.0, 32.0)
            assert grid.cell_screen_rect(col, row) == grid.world_rect_to_screen(
                col * eff_w, row * eff_h, eff_w, eff_h
            )

    def test_range_rect_spans_cells_exactly(self):
        grid = make_grid()
        grid.zoom_level = 1.37
        grid.scroll_x, grid.scroll_y = (13.7, -7.3)
        spanned = grid.cell_range_rect(2, 3, 5, 7)
        first = grid.cell_screen_rect(2, 3)
        last = grid.cell_screen_rect(5, 7)
        assert (spanned.x, spanned.y) == (first.x, first.y)
        assert (spanned.right, spanned.bottom) == (last.right, last.bottom)

    def test_image_rect_uses_world_rule(self):
        import types

        from widgets.tile_grid import TileGrid

        ed = types.SimpleNamespace(
            tilemap=types.SimpleNamespace(tile_size=(16, 16), render_scale=2.0)
        )
        grid = TileGrid(ed, Rect(0, 0, 800, 600))
        grid.zoom_level = 1.5
        rect = grid._image_screen_rect({"x": 10, "y": 20, "w": 30, "h": 40})
        # world px after render_scale: (20, 40, 60, 80)
        assert rect == grid.world_rect_to_screen(20, 40, 60, 80)
        assert (rect.w, rect.h) == (round(60 * 1.5), round(80 * 1.5))


class TestScaleCache:
    def test_hit_returns_same_surface(self):
        grid = make_grid()
        base = pygame.Surface((64, 64), pygame.SRCALPHA)
        base.fill((10, 20, 30, 255))
        src = Rect(0, 0, 32, 32)
        first = grid._scaled_tile(base, src, (48, 48))
        second = grid._scaled_tile(base, src, (48, 48))
        assert first is second
        assert (first.get_width(), first.get_height()) == (48, 48)

    def test_size_and_alpha_are_keyed(self):
        grid = make_grid()
        base = pygame.Surface((64, 64), pygame.SRCALPHA)
        base.fill((10, 20, 30, 255))
        src = Rect(0, 0, 32, 32)
        plain = grid._scaled_tile(base, src, (48, 48))
        other_size = grid._scaled_tile(base, src, (24, 24))
        ghost = grid._scaled_tile(base, src, (48, 48), alpha=128)
        assert plain is not other_size
        assert plain is not ghost
        assert ghost.get_alpha() == 128

    def test_cache_bounded(self):
        grid = make_grid()
        base = pygame.Surface((64, 64), pygame.SRCALPHA)
        base.fill((10, 20, 30, 255))
        for i in range(grid.TILE_SCALE_CACHE_MAX + 50):
            grid._scaled_tile(base, Rect(0, 0, 32, 32), (40 + i, 40))
        assert len(grid._tile_scale_cache) <= grid.TILE_SCALE_CACHE_MAX

    def test_invalidate_clears_cache(self):
        grid = make_grid()
        base = pygame.Surface((64, 64), pygame.SRCALPHA)
        grid._scaled_tile(base, Rect(0, 0, 32, 32), (48, 48))
        assert len(grid._tile_scale_cache) == 1
        grid.invalidate_image_cache()
        assert grid._tile_scale_cache == {}


class TestRenderMapSmoke:
    def _make_render_grid(self):
        import types

        sheet = pygame.Surface((64, 64), pygame.SRCALPHA)
        sheet.fill((90, 120, 160, 255))

        class FakeLayer:
            layer_type = "tile"
            opacity = 1.0

            def get_tile(self, pos):
                x, y = pos
                if 0 <= x < 4 and 0 <= y < 4:
                    return {"ttype": 0, "variant": 0}
                return None

        tilemap = types.SimpleNamespace(
            tile_size=(32, 32),
            render_scale=1.0,
            map_size=(20, 15),
            offset=(0, 0),
            initialized=True,
            layer_manager=types.SimpleNamespace(
                get_rendered_layers=lambda: [FakeLayer()]
            ),
        )
        ed = types.SimpleNamespace(
            tilemap=tilemap,
            tileset_widget=types.SimpleNamespace(
                tileset_map={
                    0: types.SimpleNamespace(surface=sheet, animation=None)
                }
            ),
        )
        from widgets.tile_grid import TileGrid

        return TileGrid(ed, Rect(0, 0, 800, 600))

    @pytest.mark.parametrize("zoom", [0.5, 1.0, 1.37, 2.0])
    def test_render_map_tiles_no_crash(self, zoom):
        grid = self._make_render_grid()
        grid.zoom_level = zoom
        surface = pygame.Surface((800, 600))
        grid.render_map(surface)  # must not raise

    def test_render_map_tiles_land_on_snapped_rects(self):
        grid = self._make_render_grid()
        grid.zoom_level = 1.37
        surface = pygame.Surface((800, 600))
        surface.fill((0, 0, 0, 255))
        grid.render_map(surface)
        # tile (0,0) area must contain sheet pixels, not background
        rect = grid.cell_screen_rect(0, 0)
        assert rect.w > 0 and rect.h > 0
        sample = surface.get_at(rect.center)
        assert tuple(sample) != (0, 0, 0, 255)


class TestDenseGrid:
    def test_step_one_at_normal_zoom(self):
        grid = make_grid()
        grid.zoom_level = 1.0
        assert grid.grid_step() == 1

    def test_step_grows_when_cells_shrink(self):
        grid = make_grid()
        grid.zoom_level = 0.1  # 3.2px cells
        assert grid.grid_step() == 2
        grid.zoom_level = 0.05  # 1.6px cells (below min, set directly)
        assert grid.grid_step() == 3

    def test_draw_grid_no_crash_at_extremes(self):
        grid = make_grid()
        screen = pygame.Surface((800, 600))
        for zoom in (0.1, 1.37, 5.0):
            grid.zoom_level = zoom
            grid._draw_grid(screen)  # must not raise
