"""
Centralized Font Manager - Singleton Pattern
Provides efficient font loading and management with customizable weight variants.
"""

import logging
import os
from enum import Enum
from pathlib import Path

import pygame

logger = logging.getLogger(__name__)


class FontWeight(Enum):
    """Font weight variants."""

    THIN = "thin"
    EXTRA_LIGHT = "extralight"
    LIGHT = "light"
    REGULAR = "regular"
    MEDIUM = "medium"
    SEMI_BOLD = "semibold"
    BOLD = "bold"
    EXTRA_BOLD = "extrabold"
    BLACK = "black"


class FontStyle(Enum):
    """Font style variants."""

    NORMAL = "normal"
    ITALIC = "italic"


class FontManager:
    """Singleton font manager for centralized font loading."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._fonts: dict[str, pygame.font.Font] = {}
            self._font_families: dict[str, dict[str, str]] = {}
            self._default_family = "Arial"
            self._assets_path = Path(__file__).parent.parent.parent / "assets" / "fonts"
            logger.info(f"Font Manager initializing - Assets path: {self._assets_path}")
            self._load_font_families()
            logger.info(
                f"Font Manager initialized with {len(self._font_families)} font families"
            )
            FontManager._initialized = True

    def _load_font_families(self):
        """Load available font families from assets directory."""
        if not self._assets_path.exists():
            logger.warning(f"Font assets directory not found: {self._assets_path}")
            return

        logger.info(f"Loading font families from: {self._assets_path}")
        for family_dir in self._assets_path.iterdir():
            if family_dir.is_dir():
                family_name = family_dir.name.lower()
                self._font_families[family_name] = {}

                font_count = 0
                for font_file in family_dir.glob("*.ttf"):
                    weight, style = self._parse_font_filename(font_file.stem)
                    key = f"{weight.value}_{style.value}"
                    self._font_families[family_name][key] = str(font_file)
                    font_count += 1
                    logger.debug(
                        f"Loaded font: {family_name}/{font_file.name} -> {key}"
                    )

                logger.info(
                    f"Font family '{family_name}': {font_count} variants loaded"
                )

    def _parse_font_filename(self, filename: str) -> tuple[FontWeight, FontStyle]:
        """Parse font filename to extract weight and style."""
        filename_lower = filename.lower()

        style = FontStyle.NORMAL
        if "italic" in filename_lower:
            style = FontStyle.ITALIC

        weight = FontWeight.REGULAR
        for weight_enum in FontWeight:
            if weight_enum.value in filename_lower:
                weight = weight_enum
                break

        return weight, style

    def get_font(
        self,
        family: str | None = None,
        size: int = 12,
        weight: FontWeight = FontWeight.REGULAR,
        style: FontStyle = FontStyle.NORMAL,
        bold: bool | None = None,
        italic: bool | None = None,
    ) -> pygame.font.Font:
        """
        Get a font with specified properties.

        Args:
            family: Font family name (e.g., 'jetbrainsmono', 'noto')
            size: Font size
            weight: Font weight
            style: Font style
            bold: Override for bold (deprecated, use weight)
            italic: Override for italic (deprecated, use style)

        Returns:
            pygame.font.Font object
        """

        if bold is not None:
            weight = FontWeight.BOLD if bold else FontWeight.REGULAR
        if italic is not None:
            style = FontStyle.ITALIC if italic else FontStyle.NORMAL

        if family is None:
            family = self._default_family

        cache_key = f"{family}_{size}_{weight.value}_{style.value}"

        logger.debug(f"Font request: {family} {size} {weight.value} {style.value}")

        if cache_key in self._fonts:
            logger.debug(f"Font cache hit: {cache_key}")
            return self._fonts[cache_key]

        logger.debug(f"Attempting to load system font first: {family}")
        font = self._load_system_font(family, size, weight, style)

        if font is None:
            logger.debug(f"System font failed, trying custom font: {family}")
            font = self._load_custom_font(family, size, weight, style)

        if font:
            self._fonts[cache_key] = font
            logger.info(f"Font loaded successfully: {cache_key}")
            return font
        logger.warning(f"Failed to load font: {cache_key}, using fallback")

        return pygame.font.Font(None, size)

    def _load_custom_font(
        self, family: str, size: int, weight: FontWeight, style: FontStyle
    ) -> pygame.font.Font | None:
        """Load custom font from assets directory."""
        family_lower = family.lower()

        if family_lower not in self._font_families:
            logger.debug(f"Font family not found in assets: {family}")
            return None

        font_key = f"{weight.value}_{style.value}"
        font_path = self._font_families[family_lower].get(font_key)

        if not font_path and weight in [
            FontWeight.BOLD,
            FontWeight.SEMI_BOLD,
            FontWeight.MEDIUM,
        ]:
            font_key = f"bold_{style.value}"
            font_path = self._font_families[family_lower].get(font_key)

        if font_path and os.path.exists(font_path):
            try:
                font = pygame.font.Font(font_path, size)
                logger.info(
                    f"Loaded custom font: {font_path} -> {family_lower} {size} {weight.value} {style.value}"
                )
                return font
            except (pygame.error, OSError) as e:
                logger.error(f"Failed to load custom font {font_path}: {e}")
        else:
            logger.debug(
                f"Font variant not found: {family_lower} {font_key} (available: {list(self._font_families[family_lower].keys())})"
            )

        return None

    def _load_system_font(
        self, family: str, size: int, weight: FontWeight, style: FontStyle
    ) -> pygame.font.Font | None:
        """Load system font with fallback."""

        try:
            bold = weight in [
                FontWeight.SEMI_BOLD,
                FontWeight.BOLD,
                FontWeight.EXTRA_BOLD,
                FontWeight.BLACK,
            ]
            italic = style == FontStyle.ITALIC
            font = pygame.font.SysFont(family, size, bold=bold, italic=italic)
            logger.info(
                f"Loaded system font: {family} {size} bold={bold} italic={italic}"
            )
            return font
        except (pygame.error, OSError) as e:
            logger.debug(f"System font failed: {family} - {e}")

        family_variants = [family]
        if "mono" in family.lower():
            family_variants.extend(["consolas", "monaco", "courier new"])
        elif "sans" in family.lower():
            family_variants.extend(["arial", "helvetica", "liberation sans"])

        for variant in family_variants:
            try:
                bold = weight in [
                    FontWeight.SEMI_BOLD,
                    FontWeight.BOLD,
                    FontWeight.EXTRA_BOLD,
                    FontWeight.BLACK,
                ]
                italic = style == FontStyle.ITALIC
                font = pygame.font.SysFont(variant, size, bold=bold, italic=italic)
                logger.info(
                    f"Loaded system font variant: {variant} {size} bold={bold} italic={italic}"
                )
                return font
            except (pygame.error, OSError) as e:
                logger.debug(f"System font variant failed: {variant} - {e}")
                continue

        return None

    def set_default_family(self, family: str):
        """Set default font family."""
        self._default_family = family

    def get_available_families(self) -> list[str]:
        """Get list of available font families."""
        families = list(self._font_families.keys())
        families.extend(pygame.font.get_fonts())
        return list(set(families))

    def preload_font(
        self,
        family: str,
        size: int,
        weight: FontWeight = FontWeight.REGULAR,
        style: FontStyle = FontStyle.NORMAL,
    ):
        """Preload a font to cache it for later use."""
        self.get_font(family, size, weight, style)

    def clear_cache(self):
        """Clear font cache."""
        self._fonts.clear()

    def get_font_info(self, family: str) -> dict[str, str]:
        """Get information about available font variants for a family."""
        family_lower = family.lower()
        return self._font_families.get(family_lower, {})


font_manager = FontManager()


def get_font(
    family: str | None = None,
    size: int = 12,
    weight: FontWeight = FontWeight.REGULAR,
    style: FontStyle = FontStyle.NORMAL,
) -> pygame.font.Font:
    """Get font using global font manager."""
    return font_manager.get_font(family, size, weight, style)


def get_system_font(
    name: str | None = None,
    size: int = 12,
    bold: bool = False,
    italic: bool = False,
) -> pygame.font.Font:
    """Get system font (backward compatibility)."""
    weight = FontWeight.BOLD if bold else FontWeight.REGULAR
    style = FontStyle.ITALIC if italic else FontStyle.NORMAL
    return font_manager.get_font(name, size, weight, style)


def preload_common_fonts():
    """Preload commonly used fonts."""
    common_sizes = [11, 12, 13, 14, 16, 18]

    if "jetbrain-fonts" in font_manager._font_families:
        for size in common_sizes:
            font_manager.preload_font("jetbrainsmono", size, FontWeight.REGULAR)
            font_manager.preload_font("jetbrainsmono", size, FontWeight.BOLD)
            font_manager.preload_font(
                "jetbrainsmono", size, FontWeight.REGULAR, FontStyle.ITALIC
            )

    if "noto" in font_manager._font_families:
        for size in common_sizes:
            font_manager.preload_font("noto", size, FontWeight.REGULAR)
            font_manager.preload_font("noto", size, FontWeight.BOLD)

    for size in common_sizes:
        font_manager.preload_font("Arial", size, FontWeight.REGULAR)
        font_manager.preload_font("Arial", size, FontWeight.BOLD)
