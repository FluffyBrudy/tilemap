"""Editor interaction tests: selection, copy/paste, move, region, tools, chrome.

Drives the full event pipeline (pygame event -> editor -> tool -> command),
same shape as the plan's §14 test list.
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

from plugins.sprite_editor.document import Region  # noqa: E402
from plugins.sprite_editor.editor import SpriteEditor, STATUS_H, TOOLBAR_H  # noqa: E402
from plugins.sprite_editor.tools import PasteTool, RegionTool, SelectTool  # noqa: E402
from plugins.sprite_editor.viewport import HEADER_H  # noqa: E402


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    pygame.key.set_mods(0)
    yield
    pygame.key.set_mods(0)
    pygame.quit()
    from utils.font_manager import font_manager

    font_manager.clear_cache()


@pytest.fixture
def editor():
    surf = pygame.Surface((128, 128), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    for c in range(4):
        for r in range(4):
            surf.fill((100 + c * 20, 60 + r * 20, 200), (c * 32 + 2, r * 32 + 2, 28, 28))
    ed = SpriteEditor(Rect(0, 0, 1000, 700), surf, (32, 32))
    ed._notifications.notifications.clear()
    return ed


def ev(t, **kw):
    return pygame.event.Event(t, **kw)


def screen_for(cell):
    """Center of a cell on screen at zoom 1, scroll 0, content below header."""
    return (cell[0] * 32 + 16, TOOLBAR_H + HEADER_H + cell[1] * 32 + 16)


def click(ed, pos, button=1):
    ed.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=button, pos=pos))
    ed.handle_event(ev(pygame.MOUSEBUTTONUP, button=button, pos=pos))


def ctrl_click(editor, cell):
    pygame.key.set_mods(pygame.KMOD_CTRL)
    click(editor, screen_for(cell))
    pygame.key.set_mods(0)


def drag(ed, start, end, button=1):
    """Press at start, move to end while held, release at end."""
    ed.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=button, pos=start))
    ed.handle_event(ev(pygame.MOUSEMOTION, pos=end))
    ed.handle_event(ev(pygame.MOUSEBUTTONUP, button=button, pos=end))


def pixel_at(doc, col, row, dx=5, dy=5):
    return doc.surface.get_at((col * doc.tw + dx, row * doc.th + dy))


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


class TestSelectionFlow:
    def test_click_selects(self, editor):
        click(editor, screen_for((1, 1)))
        assert editor.selection.cells == {(1, 1)}

    def test_click_empty_clears(self, editor):
        click(editor, screen_for((0, 0)))
        assert editor.selection.cells == {(0, 0)}
        # click below the canvas
        click(editor, (16, TOOLBAR_H + 200))
        assert not editor.selection

    def test_ctrl_click_toggles(self, editor):
        click(editor, screen_for((0, 0)))
        pygame.key.set_mods(pygame.KMOD_CTRL)
        click(editor, screen_for((1, 0)))
        pygame.key.set_mods(pygame.KMOD_CTRL)
        click(editor, screen_for((0, 0)))
        pygame.key.set_mods(0)
        assert editor.selection.cells == {(1, 0)}

    def test_ctrl_drag_marquee(self, editor):
        pygame.key.set_mods(pygame.KMOD_CTRL)
        editor.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(4, TOOLBAR_H + 4)))
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=screen_for((2, 2))))
        editor.handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=screen_for((2, 2))))
        pygame.key.set_mods(0)
        # world from (4,4) to (80,80) covers cells (0,0)..(2,2)
        assert len(editor.selection) == 9


# ---------------------------------------------------------------------------
# Copy / Paste / Cut (plan §7 + P1-P9)
# ---------------------------------------------------------------------------


class TestCopyPaste:
    def test_copy_paste_places_and_selects(self, editor):
        click(editor, screen_for((0, 0)))
        ctrl_click(editor, (1, 0))
        editor._on_copy()
        assert len(editor.clipboard) == 2
        assert editor.clipboard.tile_size == (32, 32)

        editor._on_paste()
        assert isinstance(editor._active_tool, PasteTool)
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=screen_for((2, 2))))
        click(editor, screen_for((2, 2)))
        assert isinstance(editor._active_tool, SelectTool)
        assert editor.selection.cells == {(2, 2), (3, 2)}
        assert pixel_at(editor.doc, 2, 2)[:3] == (100, 60, 200)
        assert pixel_at(editor.doc, 3, 2)[:3] == (120, 60, 200)

    def test_paste_esc_cancels(self, editor):
        click(editor, screen_for((0, 0)))
        editor._on_copy()
        editor._on_paste()
        assert isinstance(editor._active_tool, PasteTool)
        editor.handle_event(ev(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert isinstance(editor._active_tool, SelectTool)
        assert editor.doc.revision < 2  # nothing changed

    def test_paste_click_empty_cancels_with_toast(self, editor):
        click(editor, screen_for((0, 0)))
        editor._on_copy()
        editor._on_paste()
        editor.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(16, TOOLBAR_H + 300)))
        assert isinstance(editor._active_tool, SelectTool)
        assert any("canceled" in n.text.lower() for n in editor._notifications.notifications)

    def test_paste_empty_clipboard_warns(self, editor):
        editor._on_paste()
        assert isinstance(editor._active_tool, SelectTool)
        assert editor._status_bar.current.message == "Nothing to paste"

    def test_paste_toggle_cancels(self, editor):
        click(editor, screen_for((0, 0)))
        editor._on_copy()
        editor._on_paste()
        assert isinstance(editor._active_tool, PasteTool)
        editor._on_paste()  # click Paste again = cancel, not toggle-to-place
        assert isinstance(editor._active_tool, SelectTool)

    def test_cut_clears_and_pastes(self, editor):
        click(editor, screen_for((0, 0)))
        ctrl_click(editor, (1, 0))
        editor._on_cut()
        assert pixel_at(editor.doc, 0, 0) == (0, 0, 0, 0)
        assert pixel_at(editor.doc, 1, 0) == (0, 0, 0, 0)
        assert len(editor.clipboard) == 2
        assert not editor.selection
        editor._on_paste()
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=screen_for((1, 1))))
        click(editor, screen_for((1, 1)))
        assert pixel_at(editor.doc, 1, 1)[:3] == (100, 60, 200)

    def test_cut_button_exists(self, editor):
        btn = editor._get_btn("cut")
        assert btn is not None

    def test_paste_after_scale_lands_in_current_grid_cells(self, editor):
        # P6: clipboard survives scale; pastes land in (dx,dy) cells of the new grid
        click(editor, screen_for((0, 0)))
        ctrl_click(editor, (1, 0))
        editor._on_copy()
        editor._apply_scale(0.5)  # canvas 64x64, tile still 32
        assert editor.doc.surface.get_size() == (64, 64)
        editor._on_paste()
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=screen_for((0, 0))))
        click(editor, screen_for((0, 0)))
        # target = (0,0); covered = (0,0),(1,0); canvas expands to 64 wide
        assert editor.selection.cells == {(0, 0), (1, 0)}
        assert editor.doc.surface.get_size() == (64, 64)

    def test_copy_without_selection_warns(self, editor):
        editor._on_copy()
        assert editor._status_bar.current.message == "Nothing to copy"


# ---------------------------------------------------------------------------
# Move / drag (plan §6.3)
# ---------------------------------------------------------------------------


class TestMove:
    def test_drag_move_commits(self, editor):
        click(editor, screen_for((0, 0)))
        drag(editor, screen_for((0, 0)), screen_for((2, 0)))
        assert editor.selection.cells == {(2, 0)}
        assert pixel_at(editor.doc, 2, 0)[:3] == (100, 60, 200)
        assert pixel_at(editor.doc, 0, 0) == (0, 0, 0, 0)
        assert editor.commands.can_undo

    def test_move_esc_restores(self, editor):
        click(editor, screen_for((0, 0)))
        editor.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=screen_for((0, 0))))
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=screen_for((3, 3))))
        editor.handle_event(ev(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        assert pixel_at(editor.doc, 0, 0)[:3] == (100, 60, 200)
        assert pixel_at(editor.doc, 3, 3)[:3] != (100, 60, 200)
        assert not editor.commands.can_undo

    def test_move_zero_offset_no_command(self, editor):
        click(editor, screen_for((0, 0)))
        drag(editor, screen_for((0, 0)), screen_for((0, 0)))
        assert not editor.commands.can_undo
        assert pixel_at(editor.doc, 0, 0)[:3] == (100, 60, 200)

    def test_move_expands_then_undo_shrinks(self, editor):
        click(editor, screen_for((3, 0)))
        drag(editor, screen_for((3, 0)), screen_for((6, 0)))
        assert editor.doc.surface.get_size() == (224, 128)
        editor._on_undo()
        assert editor.doc.surface.get_size() == (128, 128)

    def test_arrows_nudge_selection(self, editor):
        click(editor, screen_for((1, 1)))
        editor.handle_event(ev(pygame.KEYDOWN, key=pygame.K_RIGHT))
        assert editor.selection.cells == {(2, 1)}
        assert pixel_at(editor.doc, 2, 1)[:3] == (120, 80, 200)

    def test_delete_clears_selection(self, editor):
        click(editor, screen_for((0, 0)))
        editor.handle_event(ev(pygame.KEYDOWN, key=pygame.K_DELETE))
        assert pixel_at(editor.doc, 0, 0) == (0, 0, 0, 0)
        assert not editor.selection

    def test_move_undo_redo_selection_memory(self, editor):
        click(editor, screen_for((0, 0)))
        ctrl_click(editor, (1, 0))
        editor._on_copy()
        editor._on_paste()
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=screen_for((2, 2))))
        click(editor, screen_for((2, 2)))
        assert editor.selection.cells == {(2, 2), (3, 2)}
        editor._on_undo()
        assert editor.selection.cells == {(0, 0), (1, 0)}
        editor._on_redo()
        assert editor.selection.cells == {(2, 2), (3, 2)}


# ---------------------------------------------------------------------------
# Region tool (plan §8)
# ---------------------------------------------------------------------------


class TestRegionTool:
    def test_mode_switch(self, editor):
        editor._on_mode_changed("grid", "regions")
        assert editor.mode == "regions"
        assert isinstance(editor._active_tool, RegionTool)
        editor._on_mode_changed("regions", "grid")
        assert isinstance(editor._active_tool, SelectTool)

    def test_create_region(self, editor):
        editor._on_mode_changed("grid", "regions")
        editor.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(16, TOOLBAR_H + HEADER_H + 16)))
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=(100, TOOLBAR_H + HEADER_H + 100)))
        editor.handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=(100, TOOLBAR_H + HEADER_H + 100)))
        assert len(editor.doc.regions) == 1
        r = editor.doc.regions[0]
        assert r.x == 16 and r.y == 16 and r.w == 84 and r.h == 84

    def test_create_clamps_to_doc(self, editor):
        editor._on_mode_changed("grid", "regions")
        editor.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(16, TOOLBAR_H + HEADER_H + 16)))
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=(600, TOOLBAR_H + HEADER_H + 600)))
        editor.handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=(600, TOOLBAR_H + HEADER_H + 600)))
        r = editor.doc.regions[0]
        assert r.w <= 128 and r.h <= 128

    def test_min_size_uniform_in_screen_px(self, editor):
        editor._on_mode_changed("grid", "regions")
        for zoom, label in [(0.5, "out"), (4.0, "in")]:
            editor.camera.zoom = zoom
            # 4 screen px drag → 8/0.5=16 world px at 0.5x; 1 world px at 4x
            editor.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, TOOLBAR_H + HEADER_H + 100)))
            editor.handle_event(ev(pygame.MOUSEMOTION, pos=(104, TOOLBAR_H + HEADER_H + 104)))
            editor.handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=(104, TOOLBAR_H + HEADER_H + 104)))
            assert not editor.doc.regions, f"tiny drag at zoom {zoom} must be rejected"
            assert any("small" in n.text.lower() for n in editor._notifications.notifications)

    def test_create_works_at_extreme_zooms(self, editor):
        editor._on_mode_changed("grid", "regions")
        for zoom in (0.5, 4.0):
            editor.doc.regions.clear()
            editor.camera.zoom = zoom
            sx, sy = editor.camera.world_to_screen(10, 10)
            ex, ey = editor.camera.world_to_screen(90, 90)
            editor.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=(sx, sy)))
            editor.handle_event(ev(pygame.MOUSEMOTION, pos=(ex, ey)))
            editor.handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=(ex, ey)))
            assert len(editor.doc.regions) == 1
            r = editor.doc.regions[0]
            assert abs(r.w - 80) < 0.01 and abs(r.h - 80) < 0.01

    def test_move_region(self, editor):
        editor._on_mode_changed("grid", "regions")
        editor.doc.regions = [Region(id="a", rect=[10.0, 10.0, 40.0, 40.0])]
        editor._active_tool.selected_id = "a"
        p1 = editor.camera.world_to_screen(30, 30)
        p2 = editor.camera.world_to_screen(60, 60)
        editor.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=p1))
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=p2))
        editor.handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=p2))
        assert editor.doc.regions[0].rect == [40.0, 40.0, 40.0, 40.0]

    def test_move_clamps_to_doc(self, editor):
        editor._on_mode_changed("grid", "regions")
        editor.doc.regions = [Region(id="a", rect=[100.0, 100.0, 40.0, 40.0])]
        editor._active_tool.selected_id = "a"
        p1 = editor.camera.world_to_screen(120, 120)
        p2 = editor.camera.world_to_screen(500, 500)
        editor.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=p1))
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=p2))
        editor.handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=p2))
        r = editor.doc.regions[0]
        assert r.x + r.w <= 128 and r.y + r.h <= 128

    def test_resize_region(self, editor):
        editor._on_mode_changed("grid", "regions")
        editor.doc.regions = [Region(id="a", rect=[10.0, 10.0, 40.0, 40.0])]
        tool = editor._active_tool
        tool.selected_id = "a"
        # grab the BR handle: world (50,50) → screen
        p1 = editor.camera.world_to_screen(50, 50)
        p2 = editor.camera.world_to_screen(80, 70)
        editor.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=p1))
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=p2))
        editor.handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=p2))
        assert editor.doc.regions[0].rect == [10.0, 10.0, 70.0, 60.0]

    def test_handle_hit_constant_screen_px(self, editor):
        from plugins.sprite_editor.overlays import handle_at

        editor._on_mode_changed("grid", "regions")
        region = Region(id="a", rect=[10.0, 10.0, 40.0, 40.0])
        editor.doc.regions = [region]
        for zoom in (0.25, 1.0, 4.0):
            editor.camera.zoom = zoom
            sx, sy = editor.camera.world_to_screen(10, 10)
            sw = 40 * zoom
            sh = 40 * zoom
            rect = Rect(sx, sy, sw, sh)
            cx, cy = round(sx + sw), round(sy + sh)  # BR corner center (screen px)
            assert handle_at(rect, (cx, cy), 8) == "br", f"zoom {zoom} center"
            # ±3 px around the corner center still hits (8px handles).
            # At zoom 0.25 the 10px-wide rect makes corners overlap the
            # edge handles, so only test the full ring at zoom >= 1.
            offsets = [(0, 0), (3, 0), (-3, 0), (0, 3), (0, -3)] if zoom >= 1 else [(0, 0)]
            for dx, dy in offsets:
                assert handle_at(rect, (cx + dx, cy + dy), 8) == "br", f"zoom {zoom} d=({dx},{dy})"

    def test_resize_clamps_to_bounds(self, editor):
        editor._on_mode_changed("grid", "regions")
        editor.doc.regions = [Region(id="a", rect=[100.0, 100.0, 20.0, 20.0])]
        tool = editor._active_tool
        tool.selected_id = "a"
        p1 = editor.camera.world_to_screen(120, 120)
        p2 = editor.camera.world_to_screen(300, 200)
        editor.handle_event(ev(pygame.MOUSEBUTTONDOWN, button=1, pos=p1))
        editor.handle_event(ev(pygame.MOUSEMOTION, pos=p2))
        editor.handle_event(ev(pygame.MOUSEBUTTONUP, button=1, pos=p2))
        r = editor.doc.regions[0]
        assert r.x + r.w <= 128 and r.y + r.h <= 128

    def test_delete_selected_region(self, editor):
        editor._on_mode_changed("grid", "regions")
        editor.doc.regions = [Region(id="a", rect=[10.0, 10.0, 40.0, 40.0])]
        editor._active_tool.selected_id = "a"
        editor.handle_event(ev(pygame.KEYDOWN, key=pygame.K_DELETE))
        assert not editor.doc.regions

    def test_rename_region_f2(self, editor):
        editor._on_mode_changed("grid", "regions")
        editor.doc.regions = [Region(id="a", rect=[10.0, 10.0, 40.0, 40.0])]
        tool = editor._active_tool
        tool.selected_id = "a"
        tool.handle_event(ev(pygame.KEYDOWN, key=pygame.K_F2))
        assert tool._editing_id == "a"
        for ch in "hero":
            tool.handle_event(ev(pygame.KEYDOWN, key=getattr(pygame, "K_" + ch), unicode=ch))
        tool.handle_event(ev(pygame.KEYDOWN, key=pygame.K_RETURN))
        assert editor.doc.regions[0].name == "hero"

    def test_export_button_disabled_without_regions(self, editor):
        btn = editor._get_btn("export_all")
        assert btn is not None
        assert not btn.enabled
        editor.doc.regions = [Region(id="a", rect=[0.0, 0.0, 10.0, 10.0])]
        editor._update_button_states()
        assert btn.enabled


# ---------------------------------------------------------------------------
# View / chrome (plan §10)
# ---------------------------------------------------------------------------


class TestChrome:
    def test_toolbar_groups_and_separators(self, editor):
        tags = [getattr(b, "_tag", "") for b in editor._buttons]
        assert "open" in tags and "save" in tags
        assert "undo" in tags and "redo" in tags and "cut" in tags and "copy" in tags and "paste" in tags
        assert "flip_x" in tags and "flip_y" in tags and "scale" in tags
        assert "grid" in tags and "fit" in tags and "zoom_in" in tags and "zoom_out" in tags and "zoom_0" in tags
        assert "export_all" in tags
        assert len(editor._separators) >= 4
        # two rows: row-2 buttons sit below row-1 buttons, all inside the window
        row1_y = editor._get_btn("open").rect.y
        row2_y = editor._get_btn("export_all").rect.y
        assert row2_y > row1_y
        assert editor._get_btn("export_all").rect.right <= 1000
        assert editor._get_btn("stack").rect.right <= 1000

    def test_zoom_buttons(self, editor):
        editor._on_zoom_in()
        assert editor.camera.zoom > 1.0
        editor._on_zoom_out()
        assert editor.camera.zoom == pytest.approx(1.0)
        editor._on_zoom_in()
        editor._on_reset_zoom()
        assert editor.camera.zoom == pytest.approx(1.0)
        editor._on_fit()
        assert editor.camera.zoom > 1.0  # 128x128 in a 1000x632 viewport

    def test_zoom_label_updates(self, editor):
        editor._on_zoom_in()
        editor._update_button_states()
        assert editor._zoom_btn.text == f"{editor.camera.zoom * 100:.0f}%"

    def test_viewport_draw_does_not_mutate_doc(self, editor):
        from plugins.sprite_editor.document import Document
        from plugins.sprite_editor.viewport import Viewport

        doc = Document(editor.doc.surface.copy(), (32, 32))
        rev = doc.revision
        screen = pygame.Surface((1000, 700))
        viewport = Viewport(Rect(0, 42, 1000, 632), doc, editor.camera, editor.selection)
        viewport.draw(screen, editor._select_tool)
        assert doc.revision == rev
        assert pygame.image.tostring(doc.surface, "RGBA") == pygame.image.tostring(editor.doc.surface.copy(), "RGBA")

    def test_draw_reflects_in_place_mutation_immediately(self, editor):
        # regression: the sheet cache was keyed on (id, size, zoom) only, so
        # in-place moves/pastes kept blitting the stale pre-edit image
        click(editor, screen_for((0, 0)))
        drag(editor, screen_for((0, 0)), screen_for((2, 0)))
        assert pixel_at(editor.doc, 2, 0)[:3] == (100, 60, 200)

        editor.selection.replace([])  # drop the selection tint overlay
        editor._active_tool._hover_cell = None  # drop the hover tint overlay
        screen = pygame.Surface((1000, 700))
        editor.draw(screen)
        x, y = screen_for((2, 0))
        assert screen.get_at((x, y))[:3] == (100, 60, 200), "viewport must show moved tile"
        x0, y0 = screen_for((0, 0))
        assert screen.get_at((x0, y0))[:3] != (100, 60, 200), "origin cell must be cleared on screen"

    def test_grid_spans_full_content_area(self, editor):
        # regression: grid lines must cover the whole canvas like TileGrid,
        # not just the sheet bounds
        screen = pygame.Surface((1000, 700))
        editor.draw(screen)
        content_y = TOOLBAR_H + HEADER_H
        line_color = (120, 120, 120)  # COLORS.text_muted default theme
        # vertical line at world x=96 (col 3 edge), inside the sheet
        vx = round(editor.camera.world_to_screen(96, 0)[0])
        assert screen.get_at((vx, content_y + 100))[:3] == line_color
        # vertical line at world x=192 (col 6) — past the 128px sheet edge
        wx = round(editor.camera.world_to_screen(192, 0)[0])
        assert screen.get_at((wx, content_y + 100))[:3] == line_color
        # horizontal line at world y=96 (row 3), past the sheet edge (x=700)
        wy = round(editor.camera.world_to_screen(0, 96)[1])
        assert screen.get_at((700, wy))[:3] == line_color

    def test_canvas_never_bleeds_into_toolbar_when_panned(self, editor):
        from widgets.ui.theme import COLORS

        editor.camera.pan(0, -200)  # pan up: sheet would cover the header/toolbar
        screen = pygame.Surface((1000, 700))
        editor.draw(screen)
        # toolbar bg (x=60 is between buttons) and canvas-header strip stay theme-painted
        assert screen.get_at((60, 20))[:3] == COLORS.header[:3]
        assert screen.get_at((500, 90))[:3] == COLORS.header[:3]

    def test_status_bar_initial(self, editor):
        assert editor._status_bar.current.message == "Ready"

    def test_undo_redo_via_ctrl_keys(self, editor):
        click(editor, screen_for((0, 0)))
        editor.handle_event(ev(pygame.KEYDOWN, key=pygame.K_DELETE))
        assert editor.commands.can_undo
        pygame.key.set_mods(pygame.KMOD_CTRL)
        editor.handle_event(ev(pygame.KEYDOWN, key=pygame.K_z))
        pygame.key.set_mods(0)
        assert not editor.commands.can_undo
        assert pixel_at(editor.doc, 0, 0)[:3] == (100, 60, 200)
        pygame.key.set_mods(pygame.KMOD_CTRL)
        editor.handle_event(ev(pygame.KEYDOWN, key=pygame.K_y))
        pygame.key.set_mods(0)
        assert editor.commands.can_undo
        assert pixel_at(editor.doc, 0, 0) == (0, 0, 0, 0)

    def test_undo_redo_button_enabled_state(self, editor):
        undo_btn = editor._get_btn("undo")
        redo_btn = editor._get_btn("redo")
        assert not undo_btn.enabled and not redo_btn.enabled
        click(editor, screen_for((0, 0)))
        editor.handle_event(ev(pygame.KEYDOWN, key=pygame.K_DELETE))
        editor._update_button_states()
        assert undo_btn.enabled
        editor._on_undo()
        editor._update_button_states()
        assert redo_btn.enabled

    def test_status_is_action_not_config(self, editor):
        click(editor, screen_for((0, 0)))
        assert editor._status_bar.current.message.startswith("Selection")

    def test_mousewheel_routes_to_tool(self, editor):
        # regression: MOUSEWHEEL has no `pos`; it must still reach the tool
        z0 = editor.camera.zoom
        pygame.key.set_mods(pygame.KMOD_CTRL)
        editor.handle_event(ev(pygame.MOUSEWHEEL, x=0, y=1, flipped=False))
        pygame.key.set_mods(0)
        assert editor.camera.zoom > z0, "ctrl+wheel up must zoom in"

    def test_mousewheel_pan(self, editor):
        s0 = editor.camera.scroll_y
        editor.handle_event(ev(pygame.MOUSEWHEEL, x=0, y=1, flipped=False))
        assert editor.camera.scroll_y == s0 + 30, "plain wheel up pans down 30px"

    def test_mousewheel_horizontal_pan(self, editor):
        s0 = editor.camera.scroll_x
        editor.handle_event(ev(pygame.MOUSEWHEEL, x=1, y=0, flipped=False))
        assert editor.camera.scroll_x == s0 + 30, "horizontal wheel pans right 30px"

class TestStacking:
    """Multi-sheet load: natural sort order + vertical/horizontal stacking."""

    @staticmethod
    def _write_png(path: Path, color: tuple, w: int = 32, h: int = 16) -> None:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((*color, 255))
        pygame.image.save(surf, str(path))

    def _load(self, editor, tmp_path, colors):
        for name, color in colors:
            self._write_png(tmp_path / name, color)
        # deliberately shuffled — must come out naturally sorted
        editor._on_add_sheets([tmp_path / name for name, _ in reversed(colors)])

    def test_multi_sheet_load_sorted_naturally(self, tmp_path, editor):
        green, red, blue = (0, 200, 0), (200, 0, 0), (0, 0, 200)
        self._load(editor, tmp_path, [("frame_1.png", green), ("frame_2.png", red), ("frame_11.png", blue)])
        doc = editor.doc
        assert doc.surface.get_size() == (32, 48)  # vertical stack: max_w, sum_h
        assert doc.sheets == ["frame_1.png", "frame_2.png", "frame_11.png"]
        assert doc.surface.get_at((16, 8))[:3] == green
        assert doc.surface.get_at((16, 24))[:3] == red
        assert doc.surface.get_at((16, 40))[:3] == blue

    def test_stack_horizontal(self, tmp_path, editor):
        green, red, blue = (0, 200, 0), (200, 0, 0), (0, 0, 200)
        editor._toggle_stack()
        assert editor._get_btn("stack").text == "Stack H"
        self._load(editor, tmp_path, [("frame_1.png", green), ("frame_2.png", red), ("frame_11.png", blue)])
        doc = editor.doc
        assert doc.surface.get_size() == (96, 16)  # horizontal stack: sum_w, max_h
        assert doc.surface.get_at((16, 8))[:3] == green
        assert doc.surface.get_at((48, 8))[:3] == red
        assert doc.surface.get_at((80, 8))[:3] == blue

    def test_stack_toggle_roundtrip(self, editor):
        assert editor._stack_horizontal is False
        assert editor._get_btn("stack").text == "Stack V"
        editor._toggle_stack()
        assert editor._stack_horizontal is True
        assert editor._get_btn("stack").text == "Stack H"
        editor._toggle_stack()
        assert editor._stack_horizontal is False
        assert editor._get_btn("stack").text == "Stack V"
