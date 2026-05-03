from typing import TYPE_CHECKING, Any, Dict, Tuple, Optional, Union
from pygame import Rect
from json import load as JSONLoad, dump as JSONDump
from pathlib import Path

from constants import BASE_PATH
from utils.serialization import (
    deserialize_point,
    serialize_point,
)
from ttypes.tilemap import TypeObject
from layers import create_default_layer_manager
from utils.history import HistoryManager
from utils import error_handler

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

        self.tile_size = (32, 32)
        self.map_size = (50, 50)
        self.initial_map_size = (50, 50)
        self.initialized = False

        self.active_project_path: Optional[Path] = None
        self.history = HistoryManager()

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
        self.initial_map_size = map_size  # Store what user initially setup
        self.initialized = True
        self.active_project_path = None

        # Clear and create default layer
        self.layer_manager.layers.clear()
        self.layer_manager.create_layer("Layer 1", "tile")
        self.layer_manager.set_active_layer(0)

    def capture_history(self, description: str = "State Change"):
        # Capture current full state
        designer = getattr(self.editor, "autotiler", None)
        groups_data = []
        if designer:
            groups_data = [g.to_dict() for g in designer.groups]

        state = {
            "layers": [L.to_dict() for L in self.layer_manager.layers],
            "groups": groups_data,
            "selected_group_idx": designer.selected_group_idx if designer else 0,
            "active_layer_idx": self.layer_manager.active_layer_idx,
            "tile_size": self.tile_size,
            "map_size": self.map_size,
        }
        self.history.save_state(state, description)

    def undo(self):
        designer = getattr(self.editor, "autotiler", None)
        groups_data = []
        if designer:
            groups_data = [g.to_dict() for g in designer.groups]

        current_state = {
            "layers": [L.to_dict() for L in self.layer_manager.layers],
            "groups": groups_data,
            "selected_group_idx": designer.selected_group_idx if designer else 0,
            "active_layer_idx": self.layer_manager.active_layer_idx,
            "tile_size": self.tile_size,
            "map_size": self.map_size,
        }
        prev_state = self.history.undo(current_state)
        if prev_state:
            self._apply_history_state(prev_state)

    def redo(self):
        designer = getattr(self.editor, "autotiler", None)
        groups_data = []
        if designer:
            groups_data = [g.to_dict() for g in designer.groups]

        current_state = {
            "layers": [L.to_dict() for L in self.layer_manager.layers],
            "groups": groups_data,
            "selected_group_idx": designer.selected_group_idx if designer else 0,
            "active_layer_idx": self.layer_manager.active_layer_idx,
            "tile_size": self.tile_size,
            "map_size": self.map_size,
        }
        next_state = self.history.redo(current_state)
        if next_state:
            self._apply_history_state(next_state)

    def update_map_size(self):
        """Full scan to recalculate map size based on all layers."""
        if not self.initialized:
            return

        max_w = self.initial_map_size[0]
        max_h = self.initial_map_size[1]

        for layer in self.layer_manager.layers:
            if layer.tiles:
                for pos in layer.tiles.keys():
                    max_w = max(max_w, pos[0] + 1)
                    max_h = max(max_h, pos[1] + 1)

            if layer.objects:
                for obj in layer.objects.values():
                    area = obj["area"]
                    grid_r = (area["x"] + area["w"]) / self.tile_size[0]
                    grid_b = (area["y"] + area["h"]) / self.tile_size[1]
                    max_w = max(max_w, int(grid_r) + 1)
                    max_h = max(max_h, int(grid_b) + 1)

        self.map_size = (max_w, max_h)

    def incremental_update_map_size(
        self,
        pos: Tuple[int, int],
        is_pixel: bool = False,
        size: Optional[Tuple[int, int]] = None,
    ):
        """Update map size based on a single point or area without full scan."""
        if not self.initialized:
            return

        if is_pixel:
            # For objects/pixel positions
            w, h = size if size else self.tile_size
            grid_r = int((pos[0] + w) / self.tile_size[0]) + 1
            grid_b = int((pos[1] + h) / self.tile_size[1]) + 1
            new_w = max(self.map_size[0], grid_r)
            new_h = max(self.map_size[1], grid_b)
        else:
            # For grid positions
            new_w = max(self.map_size[0], pos[0] + 1)
            new_h = max(self.map_size[1], pos[1] + 1)

        if (new_w, new_h) != self.map_size:
            self.map_size = (new_w, new_h)

    def _apply_history_state(self, state):
        from layers import Layer
        from widgets.autotiler import AutotileGroup

        self.layer_manager.layers = [Layer.from_dict(L) for L in state["layers"]]
        self.layer_manager.active_layer_idx = state["active_layer_idx"]
        self.tile_size = state["tile_size"]
        self.map_size = state["map_size"]

        if hasattr(self.editor, "autotiler"):
            designer = self.editor.autotiler
            if "groups" in state:
                designer.groups = [AutotileGroup.from_dict(G) for G in state["groups"]]
                designer.selected_group_idx = state.get("selected_group_idx", 0)
            elif "rules" in state:  # Fallback for old history
                from widgets.autotiler import AutotileRule

                default_group = AutotileGroup("Default")
                default_group.rules = [
                    AutotileRule.from_dict(R) for R in state["rules"]
                ]
                designer.groups = [default_group]
                designer.selected_group_idx = 0
            designer.selected_rule_index = -1

    def get_nearest_tiles(self, tile_location: "TCoor") -> Tuple["TCoor"]:
        """Get empty neighboring tile positions for the given location."""
        assert len(tile_location) == 2
        tiles_around = []

        active_layer = self.layer_manager.get_active_layer()
        if not active_layer or tile_location not in active_layer.tiles:
            return tuple(tiles_around)

        x, y = tile_location
        for nx, ny in NEAREST_NEIGHBOUR_OFFSET:
            check_loc = (x + nx, y + ny)

            if check_loc not in active_layer.tiles:
                tiles_around.append(check_loc)
        return tuple(tiles_around)

    def save_map(self, relative_path: Optional[Union[str, Path]] = None):
        target_path: Optional[Path] = None

        if relative_path:
            path_obj = Path(relative_path)
            if path_obj.suffix == "":
                path_obj = path_obj.with_suffix(".json")

            if path_obj.is_absolute():
                target_path = path_obj
            else:
                data_root = getattr(getattr(self, 'editor', None), 'data_root', None)
                if data_root:
                    target_path = data_root / path_obj
                else:
                    raise RuntimeError("Cannot determine data_root - Editor not initialized with settings.json")

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
                "zoom_level": (
                    getattr(self.editor.tile_grid_widget, "zoom_level", 1.0)
                    if self.editor.tile_grid_widget
                    else 1.0
                ),
                "scroll": serialize_point(
                    (
                        (
                            getattr(self.editor.tile_grid_widget, "scroll_x", 0)
                            if self.editor.tile_grid_widget
                            else 0
                        ),
                        (
                            getattr(self.editor.tile_grid_widget, "scroll_y", 0)
                            if self.editor.tile_grid_widget
                            else 0
                        ),
                    )
                ),
                "initial_map_size": serialize_point(self.initial_map_size),
                "version": "1.1",
            },
            "resources": {"tilesets": []},
            "project_state": {"rules": []},
            "data": {
                "ongrid": {},
                "layers": [],
            },
        }

        if hasattr(self.editor, "tileset_widget") and self.editor.tileset_widget:
            for ts in self.editor.tileset_widget.tilesets:
                try:
                    # Try to save path relative to map file directory first
                    rel = ts.path.relative_to(target_path.parent)
                    path_str = str(rel)
                except ValueError:
                    # If that fails, try relative to BASE_PATH
                    try:
                        rel = ts.path.relative_to(BASE_PATH)
                        path_str = str(rel)
                    except ValueError:
                        # If both fail, use absolute path
                        path_str = str(ts.path)

                ts_data: Dict[str, Any] = {"path": path_str, "type": ts.tileset_type}
                if ts.properties:
                    ts_data["properties"] = ts.properties
                if ts.tile_properties:
                    # Convert int keys to str for JSON
                    ts_data["tile_properties"] = {
                        str(k): v for k, v in ts.tile_properties.items()
                    }

                save_data["resources"]["tilesets"].append(ts_data)

        if hasattr(self.editor, "autotiler") and self.editor.autotiler:
            if not hasattr(save_data["project_state"], "groups"):
                save_data["project_state"]["groups"] = []

            for group in self.editor.autotiler.groups:
                save_data["project_state"]["groups"].append(group.to_dict())

            # For backward compatibility with simpler loaders, also save flat rules
            save_data["project_state"]["rules"] = []
            for rule in self.editor.autotiler.rules:
                save_data["project_state"]["rules"].append(rule.to_dict())

        # Save automap pattern rules
        if (
            hasattr(self.editor, "regex_automap_designer")
            and self.editor.regex_automap_designer
        ):
            try:
                automap_rules = self.editor.regex_automap_designer.serialize_rules()
                save_data["project_state"]["automap_rules"] = automap_rules
            except Exception as e:
                import logging

                logging.error(f"Error serializing automap rules: {e}", exc_info=True)
                error_handler.capture(
                    e, context="save_automap_rules", severity="warning"
                )
                # Continue saving other data

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

            for loc, tile in layer.tiles.items():
                key = serialize_point(loc)
                tile_data: Dict[str, Any] = {
                    "pos": serialize_point(tile["pos"]),
                    "ttype": tile["ttype"],
                    "variant": tile["variant"],
                }
                if "properties" in tile:
                    tile_data["properties"] = tile["properties"]
                layer_data["tiles"][key] = tile_data

            if layer.layer_type == "object":
                layer_data["objects"] = {}
                for obj_id, obj in layer.objects.items():
                    obj_data: Dict[str, Any] = {
                        "area": obj["area"],
                        "ttype": obj["ttype"],
                        "tileset_type": obj["tileset_type"],
                        "variant": obj["variant"],
                    }
                    if "properties" in obj:
                        obj_data["properties"] = obj["properties"]
                    layer_data["objects"][str(obj_id)] = obj_data

                layer_data["next_object_id"] = layer.next_object_id

            layer_data["properties"] = getattr(layer, "properties", {})
            save_data["data"]["layers"].append(layer_data)

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

        with open(target_path, "w") as f:
            JSONDump(save_data, f, indent=2)

        print(f"Saved to {target_path}")

    def _resolve_rule_resources(self, rule: "AutotileRule", ts_widget):
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
            pr_rect = Rect(tx, ty, *self.tile_size)
            if resolved_ts.surface.get_rect().contains(pr_rect):
                rule.preview_surf = resolved_ts.surface.subsurface(pr_rect).copy()

    def read_map_payload(self, path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist")
        if path.suffix.lower() != ".json":
            raise ValueError(f"{path.name} is not a JSON file")
        with open(path, "r", encoding="utf-8") as f:
            payload = JSONLoad(f)
        if not isinstance(payload, dict) or "meta" not in payload:
            raise ValueError("Invalid project format")
        return payload

    def apply_map_payload(self, path: Path, payload: dict) -> None:
        self.layer_manager.clear_all_layers()
        self.active_project_path = path

        try:
            self.tile_size = deserialize_point(payload["meta"]["tile_size"])
            self.map_size = deserialize_point(payload["meta"].get("map_size", "50;50"))
            # If the file tells us the map is large, we assume that was intended
            # But the 'initial' setup might be in meta or we use map_size as base
            self.initial_map_size = payload["meta"].get("initial_map_size")
            if self.initial_map_size:
                self.initial_map_size = deserialize_point(self.initial_map_size)
            else:
                self.initial_map_size = self.map_size
        except (KeyError, ValueError) as e:
            raise ValueError(f"Error loading map metadata: {e}") from e

        # Restore view state
        if self.editor.tile_grid_widget:
            if "zoom_level" in payload["meta"]:
                self.editor.tile_grid_widget.zoom_level = payload["meta"]["zoom_level"]
            if "scroll" in payload["meta"]:
                scroll = deserialize_point(payload["meta"]["scroll"])
                self.editor.tile_grid_widget.scroll_x = scroll[0]
                self.editor.tile_grid_widget.scroll_y = scroll[1]
            self.editor.tile_grid_widget.clamp_view()

        resources = payload.get("resources", {})
        tilesets = []
        if isinstance(resources, list):
            tilesets = resources
        elif isinstance(resources, dict):
            tilesets = resources.get("tilesets", [])

        if hasattr(self.editor, "tileset_widget") and self.editor.tileset_widget:
            self.editor.tileset_widget.tilesets.clear()
            self.editor.tileset_widget.tileset_map.clear()

            for ts_entry in tilesets:

                if isinstance(ts_entry, str):

                    path_str = ts_entry
                    tileset_type = "tile"
                else:

                    path_str = ts_entry.get("path", "")
                    tileset_type = ts_entry.get("type", "tile")

                # Resolve tileset path relative to map file location
                p = Path(path_str)
                if not p.is_absolute():
                    # First try relative to map file directory
                    map_dir = path.parent
                    p = map_dir / p

                    # If that doesn't exist, try relative to BASE_PATH (for backward compatibility)
                    if not p.exists():
                        p = BASE_PATH / path_str

                # Log error if tileset file not found
                if not p.exists():
                    error_msg = f"Tileset file not found: {path_str} (tried: {p})"
                    error_handler.capture(
                        Exception(error_msg),
                        context="load_tileset_missing",
                        severity="warning",
                    )
                    import logging

                    logging.error(error_msg)
                    continue

                try:
                    self.editor.tileset_widget.load_tileset_from_path(
                        p,
                        tileset_type,
                        properties=ts_entry.get("properties", {}),
                        tile_properties=ts_entry.get("tile_properties", {}),
                    )
                except Exception as e:
                    error_msg = f"Error loading tileset {path_str}: {e}"
                    error_handler.capture(
                        Exception(error_msg),
                        context="load_tileset_error",
                        severity="warning",
                    )
                    import logging

                    logging.error(error_msg)

        if hasattr(self.editor, "autotiler") and self.editor.autotiler:
            from widgets.autotiler import AutotileGroup, AutotileRule

            designer = self.editor.autotiler
            designer.groups.clear()

            ts_widget = self.editor.tileset_widget
            assert ts_widget is not None

            if "project_state" in payload:
                # Load hierarchical groups if available
                if "groups" in payload["project_state"]:
                    for group_dict in payload["project_state"]["groups"]:
                        group = AutotileGroup.from_dict(group_dict)
                        # Resolve tileset indices/previews for all rules in group
                        for rule in group.rules:
                            self._resolve_rule_resources(rule, ts_widget)
                        designer.groups.append(group)

                # Fallback / Migration for old flat rules
                elif "rules" in payload["project_state"]:
                    default_group = AutotileGroup("Default")
                    for rule_dict in payload["project_state"]["rules"]:
                        try:
                            rule = AutotileRule.from_dict(rule_dict)
                            self._resolve_rule_resources(rule, ts_widget)
                            default_group.rules.append(rule)
                        except Exception as e:
                            error_handler.capture(
                                e, context="load_automap_rule", severity="warning"
                            )
                    designer.groups.append(default_group)

            if not designer.groups:
                designer.groups.append(AutotileGroup("Default"))
            designer.selected_group_idx = 0

        # Load automap pattern rules
        if (
            hasattr(self.editor, "regex_automap_designer")
            and self.editor.regex_automap_designer
        ):
            if (
                "project_state" in payload
                and "automap_rules" in payload["project_state"]
            ):
                try:
                    automap_rules_data = payload["project_state"]["automap_rules"]
                    if isinstance(automap_rules_data, list):
                        self.editor.regex_automap_designer.deserialize_rules(
                            automap_rules_data
                        )
                    else:
                        import logging

                        logging.warning(
                            "Invalid automap_rules format in project file, expected list"
                        )
                except Exception as e:
                    import logging

                    logging.error(f"Error loading automap rules: {e}", exc_info=True)
                    error_handler.capture(
                        e, context="load_automap_rules", severity="warning"
                    )
                    # Continue loading other data

        data_section = payload.get("data", {})

        if "layers" in data_section and data_section["layers"]:

            self.layer_manager.layers.clear()
            for layer_data in data_section["layers"]:
                layer = self._load_layer_from_dict(layer_data)
                self.layer_manager.layers.append(layer)

            if not self.layer_manager.layers:
                self.layer_manager.create_layer("Default")

            self.layer_manager.active_layer_idx = 0
        else:

            raw_ongrid = data_section.get("ongrid", {})
            if raw_ongrid:

                self.layer_manager.layers.clear()
                self.layer_manager.create_layer("Terrain")
                active_layer = self.layer_manager.get_active_layer()

                for loc_str, tile_data in raw_ongrid.items():
                    pos = deserialize_point(loc_str)
                    tile_data["pos"] = pos
                    self._normalize_ttype(tile_data)
                    if active_layer:
                        active_layer.tiles[pos] = tile_data

        self.initialized = True
        error_handler.capture(None, context="load_map")

    def load_map(self, path: Path):
        try:
            payload = self.read_map_payload(path)
            self.apply_map_payload(path, payload)
        except Exception as e:
            error_msg = f"Error loading map: {e}"
            error_handler.capture(Exception(error_msg), context="load_map")
            import logging

            logging.error(error_msg, exc_info=True)

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
        layer.properties = layer_data.get("properties", {})

        for loc_str, tile_data in layer_data.get("tiles", {}).items():
            pos = deserialize_point(loc_str)
            tile_copy = tile_data.copy()
            tile_copy["pos"] = pos
            if "properties" in tile_data:
                tile_copy["properties"] = tile_data["properties"]
            self._normalize_ttype(tile_copy)
            layer.tiles[pos] = tile_copy

        if layer.layer_type == "object":
            for obj_id_str, obj_data in layer_data.get("objects", {}).items():
                try:
                    obj_id = int(obj_id_str)

                    obj_copy: TypeObject = {
                        "area": obj_data.get(
                            "area", {"x": 0, "y": 0, "w": 32, "h": 32}
                        ),
                        "ttype": obj_data.get("ttype", 0),
                        "tileset_type": obj_data.get("tileset_type", "object"),
                        "variant": obj_data.get("variant", 0),
                        "properties": obj_data.get("properties", {}),
                    }
                    layer.objects[obj_id] = obj_copy

                    if obj_id >= layer.next_object_id:
                        layer.next_object_id = obj_id + 1
                except (ValueError, TypeError, KeyError):
                    pass

            if "next_object_id" in layer_data:
                layer.next_object_id = layer_data["next_object_id"]

        return layer

    def _normalize_ttype(self, tile_data: dict) -> None:
        """Normalize ttype field - convert path strings to indices if needed."""
        ttype = tile_data.get("ttype")
        if hasattr(self.editor, "tileset_widget") and self.editor.tileset_widget:
            ts_widget = self.editor.tileset_widget

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
