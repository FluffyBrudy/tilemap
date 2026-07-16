from widgets.ui.drag_tracker import DragTracker


def test_drag_tracker_initial_state():
    t = DragTracker()
    assert not t.active


def test_drag_tracker_begin_active():
    t = DragTracker()
    t.begin((100, 200), 1.0, 0, 0, 0, 0)
    assert t.active


def test_drag_tracker_reset():
    t = DragTracker()
    t.begin((100, 200), 1.0, 0, 0, 0, 0)
    t.reset()
    assert not t.active


def test_drag_tracker_delta_at_zoom_1():
    t = DragTracker()
    t.begin((100, 200), 1.0, 50, 60, 0, 0)
    dx, dy = t.update((150, 260), 1.0, 50, 60, 0, 0)
    assert dx == 50.0
    assert dy == 60.0


def test_drag_tracker_delta_with_scroll():
    t = DragTracker()
    t.begin((100, 200), 1.0, 100, 200, 0, 0)
    dx, dy = t.update((150, 260), 1.0, 100, 200, 0, 0)
    assert dx == 50.0
    assert dy == 60.0


def test_drag_tracker_delta_at_zoom_2():
    t = DragTracker()
    t.begin((200, 400), 2.0, 0, 0, 0, 0)
    dx, dy = t.update((220, 420), 2.0, 0, 0, 0, 0)
    assert dx == 10.0
    assert dy == 10.0


def test_drag_tracker_sub_pixel():
    """At zoom=2, a 1px mouse move should yield 0.5 world delta."""
    t = DragTracker()
    t.begin((100, 200), 2.0, 0, 0, 0, 0)
    dx, dy = t.update((101, 200), 2.0, 0, 0, 0, 0)
    assert dx == 0.5
    assert dy == 0.0


def test_drag_tracker_rect_offset():
    t = DragTracker()
    t.begin((110, 220), 1.0, 0, 0, 10, 20)
    dx, dy = t.update((160, 280), 1.0, 0, 0, 10, 20)
    assert dx == 50.0
    assert dy == 60.0


def test_drag_tracker_idempotent():
    t = DragTracker()
    t.begin((100, 100), 1.0, 0, 0, 0, 0)
    dx1, dy1 = t.update((200, 200), 1.0, 0, 0, 0, 0)
    dx2, dy2 = t.update((200, 200), 1.0, 0, 0, 0, 0)
    assert dx1 == dx2
    assert dy1 == dy2


def test_drag_tracker_negative_delta():
    t = DragTracker()
    t.begin((200, 200), 1.0, 0, 0, 0, 0)
    dx, dy = t.update((100, 100), 1.0, 0, 0, 0, 0)
    assert dx == -100.0
    assert dy == -100.0
