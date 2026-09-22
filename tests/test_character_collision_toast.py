"""Already-loaded collision files must not re-toast success (errors still show)."""

from pathlib import Path
from types import SimpleNamespace

import pygame  # noqa: E402
import pytest  # noqa: E402

from plugins.character_collision.editor import CharacterCollisionEditor  # noqa: E402


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


class Recorder:
    def __init__(self):
        self.successes = []
        self.errors = []

    def success(self, msg, *a):
        self.successes.append(msg)

    def error(self, msg, *a):
        self.errors.append(msg)


def make_editor(tmp_path):
    ed = CharacterCollisionEditor.__new__(CharacterCollisionEditor)
    ed._toast_manager = Recorder()
    ed._current_collision_path = None
    ed._data_root = tmp_path

    def fake_load(path):
        ed._current_collision_path = Path(path)

    ed.load_from_file = fake_load
    return ed


def write_collision(path):
    import json

    path.write_text(json.dumps({"name": "x", "shape": {"type": "rectangle"}}))


def test_repeat_selection_suppresses_success(tmp_path):
    ed = make_editor(tmp_path)
    p = tmp_path / "a.collision.json"
    write_collision(p)
    node = SimpleNamespace(data=p)
    ed._file_tree = SimpleNamespace(find_node=lambda _id: node)
    ed._on_tree_selection(["a.collision.json"])
    assert ed._toast_manager.successes == ["Loaded collision: a.collision.json"]
    ed._on_tree_selection(["a.collision.json"])
    assert ed._toast_manager.successes == ["Loaded collision: a.collision.json"]
    assert ed._toast_manager.errors == []


def test_alternating_files_still_toast_once_each(tmp_path):
    ed = make_editor(tmp_path)
    pa, pb = tmp_path / "a.collision.json", tmp_path / "b.collision.json"
    write_collision(pa)
    write_collision(pb)
    nodes = {"a.collision.json": SimpleNamespace(data=pa),
             "b.collision.json": SimpleNamespace(data=pb)}
    ed._file_tree = SimpleNamespace(find_node=lambda _id: nodes[_id])
    ed._on_tree_selection(["a.collision.json"])
    ed._on_tree_selection(["b.collision.json"])
    ed._on_tree_selection(["a.collision.json"])
    assert ed._toast_manager.successes == [
        "Loaded collision: a.collision.json",
        "Loaded collision: b.collision.json",
        "Loaded collision: a.collision.json",
    ]


def test_errors_never_suppressed(tmp_path):
    ed = make_editor(tmp_path)
    p = tmp_path / "bad.collision.json"
    p.write_text("{nope")
    ed._file_tree = SimpleNamespace(find_node=lambda _id: SimpleNamespace(data=p))

    def boom(_path):
        raise ValueError("Invalid collision file: not valid JSON")

    ed.load_from_file = boom
    ed._on_tree_selection(["bad.collision.json"])
    ed._on_tree_selection(["bad.collision.json"])
    assert ed._toast_manager.successes == []
    assert len(ed._toast_manager.errors) == 2
