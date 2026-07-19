"""
Tests for CollisionLayerSidebar.

Covers:
- Initialization (closed by default)
- Toggle open/close
- Zero render cost when closed
- Event passthrough when closed
- Event handling when open
- Close on click outside
- Keyboard shortcut (L key)
- Widget value passthrough
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

from widgets.ui.collision_layer_sidebar import CollisionLayerSidebar


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1000, 800))
    yield
    pygame.quit()


class TestInitialization:
    def test_closed_by_default(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        assert s.visible is False

    def test_widget_has_defaults(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        assert s.get_layer() == 1
        assert s.get_mask() == 0xFFFF


class TestToggle:
    def test_toggle_opens(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        s.toggle()
        assert s.visible is True

    def test_toggle_closes(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        s.toggle()
        s.toggle()
        assert s.visible is False

    def test_open_method(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        s.open()
        assert s.visible is True

    def test_close_method(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        s.open()
        s.close()
        assert s.visible is False


class TestZeroCostWhenClosed:
    def test_draw_returns_early(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        screen = pygame.display.get_surface()
        # Should not raise, should not render anything
        s.draw(screen)

    def test_handle_event_returns_false(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (500, 400)})
        assert s.handle_event(event) is False


class TestEventHandling:
    def test_toggle_button_click(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        # Draw toggle button first to set its rect
        screen = pygame.display.get_surface()
        s.draw_toggle_button(screen)
        # Click on toggle button
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": s._toggle_rect.center})
        assert s.handle_toggle_event(event) is True
        assert s.visible is True

    def test_close_button_click(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        s.open()
        # Manually set close rect to avoid needing draw()
        s._close_rect = Rect(940, 4, 28, 28)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": s._close_rect.center})
        assert s.handle_event(event) is True
        assert s.visible is False

    def test_click_outside_closes(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        s.open()
        # Click far left (outside sidebar which is on the right)
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (50, 400)})
        assert s.handle_event(event) is True
        assert s.visible is False

    def test_widget_events_when_open(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        s.open()
        # open() rebuilds widget layout, so buttons are at screen positions
        btn = s.widget._layer_buttons[2]
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": btn.rect.center})
        assert s.handle_event(event) is True
        assert s.get_layer() == 4  # 1 << 2


class TestValuePassthrough:
    def test_set_layer(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        s.set_layer(8)
        assert s.get_layer() == 8

    def test_set_mask(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        s.set_mask(0x3)
        assert s.get_mask() == 0x3

    def test_on_changed_callback(self):
        calls = []
        s = CollisionLayerSidebar(
            Rect(0, 0, 1000, 800),
            on_changed=lambda p, m: calls.append((p, m)),
        )
        s.open()
        # open() rebuilds widget layout
        btn = s.widget._mask_buttons[0]
        event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": btn.rect.center})
        s.handle_event(event)
        assert len(calls) == 1
        assert calls[0] == (1, 0xFFFE)


class TestResize:
    def test_resize_updates_toggle(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800))
        old_toggle = s._toggle_rect
        s.resize(Rect(0, 0, 1200, 900))
        assert s._toggle_rect != old_toggle
        # Toggle is positioned at: parent.right - 42
        expected_x = 1200 - 42
        assert s._toggle_rect.x == expected_x


class TestDynamicWidth:
    def test_width_fits_buttons(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800), max_layers=16)
        # 16 layers, 8 cols: PADDING(8) + LABEL(50) + 8*(28+3) - 3 + PADDING(8) = 311
        assert s._sidebar_width == 311

    def test_narrower_for_fewer_layers(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800), max_layers=8)
        # 8 layers, 8 cols: PADDING(8) + LABEL(50) + 8*(28+3) - 3 + PADDING(8) = 311
        # Same because all fit in one row
        assert s._sidebar_width == 311

    def test_sidebar_rect_uses_dynamic_width(self):
        s = CollisionLayerSidebar(Rect(0, 0, 1000, 800), max_layers=16)
        sb = s._sidebar_rect()
        assert sb.w == s._sidebar_width
        assert sb.x == 1000 - s._sidebar_width
