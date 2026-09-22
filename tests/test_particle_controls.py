"""Unit tests for the particle editor's control mappings.

Only the mappings with real consequences live here (log scale, integer
rounding, direction sentinel). The widgets themselves are exercised
through the e2e journeys.
"""

import pygame
import pytest

from plugins.particle_editor.controls import DirectionDial, NumberControl


def test_log_mapping_roundtrip():
    ctrl = NumberControl("lifetime_min", "Life min", 0.1, 5.0, 1.0, kind="log")
    assert ctrl._from_t(0.0) == pytest.approx(0.1)
    assert ctrl._from_t(1.0) == pytest.approx(5.0)
    assert ctrl._to_t(1.0) == pytest.approx(ctrl._to_t(ctrl._from_t(ctrl._to_t(1.0))))


def test_integer_rounding_and_clamp():
    ctrl = NumberControl("spawn_rate", "Rate", 1, 300, 10.6, integer=True)
    assert ctrl.value == 11
    ctrl.set_value(9999)
    assert ctrl.value == 300


def test_dial_random_and_degrees(monkeypatch):
    dial = DirectionDial(-1)
    assert dial.value == -1.0 and dial.random
    dial.set_rect(0, 0, 300)
    # Flip Random off via its toggle (box at x+92).
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (100, 11))
    event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 11))
    dial.handle_event(event)
    assert dial.random is False
    assert dial.value == pytest.approx(270.0)
    dial.set_value(45)
    assert dial.value == pytest.approx(45.0)
