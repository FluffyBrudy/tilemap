"""Each import appends a block. Row goes below, column goes right."""

from pathlib import Path
import sys

import pytest


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
        doc.append_sheet(solid(64, 32, (0, 80, 0)), place="below")
        assert doc.surface.get_size() == (64, 64)
        assert doc.surface.get_at((10, 10))[:3] == (200, 0, 0)
        assert doc.surface.get_at((10, 42))[:3] == (0, 80, 0)

    def test_vertical_block_goes_right_existing_columns(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(32, 64, (150, 0, 0)))
        doc.append_sheet(solid(32, 64, (0, 60, 0)), place="right")
        assert doc.surface.get_size() == (64, 64)
        assert doc.surface.get_at((10, 10))[:3] == (150, 0, 0)
        assert doc.surface.get_at((42, 10))[:3] == (0, 60, 0)

    def test_append_never_shrinks_or_overwrites(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(96, 96, (200, 0, 0)))
        doc.append_sheet(solid(32, 32, (0, 60, 0)), place="below")
        assert doc.surface.get_at((90, 90))[:3] == (200, 0, 0)
        assert doc.surface.get_size() == (96, 128)

    def test_blank_canvas_adopts_sheet(self):
        doc = Document(tile_size=(32, 32))
        doc.append_sheet(solid(48, 16, (9, 9, 9)), place="below")
        assert doc.surface.get_size() == (48, 16)

    def test_row_snaps_to_tile_boundary(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(64, 40, (1, 1, 1)))
        doc.append_sheet(solid(64, 32, (2, 2, 2)), place="below")
        assert doc.surface.get_at((10, 44))[:3] == (0, 0, 0)
        assert doc.surface.get_at((10, 66))[:3] == (2, 2, 2)


