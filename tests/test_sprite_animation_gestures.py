"""Gesture tests: timeline click-click move + drag threshold, picker paint-sweep.

Covers the UX overhaul:
- timeline: micro-jitter clicks never reorder; real drags still do
- timeline: click frame then click another slot moves it (click-click)
- timeline: same-cell re-click / Esc cancels the armed move
- picker: LMB sweep across tiles bulk-adds (or removes) with locked intent
- picker: hover highlight suppressed while RMB panning
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from plugins.sprite_animation.frame_picker import (  # noqa: E402
    TOP_BAR_TOTAL as FP_TOP_BAR,
)
from plugins.sprite_animation.frame_picker import (
    FramePicker,
)
from plugins.sprite_animation.models import AnimationFrame  # noqa: E402
from plugins.sprite_animation.timeline import Timeline  # noqa: E402


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    # real-sized window: widgets hit-test via get_pos, and a 1x1 screen
    # clamps set_pos to (0,0) which lands inside UI hit zones
    pygame.display.set_mode((900, 700))
    yield
    pygame.quit()
    from utils.font_manager import font_manager

    font_manager.clear_cache()


def send(widget, t, **kw):
    """Sync the real cursor to event pos (widgets hit-test via get_pos), dispatch."""
    if "pos" in kw:
        pygame.mouse.set_pos(kw["pos"])
    return widget.handle_event(pygame.event.Event(t, **kw))


def make_timeline(n=4, cell_w=64):
    tl = Timeline(
        pygame.Rect(0, 0, cell_w * n + 200, 120),
        pygame.Surface((cell_w * n + 200, 120)),
        (48, 48),
    )
    frames = [
        AnimationFrame(variant_id=i, duration_ms=100) for i in range(n)
    ]
    tl.set_frames(frames)

    def thumb(vid):
        s = pygame.Surface((32, 32))
        s.fill((vid * 40, 100, 200))
        return s

    tl._get_thumb = thumb
    return tl


def cell_center(tl, idx):
    """Center of timeline cell idx using the widget's own layout constants."""
    from plugins.sprite_animation.timeline import (
        CELL_BODY_H,
        CELL_PAD,
        CELL_W,
        Timeline,
    )

    x = tl.rect.x + CELL_PAD + idx * (CELL_W + CELL_PAD) - tl.scroll_x
    # upper half of the thumb area — below is the duration-label hit zone
    y = tl._content_y() + 10
    return int(x + CELL_W // 2), int(y)


class TestTimelineDragThreshold:
    def test_jitter_click_does_not_reorder(self):
        tl = make_timeline()
        order = [f.variant_id for f in tl.frames]
        src = cell_center(tl, 1)
        send(tl, pygame.MOUSEBUTTONDOWN, button=1, pos=src)
        send(tl, pygame.MOUSEMOTION, pos=(src[0] + 3, src[1]))
        assert tl._drag_insert == -1, "insert marker must stay hidden pre-threshold"
        send(tl, pygame.MOUSEBUTTONUP, button=1, pos=(src[0] + 3, src[1]))
        assert [f.variant_id for f in tl.frames] == order

    def test_real_drag_reorders(self):
        tl = make_timeline()
        src = cell_center(tl, 0)
        dst = cell_center(tl, 2)
        send(tl, pygame.MOUSEBUTTONDOWN, button=1, pos=src)
        send(tl, pygame.MOUSEMOTION, pos=(dst[0], dst[1]))
        assert tl._drag_moved is True
        send(tl, pygame.MOUSEBUTTONUP, button=1, pos=(dst[0], dst[1]))
        assert [f.variant_id for f in tl.frames] == [1, 2, 0, 3]


class TestTimelineClickClickMove:
    def test_click_then_click_moves_frame(self):
        tl = make_timeline()
        a = cell_center(tl, 0)
        b = cell_center(tl, 3)
        selected = []
        tl.on_frame_selected = lambda i: selected.append(i)

        send(tl, pygame.MOUSEBUTTONDOWN, button=1, pos=a)
        send(tl, pygame.MOUSEBUTTONUP, button=1, pos=a)
        assert tl._pending_move == 0

        send(tl, pygame.MOUSEBUTTONDOWN, button=1, pos=b)
        # frame 0 moved to the end
        assert [f.variant_id for f in tl.frames] == [1, 2, 3, 0]
        assert tl._pending_move == -1
        assert selected[-1] == tl.selected_index

    def test_reclick_same_cell_cancels(self):
        tl = make_timeline()
        a = cell_center(tl, 1)
        send(tl, pygame.MOUSEBUTTONDOWN, button=1, pos=a)
        assert tl._pending_move == 1
        order = [f.variant_id for f in tl.frames]
        send(tl, pygame.MOUSEBUTTONDOWN, button=1, pos=a)
        assert tl._pending_move == -1
        assert [f.variant_id for f in tl.frames] == order

    def test_esc_cancels_pending(self):
        tl = make_timeline()
        pygame.mouse.set_pos(*cell_center(tl, 2))
        a = cell_center(tl, 2)
        send(tl, pygame.MOUSEBUTTONDOWN, button=1, pos=a)
        assert tl._pending_move == 2
        send(tl, pygame.KEYDOWN, key=pygame.K_ESCAPE)
        assert tl._pending_move == -1

    def test_drag_supersedes_pending(self):
        tl = make_timeline()
        src = cell_center(tl, 0)
        dst = cell_center(tl, 3)
        send(tl, pygame.MOUSEBUTTONDOWN, button=1, pos=src)
        send(tl, pygame.MOUSEMOTION, pos=(dst[0], dst[1]))
        send(tl, pygame.MOUSEBUTTONUP, button=1, pos=(dst[0], dst[1]))
        assert tl._pending_move == -1


class TestPickerPaintSweep:
    class FakeEditor:
        def __init__(self):
            self.clip: list[int] = []
            self.painted: list[tuple[int, bool]] = []

        def clicked(self, vid):
            if vid in self.clip:
                self.clip.remove(vid)
            else:
                self.clip.append(vid)

        def paint(self, vid, add):
            self.painted.append((vid, add))
            if add and vid not in self.clip:
                self.clip.append(vid)
            elif not add and vid in self.clip:
                self.clip.remove(vid)

        def in_clip(self, vid):
            return vid in self.clip

    @pytest.fixture
    def picker(self):
        fp = FramePicker(
            pygame.Rect(0, 0, 400, 300),
            pygame.Surface((320, 64)),
            (32, 32),
        )
        fp._recalc_grid()
        # scroll the sheet down so row-0 tiles sit below the top bar
        fp.offset_y = 60

        editor = self.FakeEditor()
        fp.on_frame_clicked = editor.clicked
        fp.on_frame_paint = editor.paint
        fp.is_variant_in_clip = editor.in_clip
        fp.editor = editor
        return fp

    def tile(self, fp, col, row=0):
        x = fp.rect.x + fp.offset_x + int(col * fp.tile_size[0] * fp.zoom) + 16
        y = fp.rect.y + fp.offset_y + int(row * fp.tile_size[1] * fp.zoom) + 16
        return int(x), int(y)

    def test_single_click_still_toggles(self, picker):
        c = self.tile(picker, 0)
        send(picker, pygame.MOUSEBUTTONDOWN, button=1, pos=c)
        send(picker, pygame.MOUSEBUTTONUP, button=1, pos=c)
        assert picker.editor.clip == [0]
        assert picker._painting is False

    def test_sweep_adds_all_crossed_tiles(self, picker):
        start = self.tile(picker, 0)
        send(picker, pygame.MOUSEBUTTONDOWN, button=1, pos=start)
        assert picker._painting is True and picker._paint_add is True
        for col in range(1, 4):
            send(picker, pygame.MOUSEMOTION, pos=self.tile(picker, col))
        send(picker, pygame.MOUSEBUTTONUP, button=1, pos=self.tile(picker, 3))
        assert sorted(picker.editor.clip) == [0, 1, 2, 3]

    def test_sweep_from_added_tile_removes(self, picker):
        picker.editor.clip = [0, 1, 2]
        start = self.tile(picker, 0)
        send(picker, pygame.MOUSEBUTTONDOWN, button=1, pos=start)
        assert picker._paint_add is False
        for col in range(1, 3):
            send(picker, pygame.MOUSEMOTION, pos=self.tile(picker, col))
        send(picker, pygame.MOUSEBUTTONUP, button=1, pos=self.tile(picker, 2))
        assert picker.editor.clip == []

    def test_no_duplicate_on_backtrack(self, picker):
        start = self.tile(picker, 0)
        send(picker, pygame.MOUSEBUTTONDOWN, button=1, pos=start)
        send(picker, pygame.MOUSEMOTION, pos=self.tile(picker, 1))
        send(picker, pygame.MOUSEMOTION, pos=self.tile(picker, 0))
        send(picker, pygame.MOUSEBUTTONUP, button=1, pos=self.tile(picker, 0))
        assert picker.editor.clip.count(0) == 1


class TestPanHoverSuppression:
    def test_hover_hidden_while_panning(self):
        fp = FramePicker(
            pygame.Rect(0, 0, 400, 300),
            pygame.Surface((320, 64)),
            (32, 32),
        )
        fp._recalc_grid()
        fp.offset_y = 60

        t = (
            int(fp.rect.x + fp.offset_x + 16),
            int(fp.rect.y + fp.offset_y + 16),
        )
        pygame.mouse.set_pos(t)
        send(fp, pygame.MOUSEBUTTONDOWN, button=3, pos=t)
        assert fp._panning is True

        moved = (t[0] - 20, t[1] - 10)
        pygame.mouse.set_pos(moved)
        send(fp, pygame.MOUSEMOTION, pos=moved)
        assert fp.hover_index == -1, "panning must not highlight tiles"


class TestFrameSizeMode:
    """Frame-size inputs interpret values as px or as cell counts."""

    @pytest.fixture
    def editor(self):
        from plugins.sprite_animation.editor import SpriteAnimationEditor

        surf = pygame.Surface((320, 64))  # 10 x 2 cells of 32px
        return SpriteAnimationEditor(
            pygame.Rect(0, 0, 900, 700), surface=surf, tile_size=(32, 32)
        )

    def test_default_is_px_mode(self, editor):
        assert editor._frame_size_mode == "px"

    def test_px_mode_unchanged(self, editor):
        editor._frame_width_input = "16"
        editor._frame_height_input = "64"
        editor._apply_frame_size()
        assert editor._tile_size == (16, 64)
        assert editor._frame_width_input == "16"

    def test_cells_mode_divides_sheet(self, editor):
        editor._frame_size_mode = "cells"
        editor._frame_width_input = "10"
        editor._frame_height_input = "2"
        editor._apply_frame_size()
        assert editor._tile_size == (32, 32)
        # inputs echo the cell counts
        assert editor._frame_width_input == "10"
        assert editor._frame_height_input == "2"

    def test_cells_non_divisor_floors(self, editor):
        editor._frame_size_mode = "cells"
        editor._frame_width_input = "3"   # 320/3 -> 106 px
        editor._frame_height_input = "3"  # 64/3 -> 21 px
        editor._apply_frame_size()
        assert editor._tile_size == (106, 21)

    def test_toggle_converts_values_without_jump(self, editor):
        editor._apply_frame_size()          # 32x32 on a 320x64 sheet
        editor._toggle_frame_size_mode()
        assert editor._frame_size_mode == "cells"
        assert editor._frame_width_input == "10"
        assert editor._frame_height_input == "2"
        assert editor._tile_size == (32, 32)  # grid held still

    def test_toggle_back_to_px(self, editor):
        editor._toggle_frame_size_mode()
        editor._toggle_frame_size_mode()
        assert editor._frame_size_mode == "px"
        assert editor._frame_width_input == "32"
        assert editor._tile_size == (32, 32)

    def test_new_sheet_rederives_in_cells_mode(self, editor):
        editor._frame_size_mode = "cells"
        editor._frame_width_input = "8"
        editor._frame_height_input = "4"
        editor._apply_frame_size()

        import pygame as pg

        editor._surface = pg.Surface((160, 128))
        editor._apply_frame_size()
        assert editor._tile_size == (20, 32)
