"""Unit tests for the shared ToastManager.

Alert surfacing (blocked actions, failures) is verified here once,
so editors only assert *which* toast they emit, never the mechanics.
"""

import pygame
import pytest

from widgets.ui.toast import ToastManager


def _screen():
    return pygame.Surface((1180, 760))


class TestVariants:
    @pytest.mark.parametrize(
        "method",
        ["success", "warning", "error"],
    )
    def test_variant_queued_with_message(self, method):
        mgr = ToastManager()
        getattr(mgr, method)("hello")
        assert len(mgr._toasts) == 1
        assert mgr._toasts[0].variant == method
        assert mgr._toasts[0].message == "hello"

    def test_show_default_variant(self):
        mgr = ToastManager()
        mgr.show("plain")
        assert mgr._toasts[0].variant == "default"


class TestExpiry:
    def test_toast_clears_after_duration(self):
        mgr = ToastManager()
        mgr.show("gone soon", duration=0.1)
        screen = _screen()
        for _ in range(60):
            mgr.update(screen, 1 / 60)
        assert mgr._toasts == []

    def test_fresh_toast_survives(self):
        mgr = ToastManager()
        mgr.warning("blocked")
        mgr.update(_screen(), 1 / 60)
        assert len(mgr._toasts) == 1


class TestDraw:
    def test_draw_does_not_raise(self):
        mgr = ToastManager()
        mgr.success("saved")
        mgr.warning("blocked")
        mgr.error("failed")
        screen = _screen()
        mgr.update(screen, 1 / 60)
        mgr.draw(screen)

    def test_draw_empty_is_noop(self):
        mgr = ToastManager()
        mgr.draw(_screen())
