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
    yield
    set_theme("dark")


class TestBuiltinThemes:
    def test_monokai_registered(self):
        assert "monokai" in THEMES
        colors = THEMES["monokai"]
        assert colors.bg == (39, 40, 34)
        assert colors.accent == (253, 151, 31)

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