class TestOpenFlowAppends:
    def _editor(self):
        from plugins.sprite_editor.editor import SpriteEditor

        ed = SpriteEditor(Rect(0, 0, 1000, 700), tile_size=(32, 32))
        return ed

    def test_second_open_appends_row_instead_of_replacing(self):
        ed = self._editor()
        ed._append_below = True
        first = pygame.Surface((256, 32), pygame.SRCALPHA)
        first.fill((200, 5, 30))
        ed._load_surface(first, ["batch1"])
        size_before = ed.doc.size

        second = pygame.Surface((256, 32), pygame.SRCALPHA)
        second.fill((80, 5, 30))
        combined = ed._build_combined_surface([second], arrange="row")
        ed.commands.push(
            AppendSheetCommand(combined, names=["batch2"], place="below"),
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
        ed._append_below = False
        ed._load_surface(pygame.Surface((32, 64), pygame.SRCALPHA), ["c1"])
        col = pygame.Surface((32, 64), pygame.SRCALPHA)
        col.fill((60, 60, 60))
        ed.commands.push(
            AppendSheetCommand(col, names=["c2"], place="right"), ed.doc, ed.selection
        )
        assert ed.doc.size == (64, 64)
        ed._on_undo()
        assert ed.doc.size == (32, 64)

    def test_undo_restores_sheet_list(self):

        ed = self._editor()
        ed._load_surface(solid(32, 32, (1, 1, 1)), ["batch1"])
        ed.commands.push(
            AppendSheetCommand(
                solid(32, 32, (2, 2, 2)), names=["batch2"], place="below"
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
        doc.blit_surface(solid(20, 20, (0, 200, 0)), (-17, 4))

        assert doc.origin_col == -1
        assert doc.origin_row == 0
        assert doc.surface.get_at((10 + 32, 10))[:3] == (200, 0, 0)
        col, row = doc.cell_at(10 + 32, 10)
        assert (col, row) == (0, 0)

    def test_pixel_to_cell_tracks_shifted_content(self):
        doc = self._doc()
        doc.set_surface(solid(64, 64, (9, 9, 9)))
        before = doc.cell_at_unbounded(40, 40)
        doc.blit_surface(solid(16, 16, (5, 5, 5)), (-64, -32))
        after = doc.cell_at_unbounded(40 + 64, 40 + 32)
        assert after == before

    def test_positive_growth_unchanged_no_origin_bump(self):
        doc = self._doc()
        doc.set_surface(solid(32, 32, (7, 7, 7)))
        doc.blit_surface(solid(16, 16, (8, 8, 8)), (40, 50))
        assert doc.origin_col == 0 and doc.origin_row == 0
        assert doc.surface.get_at((45, 55))[:3] == (8, 8, 8)


class TestAppendWrap:
    def _strip(self, colors, vertical=False):
        cells = [solid(32, 32, c) for c in colors]
        if vertical:
            out = Surface((32, 32 * len(cells)), pygame.SRCALPHA)
            for i, c in enumerate(cells):
                out.blit(c, (0, i * 32))
        else:
            out = Surface((32 * len(cells), 32), pygame.SRCALPHA)
            for i, c in enumerate(cells):
                out.blit(c, (i * 32, 0))
        return out

    def test_below_wrap_holds_width(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(64, 32, (200, 0, 0)))
        doc.wrap_cols = 2
        doc.append_sheet(self._strip([(0, 80, 0), (0, 0, 200), (80, 80, 0)]), place="below")
        assert doc.surface.get_size() == (64, 96)
        assert doc.surface.get_at((10, 42))[:3] == (0, 80, 0)
        assert doc.surface.get_at((42, 42))[:3] == (0, 0, 200)
        assert doc.surface.get_at((10, 74))[:3] == (80, 80, 0)

    def test_below_narrow_strip_ignores_lock(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(64, 32, (200, 0, 0)))
        doc.wrap_cols = 2
        doc.append_sheet(self._strip([(0, 80, 0)]), place="below")
        assert doc.surface.get_size() == (64, 64)
        assert doc.surface.get_at((10, 42))[:3] == (0, 80, 0)

    def test_right_wrap_holds_height(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(32, 64, (200, 0, 0)))
        doc.wrap_rows = 2
        doc.append_sheet(self._strip([(0, 80, 0), (0, 0, 200), (80, 80, 0)], vertical=True), place="right")
        assert doc.surface.get_size() == (96, 64)
        assert doc.surface.get_at((42, 10))[:3] == (0, 80, 0)
        assert doc.surface.get_at((42, 42))[:3] == (0, 0, 200)
        assert doc.surface.get_at((74, 10))[:3] == (80, 80, 0)

    def test_blank_adopt_ignores_lock(self):
        doc = Document(tile_size=(32, 32))
        doc.wrap_cols = 2
        doc.append_sheet(solid(96, 32, (9, 9, 9)), place="below")
        assert doc.surface.get_size() == (96, 32)

    def test_unknown_place_falls_below(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(32, 32, (200, 0, 0)))
        doc.append_sheet(solid(32, 32, (0, 80, 0)), place="diagonal")
        assert doc.surface.get_size() == (32, 64)
        assert doc.surface.get_at((10, 42))[:3] == (0, 80, 0)

    def test_locks_survive_snapshot_restore(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(32, 32, (200, 0, 0)))
        doc.wrap_cols = 4
        snap = doc.snapshot()
        doc.wrap_cols = None
        doc.restore(snap)
        assert doc.wrap_cols is None

    def test_lock_toggles_from_canvas(self):
        from plugins.sprite_editor.editor import SpriteEditor

        ed = SpriteEditor(Rect(0, 0, 1000, 700), tile_size=(32, 32))
        assert ed.doc.wrap_cols is None
        ed._toggle_lock_width()
        assert ed.doc.wrap_cols is None
        ed._load_surface(solid(64, 32, (1, 1, 1)), ["s"])
        ed._toggle_lock_width()
        assert ed.doc.wrap_cols == 2
        ed._toggle_lock_width()
        assert ed.doc.wrap_cols is None
        ed._toggle_lock_height()
        assert ed.doc.wrap_rows == 1
        ed._toggle_lock_height()
        assert ed.doc.wrap_rows is None

    def test_arrange_toggle_roundtrip(self):
        from plugins.sprite_editor.editor import SpriteEditor

        ed = SpriteEditor(Rect(0, 0, 1000, 700), tile_size=(32, 32))
        assert ed._append_below is False
        ed._toggle_append()
        assert ed._append_below is True
        ed._toggle_append()
        assert ed._append_below is False


class TestLockMenuState:
    def _file_actions(self, ed):
        file_menu = next(m for m in ed.menubar.menus if m.label == "File")
        return {getattr(a, "label", ""): a for a in file_menu.actions}

    def test_locks_disabled_without_canvas(self):
        from plugins.sprite_editor.editor import SpriteEditor

        ed = SpriteEditor(Rect(0, 0, 1000, 700), tile_size=(32, 32))
        actions = self._file_actions(ed)
        assert actions["Lock Width to Canvas"].is_enabled() is False
        assert actions["Lock Height to Canvas"].is_enabled() is False

    def test_locks_enabled_and_checked_with_canvas(self):
        from plugins.sprite_editor.editor import SpriteEditor

        ed = SpriteEditor(Rect(0, 0, 1000, 700), tile_size=(32, 32))
        ed._load_surface(solid(64, 32, (1, 1, 1)), ["s"])
        actions = self._file_actions(ed)
        assert actions["Lock Width to Canvas"].is_enabled() is True
        assert actions["Lock Width to Canvas"].is_checked() is False
        ed._toggle_lock_width()
        assert actions["Lock Width to Canvas"].is_checked() is True
        assert actions["Lock Height to Canvas"].is_checked() is False
        ed._toggle_lock_height()
        assert actions["Lock Height to Canvas"].is_checked() is True
