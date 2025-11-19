from typing import TYPE_CHECKING
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
        "colours": {"dark_bg": "rgb(100, 100, 50)"},
        "misc": {"border_width": "0"},
    },
}
