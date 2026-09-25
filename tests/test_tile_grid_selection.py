"""
Tests for TileGrid selection/clipboard/move/delete features added in PR.

Covers:
- Selection state initialisation (selection_rect, is_selecting, etc.)
- _point_in_selection
- _finalize_selection (collapses single-cell drags)
- copy_selection (tile layer)
- paste_clipboard (tile layer)
- delete_selection (tile layer)
- _begin_move / cancel_move
- commit_move (tile layer)
- Initial state for new fields (eraser_mode, select_mode, _prev_tool)
"""

import os
import sys
import types
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


# ---------------------------------------------------------------------------
# Minimal fakes
# ---------------------------------------------------------------------------


class FakeNotifications:
    def __init__(self):
        self.messages = []

    def success(self, msg):
        self.messages.append(("success", msg))

    def notify(self, msg):
        self.messages.append(("notify", msg))


class FakeTileLayer:
    layer_type = "tile"

    def __init__(self):
        self._tiles = {}

    def get_tile(self, pos):
        return self._tiles.get(pos)

    def set_tile(self, pos, tile):
        self._tiles[pos] = tile

    def remove_tile(self, pos):
        if pos in self._tiles:
            del self._tiles[pos]
            return True
        return False

    def get_all_objects(self):
        return {}

    def add_object(self, pos, data):
        pass

    def remove_object(self, obj_id):
        pass

    def autotile_at_pos(self, pos, rules):
        pass


class FakeObjectLayer:
    layer_type = "object"

    def __init__(self):
        self._objects = {}
        self._next_id = 1

    def get_tile(self, pos):
        return None

    def set_tile(self, pos, tile):
        pass

    def remove_tile(self, pos):
        return False

    def get_all_objects(self):
        return dict(self._objects)

    def add_object(self, pos, data):
        oid = self._next_id
        self._next_id += 1
        self._objects[oid] = data
        return oid

    def remove_object(self, obj_id):
        self._objects.pop(obj_id, None)


class FakeLayerManager:
    def __init__(self, layer):
        self._layer = layer

    def get_active_layer(self):
        return self._layer


class FakeTilemap:
    def __init__(self, layer):
        self.tile_size = (32, 32)
        self.render_scale = 1.0
        self.map_size = (20, 20)
        self.offset = (0, 0)
        self.initialized = False
        self.layer_manager = FakeLayerManager(layer)
        self._history = []

    def capture_history(self, label):
        self._history.append(label)

    def update_map_size(self):
        pass


class FakeSaveInput:
    active = False


class FakeTilesetWidget:
    def __init__(self):
        self.selected_calls = []

    def select_tile_by_variant(self, ttype, variant):
        self.selected_calls.append((ttype, variant))


class FakeEditor:
    def __init__(self, layer=None):
        if layer is None:
            layer = FakeTileLayer()
        self.tilemap = FakeTilemap(layer)
        self.pan_mode = False
        self.select_mode = False
        self.eraser_mode = False
        self.autotile_mode = False
        self.notifications = FakeNotifications()
        self.save_input = FakeSaveInput()
        self.tileset_widget = FakeTilesetWidget()
        self.autotiler = None


def make_grid(layer=None):
    from widgets.tile_grid import TileGrid

    editor = FakeEditor(layer)
    rect = Rect(0, 0, 800, 600)
    return TileGrid(editor, rect)


# ---------------------------------------------------------------------------
# _point_in_selection
# ---------------------------------------------------------------------------


class TestPointInSelection:
    @pytest.mark.parametrize(
        ("rect", "point", "expected"),
        [
            (None, (3, 3), False),
            ((2, 2, 5, 5), (3, 3), True),
            ((2, 2, 5, 5), (2, 2), True),
            ((2, 2, 5, 5), (5, 5), True),
            ((2, 2, 5, 5), (6, 3), False),
            ((2, 2, 5, 5), (1, 3), False),
        ],
    )
    def test_point_membership(self, rect, point, expected):
        g = make_grid()
        g.selection_rect = rect
        assert g._point_in_selection(point) is expected


# ---------------------------------------------------------------------------
# _finalize_selection
# ---------------------------------------------------------------------------


class TestFinalizeSelection:
    def test_single_cell_collapses_multi_cell_keeps(self):
        g = make_grid()
        g.selection_rect = (3, 3, 3, 3)
        g._finalize_selection()
        assert g.selection_rect is None
        g.selection_rect = (1, 1, 4, 4)
        g._finalize_selection()
        assert g.selection_rect == (1, 1, 4, 4)


