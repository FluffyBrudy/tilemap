"""
Tests for MAP_OBJECT property context (placed objects on object layers).

Covers:
- The property editor targets the clicked object, not its tileset
- Editing one of two objects sharing a tileset affects only that object
- Saving writes per-object properties into the object dict
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import sys
from pathlib import Path

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.context_dispatch import (
    ContextKind,
    PropertyContext,
    PropertyContextDispatcher,
)
from utils.property_suggestions import PropertySuggestionRegistry
from widgets.tile_selector import TileSelector, TilesetData


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


class FakeEditor:
    def __init__(self):
        self.width = 800
        self.height = 600
        self.context_dispatch = PropertyContextDispatcher()
        self.suggestion_registry = PropertySuggestionRegistry()
        self.tileset_widget = None
        self.tilemap = None
        self.node_manager = None


def _make_selector() -> TileSelector:
    editor = FakeEditor()
    return TileSelector(editor, x=0, y=0, w=400, h=600)


def _make_object(obj_id: int) -> dict:
    return {
        "area": {"x": 0, "y": 0, "w": 64, "h": 64},
        "ttype": 0,
        "tileset_type": "object",
        "variant": 0,
    }


def _make_shared_tileset(selector: TileSelector) -> TilesetData:
    surf = pygame.Surface((64, 64))
    surf.fill((100, 100, 200))
    ts = TilesetData("shared_ts", Path("shared.png"), surf, tileset_type="object")
    selector.tilesets.append(ts)
    selector.tileset_map[0] = ts
    return ts


class TestMapObjectContext:
    def test_opener_targets_clicked_object(self):
        selector = _make_selector()
        ts = _make_shared_tileset(selector)
        obj2 = _make_object(2)
        ctx = PropertyContext(
            ContextKind.MAP_OBJECT,
            obj2,
            {"obj_id": 2, "layer_name": "Objects", "tileset_name": ts.name},
        )

        selector.editor.context_dispatch.open(ctx)

        pe = selector.editor.property_editor
        assert pe is not None
        assert pe.context.target is obj2
        assert "#2" in pe.title
        assert ts.name in pe.title

    def test_save_affects_only_clicked_object(self):
        selector = _make_selector()
        _make_shared_tileset(selector)
        obj1 = _make_object(1)
        obj2 = _make_object(2)
        ctx1 = PropertyContext(
            ContextKind.MAP_OBJECT, obj1, {"obj_id": 1, "layer_name": "Objects"}
        )

        selector.editor.context_dispatch.open(ctx1)
        pe = selector.editor.property_editor
        pe.properties["hp"] = 5
        pe._commit_save()

        assert obj1["properties"] == {"hp": 5}
        assert "properties" not in obj2

    def test_save_via_dispatch_writes_only_target_object(self):
        selector = _make_selector()
        _make_shared_tileset(selector)
        obj1 = _make_object(1)
        obj2 = _make_object(2)
        ctx2 = PropertyContext(
            ContextKind.MAP_OBJECT, obj2, {"obj_id": 2, "layer_name": "Objects"}
        )

        selector.editor.context_dispatch.save(ctx2, {"color": "red"})

        assert obj2["properties"] == {"color": "red"}
        assert "properties" not in obj1
        assert selector.tilesets[0].properties == {}
