from typing import TYPE_CHECKING
from constants import MAIN_PANEL_ID

if TYPE_CHECKING:
    from ttypes.theme import TTheme

DEFAULT_THEME: "TTheme" = {
    "defaults": {
        "colours": {
            "normal_bg": "#2b2e34",
            "hovered_bg": "#3c4048",
            "disabled_bg": "#1f2227",
            "selected_bg": "#1a5276",
            "normal_text": "#e0e0e0",
            "hovered_text": "#ffffff",
            "normal_border": "#555555",
        },
    },
    MAIN_PANEL_ID: {
        "colours": {"dark_bg": "rgb(60, 65, 70)"},
        "misc": {"border_width": "0"},
    },
    "label": {
        "font": {"name": "noto_sans", "bold": "1", "size": "14"},
        "colours": {"normal_text": "#f0f0f0"},
    },
    "#submit_button": {
        # fmt: off
        "colours": {
            "normal_bg": "#2b2e34",
            "hovered_bg": "#3c4048",
            "active_bg": "#2b2e34",
            "selected_bg": "#1a5276",
            "disabled_bg": "#1f2227",
            
            "normal_text": "#e0e0e0",
            "hovered_text": "#ffffff",
            "active_text": "#e0e0e0",
            "selected_text": "#ffffff",
            "disabled_text": "#808080",
            
            "normal_text_shadow": "#2b2e34",
            "hovered_text_shadow": "#3c4048",
            "active_text_shadow": "#2b2e34",
            "selected_text_shadow": "#1a5276",
            "disabled_text_shadow": "#1f2227",
            
            "normal_border": "#2b2e34",
            "hovered_border": "#2a2e40",
            "active_border": "#2b2e34",
            "selected_border": "#1a5276",
            "disabled_border": "#1f2227",
        },
        # fmt: on
        "misc": {
            "border_width": "10",
            "shape_corner_radius": "2",
            "text_shadow_size": "2",
            "text_shadow_offset": "0,0",
        },
    },
    "@alert": {
        "colours": {
            "normal_bg": "#3e3e3e",
            "normal_border": "#e74c3c",
            "normal_text": "#ffffff",
        },
        "misc": {"border_width": "2", "shadow_width": "3"},
    },
    "@alert.text_box": {
        "colours": {
            "dark_bg": "#4b4b4b",
            "normal_text": "#ffffff",
        },
        "misc": {"border_width": "0", "shadow_width": "0"},
    },
    "@alert.#dismiss_button": {
        "colours": {
            "normal_bg": "#e74c3c",
            "hovered_bg": "#c0392b",
            "normal_text": "#ffffff",
        }
    },
    "#tile_grid": {"colours": {"normal_bg": "#ff0000", "dark_bg": "#ff0000"}},
    "#tileset_btm_toolbar": {},
}
