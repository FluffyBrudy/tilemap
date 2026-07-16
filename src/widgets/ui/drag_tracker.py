from typing import Tuple


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
        self._start: Tuple[float, float] = (0.0, 0.0)

    def begin(
        self,
        mouse_pos: Tuple[int, int],
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
        mouse_pos: Tuple[int, int],
        zoom: float,
        scroll_x: float,
        scroll_y: float,
        rect_x: int,
        rect_y: int,
    ) -> Tuple[float, float]:
        wx = (mouse_pos[0] - rect_x) / zoom + scroll_x
        wy = (mouse_pos[1] - rect_y) / zoom + scroll_y
        return (wx - self._start[0], wy - self._start[1])

    @property
    def active(self) -> bool:
        return self._active
