"""Theme system tests: built-in registry, text_on_accent token, custom themes."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from widgets.ui.theme import (  # noqa: E402
    THEMES,
    UIColorSet,
    get_theme_manager,
    set_theme,
)


@pytest.fixture(autouse=True)
def restore_default_theme():
    # other suites call pygame.quit() in teardowns; theme swaps touch font
    # caches so make sure pygame is alive before and after each test
    import pygame

    if not pygame.get_init():
        pygame.init()
    if not pygame.display.get_init():
        pygame.display.set_mode((1, 1))
    yield
    set_theme("dark")


class TestBuiltinThemes:
    def test_monokai_registered(self):
        assert "monokai" in THEMES
        colors = THEMES["monokai"]
        assert colors.bg == (39, 40, 34)
        assert colors.accent == (253, 151, 31)

    def test_midnight_registered(self):
        assert "midnight" in THEMES
        colors = THEMES["midnight"]
        assert colors.bg == (10, 13, 22)
        assert colors.accent == (45, 190, 205)

    def test_nord_registered(self):
        assert "nord" in THEMES
        colors = THEMES["nord"]
        assert colors.bg == (32, 36, 47)
        assert colors.accent == (136, 192, 208)
        # light frost accent needs dark foreground for contrast
        assert sum(colors.text_on_accent) / 3 < 100

    def test_settings_catalog_covers_registry(self):
        from tilemap_editor.settings import BUILTIN_THEMES

        assert set(THEMES) <= set(BUILTIN_THEMES), set(THEMES) - set(BUILTIN_THEMES)

    def test_cli_help_derives_from_catalog(self):
        cli_path = Path(__file__).parent.parent / "src" / "tilemap_editor" / "cli.py"
        cli_source = cli_path.read_text(encoding="utf-8")
        assert "BUILTIN_THEMES" in cli_source

    def test_surfaces_have_elevation_depth(self):
        """No more flat same-bg-everywhere: bg/panel/alt/header distinct."""
        for name, colors in THEMES.items():
            assert len({colors.bg, colors.panel, colors.panel_alt,
                        colors.header}) == 4, name

    def test_set_theme_by_name(self):
        assert set_theme("monokai") is True
        assert get_theme_manager().name == "monokai"
        assert get_theme_manager().colors.bg == (39, 40, 34)

    def test_unknown_theme_fails_cleanly(self):
        assert set_theme("nope") is False

    def test_all_themes_have_text_on_accent(self):
        for name, colors in THEMES.items():
            assert colors.text_on_accent is not None, name
            assert len(colors.text_on_accent) == 3

    def test_light_theme_selected_takes_light_text(self):
        light = THEMES["light"]
        # selection is a mid blue: foreground must be light for contrast
        r, g, b = light.selected
        assert (r + g + b) / 3 < 160
        assert sum(light.text_on_accent) / 3 > 200


class TestTextOnAccentToken:
    def test_from_dict_hex_override(self):
        cs = UIColorSet.from_dict({"text_on_accent": "#111111"})
        assert cs.text_on_accent == (17, 17, 17)

    def test_from_dict_missing_uses_default(self):
        assert UIColorSet.from_dict({}).text_on_accent == (255, 255, 255)

    def test_dynamic_proxy_exposes_token(self):
        assert hasattr(get_theme_manager().colors, "text_on_accent")
