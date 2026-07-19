from __future__ import annotations

from enum import IntFlag


class ResizeEdge(IntFlag):
    LEFT = 1
    RIGHT = 2
    TOP = 4
    BOTTOM = 8


class DragTracker:
    """Float-precision delta tracker for drag operations.

    Stores the initial world-coordinate position on begin(),
    then returns float-precision deltas on update().
    All consumers share the same coordinate math — no int truncation until final assignment.

    Usage:
        tracker = DragTracker()

        # On mouse down:
        tracker.begin(mouse_pos, zoom, scroll_x, scroll_y, rect_x, rect_y)

        # On mouse motion:
        dx, dy = tracker.update(mouse_pos, zoom, scroll_x, scroll_y, rect_x, rect_y)
        target.x = int(orig_x + dx)
        target.y = int(orig_y + dy)

        # On mouse up:
        tracker.reset()
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self._active = False
        self._start: tuple[float, float] = (0.0, 0.0)

    def begin(
        self,
        mouse_pos: tuple[int, int],
        zoom: float,
        scroll_x: float,
        scroll_y: float,
        rect_x: int,
        rect_y: int,
    ):
        self._active = True
        wx = (mouse_pos[0] - rect_x) / zoom + scroll_x
        wy = (mouse_pos[1] - rect_y) / zoom + scroll_y
        self._start = (wx, wy)

    def update(
        self,
        mouse_pos: tuple[int, int],
        zoom: float,
        scroll_x: float,
        scroll_y: float,
        rect_x: int,
        rect_y: int,
    ) -> tuple[float, float]:
        wx = (mouse_pos[0] - rect_x) / zoom + scroll_x
        wy = (mouse_pos[1] - rect_y) / zoom + scroll_y
        return (wx - self._start[0], wy - self._start[1])

    @property
    def active(self) -> bool:
        return self._active


class ResizeTracker:
    """Float-precision rect resize with old_r/old_b fixed-edge math.

    Stores the original rect as floats on begin(),
    then computes new rect from current world position on update().
    Only one int truncation per edge (at the derived width/height).

    Usage:
        tracker = ResizeTracker()

        # On mouse down:
        tracker.begin(orig_rect.x, orig_rect.y, orig_rect.w, orig_rect.h)

        # On mouse motion:
        edges = ResizeEdge.LEFT | ResizeEdge.TOP
        nx, ny, nw, nh = tracker.update(wx, wy, edges, min_size=8)
        region.rect = Rect(nx, ny, nw, nh)

        # On mouse up:
        tracker.reset()
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self._active = False
        self._ox: float = 0.0
        self._oy: float = 0.0
        self._ow: float = 0.0
        self._oh: float = 0.0

    def begin(self, x: float, y: float, w: float, h: float):
        self._active = True
        self._ox = x
        self._oy = y
        self._ow = w
        self._oh = h

    def update(
        self,
        wx: float,
        wy: float,
        edges: ResizeEdge,
        min_size: int = 8,
    ) -> tuple[int, int, int, int]:
        old_r = self._ox + self._ow
        old_b = self._oy + self._oh

        nx = self._ox
        ny = self._oy
        nw = self._ow
        nh = self._oh

        if edges & ResizeEdge.LEFT:
            nx = int(min(wx, old_r - min_size))
            nw = int(old_r - nx)
        if edges & ResizeEdge.RIGHT:
            nw = int(max(min_size, wx - self._ox))
        if edges & ResizeEdge.TOP:
            ny = int(min(wy, old_b - min_size))
            nh = int(old_b - ny)
        if edges & ResizeEdge.BOTTOM:
            nh = int(max(min_size, wy - self._oy))

        nw = max(min_size, nw)
        nh = max(min_size, nh)
        return (nx, ny, nw, nh)

    @property
    def active(self) -> bool:
        return self._active
