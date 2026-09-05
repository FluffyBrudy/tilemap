"""Tests for node selector key handling (no swallowing)."""

import os
import sys
from pathlib import Path

import pygame
import pytest
from pygame import Rect

from node_manager import NodeManager
from widgets.ui.node_selector import NodeSelector

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

pygame.init()
pygame.display.set_mode((1, 1))


@pytest.fixture(autouse=True)
def _reinit_pygame():
    # Earlier modules quit video in fixtures; get_mods needs it live.
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield


class FakeEditor:
    node_editing_mode = True
    node_editor = None

    def __init__(self):
        self.node_manager = NodeManager(object())


def make_selector():
    ed = FakeEditor()
    s = NodeSelector.__new__(NodeSelector)
    s.editor = ed
    s.rect = Rect(0, 65, 260, 240)
    s.search_text = ""
    s.scroll_offset = 0
    s.item_h = 28
    s.header_h = 32
    s.collapsed_groups = set()
    s._filtered_rows = []
    s._add_dropdown_open = False
    return s


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, {"key": key, "unicode": unicode})


class TestKeyRelease:
    def test_function_key_released(self, monkeypatch):
        s = make_selector()
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert s.handle_event(key_event(pygame.K_F1)) is False
        assert s.search_text == ""

    def test_f_key_empty_unicode_released(self, monkeypatch):
        s = make_selector()
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert s.handle_event(key_event(pygame.K_f, "")) is False
        assert s.search_text == ""

    def test_delete_released(self, monkeypatch):
        s = make_selector()
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert s.handle_event(key_event(pygame.K_DELETE, "")) is False

    def test_ctrl_combo_released(self, monkeypatch):
        s = make_selector()
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        monkeypatch.setattr(pygame.key, "get_mods", lambda: pygame.KMOD_LCTRL)
        assert s.handle_event(key_event(pygame.K_z, "\x1a")) is False


class TestSearchKept:
    def test_printable_typed(self, monkeypatch):
        s = make_selector()
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert s.handle_event(key_event(pygame.K_g, "g")) is True
        assert s.search_text == "g"

    def test_backspace_consumed(self, monkeypatch):
        s = make_selector()
        s.search_text = "ab"
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert s.handle_event(key_event(pygame.K_BACKSPACE, "\x08")) is True
        assert s.search_text == "a"

    def test_return_consumed(self, monkeypatch):
        s = make_selector()
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert s.handle_event(key_event(pygame.K_RETURN, "\r")) is True

    def test_escape_consumed(self, monkeypatch):
        s = make_selector()
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (0, 0))
        assert s.handle_event(key_event(pygame.K_ESCAPE, "")) is True
