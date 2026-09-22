"""Temp test: FramePicker fit_sheet keeps small sheets visible below the header."""

import pygame  # noqa: E402
import pytest  # noqa: E402
from pygame import Rect  # noqa: E402

from plugins.sprite_animation.frame_picker import (  # noqa: E402
    TOP_BAR_TOTAL,
    FramePicker,
)


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((900, 700))
    yield
    pygame.quit()


def test_small_sheet_centered_one_to_one():
    fp = FramePicker(Rect(0, 0, 400, 300), pygame.Surface((64, 64)), (32, 32))
    assert fp.zoom == 1.0
    img_x = fp.rect.x + fp.offset_x
    img_y = fp.rect.y + fp.offset_y
    assert img_x == pytest.approx((400 - 64) / 2)
    assert img_y >= TOP_BAR_TOTAL
    assert img_y == pytest.approx(TOP_BAR_TOTAL + (300 - TOP_BAR_TOTAL - 64) / 2)


def test_large_sheet_scaled_with_margin():
    fp = FramePicker(Rect(0, 0, 400, 300), pygame.Surface((800, 600)), (32, 32))
    assert fp.zoom < 1.0
    assert fp.zoom == pytest.approx(min(400 / 800, (300 - TOP_BAR_TOTAL) / 600) * 0.9)
    assert fp.rect.y + fp.offset_y >= TOP_BAR_TOTAL


def test_set_surface_refits():
    fp = FramePicker(Rect(0, 0, 400, 300), pygame.Surface((800, 600)), (32, 32))
    fp.offset_x, fp.offset_y, fp.zoom = 0.0, 0.0, 3.0
    fp.set_surface(pygame.Surface((64, 64)))
    assert fp.zoom == 1.0
    assert fp.rect.y + fp.offset_y >= TOP_BAR_TOTAL


def test_zero_key_refits():
    fp = FramePicker(Rect(0, 0, 400, 300), pygame.Surface((64, 64)), (32, 32))
    fp.offset_x, fp.offset_y, fp.zoom = 5.0, 5.0, 4.0
    pygame.mouse.set_pos((200, 200))
    fp.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_0}))
    assert fp.zoom == 1.0
    assert fp.rect.y + fp.offset_y >= TOP_BAR_TOTAL
