"""Grid alignment + canvas limit-border regression tests (sprite editor).

Covers:
- sheet right/bottom edge lands exactly on the grid line at every zoom
  (the zoom_bucket drift: sheet scaled with a quantized zoom while the
  grid used the true zoom, so the sheet visibly left the grid).
- adjacent cell rects tile without 1px gaps/overlaps at fractional zooms.
- overlay screen_rect_for() agrees with Viewport.cell_screen_rect().
- canvas limit border: sheet_screen_rect geometry + draw without errors.
- hover outside hints: blocked (top/left) vs expand (bottom/right).
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


def _make_viewport(w=128, h=128, tw=32, th=32):
    from plugins.sprite_editor.camera import Camera
    from plugins.sprite_editor.document import Document
    from plugins.sprite_editor.selection import Selection
    from plugins.sprite_editor.viewport import Viewport

    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((80, 80, 80, 255))
    doc = Document(tile_size=(tw, th))
    doc.set_surface(surf)
    selection = Selection()
    camera = Camera()
    viewport = Viewport(Rect(0, 0, 800, 600), doc, camera, selection)
    return viewport, doc, camera, selection


ZOOMS = [0.5, 0.75, 1.0, 1.12, 1.25, 1.5, 1.75, 2.0, 2.3, 3.0]


class TestSheetGridAlignment:
    @pytest.mark.parametrize("zoom", ZOOMS)
    def test_sheet_edges_match_grid_lines(self, zoom):
        from plugins.sprite_editor.overlays import snapped_origin

        viewport, doc, camera, _ = _make_viewport()
        camera.zoom = zoom
        sheet = viewport.sheet_screen_rect()
        assert sheet is not None
        x0, _ = snapped_origin(camera)
        # grid lines use the same snapped-origin rule: line k at x0+round(k*tw*z)
        cols, rows = doc.cols, doc.rows
        grid_right = x0 + round(cols * doc.tw * zoom)
        assert sheet.right == grid_right
        # vertical: recompute with y origin
        _, y0 = snapped_origin(camera)
        grid_bottom = y0 + round(rows * doc.th * zoom)
        assert sheet.bottom == grid_bottom

    @pytest.mark.parametrize("zoom", ZOOMS)
    def test_sheet_size_is_exact_zoom(self, zoom):
        viewport, doc, camera, _ = _make_viewport()
        camera.zoom = zoom
        sheet = viewport.sheet_screen_rect()
        w, h = doc.size
        assert (sheet.w, sheet.h) == (round(w * zoom), round(h * zoom))

    @pytest.mark.parametrize("zoom", ZOOMS)
    def test_cells_tile_without_gaps(self, zoom):
        viewport, doc, camera, _ = _make_viewport()
        camera.zoom = zoom
        cols, rows = doc.cols, doc.rows
        for col in range(cols - 1):
            left = viewport.cell_screen_rect(col, 0)
            right = viewport.cell_screen_rect(col + 1, 0)
            assert left.right == right.x
        for row in range(rows - 1):
            top = viewport.cell_screen_rect(0, row)
            bottom = viewport.cell_screen_rect(0, row + 1)
            assert top.bottom == bottom.y

    @pytest.mark.parametrize("zoom", ZOOMS)
    def test_cell_edges_match_grid_lines(self, zoom):
        from plugins.sprite_editor.overlays import snapped_origin

        viewport, doc, camera, _ = _make_viewport()
        camera.zoom = zoom
        x0, y0 = snapped_origin(camera)
        for col in range(doc.cols + 1):
            # right edge of cell col-1 == left edge of cell col == grid line
            line = x0 + round(col * doc.tw * zoom)
            if col < doc.cols:
                assert viewport.cell_screen_rect(col, 0).x == line
            if col > 0:
                assert viewport.cell_screen_rect(col - 1, 0).right == line

    def test_overlay_rect_agrees_with_viewport(self):
        from plugins.sprite_editor.overlays import screen_rect_for

        viewport, doc, camera, _ = _make_viewport()
        camera.zoom = 1.37
        for col in range(doc.cols):
            for row in range(doc.rows):
                rect = doc.tile_rect(col, row)
                assert screen_rect_for(camera, rect.x, rect.y, rect.w, rect.h) == \
                    viewport.cell_screen_rect(col, row)

    def test_panned_origin_stays_aligned(self):
        from plugins.sprite_editor.overlays import snapped_origin

        viewport, doc, camera, _ = _make_viewport()
        camera.zoom = 1.37
        camera.pan(13.7, -7.3)
        sheet = viewport.sheet_screen_rect()
        x0, y0 = snapped_origin(camera)
        assert (sheet.x, sheet.y) == (x0, y0)
        assert sheet.right == x0 + round(doc.cols * doc.tw * camera.zoom)
        # cells still tile after pan
        for col in range(doc.cols - 1):
            assert viewport.cell_screen_rect(col, 0).right == \
                viewport.cell_screen_rect(col + 1, 0).x


class TestCanvasBounds:
    def test_sheet_screen_rect_geometry(self):
        viewport, doc, camera, _ = _make_viewport()
        camera.zoom = 2.0
        sheet = viewport.sheet_screen_rect()
        # world origin sits one header below viewport top: (0, 24)
        assert (sheet.x, sheet.y) == (0, 24)
        assert (sheet.w, sheet.h) == (256, 256)

    def test_draw_canvas_bounds_no_crash(self):
        viewport, _, _, _ = _make_viewport()
        screen = pygame.Surface((800, 600))
        viewport._draw_canvas_bounds(screen)  # must not raise

    def test_draw_full_viewport_no_crash_fractional_zoom(self):
        viewport, _, camera, _ = _make_viewport()
        camera.zoom = 1.37
        camera.pan(40.2, -15.7)
        screen = pygame.Surface((800, 600))
        viewport.draw(screen, None)  # sheet + bounds + grid + selection


class TestOutsideHints:
    def _make_tool(self, viewport, doc, camera, selection):
        from plugins.sprite_editor.tools import SelectTool, ToolContext

        messages: list[tuple[str, str]] = []

        def status(msg: str, detail: str = "") -> None:
            messages.append((msg, detail))

        ctx = ToolContext(
            doc=doc,
            selection=selection,
            camera=camera,
            viewport=viewport,
            clipboard=None,
            commands=None,
            status=status,
            toast=lambda *a: None,
            set_tool=lambda *a: None,
        )
        return SelectTool(ctx), messages

    def test_blocked_top_left(self):
        viewport, doc, camera, selection = _make_viewport()
        tool, messages = self._make_tool(viewport, doc, camera, selection)
        tool._update_hover((-5, 100))  # world x < 0
        assert tool._hover_outside == "blocked"
        assert tool._hover_cell is None
        assert messages[-1][0] == "Canvas edge — top/left blocked"

    def test_expand_bottom_right(self):
        viewport, doc, camera, selection = _make_viewport()
        tool, messages = self._make_tool(viewport, doc, camera, selection)
        # world (144, 64): past the 128px sheet on x
        tool._update_hover((144, 24 + 64))
        assert tool._hover_outside == "expand"
        assert messages[-1][0] == "Outside canvas — bottom/right expands"

    def test_inside_canvas(self):
        viewport, doc, camera, selection = _make_viewport()
        tool, messages = self._make_tool(viewport, doc, camera, selection)
        tool._update_hover((64, 24 + 64))
        assert tool._hover_outside is None
        assert tool._hover_cell == (2, 2)
