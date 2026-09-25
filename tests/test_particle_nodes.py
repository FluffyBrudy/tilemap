"""Unit tests for particle nodes: viewer integration, sidecar tolerance."""

import json
from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest
from pygame import Rect

from node_manager import NodeManager
from nodes import Node, NodeRect
from plugins.particle_editor.models import normalize_config
from plugins.particle_editor.presets import get_preset_config
from utils.font_manager import FontWeight, font_manager
from widgets.ui.node_editor import NodeEditor
from widgets.ui.theme import FONTS
from widgets.ui.toolbar import Toolbar

SRC = Path(__file__).parent.parent / "src"


def make_emitter(name="Emitter 1", properties=None, node_id="emit-1"):
    return Node(
        node_id=node_id,
        name=name,
        node_type="particle_emitter",
        area=NodeRect(x=0, y=0, w=64, h=64),
        layer_name="Objects",
        properties=dict(
            properties if properties is not None else get_preset_config("Campfire")
        ),
    )


class FakeScreen:
    def get_width(self):
        return 1280

    def get_height(self):
        return 800


class FakeGrid:
    def __init__(self):
        self.reset_calls = []

    def _node_to_screen(self, x, y):
        return (x, y)

    def _node_screen_size(self, w, h):
        return (w, h)

    def reset_particle_preview(self, node_id, config):
        self.reset_calls.append((node_id, dict(config)))


class FakeNotifications:
    def __init__(self):
        self.messages = []

    def notify(self, text, **kwargs):
        self.messages.append(text)


class FakeSuggestions:
    def __init__(self):
        self.refreshes = 0

    def refresh(self, editor):
        self.refreshes += 1


class FakeTilemap:
    def __init__(self):
        self.history = []
        self.render_scale = 1

    def capture_history(self, description=""):
        self.history.append(description)


class FakeEditor:
    node_editing_mode = True
    show_particles = True

    def __init__(self, manager, data_root):
        self.node_manager = manager
        self.tile_grid_widget = FakeGrid()
        self.screen = FakeScreen()
        self.tilemap = FakeTilemap()
        self.data_root = Path(data_root)
        self.notifications = FakeNotifications()
        self.suggestion_registry = FakeSuggestions()
        self.launched = []
        self.reload_calls = []

    def launch_particle_editor(self, node=None):
        self.launched.append(node.node_id if node else None)

    def reload_particle_from_export(self, node):
        self.reload_calls.append(node.node_id)
        return True


def make_viewer(manager, data_root):
    ed = FakeEditor(manager, data_root)
    viewer = NodeEditor.__new__(NodeEditor)
    viewer.editor = ed
    viewer.rect = Rect(0, 310, 260, 230)
    viewer._dock_x, viewer._dock_y = 0, 310
    viewer.font = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)
    viewer.font_bold = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.BOLD)
    viewer.font_input = font_manager.get_font(FONTS.name, 11, FontWeight.REGULAR)
    viewer._editing_field = None
    viewer._input_text = ""
    viewer.text_selected = False
    viewer._is_dragging = False
    viewer._drag_offset = (0, 0)
    viewer._last_node_id = None
    viewer._preset_dd = None
    viewer._preset_owner = None
    viewer._particle_lib = None
    viewer._particle_lib_key = None
    viewer._is_particle = False
    return viewer, ed


def _active_manager(node):
    manager = NodeManager.__new__(NodeManager)
    manager.nodes = {}
    manager.active_node_id = None
    manager.active_group_name = None
    manager.groups = []
    manager.nodes[node.node_id] = node
    manager.active_node_id = node.node_id
    return manager


def test_preset_apply_updates_preview_and_preserves_hidden(tmp_path):
    node = make_emitter()
    node.properties["_hidden"] = True
    viewer, ed = make_viewer(_active_manager(node), tmp_path)

    assert viewer._apply_library_preset(node, "Snow") is True
    assert node.properties == {**get_preset_config("Snow"), "_hidden": True}
    assert (node.node_id, get_preset_config("Snow")) in [
        (nid, cfg) for nid, cfg in ed.tile_grid_widget.reset_calls
    ]
    assert ed.suggestion_registry.refreshes == 1
    assert "Apply Particle Preset" in ed.tilemap.history
    assert viewer._apply_library_preset(node, "Nope") is False


def test_hidden_flag_survives_normalization_and_sidecar():
    node = make_emitter()
    node.properties["_hidden"] = True
    normalized, _ = normalize_config(dict(node.properties))
    assert normalized["_hidden"] is True
    payload = json.loads(json.dumps(node.to_dict()))
    assert payload["properties"]["_hidden"] is True


def test_hidden_flag_stripped_from_saved_sidecar_bytes():
    from node_manager import _save_dict

    node = make_emitter()
    node.properties["_hidden"] = True
    saved = json.loads(json.dumps(_save_dict(node)))
    assert "_hidden" not in saved["properties"]
    # Game data survives; in-memory view state untouched.
    assert saved["properties"]["mode"] == node.properties["mode"]
    assert node.properties["_hidden"] is True


