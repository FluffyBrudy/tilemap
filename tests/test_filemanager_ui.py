"""Tests for filemanager UI helpers (no pygame needed)."""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from widgets.filemanager import FileItem, FileManager, format_file_size


class TestFormatFileSize:
    def test_unknown_and_zero(self):
        assert format_file_size(None) == ""
        assert format_file_size(0) == "0 B"

    def test_bytes(self):
        assert format_file_size(512) == "512 B"

    def test_kilobytes(self):
        assert format_file_size(1536) == "1.5 KB"

    def test_megabytes(self):
        assert format_file_size(2 * 1024 * 1024) == "2.0 MB"

    def test_gigabytes(self):
        assert format_file_size(3 * 1024**3) == "3.0 GB"


class TestBreadcrumbs:
    def test_short_path_no_ellipsis(self):
        crumbs = FileManager.breadcrumb_segments(Path("/a/b"))
        assert [label for label, _ in crumbs] == ["/", "a", "b"]
        assert all(target is not None for _, target in crumbs)
        assert crumbs[-1][1] == Path("/a/b")

    def test_long_path_collapses_middle(self):
        crumbs = FileManager.breadcrumb_segments(Path("/a/b/c/d/e/f"))
        labels = [label for label, _ in crumbs]
        assert labels[0] == "/"
        assert "…" in labels
        assert labels[-2:] == ["e", "f"]
        ellipsis = [c for c in crumbs if c[0] == "…"][0]
        assert ellipsis[1] is None
        assert crumbs[-1][1] == Path("/a/b/c/d/e/f")

    def test_tail_targets_resolve(self):
        crumbs = FileManager.breadcrumb_segments(Path("/a/b/c/d/e"))
        for label, target in crumbs:
            if label not in ("/", "…"):
                assert target is not None
                assert target.name == label


class TestCountSummary:
    def _summary(self, items):
        stub = types.SimpleNamespace(items=items)
        return FileManager._count_summary(stub)

    def test_mixed(self, tmp_path):
        (tmp_path / "a.png").write_bytes(b"x" * 10)
        (tmp_path / "sub").mkdir()
        items = [FileItem(tmp_path / "a.png"), FileItem(tmp_path / "sub")]
        assert self._summary(items) == "2 items · 1 files · 1 folders"

    def test_empty(self):
        assert self._summary([]) == "0 items · 0 files · 0 folders"


class TestFileItemMetadata:
    def test_file_size_and_mtime(self, tmp_path):
        f = tmp_path / "pic.png"
        f.write_bytes(b"x" * 2048)
        item = FileItem(f)
        assert item.size == 2048
        assert item.mtime is not None
        assert item.is_hidden is False

    def test_dir_has_no_size(self, tmp_path):
        item = FileItem(tmp_path)
        assert item.size is None
        assert item.mtime is not None

    def test_hidden_flag(self, tmp_path):
        assert FileItem(tmp_path / ".hidden").is_hidden is True


def make_manager(**overrides):
    import pygame

    fm = FileManager.__new__(FileManager)
    fm.rect = pygame.Rect(0, 0, 900, 600)
    fm.sidebar_width = 156
    fm.header_height = 40
    fm.footer_height = 52
    fm.search_header_height = 35
    fm.item_height = 34
    fm.scroll_speed = 30
    fm.view_mode = "files"
    fm.items = []
    fm.selected_index = -1
    fm.selected_indices = []
    fm.scroll_y = 0
    fm.hover_index = -1
    fm.clicked_item_index = -1
    fm.double_click_timer = 0
    fm.multi_select = False
    fm.data_root = None
    fm.allowed_exts = [".png", ".json"]
    fm.renaming_item_idx = None
    fm.rename_input = types.SimpleNamespace(text="", cursor_pos=0, is_focused=False)
    fm.search_input = types.SimpleNamespace(text="", is_focused=False)
    fm.save_input = types.SimpleNamespace(text="", cursor_pos=0, is_focused=False)
    fm.search_rect = pygame.Rect(0, 0, 0, 0)
    fm.save_name_rect = pygame.Rect(0, 0, 0, 0)
    fm.new_folder_button_rect = pygame.Rect(0, 0, 0, 0)
    fm.mode = "open"
    fm.enable_window_drag = False
    fm.enable_resize_handles = False
    fm.is_dragging_window = False
    fm.drag_offset_x = 0
    fm.drag_offset_y = 0

    class NoResize:
        is_dragging = False

        def get_handle_at_pos(self, pos):
            return None

    fm.resize_handler = NoResize()
    fm.image_preview = types.SimpleNamespace(is_visible=False)
    fm.last_error = None
    fm._error_until_ms = 0
    fm._error_rect = None
    fm._crumb_rects = []
    for key, value in overrides.items():
        setattr(fm, key, value)
    return fm


