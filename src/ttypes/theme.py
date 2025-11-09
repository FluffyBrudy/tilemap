from typing import TypedDict, NotRequired  
  
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
  
class TTheme(TypedDict, total=False):  
    defaults: ThemeBlock