"""
Icon Manager - Native SVG Support via pygame-ce
Uses pygame's built-in SVG loading (pygame-ce 2.2.0+)
"""

import pygame
from pathlib import Path
import sys
from typing import Dict, Optional, Tuple


class IconManager:
    """Manages loading and rendering of SVG icons using pygame's native support."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._icons_path = self._resolve_icons_path()
            self._surface_cache: Dict[
                Tuple[str, int, Tuple[int, int, int]], pygame.Surface
            ] = {}
            self._available_icons = self._scan_icons()
            IconManager._initialized = True

    def _resolve_icons_path(self) -> Path:
        """Find bundled icons in package data or fallback locations."""

        try:
            from importlib.resources import files

            pkg_path = files("tilemap_editor.assets") / "icons"

            if hasattr(pkg_path, "__fspath__"):
                path = Path(pkg_path)
            else:
                path = Path(str(pkg_path))

            if path.exists() and any(path.glob("*.svg")):
                return path
        except (ImportError, AttributeError, TypeError):
            pass

        try:
            import tilemap_editor.assets

            pkg_assets_path = Path(tilemap_editor.assets.__file__).parent / "icons"
            if pkg_assets_path.exists() and any(pkg_assets_path.glob("*.svg")):
                return pkg_assets_path
        except (ImportError, AttributeError):
            pass

        for prefix in [sys.prefix, sys.base_prefix]:
            data_files_path = (
                Path(prefix) / "share" / "tilemap_editor" / "assets" / "icons"
            )
            if data_files_path.exists() and any(data_files_path.glob("*.svg")):
                return data_files_path

        dev_path = Path(__file__).parent.parent.parent / "assets" / "icons"
        if dev_path.exists():
            return dev_path

        try:
            import tilemap_editor.assets

            return Path(tilemap_editor.assets.__file__).parent / "icons"
        except ImportError:
            return Path(__file__).parent.parent.parent / "assets" / "icons"

    def _scan_icons(self) -> set:
        """Scan available icon files."""
        icons = set()
        if self._icons_path.exists():
            for f in self._icons_path.glob("*.svg"):
                icons.add(f.stem)
        return icons

    def list_icons(self) -> list:
        """Return list of available icon names."""
        return sorted(self._available_icons)

    def has_icon(self, name: str) -> bool:
        """Check if an icon exists."""
        return name in self._available_icons

    def _draw_fallback_icon(
        self, name: str, size: int, color: Tuple[int, int, int]
    ) -> pygame.Surface:
        """Draw a simple fallback icon using pygame primitives."""
        surface = pygame.Surface((size, size), pygame.SRCALPHA)
        padding = max(2, size // 8)

        if name == "plus":
            thickness = max(2, size // 8)
            cx, cy = size // 2, size // 2
            pygame.draw.line(
                surface, color, (cx, padding), (cx, size - padding), thickness
            )
            pygame.draw.line(
                surface, color, (padding, cy), (size - padding, cy), thickness
            )

        elif name in ("close", "x"):
            thickness = max(2, size // 8)
            pygame.draw.line(
                surface,
                color,
                (padding, padding),
                (size - padding, size - padding),
                thickness,
            )
            pygame.draw.line(
                surface,
                color,
                (size - padding, padding),
                (padding, size - padding),
                thickness,
            )

        elif name == "pencil":
            thickness = max(2, size // 10)
            pygame.draw.line(
                surface,
                color,
                (size // 4, size // 2),
                (size * 3 // 4, size // 4),
                thickness,
            )
            pygame.draw.polygon(
                surface,
                color,
                [
                    (size // 4, size // 2),
                    (size // 4 - thickness, size // 2 + thickness),
                    (size // 4 + thickness, size // 2 + thickness),
                ],
            )

        elif name == "play":
            pygame.draw.polygon(
                surface,
                color,
                [
                    (padding, padding),
                    (padding, size - padding),
                    (size - padding, size // 2),
                ],
            )

        elif name == "pause":
            bar_width = size // 4
            gap = size // 8
            pygame.draw.rect(
                surface,
                color,
                (padding, padding, bar_width, size - 2 * padding),
                border_radius=1,
            )
            pygame.draw.rect(
                surface,
                color,
                (padding + bar_width + gap, padding, bar_width, size - 2 * padding),
                border_radius=1,
            )

        elif name == "stop":
            pygame.draw.rect(
                surface,
                color,
                (padding, padding, size - 2 * padding, size - 2 * padding),
                border_radius=2,
            )

        elif name == "arrow-down":
            thickness = max(2, size // 8)
            pygame.draw.line(
                surface,
                color,
                (padding, size // 3),
                (size // 2, size * 2 // 3),
                thickness,
            )
            pygame.draw.line(
                surface,
                color,
                (size // 2, size * 2 // 3),
                (size - padding, size // 3),
                thickness,
            )

        elif name == "warning":
            pygame.draw.polygon(
                surface,
                color,
                [
                    (size // 2, padding),
                    (size - padding, size - padding),
                    (padding, size - padding),
                ],
            )
            dot_y = size * 3 // 5
            pygame.draw.circle(surface, (255, 255, 255), (size // 2, dot_y), size // 12)
            pygame.draw.rect(
                surface,
                (255, 255, 255),
                (size // 2 - size // 20, padding + size // 8, size // 10, size // 4),
            )

        elif name == "check":
            thickness = max(2, size // 8)
            pygame.draw.line(
                surface,
                color,
                (padding, size // 2),
                (size // 3, size - padding),
                thickness,
            )
            pygame.draw.line(
                surface,
                color,
                (size // 3, size - padding),
                (size - padding, padding),
                thickness,
            )

        elif name == "info":
            thickness = max(2, size // 16)
            pygame.draw.circle(
                surface, color, (size // 2, size // 2), size // 2 - padding, thickness
            )
            pygame.draw.circle(surface, color, (size // 2, size // 3), size // 12)
            pygame.draw.rect(
                surface,
                color,
                (size // 2 - size // 16, size // 2, size // 8, size // 4),
            )

        elif name == "duplicate":
            rect_w = size // 2 - 2
            pygame.draw.rect(
                surface, color, (padding, padding + 4, rect_w, rect_w), border_radius=2
            )
            pygame.draw.rect(
                surface, color, (padding + 6, padding, rect_w, rect_w), border_radius=2
            )

        elif name == "zoomin":
            thickness = max(2, size // 8)
            cx, cy = size // 2 - 2, size // 2 - 2

            pygame.draw.circle(surface, color, (cx, cy), size // 3, thickness)

            pygame.draw.line(
                surface,
                color,
                (cx, cy - size // 6),
                (cx, cy + size // 6),
                thickness - 1,
            )
            pygame.draw.line(
                surface,
                color,
                (cx - size // 6, cy),
                (cx + size // 6, cy),
                thickness - 1,
            )

            pygame.draw.line(
                surface,
                color,
                (cx + size // 4, cy + size // 4),
                (size - padding, size - padding),
                thickness + 1,
            )

        elif name == "zoomout":
            thickness = max(2, size // 8)
            cx, cy = size // 2 - 2, size // 2 - 2

            pygame.draw.circle(surface, color, (cx, cy), size // 3, thickness)

            pygame.draw.line(
                surface,
                color,
                (cx - size // 6, cy),
                (cx + size // 6, cy),
                thickness - 1,
            )

            pygame.draw.line(
                surface,
                color,
                (cx + size // 4, cy + size // 4),
                (size - padding, size - padding),
                thickness + 1,
            )

        elif name == "reset":
            thickness = max(2, size // 8)
            cx, cy = size // 2, size // 2
            radius = size // 3

            import math

            points = []
            for angle in range(45, 315, 10):
                rad = math.radians(angle)
                px = cx + int(radius * math.cos(rad))
                py = cy + int(radius * math.sin(rad))
                points.append((px, py))
            if len(points) > 1:
                pygame.draw.lines(surface, color, False, points, thickness)

            arrow_angle = math.radians(45)
            head_x = cx + int(radius * math.cos(arrow_angle))
            head_y = cy + int(radius * math.sin(arrow_angle))
            pygame.draw.polygon(
                surface,
                color,
                [
                    (head_x, head_y),
                    (head_x - 5, head_y - 3),
                    (head_x - 3, head_y + 5),
                ],
            )

        elif name == "fit":
            thickness = max(2, size // 8)

            pygame.draw.line(
                surface, color, (padding, padding + 6), (padding, padding), thickness
            )
            pygame.draw.line(
                surface, color, (padding, padding), (padding + 6, padding), thickness
            )

            pygame.draw.line(
                surface,
                color,
                (size - padding, padding + 6),
                (size - padding, padding),
                thickness,
            )
            pygame.draw.line(
                surface,
                color,
                (size - padding, padding),
                (size - padding - 6, padding),
                thickness,
            )

            pygame.draw.line(
                surface,
                color,
                (padding, size - padding - 6),
                (padding, size - padding),
                thickness,
            )
            pygame.draw.line(
                surface,
                color,
                (padding, size - padding),
                (padding + 6, size - padding),
                thickness,
            )

            pygame.draw.line(
                surface,
                color,
                (size - padding, size - padding - 6),
                (size - padding, size - padding),
                thickness,
            )
            pygame.draw.line(
                surface,
                color,
                (size - padding, size - padding),
                (size - padding - 6, size - padding),
                thickness,
            )

        elif name == "select":
            thickness = max(2, size // 8)
            p = padding
            r = size - padding
            pygame.draw.rect(surface, color, (p + 2, p + 2, r - p - 6, r - p - 6), thickness)
            pygame.draw.line(surface, color, (r - 6, r - 6), (r, r), thickness + 1)

        elif name == "eraser":
            thickness = max(2, size // 8)
            p = padding
            r = size - padding
            pygame.draw.rect(surface, color, (p, r // 2, r - p, r // 2 - p + 2))
            pygame.draw.polygon(
                surface, color,
                [(r - p - 4, p + 2), (r - p, p + 2), (p + 4, r // 2), (p, r // 2)],
            )

        elif name == "auto":
            thickness = max(2, size // 10)
            cx, cy = size // 2, size // 2
            pygame.draw.circle(surface, color, (cx, cy), size // 4, thickness)
            pygame.draw.line(surface, color, (cx, cy), (cx, padding), thickness)
            pygame.draw.line(surface, color, (cx, cy), (size - padding, cy), thickness)
            pygame.draw.line(surface, color, (cx, cy), (cx, size - padding), thickness)

        elif name == "nodes":
            thickness = max(2, size // 10)
            r = size // 8
            positions = [(size // 2, size // 4), (size // 4, size * 3 // 4), (size * 3 // 4, size * 3 // 4)]
            for px, py in positions:
                pygame.draw.circle(surface, color, (px, py), r)
            for i in range(len(positions)):
                for j in range(i + 1, len(positions)):
                    pygame.draw.line(surface, color, positions[i], positions[j], 1)

        elif name == "pan":
            thickness = max(2, size // 8)
            cx, cy = size // 2, size // 2

            pygame.draw.line(
                surface, color, (cx, padding + 4), (cx, size - padding - 4), thickness
            )
            pygame.draw.polygon(
                surface,
                color,
                [(cx, padding), (cx - 4, padding + 5), (cx + 4, padding + 5)],
            )
            pygame.draw.polygon(
                surface,
                color,
                [
                    (cx, size - padding),
                    (cx - 4, size - padding - 5),
                    (cx + 4, size - padding - 5),
                ],
            )

            pygame.draw.line(
                surface, color, (padding + 4, cy), (size - padding - 4, cy), thickness
            )
            pygame.draw.polygon(
                surface,
                color,
                [(padding, cy), (padding + 5, cy - 4), (padding + 5, cy + 4)],
            )
            pygame.draw.polygon(
                surface,
                color,
                [
                    (size - padding, cy),
                    (size - padding - 5, cy - 4),
                    (size - padding - 5, cy + 4),
                ],
            )

        elif name == "save":
            pygame.draw.rect(
                surface,
                color,
                (padding, padding, size - 2 * padding, size - 2 * padding),
                border_radius=2,
            )

            pygame.draw.rect(
                surface,
                color,
                (padding + 4, padding + 8, size - 2 * padding - 8, size // 2),
                border_radius=1,
            )

        elif name == "load" or name == "folder":
            pygame.draw.rect(
                surface,
                color,
                (padding, padding + 4, size - 2 * padding, size - 2 * padding - 4),
                border_radius=2,
            )
            pygame.draw.rect(
                surface, color, (padding, padding, size // 2, 6), border_radius=1
            )

        else:
            pygame.draw.rect(
                surface,
                color,
                (padding, padding, size - 2 * padding, size - 2 * padding),
                2,
            )

        return surface

    def get_icon(
        self, name: str, size: int = 16, color: Optional[Tuple[int, int, int]] = None
    ) -> pygame.Surface:
        """
        Get an icon as a pygame surface.

        Args:
            name: Icon name (without .svg extension)
            size: Desired size in pixels
            color: Optional color to tint the icon (R, G, B)

        Returns:
            pygame.Surface with the rendered icon
        """
        svg_name = _ICON_ALIASES.get(name, name)
        cache_key = (name, size, color or (0, 0, 0))
        if cache_key in self._surface_cache:
            return self._surface_cache[cache_key]

        surface = None

        if self.has_icon(svg_name):
            svg_path = self._icons_path / f"{svg_name}.svg"
            try:
                if hasattr(pygame.image, "load_sized_svg"):
                    surface = pygame.image.load_sized_svg(str(svg_path), (size, size))
                else:
                    surface = pygame.image.load(str(svg_path)).convert_alpha()
                    if surface.get_size() != (size, size):
                        surface = pygame.transform.smoothscale(surface, (size, size))
            except Exception:
                pass

        if surface is None:
            fallback_color = color or (200, 200, 200)
            surface = self._draw_fallback_icon(svg_name, size, fallback_color)

        if color and surface:
            tinted = surface.copy()
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((*color, 255))
            tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            surface = tinted

        self._surface_cache[cache_key] = surface
        return surface

    def clear_cache(self):
        """Clear the icon cache."""
        self._surface_cache.clear()


icon_manager = IconManager()


def get_icon(
    name: str, size: int = 16, color: Optional[Tuple[int, int, int]] = None
) -> pygame.Surface:
    """Convenience function to get an icon."""
    return icon_manager.get_icon(name, size, color)


_ICON_ALIASES = {
    "zoom_in": "zoomin",
    "zoom_out": "zoomout",
}


def has_icon(name: str) -> bool:
    """Check if an icon exists (either as SVG or fallback)."""
    resolved = _ICON_ALIASES.get(name, name)
    return icon_manager.has_icon(resolved) or resolved in [
        "plus",
        "close",
        "x",
        "pencil",
        "play",
        "pause",
        "stop",
        "arrow-down",
        "warning",
        "check",
        "info",
        "duplicate",
        "save",
        "load",
        "folder",
        "zoomin",
        "zoomout",
        "reset",
        "fit",
        "pan",
        "radio",
        "select",
        "eraser",
        "auto",
        "nodes",
    ]