# ---------------------------------------------------------------------------
# copy_selection (tile layer)
# ---------------------------------------------------------------------------


class TestCopySelection:
    def test_copy_populates_clipboard(self):
        layer = FakeTileLayer()
        layer.set_tile((0, 0), {"pos": (0, 0), "ttype": 0, "variant": 1})
        layer.set_tile((1, 0), {"pos": (1, 0), "ttype": 0, "variant": 2})
        layer.set_tile((0, 1), {"pos": (0, 1), "ttype": 0, "variant": 3})
        g = make_grid(layer)
        g.selection_rect = (0, 0, 1, 1)
        g.copy_selection()
        assert g.clipboard is not None
        assert len(g.clipboard["tiles"]) == 3
        assert (0, 0) in g.clipboard["tiles"]  # relative positions
        assert g.clipboard["layer_type"] == "tile"
        assert g.clipboard["origin"] == (0, 0)

        g.selection_rect = (9, 9, 10, 10)  # empty region
        g.copy_selection()
        assert g.clipboard is None


# ---------------------------------------------------------------------------
# paste_clipboard (tile layer)
# ---------------------------------------------------------------------------


class TestPasteClipboard:
    def _setup_clipboard(self):
        layer = FakeTileLayer()
        layer.set_tile((2, 2), {"pos": (2, 2), "ttype": 0, "variant": 7})
        g = make_grid(layer)
        g.selection_rect = (2, 2, 3, 3)
        g.copy_selection()
        return g

    def test_paste_places_tiles(self):
        g = self._setup_clipboard()
        layer = g.editor.tilemap.layer_manager.get_active_layer()
        g.paste_clipboard((5, 5))
        tile = layer.get_tile((5, 5))
        assert tile is not None
        assert tile["variant"] == 7

    def test_paste_layer_mismatch_notifies(self):
        """Pasting tile data onto an object layer should notify the user."""
        tile_layer = FakeTileLayer()
        tile_layer.set_tile((0, 0), {"pos": (0, 0), "ttype": 0, "variant": 1})
        g = make_grid(tile_layer)
        g.selection_rect = (0, 0, 0, 0)
        g.copy_selection()

        # Switch to object layer
        obj_layer = FakeObjectLayer()
        g.editor.tilemap.layer_manager._layer = obj_layer

        g.paste_clipboard((0, 0))
        msgs = [m[1] for m in g.editor.notifications.messages]
        assert any("mismatch" in m.lower() or "cannot" in m.lower() for m in msgs)


# ---------------------------------------------------------------------------
# delete_selection
# ---------------------------------------------------------------------------


class TestDeleteSelection:
    def test_delete_removes_rect_contents_only(self):
        layer = FakeTileLayer()
        layer.set_tile((1, 1), {"pos": (1, 1), "ttype": 0, "variant": 1})
        layer.set_tile((2, 1), {"pos": (2, 1), "ttype": 0, "variant": 2})
        layer.set_tile((5, 5), {"pos": (5, 5), "ttype": 0, "variant": 9})
        g = make_grid(layer)
        g.selection_rect = (1, 1, 2, 1)
        g.delete_selection()
        assert layer.get_tile((1, 1)) is None
        assert layer.get_tile((2, 1)) is None
        assert layer.get_tile((5, 5)) is not None
        assert g.selection_rect is None


# ---------------------------------------------------------------------------
# _begin_move and cancel_move
# ---------------------------------------------------------------------------


class TestBeginAndCancelMove:
    def test_begin_saves_origin_state(self):
        g = make_grid()
        g.selection_rect = (1, 1, 3, 3)
        g.move_delta = (5, 5)
        g._begin_move((100, 200))
        assert g.is_moving is True
        assert g.move_start_mouse == (100, 200)
        assert g.move_origin_rect == (1, 1, 3, 3)
        assert g.move_delta == (0, 0)

    def test_cancel_restores_everything(self):
        g = make_grid()
        g.selection_rect = (1, 1, 3, 3)
        g._begin_move((50, 50))
        g.selection_rect = (2, 2, 4, 4)  # simulate drag update
        g.move_delta = (3, 2)
        g.cancel_move()
        assert g.is_moving is False
        assert g.selection_rect == (1, 1, 3, 3)
        assert g.move_delta == (0, 0)


