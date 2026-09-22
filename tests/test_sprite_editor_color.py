"""Color pick and replace: remap, command, tool flow."""

import pygame  # noqa: E402
import pytest  # noqa: E402
from pygame import Rect, Surface  # noqa: E402

from plugins.sprite_editor.commands import ColorReplaceCommand  # noqa: E402
from plugins.sprite_editor.document import Document  # noqa: E402
from plugins.sprite_editor.selection import Selection  # noqa: E402
from plugins.sprite_editor.tools import (  # noqa: E402
    _hex_of,
    _parse_hex,
    ColorTool,
)


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))


def solid(w, h, color):
    s = Surface((w, h), pygame.SRCALPHA)
    s.fill(color)
    return s


def split_canvas():
    doc = Document(tile_size=(32, 32))
    surf = Surface((64, 32), pygame.SRCALPHA)
    surf.fill((200, 0, 0, 255), Rect(0, 0, 32, 32))
    surf.fill((0, 0, 200, 255), Rect(32, 0, 32, 32))
    doc.set_surface(surf)
    return doc


class TestHex:
    def test_roundtrip_opaque(self):
        assert _parse_hex(_hex_of((200, 0, 0, 255))) == (200, 0, 0, 255)

    def test_roundtrip_alpha(self):
        assert _parse_hex(_hex_of((1, 2, 3, 0))) == (1, 2, 3, 0)
        assert _parse_hex("#ff000080") == (255, 0, 0, 128)

    def test_bad_hex(self):
        assert _parse_hex("nope") is None
        assert _parse_hex("#12345") is None


class TestRemap:
    def test_exact_full_canvas(self):
        doc = split_canvas()
        n = doc.remap_pixels((200, 0, 0, 255), (0, 200, 0, 255))
        assert n == 32 * 32
        assert doc.surface.get_at((5, 5)) == (0, 200, 0, 255)
        assert doc.surface.get_at((40, 5))[:3] == (0, 0, 200)

    def test_transparent_needs_exact(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(32, 32, (0, 0, 0, 0)))
        assert doc.remap_pixels((0, 0, 0, 0), (255, 0, 0, 255)) == 32 * 32
        doc2 = split_canvas()
        assert doc2.remap_pixels((0, 0, 0, 0), (255, 0, 0, 255)) == 0

    def test_solid_to_transparent(self):
        doc = split_canvas()
        n = doc.remap_pixels((200, 0, 0, 255), (0, 0, 0, 0))
        assert n == 32 * 32
        assert doc.surface.get_at((5, 5)).a == 0
        assert doc.surface.get_at((40, 5)).a == 255

    def test_tolerance(self):
        doc = Document(tile_size=(32, 32))
        doc.set_surface(solid(16, 16, (200, 0, 0, 255)))
        assert doc.remap_pixels((205, 0, 0, 255), (0, 200, 0, 255)) == 0
        doc.set_surface(solid(16, 16, (200, 0, 0, 255)))
        assert doc.remap_pixels((205, 0, 0, 255), (0, 200, 0, 255), tolerance=10) == 16 * 16

    def test_rect_scope(self):
        doc = split_canvas()
        n = doc.remap_pixels((200, 0, 0, 255), (0, 200, 0, 255), rect=Rect(0, 0, 16, 16))
        assert n == 16 * 16
        assert doc.surface.get_at((20, 5))[:3] == (200, 0, 0)

    def test_flood(self):
        doc = split_canvas()
        n = doc.remap_pixels(
            (200, 0, 0, 255), (0, 200, 0, 255),
            contiguous=True, seed=(5, 5),
        )
        assert n == 32 * 32
        assert doc.surface.get_at((40, 5))[:3] == (0, 0, 200)

    def test_flood_seed_miss(self):
        doc = split_canvas()
        assert doc.remap_pixels(
            (200, 0, 0, 255), (0, 200, 0, 255),
            contiguous=True, seed=(40, 5),
        ) == 0
        assert doc.remap_pixels(
            (200, 0, 0, 255), (0, 200, 0, 255), contiguous=True, seed=None
        ) == 0

    def test_dry_run_keeps_pixels(self):
        doc = split_canvas()
        n = doc.remap_pixels((200, 0, 0, 255), (0, 200, 0, 255), dry_run=True)
        assert n == 32 * 32
        assert doc.surface.get_at((5, 5))[:3] == (200, 0, 0)


class TestColorReplaceCommand:
    def test_apply_undo_redo(self):
        from plugins.sprite_editor.commands import CommandStack

        doc = split_canvas()
        sel = Selection()
        stack = CommandStack(10)
        stack.push(ColorReplaceCommand((200, 0, 0, 255), (0, 200, 0, 255)), doc, sel)
        assert doc.surface.get_at((5, 5))[:3] == (0, 200, 0)
        stack.undo(doc, sel)
        assert doc.surface.get_at((5, 5))[:3] == (200, 0, 0)
        stack.redo(doc, sel)
        assert doc.surface.get_at((5, 5))[:3] == (0, 200, 0)


class FakeViewport:
    def __init__(self):
        self.rect = Rect(0, 0, 400, 400)
        self.content_rect = Rect(0, 0, 400, 400)

    def screen_to_world(self, x, y):
        return (float(x), float(y))


class FakeCamera:
    def world_to_screen(self, x, y):
        return (float(x), float(y))


class FakeCtx:
    def __init__(self, doc):
        from plugins.sprite_editor.clipboard import Clipboard
        from plugins.sprite_editor.commands import CommandStack

        self.doc = doc
        self.selection = Selection()
        self.camera = FakeCamera()
        self.viewport = FakeViewport()
        self.clipboard = Clipboard()
        self.commands = CommandStack(10)
        self.notes = []

    def status(self, msg, detail=""):
        self.notes.append((msg, detail))

    def toast(self, msg):
        self.notes.append(msg)

    def set_tool(self, name):
        pass


class TestColorTool:
    def test_pick_and_apply_full(self):
        doc = split_canvas()
        ctx = FakeCtx(doc)
        tool = ColorTool(ctx)
        tool.enter()
        assert tool.pick_source((5, 5)) is True
        assert tool._src == (200, 0, 0, 255)
        tool._dst = (0, 200, 0, 255)
        tool._apply()
        assert doc.surface.get_at((5, 5))[:3] == (0, 200, 0)
        assert doc.surface.get_at((40, 5))[:3] == (0, 0, 200)

    def test_pick_outside_canvas(self):
        doc = split_canvas()
        ctx = FakeCtx(doc)
        tool = ColorTool(ctx)
        assert tool.pick_source((500, 500)) is False
        assert tool._src is None

    def test_marquee_scope(self):
        doc = split_canvas()
        ctx = FakeCtx(doc)
        tool = ColorTool(ctx)
        tool._src = (200, 0, 0, 255)
        tool._dst = (0, 200, 0, 255)
        tool._scope = "marquee"
        tool._marquee = [0.0, 0.0, 16.0, 16.0]
        tool._apply()
        assert doc.surface.get_at((5, 5))[:3] == (0, 200, 0)
        assert doc.surface.get_at((20, 5))[:3] == (200, 0, 0)

    def test_flood_needs_seed(self):
        doc = split_canvas()
        ctx = FakeCtx(doc)
        tool = ColorTool(ctx)
        tool._src = (200, 0, 0, 255)
        tool._dst = (0, 200, 0, 255)
        tool._scope = "flood"
        tool._apply()
        assert doc.surface.get_at((5, 5))[:3] == (200, 0, 0)
        tool._seed = (5, 5)
        tool._apply()
        assert doc.surface.get_at((5, 5))[:3] == (0, 200, 0)
