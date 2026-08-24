"""Stacking semantics — each import pass appends a block, never overwrites.

horizontal mode: batch hstacks into a row; next pass = next row BELOW.
vertical mode:   batch vstacks into a column; next pass = next column RIGHT.
"""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pygame  # noqa: E402

from plugins.sprite_editor.commands import AppendSheetCommand  # noqa: E402
from plugins.sprite_editor.document import Document  # noqa: E402
from pygame import Rect, Surface  # noqa: E402


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))


def solid(w, h, color):
    s = Surface((w, h), pygame.SRCALPHA)
    s.fill(color)
    return s


class TestAppendSheetSemantics:
    def test_horizontal_block_goes_below_existing_rows(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(64, 32, (200, 0, 0)))
        doc.append_sheet(solid(64, 32, (0, 80, 0)), horizontal=True)
        assert doc.surface.get_size() == (64, 64)
        assert doc.surface.get_at((10, 10))[:3] == (200, 0, 0)
        assert doc.surface.get_at((10, 42))[:3] == (0, 80, 0)

    def test_vertical_block_goes_right_existing_columns(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(32, 64, (150, 0, 0)))
        doc.append_sheet(solid(32, 64, (0, 60, 0)), horizontal=False)
        assert doc.surface.get_size() == (64, 64)
        assert doc.surface.get_at((10, 10))[:3] == (150, 0, 0)
        assert doc.surface.get_at((42, 10))[:3] == (0, 60, 0)

    def test_append_never_shrinks_or_overwrites(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(96, 96, (200, 0, 0)))
        doc.append_sheet(solid(32, 32, (0, 60, 0)), horizontal=True)
        # old canvas untouched, block appended on the snapped row below
        assert doc.surface.get_at((90, 90))[:3] == (200, 0, 0)
        assert doc.surface.get_size() == (96, 128)

    def test_blank_canvas_adopts_sheet(self):
        doc = Document(tile_size=(32, 32))
        doc.append_sheet(solid(48, 16, (9, 9, 9)), horizontal=True)
        assert doc.surface.get_size() == (48, 16)

    def test_row_snaps_to_tile_boundary(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(64, 40, (1, 1, 1)))  # height not tile-aligned
        doc.append_sheet(solid(64, 32, (2, 2, 2)), horizontal=True)
        # row starts at y=64 (next multiple of 32), leaving a gap band
        assert doc.surface.get_at((10, 44))[:3] == (0, 0, 0)
        assert doc.surface.get_at((10, 66))[:3] == (2, 2, 2)


class TestOpenFlowAppends:
    def _editor(self):
        from plugins.sprite_editor.editor import SpriteEditor

        ed = SpriteEditor(Rect(0, 0, 1000, 700), tile_size=(32, 32))
        return ed

    def test_second_open_appends_row_instead_of_replacing(self):
        ed = self._editor()
        ed._stack_horizontal = True
        first = pygame.Surface((256, 32), pygame.SRCALPHA)
        first.fill((200, 5, 30))
        ed._load_surface(first, ["batch1"])
        size_before = ed.doc.size

        second = pygame.Surface((256, 32), pygame.SRCALPHA)
        second.fill((80, 5, 30))
        combined = ed._build_combined_surface([second], horizontal=True)
        ed.commands.push(
            AppendSheetCommand(combined, names=["batch2"], horizontal=True),
            ed.doc,
            ed.selection,
        )

        assert ed.doc.size[0] == max(size_before[0], 256)
        assert ed.doc.size[1] == size_before[1] + 32
        assert ed.doc.surface.get_at((10, 10))[:3] == (200, 5, 30)
        assert ed.doc.surface.get_at((10, size_before[1] + 10))[:3] == (80, 5, 30)
        assert ed.commands.can_undo
        assert ed.doc.sheets == ["batch1", "batch2"]

    def test_undo_restores_pre_append_canvas(self):
        ed = self._editor()
        ed._stack_horizontal = False
        ed._load_surface(pygame.Surface((32, 64), pygame.SRCALPHA), ["c1"])
        col = pygame.Surface((32, 64), pygame.SRCALPHA)
        col.fill((60, 60, 60))
        ed.commands.push(
            AppendSheetCommand(col, names=["c2"], horizontal=False), ed.doc, ed.selection
        )
        assert ed.doc.size == (64, 64)
        ed._on_undo()
        assert ed.doc.size == (32, 64)

    def test_undo_restores_sheet_list(self):
        """Sheet names ride inside the command: undo must revert the append."""
        ed = self._editor()
        ed._load_surface(solid(32, 32, (1, 1, 1)), ["batch1"])
        ed.commands.push(
            AppendSheetCommand(
                solid(32, 32, (2, 2, 2)), names=["batch2"], horizontal=True
            ),
            ed.doc,
            ed.selection,
        )
        assert ed.doc.sheets == ["batch1", "batch2"]

        ed._on_undo()
        assert ed.doc.sheets == ["batch1"]
        assert ed.doc.size == (32, 32)

        ed._on_redo()
        assert ed.doc.sheets == ["batch1", "batch2"]
        assert ed.doc.size == (32, 64)


class TestBlitSurfaceGrowth:
    def _doc(self):
        return Document(tile_size=(32, 32))

    def test_negative_origin_shift_is_tile_aligned_and_bumps_origin(self):
        doc = self._doc()
        doc.set_surface(solid(64, 64, (200, 0, 0)))
        # stamp 17px left of origin -> shift pads up to a full 32px tile
        doc.blit_surface(solid(20, 20, (0, 200, 0)), (-17, 4))

        assert doc.origin_col == -1
        assert doc.origin_row == 0
        # old content re-anchored at +32px; grid mapping follows the content
        assert doc.surface.get_at((10 + 32, 10))[:3] == (200, 0, 0)
        col, row = doc.cell_at(10 + 32, 10)
        assert (col, row) == (0, 0)  # same content, same absolute cell

    def test_pixel_to_cell_tracks_shifted_content(self):
        doc = self._doc()
        doc.set_surface(solid(64, 64, (9, 9, 9)))
        before = doc.cell_at_unbounded(40, 40)  # (1, 1)
        doc.blit_surface(solid(16, 16, (5, 5, 5)), (-64, -32))
        after = doc.cell_at_unbounded(40 + 64, 40 + 32)
        assert after == before  # same content cell, new coordinates

    def test_positive_growth_unchanged_no_origin_bump(self):
        doc = self._doc()
        doc.set_surface(solid(32, 32, (7, 7, 7)))
        doc.blit_surface(solid(16, 16, (8, 8, 8)), (40, 50))
        assert doc.origin_col == 0 and doc.origin_row == 0
        assert doc.surface.get_at((45, 55))[:3] == (8, 8, 8)
