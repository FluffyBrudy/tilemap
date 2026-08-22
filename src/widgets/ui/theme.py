import json
from dataclasses import dataclass
from pathlib import Path

import pygame

from constants import THEME_PATH
from utils.font_manager import FontStyle, FontWeight, font_manager

Color = tuple[int, int, int]


@dataclass(frozen=True)
class UIColorSet:
    bg: Color = (35, 38, 44)
    panel: Color = (30, 32, 36)
    panel_alt: Color = (25, 27, 30)
    header: Color = (40, 42, 46)
    border: Color = (60, 62, 65)
    border_soft: Color = (50, 54, 59)
    text: Color = (230, 230, 230)
    text_dim: Color = (150, 150, 150)
    text_muted: Color = (120, 120, 120)
    text_on_accent: Color = (255, 255, 255)
    text_on_selected: Color = (255, 255, 255)
    accent: Color = (80, 120, 200)
    accent_hover: Color = (100, 140, 220)
    accent_active: Color = (70, 110, 190)
    success: Color = (80, 180, 120)
    danger: Color = (200, 80, 80)
    danger_hover: Color = (160, 60, 60)
    warning: Color = (220, 180, 80)
    hover: Color = (55, 60, 70)
    selected: Color = (50, 70, 110)
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
    bg=(35, 38, 44),
    panel=(30, 32, 36),
    panel_alt=(25, 27, 30),
    header=(40, 42, 46),
    border=(60, 62, 65),
    border_soft=(50, 54, 59),
    text=(230, 230, 230),
    text_dim=(150, 150, 150),
    text_muted=(120, 120, 120),
    accent=(80, 120, 200),
    accent_hover=(100, 140, 220),
    accent_active=(70, 110, 190),
    success=(80, 180, 120),
    danger=(200, 80, 80),
    danger_hover=(160, 60, 60),
    warning=(220, 180, 80),
    hover=(55, 60, 70),
    selected=(50, 70, 110),
)
MOLOKAI_COLORS = UIColorSet(
    # Base
    bg=(32, 35, 42),
    panel=(40, 43, 51),
    panel_alt=(35, 38, 46),
    header=(46, 49, 58),
    # Borders
    border=(68, 72, 82),
    border_soft=(56, 60, 70),
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
    hover=(58, 64, 75),
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
    bg=(60, 63, 68),
    panel=(55, 58, 63),
    panel_alt=(50, 52, 57),
    header=(65, 68, 73),
    border=(80, 82, 87),
    border_soft=(70, 72, 77),
    text=(220, 220, 220),
    text_dim=(140, 140, 140),
    text_muted=(110, 110, 110),
    accent=(90, 130, 210),
    accent_hover=(110, 150, 230),
    accent_active=(80, 120, 200),
    success=(90, 170, 120),
    danger=(210, 90, 90),
    danger_hover=(190, 80, 80),
    warning=(230, 180, 90),
    hover=(75, 80, 85),
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


THEMES: dict[str, UIColorSet] = {
    "dark": DARK_COLORS,
    "molokai": MOLOKAI_COLORS,
    "light": LIGHT_COLORS,
    "semi_light": SEMI_LIGHT_COLORS,
    "monokai": MONOKAI_COLORS,
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
    radius: int = 5
    radius_sm: int = 3
    border: int = 1


@dataclass(frozen=True)
class UIFontConfig:
    """Font configuration with family, sizes, and default weights."""

    family: str = "Arial"
    size_sm: int = 11
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
