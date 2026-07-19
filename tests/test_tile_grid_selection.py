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

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

import pygame
import pytest
from pygame import Rect

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


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
        self.initial_map_size = (20, 20)
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
# Initial state
# ---------------------------------------------------------------------------


class TestInitialState:
    def test_selection_rect_is_none(self):
        g = make_grid()
        assert g.selection_rect is None

    def test_selection_start_is_none(self):
        g = make_grid()
        assert g.selection_start is None

    def test_is_selecting_is_false(self):
        g = make_grid()
        assert g.is_selecting is False

    def test_is_moving_is_false(self):
        g = make_grid()
        assert g.is_moving is False

    def test_move_delta_is_zero(self):
        g = make_grid()
        assert g.move_delta == (0, 0)

    def test_move_start_mouse_is_none(self):
        g = make_grid()
        assert g.move_start_mouse is None

    def test_move_origin_rect_is_none(self):
        g = make_grid()
        assert g.move_origin_rect is None

    def test_clipboard_is_none(self):
        g = make_grid()
        assert g.clipboard is None


# ---------------------------------------------------------------------------
# _point_in_selection
# ---------------------------------------------------------------------------


class TestPointInSelection:
    def test_returns_false_when_no_selection(self):
        g = make_grid()
        assert g._point_in_selection((3, 3)) is False

    def test_point_inside_selection(self):
        g = make_grid()
        g.selection_rect = (2, 2, 5, 5)
        assert g._point_in_selection((3, 3)) is True

    def test_point_on_top_left_corner(self):
        g = make_grid()
        g.selection_rect = (2, 2, 5, 5)
        assert g._point_in_selection((2, 2)) is True

    def test_point_on_bottom_right_corner(self):
        g = make_grid()
        g.selection_rect = (2, 2, 5, 5)
        assert g._point_in_selection((5, 5)) is True

    def test_point_outside_selection(self):
        g = make_grid()
        g.selection_rect = (2, 2, 5, 5)
        assert g._point_in_selection((6, 3)) is False

    def test_point_just_outside_left(self):
        g = make_grid()
        g.selection_rect = (2, 2, 5, 5)
        assert g._point_in_selection((1, 3)) is False


# ---------------------------------------------------------------------------
# _finalize_selection
# ---------------------------------------------------------------------------


class TestFinalizeSelection:
    def test_removes_single_cell_selection(self):
        g = make_grid()
        g.selection_rect = (3, 3, 3, 3)
        g._finalize_selection()
        assert g.selection_rect is None

    def test_keeps_multi_cell_selection(self):
        g = make_grid()
        g.selection_rect = (1, 1, 4, 4)
        g._finalize_selection()
        assert g.selection_rect == (1, 1, 4, 4)

    def test_noop_when_no_selection(self):
        g = make_grid()
        g._finalize_selection()
        assert g.selection_rect is None


# ---------------------------------------------------------------------------
# copy_selection (tile layer)
# ---------------------------------------------------------------------------


