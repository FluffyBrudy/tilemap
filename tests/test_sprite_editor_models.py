"""Model-layer tests: Camera (pure), Selection, Document, Clipboard."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from plugins.sprite_editor.camera import Camera  # noqa: E402
from plugins.sprite_editor.clipboard import Clipboard  # noqa: E402
from plugins.sprite_editor.document import Document, Region  # noqa: E402
from plugins.sprite_editor.selection import Selection  # noqa: E402


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


# ---------------------------------------------------------------------------
# Camera — pure math, no pygame
# ---------------------------------------------------------------------------


class TestCameraPure:
    def test_no_pygame_import(self):
        import ast
        from pathlib import Path

        camera_path = Path(__file__).parent.parent / "src" / "plugins" / "sprite_editor" / "camera.py"
        src = camera_path.read_text()
        tree = ast.parse(src)
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert not any("pygame" in name for name in imports)

    def test_roundtrip_identity(self):
        cam = Camera(viewport_x=10, viewport_y=20, zoom=2.5, scroll_x=-30, scroll_y=40)
        for x, y in [(0, 0), (12.5, -7.25), (300, 100), (1e6, -1e6)]:
            sx, sy = cam.world_to_screen(x, y)
            wx, wy = cam.screen_to_world(sx, sy)
            assert abs(wx - x) < 1e-9
            assert abs(wy - y) < 1e-9

    def test_zoom_at_keeps_cursor_fixed(self):
        cam = Camera(viewport_x=0, viewport_y=0, zoom=1.0, scroll_x=0, scroll_y=0)
        point = (123.0, 456.0)
        world_before = cam.screen_to_world(*point)
        cam.zoom_at(point, 1.8)
        world_after = cam.screen_to_world(*point)
        assert abs(world_before[0] - world_after[0]) < 1e-9
        assert abs(world_before[1] - world_after[1]) < 1e-9
        assert cam.zoom == pytest.approx(1.8)

    def test_zoom_at_zoom_in_zooms(self):
        cam = Camera()
        cam.zoom_at((50, 50), 2.0)
        assert cam.zoom == pytest.approx(2.0)

    def test_zoom_clamped(self):
        from plugins.sprite_editor.camera import MAX_ZOOM, MIN_ZOOM

        cam = Camera(zoom=1.0)
        cam.zoom_at((10, 10), 1000.0)
        assert cam.zoom == pytest.approx(MAX_ZOOM)
        cam.zoom_at((10, 10), 1e-9)
        assert cam.zoom == pytest.approx(MIN_ZOOM)

    def test_fit_covers_sheet(self):
        cam = Camera(viewport_x=0, viewport_y=0)
        cam.fit((128, 128), (640, 480))
        assert cam.zoom == pytest.approx(480 / 128)  # height-limited
        assert cam.scroll_x == pytest.approx((640 - 128 * cam.zoom) / 2)
        assert cam.scroll_y == pytest.approx(0)

    def test_fit_width_limited(self):
        cam = Camera()
        cam.fit((1024, 128), (640, 480))
        assert cam.zoom == pytest.approx(640 / 1024)

    def test_fit_zero_size_resets(self):
        cam = Camera(zoom=2.0, scroll_x=50, scroll_y=50)
        cam.fit((0, 0), (640, 480))
        assert cam.zoom == pytest.approx(1.0)
        assert cam.scroll_x == pytest.approx(0.0)

    def test_reset(self):
        cam = Camera(zoom=3.0, scroll_x=10, scroll_y=-20)
        cam.reset()
        assert cam.zoom == pytest.approx(1.0)
        assert cam.scroll_x == 0.0 and cam.scroll_y == 0.0

    def test_pan(self):
        cam = Camera()
        cam.pan(15.0, -3.5)
        assert cam.scroll_x == 15.0 and cam.scroll_y == -3.5

    def test_world_to_screen_rect(self):
        cam = Camera(viewport_x=5, viewport_y=5, zoom=2.0)
        sx, sy, sw, sh = cam.world_to_screen_rect(10, 20, 32, 16)
        assert (sx, sy, sw, sh) == (25.0, 45.0, 64.0, 32.0)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


class TestSelection:
    def test_empty(self):
        s = Selection()
        assert not s
        assert s.bounds() is None

    def test_add_remove_toggle_contains(self):
        s = Selection()
        s.add(1, 2)
        assert s.contains(1, 2)
        s.remove(1, 2)
        assert not s.contains(1, 2)
        s.toggle(0, 0)
        s.toggle(0, 0)
        assert not s
        s.toggle(3, 4)
        assert s.contains(3, 4)

    def test_bounds(self):
        s = Selection.from_cells([(1, 2), (5, 0), (3, 7)])
        assert s.bounds() == (1, 0, 5, 7)

    def test_anchor(self):
        s = Selection.from_cells([(0, 0), (1, 1)])
        s.anchor = (1, 1)
        assert s.anchor == (1, 1)

    def test_clear_resets_anchor(self):
        s = Selection.from_cells([(0, 0)])
        s.anchor = (0, 0)
        s.clear()
        assert not s
        assert s.anchor is None

    def test_copy_independent(self):
        s = Selection.from_cells([(0, 0), (2, 2)])
        c = s.copy()
        c.add(9, 9)
        assert not s.contains(9, 9)

    def test_sorted_cells_row_major(self):
        s = Selection.from_cells([(1, 0), (0, 1), (0, 0)])
        assert s.sorted_cells() == [(0, 0), (1, 0), (0, 1)]

    def test_len(self):
        s = Selection.from_cells([(0, 0), (1, 1)])
        assert len(s) == 2


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class TestDocument:
    def make_doc(self, w=128, h=128, tile_size=(32, 32)):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        return Document(surf, tile_size)

    def test_grid_math(self):
        doc = self.make_doc()
        assert doc.cols == 4 and doc.rows == 4
        assert doc.cell_at(10, 10) == (0, 0)
        assert doc.cell_at(32, 32) == (1, 1)
        assert doc.cell_at(-1, 0) is None
        assert doc.cell_at(200, 10) is None
        assert doc.cell_index(1, 2) == 9
        assert doc.cell_col_row(9) == (1, 2)
        assert doc.index_at(10, 10) == 0
        assert doc.index_at(-5, 0) == -1

    def test_partial_edge_tile(self):
        doc = self.make_doc(100, 100)
        assert doc.cols == 4  # ceil(100/32)
        assert doc.cell_at(99, 99) == (3, 3)

    def test_extract_write_tile(self):
        doc = self.make_doc()
        tile = doc.extract_tile(1, 1)
        tile.fill((255, 0, 0, 255))
        doc.write_tile(1, 1, tile)
        px = doc.surface.get_at((32 + 5, 32 + 5))
        assert px[:3] == (255, 0, 0)

    def test_extract_tile_outside_canvas(self):
        doc = self.make_doc()
        tile = doc.extract_tile(5, 0)  # beyond right edge
        assert tile.get_size() == (32, 32)

    def test_clear_tiles(self):
        doc = self.make_doc()
        doc.write_tile(0, 0, pygame.Surface((32, 32), pygame.SRCALPHA))
        doc.clear_tiles([(0, 0)])
        assert doc.surface.get_at((5, 5)) == (0, 0, 0, 0)

    def test_flip_tiles(self):
        doc = self.make_doc()
        tile = pygame.Surface((32, 32), pygame.SRCALPHA)
        tile.fill((10, 0, 0, 255))
        pygame.draw.rect(tile, (255, 0, 0, 255), (0, 0, 4, 4))
        doc.write_tile(0, 0, tile)
        doc.flip_tiles([(0, 0)], True, False)
        assert doc.surface.get_at((2, 2))[:3] == (10, 0, 0)
        assert doc.surface.get_at((30, 2))[:3] == (255, 0, 0)

    def test_expand_canvas(self):
        doc = self.make_doc()
        assert doc.expand_canvas_to(6, 6)
        assert doc.surface.get_size() == (192, 192)
        assert not doc.expand_canvas_to(4, 4)

    def test_ensure_contains_cells(self):
        doc = self.make_doc()
        assert doc.ensure_contains_cells([(5, 2)])
        assert doc.surface.get_size() == (192, 128)

    def test_scale(self):
        doc = self.make_doc()
        doc.scale(0.5)
        assert doc.surface.get_size() == (64, 64)

    def test_revision_bumps_on_mutation(self):
        doc = self.make_doc()
        rev = doc.revision
        doc.clear_tiles([(0, 0)])
        assert doc.revision > rev
        rev = doc.revision
        doc.surface.get_size()
        assert doc.revision == rev  # reads don't bump

    def test_snapshot_restore_regions(self):
        doc = self.make_doc()
        doc.regions = [Region(id="a", rect=[0, 0, 10, 10])]
        snap = doc.snapshot()
        doc.regions.clear()
        doc.clear_tiles([(0, 0)])
        doc.restore(snap)
        assert len(doc.regions) == 1

    def test_region_dict_roundtrip(self):
        r = Region(id="abc", rect=[1.5, 2.5, 10.0, 20.0], name="hero")
        d = r.to_dict()
        assert d["rect"] == [2, 2, 10, 20]  # rounded ints, legacy format
        r2 = Region.from_dict(d)
        assert r2.id == "abc" and r2.name == "hero"
        assert r2.rect == [2.0, 2.0, 10.0, 20.0]

    def test_region_from_dict_missing_id(self):
        r = Region.from_dict({"rect": [0, 0, 8, 8], "name": ""})
        assert r.id
        assert r.rect == [0.0, 0.0, 8.0, 8.0]


class TestDocumentOrigin:
    """Canvas origin: writes above/left of (0,0) shift the origin instead of
    being dropped; all coordinate math stays consistent."""

    def make_doc(self, w=128, h=128, tile_size=(32, 32)):
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        return Document(surf, tile_size)

    def test_write_negative_row_shifts_origin(self):
        doc = self.make_doc()
        tile = pygame.Surface((32, 32), pygame.SRCALPHA)
        tile.fill((255, 0, 0, 255))
        doc.write_tile(0, -1, tile)
        assert doc.origin_row == -1
        assert doc.origin_col == 0
        # label -1 sits at the canvas top; nothing was clipped
        assert doc.surface.get_at((5, 5))[:3] == (255, 0, 0)
        assert doc.surface.get_size() == (128, 128)  # no right/down growth

    def test_write_negative_both_axes(self):
        doc = self.make_doc()
        doc.write_tile(-2, -3, pygame.Surface((32, 32), pygame.SRCALPHA))
        assert (doc.origin_col, doc.origin_row) == (-2, -3)
        assert doc.is_valid_cell(-2, -3)
        assert doc.is_valid_cell(-1, -2)
        assert doc.is_valid_cell(1, 0)
        assert not doc.is_valid_cell(-3, -3)
        assert doc.tile_rect(-2, -3).topleft == (0, 0)
        assert doc.tile_rect(1, 0).topleft == (96, 96)

    def test_cell_at_uses_origin(self):
        doc = self.make_doc()
        doc.write_tile(0, -1, pygame.Surface((32, 32), pygame.SRCALPHA))
        assert doc.cell_at(0, 0) == (0, -1)
        assert doc.cell_at(32, 32) == (1, 0)
        assert doc.cell_at_unbounded(96, 0) == (3, -1)

    def test_write_below_origin_after_shift_grows_right(self):
        doc = self.make_doc()
        doc.write_tile(0, -1, pygame.Surface((32, 32), pygame.SRCALPHA))
        doc.write_tile(4, 0, pygame.Surface((32, 32), pygame.SRCALPHA))  # col 4 with origin -1
        assert doc.is_valid_cell(4, 0)
        assert doc.surface.get_size() == (160, 128)  # 5 cols * 32

    def test_snapshot_restore_origin(self):
        doc = self.make_doc()
        doc.write_tile(0, -1, pygame.Surface((32, 32), pygame.SRCALPHA))
        snap = doc.snapshot()
        assert snap[3] == (0, -1)
        doc.write_tile(3, 3, pygame.Surface((32, 32), pygame.SRCALPHA))
        doc.restore(snap)
        assert (doc.origin_col, doc.origin_row) == (0, -1)
        assert doc.surface.get_size() == (128, 128)


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------


class TestClipboard:
    def make_doc(self):
        surf = pygame.Surface((128, 128), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        return Document(surf, (32, 32))

    def test_copy_from_selection(self):
        doc = self.make_doc()
        sel = Selection.from_cells([(1, 1), (2, 1), (1, 2)])
        cl = Clipboard()
        assert cl.copy_from_selection(doc, sel)
        assert len(cl) == 3
        assert cl.tile_size == (32, 32)
        # offsets relative to top-left of selection
        assert sorted((dx, dy) for dx, dy, _ in cl.tiles) == [(0, 0), (0, 1), (1, 0)]

    def test_copy_empty_selection_clears(self):
        doc = self.make_doc()
        cl = Clipboard()
        cl.tiles = [(0, 0, pygame.Surface((1, 1)))]
        assert not cl.copy_from_selection(doc, Selection())
        assert cl.is_empty

    def test_paste_surfaces_recompute(self):
        doc = self.make_doc()
        sel = Selection.from_cells([(0, 0), (1, 0)])
        cl = Clipboard()
        cl.copy_from_selection(doc, sel)
        assert sorted((c, r) for c, r, _ in cl.paste_surfaces(5, 3)) == [(5, 3), (6, 3)]

    def test_covered_cells(self):
        doc = self.make_doc()
        sel = Selection.from_cells([(0, 0), (1, 0), (1, 1)])
        cl = Clipboard()
        cl.copy_from_selection(doc, sel)
        assert sorted(cl.covered_cells(2, 2)) == [(2, 2), (3, 2), (3, 3)]

    def test_bounds_cells(self):
        doc = self.make_doc()
        sel = Selection.from_cells([(0, 0), (2, 1)])
        cl = Clipboard()
        cl.copy_from_selection(doc, sel)
        assert cl.bounds_cells() == (3, 2)