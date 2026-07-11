"""
Tests for CollisionLayerMaskWidget.

Covers:
- Initialization with defaults and custom values
- Layer single-select (radio) behavior
- Mask multi-select (checkbox) behavior
- get_layer / set_layer correctness
- get_mask / set_mask correctness
- on_changed callback
- Event handling (mouse clicks)
- Edge cases (zero values, max values)
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest
import pygame
from pygame import Rect

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from widgets.ui.collision_layer_mask import CollisionLayerMaskWidget


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


class TestInitialization:
    def test_defaults(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        assert w.get_layer() == 1
        assert w.get_mask() == 0xFFFF
        assert w.max_layers == 16

    def test_custom_initial_values(self):
        w = CollisionLayerMaskWidget(
            Rect(0, 0, 400, 80),
            initial_layer=4,
            initial_mask=0x5,
        )
        assert w.get_layer() == 4
        assert w.get_mask() == 0x5

    def test_zero_layer_defaults_to_one(self):
        w = CollisionLayerMaskWidget(
            Rect(0, 0, 400, 80),
            initial_layer=0,
        )
        assert w.get_layer() == 1

    def test_max_layers_capped(self):
        w = CollisionLayerMaskWidget(
            Rect(0, 0, 400, 80),
            max_layers=64,
        )
        assert w.max_layers == 32


class TestLayerSingleSelect:
    def test_set_layer_power_of_two(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        w.set_layer(1)  # bit 0
        assert w.get_layer() == 1
        w.set_layer(2)  # bit 1
        assert w.get_layer() == 2
        w.set_layer(8)  # bit 3
        assert w.get_layer() == 8
        w.set_layer(32768)  # bit 15
        assert w.get_layer() == 32768

    def test_set_layer_zero_defaults_to_one(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        w.set_layer(0)
        assert w.get_layer() == 1

    def test_layer_click_sets_single_bit(self):
        """Clicking a layer button should set only that bit."""
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        w.set_layer(4)
        assert w.get_layer() == 4
        w.set_layer(1)
        assert w.get_layer() == 1
        assert w.get_layer() & 4 == 0  # old bit cleared


class TestMaskMultiSelect:
    def test_set_mask_various(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        w.set_mask(0)
        assert w.get_mask() == 0
        w.set_mask(0xFFFF)
        assert w.get_mask() == 0xFFFF
        w.set_mask(0x5)
        assert w.get_mask() == 0x5

    def test_mask_toggle_bits(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        w.set_mask(0)
        w.set_mask(0x1)
        assert w.get_mask() == 0x1
        w.set_mask(w.get_mask() | 0x4)
        assert w.get_mask() == 0x5


class TestOnChangedCallback:
    def test_callback_fires_on_layer_change(self):
        calls = []
        w = CollisionLayerMaskWidget(
            Rect(0, 0, 400, 80),
            on_changed=lambda l, m: calls.append((l, m)),
        )
        w.set_layer(2)
        assert len(calls) == 0  # set_layer doesn't fire callback (only events do)

    def test_callback_fires_on_event(self):
        calls = []
        w = CollisionLayerMaskWidget(
            Rect(0, 0, 400, 80),
            initial_layer=1,
            initial_mask=0xFFFF,
            on_changed=lambda l, m: calls.append((l, m)),
        )
        # Simulate click on layer button 2 (bit index 1)
        btn = w._layer_buttons[1]
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": btn.rect.center}
        )
        w.handle_event(event)
        assert len(calls) == 1
        assert calls[0] == (2, 0xFFFF)

    def test_callback_fires_on_mask_click(self):
        calls = []
        w = CollisionLayerMaskWidget(
            Rect(0, 0, 400, 80),
            initial_layer=1,
            initial_mask=0xFFFF,
            on_changed=lambda l, m: calls.append((l, m)),
        )
        # Simulate click on mask button 1 (bit index 0) to toggle off
        btn = w._mask_buttons[0]
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": btn.rect.center}
        )
        w.handle_event(event)
        assert len(calls) == 1
        assert calls[0] == (1, 0xFFFE)  # bit 0 toggled off


class TestEventHandling:
    def test_layer_click_returns_true(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        btn = w._layer_buttons[0]
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": btn.rect.center}
        )
        assert w.handle_event(event) is True

    def test_mask_click_returns_true(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        btn = w._mask_buttons[0]
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": btn.rect.center}
        )
        assert w.handle_event(event) is True

    def test_click_outside_returns_false(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (500, 500)}
        )
        assert w.handle_event(event) is False

    def test_mouse_motion_does_not_consume(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        event = pygame.event.Event(pygame.MOUSEMOTION, {"pos": (100, 50)})
        assert w.handle_event(event) is False

    def test_layer_click_sets_correct_bit(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        # Click layer button 3 (bit index 2)
        btn = w._layer_buttons[2]
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": btn.rect.center}
        )
        w.handle_event(event)
        assert w.get_layer() == 4  # 1 << 2

    def test_mask_click_toggles_bit(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80), initial_mask=0xFFFF)
        # Click mask button 1 (bit index 0) to toggle off
        btn = w._mask_buttons[0]
        event = pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": btn.rect.center}
        )
        w.handle_event(event)
        assert w.get_mask() == 0xFFFE
        # Click again to toggle on
        w.handle_event(event)
        assert w.get_mask() == 0xFFFF


class TestResize:
    def test_resize_rebuilds_buttons(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        old_layer_buttons = list(w._layer_buttons)
        w.resize(Rect(0, 0, 600, 100))
        assert w._layer_buttons is not old_layer_buttons
        assert w.rect == Rect(0, 0, 600, 100)


class TestDraw:
    def test_draw_no_exception(self):
        w = CollisionLayerMaskWidget(Rect(0, 0, 400, 80))
        screen = pygame.display.get_surface()
        w.draw(screen)


class TestCalcSize:
    def test_min_width_16_layers(self):
        assert CollisionLayerMaskWidget.calc_min_width(16) == 311

    def test_min_width_8_layers(self):
        assert CollisionLayerMaskWidget.calc_min_width(8) == 311

    def test_min_height_16_layers(self):
        assert CollisionLayerMaskWidget.calc_min_height(16) == 114

    def test_min_height_8_layers(self):
        assert CollisionLayerMaskWidget.calc_min_height(8) == 64
