"""
Tests for SpriteAnimationEditor._apply_library_grid_settings() added in PR.

Verifies that after loading a library, tile_size and grid_offset are
correctly synced to internal editor state and sub-widget properties.
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


def _make_editor(tile_size=(32, 32)):
    from plugins.sprite_animation.editor import SpriteAnimationEditor

    surf = pygame.Surface((128, 128))
    surf.fill((80, 80, 80))
    rect = Rect(0, 0, 900, 600)
    return SpriteAnimationEditor(rect=rect, surface=surf, tile_size=tile_size)


class TestApplyLibraryGridSettings:
    def test_tile_size_synced_to_internal_field(self):
        from plugins.sprite_animation.models import AnimationLibrary

        ed = _make_editor()
        ed.library = AnimationLibrary(tile_size=(16, 16), grid_offset=(0, 0))
        ed._apply_library_grid_settings()
        assert ed._tile_size == (16, 16)

    def test_frame_width_input_updated(self):
        from plugins.sprite_animation.models import AnimationLibrary

        ed = _make_editor()
        ed.library = AnimationLibrary(tile_size=(48, 24), grid_offset=(0, 0))
        ed._apply_library_grid_settings()
        assert ed._frame_width_input == "48"

    def test_frame_height_input_updated(self):
        from plugins.sprite_animation.models import AnimationLibrary

        ed = _make_editor()
        ed.library = AnimationLibrary(tile_size=(48, 24), grid_offset=(0, 0))
        ed._apply_library_grid_settings()
        assert ed._frame_height_input == "24"

    def test_grid_offset_x_synced(self):
        from plugins.sprite_animation.models import AnimationLibrary

        ed = _make_editor()
        ed.library = AnimationLibrary(tile_size=(32, 32), grid_offset=(8, 4))
        ed._apply_library_grid_settings()
        assert ed._grid_offset_x == 8

    def test_grid_offset_y_synced(self):
        from plugins.sprite_animation.models import AnimationLibrary

        ed = _make_editor()
        ed.library = AnimationLibrary(tile_size=(32, 32), grid_offset=(8, 4))
        ed._apply_library_grid_settings()
        assert ed._grid_offset_y == 4

    def test_offset_x_input_updated(self):
        from plugins.sprite_animation.models import AnimationLibrary

        ed = _make_editor()
        ed.library = AnimationLibrary(tile_size=(32, 32), grid_offset=(12, 0))
        ed._apply_library_grid_settings()
        assert ed._offset_x_input == "12"

    def test_offset_y_input_updated(self):
        from plugins.sprite_animation.models import AnimationLibrary

        ed = _make_editor()
        ed.library = AnimationLibrary(tile_size=(32, 32), grid_offset=(0, 7))
        ed._apply_library_grid_settings()
        assert ed._offset_y_input == "7"

    def test_timeline_tile_size_updated(self):
        from plugins.sprite_animation.models import AnimationLibrary

        ed = _make_editor()
        ed.library = AnimationLibrary(tile_size=(16, 16), grid_offset=(0, 0))
        ed._apply_library_grid_settings()
        assert ed.timeline.tile_size == (16, 16)

    def test_timeline_grid_offset_updated(self):
        from plugins.sprite_animation.models import AnimationLibrary

        ed = _make_editor()
        ed.library = AnimationLibrary(tile_size=(32, 32), grid_offset=(5, 3))
        ed._apply_library_grid_settings()
        assert ed.timeline.grid_offset_x == 5
        assert ed.timeline.grid_offset_y == 3

    def test_timeline_cache_cleared_after_apply(self):
        """_apply_library_grid_settings must invalidate the timeline's thumb cache."""
        from plugins.sprite_animation.models import AnimationFrame, AnimationLibrary

        ed = _make_editor(tile_size=(32, 32))
        ed.timeline.frames = [AnimationFrame(variant_id=0)]
        _ = ed.timeline._get_thumb(0)  # populate cache
        assert len(ed.timeline._thumb_cache) > 0

        ed.library = AnimationLibrary(tile_size=(32, 32), grid_offset=(4, 4))
        ed._apply_library_grid_settings()
        assert ed.timeline._thumb_cache == {}

    def test_zero_offset_resets_previous_offset(self):
        """Calling _apply with offset (0,0) must clear any previously set offset."""
        from plugins.sprite_animation.models import AnimationLibrary

        ed = _make_editor()
        ed._grid_offset_x = 99
        ed._grid_offset_y = 99
        ed.library = AnimationLibrary(tile_size=(32, 32), grid_offset=(0, 0))
        ed._apply_library_grid_settings()
        assert ed._grid_offset_x == 0
        assert ed._grid_offset_y == 0

    def test_library_tile_size_unchanged_by_apply(self):
        """_apply_library_grid_settings must not change library.tile_size value."""
        from plugins.sprite_animation.models import AnimationLibrary

        ed = _make_editor()
        ed.library = AnimationLibrary(tile_size=(24, 24), grid_offset=(0, 0))
        ed._apply_library_grid_settings()
        assert ed.library.tile_size == (24, 24)


class TestSpriteAnimationKeyboardShortcuts:
    def test_ctrl_shift_s_opens_save_dialog(self, monkeypatch):
        ed = _make_editor()

        calls: list[str] = []
        monkeypatch.setattr(ed, "_save_dialog", lambda: calls.append("save_dialog"))
        monkeypatch.setattr(ed, "_quick_save", lambda: calls.append("quick_save"))

        old_mods = pygame.key.get_mods()
        try:
            pygame.key.set_mods(pygame.KMOD_CTRL | pygame.KMOD_SHIFT)
            event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_s})
            assert ed.handle_event(event) is True
            assert calls == ["save_dialog"]
        finally:
            pygame.key.set_mods(old_mods)
