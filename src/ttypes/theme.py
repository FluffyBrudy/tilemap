from typing import Dict, TypedDict, Union


class ThemeColours(TypedDict, total=False):
    normal_bg: str
    hovered_bg: str
    disabled_bg: str
    selected_bg: str
    active_bg: str
    dark_bg: str
    disabled_dark_bg: str
    normal_text: str
    hovered_text: str
    disabled_text: str
    selected_text: str
    active_text: str
    normal_border: str
    hovered_border: str
    disabled_border: str
    selected_border: str
    active_border: str
    link_text: str
    link_hover: str
    link_selected: str
    text_shadow: str
    filled_bar: str
    unfilled_bar: str
    text_cursor: str


class ThemeMisc(TypedDict, total=False):
    shape: str
    shape_corner_radius: str
    border_width: str
    shadow_width: str
    tool_tip_delay: str
    text_horiz_alignment_padding: str
    enable_arrow_buttons: str
    sliding_button_width: str


class ThemeFont(TypedDict, total=False):
    name: str
    size: str
    bold: str
    italic: str
    regular_path: str
    bold_path: str
    italic_path: str
    bold_italic_path: str


class ThemeImages(TypedDict, total=False):
    normal_image: dict
    hovered_image: dict
    disabled_image: dict
    selected_image: dict
    active_image: dict


class ThemeBlock(TypedDict, total=False):
    colours: ThemeColours
    misc: ThemeMisc
    font: ThemeFont
    images: ThemeImages
    prototype: str


class TThemeBase(TypedDict, total=False):
    defaults: ThemeBlock


TTheme = Union[Dict[str, ThemeBlock], TThemeBase]


"""
USUAGE:
from typing import TYPE_CHECKING, Dict, cast
from constants import MAIN_PANEL_ID


if TYPE_CHECKING:
    from ttypes.theme import TTheme


DEFAULT_THEME: "TTheme" = {
    "defaults": {
        "colours": {
            "normal_bg": "#ff0000",
            "hovered_bg": "#35393e",
            "disabled_bg": "#25292e",
            "selected_bg": "#193754",
            "normal_text": "#c5cbd8",
            "hovered_text": "#FFFFFF",
            "normal_border": "#DDDDDD",
        }
    },
    MAIN_PANEL_ID: {
        "colours": {"dark_bg": "rgb(50, 100, 50)"},
        "misc": {"border_width": "0"},
    },
}
"""
"""
NOTE: It is required you to add TTheme option in union of UIManager
        self.manager = pygame_gui.UIManager(
            (self.width, self.height), DEFAULT_THEME, enable_live_theme_updates=True
        )
        right now linter show error because TTheme isnt in your type system.
"""