def test_reload_export_ok_and_missing(tmp_path):
    from editor import Editor

    node = make_emitter()
    export = tmp_path / "emit-1.node.json"
    export.write_text(
        json.dumps({"name": node.name, "config": get_preset_config("Snow")}),
        encoding="utf-8",
    )
    grid = FakeGrid()
    fake = SimpleNamespace(
        _particle_exports={node.node_id: export},
        notifications=FakeNotifications(),
        tile_grid_widget=grid,
        suggestion_registry=FakeSuggestions(),
        tilemap=FakeTilemap(),
    )
    assert Editor.reload_particle_from_export(fake, node) is True
    assert node.properties == get_preset_config("Snow")
    assert grid.reset_calls and grid.reset_calls[0][0] == node.node_id

    lonely = SimpleNamespace(
        _particle_exports={},
        notifications=FakeNotifications(),
        tile_grid_widget=FakeGrid(),
        suggestion_registry=FakeSuggestions(),
        tilemap=FakeTilemap(),
    )
    assert Editor.reload_particle_from_export(lonely, make_emitter()) is False
    assert any("Save first" in m for m in lonely.notifications.messages)


def test_build_particle_editor_args():
    from editor import build_particle_editor_args

    assert build_particle_editor_args(None, "/data") == ["--data-root", "/data"]
    node = make_emitter()
    args = build_particle_editor_args(node, "/data", "/data/x.node.json")
    assert args == [
        "--data-root",
        "/data",
        "--import-node",
        "/data/x.node.json",
        "--export-node",
        "/data/x.node.json",
    ]


def test_tile_grid_tracks_all_visible_emitters(tmp_path):
    from widgets.tile_grid import TileGrid

    grid = TileGrid.__new__(TileGrid)
    grid._particle_previews = {}
    grid._last_preview_time = 0.0
    nodes = {f"e{i}": make_emitter(name=f"E{i}", node_id=f"e{i}") for i in range(3)}
    manager = SimpleNamespace(nodes=nodes)
    tilemap = SimpleNamespace(render_scale=1)
    editor = SimpleNamespace(
        node_manager=manager,
        node_editing_mode=True,
        show_particles=True,
        tilemap=tilemap,
    )
    grid.editor = editor

    grid._update_particle_previews()
    grid._update_particle_previews()
    assert set(grid._particle_previews) == {"e0", "e1", "e2"}

    nodes["e1"].properties["_hidden"] = True
    grid._update_particle_previews()
    assert set(grid._particle_previews) == {"e0", "e2"}

    editor.show_particles = False
    grid._update_particle_previews()
    assert grid._particle_previews == {}


def test_editor_chrome_registers_particle_actions():
    editor_src = (SRC / "editor.py").read_text()
    node_src = (SRC / "widgets" / "ui" / "node_editor.py").read_text()
    assert "particle_config_dialog" not in editor_src
    assert "ParticleConfigDialog" not in node_src
    assert "self.editor.particle_config_dialog" not in node_src
    assert "self.particle_config_dialog" not in editor_src

    menubar_src = (SRC / "widgets" / "ui" / "menubar.py").read_text()
    assert "Particle Editor" in menubar_src
    assert "Particle Previews" in menubar_src

    from utils.icon_manager import icon_manager

    assert icon_manager.has_icon("sparkle")

    fake = SimpleNamespace(
        tool_manager=SimpleNamespace(is_active=lambda kind: False),
        tile_grid_widget=SimpleNamespace(show_grid=True),
        autotile_mode=False,
        node_editing_mode=False,
        show_particles=True,
        dice_brush=False,
    )
    toolbar = Toolbar.__new__(Toolbar)
    toolbar.editor = fake
    toolbar.rect = Rect(0, 30, 800, 35)
    toolbar.btn_size = 28
    toolbar.gap = 6
    toolbar.sep_w = 10
    toolbar.pad = 8
    toolbar._buttons = []
    toolbar._separator_centers = []
    toolbar._build_tool_buttons(
        toolbar.rect.x + toolbar.pad,
        toolbar.rect.y + (toolbar.rect.height - toolbar.btn_size) // 2,
        toolbar.btn_size,
    )
    keys = [getattr(b, "tool_key", b.icon_key) for b in toolbar._buttons]
    assert "particles" in keys

    fake.toggle_calls = []
    fake.toggle_show_particles = lambda: (
        setattr(fake, "show_particles", not fake.show_particles),
        fake.toggle_calls.append(1),
    )
    toolbar._on_tool_click("particles")
    assert fake.toggle_calls == [1]
    assert fake.show_particles is False
    toolbar._update_active_states()
    states = {getattr(b, "tool_key", b.icon_key): b.active for b in toolbar._buttons}
    assert states["particles"] is False
