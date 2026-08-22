"""System file-drop (DROPFILE) tests for the sprite editor.

Simulates the SDL2 drop event sequence the OS sends when files are
dragged from Finder / Explorer / Linux file managers onto the window:
DROPBEGIN -> one DROPFILE per file -> DROPCOMPLETE.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

import pygame
import pytest
from pygame import Rect

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from plugins.sprite_editor.editor import SpriteEditor  # noqa: E402


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    from utils.font_manager import font_manager

    font_manager.clear_cache()
    yield
    pygame.quit()
    from utils.font_manager import font_manager

    font_manager.clear_cache()


def make_png(path: Path, size: tuple[int, int], color) -> Path:
    surf = pygame.Surface(size, pygame.SRCALPHA)
    surf.fill(color)
    pygame.image.save(surf, str(path))
    return path


@pytest.fixture
def editor():
    ed = SpriteEditor(Rect(0, 0, 1000, 700), tile_size=(32, 32))
    ed._notifications.notifications.clear()
    return ed


def ev(t, **kw):
    return pygame.event.Event(t, **kw)


def drop(editor, *paths):
    """Full drag sequence: enter window, drop files, release."""
    assert editor.handle_event(ev(pygame.DROPBEGIN)) is True
    for p in paths:
        assert editor.handle_event(ev(pygame.DROPFILE, file=str(p))) is True
    assert editor.handle_event(ev(pygame.DROPCOMPLETE)) is True


def drop_text(editor, text):
    """Text drop (no BEGIN/COMPLETE pairing on some platforms)."""
    assert editor.handle_event(ev(pygame.DROPTEXT, text=text)) is True


class TestDropLoadsSheets:
    def test_single_file(self, editor, tmp_path):
        p = make_png(tmp_path / "sheet.png", (64, 32), (255, 0, 0, 255))
        drop(editor, p)
        assert editor.doc.has_canvas
        assert editor.doc.surface.get_size() == (64, 32)
        assert editor.doc.sheets == ["sheet.png"]

    def test_multiple_files_stack_vertically(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (64, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (32, 64), (0, 255, 0, 255))
        drop(editor, a, b)
        assert editor.doc.sheets == ["a.png", "b.png"]
        assert editor.doc.surface.get_size() == (64, 96)

    def test_multiple_files_stack_horizontally(self, editor, tmp_path):
        editor._stack_horizontal = True
        a = make_png(tmp_path / "a.png", (64, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (32, 64), (0, 255, 0, 255))
        drop(editor, a, b)
        assert editor.doc.surface.get_size() == (96, 64)

    def test_files_dropped_in_reverse_order_are_natural_sorted(
        self, editor, tmp_path
    ):
        a = make_png(tmp_path / "s1.png", (32, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "s2.png", (32, 32), (0, 255, 0, 255))
        drop(editor, b, a)
        assert editor.doc.sheets == ["s1.png", "s2.png"]

    def test_tile_size_detected_from_first_drop_when_blank(self, editor, tmp_path):
        make_png(tmp_path / "sheet.png", (64, 64), (10, 20, 30, 255))
        drop(editor, tmp_path / "sheet.png")
        assert editor.doc.tile_size == (64, 64)

    def test_second_drop_replaces_canvas(self, editor, tmp_path):
        make_png(tmp_path / "one.png", (32, 32), (1, 2, 3, 255))
        make_png(tmp_path / "two.png", (48, 48), (4, 5, 6, 255))
        drop(editor, tmp_path / "one.png")
        drop(editor, tmp_path / "two.png")
        assert editor.doc.sheets == ["two.png"]
        assert editor.doc.surface.get_size() == (48, 48)


class TestDropFiltering:
    def test_non_image_files_skipped(self, editor, tmp_path):
        txt = tmp_path / "notes.txt"
        txt.write_text("hello")
        p = make_png(tmp_path / "sheet.png", (32, 32), (9, 9, 9, 255))
        drop(editor, txt, p)
        assert editor.doc.sheets == ["sheet.png"]

    def test_only_non_image_files_warns(self, editor, tmp_path):
        txt = tmp_path / "notes.txt"
        txt.write_text("hello")
        drop(editor, txt)
        assert not editor.doc.has_canvas

    def test_missing_file_skipped(self, editor, tmp_path):
        p = make_png(tmp_path / "real.png", (32, 32), (1, 1, 1, 255))
        drop(editor, tmp_path / "ghost.png", p)
        assert editor.doc.sheets == ["real.png"]

    def test_extension_case_insensitive(self, editor, tmp_path):
        make_png(tmp_path / "sheet.PNG", (32, 32), (1, 1, 1, 255))
        drop(editor, tmp_path / "sheet.PNG")
        assert editor.doc.has_canvas


class TestDropState:
    def test_hover_flag_lifecycle(self, editor, tmp_path):
        p = make_png(tmp_path / "sheet.png", (32, 32), (1, 1, 1, 255))
        editor.handle_event(ev(pygame.DROPBEGIN))
        assert editor._drop_hover is True
        editor.handle_event(ev(pygame.DROPFILE, file=str(p)))
        editor.handle_event(ev(pygame.DROPCOMPLETE))
        assert editor._drop_hover is False
        assert editor._pending_drops is None

    def test_unrelated_motion_consumed_by_tool(self, editor):
        # SelectTool consumes every MOUSEMOTION (hover/marquee tracking)
        # regardless of position — document that contract explicitly
        assert (
            editor.handle_event(ev(pygame.MOUSEMOTION, pos=(1500, 900))) is True
        )
        before = editor._pending_drops
        editor.handle_event(ev(pygame.KEYDOWN, key=pygame.K_a))
        assert editor._pending_drops is before

    def test_new_drag_flushes_stale_batch(self, editor, tmp_path):
        p = make_png(tmp_path / "late.png", (32, 32), (1, 1, 1, 255))
        editor.handle_event(ev(pygame.DROPBEGIN))
        editor.handle_event(ev(pygame.DROPFILE, file=str(p)))
        editor.handle_event(ev(pygame.DROPBEGIN))
        assert editor.doc.has_canvas

    def test_draw_with_hover_does_not_crash(self, editor, tmp_path):
        screen = pygame.Surface((1000, 700))
        editor.handle_event(ev(pygame.DROPBEGIN))
        editor.draw(screen)


class TestDropWithModalOpen:
    def test_drop_while_file_manager_open_loads_and_closes(self, editor, tmp_path):
        class FakeDialog:
            def handle_event(self, event):
                return True

            def draw(self, screen):
                pass

        editor._file_manager = FakeDialog()
        p = make_png(tmp_path / "sheet.png", (32, 32), (1, 1, 1, 255))
        drop(editor, p)
        assert editor._file_manager is None
        assert editor.doc.has_canvas


class TestTextDrop:
    """Drops from code editors (e.g. Zed) arrive as text/URI lists."""

    def test_file_uri(self, editor, tmp_path):
        p = make_png(tmp_path / "sheet.png", (32, 32), (1, 1, 1, 255))
        drop_text(editor, f"file://{p}")
        assert editor.doc.sheets == ["sheet.png"]

    def test_uri_list_multiple(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (1, 1, 1, 255))
        b = make_png(tmp_path / "b.png", (32, 32), (2, 2, 2, 255))
        drop_text(editor, f"file://{a}\nfile://{b}")
        assert editor.doc.sheets == ["a.png", "b.png"]

    def test_localhost_uri(self, editor, tmp_path):
        p = make_png(tmp_path / "sheet.png", (32, 32), (1, 1, 1, 255))
        drop_text(editor, f"file://localhost{p}")
        assert editor.doc.has_canvas

    def test_plain_absolute_path(self, editor, tmp_path):
        p = make_png(tmp_path / "sheet.png", (32, 32), (1, 1, 1, 255))
        drop_text(editor, str(p))
        assert editor.doc.has_canvas

    def test_spaces_in_path_unquoted(self, editor, tmp_path):
        p = make_png(tmp_path / "my sheet.png", (32, 32), (1, 1, 1, 255))
        drop_text(editor, f"file://{p}")
        assert editor.doc.has_canvas

    def test_plain_code_text_ignored(self, editor):
        drop_text(editor, "def hello_world():\n    pass")
        assert not editor.doc.has_canvas
        assert editor._pending_drops is None

    def test_non_image_uri_ignored(self, editor, tmp_path):
        txt = tmp_path / "notes.txt"
        txt.write_text("hi")
        drop_text(editor, f"file://{txt}")
        assert not editor.doc.has_canvas

    def test_consumed_even_when_not_paths(self, editor):
        assert editor.handle_event(ev(pygame.DROPTEXT, text="just words")) is True


class TestClipboardPaste:
    """Cmd/Ctrl+V loads sheets when the clipboard holds image paths."""

    def press_ctrl_v(self, editor):
        pygame.key.set_mods(pygame.KMOD_CTRL)
        result = editor.handle_event(ev(pygame.KEYDOWN, key=pygame.K_v))
        pygame.key.set_mods(0)
        return result

    def test_clipboard_file_uri_loads(self, editor, tmp_path):
        p = make_png(tmp_path / "sheet.png", (32, 32), (1, 1, 1, 255))
        editor._clipboard_text = lambda: f"file://{p}"
        assert self.press_ctrl_v(editor) is True
        assert editor.doc.sheets == ["sheet.png"]

    def test_clipboard_uri_list_loads(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (1, 1, 1, 255))
        b = make_png(tmp_path / "b.png", (32, 32), (2, 2, 2, 255))
        editor._clipboard_text = lambda: f"file://{a}\nfile://{b}"
        assert editor._paste_paths_from_clipboard() is True
        assert editor.doc.sheets == ["a.png", "b.png"]

    def test_clipboard_plain_path_loads(self, editor, tmp_path):
        p = make_png(tmp_path / "sheet.png", (32, 32), (1, 1, 1, 255))
        editor._clipboard_text = lambda: str(p)
        assert editor._paste_paths_from_clipboard() is True
        assert editor.doc.has_canvas

    def test_clipboard_code_text_returns_false(self, editor):
        editor._clipboard_text = lambda: "def hello(): pass"
        assert editor._paste_paths_from_clipboard() is False
        assert not editor.doc.has_canvas

    def test_empty_clipboard_returns_false(self, editor):
        editor._clipboard_text = lambda: ""
        assert editor._paste_paths_from_clipboard() is False

    def test_ctrl_v_falls_back_without_crash(self, editor):
        editor._clipboard_text = lambda: "no paths here"
        assert self.press_ctrl_v(editor) is True


class TestPasteStacksOntoCanvas:
    """Pasting paths with content loaded appends (stacks), never overwrites."""

    def paste(self, editor, *paths):
        editor._clipboard_text = lambda: "\n".join(str(p) for p in paths)
        return editor._paste_paths_from_clipboard()

    def test_first_paste_loads(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        self.paste(editor, a)
        assert editor.doc.surface.get_size() == (32, 32)
        assert editor.doc.sheets == ["a.png"]

    def test_second_paste_stacks_vertically(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (32, 16), (0, 255, 0, 255))
        self.paste(editor, a)
        self.paste(editor, b)
        assert editor.doc.surface.get_size() == (32, 48)
        assert editor.doc.sheets == ["a.png", "b.png"]

    def test_second_paste_stacks_horizontally(self, editor, tmp_path):
        editor._stack_horizontal = True
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (16, 32), (0, 255, 0, 255))
        self.paste(editor, a)
        self.paste(editor, b)
        assert editor.doc.surface.get_size() == (48, 32)

    def test_wider_sheet_grows_width(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (64, 16), (0, 255, 0, 255))
        self.paste(editor, a)
        self.paste(editor, b)
        assert editor.doc.surface.get_size() == (64, 48)

    def test_existing_pixels_preserved(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (32, 16), (0, 255, 0, 255))
        self.paste(editor, a)
        self.paste(editor, b)
        assert editor.doc.surface.get_at((5, 5)) == (255, 0, 0, 255)
        assert editor.doc.surface.get_at((5, 40)) == (0, 255, 0, 255)

    def test_append_is_undoable(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (32, 16), (0, 255, 0, 255))
        self.paste(editor, a)
        self.paste(editor, b)
        assert editor.commands.undo_name() == "Import Sheets"
        editor.commands.undo(editor.doc, editor.selection)
        assert editor.doc.surface.get_size() == (32, 32)

    def test_multi_path_single_paste_stacks_once(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (32, 16), (0, 255, 0, 255))
        c = make_png(tmp_path / "c.png", (32, 8), (0, 0, 255, 255))
        self.paste(editor, a)
        self.paste(editor, b, c)
        assert editor.doc.surface.get_size() == (32, 56)


class TestStackPlacement:
    """Direction changes mid-build continue from the latest content."""

    def paste(self, editor, *paths):
        editor._clipboard_text = lambda: "\n".join(str(p) for p in paths)
        ok = editor._paste_paths_from_clipboard()
        editor.doc.tile_size = (32, 32)
        return ok

    def bounds_of(self, doc, color):
        px = doc.surface
        pts = [
            (x, y)
            for x in range(px.get_width())
            for y in range(px.get_height())
            if tuple(px.get_at((x, y)))[:3] == color
        ]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    def test_hstack_after_vstack_beside_latest_row(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (32, 16), (0, 255, 0, 255))
        c = make_png(tmp_path / "c.png", (16, 16), (0, 0, 255, 255))
        self.paste(editor, a)
        self.paste(editor, b)
        editor._stack_horizontal = True
        self.paste(editor, c)
        assert self.bounds_of(editor.doc, (0, 0, 255)) == (32, 32, 47, 47)

    def test_hstack_snaps_up_when_not_row_multiple(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (32, 16), (0, 255, 0, 255))
        c = make_png(tmp_path / "c.png", (16, 20), (0, 0, 255, 255))
        self.paste(editor, a)
        self.paste(editor, b)
        editor._stack_horizontal = True
        self.paste(editor, c)
        assert editor.doc.surface.get_size() == (48, 52)
        assert self.bounds_of(editor.doc, (0, 0, 255)) == (32, 32, 47, 51)

    def test_vstack_pads_to_grid_on_misaligned_canvas(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 20), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (32, 16), (0, 255, 0, 255))
        self.paste(editor, a)
        self.paste(editor, b)
        assert editor.doc.surface.get_size() == (32, 48)
        assert editor.doc.surface.get_at((5, 25))[3] == 0
        assert editor.doc.surface.get_at((5, 40)) == (0, 255, 0, 255)

    def test_oversized_hsheet_grows_canvas(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        c = make_png(tmp_path / "c.png", (16, 64), (0, 0, 255, 255))
        self.paste(editor, a)
        editor._stack_horizontal = True
        self.paste(editor, c)
        assert editor.doc.surface.get_size() == (48, 64)
        assert self.bounds_of(editor.doc, (0, 0, 255)) == (32, 0, 47, 63)

    def test_mixed_directions_preserve_pixels(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (32, 16), (0, 255, 0, 255))
        c = make_png(tmp_path / "c.png", (16, 16), (0, 0, 255, 255))
        self.paste(editor, a)
        self.paste(editor, b)
        editor._stack_horizontal = True
        self.paste(editor, c)
        px = editor.doc.surface
        assert px.get_at((5, 5)) == (255, 0, 0, 255)
        assert px.get_at((5, 40)) == (0, 255, 0, 255)
        assert px.get_at((40, 40)) == (0, 0, 255, 255)

    def test_placement_undo_restores_canvas(self, editor, tmp_path):
        a = make_png(tmp_path / "a.png", (32, 32), (255, 0, 0, 255))
        b = make_png(tmp_path / "b.png", (32, 16), (0, 255, 0, 255))
        c = make_png(tmp_path / "c.png", (16, 16), (0, 0, 255, 255))
        self.paste(editor, a)
        self.paste(editor, b)
        editor._stack_horizontal = True
        self.paste(editor, c)
        assert editor.doc.surface.get_size() == (48, 48)
        editor.commands.undo(editor.doc, editor.selection)
        assert editor.doc.surface.get_size() == (32, 48)
        editor.commands.undo(editor.doc, editor.selection)
        assert editor.doc.surface.get_size() == (32, 32)


class TestClipboardFallbackRobustness:
    """No crash when scrap fails and no platform clipboard tool exists."""

    def test_all_tools_missing(self, editor, monkeypatch):
        import pygame.scrap

        monkeypatch.setattr(
            pygame.scrap, "get_text", lambda *a, **k: (_ for _ in ()).throw(Exception("no scrap"))
        )
        import shutil

        monkeypatch.setattr(shutil, "which", lambda name: None)
        assert SpriteEditor._clipboard_text() == ""

    def test_subprocess_raises_file_not_found(self, editor, monkeypatch):
        import shutil
        import subprocess

        import pygame.scrap

        monkeypatch.setattr(
            pygame.scrap, "get_text", lambda *a, **k: (_ for _ in ()).throw(Exception("no scrap"))
        )
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
        def boom(*a, **k):
            raise FileNotFoundError("gone")
        monkeypatch.setattr(subprocess, "run", boom)
        assert SpriteEditor._clipboard_text() == ""

    def test_subprocess_timeout_ignored(self, editor, monkeypatch):
        import shutil
        import subprocess

        import pygame.scrap

        monkeypatch.setattr(
            pygame.scrap, "get_text", lambda *a, **k: (_ for _ in ()).throw(Exception("no scrap"))
        )
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
        def slow(*a, **k):
            raise subprocess.TimeoutExpired(cmd="pbpaste", timeout=5)
        monkeypatch.setattr(subprocess, "run", slow)
        assert SpriteEditor._clipboard_text() == ""

    def test_fallback_tool_output_used(self, editor, monkeypatch):
        import shutil
        import subprocess

        import pygame.scrap

        monkeypatch.setattr(
            pygame.scrap, "get_text", lambda *a, **k: (_ for _ in ()).throw(Exception("no scrap"))
        )
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
        class R:
            returncode = 0
            stdout = "/tmp/x.png"
        monkeypatch.setattr(subprocess, "run", lambda *a, **k: R())
        assert SpriteEditor._clipboard_text() == "/tmp/x.png"

    def test_scrap_none_then_fallback(self, editor, monkeypatch):
        import shutil
        import subprocess

        import pygame.scrap

        monkeypatch.setattr(pygame.scrap, "get_text", lambda *a, **k: None)
        monkeypatch.setattr(shutil, "which", lambda name: None)
        assert SpriteEditor._clipboard_text() == ""
