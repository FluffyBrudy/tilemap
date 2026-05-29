"""
Tests for Timeline.invalidate_cache() added in PR.

Also covers set_surface and set_frames cache-clearing behavior that
invalidate_cache now consolidates.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from pathlib import Path
import pytest
import pygame
from pygame import Rect

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


def _make_surface(w=128, h=64, color=(255, 0, 0)) -> pygame.Surface:
    """Create a simple coloured surface for testing."""
    surf = pygame.Surface((w, h))
    surf.fill(color)
    return surf


def _make_timeline(tile_size=(32, 32), surf_size=(128, 64)) -> "Timeline":
    from plugins.sprite_animation.timeline import Timeline

    surf = _make_surface(*surf_size)
    rect = Rect(0, 0, 400, 120)
    return Timeline(rect=rect, surface=surf, tile_size=tile_size)


class TestInvalidateCache:
    """Tests for Timeline.invalidate_cache()."""

    def test_invalidate_cache_clears_empty_cache(self):
        """invalidate_cache() is safe to call when cache is already empty."""
        tl = _make_timeline()
        tl.invalidate_cache()
        assert tl._thumb_cache == {}

    def test_invalidate_cache_clears_populated_cache(self):
        """invalidate_cache() removes all entries from _thumb_cache."""
        from plugins.sprite_animation.models import AnimationFrame

        tl = _make_timeline(tile_size=(32, 32), surf_size=(128, 64))
        # Populate the cache by adding frames and calling _get_thumb
        tl.frames = [AnimationFrame(variant_id=0)]
        _ = tl._get_thumb(0)  # should add entry to cache
        assert len(tl._thumb_cache) > 0

        tl.invalidate_cache()
        assert tl._thumb_cache == {}

    def test_invalidate_cache_multiple_entries(self):
        """invalidate_cache() clears all cached thumbnails, not just one."""
        from plugins.sprite_animation.models import AnimationFrame

        tl = _make_timeline(tile_size=(32, 32), surf_size=(128, 64))
        tl.frames = [
            AnimationFrame(variant_id=0),
            AnimationFrame(variant_id=1),
            AnimationFrame(variant_id=2),
        ]
        # Populate cache for all three
        tl._get_thumb(0)
        tl._get_thumb(1)
        tl._get_thumb(2)
        assert len(tl._thumb_cache) == 3

        tl.invalidate_cache()
        assert len(tl._thumb_cache) == 0

    def test_invalidate_cache_can_be_called_repeatedly(self):
        """Calling invalidate_cache() multiple times is safe."""
        tl = _make_timeline()
        tl.invalidate_cache()
        tl.invalidate_cache()
        tl.invalidate_cache()
        assert tl._thumb_cache == {}

    def test_cache_repopulates_after_invalidate(self):
        """After invalidate_cache(), thumbnails can be re-generated."""
        from plugins.sprite_animation.models import AnimationFrame

        tl = _make_timeline(tile_size=(32, 32), surf_size=(128, 64))
        tl.frames = [AnimationFrame(variant_id=0)]
        tl._get_thumb(0)
        tl.invalidate_cache()
        assert tl._thumb_cache == {}

        # Re-generate
        thumb = tl._get_thumb(0)
        assert 0 in tl._thumb_cache
        assert thumb is not None

    def test_set_surface_clears_cache(self):
        """set_surface() already clears _thumb_cache (existing behaviour)."""
        from plugins.sprite_animation.models import AnimationFrame

        tl = _make_timeline(tile_size=(32, 32), surf_size=(128, 64))
        tl.frames = [AnimationFrame(variant_id=0)]
        tl._get_thumb(0)
        assert len(tl._thumb_cache) > 0

        new_surf = _make_surface(128, 64, color=(0, 255, 0))
        tl.set_surface(new_surf)
        assert tl._thumb_cache == {}

    def test_set_frames_clears_cache(self):
        """set_frames() already clears _thumb_cache (existing behaviour)."""
        from plugins.sprite_animation.models import AnimationFrame

        tl = _make_timeline(tile_size=(32, 32), surf_size=(128, 64))
        tl.frames = [AnimationFrame(variant_id=0)]
        tl._get_thumb(0)
        assert len(tl._thumb_cache) > 0

        tl.set_frames([AnimationFrame(variant_id=1)])
        assert tl._thumb_cache == {}

    def test_invalidate_cache_is_public_method(self):
        """invalidate_cache should be accessible as a public method."""
        tl = _make_timeline()
        assert callable(tl.invalidate_cache)

    def test_invalidate_after_grid_offset_change(self):
        """Caller must invalidate cache after changing grid offsets."""
        from plugins.sprite_animation.models import AnimationFrame

        tl = _make_timeline(tile_size=(32, 32), surf_size=(128, 64))
        tl.frames = [AnimationFrame(variant_id=0)]
        tl._get_thumb(0)
        assert 0 in tl._thumb_cache

        # Simulate what the editor does when grid offset changes
        tl.grid_offset_x = 8
        tl.grid_offset_y = 8
        tl.invalidate_cache()

        assert tl._thumb_cache == {}
        # Re-fetching the thumb should use the new offset
        tl._get_thumb(0)  # might return None if out-of-bounds; either is valid