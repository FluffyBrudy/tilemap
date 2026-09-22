"""Batch tileset-type import tests ("apply to all").

Covers:
- dialog checkbox hidden for single files, shown with the remaining
  count otherwise; toggles; persists across show() calls.
- queue: first manual confirm captures the preset, remaining files
  commit without re-showing the dialog; drain clears the preset.
- cancel-mid-batch keeps any preset and advances the queue.
- size-warning confirm still fires per mismatched file under a preset.
- fresh file-manager batches reset checkbox + preset.
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


class FakeTilemap:
    def __init__(self, tile_size=(32, 32)):
        self.tile_size = tile_size


class FakeNotifications:
    def __init__(self):
        self.messages = []

    def notify(self, msg, duration=2.0, **kwargs):
        self.messages.append(msg)

    def success(self, msg, **kwargs):
        self.messages.append(msg)


class FakeSuggestions:
    def refresh(self, editor):
        pass


class FakeConfirmDialog:
    def __init__(self):
        self.shown = []

    def show(self, **kwargs):
        self.shown.append(kwargs)


class FakeEditor:
    def __init__(self, tile_size=(32, 32)):
        from utils.context_dispatch import PropertyContextDispatcher
        from widgets.ui.tileset_type_dialog import TilesetTypeDialog

        self.tilemap = FakeTilemap(tile_size)
        self.context_dispatch = PropertyContextDispatcher()
        self.tileset_type_dialog = TilesetTypeDialog(Rect(0, 0, 1000, 700))
        self.notifications = FakeNotifications()
        self.suggestion_registry = FakeSuggestions()
        self.confirm_dialog = FakeConfirmDialog()


def _make_selector(tile_size=(32, 32)):
    from widgets.tile_selector import TileSelector

    return TileSelector(FakeEditor(tile_size=tile_size), x=0, y=0, w=400, h=600)


def _surf(w=64, h=64):
    s = pygame.Surface((w, h))
    s.fill((90, 120, 160))
    return s


def _click(dialog, pos, monkeypatch):
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: pos)
    return dialog.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos}))


class TestApplyAllCheckbox:
    def test_hidden_for_single_file(self, monkeypatch):
        sel = _make_selector()
        dlg = sel.editor.tileset_type_dialog
        dlg.show(on_confirm=lambda t: None, on_cancel=lambda: None, remaining=0)
        assert dlg._batch_remaining == 0
        # clicking where the row would be must not toggle anything
        before = dlg.apply_to_all
        _click(dlg, (dlg.rect.x + 42, dlg.rect.y + 200), monkeypatch)
        assert dlg.apply_to_all is before

    def test_shown_toggles_and_persists(self, monkeypatch):
        sel = _make_selector()
        dlg = sel.editor.tileset_type_dialog
        dlg.show(on_confirm=lambda t: None, on_cancel=lambda: None, remaining=3)
        dlg._layout()
        assert dlg._batch_remaining == 3
        assert dlg.apply_to_all is False
        assert _click(dlg, dlg.apply_all_rect.center, monkeypatch) is True
        assert dlg.apply_to_all is True
        # persists across the batch's shows (never auto-reset by show)
        dlg.show(on_confirm=lambda t: None, on_cancel=lambda: None, remaining=2)
        assert dlg.apply_to_all is True

    def test_layout_does_not_drift(self):
        sel = _make_selector()
        dlg = sel.editor.tileset_type_dialog
        dlg.show(on_confirm=lambda t: None, on_cancel=lambda: None, remaining=2)
        dlg._layout()
        settled = Rect(dlg.rect)
        for _ in range(5):
            dlg.handle_event(
                pygame.event.Event(pygame.MOUSEMOTION, {"pos": (0, 0)}))
            dlg._layout()
        assert dlg.rect == settled

    def test_show_recenters_after_resize(self):
        sel = _make_selector()
        dlg = sel.editor.tileset_type_dialog
        dlg.show(on_confirm=lambda t: None, on_cancel=lambda: None, remaining=0)
        dlg._layout()
        dlg.editor_rect = Rect(0, 0, 1600, 900)
        dlg.show(on_confirm=lambda t: None, on_cancel=lambda: None, remaining=0)
        dlg._layout()
        assert dlg.rect.center == (800, 450)

    def test_draw_with_checkbox(self):
        sel = _make_selector()
        dlg = sel.editor.tileset_type_dialog
        dlg.show(on_confirm=lambda t: None, on_cancel=lambda: None, remaining=2)
        screen = pygame.Surface((1000, 700))
        dlg.draw(screen)  # must not raise


class TestBatchQueue:
    def _queued_selector(self, sizes=((64, 64), (64, 64), (64, 64))):
        sel = _make_selector()
        sel._pending_tileset_queue = [
            (Path(f"sheet{i}.png"), _surf(w, h)) for i, (w, h) in enumerate(sizes)
        ]
        return sel

    def _confirm_first_with_apply_all(self, sel, monkeypatch, tileset_type="tile"):
        sel._start_tileset_queue()
        dlg = sel.editor.tileset_type_dialog
        assert dlg.active is True
        dlg._layout()
        dlg.selected_type = tileset_type
        dlg.apply_to_all = True
        assert _click(sel.editor.tileset_type_dialog, dlg.btn_ok.center, monkeypatch) is True

    def test_one_confirm_applies_to_all(self, monkeypatch):
        sel = self._queued_selector()
        self._confirm_first_with_apply_all(sel, monkeypatch, "tile")
        assert sel._batch_type == "tile"
        assert any("remaining" in m for m in sel.editor.notifications.messages)
        # remaining files commit with no dialog
        sel._start_tileset_queue()
        assert sel.editor.tileset_type_dialog.active is False
        sel._start_tileset_queue()
        assert sel.editor.tileset_type_dialog.active is False
        assert len(sel.tilesets) == 3
        assert all(t.tileset_type == "tile" for t in sel.tilesets)
        # drain clears the preset
        sel._start_tileset_queue()
        assert sel._batch_type is None

    def test_object_preset(self, monkeypatch):
        sel = self._queued_selector()
        self._confirm_first_with_apply_all(sel, monkeypatch, "object")
        sel._start_tileset_queue()
        sel._start_tileset_queue()
        assert [t.tileset_type for t in sel.tilesets] == ["object"] * 3

    def test_unchecked_asks_every_file(self, monkeypatch):
        sel = self._queued_selector(sizes=((64, 64), (64, 64)))
        sel._start_tileset_queue()
        dlg = sel.editor.tileset_type_dialog
        assert dlg.active is True
        dlg._layout()
        dlg.selected_type = "tile"  # apply_to_all left False
        assert _click(dlg, dlg.btn_ok.center, monkeypatch) is True
        assert sel._batch_type is None
        sel._start_tileset_queue()
        assert sel.editor.tileset_type_dialog.active is True

    def test_cancel_advances_without_preset(self):
        sel = self._queued_selector(sizes=((64, 64), (64, 64)))
        sel._start_tileset_queue()
        sel._on_tileset_type_cancel()
        assert sel._batch_type is None
        # canceled file skipped, next file prompts
        assert sel.editor.tileset_type_dialog.active is True
        assert len(sel.tilesets) == 0

    def test_size_warning_still_fires_per_file(self, monkeypatch):
        sel = self._queued_selector(sizes=((64, 64), (40, 40)))
        self._confirm_first_with_apply_all(sel, monkeypatch, "tile")
        assert len(sel.tilesets) == 1
        sel._start_tileset_queue()  # 40x40 is not a multiple of 32
        shown = sel.editor.confirm_dialog.shown
        assert len(shown) == 1
        assert "Tileset Size Warning" in shown[0]["title"]
        # proceed through the warning: file still loads as tile
        shown[0]["on_confirm"]()
        assert len(sel.tilesets) == 2
        assert sel.tilesets[1].tileset_type == "tile"

    def test_fresh_batch_resets(self, monkeypatch, tmp_path):
        sel = self._queued_selector()
        self._confirm_first_with_apply_all(sel, monkeypatch, "tile")
        assert sel._batch_type == "tile"
        # new file-manager run with real files on disk
        paths = []
        for i in range(2):
            p = tmp_path / f"batch{i}.png"
            pygame.image.save(_surf(), str(p))
            paths.append(p)
        sel.on_files_selected(paths)
        assert sel.editor.tileset_type_dialog.apply_to_all is False
        assert sel._batch_type is None
        assert sel.editor.tileset_type_dialog.active is True
