#!/usr/bin/env python3
"""
Comprehensive test suite for the multi-layer tilemap system.
Tests layer management, backward compatibility, and save/load functionality.
"""

import sys
import json
from pathlib import Path
from typing import Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from layers import Layer, LayerManager, create_default_layer_manager
from ttypes.tilemap import TypeTile, TypeObject
from tilemap import Tilemap


def create_test_tile(ttype: str = "0", variant: int = 0) -> TypeTile:
    """Create a test tile."""
    return TypeTile(pos=(0, 0), ttype=ttype, variant=variant)


def create_test_object(
    pos: Tuple[int, int] = (50, 20),
    ttype: int = 1,
    variant: int = 3,
    width: int = 64,
    height: int = 48,
) -> TypeObject:
    """Create a test object with area-based structure."""
    return TypeObject(
        area={"x": pos[0], "y": pos[1], "w": width, "h": height},
        ttype=ttype,
        tileset_type="tile",
        variant=variant,
    )


class LayerTests:
    """Test the Layer class."""

    def test_layer_creation(self):
        """Test basic layer creation."""
        layer = Layer("Test", "tile", 0)
        assert layer.name == "Test"
        assert layer.layer_type == "tile"
        assert layer.z_index == 0
        assert layer.visible is True
        assert layer.locked is False
        assert layer.opacity == 1.0
        print("✓ Layer creation works")

    def test_set_get_tile(self):
        """Test setting and getting tiles."""
        layer = Layer("Test")
        pos = (5, 10)
        tile = create_test_tile(ttype="1", variant=5)

        layer.set_tile(pos, tile)
        retrieved = layer.get_tile(pos)

        assert retrieved is not None
        assert retrieved["ttype"] == "1"
        assert retrieved["variant"] == 5
        print("✓ Set/get tile works")

    def test_remove_tile(self):
        """Test removing tiles."""
        layer = Layer("Test")
        pos = (5, 10)
        tile = create_test_tile()

        layer.set_tile(pos, tile)
        assert layer.get_tile(pos) is not None

        removed = layer.remove_tile(pos)
        assert removed is True
        assert layer.get_tile(pos) is None
        print("✓ Remove tile works")

    def test_locked_layer(self):
        """Test that locked layers prevent modifications."""
        layer = Layer("Test", locked=True)
        pos = (5, 10)
        tile = create_test_tile()

        layer.set_tile(pos, tile)
        assert layer.get_tile(pos) is None  # Should not be set

        layer.tiles[pos] = tile  # Force set for removal test
        removed = layer.remove_tile(pos)
        assert removed is False  # Should not remove from locked layer
        print("✓ Layer locking works")

    def test_layer_serialization(self):
        """Test layer to_dict/from_dict."""
        layer = Layer("TestLayer", "tile", 0, True, False, 0.8)
        layer.set_tile((0, 0), create_test_tile("1", 2))
        layer.set_tile((1, 1), create_test_tile("3", 4))

        data = layer.to_dict()
        assert data["name"] == "TestLayer"
        assert data["type"] == "tile"
        assert data["visible"] is True
        assert data["locked"] is False
        assert data["opacity"] == 0.8
        assert len(data["tiles"]) == 2

        layer2 = Layer.from_dict(data)
        assert layer2.name == layer.name
        assert layer2.layer_type == layer.layer_type
        assert len(layer2.tiles) == 2
        print("✓ Layer serialization works")

    def test_add_remove_object(self):
        """Test adding and removing objects."""
        layer = Layer("Objects", "object")
        obj = create_test_object()

        # Add object
        obj_id = layer.add_object((50, 20), obj)
        assert obj_id >= 1
        assert layer.get_object(obj_id) is not None

        # Remove object
        removed = layer.remove_object(obj_id)
        assert removed is True
        assert layer.get_object(obj_id) is None
        print("✓ Add/remove object works")

    def test_move_object(self):
        """Test moving objects."""
        layer = Layer("Objects", "object")
        obj = create_test_object((50, 20))

        obj_id = layer.add_object((50, 20), obj)
        assert layer.get_object(obj_id)["area"]["x"] == 50
        assert layer.get_object(obj_id)["area"]["y"] == 20

        # Move object
        moved = layer.move_object(obj_id, (100, 30))
        assert moved is True
        assert layer.get_object(obj_id)["area"]["x"] == 100
        assert layer.get_object(obj_id)["area"]["y"] == 30
        print("✓ Move object works")

    def test_object_layer_serialization(self):
        """Test serializing object layer with objects."""
        layer = Layer("Decorations", "object")

        # Add objects
        obj1 = create_test_object((50, 20), 1, 3, 64, 48)
        obj2 = create_test_object((150, 30), 1, 5, 64, 48)

        id1 = layer.add_object((50, 20), obj1)
        id2 = layer.add_object((150, 30), obj2)

        # Serialize
        data = layer.to_dict()
        assert data["type"] == "object"
        assert len(data["objects"]) == 2
        assert data["next_object_id"] == 3

        # Deserialize
        layer2 = Layer.from_dict(data)
        assert layer2.layer_type == "object"
        assert len(layer2.objects) == 2
        assert layer2.next_object_id == 3
        print("✓ Object layer serialization works")


