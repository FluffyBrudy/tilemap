from dataclasses import dataclass
from typing import Tuple


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
class UIFonts:
    name: str = "Arial"
    size_sm: int = 11
    size_md: int = 13
    size_lg: int = 16
    size_title: int = 18


COLORS = UIColorSet()
SHAPE = UIShape()
FONTS = UIFonts()
