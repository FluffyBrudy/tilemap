from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import json

from layers import Layer
from ttypes.tilemap import (
    TypeTile,
    TypeTileSerealized,
    TypeObject,
    TypeObjectSerialized,
    TTile,
    TObject,
)
from utils.serialization import serialize_point, deserialize_point
from widgets.autotiler import AutotileRule


class TileLayerParser:
    @staticmethod
    def serialize_tiles(tiles: TTile) -> Dict[str, TypeTileSerealized]:
        return {
            serialize_point(pos): TileLayerParser.serialize_tile(tile)
            for pos, tile in tiles.items()
        }

    @staticmethod
    def serialize_tile(tile: TypeTile) -> TypeTileSerealized:
        data = TypeTileSerealized(
            pos=serialize_point(tile["pos"]),
            ttype=str(tile["ttype"]),
            variant=tile["variant"],
        )
        if "properties" in tile:
            data["properties"] = tile["properties"]
        return data

    @staticmethod
    def deserialize_tiles(data: Dict[str, TypeTileSerealized]) -> TTile:
        return {
            deserialize_point(pos_str): TileLayerParser.deserialize_tile(tile_data)
            for pos_str, tile_data in data.items()
        }

    @staticmethod
    def deserialize_tile(data: TypeTileSerealized) -> TypeTile:
        tile = TypeTile(
            pos=deserialize_point(data["pos"]),
            ttype=int(data["ttype"]),
            variant=data["variant"],
        )
        if "properties" in data:
            tile["properties"] = data["properties"]
        return tile


class ObjectLayerParser:
    @staticmethod
    def serialize_objects(objects: TObject) -> Dict[str, TypeObjectSerialized]:
        return {
            str(obj_id): ObjectLayerParser.serialize_object(obj)
            for obj_id, obj in objects.items()
        }

    @staticmethod
    def serialize_object(obj: TypeObject) -> TypeObjectSerialized:
        data = TypeObjectSerialized(
            area=obj["area"],
            ttype=obj["ttype"],
            tileset_type=obj["tileset_type"],
            variant=obj["variant"],
        )
        if "properties" in obj:
            data["properties"] = obj["properties"]
        return data

    @staticmethod
    def deserialize_objects(data: Dict[str, TypeObjectSerialized]) -> TObject:
        return {
            int(obj_id_str): ObjectLayerParser.deserialize_object(obj_data)
            for obj_id_str, obj_data in data.items()
        }

    @staticmethod
    def deserialize_object(data: TypeObjectSerialized) -> TypeObject:
        obj = TypeObject(
            area=data["area"],
            ttype=data["ttype"],
            tileset_type=data["tileset_type"],
            variant=data["variant"],
        )
        if "properties" in data:
            obj["properties"] = data["properties"]
        return obj


class AutotileParser:
    """Parse and serialize autotile rules including neighbors."""

    @staticmethod
    def serialize_rules(rules: List[AutotileRule]) -> List[dict]:
        return [
            {
                "name": rule.name,
                "neighbors": [list(n) for n in rule.neighbors],
                "tileset_path": rule.tileset_path,
                "tileset_index": rule.tileset_index,
                "variant_ids": rule.variant_ids,
            }
            for rule in rules
        ]

    @staticmethod
    def deserialize_rules(rules_data: List[dict]) -> List[AutotileRule]:
        rules: List[AutotileRule] = []
        for rd in rules_data:
            neighbors = {tuple(n) for n in rd.get("neighbors", [])}
            rule = AutotileRule(
                name=rd.get("name", "Unnamed"),
                neighbors=neighbors,
                tileset_path=rd.get("tileset_path", ""),
                variant_ids=rd.get("variant_ids", []),
                surface_subsurface=None,
                tileset_index=rd.get("tileset_index"),
            )
            rules.append(rule)
        return rules


class TilemapParser:
    """Fully typed parser for tiles, objects, and autotile rules."""

    def __init__(
        self,
        tile_size: Tuple[int, int] = (32, 32),
        map_size: Tuple[int, int] = (50, 50),
    ):
        self.tile_size = tile_size
        self.map_size = map_size
        self.initial_map_size = map_size
        self.zoom_level = 1.0
        self.scroll = (0, 0)

    def save_layer(self, layer: Layer) -> dict:
        layer_data = {
            "name": layer.name,
            "type": layer.layer_type,
            "visible": layer.visible,
            "locked": layer.locked,
            "opacity": layer.opacity,
            "z_index": layer.z_index,
            "tiles": TileLayerParser.serialize_tiles(layer.tiles),
            "properties": getattr(layer, "properties", {})
        }

        if layer.layer_type == "object":
            layer_data["objects"] = ObjectLayerParser.serialize_objects(layer.objects)
            layer_data["next_object_id"] = layer.next_object_id

        return layer_data

    def load_layer(self, data: dict) -> Layer:
        layer = Layer(
            name=data.get("name", "Unnamed"),
            layer_type=data.get("type", "tile"),
            visible=data.get("visible", True),
            locked=data.get("locked", False),
            opacity=data.get("opacity", 1.0),
            z_index=data.get("z_index", 0),
        )

        layer.properties = data.get("properties", {})
        layer.tiles = TileLayerParser.deserialize_tiles(data.get("tiles", {}))

        if layer.layer_type == "object":
            layer.objects = ObjectLayerParser.deserialize_objects(
                data.get("objects", {})
            )
            layer.next_object_id = data.get("next_object_id", layer.next_object_id)

        return layer

    def save_tilemap(
        self,
        layers: List[Layer],
        autotile_rules: Optional[List[AutotileRule]],
        path: Path,
        **kwargs
    ) -> None:
        """
        Save the tilemap to a JSON file.
        Accepts optional kwargs for metadata like zoom_level, scroll, etc.
        """
        payload = {
            "meta": {
                "tile_size": serialize_point(self.tile_size),
                "map_size": serialize_point(self.map_size),
                "initial_map_size": serialize_point(kwargs.get("initial_map_size", self.initial_map_size)),
                "zoom_level": kwargs.get("zoom_level", self.zoom_level),
                "scroll": serialize_point(kwargs.get("scroll", self.scroll)),
                "version": "1.1",
            },
            "project_state": {
                "rules": AutotileParser.serialize_rules(autotile_rules or [])
            },
            "data": {"layers": [self.save_layer(layer) for layer in layers]},
            "resources": kwargs.get("resources", {"tilesets": []})
        }
        
        # Support for groups if provided in kwargs
        if "groups" in kwargs:
             payload["project_state"]["groups"] = kwargs["groups"]

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)

    def load_tilemap(self, path: Path) -> Tuple[List[Layer], List[AutotileRule], dict]:
        """
        Load a tilemap and return layers, rules, and additional metadata.
        """
        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist")
        with open(path, "r") as f:
            payload = json.load(f)

        meta = payload.get("meta", {})
        self.tile_size = deserialize_point(meta.get("tile_size", "32;32"))
        self.map_size = deserialize_point(meta.get("map_size", "50;50"))
        self.initial_map_size = deserialize_point(meta.get("initial_map_size", serialize_point(self.map_size)))
        self.zoom_level = meta.get("zoom_level", 1.0)
        self.scroll = deserialize_point(meta.get("scroll", "0;0"))

        layers_data = payload.get("data", {}).get("layers", [])
        layers = [self.load_layer(ld) for ld in layers_data]

        project_state = payload.get("project_state", {})
        rules_data = project_state.get("rules", [])
        rules = AutotileParser.deserialize_rules(rules_data)
        
        # Also return the full payload or specific extra data if needed
        return layers, rules, payload