class TestCopySelection:
    def test_copy_with_no_selection_does_nothing(self):
        g = make_grid()
        g.copy_selection()
        assert g.clipboard is None

    def test_copy_empty_selection_sets_clipboard_none(self):
        """Copying a region with no tiles sets clipboard to None."""
        g = make_grid()
        g.selection_rect = (0, 0, 2, 2)
        g.copy_selection()
        # No tiles in the layer, so clipboard should be None
        assert g.clipboard is None

    def test_copy_with_tiles_populates_clipboard(self):
        layer = FakeTileLayer()
        layer.set_tile((1, 1), {"pos": (1, 1), "ttype": 0, "variant": 3})
        g = make_grid(layer)
        g.selection_rect = (1, 1, 2, 2)
        g.copy_selection()
        assert g.clipboard is not None
        assert len(g.clipboard["tiles"]) == 1

    def test_copy_preserves_relative_positions(self):
        layer = FakeTileLayer()
        layer.set_tile((2, 3), {"pos": (2, 3), "ttype": 0, "variant": 5})
        g = make_grid(layer)
        g.selection_rect = (2, 3, 3, 4)
        g.copy_selection()
        assert (0, 0) in g.clipboard["tiles"]

    def test_copy_records_layer_type(self):
        layer = FakeTileLayer()
        layer.set_tile((0, 0), {"pos": (0, 0), "ttype": 0, "variant": 1})
        g = make_grid(layer)
        g.selection_rect = (0, 0, 1, 1)
        g.copy_selection()
        assert g.clipboard["layer_type"] == "tile"

    def test_copy_records_origin(self):
        layer = FakeTileLayer()
        layer.set_tile((3, 2), {"pos": (3, 2), "ttype": 0, "variant": 1})
        g = make_grid(layer)
        g.selection_rect = (3, 2, 4, 3)
        g.copy_selection()
        assert g.clipboard["origin"] == (3, 2)

    def test_copy_multiple_tiles(self):
        layer = FakeTileLayer()
        layer.set_tile((0, 0), {"pos": (0, 0), "ttype": 0, "variant": 1})
        layer.set_tile((1, 0), {"pos": (1, 0), "ttype": 0, "variant": 2})
        layer.set_tile((0, 1), {"pos": (0, 1), "ttype": 0, "variant": 3})
        g = make_grid(layer)
        g.selection_rect = (0, 0, 1, 1)
        g.copy_selection()
        assert len(g.clipboard["tiles"]) == 3

    def test_copy_notifies_success(self):
        layer = FakeTileLayer()
        layer.set_tile((0, 0), {"pos": (0, 0), "ttype": 0, "variant": 1})
        g = make_grid(layer)
        g.selection_rect = (0, 0, 0, 0)
        g.copy_selection()
        msgs = [m[0] for m in g.editor.notifications.messages]
        assert "success" in msgs


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

    def test_paste_does_nothing_with_no_clipboard(self):
        g = make_grid()
        g.paste_clipboard((0, 0))
        # No exception; layer is unchanged
        layer = g.editor.tilemap.layer_manager.get_active_layer()
        assert layer.get_tile((0, 0)) is None

    def test_paste_places_tile_at_target(self):
        g = self._setup_clipboard()
        layer = g.editor.tilemap.layer_manager.get_active_layer()
        g.paste_clipboard((5, 5))
        assert layer.get_tile((5, 5)) is not None

    def test_paste_tile_has_correct_variant(self):
        g = self._setup_clipboard()
        layer = g.editor.tilemap.layer_manager.get_active_layer()
        g.paste_clipboard((5, 5))
        tile = layer.get_tile((5, 5))
        assert tile["variant"] == 7

    def test_paste_notifies_success(self):
        g = self._setup_clipboard()
        g.paste_clipboard((5, 5))
        msgs = [m[0] for m in g.editor.notifications.messages]
        assert "success" in msgs

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
    def test_delete_with_no_selection_does_nothing(self):
        g = make_grid()
        g.delete_selection()  # should not raise
        assert g.selection_rect is None

    def test_delete_removes_tiles_in_rect(self):
        layer = FakeTileLayer()
        layer.set_tile((1, 1), {"pos": (1, 1), "ttype": 0, "variant": 1})
        layer.set_tile((2, 1), {"pos": (2, 1), "ttype": 0, "variant": 2})
        g = make_grid(layer)
        g.selection_rect = (1, 1, 2, 1)
        g.delete_selection()
        assert layer.get_tile((1, 1)) is None
        assert layer.get_tile((2, 1)) is None

    def test_delete_clears_selection_rect(self):
        layer = FakeTileLayer()
        layer.set_tile((0, 0), {"pos": (0, 0), "ttype": 0, "variant": 1})
        g = make_grid(layer)
        g.selection_rect = (0, 0, 1, 1)
        g.delete_selection()
        assert g.selection_rect is None

    def test_delete_does_not_remove_tiles_outside_selection(self):
        layer = FakeTileLayer()
        layer.set_tile((5, 5), {"pos": (5, 5), "ttype": 0, "variant": 9})
        g = make_grid(layer)
        g.selection_rect = (0, 0, 2, 2)
        g.delete_selection()
        assert layer.get_tile((5, 5)) is not None

    def test_delete_notifies_success(self):
        layer = FakeTileLayer()
        layer.set_tile((0, 0), {"pos": (0, 0), "ttype": 0, "variant": 1})
        g = make_grid(layer)
        g.selection_rect = (0, 0, 1, 1)
        g.delete_selection()
        msgs = [m[0] for m in g.editor.notifications.messages]
        assert "success" in msgs


# ---------------------------------------------------------------------------
# _begin_move and cancel_move
# ---------------------------------------------------------------------------


