from typing import TYPE_CHECKING, Any, Dict, List, Set, Tuple, Optional, cast
from pygame import Rect
from json import load as JSONLoad, dump as JSONDump
from pathlib import Path

from constants import BASE_PATH
from utils.serialization import deserialize_point, serialize_point
from ttypes.tilemap import TypeTile, TypeTileSerealized

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
        self.ongrid_tiles: TTile = {}
        self.offgrid_tiles: Set[TypeTile] = set()

        self.tile_size = (32, 32)
        self.map_size = (50, 50)
        self.initialized = False

        self.active_project_path: Optional[Path] = None

    def init_size(self, tile_size: "TCoor", map_size: "TCoor"):
        self.tile_size = tile_size
        self.map_size = map_size
        self.initialized = True
        self.active_project_path = None

    def get_nearest_tiles(self, tile_location: "TCoor") -> Tuple["TCoor"]:
        assert len(tile_location) == 2
        tiles_around = []
        if tile_location not in self.ongrid_tiles:
            return tuple(tiles_around)
        x, y = tile_location
        for nx, ny in NEAREST_NEIGHBOUR_OFFSET:
            check_loc = (x + nx, y + ny)
            if check_loc not in self.ongrid_tiles:
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
                "version": "1.0",
            },
            "resources": {"tilesets": []},
            "project_state": {"rules": []},
            "data": {"ongrid": {}, "offgrid": []},
        }

        if hasattr(self.editor, "tileset_widget") and self.editor.tileset_widget:
            for ts in self.editor.tileset_widget.tilesets:
                try:
                    rel = ts.path.relative_to(BASE_PATH)
                    save_data["resources"]["tilesets"].append(str(rel))
                except ValueError:
                    save_data["resources"]["tilesets"].append(str(ts.path))

        if hasattr(self.editor, "autotiler") and self.editor.autotiler:
            for rule in self.editor.autotiler.rules:
                save_data["project_state"]["rules"].append(rule.to_dict())

        for loc, tile in self.ongrid_tiles.items():
            key = serialize_point(loc)
            tile_copy = cast(TypeTileSerealized, tile.copy())

            tile_copy["pos"] = serialize_point(tile["pos"])

            save_data["data"]["ongrid"][key] = tile_copy

        for tile in self.offgrid_tiles:
            tile_copy = cast(TypeTileSerealized, tile.copy())
            tile_copy["pos"] = serialize_point(tile["pos"])
            save_data["data"]["offgrid"].append(tile_copy)

        with open(target_path, "w") as f:
            JSONDump(save_data, f, indent=2)

        print(f"Saved to {target_path}")

    def load_map(self, path: Path):
        if not path.exists():
            print(f"Error: {path} does not exist")
            return

        with open(path, "r") as f:
            payload = JSONLoad(f)

        self.ongrid_tiles.clear()
        self.offgrid_tiles.clear()
        self.active_project_path = path

        self.tile_size = deserialize_point(payload["meta"]["tile_size"])
        self.map_size = deserialize_point(payload["meta"].get("map_size", "50;50"))

        if hasattr(self.editor, "tileset_widget") and self.editor.tileset_widget:
            self.editor.tileset_widget.tilesets.clear()
            self.editor.tileset_widget.tileset_map.clear()

            for path_str in payload["resources"]["tilesets"]:
                p = Path(path_str)
                if not p.is_absolute():
                    p = BASE_PATH / p
                self.editor.tileset_widget.on_file_selected(p)

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

        raw_ongrid = payload["data"]["ongrid"]
        for loc_str, tile_data in raw_ongrid.items():
            pos = deserialize_point(loc_str)
            tile_data["pos"] = pos

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

            self.ongrid_tiles[pos] = tile_data

        for tile_data in payload["data"]["offgrid"]:
            tile_copy = tile_data.copy()
            tile_copy["pos"] = deserialize_point(tile_data["pos"])
            self.offgrid_tiles.add(tile_copy)

        self.initialized = True
        print(f"Map Loaded: {path.name}")
