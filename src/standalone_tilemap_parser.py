from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

JsonDict = Dict[str, Any]
Point = Tuple[int, int]


def _require_dict(value: Any, ctx: str) -> JsonDict:
    if not isinstance(value, dict):
        raise TypeError(f"{ctx}: expected object")
    return value


def _require_list(value: Any, ctx: str) -> List[Any]:
    if not isinstance(value, list):
        raise TypeError(f"{ctx}: expected array")
    return value


def _require_str(value: Any, ctx: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{ctx}: expected string")
    return value


def _require_int(value: Any, ctx: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{ctx}: expected int")
    return value


def _require_float(value: Any, ctx: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{ctx}: expected float")
    return float(value)


def _require_bool(value: Any, ctx: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{ctx}: expected bool")
    return value


def _optional_dict(value: Any, ctx: str) -> Optional[JsonDict]:
    if value is None:
        return None
    return _require_dict(value, ctx)


def _parse_point(text: str, ctx: str) -> Point:
    try:
        x_str, y_str = text.split(";")
        return int(x_str), int(y_str)
    except Exception as exc:
        raise ValueError(f"{ctx}: invalid point '{text}'") from exc


def _coerce_int(value: Any, ctx: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{ctx}: expected int")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except Exception as exc:
            raise TypeError(f"{ctx}: expected int-like string") from exc
    raise TypeError(f"{ctx}: expected int")


@dataclass
class Tile:
    pos: Point
    ttype: int
    variant: int
    properties: Optional[JsonDict] = None


@dataclass
class ObjectArea:
    x: int
    y: int
    w: int
    h: int


@dataclass
class ObjectSprite:
    area: ObjectArea
    ttype: int
    tileset_type: str
    variant: int
    properties: Optional[JsonDict] = None


@dataclass
class Layer:
    name: str
    layer_type: str
    visible: bool
    locked: bool
    opacity: float
    z_index: int
    tiles: Dict[Point, Tile] = field(default_factory=dict)
    objects: Dict[int, ObjectSprite] = field(default_factory=dict)
    next_object_id: Optional[int] = None
    properties: Optional[JsonDict] = None


@dataclass
class AutotileRule:
    name: str
    neighbors: List[Point]
    tileset_path: str
    tileset_index: Optional[int]
    variant_ids: List[int]
    group_id: Optional[str] = None


@dataclass
class AutotileGroup:
    name: str
    rules: List[AutotileRule]


@dataclass
class TilesetResource:
    path: str
    type: str
    properties: Optional[JsonDict] = None
    tile_properties: Optional[Dict[str, JsonDict]] = None


@dataclass
class TilemapMeta:
    tile_size: Point
    map_size: Point
    initial_map_size: Point
    zoom_level: float
    scroll: Point
    version: str


@dataclass
class TilemapProjectState:
    rules: List[AutotileRule]
    groups: List[AutotileGroup]


@dataclass
class TilemapData:
    layers: List[Layer]


@dataclass
class TilemapResources:
    tilesets: List[TilesetResource]


@dataclass
class Tilemap:
    meta: TilemapMeta
    project_state: TilemapProjectState
    data: TilemapData
    resources: TilemapResources
    raw: JsonDict


def _parse_tile(tile_data: JsonDict, ctx: str) -> Tile:
    pos_str = _require_str(tile_data.get("pos"), f"{ctx}.pos")
    ttype = _coerce_int(tile_data.get("ttype"), f"{ctx}.ttype")
    variant = _require_int(tile_data.get("variant"), f"{ctx}.variant")
    props = _optional_dict(tile_data.get("properties"), f"{ctx}.properties")
    return Tile(
        pos=_parse_point(pos_str, f"{ctx}.pos"),
        ttype=ttype,
        variant=variant,
        properties=props,
    )


def _parse_tiles(tiles_obj: JsonDict, ctx: str) -> Dict[Point, Tile]:
    result: Dict[Point, Tile] = {}
    for key, value in tiles_obj.items():
        tile_dict = _require_dict(value, f"{ctx}.{key}")
        tile = _parse_tile(tile_dict, f"{ctx}.{key}")
        result[tile.pos] = tile
    return result


def _parse_object_area(area_obj: JsonDict, ctx: str) -> ObjectArea:
    return ObjectArea(
        x=_require_int(area_obj.get("x"), f"{ctx}.x"),
        y=_require_int(area_obj.get("y"), f"{ctx}.y"),
        w=_require_int(area_obj.get("w"), f"{ctx}.w"),
        h=_require_int(area_obj.get("h"), f"{ctx}.h"),
    )


def _parse_objects(objs_obj: JsonDict, ctx: str) -> Dict[int, ObjectSprite]:
    result: Dict[int, ObjectSprite] = {}
    for key, value in objs_obj.items():
        obj_id = _coerce_int(key, f"{ctx}.<id>")
        obj_dict = _require_dict(value, f"{ctx}.{key}")
        area_dict = _require_dict(obj_dict.get("area"), f"{ctx}.{key}.area")
        area = _parse_object_area(area_dict, f"{ctx}.{key}.area")
        obj = ObjectSprite(
            area=area,
            ttype=_require_int(obj_dict.get("ttype"), f"{ctx}.{key}.ttype"),
            tileset_type=_require_str(
                obj_dict.get("tileset_type"), f"{ctx}.{key}.tileset_type"
            ),
            variant=_require_int(obj_dict.get("variant"), f"{ctx}.{key}.variant"),
            properties=_optional_dict(
                obj_dict.get("properties"), f"{ctx}.{key}.properties"
            ),
        )
        result[obj_id] = obj
    return result


def _parse_layer(layer_obj: JsonDict, ctx: str) -> Layer:
    layer = Layer(
        name=_require_str(layer_obj.get("name"), f"{ctx}.name"),
        layer_type=_require_str(layer_obj.get("type"), f"{ctx}.type"),
        visible=_require_bool(layer_obj.get("visible"), f"{ctx}.visible"),
        locked=_require_bool(layer_obj.get("locked"), f"{ctx}.locked"),
        opacity=_require_float(layer_obj.get("opacity"), f"{ctx}.opacity"),
        z_index=_require_int(layer_obj.get("z_index"), f"{ctx}.z_index"),
        properties=_optional_dict(layer_obj.get("properties"), f"{ctx}.properties"),
    )
    tiles_obj = _require_dict(layer_obj.get("tiles"), f"{ctx}.tiles")
    layer.tiles = _parse_tiles(tiles_obj, f"{ctx}.tiles")

    if layer.layer_type == "object":
        objs_obj = _require_dict(layer_obj.get("objects"), f"{ctx}.objects")
        layer.objects = _parse_objects(objs_obj, f"{ctx}.objects")
        if "next_object_id" in layer_obj:
            layer.next_object_id = _require_int(
                layer_obj.get("next_object_id"), f"{ctx}.next_object_id"
            )
    return layer


def _parse_rule(rule_obj: JsonDict, ctx: str) -> AutotileRule:
    neighbors_raw = _require_list(rule_obj.get("neighbors"), f"{ctx}.neighbors")
    neighbors: List[Point] = []
    for idx, pair in enumerate(neighbors_raw):
        pair_list = _require_list(pair, f"{ctx}.neighbors[{idx}]")
        if len(pair_list) != 2:
            raise ValueError(f"{ctx}.neighbors[{idx}]: expected [x, y]")
        neighbors.append(
            (
                _coerce_int(pair_list[0], f"{ctx}.neighbors[{idx}][0]"),
                _coerce_int(pair_list[1], f"{ctx}.neighbors[{idx}][1]"),
            )
        )
    variant_ids_raw = rule_obj.get("variant_ids", [])
    variant_ids: List[int] = []
    for i, v in enumerate(_require_list(variant_ids_raw, f"{ctx}.variant_ids")):
        variant_ids.append(_coerce_int(v, f"{ctx}.variant_ids[{i}]"))
    return AutotileRule(
        name=_require_str(rule_obj.get("name"), f"{ctx}.name"),
        neighbors=neighbors,
        tileset_path=_require_str(
            rule_obj.get("tileset_path", ""), f"{ctx}.tileset_path"
        ),
        tileset_index=(
            _coerce_int(rule_obj.get("tileset_index"), f"{ctx}.tileset_index")
            if rule_obj.get("tileset_index") is not None
            else None
        ),
        variant_ids=variant_ids,
        group_id=rule_obj.get("group_id"),
    )


def _parse_group(group_obj: JsonDict, ctx: str) -> AutotileGroup:
    rules_raw = _require_list(group_obj.get("rules", []), f"{ctx}.rules")
    rules = [
        _parse_rule(_require_dict(r, f"{ctx}.rules[{i}]"), f"{ctx}.rules[{i}]")
        for i, r in enumerate(rules_raw)
    ]
    return AutotileGroup(
        name=_require_str(group_obj.get("name"), f"{ctx}.name"), rules=rules
    )


def _parse_tilesets(resources_obj: JsonDict, ctx: str) -> List[TilesetResource]:
    tilesets_raw = _require_list(resources_obj.get("tilesets", []), f"{ctx}.tilesets")
    tilesets: List[TilesetResource] = []
    for i, ts in enumerate(tilesets_raw):
        ts_obj = _require_dict(ts, f"{ctx}.tilesets[{i}]")
        tilesets.append(
            TilesetResource(
                path=_require_str(ts_obj.get("path"), f"{ctx}.tilesets[{i}].path"),
                type=_require_str(ts_obj.get("type"), f"{ctx}.tilesets[{i}].type"),
                properties=_optional_dict(
                    ts_obj.get("properties"), f"{ctx}.tilesets[{i}].properties"
                ),
                tile_properties=_optional_dict(
                    ts_obj.get("tile_properties"),
                    f"{ctx}.tilesets[{i}].tile_properties",
                ),
            )
        )
    return tilesets


def parse_tilemap_dict(payload: JsonDict) -> Tilemap:
    root = _require_dict(payload, "payload")

    meta_obj = _require_dict(root.get("meta"), "payload.meta")
    tile_size = _parse_point(
        _require_str(meta_obj.get("tile_size"), "payload.meta.tile_size"),
        "payload.meta.tile_size",
    )
    map_size = _parse_point(
        _require_str(meta_obj.get("map_size"), "payload.meta.map_size"),
        "payload.meta.map_size",
    )
    initial_map_size_str = meta_obj.get(
        "initial_map_size", f"{map_size[0]};{map_size[1]}"
    )
    initial_map_size = _parse_point(
        _require_str(initial_map_size_str, "payload.meta.initial_map_size"),
        "payload.meta.initial_map_size",
    )
    zoom_level = _require_float(
        meta_obj.get("zoom_level", 1.0), "payload.meta.zoom_level"
    )
    scroll = _parse_point(
        _require_str(meta_obj.get("scroll", "0;0"), "payload.meta.scroll"),
        "payload.meta.scroll",
    )
    version = _require_str(meta_obj.get("version", "1.1"), "payload.meta.version")
    meta = TilemapMeta(
        tile_size=tile_size,
        map_size=map_size,
        initial_map_size=initial_map_size,
        zoom_level=zoom_level,
        scroll=scroll,
        version=version,
    )

    data_obj = _require_dict(root.get("data"), "payload.data")
    layers_raw = _require_list(data_obj.get("layers", []), "payload.data.layers")
    layers = [
        _parse_layer(
            _require_dict(layer, f"payload.data.layers[{i}]"),
            f"payload.data.layers[{i}]",
        )
        for i, layer in enumerate(layers_raw)
    ]
    data = TilemapData(layers=layers)

    project_state_obj = _require_dict(
        root.get("project_state", {}), "payload.project_state"
    )
    rules_raw = _require_list(
        project_state_obj.get("rules", []), "payload.project_state.rules"
    )
    rules = [
        _parse_rule(
            _require_dict(rule, f"payload.project_state.rules[{i}]"),
            f"payload.project_state.rules[{i}]",
        )
        for i, rule in enumerate(rules_raw)
    ]
    groups_raw = _require_list(
        project_state_obj.get("groups", []), "payload.project_state.groups"
    )
    groups = [
        _parse_group(
            _require_dict(group, f"payload.project_state.groups[{i}]"),
            f"payload.project_state.groups[{i}]",
        )
        for i, group in enumerate(groups_raw)
    ]
    project_state = TilemapProjectState(rules=rules, groups=groups)

    resources_obj = _require_dict(
        root.get("resources", {"tilesets": []}), "payload.resources"
    )
    resources = TilemapResources(
        tilesets=_parse_tilesets(resources_obj, "payload.resources")
    )

    return Tilemap(
        meta=meta, project_state=project_state, data=data, resources=resources, raw=root
    )


def parse_tilemap_json(text: str) -> Tilemap:
    payload = json.loads(text)
    return parse_tilemap_dict(_require_dict(payload, "payload"))


def parse_tilemap_file(path: Union[str, Path]) -> Tilemap:
    p = Path(path)
    with open(p, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return parse_tilemap_dict(_require_dict(payload, "payload"))


print(
    parse_tilemap_file("/home/rudy/Documents/games/rpg/map/0.json")
    .resources.tilesets[0]
    .tile_properties
)