class TestErrorPill:
    def test_set_and_expiry(self):
        fm = make_manager()
        assert fm._error_live(now=1000) is False
        fm._set_error("boom")
        assert fm.last_error == "boom"
        assert fm._error_live(now=10**12) is False

    def test_clear(self):
        fm = make_manager()
        fm._set_error("boom")
        fm._clear_error()
        assert fm.last_error is None
        assert fm._error_live(now=10**12) is False


class TestCreateFolderFeedback:
    def test_outside_root_reports(self, tmp_path):
        root = tmp_path / "data"
        root.mkdir()
        outside = tmp_path / "elsewhere"
        outside.mkdir()
        fm = make_manager(current_path=outside, data_root=root)
        fm._create_folder()
        assert not (outside / "New Folder").exists()
        assert fm.last_error is not None
        assert "project" in fm.last_error

    def test_recents_reports(self, tmp_path):
        fm = make_manager(current_path=tmp_path, view_mode="recents")
        fm._create_folder()
        assert fm.last_error is not None
        assert "Recents" in fm.last_error

    def test_inside_root_creates(self, tmp_path):
        root = tmp_path / "data"
        root.mkdir()
        fm = make_manager(current_path=root, data_root=root)
        fm._create_folder()
        assert (root / "New Folder").is_dir()
        assert fm.last_error is None


class TestRenameFeedback:
    def test_invalid_chars_reported(self, tmp_path):
        f = tmp_path / "a.png"
        f.write_bytes(b"x")
        fm = make_manager(current_path=tmp_path)
        fm.items = [FileItem(f)]
        fm.renaming_item_idx = 0
        fm.rename_input.text = "bad/name"
        fm._confirm_rename()
        assert f.exists()
        assert fm.last_error is not None
        assert "Invalid" in fm.last_error

    def test_existing_name_reported(self, tmp_path):
        a = tmp_path / "a.png"
        b = tmp_path / "b.png"
        a.write_bytes(b"x")
        b.write_bytes(b"y")
        fm = make_manager(current_path=tmp_path)
        fm.items = [FileItem(a), FileItem(b)]
        fm.renaming_item_idx = 0
        fm.rename_input.text = "b.png"
        fm._confirm_rename()
        assert fm.last_error is not None
        assert "exists" in fm.last_error


class TestSaveResolveFeedback:
    def test_invalid_extension_reported(self, tmp_path):
        fm = make_manager(current_path=tmp_path)
        fm.save_input.text = "map.txt"
        assert fm._resolve_save_path() is None
        assert fm.last_error is not None
        assert "extension" in fm.last_error


class TestHeaderDispatch:
    def _click(self, fm, pos):
        import pygame

        if not pygame.display.get_init():
            pygame.init()
            pygame.display.set_mode((1, 1))
        return fm.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos})
        )

    def test_new_folder_button_dispatches(self, tmp_path):
        root = tmp_path / "data"
        root.mkdir()
        fm = make_manager(current_path=root, data_root=root)
        assert self._click(fm, (840, 20)) is True
        assert (root / "New Folder").is_dir()
        assert fm.renaming_item_idx == 0

    def test_header_click_consumed(self, tmp_path):
        fm = make_manager(current_path=tmp_path)
        # Click on empty header area: consumed, no navigation, no crash.
        assert self._click(fm, (400, 20)) is True
        assert fm.current_path == tmp_path


class TestEscapeLocalOnly:
    def test_cancels_rename(self, tmp_path):
        f = tmp_path / "a.png"
        f.write_bytes(b"x")
        fm = make_manager(current_path=tmp_path)
        fm.items = [FileItem(f)]
        fm.renaming_item_idx = 0
        fm.rename_input.text = "changed"
        assert fm._handle_escape() is True
        assert fm.renaming_item_idx is None
        assert f.exists()  # reverted, not committed

    def test_unfocuses_search(self):
        fm = make_manager()
        fm.search_input.is_focused = True
        assert fm._handle_escape() is True
        assert fm.search_input.is_focused is False

    def test_unfocuses_save_name(self):
        fm = make_manager()
        fm.save_input.is_focused = True
        assert fm._handle_escape() is True
        assert fm.save_input.is_focused is False

    def test_bare_escape_does_not_close(self):
        closed = []
        fm = make_manager()
        fm.on_cancel_callback = lambda: closed.append(True)
        assert fm._handle_escape() is False
        assert closed == []