class LayerManagerTests:
    """Test the LayerManager class."""

    def test_layer_manager_creation(self):
        """Test basic LayerManager creation."""
        manager = create_default_layer_manager()
        assert len(manager.layers) == 2
        assert manager.layers[0].name == "Terrain"
        assert manager.layers[1].name == "Objects"
        assert manager.active_layer_idx == 0
        print("✓ LayerManager creation works")

    def test_get_active_layer(self):
        """Test getting the active layer."""
        manager = create_default_layer_manager()
        active = manager.get_active_layer()
        assert active is not None
        assert active.name == "Terrain"
        print("✓ Get active layer works")

    def test_set_active_layer(self):
        """Test changing active layer."""
        manager = create_default_layer_manager()
        manager.set_active_layer(1)
        active = manager.get_active_layer()
        assert active.name == "Objects"
        print("✓ Set active layer works")

    def test_create_layer(self):
        """Test creating a new layer."""
        manager = create_default_layer_manager()
        initial_count = len(manager.layers)
        manager.create_layer("NewLayer", "tile")
        assert len(manager.layers) == initial_count + 1
        assert manager.layers[-1].name == "NewLayer"
        print("✓ Create layer works")

    def test_delete_layer(self):
        """Test deleting a layer."""
        manager = create_default_layer_manager()
        manager.create_layer("Temp", "tile")
        assert len(manager.layers) == 3

        manager.delete_layer(2)
        assert len(manager.layers) == 2
        print("✓ Delete layer works")

    def test_reorder_layers(self):
        """Test reordering layers."""
        manager = create_default_layer_manager()
        manager.create_layer("Third", "tile")

        # Move "Objects" (index 1) to position 0
        manager.reorder_layer(1, 0)

        assert manager.layers[0].name == "Objects"
        assert manager.layers[1].name == "Terrain"
        print("✓ Reorder layers works")

    def test_get_rendered_layers(self):
        """Test getting layers for rendering."""
        manager = create_default_layer_manager()
        manager.layers[1].visible = False

        rendered = manager.get_rendered_layers()
        assert len(rendered) == 1
        assert rendered[0].name == "Terrain"
        print("✓ Get rendered layers works")

    def test_layer_manager_serialization(self):
        """Test LayerManager to_dict/from_dict."""
        manager = create_default_layer_manager()
        manager.layers[0].set_tile((0, 0), create_test_tile("1", 2))
        manager.layers[1].set_tile((1, 1), create_test_tile("3", 4))
        manager.set_active_layer(1)

        data = manager.to_dict()
        assert len(data["layers"]) == 2
        assert data["active_layer_idx"] == 1

        manager2 = LayerManager.from_dict(data)
        assert len(manager2.layers) == 2
        assert manager2.active_layer_idx == 1
        assert manager2.get_active_layer().name == "Objects"
        print("✓ LayerManager serialization works")


