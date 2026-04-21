"""
Icon rendering and caching system for pygame applications.

Provides rich, vector-style icons with disk caching to improve performance.
Icons are rendered once and cached as PNGs in .cache/icons/ directory.
"""

import pygame
import json
import hashlib
import time
from pathlib import Path
from typing import Dict, Tuple, Optional, Callable


SOURCE_VERSION = "1.0.0"


CACHE_DIR = Path(".cache/icons")
INDEX_FILE = CACHE_DIR / "index.json"
MAX_RECENTS = 50
RECENTS_COMPRESSION_WINDOW = 5


_pygame_initialized = False


def _ensure_pygame():
    """Ensure pygame is initialized (lazy initialization)."""
    global _pygame_initialized
    if not _pygame_initialized:
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()
        _pygame_initialized = True


def _ensure_cache_dir():
    """Ensure cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _compute_key(renderer_name: str, params: dict, size: Tuple[int, int]) -> str:
    """Generate stable cache key from parameters."""
    data = {
        "version": SOURCE_VERSION,
        "renderer": renderer_name,
        "params": params,
        "size": size,
    }

    json_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()


def _load_index() -> dict:
    """Load cache index from disk."""
    if not INDEX_FILE.exists():
        return {"version": SOURCE_VERSION, "entries": {}}

    try:
        with open(INDEX_FILE, "r") as f:
            index = json.load(f)

        if index.get("version") != SOURCE_VERSION:
            return {"version": SOURCE_VERSION, "entries": {}}

        return index
    except (json.JSONDecodeError, IOError):
        return {"version": SOURCE_VERSION, "entries": {}}


def _save_index(index: dict):
    """Save cache index to disk with atomic write."""
    _ensure_cache_dir()

    temp_file = INDEX_FILE.with_suffix(".tmp")
    try:
        with open(temp_file, "w") as f:
            json.dump(index, f, indent=2)
        temp_file.replace(INDEX_FILE)
    except IOError as e:
        print(f"Warning: Could not save icon cache index: {e}")
        if temp_file.exists():
            temp_file.unlink()


def _read_png_to_surface(path: Path) -> Optional[pygame.Surface]:
    """Load PNG from disk and convert to Surface."""
    try:
        surface = pygame.image.load(str(path))
        return surface.convert_alpha()
    except (pygame.error, IOError):
        return None


def _write_surface_to_png(surface: pygame.Surface, path: Path) -> bool:
    """Write Surface to PNG file."""
    try:
        _ensure_cache_dir()

        if surface.get_flags() & pygame.SRCALPHA == 0:
            surface = surface.convert_alpha()
        pygame.image.save(surface, str(path))
        return True
    except (pygame.error, IOError) as e:
        print(f"Warning: Could not write icon cache: {e}")
        return False


def _draw_rounded_rect(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: Tuple[int, int, int, int],
    radius: int,
):
    """Draw a rounded rectangle with anti-aliasing."""
    pygame.draw.rect(surface, color, rect, border_radius=radius)


def _draw_gradient_rect(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color_top: Tuple[int, int, int],
    color_bottom: Tuple[int, int, int],
):
    """Draw a vertical gradient rectangle."""
    for y in range(rect.height):
        ratio = y / rect.height
        r = int(color_top[0] * (1 - ratio) + color_bottom[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bottom[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bottom[2] * ratio)
        pygame.draw.line(
            surface, (r, g, b), (rect.x, rect.y + y), (rect.x + rect.width, rect.y + y)
        )


def render_folder_icon(
    size: Tuple[int, int] = (64, 64), color: Tuple[int, int, int] = (220, 180, 80)
) -> pygame.Surface:
    """Render a rich folder icon."""
    _ensure_pygame()

    surface = pygame.Surface(size, pygame.SRCALPHA)
    w, h = size

    scale = min(w, h) / 64

    tab_rect = pygame.Rect(int(w * 0.15), int(h * 0.25), int(w * 0.35), int(h * 0.15))
    _draw_rounded_rect(surface, tab_rect, (*color, 255), int(4 * scale))

    body_rect = pygame.Rect(int(w * 0.15), int(h * 0.35), int(w * 0.7), int(h * 0.5))
    color_light = tuple(min(c + 30, 255) for c in color)
    color_dark = tuple(max(c - 20, 0) for c in color)
    _draw_gradient_rect(surface, body_rect, color_light, color_dark)
    _draw_rounded_rect(surface, body_rect, (*color, 0), int(6 * scale))

    highlight_rect = pygame.Rect(int(w * 0.2), int(h * 0.4), int(w * 0.6), int(h * 0.1))
    pygame.draw.rect(
        surface, (*color_light, 100), highlight_rect, border_radius=int(3 * scale)
    )

    return surface


def render_file_icon(
    size: Tuple[int, int] = (64, 64), color: Tuple[int, int, int] = (180, 180, 180)
) -> pygame.Surface:
    """Render a rich file icon."""
    _ensure_pygame()

    surface = pygame.Surface(size, pygame.SRCALPHA)
    w, h = size

    scale = min(w, h) / 64

    body_rect = pygame.Rect(int(w * 0.2), int(h * 0.15), int(w * 0.6), int(h * 0.7))
    color_light = tuple(min(c + 20, 255) for c in color)
    _draw_gradient_rect(surface, body_rect, color_light, color)
    pygame.draw.rect(
        surface, (*color, 255), body_rect, int(2 * scale), border_radius=int(3 * scale)
    )

    corner_size = int(w * 0.15)
    corner_points = [
        (body_rect.right, body_rect.top),
        (body_rect.right, body_rect.top + corner_size),
        (body_rect.right - corner_size, body_rect.top),
    ]
    pygame.draw.polygon(surface, (200, 200, 200, 255), corner_points)
    pygame.draw.lines(surface, (*color, 255), False, corner_points, int(2 * scale))

    line_color = tuple(max(c - 40, 0) for c in color)
    for i in range(3):
        y = int(body_rect.top + body_rect.height * (0.35 + i * 0.15))
        pygame.draw.line(
            surface,
            (*line_color, 180),
            (body_rect.left + int(w * 0.1), y),
            (body_rect.right - int(w * 0.1), y),
            int(2 * scale),
        )

    return surface


def render_image_icon(
    size: Tuple[int, int] = (64, 64), color: Tuple[int, int, int] = (100, 180, 120)
) -> pygame.Surface:
    """Render a rich image file icon."""
    _ensure_pygame()

    surface = pygame.Surface(size, pygame.SRCALPHA)
    w, h = size

    scale = min(w, h) / 64

    frame_rect = pygame.Rect(int(w * 0.15), int(h * 0.15), int(w * 0.7), int(h * 0.7))
    pygame.draw.rect(surface, (*color, 255), frame_rect, border_radius=int(4 * scale))

    inner_rect = frame_rect.inflate(-int(8 * scale), -int(8 * scale))
    color_light = tuple(min(c + 40, 255) for c in color)
    _draw_gradient_rect(surface, inner_rect, color_light, color)

    mountain_color = tuple(max(c - 60, 0) for c in color)
    mountain_points = [
        (inner_rect.left, inner_rect.bottom),
        (inner_rect.left + int(inner_rect.width * 0.3), inner_rect.centery),
        (inner_rect.left + int(inner_rect.width * 0.5), inner_rect.bottom),
    ]
    pygame.draw.polygon(surface, (*mountain_color, 200), mountain_points)

    mountain_points2 = [
        (inner_rect.left + int(inner_rect.width * 0.4), inner_rect.bottom),
        (
            inner_rect.left + int(inner_rect.width * 0.7),
            inner_rect.centery + int(h * 0.05),
        ),
        (inner_rect.right, inner_rect.bottom),
    ]
    pygame.draw.polygon(surface, (*mountain_color, 200), mountain_points2)

    sun_center = (inner_rect.right - int(w * 0.12), inner_rect.top + int(h * 0.12))
    sun_radius = int(w * 0.08)
    pygame.draw.circle(surface, (255, 220, 100, 220), sun_center, sun_radius)

    return surface


_RENDERERS: Dict[str, Callable] = {
    "folder": render_folder_icon,
    "file": render_file_icon,
    "image": render_image_icon,
}


def get_icon(
    renderer_name: str, params: Optional[dict] = None, size: Tuple[int, int] = (64, 64)
) -> pygame.Surface:
    """
    Get icon Surface, using cache if available.

    Args:
        renderer_name: Name of the icon renderer ("folder", "file", "image")
        params: Optional parameters to pass to renderer (e.g., {"color": (255, 0, 0)})
        size: Icon size in pixels

    Returns:
        pygame.Surface with the rendered icon
    """
    _ensure_pygame()

    if params is None:
        params = {}

    if renderer_name not in _RENDERERS:

        surface = pygame.Surface(size, pygame.SRCALPHA)
        surface.fill((255, 0, 255, 128))
        return surface

    key = _compute_key(renderer_name, params, size)
    cache_path = CACHE_DIR / f"{key}.png"

    if cache_path.exists():
        index = _load_index()
        if key in index.get("entries", {}):
            surface = _read_png_to_surface(cache_path)
            if surface:

                index["entries"][key]["hits"] = index["entries"][key].get("hits", 0) + 1
                index["entries"][key]["last_access"] = time.time()
                _save_index(index)
                return surface

    renderer = _RENDERERS[renderer_name]
    surface = renderer(size=size, **params)

    if _write_surface_to_png(surface, cache_path):

        index = _load_index()
        index["entries"][key] = {
            "renderer": renderer_name,
            "params": params,
            "size": list(size),
            "filename": f"{key}.png",
            "created": time.time(),
            "last_access": time.time(),
            "hits": 1,
        }
        _save_index(index)

    return surface


def invalidate_cache(key: Optional[str] = None):
    """
    Invalidate cached icons.

    Args:
        key: Specific cache key to invalidate, or None to clear all
    """
    if key is None:

        if CACHE_DIR.exists():
            import shutil

            shutil.rmtree(CACHE_DIR)
        _ensure_cache_dir()
    else:

        cache_path = CACHE_DIR / f"{key}.png"
        if cache_path.exists():
            cache_path.unlink()

        index = _load_index()
        if key in index.get("entries", {}):
            del index["entries"][key]
            _save_index(index)


def purge_cache():
    """Completely remove cache directory and all cached icons."""
    invalidate_cache(None)


def prewarm_common_icons(sizes: list = [(32, 32), (64, 64)]):
    """
    Pre-render commonly used icons to warm up the cache.

    Args:
        sizes: List of icon sizes to pre-render
    """
    common_icons = [
        ("folder", {}),
        ("file", {}),
        ("image", {}),
    ]

    for renderer_name, params in common_icons:
        for size in sizes:
            get_icon(renderer_name, params, size)


if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Icon Cache Demo - Press R to rebuild cache")
    clock = pygame.time.Clock()

    test_icons = [
        ("folder", {}, (128, 128)),
        ("folder", {"color": (100, 150, 200)}, (128, 128)),
        ("file", {}, (128, 128)),
        ("file", {"color": (200, 100, 100)}, (128, 128)),
        ("image", {}, (128, 128)),
        ("image", {"color": (150, 100, 200)}, (128, 128)),
    ]

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    print("Rebuilding cache...")
                    purge_cache()
                elif event.key == pygame.K_ESCAPE:
                    running = False

        screen.fill((40, 40, 45))

        x, y = 50, 50
        for i, (name, params, size) in enumerate(test_icons):
            icon = get_icon(name, params, size)
            screen.blit(icon, (x, y))

            font = pygame.font.SysFont("Arial", 12)
            label = f"{name}"
            if params:
                label += f" {params}"
            text = font.render(label, True, (200, 200, 200))
            screen.blit(text, (x, y + size[1] + 5))

            x += size[0] + 30
            if x > 700:
                x = 50
                y += size[1] + 60

        font = pygame.font.SysFont("Arial", 14)
        text = font.render(
            "Press R to rebuild cache, ESC to quit", True, (150, 150, 150)
        )
        screen.blit(text, (10, screen.get_height() - 30))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
