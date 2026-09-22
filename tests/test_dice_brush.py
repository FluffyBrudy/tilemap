"""Tests for the dice brush (random tiles from multi-tile selection)."""

import sys
from pathlib import Path

import pygame

from layers import Layer
from widgets.autotiler import AutotileGroup


class FakeNotifications:
    def __init__(self):
        self.messages = []

    def notify(self, text, **kwargs):
        self.messages.append(text)

    def success(self, text, **kwargs):
        self.messages.append(text)


class FakeAutotiler:
    def __init__(self):
        self.groups = []
        self.selected_group_idx = -1
        self.rules = []

    @property
    def variant_to_group(self):
        return {}


class FakeTilemap:
    offset = (0, 0)
    map_size = (10, 10)
    tile_size = (32, 32)


class FakeEditor:
    node_editing_mode = False
    show_nodes = False

    def __init__(self, dice=False):
        self.autotile_mode = False
        self.autotiler = FakeAutotiler()
        self.tilemap = FakeTilemap()
        self.notifications = FakeNotifications()
        self.dice_brush = dice

    def toggle_dice_brush(self):
        from editor import Editor

        return Editor.toggle_dice_brush(self)


class FakeTilesetData:
    tile_properties = {}


def make_grid(editor):
    from widgets.tile_grid import TileGrid

    g = TileGrid.__new__(TileGrid)
    g.editor = editor
    g.hover_cell = (2, 2)
    return g


def paint(editor, src_rect, w=4, h=1):
    from widgets.tile_grid import TileGrid  # noqa: F401 (import sanity)

    grid = make_grid(editor)
    layer = Layer("t")
    # 8-wide sheet; selection rect in pixels on 32px tiles.
    grid._place_tile_grid(layer, 0, FakeTilesetData(), src_rect, 32, 32, 8)
    return layer


class TestDiceOff:
    def test_positional_placement_unchanged(self):
        ed = FakeEditor(dice=False)
        # 2x1 selection at sheet (3,0): variants 3,4 placed positionally.
        layer = paint(ed, (3 * 32, 0, 2 * 32, 32))
        assert layer.tiles[(2, 2)]["variant"] == 3
        assert layer.tiles[(3, 2)]["variant"] == 4

    def test_missing_flag_defaults_off(self):
        ed = FakeEditor()
        del ed.dice_brush
        layer = paint(ed, (3 * 32, 0, 2 * 32, 32))
        assert layer.tiles[(2, 2)]["variant"] == 3


