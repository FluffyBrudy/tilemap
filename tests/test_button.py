"""Unit tests for the shared Button widget.

The press/release latch lives here, so every consumer (toolbars,
dialogs, standalone editors) inherits it without re-testing it.
"""

import pygame
import pytest
from pygame import Rect

from widgets.ui.button import Button


def _button(**overrides):
    rect = overrides.pop("rect", Rect(10, 10, 64, 24))
    overrides.setdefault("text", "Go")
    return Button(rect, **overrides)


def _down(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=pos)


def _up(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos)


def _motion(pos):
    return pygame.event.Event(
        pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)
    )


class TestPressRelease:
    def test_press_fires_click_and_latches(self):
        calls = []
        btn = _button(on_click=lambda: calls.append(1))
        assert btn.handle_event(_down((20, 20))) is True
        assert calls == [1]
        assert btn._pressed is True

    def test_release_unlatches(self):
        btn = _button(on_click=lambda: None)
        btn.handle_event(_down((20, 20)))
        assert btn.handle_event(_up((20, 20))) is False
        assert btn._pressed is False

    def test_release_outside_still_unlatches(self):
        btn = _button(on_click=lambda: None)
        btn.handle_event(_down((20, 20)))
        btn.handle_event(_up((500, 500)))
        assert btn._pressed is False

    def test_press_outside_ignores(self):
        calls = []
        btn = _button(on_click=lambda: calls.append(1))
        assert btn.handle_event(_down((500, 500))) is False
        assert calls == []
        assert btn._pressed is False

    def test_right_button_ignores(self):
        calls = []
        btn = _button(on_click=lambda: calls.append(1))
        assert btn.handle_event(_down((20, 20), button=3)) is False
        assert calls == []


class TestHoverAndActive:
    def test_hover_tracks_motion(self):
        btn = _button()
        btn.handle_event(_motion((20, 20)))
        assert btn._hovered is True
        btn.handle_event(_motion((500, 500)))
        assert btn._hovered is False

    def test_active_flag_is_plain_state(self):
        btn = _button()
        assert btn.active is False
        btn.active = True
        assert btn.active is True


class TestEnabled:
    def test_disabled_ignores_press(self):
        calls = []
        btn = _button(on_click=lambda: calls.append(1))
        btn.enabled = False
        assert btn.handle_event(_down((20, 20))) is False
        assert calls == []
        assert btn._pressed is False


class TestDraw:
    @pytest.mark.parametrize("kwargs", [{}, {"accent": True}, {"danger": True}])
    def test_draw_variants_do_not_raise(self, kwargs):
        btn = _button(**kwargs)
        screen = pygame.Surface((200, 100))
        btn.active = True
        btn.draw(screen)
        btn.active = False
        btn.handle_event(_motion((20, 20)))
        btn.draw(screen)

    def test_icon_button_draws(self):
        btn = _button(text="", icon_key="save", icon_size=16)
        btn.draw(pygame.Surface((200, 100)))
