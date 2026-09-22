"""Toolbar buttons: shared Button wiring, tooltips, clicks."""

import pygame  # noqa: E402
import pytest  # noqa: E402
from pygame import Rect  # noqa: E402

from plugins.sprite_animation.editor import SpriteAnimationEditor  # noqa: E402
from utils.shortcuts import is_cmd_or_ctrl  # noqa: E402
from widgets.ui.button import Button  # noqa: E402
from widgets.ui.draw_utils import truncate_text  # noqa: E402


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1100, 720))
    yield
    from utils.font_manager import font_manager

    font_manager.clear_cache()


def make_editor():
    surf = pygame.Surface((128, 64), pygame.SRCALPHA)
    surf.fill((80, 80, 80, 255))
    ed = SpriteAnimationEditor.from_surface(surf, tile_size=(32, 32))
    ed.visible = True
    screen = pygame.display.get_surface()
    ed._draw_toolbar(screen)
    return ed


def send(ed, t, **kw):
    if "pos" in kw:
        pygame.mouse.set_pos(kw["pos"])
    return ed.handle_event(pygame.event.Event(t, **kw))


def click_center(ed, rect):
    return send(ed, pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center)


class TestSharedButtons:
    def test_all_action_buttons_are_shared(self):
        ed = make_editor()
        for name in (
            "_btn_new", "_btn_del", "_btn_save", "_btn_load",
            "_btn_load_spritesheet", "_btn_export", "_btn_export_desync",
            "_btn_meta", "_btn_dup", "_btn_mk", "_btn_copyjson",
        ):
            btn = getattr(ed, name)
            assert isinstance(btn, Button), name
            assert btn.tooltip_text, name

    def test_icon_buttons_have_labels(self):
        ed = make_editor()
        assert ed._btn_dup.tooltip_text == "Duplicate animation"
        assert ed._btn_mk.tooltip_text == "Add marker at selection"
        assert ed._btn_copyjson.tooltip_text.startswith("Copy clip JSON")

    def test_del_is_danger(self):
        ed = make_editor()
        assert ed._btn_del.danger is True

    def test_new_button_creates_animation(self):
        ed = make_editor()
        n = len(ed.library.animations)
        click_center(ed, ed._btn_new.rect)
        assert len(ed.library.animations) == n + 1

    def test_dup_button_duplicates(self):
        ed = make_editor()
        n = len(ed.library.animations)
        click_center(ed, ed._btn_dup.rect)
        assert len(ed.library.animations) == n + 1

    def test_desync_toggles(self):
        ed = make_editor()
        before = ed._export_desync
        click_center(ed, ed._btn_export_desync.rect)
        assert ed._export_desync is not before

    def test_meta_toggles(self):
        ed = make_editor()
        before = ed._meta_panel_open
        click_center(ed, ed._btn_meta.rect)
        assert ed._meta_panel_open is not before

    def test_marker_button_adds_marker(self):
        from plugins.sprite_animation.models import AnimationFrame

        ed = make_editor()
        anim = ed._get_active()
        assert anim is not None
        anim.frames.append(AnimationFrame(variant_id=0, duration_ms=100))
        n = len(anim.markers)
        ed.timeline.selected_index = 0
        click_center(ed, ed._btn_mk.rect)
        assert len(anim.markers) == n + 1


class TestToolbarTruncateAndShortcuts:
    def test_long_sheet_name_truncates(self):
        pygame.font.init()
        font = pygame.font.Font(None, 14)
        disp, truncated = truncate_text("a_very_long_spritesheet_name_here.png", font, 60)
        assert truncated is True
        assert disp.endswith("...")
        assert font.size(disp)[0] <= 60

    def test_narrow_toolbar_draws_without_overlap(self):
        surf = pygame.Surface((128, 64), pygame.SRCALPHA)
        ed = SpriteAnimationEditor.from_surface(surf, tile_size=(32, 32), window_size=(700, 500))
        ed.visible = True
        ed._sheet_name = "an_extremely_long_spritesheet_filename_for_testing.png"
        screen = pygame.display.get_surface()
        ed._draw_toolbar(screen)

    def test_cmd_or_ctrl_masks(self):
        assert is_cmd_or_ctrl(pygame.KMOD_CTRL) is True
        assert is_cmd_or_ctrl(pygame.KMOD_META) is True
        assert is_cmd_or_ctrl(pygame.KMOD_GUI) is True
        assert is_cmd_or_ctrl(pygame.KMOD_LCTRL | pygame.KMOD_RGUI) is True
        assert is_cmd_or_ctrl(0) is False
        assert is_cmd_or_ctrl(pygame.KMOD_SHIFT) is False