class TestDiceOn:
    def test_plots_single_random_tile(self):
        ed = FakeEditor(dice=True)
        # 4x1 selection at sheet row 0: exactly one tile plotted,
        # variant drawn from {0,1,2,3}.
        layer = paint(ed, (0, 0, 4 * 32, 32))
        assert len(layer.tiles) == 1
        assert layer.tiles[(2, 2)]["variant"] in (0, 1, 2, 3)

    def test_spread_over_many_cells(self):
        ed = FakeEditor(dice=True)
        from widgets.tile_grid import TileGrid

        grid = TileGrid.__new__(TileGrid)
        grid.editor = ed
        layer = Layer("t")
        # paint a 4x4 block stroke cell by cell across the map
        for i in range(16):
            grid.hover_cell = (i % 10, i // 10)
            grid._place_tile_grid(layer, 0, FakeTilesetData(),
                                  (0, 0, 4 * 32, 32), 32, 32, 8)
        assert len(layer.tiles) == 16
        got = {t["variant"] for t in layer.tiles.values()}
        assert got <= {0, 1, 2, 3}
        assert len(got) > 1

    def test_single_tile_selection_unchanged(self):
        ed = FakeEditor(dice=True)
        layer = paint(ed, (5 * 32, 0, 32, 32))
        assert len(layer.tiles) == 1
        assert layer.tiles[(2, 2)]["variant"] == 5


class TestDiceToggle:
    def test_toggle_flips_and_notifies(self):
        ed = FakeEditor(dice=False)
        ed.toggle_dice_brush()
        assert ed.dice_brush is True
        assert any("Dice Brush" in m for m in ed.notifications.messages)
        ed.toggle_dice_brush()
        assert ed.dice_brush is False

    def test_toggle_missing_flag(self):
        ed = FakeEditor()
        del ed.dice_brush
        ed.toggle_dice_brush()
        assert ed.dice_brush is True


class TestDicePool:
    def _grid(self, dice=True):
        from widgets.tile_grid import TileGrid

        g = TileGrid.__new__(TileGrid)
        g.editor = FakeEditor(dice=dice)
        return g

    def test_multi_selection_pool(self):
        g = self._grid()
        pool = g._dice_pool((0, 0, 4 * 32, 32), 32, 32, 8)
        assert pool == [0, 1, 2, 3]

    def test_single_tile_no_pool(self):
        g = self._grid()
        assert g._dice_pool((5 * 32, 0, 32, 32), 32, 32, 8) is None

    def test_flag_off_no_pool(self):
        g = self._grid(dice=False)
        assert g._dice_pool((0, 0, 4 * 32, 32), 32, 32, 8) is None


class TestPreviewGating:
    def _rig(self, dice=False):
        import pygame
        from pygame import Rect

        from widgets.tile_grid import TileGrid
        from widgets.ui.tool_manager import ToolManager

        pygame.init()
        pygame.display.set_mode((1, 1))
        ed = FakeEditor(dice=dice)
        ed.tool_manager = ToolManager()
        layer = Layer("t")
        ed.tilemap = FakeTilemap()
        ed.tilemap.render_scale = 1.0
        ed.tilemap.layer_manager = type(
            "M", (), {"get_active_layer": lambda self: layer})()
        g = TileGrid.__new__(TileGrid)
        g.editor = ed
        g.hover_cell = (2, 2)
        g.rect = Rect(0, 0, 400, 400)
        g.scroll_x = 0
        g.scroll_y = 0
        g.zoom_level = 1.0
        g.is_moving = False
        g.is_panning = False
        g.calls = []
        return g

    def test_select_tool_shows_no_brush(self):
        from widgets.ui.tool_manager import ToolKind

        g = self._rig()
        g.editor.tool_manager.toggle(ToolKind.SELECT)
        g.get_selected_brush = lambda: (_ for _ in ()).throw(
            AssertionError("brush must not resolve under select"))
        import pygame

        g._draw_preview(pygame.Surface((400, 400)))

    def test_pan_tool_shows_no_brush(self):
        from widgets.ui.tool_manager import ToolKind

        g = self._rig()
        g.editor.tool_manager.toggle(ToolKind.PAN)
        g.get_selected_brush = lambda: (_ for _ in ()).throw(
            AssertionError("brush must not resolve under pan"))
        import pygame

        g._draw_preview(pygame.Surface((400, 400)))

    def test_dice_routes_to_single_preview(self):
        import pygame

        g = self._rig(dice=True)
        seen = {}

        class FakeTilesetData:
            tile_properties = {}
            surface = pygame.Surface((8 * 32, 32))

        def fake_brush():
            return 0, FakeTilesetData(), (0, 0, 4 * 32, 32)

        g.get_selected_brush = fake_brush
        g._draw_dice_preview = lambda *a, **k: seen.setdefault("dice", True)
        g._draw_preview(pygame.Surface((400, 400)))
        assert seen.get("dice") is True

    def test_dice_preview_cycles_within_pool(self, monkeypatch):
        import pygame

        g = self._rig(dice=True)
        g._dice_preview_variant = None
        g._dice_preview_at = 0
        monkeypatch.setattr(pygame.mouse, "get_pressed", lambda: (1, 0, 0))
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (10, 10))

        class FakeTilesetData:
            surface = pygame.Surface((8 * 32, 32))

        screen = pygame.Surface((400, 400))
        g._draw_dice_preview(screen, FakeTilesetData(), 32, 32, 32, 32,
                             [0, 1, 2, 3], 8)
        assert g._dice_preview_variant in (0, 1, 2, 3)


