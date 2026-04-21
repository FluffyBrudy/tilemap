"""
Layer management system for tilemap editor.
Supports multiple layers with independent tile and object data.
"""

import random
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple, Any
from ttypes.tilemap import TypeTile, TypeObject

if TYPE_CHECKING:
    from widgets.autotiler import AutotileRule


class Layer:
    """Represents a single layer in the tilemap.

    Tile layers: store tiles at grid coordinates (grid_x, grid_y)
    Object layers: store objects at pixel coordinates (pixel_x, pixel_y) with unique IDs
    """

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
        self.layer_type = layer_type
        self.z_index = z_index
        self.visible = visible
        self.locked = locked
        self.opacity = max(0.0, min(1.0, opacity))
        self.properties: Dict[str, Any] = {}

        self.tiles: Dict[Tuple[int, int], TypeTile] = {}

        self.objects: Dict[int, TypeObject] = {}
        self.next_object_id: int = 1

        # Caching for autotile rules
        self._autotile_cache = {
            "rules_hash": None,
            "variant_to_group": {},
            "rules_by_group": {},
            "significant_offsets": set()
        }

    def set_tile(self, pos: Tuple[int, int], tile: TypeTile) -> None:
        """Set a tile at the given grid position."""
        if not self.locked:
            self.tiles[pos] = tile

    def get_tile(self, pos: Tuple[int, int]) -> Optional[TypeTile]:
        """Get a tile at the given grid position."""
        return self.tiles.get(pos)

    def autotile_layer(self, rules: List["AutotileRule"]) -> int:
        """Update all tiles in this layer according to autotile rules."""
        return self._autotile_tiles(rules, list(self.tiles.keys()))

    def autotile_at_pos(self, pos: Tuple[int, int], rules: List["AutotileRule"]) -> int:
        """Update the tile at pos and its 8 neighbors according to autotile rules."""
        positions = [pos]
        for dx, dy in [
            (-1, -1), (0, -1), (1, -1),
            (-1, 0),          (1, 0),
            (-1, 1),  (0, 1),  (1, 1)
        ]:
            positions.append((pos[0] + dx, pos[1] + dy))
        
        # Only process tiles that actually exist
        existing_positions = [p for p in positions if p in self.tiles]
        return self._autotile_tiles(rules, existing_positions)

    def _autotile_tiles(self, rules: List["AutotileRule"], positions: List[Tuple[int, int]]) -> int:
        """
        Internal helper to update specific tiles according to autotile rules.
        """
        if self.locked or self.layer_type != "tile":
            return 0

        if not rules or not positions:
            return 0

        # 1. Check cache or build dictionary for O(1) lookup
        # Simple hash based on rule count and tileset indices
        rules_hash = hash(tuple((r.group_id, r.tileset_index, tuple(sorted(r.variant_ids))) for r in rules))
        
        if self._autotile_cache["rules_hash"] != rules_hash:
            variant_to_group = {}
            rules_by_group: Dict[str, List["AutotileRule"]] = {}
            significant_offsets = set()
            
            for rule in rules:
                gid = rule.group_id
                if gid not in rules_by_group:
                    rules_by_group[gid] = []
                rules_by_group[gid].append(rule)
                
                ts_idx = rule.tileset_index
                for vid in rule.variant_ids:
                    variant_to_group[(ts_idx, vid)] = gid
                
                significant_offsets.update(rule.neighbors)

            # Sort rules in each group by neighbor count for best-match priority
            for gid in rules_by_group:
                rules_by_group[gid].sort(key=lambda r: len(r.neighbors), reverse=True)
                
            self._autotile_cache.update({
                "rules_hash": rules_hash,
                "variant_to_group": variant_to_group,
                "rules_by_group": rules_by_group,
                "significant_offsets": significant_offsets
            })
        else:
            variant_to_group = self._autotile_cache["variant_to_group"]
            rules_by_group = self._autotile_cache["rules_by_group"]
            significant_offsets = self._autotile_cache["significant_offsets"]

        changes_count = 0
        
        for pos in positions:
            if pos not in self.tiles:
                continue
                
            tile = self.tiles[pos]
            ttype = tile["ttype"]
            current_variant = tile["variant"]
            
            # 3. Identify the group of the CURRENT tile
            target_group_id = variant_to_group.get((ttype, current_variant))
            if not target_group_id:
                continue
                
            # 4. Detect neighbors (8-way) that belong to the SAME group
            actual_neighbors = []
            for dx, dy in [
                (-1, -1), (0, -1), (1, -1),
                (-1, 0),          (1, 0),
                (-1, 1),  (0, 1),  (1, 1)
            ]:
                npos = (pos[0] + dx, pos[1] + dy)
                if npos in self.tiles:
                    n_tile = self.tiles[npos]
                    n_group = variant_to_group.get((n_tile["ttype"], n_tile["variant"]))
                    
                    if n_group == target_group_id:
                        actual_neighbors.append((dx, dy))

            # 5. Filter to directions defined in the ruleset
            neighbor_offsets_set = {n for n in actual_neighbors if n in significant_offsets}

            # 6. Find matching rule WITHIN the same group
            matched_rule: Optional["AutotileRule"] = None
            group_rules = rules_by_group.get(target_group_id, [])
            
            for rule in group_rules:
                if (rule.neighbors == neighbor_offsets_set and 
                    rule.tileset_index == ttype):
                    matched_rule = rule
                    break
            
            if matched_rule and matched_rule.variant_ids:
                # Avoid unnecessary updates
                if current_variant in matched_rule.variant_ids:
                    continue
                
                new_variant = random.choice(matched_rule.variant_ids)
                tile["variant"] = new_variant
                changes_count += 1

        return changes_count

    def remove_tile(self, pos: Tuple[int, int]) -> bool:
        """Remove a tile at the given grid position. Returns True if tile existed."""
        if not self.locked and pos in self.tiles:
            del self.tiles[pos]
            return True
        return False

    def flood_fill(self, start_pos: Tuple[int, int], new_tile_data: TypeTile, map_size: Tuple[int, int]) -> None:
        """Replace contiguous tiles of the same type starting from start_pos."""
        if self.locked or self.layer_type != "tile":
            return

        target_tile = self.tiles.get(start_pos)
        target_ttype = target_tile["ttype"] if target_tile else None
        target_variant = target_tile["variant"] if target_tile else None

        new_ttype = new_tile_data["ttype"]
        new_variant = new_tile_data["variant"]

        if target_ttype == new_ttype and target_variant == new_variant:
            return

        queue = [start_pos]
        seen = {start_pos}

        while queue:
            curr = queue.pop(0)
            
            # Bounds check if necessary, though dict sparse storage handles it
            if curr[0] < 0 or curr[0] >= map_size[0] or curr[1] < 0 or curr[1] >= map_size[1]:
                continue

            # Check if current tile matches target
            curr_tile = self.tiles.get(curr)
            curr_ttype = curr_tile["ttype"] if curr_tile else None
            curr_variant = curr_tile["variant"] if curr_tile else None

            if curr_ttype == target_ttype and curr_variant == target_variant:
                # Update tile
                td = new_tile_data.copy()
                td["pos"] = curr
                self.tiles[curr] = td

                # Add neighbors
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    next_pos = (curr[0] + dx, curr[1] + dy)
                    if next_pos not in seen:
                        seen.add(next_pos)
                        queue.append(next_pos)

    def get_all_tiles(self) -> Dict[Tuple[int, int], TypeTile]:
        """Return a copy of all tiles in this layer."""
        return dict(self.tiles)

    def add_object(self, pos: Tuple[int, int], obj: TypeObject) -> int:
        """Add an object at the given pixel position. Returns the object ID."""
        if not self.locked:
            obj_id = self.next_object_id
            self.next_object_id += 1
            self.objects[obj_id] = obj
            return obj_id
        return -1

    def get_object(self, obj_id: int) -> Optional[TypeObject]:
        """Get an object by ID."""
        return self.objects.get(obj_id)

    def remove_object(self, obj_id: int) -> bool:
        """Remove an object by ID. Returns True if object existed."""
        if not self.locked and obj_id in self.objects:
            del self.objects[obj_id]
            return True
        return False

    def get_all_objects(self) -> Dict[int, TypeObject]:
        """Return a copy of all objects in this layer."""
        return dict(self.objects)

    def move_object(self, obj_id: int, new_pos: Tuple[int, int]) -> bool:
        """Move an object to a new position. Returns True if successful."""
        if not self.locked and obj_id in self.objects:

            self.objects[obj_id]["area"]["x"] = new_pos[0]
            self.objects[obj_id]["area"]["y"] = new_pos[1]
            return True
        return False

    def clear(self) -> None:
        """Clear all tiles and objects from this layer."""
        if not self.locked:
            self.tiles.clear()
            self.objects.clear()

    def to_dict(self) -> dict:
        """Serialize layer to dictionary."""
        data = {
            "name": self.name,
            "type": self.layer_type,
            "z_index": self.z_index,
            "visible": self.visible,
            "locked": self.locked,
            "opacity": self.opacity,
        }

        if self.tiles:
            data["tiles"] = {str(k): v for k, v in self.tiles.items()}
        else:
            data["tiles"] = {}

        if self.objects:
            data["objects"] = {str(obj_id): obj for obj_id, obj in self.objects.items()}
        else:
            data["objects"] = {}

        data["next_object_id"] = self.next_object_id
        
        # Metadata storage
        data["metadata"] = getattr(self, "metadata", {})

        return data

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

        if "tiles" in data:
            for pos_str, tile_data in data["tiles"].items():

                pos_parts = pos_str.strip("()").split(",")
                if len(pos_parts) == 2:
                    try:
                        pos = (int(pos_parts[0]), int(pos_parts[1]))
                        layer.tiles[pos] = tile_data
                    except (ValueError, IndexError):
                        pass

        if "objects" in data:
            for obj_id_str, obj_data in data["objects"].items():
                try:
                    obj_id = int(obj_id_str)
                    layer.objects[obj_id] = obj_data

                    if obj_id >= layer.next_object_id:
                        layer.next_object_id = obj_id + 1
                except (ValueError, TypeError):
                    pass

        if "next_object_id" in data:
            layer.next_object_id = data["next_object_id"]

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

        if not manager.layers:
            manager.create_layer("Default")

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


def create_default_layer_manager() -> LayerManager:
    """Create a default layer manager with Terrain and Objects layers."""
    manager = LayerManager()
    manager.create_layer("Terrain", "tile")
    manager.create_layer("Objects", "object")
    manager.set_active_layer(0)
    return manager
