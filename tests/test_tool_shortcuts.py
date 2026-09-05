"""Tests for tool shortcuts (V/B/R/I) and layer list keys."""

import os
import sys
from pathlib import Path

import pygame
import pytest
from pygame import Rect

from widgets.ui.tool_manager import ToolKind, ToolManager

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

pygame.init()
pygame.display.set_mode((1, 1))


@pytest.fixture(autouse=True)
def _reinit_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield


class FakeTilemap:
    tile_size = (32, 32)
    map_size = (10, 10)
    offset = (0, 0)


def make_grid():
    from widgets.tile_grid import TileGrid

    ed = types_editor()
    g = TileGrid.__new__(TileGrid)
    g.editor = ed
    g.rect = Rect(-10000, -10000, 20000, 20000)
    g.hover_cell = None
    g.is_panning = False

    class NoScroll:
        def handle_event(self, event):
            return False

    g._v_scroll = NoScroll()
    g._h_scroll = NoScroll()
    g._handle_image_layer_event = lambda event: False
    return g, ed


def types_editor():
    class E:
        node_editing_mode = False
        show_nodes = False

    ed = E()
    ed.tool_manager = ToolManager()
    ed.tilemap = FakeTilemap()
    return ed


def key_event(key):
    return pygame.event.Event(pygame.KEYDOWN, {"key": key, "unicode": ""})


class TestToolShortcuts:
    def test_v_toggles_select(self, monkeypatch):
        g, ed = make_grid()
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert g.handle_event(key_event(pygame.K_v)) is True
        assert ed.tool_manager.is_active(ToolKind.SELECT)
        g.handle_event(key_event(pygame.K_v))
        assert not ed.tool_manager.is_active(ToolKind.SELECT)

    def test_b_returns_to_paint(self, monkeypatch):
        g, ed = make_grid()
        ed.tool_manager.activate(ToolKind.ERASER)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert g.handle_event(key_event(pygame.K_b)) is True
        assert ed.tool_manager.active is None

    def test_r_toggles_eraser(self, monkeypatch):
        g, ed = make_grid()
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        g.handle_event(key_event(pygame.K_r))
        assert ed.tool_manager.is_active(ToolKind.ERASER)

    def test_i_toggles_pick(self, monkeypatch):
        g, ed = make_grid()
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        g.handle_event(key_event(pygame.K_i))
        assert ed.tool_manager.is_active(ToolKind.PICK)
