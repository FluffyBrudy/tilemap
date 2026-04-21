from dataclasses import dataclass
from typing import Tuple, Optional
import pygame
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


COLORS = UIColorSet()
SHAPE = UIShape()
FONTS = UIFonts()
