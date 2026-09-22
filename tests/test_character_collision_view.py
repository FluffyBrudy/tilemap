"""Character collision ShapeEditor view tests (large sheets).

Covers: fit-90% on load, default zoom, R refit, resize preserving
offsets, zoom-to-cursor anchoring, scaled-sprite cache reuse, and
viewport-bounded grid drawing.
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


VIEW = Rect(0, 0, 1000, 550)


def _strip(w=512, h=4096):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((70, 70, 70, 255))
    return surf


def _make_editor(surface=None):
    from plugins.character_collision.shape_editor import ShapeEditor

    return ShapeEditor(VIEW.copy(), surface if surface is not None else _strip(64, 64))


class TestFitView:
    def test_default_zoom_is_one(self):
        ed = _make_editor()
        assert ed.zoom == 1.0

    def test_load_fits_90_percent(self):
        ed = _make_editor()
        ed.load_sprite(_strip())
        expected = 0.9 * min(VIEW.w / 512, VIEW.h / 4096)
        assert ed.zoom == pytest.approx(expected)
        # whole sprite on screen with margin
        assert ed.offset_x >= 0 and ed.offset_y >= 0
        assert 512 * ed.zoom <= VIEW.w
        assert 4096 * ed.zoom <= VIEW.h

    def test_load_small_sprite(self):
        ed = _make_editor()
        ed.load_sprite(_strip(64, 64))
        expected = 0.9 * min(VIEW.w / 64, VIEW.h / 64)
        assert ed.zoom == pytest.approx(expected)

    def test_r_refits(self):
        ed = _make_editor()
        ed.load_sprite(_strip())
        ed.zoom = 3.0
        ed.offset_x, ed.offset_y = -500.0, -2000.0
        ed.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_r}))
        expected = 0.9 * min(VIEW.w / 512, VIEW.h / 4096)
        assert ed.zoom == pytest.approx(expected)

    def test_resize_preserves_offsets(self):
        ed = _make_editor()
        ed.load_sprite(_strip())
        ed.offset_x, ed.offset_y = 123.0, -456.0
        ed.resize(Rect(0, 0, 1200, 700))
        assert (ed.offset_x, ed.offset_y) == (123.0, -456.0)


class TestZoomAnchor:
    def test_ctrl_wheel_keeps_cursor_point(self, monkeypatch):
        ed = _make_editor()
        ed.load_sprite(_strip())
        mouse = (VIEW.x + 400, VIEW.y + 300)
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: mouse)
        before = ed._screen_to_sprite(mouse)
        old_mods = pygame.key.get_mods()
        try:
            pygame.key.set_mods(pygame.KMOD_CTRL)
            ed.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, {"x": 0, "y": 1}))
        finally:
            pygame.key.set_mods(old_mods)
        after = ed._screen_to_sprite(mouse)
        assert after == pytest.approx(before)
        assert ed.zoom > 0.9 * min(VIEW.w / 512, VIEW.h / 4096)


class TestRenderCache:
    def test_scaled_surface_reused(self, monkeypatch):
        ed = _make_editor()
        ed.load_sprite(_strip())
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (-10, -10))
        screen = pygame.Surface((VIEW.w, VIEW.h))
        ed.draw(screen)
        first = ed._scaled_cache
        assert first is not None
        size = first.get_size()
        ed.draw(screen)
        assert ed._scaled_cache is first
        assert ed._scaled_cache.get_size() == size

    def test_zoom_invalidates_cache(self, monkeypatch):
        ed = _make_editor()
        ed.load_sprite(_strip())
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (-10, -10))
        screen = pygame.Surface((VIEW.w, VIEW.h))
        ed.draw(screen)
        old_key = ed._scaled_cache_key
        ed.zoom *= 2
        ed.draw(screen)
        assert ed._scaled_cache_key != old_key

    def test_grid_draw_bounded_no_crash(self, monkeypatch):
        ed = _make_editor()
        ed.load_sprite(_strip())
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (-10, -10))
        screen = pygame.Surface((VIEW.w, VIEW.h))
        ed.draw(screen)  # must not raise / allocate a canvas-size surface
        ed.zoom = 3.0
        ed.offset_x, ed.offset_y = -700.0, -5000.0
        ed.draw(screen)


def _make_collision_editor(data_root=None):
    from plugins.character_collision.editor import CharacterCollisionEditor

    ed = CharacterCollisionEditor(VIEW.copy(), _strip(64, 64), "Hero")
    ed._data_root = data_root
    return ed


class TestImagePathPortability:
    def test_inside_root_stays_relative(self, tmp_path):
        assets = tmp_path / "assets"
        assets.mkdir()
        sprite = assets / "hero.png"
        sprite.write_bytes(b"x")
        ed = _make_collision_editor(data_root=tmp_path)
        assert ed._rel_path(sprite) == "assets/hero.png"

    def test_outside_root_uses_dotdot_not_absolute(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        sprite = tmp_path / "shared" / "hero.png"
        sprite.parent.mkdir()
        sprite.write_bytes(b"x")
        ed = _make_collision_editor(data_root=proj)
        rel = ed._rel_path(sprite)
        assert not Path(rel).is_absolute(), rel
        assert rel == "../shared/hero.png", rel

    def test_from_path_outside_root_not_absolute(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        sprite = tmp_path / "shared" / "fire.png"
        sprite.parent.mkdir()
        pygame.image.save(_strip(16, 16), str(sprite))
        from plugins.character_collision.editor import CharacterCollisionEditor

        ed = CharacterCollisionEditor.from_path(
            sprite_path=sprite, character_name="Fire", data_root=proj
        )
        assert ed._image_path is not None
        assert not Path(ed._image_path).is_absolute(), ed._image_path
        assert ed._image_path == "../shared/fire.png", ed._image_path

    def test_dotdot_resolves_back(self, tmp_path):
        """The saved form must resolve via the loader's base-parents walk."""
        proj = tmp_path / "proj"
        coll_dir = proj / "data" / "collision"
        coll_dir.mkdir(parents=True)
        sprite = tmp_path / "shared" / "hero.png"
        sprite.parent.mkdir()
        sprite.write_bytes(b"x")
        ed = _make_collision_editor(data_root=proj)
        rel = ed._rel_path(sprite)
        resolved = ed._resolve_image_path(rel, base=coll_dir)
        assert resolved is not None
        assert resolved.resolve() == sprite.resolve()
