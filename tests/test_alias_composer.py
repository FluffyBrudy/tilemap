"""Tests for the standalone alias composer (model ops, headless)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest
from pygame import Rect

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def _reinit_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield


def make_editor():
    from plugins.tile_alias.editor import AliasComposerEditor

    surf = pygame.Surface((8 * 32, 8 * 32), pygame.SRCALPHA)
    surf.fill((10, 20, 30, 255))
    return AliasComposerEditor(Rect(0, 0, 1200, 800), surf, (32, 32))


class TestComposerModel:
    def test_new_alias_unique_names(self):
        ed = make_editor()
        a1 = ed.new_alias()
        a2 = ed.new_alias()
        assert (a1.name, a2.name) == ("Alias 1", "Alias 2")
        assert ed.selected_alias_idx == 1

    def test_store_and_reload_round_trip(self):
        ed = make_editor()
        ed.new_alias("Wall")
        ed.cells = {(0, 0): 5, (2, 1): 6}
        assert ed.store_canvas_to_selected() is True
        alias = ed.aliases[0]
        assert (alias.w, alias.h) == (8, 8)
        assert alias.cells == [(0, 0, 5), (2, 1, 6)]
        ed.cells = {}
        assert ed.load_alias_to_canvas(0) is True
        assert ed.cells == {(0, 0): 5, (2, 1): 6}

    def test_resize_canvas_drops_outside(self):
        ed = make_editor()
        ed.cells = {(0, 0): 1, (7, 7): 2}
        ed.resize_canvas(4, 4)
        assert (ed.canvas_w, ed.canvas_h) == (4, 4)
        assert ed.cells == {(0, 0): 1}

    def test_delete_alias(self):
        ed = make_editor()
        ed.new_alias("A")
        ed.new_alias("B")
        assert ed.delete_selected_alias() is True
        assert [a.name for a in ed.aliases] == ["A"]
        assert ed.delete_selected_alias() is True
        assert ed.delete_selected_alias() is False

    def test_save_load_round_trip(self, tmp_path):
        ed = make_editor()
        ed._tileset_ref = "tiles/stone.png"
        ed.new_alias("Wall")
        ed.cells = {(1, 1): 9}
        path = tmp_path / "stone.alias.json"
        ed.save_to_file(path)
        assert ed.dirty is False
        ed2 = make_editor()
        assert ed2.load_from_file(path) is True
        assert ed2.aliases[0].name == "Wall"
        assert ed2.cells == {(1, 1): 9}
        assert ed2.get_alias_file().tileset == "tiles/stone.png"

    def test_save_persists_canvas_without_explicit_store(self, tmp_path):
        ed = make_editor()
        ed.new_alias("W")
        ed.cells = {(0, 0): 3}
        path = tmp_path / "s.alias.json"
        ed.save_to_file(path)
        from aliases import AliasFile

        assert AliasFile.load(path).aliases[0].cells == [(0, 0, 3)]

    def test_load_missing_returns_false(self, tmp_path):
        ed = make_editor()
        assert ed.load_from_file(tmp_path / "nope.alias.json") is False

    def test_key_bindings(self):
        ed = make_editor()
        assert ed.handle_event(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_n})) is True
        assert len(ed.aliases) == 1
        assert ed.handle_event(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_DELETE})) is True
        assert ed.aliases == []
        ed.new_alias()
        before = (ed.canvas_w, ed.canvas_h)
        ed.handle_event(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RIGHTBRACKET}))
        assert (ed.canvas_w, ed.canvas_h) == (before[0] + 1, before[1])


class TestComposerDraw:
    def test_draw_no_exception(self):
        ed = make_editor()
        ed.new_alias("Wall")
        ed.cells = {(0, 0): 5, (7, 7): 3}
        ed.brush_rect = (2, 0, 2, 1)
        ed.draw(pygame.display.get_surface())


class TestCanvasUndo:
    def test_paint_undo_redo(self):
        ed = make_editor()
        ed._checkpoint()
        ed.cells[(0, 0)] = 5
        assert ed.undo_canvas() is True
        assert ed.cells == {}
        assert ed.redo_canvas() is True
        assert ed.cells == {(0, 0): 5}

    def test_new_stroke_clears_redo(self):
        ed = make_editor()
        ed._checkpoint()
        ed.cells[(0, 0)] = 5
        ed.undo_canvas()
        ed._checkpoint()
        ed.cells[(1, 1)] = 6
        assert ed.redo_canvas() is False
        assert ed.cells == {(1, 1): 6}

    def test_clear_and_resize_undo(self):
        ed = make_editor()
        ed.new_alias("A")
        ed.cells = {(0, 0): 1, (7, 7): 2}
        ed.clear_canvas()
        assert ed.cells == {}
        assert ed.undo_canvas() is True
        assert ed.cells == {(0, 0): 1, (7, 7): 2}
        ed.resize_canvas(4, 4)
        assert (ed.canvas_w, ed.canvas_h) == (4, 4)
        assert ed.undo_canvas() is True
        assert (ed.canvas_w, ed.canvas_h) == (8, 8)
        assert ed.cells == {(0, 0): 1, (7, 7): 2}

    def test_undo_empty(self):
        ed = make_editor()
        assert ed.undo_canvas() is False
        assert ed.redo_canvas() is False


class TestTilesetSheet:
    def test_hit_maps_tiles(self):
        ed = make_editor()
        oy = ed.strip_rect.y + 34
        assert ed._sheet_tile_at((10, oy + 2)) == (0, 0)
        assert ed._sheet_tile_at((10 + 32, oy + 2)) == (1, 0)
        assert ed._sheet_tile_at((10, oy + 2 + 32)) == (0, 1)
        assert ed._sheet_tile_at((10, ed.strip_rect.y + 2)) is None
        assert ed._sheet_tile_at((ed.strip_rect.right + 50, oy + 2)) is None

    def test_brush_stamp_uses_rect(self):
        ed = make_editor()
        ed.brush_rect = (1, 0, 2, 1)  # variants 1, 2 on an 8-wide sheet
        assert ed._stamp_brush_at(0, 0) is True
        assert ed.cells == {(0, 0): 1, (1, 0): 2}
        # stamping identical content reports no change
        assert ed._stamp_brush_at(0, 0) is False

    def test_zoom_keeps_hit(self):
        ed = make_editor()
        ed.ts_zoom = 2.0
        oy = ed.strip_rect.y + 34
        assert ed._sheet_tile_at((10, oy + 2)) == (0, 0)

    def test_splitter_resizes_strip(self):
        ed = make_editor()
        assert ed.strip_rect.h == 200
        ed._on_splitter_drag(500)
        assert ed.strip_rect.h == 274
        assert ed.strip_rect.y == 500
        assert ed.canvas_rect.bottom == 500 - 4


class TestQuitGuard:
    def test_clean_quits(self):
        ed = make_editor()
        assert ed.confirm_quit() is True

    def test_dirty_warns_once_then_quits(self):
        ed = make_editor()
        ed.cells[(0, 0)] = 1
        ed.dirty = True
        assert ed.confirm_quit() is False
        assert "Unsaved" in ed._status
        assert ed.confirm_quit() is True

    def test_mutation_disarms_warning(self, tmp_path):
        ed = make_editor()
        ed.cells[(0, 0)] = 1
        ed.dirty = True
        assert ed.confirm_quit() is False
        ed.cells[(1, 1)] = 2
        ed._mark_dirty()
        assert ed.confirm_quit() is False  # warns again, no silent quit

    def test_rename_cancelled_first(self):
        ed = make_editor()
        ed.new_alias("A")
        ed._renaming = True
        assert ed.confirm_quit() is False
        assert ed._renaming is False


class TestBrushSelect:
    def test_drag_selects_rect(self, monkeypatch):
        ed = make_editor()
        oy = ed.strip_rect.y + 34
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (10, oy + 2))
        ed.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (10, oy + 2)}))
        assert ed.brush_rect == (0, 0, 1, 1)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (10 + 70, oy + 40))
        ed.handle_event(pygame.event.Event(
            pygame.MOUSEMOTION,
            {"pos": (10 + 70, oy + 40), "rel": (70, 38), "buttons": (1, 0, 0)}))
        assert ed.brush_rect == (0, 0, 3, 2)
        ed.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONUP, {"button": 1, "pos": (10 + 70, oy + 40)}))
        assert ed.brush_rect == (0, 0, 3, 2)


class TestAliasSwitching:
    def test_new_preserves_work_and_starts_fresh(self):
        ed = make_editor()
        ed.new_alias("First")
        ed.cells = {(0, 0): 5, (3, 3): 6}
        ed.resize_canvas(12, 10)
        ed.new_alias("Second")
        # previous work stored into First, canvas reset
        assert ed.aliases[0].cells == [(0, 0, 5), (3, 3, 6)]
        assert (ed.aliases[0].w, ed.aliases[0].h) == (12, 10)
        assert ed.cells == {}
        assert (ed.canvas_w, ed.canvas_h) == (8, 8)
        assert ed.aliases[1].name == "Second"
        assert "fresh canvas" in ed._status

    def test_delete_canvas_follows_selection(self):
        ed = make_editor()
        ed.new_alias("A")
        ed.cells = {(0, 0): 1}
        ed.store_canvas_to_selected()
        ed.new_alias("B")
        ed.cells = {(5, 5): 9}
        ed.store_canvas_to_selected()
        ed.selected_alias_idx = 1
        assert ed.delete_selected_alias() is True
        # canvas now shows A, not the deleted B
        assert ed.cells == {(0, 0): 1}
        assert ed.aliases[0].name == "A"

    def test_delete_last_clears_canvas(self):
        ed = make_editor()
        ed.new_alias("Only")
        ed.cells = {(2, 2): 4}
        assert ed.delete_selected_alias() is True
        assert ed.aliases == []
        assert ed.cells == {}

    def test_list_click_confirms_selection(self, monkeypatch):
        ed = make_editor()
        ed.new_alias("Alpha")
        ed.new_alias("Beta")
        y = ed.list_rect.y + 26 + 1 * 28 + 4
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (ed.list_rect.x + 10, y))
        assert ed.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            {"button": 1, "pos": (ed.list_rect.x + 10, y)})) is True
        assert ed.selected_alias_idx == 1
        assert "Beta" in ed._status


class TestPlotGateAndSteppers:
    def test_paint_gated_without_alias(self, monkeypatch):
        ed = make_editor()
        assert ed.aliases == []
        # canvas center: firmly inside the 8x8 grid, not the margins
        cx = ed.canvas_rect.centerx
        cy = ed.canvas_rect.centery
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (cx, cy))
        ed.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (cx, cy)}))
        assert ed.cells == {}
        assert "first" in ed._status
        assert len(ed.toasts._toasts) == 1

    def test_erase_gated_without_alias(self, monkeypatch):
        ed = make_editor()
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (400, 300))
        assert ed.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 3, "pos": (400, 300)})) is True
        assert len(ed.toasts._toasts) == 1

    def test_toolbar_has_dimension_steppers(self):
        ed = make_editor()
        labels = [b.text for b, _ in ed._toolbar_buttons]
        assert labels == ["Save", "New", "Rename", "Delete", "Clear",
                            "W-", "W+", "H-", "H+", ""]
        w, h = ed.canvas_w, ed.canvas_h
        for b, _ in ed._toolbar_buttons:
            if b.text == "W+":
                b.on_click()
        assert (ed.canvas_w, ed.canvas_h) == (w + 1, h)

    def test_save_toasts_success(self, tmp_path):
        ed = make_editor()
        ed.new_alias("W")
        ed.toasts._toasts.clear()
        ed.save_to_file(tmp_path / "s.alias.json")
        assert len(ed.toasts._toasts) == 1

    def test_empty_canvas_overlay_draws(self):
        ed = make_editor()
        assert ed.aliases == []
        ed.draw(pygame.display.get_surface())


class TestRename:
    def test_start_rename_and_commit(self):
        ed = make_editor()
        ed.new_alias("Old")
        assert ed.start_rename() is True
        assert ed._renaming is True
        ed._rename_buf = "Wall"
        ed.handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_RETURN, "unicode": ""}))
        assert ed.aliases[0].name == "Wall"
        assert ed._renaming is False
        assert "Wall" in ed._status

    def test_rename_duplicate_rejected(self):
        ed = make_editor()
        ed.new_alias("A")
        ed.new_alias("B")
        ed.start_rename()
        ed._rename_buf = "A"
        ed.handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_RETURN, "unicode": ""}))
        assert ed.aliases[1].name == "B"

    def test_rename_without_alias_warns(self):
        ed = make_editor()
        assert ed.start_rename() is False

    def test_toolbar_has_rename(self):
        ed = make_editor()
        assert "Rename" in [b.text for b, _ in ed._toolbar_buttons]

    def test_double_click_starts_rename(self, monkeypatch):
        ed = make_editor()
        ed.new_alias("Alpha")
        y = ed.list_rect.y + 26 + 4
        pos = (ed.list_rect.x + 10, y)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
        ed.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos}))
        assert ed._renaming is False
        ed.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos}))
        assert ed._renaming is True


class TestHelpOverlay:
    def test_toggle_and_draw(self):
        ed = make_editor()
        assert ed.show_help is False
        ed.toggle_help()
        assert ed.show_help is True
        ed.draw(pygame.display.get_surface())

    def test_esc_closes_help(self, monkeypatch):
        ed = make_editor()
        ed.show_help = True
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert ed.handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_ESCAPE})) is not True
