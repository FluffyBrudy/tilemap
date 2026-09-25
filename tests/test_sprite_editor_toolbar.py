"""Sprite editor toolbar tests: layout-engine migration.

Covers: cluster build at wide widths, mode icons, overflow collapse
with Export pinned right, overflow rows (incl. mode switching),
Tight toggle state sync.
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


def _make_editor(w=1000, h=700):
    from plugins.sprite_editor.editor import SpriteEditor

    return SpriteEditor(Rect(0, 0, w, h))


class TestClusterBuild:
    def test_groups_and_separators(self):
        ed = _make_editor()
        assert ed._get_btn("overflow") is None
        # file | edit | tools+tight | modes | view, export pinned right
        assert len(ed._separators) == 4
        export = ed._get_btn("export_all")
        assert getattr(export, "visible", True) is True
        assert export.rect.right == ed.rect.right - 6

    def test_mode_icons(self):
        ed = _make_editor()
        icons = {m.id: m.icon_key for m in ed._mode_indicator.modes}
        assert icons == {"grid": "grid", "regions": "region", "free": "free"}

    def test_all_buttons_visible_when_wide(self):
        ed = _make_editor(1600, 800)
        assert ed._toolbar.hidden == []
        for btn in ed._buttons:
            assert getattr(btn, "visible", True) is True


class TestOverflow:
    def test_collapse_pins_export(self):
        ed = _make_editor(300, 500)
        assert ed._get_btn("overflow") is not None
        export = ed._get_btn("export_all")
        assert getattr(export, "visible", True) is True
        assert export.rect.right == ed.rect.right - 6
        overflow = ed._get_btn("overflow")
        assert overflow.rect.right <= export.rect.x - 4

    def test_collapse_order_view_first(self):
        ed = _make_editor(640, 500)
        hidden_tags = {
            getattr(e.widget, "_tag", "") for e in ed._toolbar.hidden if e.kind == "widget"
        }
        # view cluster goes before tools/modes/edit/file
        assert "zoom_out" in hidden_tags
        assert "open" not in hidden_tags
        assert "undo" not in hidden_tags

    def test_overflow_mode_row_switches_mode(self):
        ed = _make_editor(300, 500)
        rows = ed._toolbar.overflow_rows()
        free = next(r for r in rows if r.label == "Free")
        free.on_activate()
        assert ed.mode == "free"
        assert ed._mode_indicator.active_mode_id == "free"

    def test_widening_restores(self):
        ed = _make_editor(300, 500)
        assert ed._toolbar.hidden
        ed.resize(0, 0, 1400, 800)
        assert ed._toolbar.hidden == []
        assert ed._get_btn("overflow") is None


class TestTightToggle:
    def test_default_off_and_syncs(self):
        ed = _make_editor()
        assert ed._free_tool.tight is False
        ed._toggle_tight()
        assert ed._free_tool.tight is True
        ed._update_button_states()
        assert ed._get_btn("tight").active is True
        ed._toggle_tight()
        assert ed._free_tool.tight is False

class TestSheetOpenFit:
    def test_load_fits_90_percent(self):
        from plugins.sprite_editor.editor import SpriteEditor

        ed = SpriteEditor(Rect(0, 0, 1000, 700))
        surf = pygame.Surface((512, 1024), pygame.SRCALPHA)
        surf.fill((60, 60, 60, 255))
        ed._load_surface(surf, ["strip"])
        content = ed.viewport.content_rect
        expected = 0.9 * min(content.w / 512, content.h / 1024)
        assert ed.camera.zoom == pytest.approx(expected)
        sheet = ed.viewport.sheet_screen_rect()
        assert sheet is not None
        assert content.contains(sheet)

    def test_small_sheet_opens_at_100_percent(self):
        from plugins.sprite_editor.editor import SpriteEditor

        ed = SpriteEditor(Rect(0, 0, 1000, 700))
        surf = pygame.Surface((128, 128), pygame.SRCALPHA)
        surf.fill((60, 60, 60, 255))
        ed._load_surface(surf, ["small"])
        assert ed.camera.zoom == 1.0
        assert (ed.camera.scroll_x, ed.camera.scroll_y) == (0.0, 0.0)

    def test_file_manager_top_left(self):
        from plugins.sprite_editor.editor import SpriteEditor

        ed = SpriteEditor(Rect(0, 0, 1000, 700))
        rect = ed._file_manager_rect()
        content = ed.viewport.content_rect
        assert (rect.x, rect.y) == (content.x + 12, content.y + 12)
        assert ed.rect.contains(rect)


class TestTightToggleMenu:
    def test_view_menu_reflects_state(self):
        ed = _make_editor()
        view = next(m for m in ed.menubar.menus if m.label == "View")
        tight = next(a for a in view.actions if getattr(a, "label", "") == "Tight Marquee")
        assert tight.is_checked() is False
        ed._toggle_tight()
        assert tight.is_checked() is True