class TestBrushFlip:
    def test_defaults_off_on_legacy_grids(self):
        ed = FakeEditor()
        layer = paint(ed, (0, 0, 32, 32))
        assert layer.tiles[(2, 2)]["flip_h"] is False
        assert layer.tiles[(2, 2)]["flip_v"] is False

    def test_pending_flip_stamps(self):
        from widgets.tile_grid import TileGrid

        ed = FakeEditor()
        grid = make_grid(ed)
        grid.brush_flip_h = True
        grid.brush_flip_v = True
        layer = Layer("t")
        grid._place_tile_grid(layer, 0, FakeTilesetData(), (0, 0, 32, 32), 32, 32, 8)
        assert layer.tiles[(2, 2)]["flip_h"] is True
        assert layer.tiles[(2, 2)]["flip_v"] is True
        assert layer.tiles[(2, 2)]["variant"] == 0

    def test_toggle_no_selection_flips_brush(self):
        from widgets.tile_grid import TileGrid

        ed = FakeEditor()
        grid = make_grid(ed)
        grid.toggle_brush_flip("h")
        assert grid.brush_flip_h is True
        assert getattr(grid, "brush_flip_v", False) is False
        assert any("Flip H" in m for m in ed.notifications.messages)
        grid.toggle_brush_flip("v")
        assert grid.brush_flip_v is True

    def test_flip_selected_placed_tiles(self):
        from widgets.tile_grid import TileGrid

        ed = FakeEditor()
        layer = Layer("t")
        layer.tiles[(2, 2)] = {"pos": (2, 2), "ttype": 0, "variant": 3,
                               "flip_h": False, "flip_v": False}
        layer.tiles[(3, 2)] = {"pos": (3, 2), "ttype": 0, "variant": 4,
                               "flip_h": False, "flip_v": False,
                               "properties": {"solid": True}}

        class FakeManager:
            def get_active_layer(self):
                return layer

        ed.tilemap.layer_manager = FakeManager()
        ed.tilemap.capture_history = lambda desc: None
        grid = make_grid(ed)
        grid.selection_rect = (2, 2, 3, 2)
        grid.invalidate_bounds_cache = lambda: None

        grid.toggle_brush_flip("h")
        # arrangement mirrors AND bits toggle: variant 3 moves to (3, 2)
        assert layer.tiles[(3, 2)]["variant"] == 3
        assert layer.tiles[(3, 2)]["flip_h"] is True
        assert layer.tiles[(2, 2)]["variant"] == 4
        assert layer.tiles[(2, 2)]["flip_h"] is True
        assert layer.tiles[(2, 2)]["pos"] == (2, 2)
        assert layer.tiles[(2, 2)]["properties"] == {"solid": True}
        assert grid.selection_rect == (2, 2, 3, 2)
        assert getattr(grid, "brush_flip_h", False) is False

    def test_flip_selected_vertical(self):
        from widgets.tile_grid import TileGrid

        ed = FakeEditor()
        layer = Layer("t")
        layer.tiles[(2, 2)] = {"pos": (2, 2), "ttype": 0, "variant": 3,
                               "flip_h": False, "flip_v": False}
        layer.tiles[(2, 3)] = {"pos": (2, 3), "ttype": 0, "variant": 4,
                               "flip_h": False, "flip_v": False}

        class FakeManager:
            def get_active_layer(self):
                return layer

        ed.tilemap.layer_manager = FakeManager()
        ed.tilemap.capture_history = lambda desc: None
        grid = make_grid(ed)
        grid.selection_rect = (2, 2, 2, 3)
        grid.invalidate_bounds_cache = lambda: None

        grid.toggle_brush_flip("v")
        assert layer.tiles[(2, 2)]["variant"] == 4
        assert layer.tiles[(2, 3)]["variant"] == 3
        assert layer.tiles[(2, 2)]["flip_v"] is True

    def test_double_flip_is_identity(self):
        from widgets.tile_grid import TileGrid

        ed = FakeEditor()
        layer = Layer("t")
        before = {(2, 2): {"pos": (2, 2), "ttype": 0, "variant": 3,
                           "flip_h": False, "flip_v": True},
                  (3, 2): {"pos": (3, 2), "ttype": 0, "variant": 4,
                           "flip_h": True, "flip_v": False}}
        for pos, tile in before.items():
            layer.tiles[pos] = dict(tile)

        class FakeManager:
            def get_active_layer(self):
                return layer

        ed.tilemap.layer_manager = FakeManager()
        ed.tilemap.capture_history = lambda desc: None
        grid = make_grid(ed)
        grid.selection_rect = (2, 2, 3, 2)
        grid.invalidate_bounds_cache = lambda: None

        grid.toggle_brush_flip("h")
        grid.toggle_brush_flip("h")
        assert layer.tiles == before

    def test_flip_sparse_box_moves_content(self):
        from widgets.tile_grid import TileGrid

        ed = FakeEditor()
        layer = Layer("t")
        layer.tiles[(2, 2)] = {"pos": (2, 2), "ttype": 0, "variant": 9,
                               "flip_h": False, "flip_v": False}

        class FakeManager:
            def get_active_layer(self):
                return layer

        ed.tilemap.layer_manager = FakeManager()
        ed.tilemap.capture_history = lambda desc: None
        grid = make_grid(ed)
        grid.selection_rect = (2, 2, 3, 3)
        grid.invalidate_bounds_cache = lambda: None

        grid.toggle_brush_flip("h")
        assert (2, 2) not in layer.tiles
        assert layer.tiles[(3, 2)]["variant"] == 9
        assert layer.tiles[(3, 2)]["flip_h"] is True

    def test_refused_selection_does_not_toggle_brush(self):
        from widgets.tile_grid import TileGrid

        ed = FakeEditor()
        layer = Layer("o", "object")
        layer.objects[1] = {"area": {"x": 0, "y": 0, "w": 32, "h": 32},
                            "ttype": 0, "tileset_type": "tile", "variant": 0}

        class FakeManager:
            def get_active_layer(self):
                return layer

        ed.tilemap.layer_manager = FakeManager()
        grid = make_grid(ed)
        grid.selection_rect = (0, 0, 1, 1)
        grid.invalidate_bounds_cache = lambda: None

        grid.toggle_brush_flip("h")
        assert getattr(grid, "brush_flip_h", False) is False
        assert any("active tile layer" in m for m in ed.notifications.messages)

    def test_flip_locked_layer_refused(self):
        from widgets.tile_grid import TileGrid

        ed = FakeEditor()
        layer = Layer("t")
        layer.locked = True
        layer.tiles[(2, 2)] = {"pos": (2, 2), "ttype": 0, "variant": 3,
                               "flip_h": False, "flip_v": False}

        class FakeManager:
            def get_active_layer(self):
                return layer

        ed.tilemap.layer_manager = FakeManager()
        grid = make_grid(ed)
        grid.selection_rect = (2, 2, 2, 2)
        grid.invalidate_bounds_cache = lambda: None

        assert grid._flip_selected_tiles("h") is False
        assert layer.tiles[(2, 2)]["flip_h"] is False

    def test_flip_selected_no_selection_returns_false(self):
        from widgets.tile_grid import TileGrid

        grid = make_grid(FakeEditor())
        assert grid._flip_selected_tiles("h") is False

    def test_tile_flip_flags_none_safe(self):
        from widgets.tile_grid import TileGrid

        assert TileGrid._tile_flip_flags({}) == (False, False)
        assert TileGrid._tile_flip_flags({"flip_h": None, "flip_v": 1}) == (False, True)

    def test_flipped_tile_mirrors_pixels(self):
        from pygame import Rect

        from widgets.tile_grid import TileGrid

        grid = make_grid(FakeEditor())
        grid._tile_scale_cache = {}
        surf = pygame.Surface((64, 32), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        surf.fill((255, 0, 0, 255), (0, 0, 4, 32))
        out = grid._flipped_tile(surf, Rect(0, 0, 32, 32), True, False)
        assert out is not None
        assert out.get_at((31, 5))[:3] == (255, 0, 0)
        assert out.get_at((0, 5))[:3] == (0, 0, 0)
        assert grid._flipped_tile(surf, Rect(100, 100, 32, 32), True, False) is None
