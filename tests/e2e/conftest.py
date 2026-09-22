"""E2E fixtures: fake editors, node factories, drivers.

Function scope everywhere: shared mutable fixtures cause order-dependent
flakes. Anything used by two or more flow files lives here; anything
used once stays in its test file.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from .fakes import make_emitter, make_node, make_viewer


@pytest.fixture
def driver(tmp_path, monkeypatch):
    from .harness import ParticleEditorDriver

    return ParticleEditorDriver.blank(tmp_path, monkeypatch)


@pytest.fixture
def viewer_driver(tmp_path, monkeypatch):
    from node_manager import NodeManager

    from .harness import NodeViewerDriver

    manager = NodeManager.__new__(NodeManager)
    manager.nodes = {}
    manager.active_node_id = None
    manager.active_group_name = None
    manager.groups = []
    node = make_emitter()
    manager.nodes[node.node_id] = node
    manager.active_node_id = node.node_id
    viewer, ed = make_viewer(manager, tmp_path)
    return NodeViewerDriver(viewer, ed, monkeypatch)


__all__ = ["make_emitter", "make_node", "make_viewer", "driver", "viewer_driver"]
