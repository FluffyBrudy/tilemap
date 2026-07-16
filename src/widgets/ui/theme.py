import json
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Optional, Dict
import pygame
from constants import THEME_PATH
from utils.font_manager import font_manager, FontWeight, FontStyle


Color = Tuple[int, int, int]


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
    accent: Color = (80, 120, 200)
    accent_hover: Color = (100, 140, 220)
    accent_active: Color = (70, 110, 190)
    success: Color = (80, 180, 120)
    danger: Color = (200, 80, 80)
    warning: Color = (220, 180, 80)
    hover: Color = (55, 60, 70)
    selected: Color = (50, 70, 110)

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "UIColorSet":
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
    warning=(220, 180, 80),
    hover=(55, 60, 70),
    selected=(50, 70, 110),
)

MOLOKAI_COLORS = UIColorSet(
    bg=(40, 42, 52),
    panel=(45, 47, 57),
    panel_alt=(35, 37, 45),
    header=(50, 52, 62),
    border=(70, 72, 82),
    border_soft=(60, 62, 72),
    text=(240, 240, 235),
    text_dim=(160, 160, 155),
    text_muted=(130, 130, 125),
    accent=(120, 160, 200),
    accent_hover=(140, 180, 220),
    accent_active=(100, 140, 180),
    success=(100, 200, 140),
    danger=(220, 100, 100),
    warning=(240, 200, 100),
    hover=(65, 70, 80),
    selected=(60, 90, 140),
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
    warning=(230, 180, 90),
    hover=(75, 80, 85),
    selected=(60, 100, 160),
)


THEMES: Dict[str, UIColorSet] = {
    "dark": DARK_COLORS,
    "molokai": MOLOKAI_COLORS,
    "light": LIGHT_COLORS,
    "semi_light": SEMI_LIGHT_COLORS,
}


class ThemeManager:
    def __init__(self, theme_name: str = "dark"):
        self._theme_name = theme_name
        self._colors = THEMES.get(theme_name, DARK_COLORS)
        self._custom_themes: Dict[str, UIColorSet] = {}
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
    def warning(self) -> Color:
        return self._colors.warning

    @property
    def hover(self) -> Color:
        return self._colors.hover

    @property
    def selected(self) -> Color:
        return self._colors.selected

    def resolve_theme(self, name_or_path: str) -> Optional[UIColorSet]:
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

    def __init__(self, config: Optional[UIFontConfig] = None):
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
        size: Optional[int] = None,
        weight: FontWeight = FontWeight.REGULAR,
        style: FontStyle = FontStyle.NORMAL,
        family: Optional[str] = None,
    ) -> pygame.font.Font:
        """Get font with specified properties."""
        if family is None:
            family = self.config.family
        if size is None:
            size = self.config.size_md

        return font_manager.get_font(family, size, weight, style)

    def get_mono_font(
        self,
        size: Optional[int] = None,
        weight: FontWeight = FontWeight.REGULAR,
        style: FontStyle = FontStyle.NORMAL,
    ) -> pygame.font.Font:
        """Get monospace font."""
        if size is None:
            size = self.config.size_md
        return font_manager.get_font(self.config.mono_family, size, weight, style)

    def get_sans_font(
        self,
        size: Optional[int] = None,
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

    def get_bold_font(self, size: Optional[int] = None) -> pygame.font.Font:
        """Get bold font."""
        return self.get_font(size, FontWeight.BOLD)

    def get_italic_font(self, size: Optional[int] = None) -> pygame.font.Font:
        """Get italic font."""
        return self.get_font(size, FontWeight.REGULAR, FontStyle.ITALIC)

    def get_bold_italic_font(self, size: Optional[int] = None) -> pygame.font.Font:
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
