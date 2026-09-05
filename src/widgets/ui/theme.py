import json
from dataclasses import dataclass
from pathlib import Path

import pygame

from constants import THEME_PATH
from utils.font_manager import FontStyle, FontWeight, font_manager

Color = tuple[int, int, int]


@dataclass(frozen=True)
class UIColorSet:
    bg: Color = (16, 18, 24)
    panel: Color = (24, 27, 35)
    panel_alt: Color = (19, 22, 29)
    header: Color = (33, 37, 48)
    border: Color = (54, 60, 76)
    border_soft: Color = (36, 41, 54)
    text: Color = (232, 234, 240)
    text_dim: Color = (158, 164, 178)
    text_muted: Color = (118, 124, 140)
    text_on_accent: Color = (255, 255, 255)
    text_on_selected: Color = (255, 255, 255)
    accent: Color = (82, 132, 250)
    accent_hover: Color = (110, 155, 255)
    accent_active: Color = (62, 108, 220)
    success: Color = (74, 184, 124)
    danger: Color = (224, 92, 96)
    danger_hover: Color = (180, 70, 76)
    warning: Color = (232, 184, 84)
    hover: Color = (36, 41, 56)
    selected: Color = (44, 66, 128)
    overlay: Color = (0, 0, 0)
    shadow: Color = (0, 0, 0)
    scrollbar_thumb: Color = (85, 90, 100)
    scrollbar_thumb_hover: Color = (105, 110, 120)
    marker_colors: tuple[Color, ...] = (
        (255, 180, 80),
        (90, 190, 255),
        (190, 130, 255),
        (110, 220, 140),
        (255, 120, 160),
        (240, 240, 120),
    )

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "UIColorSet":
        """Create UIColorSet from a dict mapping field names to hex/rgb strings.

        Only fields present in data are overridden; missing fields use defaults.
        """
        kw = {}
        for field_name in cls.__dataclass_fields__:
            if field_name in data:
                raw = data[field_name]
                if isinstance(raw, str) and raw.startswith("#"):
                    h = raw.lstrip("#")
                    kw[field_name] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
                elif isinstance(raw, (list, tuple)) and len(raw) == 3:
                    kw[field_name] = tuple(int(c) for c in raw)
        return cls(**kw)


DARK_COLORS = UIColorSet(
    bg=(16, 18, 24),
    panel=(24, 27, 35),
    panel_alt=(19, 22, 29),
    header=(33, 37, 48),
    border=(54, 60, 76),
    border_soft=(36, 41, 54),
    text=(232, 234, 240),
    text_dim=(158, 164, 178),
    text_muted=(118, 124, 140),
    accent=(82, 132, 250),
    accent_hover=(110, 155, 255),
    accent_active=(62, 108, 220),
    success=(74, 184, 124),
    danger=(224, 92, 96),
    danger_hover=(180, 70, 76),
    warning=(232, 184, 84),
    hover=(36, 41, 56),
    selected=(44, 66, 128),
    overlay=(0, 0, 0),
    shadow=(0, 0, 0),
    scrollbar_thumb=(78, 86, 104),
    scrollbar_thumb_hover=(100, 110, 130),
)
MOLOKAI_COLORS = UIColorSet(
    # Base - stepped elevation
    bg=(26, 29, 36),
    panel=(36, 39, 48),
    panel_alt=(30, 33, 41),
    header=(44, 47, 57),
    # Borders
    border=(62, 66, 78),
    border_soft=(46, 50, 62),
    # Text
    text=(235, 238, 242),
    text_dim=(170, 176, 185),
    text_muted=(125, 132, 142),
    # Accent - cleaner blue
    accent=(75, 145, 205),
    accent_hover=(95, 165, 220),
    accent_active=(55, 125, 185),
    # Semantic
    success=(80, 190, 125),
    danger=(220, 85, 90),
    danger_hover=(235, 105, 110),
    warning=(235, 175, 70),
    # Interaction
    hover=(50, 56, 68),
    selected=(48, 91, 145),
)