# ---------------------------------------------------------------------------
# commit_move (tile layer)
# ---------------------------------------------------------------------------


class TestCommitMove:
    def test_commit_move_journey(self):
        layer = FakeTileLayer()
        layer.set_tile((1, 1), {"pos": (1, 1), "ttype": 0, "variant": 42})
        g = make_grid(layer)
        g.selection_rect = (1, 1, 1, 1)
        g._begin_move((0, 0))
        g.move_delta = (0, 0)
        g.commit_move()  # zero delta: tiles stay, moving ends
        assert layer.get_tile((1, 1)) is not None

        g._begin_move((0, 0))
        g.move_delta = (0, 1)
        g.commit_move()
        assert layer.get_tile((1, 1)) is None
        moved = layer.get_tile((1, 2))
        assert moved is not None
        assert moved["variant"] == 42  # variant unchanged
        assert g.selection_rect == (1, 2, 1, 2)
        assert g.is_moving is False
        assert g.move_start_mouse is None
        assert g.move_origin_rect is None

    def test_commit_move_records_history(self):
        layer = FakeTileLayer()
        layer.set_tile((0, 0), {"pos": (0, 0), "ttype": 0, "variant": 1})
        g = make_grid(layer)
        g.selection_rect = (0, 0, 0, 0)
        g._begin_move((0, 0))
        g.move_delta = (1, 0)
        g.commit_move()
        assert "Move Selection" in g.editor.tilemap._history


# ---------------------------------------------------------------------------
# empty-state safety: no-ops must never raise
# ---------------------------------------------------------------------------


class TestEmptyStateSafety:
    def test_empty_operations_are_safe(self):
        g = make_grid()
        g._finalize_selection()
        g.copy_selection()
        g.paste_clipboard((0, 0))
        g.delete_selection()
        g.cancel_move()
        g.commit_move()
        assert g.selection_rect is None
        assert g.clipboard is None


# ---------------------------------------------------------------------------
# Rubber-band lifecycle: clicks never destroy committed state
# ---------------------------------------------------------------------------


def _rig_select(grid, monkeypatch):
    from widgets.ui.tool_manager import ToolKind

    grid.editor.tool_manager = types.SimpleNamespace(
        is_active=lambda kind: kind == ToolKind.SELECT
    )
    grid.editor.node_editing_mode = False
    grid.editor.show_nodes = False
    return grid


def _cell_center(grid, cell):
    return grid.cell_screen_rect(*cell).center


def _down(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos})


