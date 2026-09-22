"""E2E journeys for the file manager: create, rename, save, navigate.

Pure helpers (sizes, breadcrumbs, counts, metadata) live in
test_filemanager_ui.py. The shared widget harness (make_manager) also
lives there - imported, not duplicated. marked e2e: synthetic events,
full interaction paths.
"""

import pygame
import pytest
from test_filemanager_ui import FileItem, make_manager

pytestmark = pytest.mark.e2e


def _click(fm, pos):
    return fm.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos})
    )


def _f5(fm):
    return fm.handle_event(
        pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_F5, "unicode": ""})
    )


def test_create_folder_journey(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    outside = tmp_path / "elsewhere"
    outside.mkdir()

    fm = make_manager(current_path=outside, data_root=root)
    fm._create_folder()
    assert not (outside / "New Folder").exists()
    assert fm.last_error is not None and "project" in fm.last_error

    fm = make_manager(current_path=tmp_path, view_mode="recents")
    fm._create_folder()
    assert "Recents" in fm.last_error

    fm = make_manager(current_path=root, data_root=root)
    fm._create_folder()
    assert (root / "New Folder").is_dir()
    assert fm.last_error is None

    # ...and through the real header button, not just the method: a
    # rename session starts on the new folder.
    assert _click(fm, (840, 20)) is True
    assert fm.renaming_item_idx is not None


def test_rename_journey(tmp_path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    a.write_bytes(b"x")
    b.write_bytes(b"y")

    fm = make_manager(current_path=tmp_path)
    fm.items = [FileItem(a), FileItem(b)]
    fm.renaming_item_idx = 0
    fm.rename_input.text = "bad/name"
    fm._confirm_rename()
    assert a.exists() and "Invalid" in fm.last_error

    fm.renaming_item_idx = 0  # failed confirms cancel rename; user retries
    fm.rename_input.text = "b.png"
    fm._confirm_rename()
    assert "exists" in fm.last_error

    fm.renaming_item_idx = 0  # failed confirms cancel rename; user retries
    fm.rename_input.text = "changed"
    assert fm._handle_escape() is True
    assert fm.renaming_item_idx is None
    assert a.exists()  # reverted, not committed


def test_save_resolve_journey(tmp_path):
    fm = make_manager(current_path=tmp_path)
    fm.save_input.text = "map.txt"
    assert fm._resolve_save_path() is None
    assert "extension" in fm.last_error


def test_header_and_keyboard_journey(tmp_path):
    fm = make_manager(current_path=tmp_path)
    assert _click(fm, (400, 20)) is True  # empty header: consumed, no crash
    assert fm.current_path == tmp_path

    fm.search_input.is_focused = True
    assert fm._handle_escape() is True
    assert fm.search_input.is_focused is False

    fm.save_input.is_focused = True
    assert fm._handle_escape() is True
    assert fm.save_input.is_focused is False

    closed = []
    fm.on_cancel_callback = lambda: closed.append(True)
    assert fm._handle_escape() is False
    assert closed == []


def test_f5_refresh_guard_journey(tmp_path):
    fm = make_manager(current_path=tmp_path)
    calls = []
    fm.refresh_items = lambda: calls.append(True)
    assert _f5(fm) is True
    assert calls == [True]

    fm.renaming_item_idx = 0
    fm.rename_input.text = "half-typed"
    fm.rename_input.handle_event = lambda event: False
    assert _f5(fm) is True  # consumed by rename path...
    assert calls == [True]  # ...but no refresh happens mid-rename
    assert fm.renaming_item_idx == 0
    assert fm.rename_input.text == "half-typed"


def test_recents_prune_missing_and_write_back_journey(tmp_path):
    import json

    root = tmp_path / "data"
    root.mkdir()
    kept = root / "kept.json"
    kept.write_text("{}")
    missing = root / "gone.json"

    (root / "recents.json").write_text(json.dumps([str(kept), str(missing)]))

    fm = make_manager(data_root=root)
    fm.recents_path = root / "recents.json"
    fm.recents = fm._load_recents()

    assert fm.recents == [kept]
    assert json.loads((root / "recents.json").read_text()) == [str(kept)]


def test_recents_add_dedupes_moves_to_front_and_caps(tmp_path):
    root = tmp_path / "data"
    root.mkdir()

    fm = make_manager(data_root=root)
    fm.recents_path = root / "recents.json"
    fm.recents = []

    maps = []
    for i in range(22):
        p = root / f"map{i}.json"
        p.write_text("{}")
        maps.append(p)

    for p in maps:
        fm._add_to_recents(p)
    assert len(fm.recents) == 20
    assert fm.recents[0] == maps[-1]

    fm._add_to_recents(maps[0])
    assert fm.recents[0] == maps[0]
    assert len(fm.recents) == 20
    assert fm.recents.count(maps[0]) == 1
