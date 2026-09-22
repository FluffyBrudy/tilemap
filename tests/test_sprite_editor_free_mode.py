"""Free pixel mode regression tests (sprite editor).

Covers:
- Document.move_pixels: bytes move, source clears, canvas grows
  bottom/right, negative growth shifts origin without dropping tiles,
  destination rect accounts for the shift.
- PixelMoveCommand / PixelClearCommand undo/redo round-trips.
- FreeTool marquee: top/left wall clamped, bottom/right capped at the
  canvas, tiny drags rejected.
- FreeTool move: commit pushes PixelMoveCommand and clears the block.
- Enter with an idle block stores a Region (free-size export path).
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


def _make_doc(w=128, h=128, tw=32, th=32):
    from plugins.sprite_editor.document import Document

    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    # a red 16x16 block at (32, 32)
    surf.fill((255, 0, 0, 255), Rect(32, 32, 16, 16))
    doc = Document(tile_size=(tw, th))
    doc.set_surface(surf)
    return doc


def _make_selection():
    from plugins.sprite_editor.selection import Selection

    return Selection()


class TestMovePixels:
    def test_moves_bytes_and_clears_source(self):
        doc = _make_doc()
        dest = doc.move_pixels(Rect(32, 32, 16, 16), 16, 0)
        assert dest == Rect(48, 32, 16, 16)
        assert doc.surface.get_at((56, 40)) == pygame.Color(255, 0, 0, 255)
        assert doc.surface.get_at((32, 32)) == pygame.Color(0, 0, 0, 0)

    def test_transparent_source_moves_harmlessly(self):
        doc = _make_doc()
        # fully transparent but inside the canvas: moves no visible pixels
        dest = doc.move_pixels(Rect(0, 0, 8, 8), 10, 10)
        assert dest == Rect(10, 10, 8, 8)
        assert doc.surface.get_size() == (128, 128)

    def test_outside_source_returns_none(self):
        doc = _make_doc()
        assert doc.move_pixels(Rect(500, 500, 8, 8), 1, 1) is None

    def test_grows_bottom_right(self):
        doc = _make_doc()
        dest = doc.move_pixels(Rect(32, 32, 16, 16), 100, 100)
        assert dest == Rect(132, 132, 16, 16)
        w, h = doc.surface.get_size()
        assert (w, h) == (148, 148)
        assert doc.surface.get_at((140, 140)) == pygame.Color(255, 0, 0, 255)

    def test_negative_growth_shifts_origin_keeps_pixels(self):
        doc = _make_doc()
        dest = doc.move_pixels(Rect(32, 32, 16, 16), -40, -40)
        # block asked for (-8, -8): tile-multiple shift of one 32px tile
        assert dest == Rect(24, 24, 16, 16)
        assert (doc.origin_col, doc.origin_row) == (-1, -1)
        assert doc.surface.get_at((32, 32)) == pygame.Color(255, 0, 0, 255)
        # source pixels traveled with the content (cleared area moved too)
        assert doc.surface.get_at((64, 64)) == pygame.Color(0, 0, 0, 0)

    def test_clear_rect(self):
        doc = _make_doc()
        assert doc.clear_rect(Rect(32, 32, 16, 16)) is True
        assert doc.surface.get_at((40, 40)) == pygame.Color(0, 0, 0, 0)
        assert doc.clear_rect(Rect(500, 500, 4, 4)) is False


class TestPixelCommands:
    def test_move_undo_redo(self):
        from plugins.sprite_editor.commands import PixelMoveCommand

        doc = _make_doc()
        sel = _make_selection()
        cmd = PixelMoveCommand(Rect(32, 32, 16, 16), 16, 0)
        cmd.apply(doc, sel)
        assert doc.surface.get_at((56, 40)) == pygame.Color(255, 0, 0, 255)
        cmd.undo(doc, sel)
        assert doc.surface.get_at((40, 40)) == pygame.Color(255, 0, 0, 255)
        assert doc.surface.get_at((56, 40)) == pygame.Color(0, 0, 0, 0)
        cmd.redo(doc, sel)
        assert doc.surface.get_at((56, 40)) == pygame.Color(255, 0, 0, 255)

    def test_clear_undo_redo(self):
        from plugins.sprite_editor.commands import PixelClearCommand

        doc = _make_doc()
        sel = _make_selection()
        cmd = PixelClearCommand(Rect(32, 32, 16, 16))
        cmd.apply(doc, sel)
        assert doc.surface.get_at((40, 40)) == pygame.Color(0, 0, 0, 0)
        cmd.undo(doc, sel)
        assert doc.surface.get_at((40, 40)) == pygame.Color(255, 0, 0, 255)


def _make_tool(doc):
    from plugins.sprite_editor.camera import Camera
    from plugins.sprite_editor.selection import Selection
    from plugins.sprite_editor.tools import FreeTool, ToolContext
    from plugins.sprite_editor.viewport import Viewport

    camera = Camera()
    viewport = Viewport(Rect(0, 0, 800, 600), doc, camera, Selection())
    pushed: list = []
    toasts: list[str] = []

    class FakeCommands:
        def push(self, command, d, s):
            command.apply(d, s)
            pushed.append(command)

    ctx = ToolContext(
        doc=doc,
        selection=Selection(),
        camera=camera,
        viewport=viewport,
        clipboard=None,
        commands=FakeCommands(),
        status=lambda *a: None,
        toast=toasts.append,
        set_tool=lambda *a: None,
    )
    tool = FreeTool(ctx)
    return tool, viewport, pushed, toasts


class TestFreeToolMarquee:
    def test_marquee_selects_block(self):
        doc = _make_doc()
        tool, viewport, _, _ = _make_tool(doc)
        sx, sy = viewport.world_to_screen(32, 32)
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(sx), int(sy))}))
        ex, ey = viewport.world_to_screen(64, 64)
        tool.handle_event(pygame.event.Event(pygame.MOUSEMOTION, {"pos": (int(ex), int(ey))}))
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (int(ex), int(ey))}))
        assert tool._block == Rect(32, 32, 32, 32)

    def test_top_left_wall_clamped(self):
        doc = _make_doc()
        tool, viewport, _, _ = _make_tool(doc)
        # press inside, drag past the top/left wall
        sx, sy = viewport.world_to_screen(40, 40)
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(sx), int(sy))}))
        ex, ey = viewport.world_to_screen(-50, -50)
        tool.handle_event(pygame.event.Event(pygame.MOUSEMOTION, {"pos": (int(ex), int(ey))}))
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (int(ex), int(ey))}))
        assert tool._block is not None
        assert tool._block.x >= 0 and tool._block.y >= 0

    def test_tiny_drag_rejected(self):
        doc = _make_doc()
        tool, viewport, _, toasts = _make_tool(doc)
        sx, sy = viewport.world_to_screen(40, 40)
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(sx), int(sy))}))
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (int(sx) + 1, int(sy) + 1)}))
        assert tool._block is None
        assert toasts and "too small" in toasts[-1]


class TestFreeToolTight:
    def _marquee(self, tool, viewport, x0, y0, x1, y1):
        sx, sy = viewport.world_to_screen(x0, y0)
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(sx), int(sy))}))
        ex, ey = viewport.world_to_screen(x1, y1)
        tool.handle_event(pygame.event.Event(pygame.MOUSEMOTION, {"pos": (int(ex), int(ey))}))
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (int(ex), int(ey))}))

    def test_default_off_exact_marquee(self):
        doc = _make_doc()
        tool, viewport, _, _ = _make_tool(doc)
        assert tool.tight is False
        self._marquee(tool, viewport, 20, 20, 60, 60)
        assert tool._block == Rect(20, 20, 40, 40)

    def test_tight_shrinks_to_content(self):
        doc = _make_doc()
        tool, viewport, _, _ = _make_tool(doc)
        tool.tight = True
        # red block lives at (32, 32, 16, 16); marquee is larger
        self._marquee(tool, viewport, 20, 20, 60, 60)
        assert tool._block == Rect(32, 32, 16, 16)

    def test_tight_rejects_empty(self):
        doc = _make_doc()
        tool, viewport, _, toasts = _make_tool(doc)
        tool.tight = True
        # fully transparent corner
        self._marquee(tool, viewport, 80, 80, 110, 110)
        assert tool._block is None
        assert toasts and "Empty" in toasts[-1]

    def test_tight_block_moves_and_exports(self):
        from plugins.sprite_editor.region_export import export_all_regions

        doc = _make_doc()
        tool, viewport, pushed, _ = _make_tool(doc)
        tool.tight = True
        self._marquee(tool, viewport, 20, 20, 60, 60)
        assert tool._block == Rect(32, 32, 16, 16)
        tool.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN}))
        assert len(doc.regions) == 1
        assert doc.regions[0].rect == [32.0, 32.0, 16.0, 16.0]


class TestPixelClipboard:
    def test_copy_from_rect(self):
        from plugins.sprite_editor.clipboard import Clipboard

        doc = _make_doc()
        clip = Clipboard()
        assert clip.is_empty
        assert clip.copy_from_rect(doc, Rect(32, 32, 16, 16)) is True
        assert clip.has_pixels
        assert not clip.is_empty
        assert clip.free_surface.get_size() == (16, 16)
        assert clip.free_surface.get_at((0, 0)) == pygame.Color(255, 0, 0, 255)

    def test_copy_modes_are_exclusive(self):
        from plugins.sprite_editor.clipboard import Clipboard

        doc = _make_doc()
        clip = Clipboard()
        clip.copy_from_rect(doc, Rect(32, 32, 16, 16))
        sel = _make_selection()
        sel.replace([(0, 0)])
        assert clip.copy_from_selection(doc, sel) is True
        assert not clip.has_pixels
        assert len(clip.tiles) == 1
        clip.copy_from_rect(doc, Rect(32, 32, 16, 16))
        assert clip.has_pixels
        assert clip.tiles == []

    def test_copy_outside_canvas_fails(self):
        from plugins.sprite_editor.clipboard import Clipboard

        doc = _make_doc()
        clip = Clipboard()
        assert clip.copy_from_rect(doc, Rect(500, 500, 8, 8)) is False
        assert clip.is_empty


class TestPixelStampCommand:
    def test_stamp_undo_redo(self):
        from plugins.sprite_editor.commands import PixelStampCommand

        doc = _make_doc()
        sel = _make_selection()
        block = doc.surface.subsurface(Rect(32, 32, 16, 16)).copy()
        cmd = PixelStampCommand((64, 64), block)
        cmd.apply(doc, sel)
        assert doc.surface.get_at((72, 72)) == pygame.Color(255, 0, 0, 255)
        cmd.undo(doc, sel)
        assert doc.surface.get_at((72, 72)) == pygame.Color(0, 0, 0, 0)
        cmd.redo(doc, sel)
        assert doc.surface.get_at((72, 72)) == pygame.Color(255, 0, 0, 255)


def _make_editor_with_sheet():
    from plugins.sprite_editor.editor import SpriteEditor

    surf = pygame.Surface((128, 128), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    surf.fill((255, 0, 0, 255), Rect(32, 32, 16, 16))
    return SpriteEditor(Rect(0, 0, 1000, 700), surface=surf, tile_size=(32, 32))


def _free_marquee_on_editor(ed, x0, y0, x1, y1):
    vp = ed.viewport
    sx, sy = vp.world_to_screen(x0, y0)
    ed._free_tool.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(sx), int(sy))}))
    ex, ey = vp.world_to_screen(x1, y1)
    ed._free_tool.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, {"pos": (int(ex), int(ey))}))
    ed._free_tool.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (int(ex), int(ey))}))


class TestEditorCopyCutPaste:
    def test_free_copy_arms_free_paste(self):
        ed = _make_editor_with_sheet()
        ed._mode_indicator.set_active("free")
        assert ed.mode == "free"
        _free_marquee_on_editor(ed, 32, 32, 48, 48)
        assert ed._free_tool.has_block()
        ed._on_copy()
        assert ed.clipboard.has_pixels
        ed._on_paste()  # stays in free, arms floating ghost
        assert ed._free_tool._floating is not None
        # click elsewhere stamps a duplicate
        vp = ed.viewport
        sx, sy = vp.world_to_screen(80, 80)
        ed._free_tool.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(sx), int(sy))}))
        assert ed.doc.surface.get_at((88, 88)) == pygame.Color(255, 0, 0, 255)
        # original intact (copy, not move)
        assert ed.doc.surface.get_at((40, 40)) == pygame.Color(255, 0, 0, 255)

    def test_free_copy_without_block_warns(self):
        ed = _make_editor_with_sheet()
        ed._mode_indicator.set_active("free")
        ed._on_copy()
        assert ed.clipboard.is_empty

    def test_free_cut_clears_block(self):
        from plugins.sprite_editor.commands import PixelClearCommand

        ed = _make_editor_with_sheet()
        ed._mode_indicator.set_active("free")
        _free_marquee_on_editor(ed, 32, 32, 48, 48)
        ed._on_cut()
        assert ed.clipboard.has_pixels
        assert not ed._free_tool.has_block()
        assert ed.doc.surface.get_at((40, 40)) == pygame.Color(0, 0, 0, 0)
        assert any(isinstance(c, PixelClearCommand) for c in ed.commands._undo)

    def test_pixel_paste_switches_to_free(self):
        ed = _make_editor_with_sheet()
        ed._mode_indicator.set_active("free")
        _free_marquee_on_editor(ed, 32, 32, 48, 48)
        ed._on_copy()
        ed._mode_indicator.set_active("grid")
        ed._on_paste()
        assert ed.mode == "free"
        assert ed._free_tool._floating is not None

    def test_tile_paste_switches_to_grid(self):
        ed = _make_editor_with_sheet()
        ed.selection.replace([(1, 1)])
        ed._on_copy()
        assert not ed.clipboard.has_pixels
        ed._mode_indicator.set_active("regions")
        ed._on_paste()
        assert ed.mode == "grid"
        assert ed._active_tool is ed._paste_tool

    def test_duplicate_free_block(self):
        ed = _make_editor_with_sheet()
        ed._mode_indicator.set_active("free")
        _free_marquee_on_editor(ed, 32, 32, 48, 48)
        ed._on_duplicate()
        assert ed._free_tool._floating is not None
        vp = ed.viewport
        sx, sy = vp.world_to_screen(80, 80)
        ed._free_tool.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(sx), int(sy))}))
        assert ed.doc.surface.get_at((88, 88)) == pygame.Color(255, 0, 0, 255)

    def test_duplicate_grid_tiles(self):
        ed = _make_editor_with_sheet()
        ed.selection.replace([(1, 1)])
        ed._on_duplicate()
        assert ed._active_tool is ed._paste_tool

    def test_ctrl_d_shortcut(self):
        ed = _make_editor_with_sheet()
        ed.selection.replace([(1, 1)])
        old_mods = pygame.key.get_mods()
        try:
            pygame.key.set_mods(pygame.KMOD_CTRL)
            handled = ed.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_d}))
        finally:
            pygame.key.set_mods(old_mods)
        assert handled is True
        assert ed._active_tool is ed._paste_tool


def _slope_doc():
    """5x5 negative-slope chunk at (10, 10); column i has color (i*50, 0, 0)."""
    from plugins.sprite_editor.document import Document

    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    for i in range(5):
        surf.fill((i * 50, 0, 0, 255), Rect(10 + i, 10 + (4 - i), 1, 1))
    doc = Document(tile_size=(32, 32))
    doc.set_surface(surf)
    return doc


def _marquee(tool, viewport, x0, y0, x1, y1):
    sx, sy = viewport.world_to_screen(x0, y0)
    tool.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(sx), int(sy))}))
    ex, ey = viewport.world_to_screen(x1, y1)
    tool.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, {"pos": (int(ex), int(ey))}))
    tool.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (int(ex), int(ey))}))


class TestMirrorPixels:
    def test_h_mirror_abuts_right(self):
        doc = _slope_doc()
        dest = doc.mirror_pixels(Rect(10, 10, 5, 5), "h", 1)
        assert dest == Rect(15, 10, 5, 5)
        # slope continues straight: dest column mirrors source column
        for i in range(5):
            for j in range(5):
                assert doc.surface.get_at((15 + i, 10 + j)) == doc.surface.get_at((14 - i, 10 + j))
        # shared edge carries the same color (no seam)
        assert doc.surface.get_at((14, 10)) == doc.surface.get_at((15, 10))

    def test_h_mirror_left(self):
        doc = _slope_doc()
        assert doc.mirror_pixels(Rect(10, 10, 5, 5), "h", -1) == Rect(5, 10, 5, 5)
        for i in range(5):
            for j in range(5):
                assert doc.surface.get_at((5 + i, 10 + j)) == doc.surface.get_at((14 - i, 10 + j))

    def test_v_mirror_down(self):
        doc = _slope_doc()
        assert doc.mirror_pixels(Rect(10, 10, 5, 5), "v", 1) == Rect(10, 15, 5, 5)
        for j in range(5):
            assert doc.surface.get_at((10, 15 + j)) == doc.surface.get_at((10, 14 - j))

    def test_v_mirror_up(self):
        doc = _slope_doc()
        assert doc.mirror_pixels(Rect(10, 10, 5, 5), "v", -1) == Rect(10, 5, 5, 5)

    def test_source_kept(self):
        doc = _slope_doc()
        doc.mirror_pixels(Rect(10, 10, 5, 5), "h", 1)
        assert doc.surface.get_at((10, 14)) == pygame.Color(0, 0, 0, 255)

    def test_grows_canvas(self):
        doc = _slope_doc()
        dest = doc.mirror_pixels(Rect(60, 60, 4, 4), "h", 1)
        assert dest == Rect(64, 60, 4, 4)
        assert doc.surface.get_size() == (68, 64)

    def test_command_undo_redo_and_chain(self):
        from plugins.sprite_editor.commands import PixelMirrorCommand

        doc = _slope_doc()
        sel = _make_selection()
        first = PixelMirrorCommand(Rect(10, 10, 5, 5), "h", 1)
        first.apply(doc, sel)
        assert first.dest == Rect(15, 10, 5, 5)
        second = PixelMirrorCommand(first.dest, "h", 1)
        second.apply(doc, sel)
        assert second.dest == Rect(20, 10, 5, 5)
        assert doc.surface.get_at((22, 12)) == pygame.Color(100, 0, 0, 255)
        second.undo(doc, sel)
        assert second.dest is not None  # recorded, harmless after undo
        first.undo(doc, sel)
        assert doc.surface.get_at((17, 12)) == pygame.Color(0, 0, 0, 0)
        assert doc.surface.get_at((12, 12)) == pygame.Color(100, 0, 0, 255)


class TestFreeToolMirrorKeys:
    def _zoomed_tool(self, doc):
        tool, viewport, pushed, toasts = _make_tool(doc)
        tool.ctx.camera.zoom = 2.0  # 5px marquee clears the 8px-minimum
        return tool, viewport, pushed, toasts

    def test_h_stamps_and_chains(self):
        doc = _slope_doc()
        tool, viewport, pushed, _ = self._zoomed_tool(doc)
        _marquee(tool, viewport, 10, 10, 15, 15)
        assert tool._block == Rect(10, 10, 5, 5)
        tool.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_h}))
        assert tool._block == Rect(15, 10, 5, 5)
        assert len(pushed) == 1
        tool.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_h}))
        assert tool._block == Rect(20, 10, 5, 5)
        assert doc.surface.get_at((22, 12)) == pygame.Color(100, 0, 0, 255)

    def test_v_and_shift_side(self):
        doc = _slope_doc()
        tool, viewport, _, _ = self._zoomed_tool(doc)
        _marquee(tool, viewport, 10, 10, 15, 15)
        tool.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_v}))
        assert tool._block == Rect(10, 15, 5, 5)
        old_mods = pygame.key.get_mods()
        try:
            pygame.key.set_mods(pygame.KMOD_SHIFT)
            tool.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_h}))
        finally:
            pygame.key.set_mods(old_mods)
        assert tool._block == Rect(5, 15, 5, 5)

    def test_no_block_no_op(self):
        doc = _slope_doc()
        tool, _, pushed, _ = _make_tool(doc)
        assert tool.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_h})) is False
        assert pushed == []


def _checker_doc():
    """2x2 crisp quadrants at (32, 32): R G / B W."""
    from plugins.sprite_editor.document import Document

    surf = pygame.Surface((64, 64), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    surf.fill((255, 0, 0, 255), Rect(32, 32, 1, 1))
    surf.fill((0, 255, 0, 255), Rect(33, 32, 1, 1))
    surf.fill((0, 0, 255, 255), Rect(32, 33, 1, 1))
    surf.fill((255, 255, 255, 255), Rect(33, 33, 1, 1))
    doc = Document(tile_size=(32, 32))
    doc.set_surface(surf)
    return doc


class TestScalePixels:
    def test_nearest_upscale_exact(self):
        doc = _checker_doc()
        dest = doc.scale_pixels(Rect(32, 32, 2, 2), Rect(32, 32, 4, 4))
        assert dest == Rect(32, 32, 4, 4)
        assert doc.surface.get_at((32, 32)) == pygame.Color(255, 0, 0, 255)
        assert doc.surface.get_at((33, 32)) == pygame.Color(255, 0, 0, 255)
        assert doc.surface.get_at((34, 32)) == pygame.Color(0, 255, 0, 255)
        assert doc.surface.get_at((32, 34)) == pygame.Color(0, 0, 255, 255)
        assert doc.surface.get_at((35, 35)) == pygame.Color(255, 255, 255, 255)

    def test_source_cleared_outside_dest(self):
        doc = _checker_doc()
        doc.scale_pixels(Rect(32, 32, 2, 2), Rect(40, 40, 4, 4))
        assert doc.surface.get_at((32, 32)) == pygame.Color(0, 0, 0, 0)
        assert doc.surface.get_at((41, 41)) == pygame.Color(255, 0, 0, 255)
        assert doc.surface.get_at((42, 42)) == pygame.Color(255, 255, 255, 255)

    def test_min_size_clamped(self):
        doc = _checker_doc()
        assert doc.scale_pixels(Rect(32, 32, 2, 2), Rect(32, 32, 0, 0)) == Rect(32, 32, 1, 1)

    def test_grows_canvas(self):
        doc = _checker_doc()
        dest = doc.scale_pixels(Rect(32, 32, 2, 2), Rect(60, 60, 8, 8))
        assert dest == Rect(60, 60, 8, 8)
        assert doc.surface.get_size() == (68, 68)

    def test_command_undo_redo(self):
        from plugins.sprite_editor.commands import PixelScaleCommand

        doc = _checker_doc()
        sel = _make_selection()
        cmd = PixelScaleCommand(Rect(32, 32, 2, 2), Rect(32, 32, 4, 4))
        cmd.apply(doc, sel)
        assert cmd.dest == Rect(32, 32, 4, 4)
        assert doc.surface.get_at((34, 32)) == pygame.Color(0, 255, 0, 255)
        cmd.undo(doc, sel)
        assert doc.surface.get_at((34, 32)) == pygame.Color(0, 0, 0, 0)
        assert doc.surface.get_at((33, 32)) == pygame.Color(0, 255, 0, 255)
        cmd.redo(doc, sel)
        assert doc.surface.get_at((34, 32)) == pygame.Color(0, 255, 0, 255)


def _drag_handle(tool, viewport, handle_xy, to_world):
    tool.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": handle_xy}))
    ex, ey = viewport.world_to_screen(*to_world)
    tool.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, {"pos": (int(ex), int(ey))}))
    tool.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (int(ex), int(ey))}))


class TestFreeToolStretch:
    def _blocked_tool(self, doc):
        tool, viewport, pushed, toasts = _make_tool(doc)
        _marquee(tool, viewport, 32, 32, 48, 48)
        assert tool._block == Rect(32, 32, 16, 16)
        pushed.clear()
        return tool, viewport, pushed, toasts

    def _handle_pos(self, tool, name):
        rect = tool._block_screen_rect()
        assert rect is not None
        if name == "r":
            return (rect.right, rect.centery)
        if name == "t":
            return (rect.centerx, rect.y)
        return (rect.right, rect.bottom)  # br

    def test_edge_drags_single_axis(self):
        from plugins.sprite_editor.commands import PixelScaleCommand

        doc = _make_doc()
        tool, viewport, pushed, _ = self._blocked_tool(doc)
        _drag_handle(tool, viewport, self._handle_pos(tool, "r"), (80, 40))
        assert tool._drag is None
        assert len(pushed) == 1 and isinstance(pushed[0], PixelScaleCommand)
        assert tool._block == Rect(32, 32, 48, 16)
        assert doc.surface.get_at((70, 40)) == pygame.Color(255, 0, 0, 255)

    def test_top_edge_moves_y(self):
        doc = _make_doc()
        tool, viewport, pushed, _ = self._blocked_tool(doc)
        _drag_handle(tool, viewport, self._handle_pos(tool, "t"), (40, 16))
        assert tool._block == Rect(32, 16, 16, 32)
        assert doc.surface.get_at((40, 20)) == pygame.Color(255, 0, 0, 255)
        assert doc.surface.get_at((40, 44)) == pygame.Color(255, 0, 0, 255)

    def test_corner_scales_both_axes(self):
        doc = _make_doc()
        tool, viewport, pushed, _ = self._blocked_tool(doc)
        _drag_handle(tool, viewport, self._handle_pos(tool, "br"), (80, 64))
        assert tool._block == Rect(32, 32, 48, 32)

    def test_shift_locks_aspect(self):
        doc = _make_doc()
        tool, viewport, pushed, _ = self._blocked_tool(doc)
        old_mods = pygame.key.get_mods()
        try:
            pygame.key.set_mods(pygame.KMOD_SHIFT)
            _drag_handle(tool, viewport, self._handle_pos(tool, "br"), (80, 40))
        finally:
            pygame.key.set_mods(old_mods)
        # x-ratio 48/16 = 3 applied to both axes from the anchored corner
        assert tool._block == Rect(32, 32, 48, 48)

    def test_escape_cancels(self):
        doc = _make_doc()
        tool, viewport, pushed, _ = self._blocked_tool(doc)
        tool.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                               {"button": 1, "pos": self._handle_pos(tool, "r")}))
        assert tool._drag == "resize"
        tool.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}))
        assert tool._drag is None
        assert pushed == []
        assert tool._block == Rect(32, 32, 16, 16)

    def test_noop_keeps_block(self):
        doc = _make_doc()
        tool, viewport, pushed, _ = self._blocked_tool(doc)
        pos = self._handle_pos(tool, "r")
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos}))
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": pos}))
        assert pushed == []
        assert tool._block == Rect(32, 32, 16, 16)


class TestFreeToolMove:
    def _select_block(self, tool, viewport):
        sx, sy = viewport.world_to_screen(32, 32)
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(sx), int(sy))}))
        ex, ey = viewport.world_to_screen(48, 48)
        tool.handle_event(pygame.event.Event(pygame.MOUSEMOTION, {"pos": (int(ex), int(ey))}))
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (int(ex), int(ey))}))
        assert tool._block is not None

    def test_drag_moves_pixels_and_clears(self):
        from plugins.sprite_editor.commands import PixelMoveCommand

        doc = _make_doc()
        tool, viewport, pushed, _ = _make_tool(doc)
        self._select_block(tool, viewport)
        # grab inside the block and drag +32px
        gx, gy = viewport.world_to_screen(40, 40)
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(gx), int(gy))}))
        assert tool._drag == "move"
        hx, hy = viewport.world_to_screen(72, 40)
        tool.handle_event(pygame.event.Event(pygame.MOUSEMOTION, {"pos": (int(hx), int(hy))}))
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (int(hx), int(hy))}))
        assert any(isinstance(c, PixelMoveCommand) for c in pushed)
        assert tool._block is None
        assert doc.surface.get_at((72, 40)) == pygame.Color(255, 0, 0, 255)
        assert doc.surface.get_at((40, 40)) == pygame.Color(0, 0, 0, 0)

    def test_escape_cancels_move(self):
        doc = _make_doc()
        tool, viewport, pushed, _ = _make_tool(doc)
        self._select_block(tool, viewport)
        gx, gy = viewport.world_to_screen(40, 40)
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(gx), int(gy))}))
        tool.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE}))
        assert tool._drag is None
        assert pushed == []
        assert doc.surface.get_at((40, 40)) == pygame.Color(255, 0, 0, 255)


class TestFreeToolRegion:
    def test_enter_stores_region(self, tmp_path):
        from plugins.sprite_editor.commands import RegionAddCommand

        doc = _make_doc()
        tool, viewport, pushed, _ = _make_tool(doc)
        sx, sy = viewport.world_to_screen(32, 32)
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (int(sx), int(sy))}))
        ex, ey = viewport.world_to_screen(48, 48)
        tool.handle_event(pygame.event.Event(pygame.MOUSEMOTION, {"pos": (int(ex), int(ey))}))
        tool.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": (int(ex), int(ey))}))
        tool.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN}))
        adds = [c for c in pushed if isinstance(c, RegionAddCommand)]
        assert len(adds) == 1
        assert doc.region_by_id(adds[0].region.id) is not None
        # free-size export path yields the exact crop
        from plugins.sprite_editor.region_export import export_all_regions

        out = export_all_regions(doc.surface, doc.regions, tmp_path)
        assert len(out) == 1
        crop = pygame.image.load(str(out[0]))
        assert tuple(crop.get_size()) == (16, 16)