class TestBeginMoveAndCancelMove:
    def test_begin_move_sets_is_moving(self):
        g = make_grid()
        g.selection_rect = (1, 1, 3, 3)
        g._begin_move((100, 200))
        assert g.is_moving is True

    def test_begin_move_records_start_mouse(self):
        g = make_grid()
        g.selection_rect = (1, 1, 3, 3)
        g._begin_move((100, 200))
        assert g.move_start_mouse == (100, 200)

    def test_begin_move_saves_origin_rect(self):
        g = make_grid()
        g.selection_rect = (1, 1, 3, 3)
        g._begin_move((100, 200))
        assert g.move_origin_rect == (1, 1, 3, 3)

    def test_begin_move_resets_delta(self):
        g = make_grid()
        g.selection_rect = (1, 1, 3, 3)
        g.move_delta = (5, 5)
        g._begin_move((100, 200))
        assert g.move_delta == (0, 0)

    def test_cancel_move_clears_is_moving(self):
        g = make_grid()
        g.selection_rect = (1, 1, 3, 3)
        g._begin_move((50, 50))
        g.cancel_move()
        assert g.is_moving is False

    def test_cancel_move_restores_selection_rect(self):
        g = make_grid()
        g.selection_rect = (1, 1, 3, 3)
        g._begin_move((50, 50))
        g.selection_rect = (2, 2, 4, 4)  # simulate drag update
        g.cancel_move()
        assert g.selection_rect == (1, 1, 3, 3)

    def test_cancel_move_clears_move_delta(self):
        g = make_grid()
        g.selection_rect = (1, 1, 3, 3)
        g._begin_move((50, 50))
        g.move_delta = (3, 2)
        g.cancel_move()
        assert g.move_delta == (0, 0)

    def test_cancel_move_when_not_moving_is_safe(self):
        g = make_grid()
        g.cancel_move()  # should not raise


# ---------------------------------------------------------------------------
# commit_move (tile layer)
# ---------------------------------------------------------------------------


class TestCommitMove:
    def test_commit_move_with_zero_delta_does_not_move_tiles(self):
        layer = FakeTileLayer()
        layer.set_tile((2, 2), {"pos": (2, 2), "ttype": 0, "variant": 1})
        g = make_grid(layer)
        g.selection_rect = (2, 2, 3, 3)
        g._begin_move((0, 0))
        g.move_delta = (0, 0)
        g.commit_move()
        assert layer.get_tile((2, 2)) is not None
        assert g.is_moving is False

    def test_commit_move_moves_tiles_by_delta(self):
        layer = FakeTileLayer()
        layer.set_tile((2, 2), {"pos": (2, 2), "ttype": 0, "variant": 5})
        g = make_grid(layer)
        g.selection_rect = (2, 2, 2, 2)
        g._begin_move((0, 0))
        g.move_delta = (1, 0)
        g.commit_move()
        assert layer.get_tile((2, 2)) is None
        assert layer.get_tile((3, 2)) is not None

    def test_commit_move_updates_selection_rect(self):
        layer = FakeTileLayer()
        layer.set_tile((2, 2), {"pos": (2, 2), "ttype": 0, "variant": 5})
        g = make_grid(layer)
        g.selection_rect = (2, 2, 3, 3)
        g._begin_move((0, 0))
        g.move_delta = (2, 1)
        g.commit_move()
        assert g.selection_rect == (4, 3, 5, 4)

    def test_commit_move_clears_moving_state(self):
        layer = FakeTileLayer()
        layer.set_tile((2, 2), {"pos": (2, 2), "ttype": 0, "variant": 1})
        g = make_grid(layer)
        g.selection_rect = (2, 2, 2, 2)
        g._begin_move((0, 0))
        g.move_delta = (1, 0)
        g.commit_move()
        assert g.is_moving is False
        assert g.move_start_mouse is None
        assert g.move_origin_rect is None

    def test_commit_move_when_not_moving_is_safe(self):
        g = make_grid()
        g.commit_move()  # should not raise

    def test_commit_move_records_history(self):
        layer = FakeTileLayer()
        layer.set_tile((0, 0), {"pos": (0, 0), "ttype": 0, "variant": 1})
        g = make_grid(layer)
        g.selection_rect = (0, 0, 0, 0)
        g._begin_move((0, 0))
        g.move_delta = (1, 0)
        g.commit_move()
        assert "Move Selection" in g.editor.tilemap._history

    def test_commit_move_preserves_tile_variant(self):
        """Moved tiles should keep their variant ID unchanged."""
        layer = FakeTileLayer()
        layer.set_tile((1, 1), {"pos": (1, 1), "ttype": 0, "variant": 42})
        g = make_grid(layer)
        g.selection_rect = (1, 1, 1, 1)
        g._begin_move((0, 0))
        g.move_delta = (0, 1)
        g.commit_move()
        moved = layer.get_tile((1, 2))
        assert moved is not None
        assert moved["variant"] == 42
