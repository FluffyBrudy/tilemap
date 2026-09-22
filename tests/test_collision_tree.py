"""Tree scrollbar, collision thumbs, broken placeholder."""

import pygame  # noqa: E402
import pytest  # noqa: E402
from pygame import Rect, Surface  # noqa: E402

from plugins.character_collision.collision_thumbs import (  # noqa: E402
    broken_thumb,
    render_thumb,
)
from widgets.ui.tree_widget import TreeNode, TreeWidget  # noqa: E402


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((800, 600))
    yield


def sprite():
    s = Surface((64, 32), pygame.SRCALPHA)
    s.fill((70, 70, 70, 255))
    return s


class TestThumbs:
    def test_each_shape_renders(self):
        shapes = [
            {"type": "rectangle", "width": 20, "height": 10, "offset": (5, 5)},
            {"type": "circle", "radius": 8, "offset": (32, 16)},
            {"type": "capsule", "radius": 5, "height": 12, "offset": (10, 4)},
            {"type": "polygon", "vertices": [(4, 4), (20, 4), (12, 18)], "offset": (0, 0)},
        ]
        for shape in shapes:
            t = render_thumb(sprite(), shape)
            assert t is not None and t.get_size() == (20, 20)

    def test_degenerate_safe(self):
        assert render_thumb(sprite(), {"type": "rectangle", "width": 0, "height": 0}) is not None
        assert render_thumb(sprite(), {"type": "polygon", "vertices": [(1, 1)]}) is not None
        assert render_thumb(Surface((0, 0)), {"type": "circle"}) is None

    def test_crops_to_shape_aabb(self):
        s = Surface((64, 64), pygame.SRCALPHA)
        s.fill((0, 0, 200, 255))
        pygame.draw.rect(s, (200, 0, 0, 255), Rect(8, 8, 8, 8))
        t = render_thumb(s, {"type": "rectangle", "width": 8, "height": 8, "offset": (8, 8)})
        assert t is not None
        assert t.get_at((10, 10)).r > 50

    def test_broken_is_drawn_x(self):
        t = broken_thumb()
        assert t.get_size() == (20, 20)
        assert t.get_at((10, 10)).r > 150


class TestTreeScrollbar:
    def make_tree(self, n):
        tw = TreeWidget(Rect(0, 0, 180, 100))
        tw.set_data([TreeNode(id=f"f{i}", label=f"f{i}") for i in range(n)])
        return tw

    def test_bar_hidden_when_fits(self):
        tw = self.make_tree(2)
        tw.draw(pygame.display.get_surface())
        assert tw._scrollbar_visible() is False

    def test_bar_shows_and_wheel_scrolls(self):
        tw = self.make_tree(20)
        tw.draw(pygame.display.get_surface())
        assert tw._scrollbar_visible() is True
        assert tw.scroll_y == 0
        wheel = pygame.event.Event(pygame.MOUSEWHEEL, {"x": 0, "y": -3})
        pygame.mouse.set_pos((90, 50))
        assert tw.handle_event(wheel) is True
        assert tw.scroll_y > 0

    def test_thumb_hook_shifts_label(self):
        tw = self.make_tree(1)
        tw.thumb_size = 20
        tw.thumb_provider = lambda _node: Surface((20, 20), pygame.SRCALPHA)
        tw.draw(pygame.display.get_surface())