LIGHT_COLORS = UIColorSet(
    bg=(240, 240, 240),
    panel=(255, 255, 255),
    panel_alt=(245, 245, 245),
    header=(250, 250, 250),
    border=(200, 200, 200),
    border_soft=(220, 220, 220),
    text=(30, 30, 30),
    text_dim=(100, 100, 100),
    text_muted=(130, 130, 130),
    accent=(50, 100, 200),
    accent_hover=(70, 120, 220),
    accent_active=(40, 80, 180),
    success=(40, 160, 100),
    danger=(200, 60, 60),
    danger_hover=(220, 80, 80),
    warning=(200, 160, 60),
    hover=(230, 230, 230),
    selected=(80, 130, 200),
)

SEMI_LIGHT_COLORS = UIColorSet(
    bg=(52, 55, 61),
    panel=(64, 67, 73),
    panel_alt=(57, 60, 66),
    header=(72, 75, 81),
    border=(92, 94, 99),
    border_soft=(78, 80, 85),
    text=(228, 228, 228),
    text_dim=(150, 150, 150),
    text_muted=(118, 118, 118),
    accent=(90, 130, 210),
    accent_hover=(110, 150, 230),
    accent_active=(80, 120, 200),
    success=(90, 170, 120),
    danger=(210, 90, 90),
    danger_hover=(190, 80, 80),
    warning=(230, 180, 90),
    hover=(80, 84, 90),
    selected=(60, 100, 160),
)

MONOKAI_COLORS = UIColorSet(
    bg=(39, 40, 34),
    panel=(45, 46, 39),
    panel_alt=(34, 35, 30),
    header=(50, 51, 43),
    border=(94, 92, 78),
    border_soft=(74, 75, 66),
    text=(248, 248, 242),
    text_dim=(166, 162, 145),
    text_muted=(136, 132, 111),
    text_on_accent=(28, 27, 22),
    accent=(253, 151, 31),
    accent_hover=(255, 173, 76),
    accent_active=(204, 122, 20),
    success=(166, 226, 46),
    danger=(249, 38, 114),
    danger_hover=(196, 30, 91),
    warning=(230, 219, 116),
    hover=(62, 63, 53),
    selected=(73, 72, 62),
    text_on_selected=(248, 248, 242),
)

MIDNIGHT_COLORS = UIColorSet(
    # Deep-navy modern dark: strong elevation steps, teal accent
    bg=(10, 13, 22),
    panel=(17, 21, 33),
    panel_alt=(13, 16, 26),
    header=(25, 30, 46),
    border=(48, 56, 82),
    border_soft=(32, 38, 58),
    text=(231, 236, 245),
    text_dim=(152, 162, 184),
    text_muted=(112, 121, 144),
    text_on_accent=(255, 255, 255),
    accent=(45, 190, 205),
    accent_hover=(80, 210, 222),
    accent_active=(32, 158, 172),
    success=(70, 200, 150),
    danger=(235, 95, 110),
    danger_hover=(195, 75, 90),
    warning=(240, 190, 90),
    hover=(28, 34, 52),
    selected=(26, 84, 102),
    text_on_selected=(235, 248, 250),
    scrollbar_thumb=(64, 74, 102),
    scrollbar_thumb_hover=(86, 98, 128),
)

NORD_COLORS = UIColorSet(
    # Frosted nord dark: cool slate surfaces, icy blue accent
    bg=(32, 36, 47),
    panel=(43, 48, 62),
    panel_alt=(37, 42, 54),
    header=(52, 57, 73),
    border=(70, 78, 98),
    border_soft=(54, 61, 78),
    text=(229, 233, 240),
    text_dim=(160, 171, 189),
    text_muted=(122, 132, 152),
    text_on_accent=(30, 34, 44),
    accent=(136, 192, 208),
    accent_hover=(158, 206, 220),
    accent_active=(110, 168, 186),
    success=(163, 190, 140),
    danger=(191, 97, 106),
    danger_hover=(210, 120, 128),
    warning=(235, 203, 139),
    hover=(55, 62, 79),
    selected=(67, 76, 94),
    text_on_selected=(236, 239, 244),
    scrollbar_thumb=(88, 98, 120),
    scrollbar_thumb_hover=(110, 121, 144),
)


THEMES: dict[str, UIColorSet] = {
    "dark": DARK_COLORS,
    "molokai": MOLOKAI_COLORS,
    "light": LIGHT_COLORS,
    "semi_light": SEMI_LIGHT_COLORS,
    "monokai": MONOKAI_COLORS,
    "midnight": MIDNIGHT_COLORS,
    "nord": NORD_COLORS,
}