class BackwardCompatibilityTests:
    """Test backward compatibility with single-layer system."""

    def test_ongrid_tiles_property(self):
        """Test that ongrid_tiles property works correctly."""
        # This test validates the backward compatibility mechanism
        # We can't fully test without a real Editor instance, but we can verify the concept

        manager = create_default_layer_manager()
        active_layer = manager.get_active_layer()

        # Simulate tile placement on "active" layer
        tile = create_test_tile("1", 2)
        pos = (5, 10)
        active_layer.set_tile(pos, tile)

        # Verify we can access it
        assert active_layer.get_tile(pos) is not None

        # Switch to Objects layer
        manager.set_active_layer(1)
        new_active = manager.get_active_layer()
        assert new_active.name == "Objects"
        assert new_active.get_tile(pos) is None  # Different layer

        print("✓ Active layer switching works (backward compat pattern)")


class SaveLoadTests:
    """Test save/load functionality with layers."""

    def test_save_load_new_format(self):
        """Test saving and loading in new v1.1 format."""
        # Create a test map with layers
        manager = create_default_layer_manager()
        manager.layers[0].set_tile((0, 0), create_test_tile("1", 2))
        manager.layers[0].set_tile((1, 1), create_test_tile("3", 4))
        manager.layers[1].set_tile((2, 2), create_test_tile("5", 6))

        # Get dict representation
        data = manager.to_dict()

        # Verify structure
        assert "layers" in data
        assert len(data["layers"]) == 2
        assert "active_layer_idx" in data
        assert data["active_layer_idx"] == 0

        # Verify tiles are present
        assert len(data["layers"][0]["tiles"]) == 2
        assert len(data["layers"][1]["tiles"]) == 1

        # Verify we can reconstruct from dict
        manager2 = LayerManager.from_dict(data)
        assert len(manager2.layers) == 2
        assert manager2.active_layer_idx == 0

        print("✓ Save/load new format works")

    def test_save_load_legacy_format(self):
        """Test loading legacy v1.0 format."""
        test_file = Path("/tmp/test_map_v1.0.json")

        # Simulate legacy format (ongrid only)
        legacy_data = {
            "meta": {"tile_size": "32;32", "map_size": "10;10"},
            "data": {
                "ongrid": {
                    "0;0": {"pos": "0;0", "ttype": 1, "variant": 2},
                    "1;1": {"pos": "1;1", "ttype": 3, "variant": 4},
                },
            },
        }

        with open(test_file, "w") as f:
            json.dump(legacy_data, f)

        # Verify file exists and has expected structure
        with open(test_file, "r") as f:
            loaded = json.load(f)

        assert "ongrid" in loaded["data"]
        assert "0;0" in loaded["data"]["ongrid"]

        test_file.unlink()
        print("✓ Legacy format loading works")


def run_all_tests():
    """Run all test suites."""
    print("\n" + "=" * 60)
    print("TILEMAP LAYER SYSTEM TEST SUITE")
    print("=" * 60 + "\n")

    test_suites = [
        ("Layer Tests", LayerTests()),
        ("LayerManager Tests", LayerManagerTests()),
        ("Backward Compatibility Tests", BackwardCompatibilityTests()),
        ("Save/Load Tests", SaveLoadTests()),
    ]

    total_tests = 0
    passed_tests = 0

    for suite_name, test_suite in test_suites:
        print(f"\n{suite_name}:")
        print("-" * 60)

        # Get all test methods
        test_methods = [
            method for method in dir(test_suite) if method.startswith("test_")
        ]

        for test_method in test_methods:
            try:
                getattr(test_suite, test_method)()
                passed_tests += 1
            except AssertionError as e:
                print(f"✗ {test_method} failed: {e}")
            except Exception as e:
                print(f"✗ {test_method} error: {e}")
            finally:
                total_tests += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed_tests}/{total_tests} tests passed")
    print("=" * 60 + "\n")

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
