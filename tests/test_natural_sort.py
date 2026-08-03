"""Natural sort: natural_key util + FileManager listing order."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.natural_sort import natural_key, sorted_natural  # noqa: E402


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()
    from utils.font_manager import font_manager

    font_manager.clear_cache()


def test_frame_2_before_frame_11():
    assert natural_key("frame_2.png") < natural_key("frame_11.png")


def test_multi_digit_runs():
    assert natural_key("walk_2_5") < natural_key("walk_10_1")
    assert natural_key("walk_2b.png") < natural_key("walk_10a.png")


def test_case_insensitive():
    assert natural_key("A.png") == natural_key("a.png")
    assert natural_key("b.png") < natural_key("C.png")


def test_mixed_names_no_type_error():
    names = ["a1b", "aab", "a2", "a10", "a2b"]
    assert sorted(names, key=natural_key) == ["a1b", "a2", "a2b", "a10", "aab"]


def test_digit_suffix_order():
    # text-prefix + digit-run still sorts numerically: 2 < 10
    assert natural_key("sheet_2.png") < natural_key("sheet_10.png")


def test_sorted_natural_paths():
    paths = [Path("frame_11.png"), Path("frame_2.png"), Path("frame_1.png")]
    assert [p.name for p in sorted_natural(paths)] == [
        "frame_1.png",
        "frame_2.png",
        "frame_11.png",
    ]


def test_filemanager_lists_naturally(tmp_path):
    from widgets.filemanager import FileManager

    (tmp_path / "frame_2.png").write_bytes(b"")
    (tmp_path / "frame_11.png").write_bytes(b"")
    (tmp_path / "frame_1.png").write_bytes(b"")
    fm = FileManager(
        pygame.Rect(0, 0, 600, 400),
        initial_dir=tmp_path,
        allowed_exts=[".png"],
        data_root=tmp_path,
    )
    fm.refresh_items()
    assert [i.name for i in fm.items] == [
        "frame_1.png",
        "frame_2.png",
        "frame_11.png",
    ]