class ThemeManager:
    def __init__(self, theme_name: str = "dark"):
        self._theme_name = theme_name
        self._colors = THEMES.get(theme_name, DARK_COLORS)
        self._custom_themes: dict[str, UIColorSet] = {}
        self._listeners: list = []

    @property
    def name(self) -> str:
        return self._theme_name

    @property
    def colors(self) -> UIColorSet:
        return self._colors

    @property
    def bg(self) -> Color:
        return self._colors.bg

    @property
    def panel(self) -> Color:
        return self._colors.panel

    @property
    def panel_alt(self) -> Color:
        return self._colors.panel_alt

    @property
    def header(self) -> Color:
        return self._colors.header

    @property
    def border(self) -> Color:
        return self._colors.border

    @property
    def border_soft(self) -> Color:
        return self._colors.border_soft

    @property
    def text(self) -> Color:
        return self._colors.text

    @property
    def text_dim(self) -> Color:
        return self._colors.text_dim

    @property
    def text_muted(self) -> Color:
        return self._colors.text_muted

    @property
    def text_on_accent(self) -> Color:
        return self._colors.text_on_accent

    @property
    def text_on_selected(self) -> Color:
        return self._colors.text_on_selected

    @property
    def accent(self) -> Color:
        return self._colors.accent

    @property
    def accent_hover(self) -> Color:
        return self._colors.accent_hover

    @property
    def accent_active(self) -> Color:
        return self._colors.accent_active

    @property
    def success(self) -> Color:
        return self._colors.success

    @property
    def danger(self) -> Color:
        return self._colors.danger

    @property
    def danger_hover(self) -> Color:
        return self._colors.danger_hover

    @property
    def warning(self) -> Color:
        return self._colors.warning

    @property
    def hover(self) -> Color:
        return self._colors.hover

    @property
    def selected(self) -> Color:
        return self._colors.selected

    @property
    def marker_colors(self) -> tuple[Color, ...]:
        return self._colors.marker_colors

    @property
    def overlay(self) -> Color:
        return self._colors.overlay

    @property
    def shadow(self) -> Color:
        return self._colors.shadow

    @property
    def scrollbar_thumb(self) -> Color:
        return self._colors.scrollbar_thumb

    @property
    def scrollbar_thumb_hover(self) -> Color:
        return self._colors.scrollbar_thumb_hover

    def __getattr__(self, name: str):
        # future-proof: any new UIColorSet field auto-exposes
        if name in UIColorSet.__dataclass_fields__:
            return getattr(self._colors, name)
        raise AttributeError(f"'ThemeManager' object has no attribute '{name}'")

    def resolve_theme(self, name_or_path: str) -> UIColorSet | None:
        """Try built-in themes, then registered custom themes, then JSON file in THEME_PATH."""
        if name_or_path in THEMES:
            return THEMES[name_or_path]
        if name_or_path in self._custom_themes:
            return self._custom_themes[name_or_path]
        p = Path(name_or_path)
        if p.suffix.lower() == ".json":
            try:
                p = p.expanduser().resolve()
                if not str(p).startswith(str(THEME_PATH.resolve())):
                    return None
                if not p.exists():
                    return None
                with open(p) as f:
                    raw = json.load(f)
                colors_raw = raw.get("colors", raw)
                return UIColorSet.from_dict(colors_raw)
            except Exception:
                return None
        return None

    def set_theme(self, theme_name: str) -> bool:
        colors = self.resolve_theme(theme_name)
        if colors is None:
            return False
        self._theme_name = theme_name
        self._colors = colors
        for listener in self._listeners:
            listener(theme_name)
        return True

    def register_custom_theme(self, name: str, colors: UIColorSet) -> None:
        self._custom_themes[name] = colors

    def add_listener(self, callback) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)


_theme_manager = ThemeManager("dark")


def get_theme_manager() -> ThemeManager:
    return _theme_manager


def set_theme(theme_name: str) -> bool:
    return _theme_manager.set_theme(theme_name)


def get_current_theme_name() -> str:
    return _theme_manager.name


