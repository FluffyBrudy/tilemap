from typing import TYPE_CHECKING, Any, Dict, List, Set, Tuple, Optional
from pygame import Rect
from json import load as JSONLoad, dump as JSONDump
from pathlib import Path

from constants import BASE_PATH
from utils.serialization import (
    deserialize_point,
    serialize_point,
    copy_object,
    serialize_object,
)
from ttypes.tilemap import TypeObject, TypeTile, TypeTileSerealized
from layers import LayerManager, create_default_layer_manager

if TYPE_CHECKING:
    from src.ttypes import TTile, TCoor
    from editor import Editor

NEAREST_NEIGHBOUR_OFFSET = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (0, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)
from widgets.autotiler import AutotileRule


class Tilemap:
    def __init__(self, editor: "Editor"):
        self.editor = editor
        self.layer_manager = create_default_layer_manager()
        self.offgrid_tiles: Set[TypeTile] = set()

        self.tile_size = (32, 32)
        self.map_size = (50, 50)
        self.initialized = False

        self.active_project_path: Optional[Path] = None

    @property
    def ongrid_tiles(self) -> "TTile":
        """Backward compatibility property. Returns tiles from active layer."""
        active_layer = self.layer_manager.get_active_layer()
        if active_layer:
            return active_layer.tiles
        return {}

    @ongrid_tiles.setter
    def ongrid_tiles(self, value: "TTile") -> None:
        """Backward compatibility setter. Sets tiles in active layer."""
        active_layer = self.layer_manager.get_active_layer()
        if active_layer:
            active_layer.tiles = value

    def init_size(self, tile_size: "TCoor", map_size: "TCoor"):
        self.tile_size = tile_size
        self.map_size = map_size
        self.initialized = True
        self.active_project_path = None

    def get_nearest_tiles(self, tile_location: "TCoor") -> Tuple["TCoor"]:
        """Get empty neighboring tile positions for the given location."""
        assert len(tile_location) == 2
        tiles_around = []

        # Check all visible layers for occupied tiles
        active_layer = self.layer_manager.get_active_layer()
        if not active_layer or tile_location not in active_layer.tiles:
            return tuple(tiles_around)

        x, y = tile_location
        for nx, ny in NEAREST_NEIGHBOUR_OFFSET:
            check_loc = (x + nx, y + ny)
            # Check if position is empty in active layer
            if check_loc not in active_layer.tiles:
                tiles_around.append(check_loc)
        return tuple(tiles_around)

    def save_map(self, relative_path: Optional[str] = None):
        target_path: Path = None  # type: ignore

        if relative_path:
            if not relative_path.endswith(".json"):
                relative_path += ".json"
            target_path = BASE_PATH / "data" / relative_path
            self.active_project_path = target_path
        elif self.active_project_path:
            target_path = self.active_project_path
        else:
            raise ValueError("No path specified for save")

        if not target_path.parent.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)

        save_data = {
            "meta": {
                "tile_size": serialize_point(self.tile_size),
                "map_size": serialize_point(self.map_size),
                "version": "1.1",  # Updated version for layer support
            },
            "resources": {"tilesets": []},
            "project_state": {"rules": []},
            "data": {
                "ongrid": {},  # Legacy format - populated from first layer
                "layers": [],  # New format
                "offgrid": [],
            },
        }

        if hasattr(self.editor, "tileset_widget") and self.editor.tileset_widget:
            for ts in self.editor.tileset_widget.tilesets:
                try:
                    rel = ts.path.relative_to(BASE_PATH)
                    path_str = str(rel)
                except ValueError:
                    path_str = str(ts.path)

                # Store both path and type so we can restore without asking user
                save_data["resources"]["tilesets"].append(
                    {"path": path_str, "type": ts.tileset_type}
                )

        if hasattr(self.editor, "autotiler") and self.editor.autotiler:
            for rule in self.editor.autotiler.rules:
                save_data["project_state"]["rules"].append(rule.to_dict())

        # Save all layers in new format
        for layer in self.layer_manager.layers:
            layer_data = {
                "name": layer.name,
                "type": layer.layer_type,
                "visible": layer.visible,
                "locked": layer.locked,
                "opacity": layer.opacity,
                "z_index": layer.z_index,
                "tiles": {},
            }

            # Save tiles
            for loc, tile in layer.tiles.items():
                key = serialize_point(loc)
                tile_data: Dict[str, Any] = {
                    "pos": serialize_point(tile["pos"]),
                    "ttype": tile["ttype"],
                    "variant": tile["variant"],
                }
                layer_data["tiles"][key] = tile_data

            # Save objects (for object layers)
            if layer.layer_type == "object":
                layer_data["objects"] = {}
                for obj_id, obj in layer.objects.items():
                    obj_data: Dict[str, Any] = {
                        "area": obj["area"],
                        "ttype": obj["ttype"],
                        "tileset_type": obj["tileset_type"],
                        "variant": obj["variant"],
                    }
                    layer_data["objects"][str(obj_id)] = obj_data
                # Store next_object_id for proper restoration
                layer_data["next_object_id"] = layer.next_object_id

            save_data["data"]["layers"].append(layer_data)

        # Also save first layer to legacy ongrid format for backward compatibility
        first_layer = self.layer_manager.get_layer(0)
        if first_layer:
            for loc, tile in first_layer.tiles.items():
                key = serialize_point(loc)
                tile_data: Dict[str, Any] = {
                    "pos": serialize_point(tile["pos"]),
                    "ttype": tile["ttype"],
                    "variant": tile["variant"],
                }
                save_data["data"]["ongrid"][key] = tile_data

        for tile in self.offgrid_tiles:
            tile_data: Dict[str, Any] = {
                "pos": serialize_point(tile["pos"]),
                "ttype": tile["ttype"],
                "variant": tile["variant"],
            }
            save_data["data"]["offgrid"].append(tile_data)

        with open(target_path, "w") as f:
            JSONDump(save_data, f, indent=2)

        print(f"Saved to {target_path}")

    def load_map(self, path: Path):
        if not path.exists():
            print(f"Error: {path} does not exist")
            return

        with open(path, "r") as f:
            payload = JSONLoad(f)

        # Clear existing data
        self.layer_manager.clear_all_layers()
        self.offgrid_tiles.clear()
        self.active_project_path = path

        self.tile_size = deserialize_point(payload["meta"]["tile_size"])
        self.map_size = deserialize_point(payload["meta"].get("map_size", "50;50"))

        if hasattr(self.editor, "tileset_widget") and self.editor.tileset_widget:
            self.editor.tileset_widget.tilesets.clear()
            self.editor.tileset_widget.tileset_map.clear()

            for ts_entry in payload["resources"]["tilesets"]:
                # Handle both old format (string) and new format (dict with path and type)
                if isinstance(ts_entry, str):
                    # Legacy format: just a path string, default to "tile" type
                    path_str = ts_entry
                    tileset_type = "tile"
                else:
                    # New format: dict with path and type
                    path_str = ts_entry.get("path", "")
                    tileset_type = ts_entry.get("type", "tile")

                p = Path(path_str)
                if not p.is_absolute():
                    p = BASE_PATH / p

                # Load tileset silently without showing the type dialog
                # (we already know the type from the saved map file)
                self.editor.tileset_widget.load_tileset_from_path(p, tileset_type)

        if hasattr(self.editor, "autotiler") and self.editor.autotiler:
            designer = self.editor.autotiler
            designer.rules.clear()

            ts_widget = self.editor.tileset_widget
            assert ts_widget is not None

            if "project_state" in payload:
                for rule_dict in payload["project_state"]["rules"]:
                    try:
                        rule = AutotileRule.from_dict(rule_dict)

                        resolved_ts = None
                        if rule.tileset_index is not None:
                            idx = rule.tileset_index
                            if 0 <= idx < len(ts_widget.tilesets):
                                resolved_ts = ts_widget.tilesets[idx]
                        elif rule.tileset_path:
                            for idx, ts in enumerate(ts_widget.tilesets):
                                try:
                                    if str(Path(rule.tileset_path)) == str(ts.path):
                                        rule.tileset_index = idx
                                        resolved_ts = ts
                                        break
                                    if str(Path(rule.tileset_path)) == str(
                                        ts.path.relative_to(BASE_PATH)
                                    ):
                                        rule.tileset_index = idx
                                        resolved_ts = ts
                                        break
                                except Exception:
                                    continue

                        if resolved_ts and rule.variant_ids:
                            vid = rule.variant_ids[0]
                            cols = resolved_ts.surface.get_width() // self.tile_size[0]

                            tx = (vid % cols) * self.tile_size[0]
                            ty = (vid // cols) * self.tile_size[1]

                            rule.preview_surf = resolved_ts.surface.subsurface(
                                Rect(tx, ty, *self.tile_size)
                            ).copy()

                        designer.rules.append(rule)
                    except Exception as e:
                        print(f"Failed to load rule '{rule_dict.get('name')}': {e}")

        # Load layers - check for new format first, fall back to legacy format
        data_section = payload.get("data", {})

        if "layers" in data_section and data_section["layers"]:
            # New layer format
            self.layer_manager.layers.clear()
            for layer_data in data_section["layers"]:
                layer = self._load_layer_from_dict(layer_data)
                self.layer_manager.layers.append(layer)

            # Ensure at least one layer exists
            if not self.layer_manager.layers:
                self.layer_manager.create_layer("Default")

            self.layer_manager.active_layer_idx = 0
        else:
            # Legacy format - load ongrid into first layer
            raw_ongrid = data_section.get("ongrid", {})
            if raw_ongrid:
                # Clear default layers and create single layer
                self.layer_manager.layers.clear()
                self.layer_manager.create_layer("Terrain")
                active_layer = self.layer_manager.get_active_layer()

                for loc_str, tile_data in raw_ongrid.items():
                    pos = deserialize_point(loc_str)
                    tile_data["pos"] = pos
                    self._normalize_ttype(tile_data)
                    if active_layer:
                        active_layer.tiles[pos] = tile_data

        # Load offgrid tiles
        for tile_data in data_section.get("offgrid", []):
            tile_copy = tile_data.copy()
            tile_copy["pos"] = deserialize_point(tile_data["pos"])
            self.offgrid_tiles.add(tile_copy)

        self.initialized = True
        print(
            f"Map Loaded: {path.name} (Layers: {self.layer_manager.get_layer_count()})"
        )

    def _load_layer_from_dict(self, layer_data: dict):
        """Load a layer from dictionary format."""
        from layers import Layer

        layer = Layer(
            name=layer_data.get("name", "Unnamed"),
            layer_type=layer_data.get("type", "tile"),
            z_index=layer_data.get("z_index", 0),
            visible=layer_data.get("visible", True),
            locked=layer_data.get("locked", False),
            opacity=layer_data.get("opacity", 1.0),
        )

        # Load tiles
        for loc_str, tile_data in layer_data.get("tiles", {}).items():
            pos = deserialize_point(loc_str)
            tile_copy = tile_data.copy()
            tile_copy["pos"] = pos
            self._normalize_ttype(tile_copy)
            layer.tiles[pos] = tile_copy

        # Load objects (for object layers)
        if layer.layer_type == "object":
            for obj_id_str, obj_data in layer_data.get("objects", {}).items():
                try:
                    obj_id = int(obj_id_str)
                    # Create object with the new area structure
                    obj_copy: TypeObject = {
                        "area": obj_data.get(
                            "area", {"x": 0, "y": 0, "w": 32, "h": 32}
                        ),
                        "ttype": obj_data.get("ttype", 0),
                        "tileset_type": obj_data.get("tileset_type", "object"),
                        "variant": obj_data.get("variant", 0),
                    }
                    layer.objects[obj_id] = obj_copy
                    # Keep track of highest ID for next_object_id
                    if obj_id >= layer.next_object_id:
                        layer.next_object_id = obj_id + 1
                except (ValueError, TypeError, KeyError):
                    pass

            # Restore next_object_id if present
            if "next_object_id" in layer_data:
                layer.next_object_id = layer_data["next_object_id"]

        return layer

    def _normalize_ttype(self, tile_data: dict) -> None:
        """Normalize ttype field - convert path strings to indices if needed."""
        ttype = tile_data.get("ttype")
        if hasattr(self.editor, "tileset_widget") and self.editor.tileset_widget:
            ts_widget = self.editor.tileset_widget

            # If ttype is a string path, try to convert to index
            if isinstance(ttype, str):
                matched_idx = None
                for idx, ts in enumerate(ts_widget.tilesets):
                    try:
                        if str(Path(ttype)) == str(ts.path):
                            matched_idx = idx
                            break
                        if str(Path(ttype)) == str(ts.path.relative_to(BASE_PATH)):
                            matched_idx = idx
                            break
                    except Exception:
                        continue
                if matched_idx is not None:
                    tile_data["ttype"] = matched_idx
