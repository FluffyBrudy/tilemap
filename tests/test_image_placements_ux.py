"""Interaction tests for image-copy select/move/duplicate/remove/cycle."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pygame
import pytest
from pygame import Rect

from layers import Layer
from widgets.tile_grid import TileGrid
from widgets.ui.tool_manager import ToolKind


@pytest.fixture(autouse=True)
def init_pygame(monkeypatch):
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


class FakeManager:
    def __init__(self, layer):
        from layers import LayerManager

        self._mgr = LayerManager()
        self._mgr.layers.append(layer)
        self._mgr.active_layer_idx = 0

    def get_active_layer(self):
        return self._mgr.get_active_layer()


class FakeTools:
    def is_active(self, kind):
        return kind == ToolKind.SELECT


class FakeNotes:
    def __init__(self):
        self.messages = []

    def notify(self, msg, duration=2.0, color=None):
        self.messages.append(msg)


class FakeTilemap:
    render_scale = 1.0
    tile_size = (16, 16)

    def __init__(self, layer):
        self.layer_manager = FakeManager(layer)
        self.history = []

    def capture_history(self, label):
        self.history.append(label)


class FakeEditor:
    node_editing_mode = False
    show_nodes = False

    def __init__(self, layer):
        self.tilemap = FakeTilemap(layer)
        self.tool_manager = FakeTools()
        self.notifications = FakeNotes()


def make_grid(layer, monkeypatch):
    grid = TileGrid(FakeEditor(layer), Rect(0, 0, 800, 600))
    grid.zoom_level = 1.0
    grid.scroll_x = 0.0
    grid.scroll_y = 0.0
    return grid


def bg_layer():
    return Layer(
        "BG",
        layer_type="image",
        image_path="bg.png",
        image_rect={"x": 0, "y": 0, "w": 100, "h": 100},
    )


def click(grid, monkeypatch, pos):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
    grid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
    grid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos))


def key(grid, monkeypatch, code, pos=(0, 0)):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
    grid.handle_event(pygame.event.Event(pygame.KEYDOWN, key=code))


class TestPlacementCycling:
    def test_click_cycles_topmost_then_beneath_then_base(self, monkeypatch):
        layer = bg_layer()
        layer.add_placement({"x": 10, "y": 10, "w": 100, "h": 100})  # pid 2 over seed 1 over base
        grid = make_grid(layer, monkeypatch)
        # Stack at (50, 50) topmost-first: [2, 1, base].
        click(grid, monkeypatch, (50, 50))
        assert grid._image_placement_pid == 2
        click(grid, monkeypatch, (50, 50))
        assert grid._image_placement_pid == 1
        click(grid, monkeypatch, (50, 50))
        assert grid._image_placement_pid is None
        click(grid, monkeypatch, (50, 50))
        assert grid._image_placement_pid == 2

    def test_click_empty_space_clears_selection(self, monkeypatch):
        layer = bg_layer()
        layer.add_placement({"x": 10, "y": 10, "w": 50, "h": 50})
        grid = make_grid(layer, monkeypatch)
        click(grid, monkeypatch, (20, 20))
        assert grid._image_placement_pid == 2
        click(grid, monkeypatch, (700, 500))
        assert grid._image_placement_pid is None


class TestDuplicateRemove:
    def test_d_duplicates_selected_with_offset_and_history(self, monkeypatch):
        layer = bg_layer()
        grid = make_grid(layer, monkeypatch)
        click(grid, monkeypatch, (50, 50))  # selects base (only rect)
        key(grid, monkeypatch, pygame.K_d, pos=(50, 50))
        assert [p.pid for p in layer.image_placements] == [1, 2]
        assert grid._image_placement_pid == 2
        assert layer.get_placement(2).x == 16
        assert "Duplicate Image Copy" in grid.editor.tilemap.history

    def test_delete_removes_selected_copy_not_base(self, monkeypatch):
        layer = bg_layer()
        layer.add_placement({"x": 10, "y": 10, "w": 50, "h": 50})
        grid = make_grid(layer, monkeypatch)
        click(grid, monkeypatch, (20, 20))
        assert grid._image_placement_pid == 2
        key(grid, monkeypatch, pygame.K_DELETE, pos=(20, 20))
        assert layer.get_placement(2) is None
        assert grid._image_placement_pid is None
        assert "Remove Image Copy" in grid.editor.tilemap.history
        # Base selection + Delete is a no-op (layers die elsewhere).
        click(grid, monkeypatch, (5, 120))
        key(grid, monkeypatch, pygame.K_DELETE, pos=(5, 120))
        assert layer.image_rect == {"x": 0, "y": 0, "w": 100, "h": 100}


class TestPlacementDrag:
    def test_drag_moves_copy_and_captures_copy_history(self, monkeypatch):
        layer = bg_layer()
        pid = layer.add_placement({"x": 200, "y": 200, "w": 50, "h": 50})
        grid = make_grid(layer, monkeypatch)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (210, 210))
        grid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(210, 210)))
        assert grid._image_placement_pid == pid
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (230, 240))
        grid.handle_event(
            pygame.event.Event(pygame.MOUSEMOTION, pos=(230, 240), rel=(20, 30), buttons=(1, 0, 0))
        )
        moved = layer.get_placement(pid)
        assert (moved.x, moved.y) == (220, 230)
        assert "Edit Image Copy" in grid.editor.tilemap.history
        grid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(230, 240)))

    def test_escape_restores_copy(self, monkeypatch):
        layer = bg_layer()
        pid = layer.add_placement({"x": 200, "y": 200, "w": 50, "h": 50})
        grid = make_grid(layer, monkeypatch)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (210, 210))
        grid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(210, 210)))
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (260, 260))
        grid.handle_event(
            pygame.event.Event(pygame.MOUSEMOTION, pos=(260, 260), rel=(50, 50), buttons=(1, 0, 0))
        )
        assert (layer.get_placement(pid).x, layer.get_placement(pid).y) != (200, 200)
        grid.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert (layer.get_placement(pid).x, layer.get_placement(pid).y) == (200, 200)


def drag_to(grid, monkeypatch, start, end):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: start)
    grid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=start))
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: end)
    grid.handle_event(
        pygame.event.Event(pygame.MOUSEMOTION, pos=end, rel=(end[0] - start[0], end[1] - start[1]), buttons=(1, 0, 0))
    )


class TestShiftGridSnap:
    def test_shift_drag_snaps_to_tile_grid(self, monkeypatch):
        layer = bg_layer()
        pid = layer.add_placement({"x": 200, "y": 200, "w": 50, "h": 50})
        grid = make_grid(layer, monkeypatch)
        monkeypatch.setattr(pygame.key, "get_mods", lambda: pygame.KMOD_SHIFT)
        drag_to(grid, monkeypatch, (210, 210), (227, 233))
        moved = layer.get_placement(pid)
        assert (moved.x, moved.y) == (224, 224)
        grid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(227, 233)))

    def test_free_drag_keeps_exact_pixels(self, monkeypatch):
        layer = bg_layer()
        pid = layer.add_placement({"x": 200, "y": 200, "w": 50, "h": 50})
        grid = make_grid(layer, monkeypatch)
        monkeypatch.setattr(pygame.key, "get_mods", lambda: 0)
        drag_to(grid, monkeypatch, (210, 210), (227, 233))
        moved = layer.get_placement(pid)
        assert (moved.x, moved.y) == (217, 223)
        grid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(227, 233)))


class TestTouchHint:
    def test_touching_base_reports_hint(self, monkeypatch):
        layer = bg_layer()
        pid = layer.add_placement({"x": 200, "y": 40, "w": 50, "h": 50})
        grid = make_grid(layer, monkeypatch)
        drag_to(grid, monkeypatch, (210, 50), (110, 60))
        moved = layer.get_placement(pid)
        assert (moved.x, moved.y) == (100, 50)
        assert grid._image_snap_hint == "touches base"
        grid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(110, 60)))
        assert grid._image_snap_hint is None

    def test_gap_reports_no_hint(self, monkeypatch):
        layer = bg_layer()
        pid = layer.add_placement({"x": 200, "y": 40, "w": 50, "h": 50})
        grid = make_grid(layer, monkeypatch)
        drag_to(grid, monkeypatch, (210, 50), (150, 60))
        assert layer.get_placement(pid).x == 140
        assert grid._image_snap_hint is None
        grid.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(150, 60)))