@dataclass(frozen=True)
class UIShape:
    radius: int = 8
    radius_sm: int = 6
    radius_lg: int = 12
    border: int = 1
    border_strong: int = 2
    shadow_offset: int = 4
    shadow_blur: int = 12


@dataclass(frozen=True)
class UIFontConfig:
    """Font configuration with family, sizes, and default weights."""

    family: str = "noto"
    size_sm: int = 12
    size_md: int = 13
    size_lg: int = 16
    size_title: int = 18
    mono_family: str = "jetbrainsmono"
    sans_family: str = "noto"


class UIFonts:
    """Font manager wrapper for theme system."""

    def __init__(self, config: UIFontConfig | None = None):
        self.config = config or UIFontConfig()
        font_manager.set_default_family(self.config.family)

    @property
    def name(self) -> str:
        return self.config.family

    @property
    def size_sm(self) -> int:
        return self.config.size_sm

    @property
    def size_md(self) -> int:
        return self.config.size_md

    @property
    def size_lg(self) -> int:
        return self.config.size_lg

    @property
    def size_title(self) -> int:
        return self.config.size_title

    def get_font(
        self,
        size: int | None = None,
        weight: FontWeight = FontWeight.REGULAR,
        style: FontStyle = FontStyle.NORMAL,
        family: str | None = None,
    ) -> pygame.font.Font:
        """Get font with specified properties."""
        if family is None:
            family = self.config.family
        if size is None:
            size = self.config.size_md

        return font_manager.get_font(family, size, weight, style)

    def get_mono_font(
        self,
        size: int | None = None,
        weight: FontWeight = FontWeight.REGULAR,
        style: FontStyle = FontStyle.NORMAL,
    ) -> pygame.font.Font:
        """Get monospace font."""
        if size is None:
            size = self.config.size_md
        return font_manager.get_font(self.config.mono_family, size, weight, style)

    def get_sans_font(
        self,
        size: int | None = None,
        weight: FontWeight = FontWeight.REGULAR,
        style: FontStyle = FontStyle.NORMAL,
    ) -> pygame.font.Font:
        """Get sans-serif font."""
        if size is None:
            size = self.config.size_md
        return font_manager.get_font(self.config.sans_family, size, weight, style)

    def get_small_font(
        self,
        weight: FontWeight = FontWeight.REGULAR,
        style: FontStyle = FontStyle.NORMAL,
    ) -> pygame.font.Font:
        """Get small font."""
        return self.get_font(self.config.size_sm, weight, style)

    def get_medium_font(
        self,
        weight: FontWeight = FontWeight.REGULAR,
        style: FontStyle = FontStyle.NORMAL,
    ) -> pygame.font.Font:
        """Get medium font."""
        return self.get_font(self.config.size_md, weight, style)

    def get_large_font(
        self,
        weight: FontWeight = FontWeight.REGULAR,
        style: FontStyle = FontStyle.NORMAL,
    ) -> pygame.font.Font:
        """Get large font."""
        return self.get_font(self.config.size_lg, weight, style)

    def get_title_font(
        self, weight: FontWeight = FontWeight.BOLD, style: FontStyle = FontStyle.NORMAL
    ) -> pygame.font.Font:
        """Get title font."""
        return self.get_font(self.config.size_title, weight, style)

    def get_bold_font(self, size: int | None = None) -> pygame.font.Font:
        """Get bold font."""
        return self.get_font(size, FontWeight.BOLD)

    def get_italic_font(self, size: int | None = None) -> pygame.font.Font:
        """Get italic font."""
        return self.get_font(size, FontWeight.REGULAR, FontStyle.ITALIC)

    def get_bold_italic_font(self, size: int | None = None) -> pygame.font.Font:
        """Get bold italic font."""
        return self.get_font(size, FontWeight.BOLD, FontStyle.ITALIC)


class _DynamicColors:
    """Dynamic color proxy that forwards to the theme manager."""

    def __getattr__(self, name: str):
        return getattr(_theme_manager, name)


COLORS = _DynamicColors()
SHAPE = UIShape()
FONTS = UIFonts()
SPACING = {
    "xs": 2,
    "sm": 4,
    "md": 8,
    "lg": 12,
    "xl": 16,
    "xxl": 24,
    "xxxl": 32,
}
