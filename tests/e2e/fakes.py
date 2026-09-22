"""Fake editor harness shared by e2e flow tests.

Mirrors production wiring closely enough that journeys exercise real
dispatch paths. Unit tests must not import this: if a unit test needs
a fake, that fake belongs in its own file.
"""

from pathlib import Path

from nodes import Node, NodeRect


def make_node(node_id="node-1", node_type="area", properties=None):
    return Node(
        node_id=node_id,
        name=node_id,
        node_type=node_type,
        area=NodeRect(x=0, y=0, w=64, h=64),
        layer_name="Objects",
        properties=dict(properties or {}),
    )


def make_emitter(name="Emitter 1", properties=None, node_id="emit-1"):
    from plugins.particle_editor.presets import get_preset_config

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
    """NodeEditor bound to a fake editor harness (mirrors production wiring)."""
    from pygame import Rect

    from utils.font_manager import FontWeight, font_manager
    from widgets.ui.node_editor import NodeEditor
    from widgets.ui.theme import FONTS

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