def _up(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": 1, "pos": pos})


def _motion(pos):
    return pygame.event.Event(
        pygame.MOUSEMOTION, {"pos": pos, "rel": (0, 0), "buttons": (0, 0, 0)}
    )


def _key(key):
    return pygame.event.Event(pygame.KEYDOWN, {"key": key, "unicode": ""})


class TestRubberBandLifecycle:
    def test_click_without_drag_preserves_selection(self, monkeypatch):
        g = _rig_select(make_grid(), monkeypatch)
        g.selection_rect = (2, 2, 5, 5)
        pos = _cell_center(g, (0, 0))
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
        g.handle_event(_motion(pos))  # motion only tracks hover; unconsumed
        assert g.hover_cell == (0, 0)
        assert g.handle_event(_down(pos)) is True
        assert g.handle_event(_up(pos)) is True
        assert g.selection_rect == (2, 2, 5, 5)
        assert g.is_selecting is False

    def test_drag_replaces_selection(self, monkeypatch):
        g = _rig_select(make_grid(), monkeypatch)
        g.selection_rect = (2, 2, 5, 5)
        start = _cell_center(g, (0, 0))
        end = _cell_center(g, (3, 3))
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: start)
        g.handle_event(_motion(start))
        assert g.handle_event(_down(start)) is True
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: end)
        g.handle_event(_motion(end))
        assert g.handle_event(_up(end)) is True
        assert g.selection_rect == (0, 0, 3, 3)

    def test_no_drag_leaves_no_selection(self, monkeypatch):
        g = _rig_select(make_grid(), monkeypatch)
        assert g.selection_rect is None
        pos = _cell_center(g, (1, 1))
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
        g.handle_event(_motion(pos))  # motion only tracks hover; unconsumed
        assert g.hover_cell == (1, 1)
        assert g.handle_event(_down(pos)) is True
        assert g.handle_event(_up(pos)) is True
        assert g.selection_rect is None

    def test_escape_clears(self, monkeypatch):
        g = _rig_select(make_grid(), monkeypatch)
        g.selection_rect = (2, 2, 5, 5)
        monkeypatch.setattr(pygame.key, "get_mods", lambda: 0)
        assert g.handle_event(_key(pygame.K_ESCAPE)) is True
        assert g.selection_rect is None

    def test_return_clears(self, monkeypatch):
        g = _rig_select(make_grid(), monkeypatch)
        g.selection_rect = (2, 2, 5, 5)
        monkeypatch.setattr(pygame.key, "get_mods", lambda: 0)
        assert g.handle_event(_key(pygame.K_RETURN)) is True
        assert g.selection_rect is None

    def test_flip_after_stray_click_hits_selection(self, monkeypatch):
        from layers import Layer

        layer = Layer("t")
        layer.tiles[(2, 2)] = {"pos": (2, 2), "ttype": 0, "variant": 3,
                               "flip_h": False, "flip_v": False}
        layer.tiles[(4, 4)] = {"pos": (4, 4), "ttype": 0, "variant": 5,
                               "flip_h": False, "flip_v": False}
        g = _rig_select(make_grid(layer), monkeypatch)
        g.selection_rect = (2, 2, 4, 4)
        # stray click elsewhere (no drag): selection must survive ...
        pos = _cell_center(g, (0, 0))
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
        g.handle_event(_motion(pos))  # motion only tracks hover; unconsumed
        assert g.hover_cell == (0, 0)
        assert g.handle_event(_down(pos)) is True
        assert g.handle_event(_up(pos)) is True
        assert g.selection_rect == (2, 2, 4, 4)
        # ... so Shift+H flips the batch, not the brush.
        monkeypatch.setattr(pygame.key, "get_mods", lambda: pygame.KMOD_SHIFT)
        assert g.handle_event(_key(pygame.K_h)) is True
        assert layer.tiles[(4, 2)]["variant"] == 3
        assert layer.tiles[(2, 4)]["variant"] == 5
        assert layer.tiles[(4, 2)]["flip_h"] is True
        assert getattr(g, "brush_flip_h", False) is False


# ---------------------------------------------------------------------------
# _draw_move_preview honors flip flags (same helpers as main paint)
# ---------------------------------------------------------------------------


def _preview_grid(layer, tileset_surface):
    g = make_grid(layer)
    g.editor.tileset_widget = types.SimpleNamespace(
        tileset_map={0: types.SimpleNamespace(surface=tileset_surface)}
    )
    g._tile_scale_cache = {}
    return g


class TestMovePreviewFlip:
    def _sheet(self):
        surf = pygame.Surface((64, 32), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        surf.fill((255, 0, 0, 255), (0, 0, 4, 32))
        return surf

    def _moving_grid(self, layer, surf, dx=2, dy=0):
        g = _preview_grid(layer, surf)
        g.selection_rect = (2, 2, 2, 2)
        g.move_origin_rect = (2, 2, 2, 2)
        g.move_delta = (dx, dy)
        g.is_moving = True
        return g

    def test_flipped_tile_preview_mirrors(self):
        layer = FakeTileLayer()
        layer.set_tile((2, 2), {"pos": (2, 2), "ttype": 0, "variant": 0,
                                "flip_h": True, "flip_v": False})
        g = self._moving_grid(layer, self._sheet())
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        screen.fill((0, 0, 0, 255))
        g._draw_move_preview(screen)
        dest = g.cell_screen_rect(4, 2)
        # ghost alpha blends over black: red-dominant right, black left
        assert screen.get_at((dest.right - 2, dest.centery))[:3] == (160, 0, 0)
        assert screen.get_at((dest.x + 2, dest.centery))[:3] == (0, 0, 0)

    def test_unflipped_preview_unchanged(self):
        layer = FakeTileLayer()
        layer.set_tile((2, 2), {"pos": (2, 2), "ttype": 0, "variant": 0,
                                "flip_h": False, "flip_v": False})
        g = self._moving_grid(layer, self._sheet())
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        screen.fill((0, 0, 0, 255))
        g._draw_move_preview(screen)
        dest = g.cell_screen_rect(4, 2)
        assert screen.get_at((dest.x + 2, dest.centery))[:3] == (160, 0, 0)
