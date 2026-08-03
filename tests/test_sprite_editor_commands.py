"""Command-layer tests: CommandStack, undo/redo, selection memory, all commands."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from plugins.sprite_editor.commands import (  # noqa: E402
    ClearCommand,
    CommandStack,
    FlipCommand,
    GridResizeCommand,
    MoveCommand,
    PasteCommand,
    RegionAddCommand,
    RegionDeleteCommand,
    RegionMoveCommand,
    RegionRenameCommand,
    RegionResizeCommand,
    ScaleCommand,
)
from plugins.sprite_editor.document import Document, Region  # noqa: E402
from plugins.sprite_editor.selection import Selection  # noqa: E402


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


def make_doc(w=128, h=128, tile_size=(32, 32)):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    return Document(surf, tile_size)


def fill_tile(doc, col, row, color=(200, 30, 30, 255)):
    tile = pygame.Surface((doc.tw, doc.th), pygame.SRCALPHA)
    tile.fill(color)
    doc.write_tile(col, row, tile)


def pixel_at(doc, col, row, dx=5, dy=5):
    return doc.surface.get_at((col * doc.tw + dx, row * doc.th + dy))


class TestCommandStack:
    def test_push_undo_redo_roundtrip(self):
        doc = make_doc()
        sel = Selection.from_cells([(0, 0)])
        fill_tile(doc, 0, 0)
        stack = CommandStack()
        stack.push(FlipCommand([(0, 0)], True, False), doc, sel)
        assert stack.can_undo and not stack.can_redo
        before = pixel_at(doc, 0, 0)
        stack.undo(doc, sel)
        assert pixel_at(doc, 0, 0) == before
        stack.redo(doc, sel)
        assert pixel_at(doc, 0, 0) == before  # redone == same pixels

    def test_undo_restores_selection(self):
        doc = make_doc()
        sel = Selection.from_cells([(0, 0), (1, 0)])
        stack = CommandStack()
        stack.push(MoveCommand([(0, 0), (1, 0)], 2, 0), doc, sel)
        assert sel.sorted_cells() == [(2, 0), (3, 0)]
        stack.undo(doc, sel)
        assert sel.sorted_cells() == [(0, 0), (1, 0)]
        stack.redo(doc, sel)
        assert sel.sorted_cells() == [(2, 0), (3, 0)]

    def test_redo_cleared_on_new_push(self):
        doc = make_doc()
        sel = Selection()
        stack = CommandStack()
        stack.push(MoveCommand([(0, 0)], 1, 0), doc, sel)
        stack.undo(doc, sel)
        assert stack.can_redo
        stack.push(MoveCommand([(0, 0)], 1, 0), doc, sel)
        assert not stack.can_redo

    def test_stack_depth_limit(self):
        doc = make_doc()
        sel = Selection()
        stack = CommandStack(limit=50)
        for i in range(55):
            stack.push(MoveCommand([(0, 0)], i % 3, 0), doc, sel)
        assert len(stack._undo) == 50
        assert stack.can_undo

    def test_undo_empty_returns_false(self):
        doc = make_doc()
        stack = CommandStack()
        assert not stack.undo(doc, Selection())
        assert not stack.redo(doc, Selection())

    def test_peek_names(self):
        doc = make_doc()
        sel = Selection()
        stack = CommandStack()
        stack.push(MoveCommand([(0, 0)], 1, 0), doc, sel)
        assert stack.undo_name() == "Move"
        stack.undo(doc, sel)
        assert stack.redo_name() == "Move"


class TestMoveCommand:
    def test_move_carries_pixels(self):
        doc = make_doc()
        fill_tile(doc, 0, 0, (10, 200, 10, 255))
        sel = Selection()
        stack = CommandStack()
        stack.push(MoveCommand([(0, 0)], 2, 1), doc, sel)
        assert pixel_at(doc, 2, 1) == (10, 200, 10, 255)
        assert pixel_at(doc, 0, 0) == (0, 0, 0, 0)
        assert sel.sorted_cells() == [(2, 1)]

    def test_move_expands_canvas(self):
        doc = make_doc()
        fill_tile(doc, 0, 0)
        sel = Selection()
        stack = CommandStack()
        stack.push(MoveCommand([(0, 0)], 5, 0), doc, sel)
        assert doc.surface.get_size() == (192, 128)
        stack.undo(doc, sel)
        assert doc.surface.get_size() == (128, 128)  # canvas shrinks back

    def test_move_negative_offset_keeps_cells(self):
        doc = make_doc()
        fill_tile(doc, 2, 0)
        sel = Selection()
        stack = CommandStack()
        stack.push(MoveCommand([(2, 0)], -1, 0), doc, sel)
        assert sel.sorted_cells() == [(1, 0)]
        assert pixel_at(doc, 1, 0) != (0, 0, 0, 0)


class TestPasteCommand:
    def test_paste_expands_and_selects(self):
        doc = make_doc()
        fill_tile(doc, 0, 0, (5, 5, 200, 255))
        fill_tile(doc, 1, 0, (200, 5, 5, 255))
        sel = Selection.from_cells([(0, 0), (1, 0)])
        tiles = []
        for col, row in sel.sorted_cells():
            tiles.append((col, row, doc.extract_tile(col, row)))
        stack = CommandStack()
        stack.push(PasteCommand(4, 2, tiles), doc, sel)
        assert pixel_at(doc, 4, 2) == (5, 5, 200, 255)
        assert pixel_at(doc, 5, 2) == (200, 5, 5, 255)
        assert sel.sorted_cells() == [(4, 2), (5, 2)]

    def test_paste_overwrites(self):
        doc = make_doc()
        fill_tile(doc, 0, 0, (10, 10, 10, 255))
        fill_tile(doc, 1, 1, (99, 99, 99, 255))
        sel = Selection.from_cells([(0, 0)])
        tiles = [(0, 0, doc.extract_tile(0, 0))]
        stack = CommandStack()
        stack.push(PasteCommand(1, 1, tiles), doc, sel)
        assert pixel_at(doc, 1, 1) == (10, 10, 10, 255)


class TestClearCommand:
    def test_clear_makes_transparent(self):
        doc = make_doc()
        fill_tile(doc, 0, 0, (1, 2, 3, 255))
        sel = Selection.from_cells([(0, 0)])
        stack = CommandStack()
        stack.push(ClearCommand([(0, 0)]), doc, sel)
        assert pixel_at(doc, 0, 0) == (0, 0, 0, 0)
        assert not sel


class TestFlipCommand:
    def test_flip(self):
        doc = make_doc()
        fill_tile(doc, 0, 0)
        tile = pygame.Surface((32, 32), pygame.SRCALPHA)
        tile.fill((0, 0, 0, 0))
        pygame.draw.rect(tile, (255, 0, 0, 255), (0, 0, 4, 4))
        doc.write_tile(0, 0, tile)
        stack = CommandStack()
        stack.push(FlipCommand([(0, 0)], True, False), doc, Selection())
        assert doc.surface.get_at((30, 2))[:3] == (255, 0, 0)
        stack.undo(doc, Selection())
        assert doc.surface.get_at((2, 2))[:3] == (255, 0, 0)

    def test_flip_keeps_selection(self):
        doc = make_doc()
        sel = Selection.from_cells([(0, 0), (1, 0)])
        stack = CommandStack()
        stack.push(FlipCommand([(0, 0), (1, 0)], True, False), doc, sel)
        assert sel.sorted_cells() == [(0, 0), (1, 0)]


class TestScaleCommand:
    def test_scale(self):
        doc = make_doc()
        sel = Selection()
        stack = CommandStack()
        stack.push(ScaleCommand(0.5), doc, sel)
        assert doc.surface.get_size() == (64, 64)
        stack.undo(doc, sel)
        assert doc.surface.get_size() == (128, 128)


class TestGridResizeCommand:
    def test_tile_size(self):
        doc = make_doc()
        stack = CommandStack()
        stack.push(GridResizeCommand((16, 16)), doc, Selection())
        assert doc.tile_size == (16, 16)
        assert doc.cols == 8
        stack.undo(doc, Selection())
        assert doc.tile_size == (32, 32)


class TestRegionCommands:
    def test_add_move_resize_delete_rename(self):
        doc = make_doc()
        sel = Selection()
        stack = CommandStack()
        r = Region(id="r1", rect=[10.0, 10.0, 20.0, 20.0], name="")
        stack.push(RegionAddCommand(r), doc, sel)
        assert len(doc.regions) == 1
        stack.push(RegionMoveCommand("r1", 5.0, -2.0), doc, sel)
        assert doc.regions[0].rect == [15.0, 8.0, 20.0, 20.0]
        stack.push(RegionResizeCommand("r1", [0.0, 0.0, 50.0, 50.0]), doc, sel)
        assert doc.regions[0].rect == [0.0, 0.0, 50.0, 50.0]
        stack.push(RegionRenameCommand("r1", "hero"), doc, sel)
        assert doc.regions[0].name == "hero"
        stack.push(RegionDeleteCommand("r1"), doc, sel)
        assert not doc.regions

    def test_region_undo_restores(self):
        doc = make_doc()
        sel = Selection()
        stack = CommandStack()
        r = Region(id="r1", rect=[0.0, 0.0, 10.0, 10.0], name="a")
        stack.push(RegionAddCommand(r), doc, sel)
        stack.push(RegionRenameCommand("r1", "b"), doc, sel)
        stack.undo(doc, sel)
        assert doc.regions[0].name == "a"
        stack.undo(doc, sel)
        assert not doc.regions

    def test_commands_hold_data_not_events(self):
        """Commands must not accept pygame events anywhere."""
        import inspect

        from plugins.sprite_editor import commands as cmds

        for name in dir(cmds):
            obj = getattr(cmds, name)
            if isinstance(obj, type) and issubclass(obj, cmds.Command) and obj is not cmds.Command:
                for method in ("_do", "apply", "undo", "redo"):
                    if method in obj.__dict__:
                        src = inspect.getsource(obj.__dict__[method])
                        assert "event" not in src, f"{name}.{method} references events"