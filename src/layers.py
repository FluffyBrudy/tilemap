"""
Layer management system for tilemap editor.
Supports multiple layers with independent tile data.
"""

from typing import Dict, List, Optional, Tuple
from ttypes.tilemap import TypeTile


class Layer:
    """Represents a single layer in the tilemap."""

    def __init__(
        self,
        name: str,
        layer_type: str = "tile",
        z_index: int = 0,
        visible: bool = True,
        locked: bool = False,
        opacity: float = 1.0,
    ):
        self.name = name
        self.layer_type = layer_type  # "tile" or "object"
        self.z_index = z_index
        self.visible = visible
        self.locked = locked
        self.opacity = max(0.0, min(1.0, opacity))

        # Tile data: position -> tile mapping
        self.tiles: Dict[Tuple[int, int], TypeTile] = {}

    def set_tile(self, pos: Tuple[int, int], tile: TypeTile) -> None:
        """Set a tile at the given position."""
        if not self.locked:
            self.tiles[pos] = tile

    def get_tile(self, pos: Tuple[int, int]) -> Optional[TypeTile]:
        """Get a tile at the given position."""
        return self.tiles.get(pos)

    def remove_tile(self, pos: Tuple[int, int]) -> bool:
        """Remove a tile at the given position. Returns True if tile existed."""
        if not self.locked and pos in self.tiles:
            del self.tiles[pos]
            return True
        return False

    def clear(self) -> None:
        """Clear all tiles from this layer."""
        if not self.locked:
            self.tiles.clear()

    def get_all_tiles(self) -> Dict[Tuple[int, int], TypeTile]:
        """Return a copy of all tiles in this layer."""
        return dict(self.tiles)

    def to_dict(self) -> dict:
        """Serialize layer to dictionary."""
        return {
            "name": self.name,
            "type": self.layer_type,
            "z_index": self.z_index,
            "visible": self.visible,
            "locked": self.locked,
            "opacity": self.opacity,
            "tiles": {str(k): v for k, v in self.tiles.items()},
        }

    @staticmethod
    def from_dict(data: dict) -> "Layer":
        """Deserialize layer from dictionary."""
        layer = Layer(
            name=data.get("name", "Unnamed"),
            layer_type=data.get("type", "tile"),
            z_index=data.get("z_index", 0),
            visible=data.get("visible", True),
            locked=data.get("locked", False),
            opacity=data.get("opacity", 1.0),
        )

        # Restore tiles
        if "tiles" in data:
            for pos_str, tile_data in data["tiles"].items():
                # Parse position string back to tuple
                pos_parts = pos_str.strip("()").split(",")
                if len(pos_parts) == 2:
                    try:
                        pos = (int(pos_parts[0]), int(pos_parts[1]))
                        layer.tiles[pos] = tile_data
                    except (ValueError, IndexError):
                        pass

        return layer


class LayerManager:
    """Manages multiple layers for a tilemap."""

    def __init__(self):
        self.layers: List[Layer] = []
        self.active_layer_idx: int = -1

    def create_layer(
        self,
        name: str,
        layer_type: str = "tile",
        insert_index: Optional[int] = None,
    ) -> Layer:
        """Create a new layer and add it to the manager."""
        z_index = len(self.layers)
        layer = Layer(name, layer_type, z_index)

        if insert_index is None:
            self.layers.append(layer)
            if self.active_layer_idx == -1:
                self.active_layer_idx = 0
        else:
            self.layers.insert(insert_index, layer)
            self._update_z_indices()
            if self.active_layer_idx == -1:
                self.active_layer_idx = 0

        return layer

    def delete_layer(self, index: int) -> bool:
        """Delete a layer at the given index. Cannot delete last layer."""
        if len(self.layers) <= 1 or index < 0 or index >= len(self.layers):
            return False

        self.layers.pop(index)
        self._update_z_indices()

        # Adjust active layer index if needed
        if self.active_layer_idx >= len(self.layers):
            self.active_layer_idx = len(self.layers) - 1

        return True

    def get_layer(self, index: int) -> Optional[Layer]:
        """Get a layer by index."""
        if 0 <= index < len(self.layers):
            return self.layers[index]
        return None

    def get_active_layer(self) -> Optional[Layer]:
        """Get the currently active layer."""
        return self.get_layer(self.active_layer_idx)

    def set_active_layer(self, index: int) -> bool:
        """Set the active layer by index."""
        if 0 <= index < len(self.layers):
            self.active_layer_idx = index
            return True
        return False

    def reorder_layer(self, from_index: int, to_index: int) -> bool:
        """Move a layer from one position to another."""
        if 0 <= from_index < len(self.layers) and 0 <= to_index < len(self.layers):
            layer = self.layers.pop(from_index)
            self.layers.insert(to_index, layer)
            self._update_z_indices()

            # Update active layer index if it was moved
            if self.active_layer_idx == from_index:
                self.active_layer_idx = to_index

            return True
        return False

    def get_rendered_layers(self) -> List[Layer]:
        """Get all visible layers sorted by z_index for rendering."""
        visible = [layer for layer in self.layers if layer.visible]
        return sorted(visible, key=lambda l: l.z_index)

    def _update_z_indices(self) -> None:
        """Update z_index values for all layers based on their position."""
        for i, layer in enumerate(self.layers):
            layer.z_index = i

    def clear_all_layers(self) -> None:
        """Clear all tiles from all layers."""
        for layer in self.layers:
            layer.clear()

    def to_dict(self) -> dict:
        """Serialize all layers to dictionary."""
        return {
            "active_layer_idx": self.active_layer_idx,
            "layers": [layer.to_dict() for layer in self.layers],
        }

    @staticmethod
    def from_dict(data: dict) -> "LayerManager":
        """Deserialize layer manager from dictionary."""
        manager = LayerManager()
        manager.active_layer_idx = data.get("active_layer_idx", 0)

        for layer_data in data.get("layers", []):
            layer = Layer.from_dict(layer_data)
            manager.layers.append(layer)

        # Ensure at least one layer exists
        if not manager.layers:
            manager.create_layer("Default")

        # Validate active layer index
        if manager.active_layer_idx < 0 or manager.active_layer_idx >= len(
            manager.layers
        ):
            manager.active_layer_idx = 0

        return manager

    def get_layer_count(self) -> int:
        """Get the total number of layers."""
        return len(self.layers)

    def has_layers(self) -> bool:
        """Check if manager has any layers."""
        return len(self.layers) > 0


# Convenience function for creating a default manager with one layer
def create_default_layer_manager() -> LayerManager:
    """Create a layer manager with a single 'Default' layer."""
    manager = LayerManager()
    manager.create_layer("Terrain", "tile")
    manager.create_layer("Objects", "tile")
    return manager
