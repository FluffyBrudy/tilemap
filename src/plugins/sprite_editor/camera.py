"""Pure camera math — world (document) <-> screen transforms.

No pygame imports: this module is fully usable and testable headlessly.
Holds viewport origin and scroll as plain floats; the viewport provides
the pygame-side rect/bilt machinery.
"""

from __future__ import annotations

MIN_ZOOM = 0.1
MAX_ZOOM = 16.0


def _clamp_zoom(value: float) -> float:
    return max(MIN_ZOOM, min(MAX_ZOOM, value))


class Camera:
    """One monotonic linear transform between document and screen space.

    screen = (local - origin) * zoom + viewport_topleft + scroll
    local  = (screen - viewport_topleft - scroll) / zoom + origin
    """

    def __init__(
        self,
        viewport_x: float = 0.0,
        viewport_y: float = 0.0,
        zoom: float = 1.0,
        scroll_x: float = 0.0,
        scroll_y: float = 0.0,
    ):
        self.viewport_x = float(viewport_x)
        self.viewport_y = float(viewport_y)
        self._zoom = _clamp_zoom(float(zoom))
        self.scroll_x = float(scroll_x)
        self.scroll_y = float(scroll_y)

    @property
    def zoom(self) -> float:
        return self._zoom

    @zoom.setter
    def zoom(self, value: float) -> None:
        self._zoom = _clamp_zoom(float(value))

    def world_to_screen(self, x: float, y: float) -> tuple[float, float]:
        return (
            self.viewport_x + self.scroll_x + x * self._zoom,
            self.viewport_y + self.scroll_y + y * self._zoom,
        )

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        if self._zoom <= 0:
            return (0.0, 0.0)
        return (
            (sx - self.viewport_x - self.scroll_x) / self._zoom,
            (sy - self.viewport_y - self.scroll_y) / self._zoom,
        )

    def fit(self, world_size: tuple[float, float], viewport_size: tuple[float, float]) -> None:
        """Zoom so the whole document fits the viewport, centered."""
        ww, wh = world_size
        vw, vh = viewport_size
        if ww <= 0 or wh <= 0 or vw <= 0 or vh <= 0:
            self.reset()
            return
        self._zoom = _clamp_zoom(min(vw / ww, vh / wh))
        self.scroll_x = (vw - ww * self._zoom) / 2.0
        self.scroll_y = (vh - wh * self._zoom) / 2.0

    def reset(self) -> None:
        """100% zoom, document origin at the viewport top-left."""
        self._zoom = 1.0
        self.scroll_x = 0.0
        self.scroll_y = 0.0

    def zoom_at(self, screen_point: tuple[float, float], factor: float) -> None:
        """Zoom by factor while keeping the world point under the cursor fixed."""
        sx, sy = screen_point
        wx, wy = self.screen_to_world(sx, sy)
        new_zoom = _clamp_zoom(self._zoom * factor)
        if abs(new_zoom - self._zoom) < 1e-9:
            return
        self._zoom = new_zoom
        self.scroll_x = sx - self.viewport_x - wx * self._zoom
        self.scroll_y = sy - self.viewport_y - wy * self._zoom

    def pan(self, dx: float, dy: float) -> None:
        """Scroll by a screen-space delta (content follows the cursor)."""
        self.scroll_x += float(dx)
        self.scroll_y += float(dy)

    def world_to_screen_rect(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        """Screen-space rect for a world-space rect (floats)."""
        sx, sy = self.world_to_screen(x, y)
        return (sx, sy, w * self._zoom, h * self._zoom)
