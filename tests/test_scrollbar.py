"""Unit tests for the shared Scrollbar engine.

Range math, drag, and wheel behavior are pinned here once; consumers
(particle strip, sidebar, tile grid) only assert integration.
"""

import pygame
import pytest
from pygame import Rect

from widgets.ui.scrollbar import Scrollbar


def _bar(**overrides):
    bar = Scrollbar("horizontal", Rect(0, 0, 200, 12))
    bar.set_range(1000, 200, 0)
    for key, value in overrides.items():
        setattr(bar, key, value)
    return bar


def _down(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=pos)


def _motion(pos, rel=(0, 0)):
    return pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=rel, buttons=(0, 0, 0))


class TestRange:
    def test_no_scroll_when_content_fits(self):
        bar = Scrollbar("horizontal", Rect(0, 0, 200, 12))
        bar.set_range(100, 200, 0)
        assert bar.max_scroll == 0
        assert bar.thumb_size == bar._track_size

    def test_scroll_pos_clamped_to_range(self):
        bar = _bar()
        bar.set_range(1000, 200, 9999)
        assert bar.scroll_pos == 800
        bar.set_range(1000, 200, -50)
        assert bar.scroll_pos == 0

    def test_thumb_shrinks_with_content_ratio(self):
        roomy = _bar()
        roomy.set_range(400, 200, 0)
        tight = _bar()
        tight.set_range(2000, 200, 0)
        assert roomy.thumb_size > tight.thumb_size


class TestDrag:
    def test_drag_thumb_moves_scroll(self):
        seen = []
        bar = Scrollbar("horizontal", Rect(0, 0, 200, 12), on_scroll=seen.append)
        bar.set_range(1000, 200, 0)
        thumb = bar._thumb_rect()
        assert bar.handle_event(_down(thumb.center)) is True
        bar.handle_event(_motion((150, 6), rel=(140, 0)))
        assert bar.scroll_pos > 0
        assert seen and seen[-1] == bar.scroll_pos

    def test_release_ends_drag(self):
        bar = _bar()
        bar.handle_event(_down(bar._thumb_rect().center))
        assert bar._dragging is True
        up = pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(0, 0))
        assert bar.handle_event(up) is True
        assert bar._dragging is False

    def test_track_click_jumps(self):
        bar = _bar()
        assert bar.handle_event(_down((190, 6))) is True
        assert bar.scroll_pos > 0

    def test_click_outside_ignored(self):
        bar = _bar()
        assert bar.handle_event(_down((500, 500))) is False
        assert bar.scroll_pos == 0


class TestWheel:
    def test_wheel_down_scrolls_when_hovered(self):
        seen = []
        bar = Scrollbar("vertical", Rect(0, 0, 12, 200), on_scroll=seen.append)
        bar.set_range(1000, 200, 0)
        bar.handle_event(_motion((6, 100)))
        wheel = pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-3)
        assert bar.handle_event(wheel) is True
        assert bar.scroll_pos > 0
        assert seen == [bar.scroll_pos]

    def test_wheel_ignored_when_not_hovered(self):
        bar = _bar()
        wheel = pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-3)
        assert bar.handle_event(wheel) is False
        assert bar.scroll_pos == 0


class TestDraw:
    def test_draw_hidden_bar_is_noop(self):
        bar = Scrollbar("horizontal", Rect(0, 0, 200, 12))
        bar.set_range(100, 200, 0)
        bar.draw(pygame.Surface((300, 100)))  # must not raise

    def test_draw_shows_thumb(self):
        bar = _bar()
        bar.handle_event(_motion((100, 6)))
        bar.draw(pygame.Surface((300, 100)))
