"""
Strict, synchronous parser for tilemap editor JSON (version 1.1+).

The root JSON object matches what ``Tilemap.save_map`` writes: ``meta``, ``data``,
``resources``, and optional ``project_state``. This is **not** wrapped in a
``payload`` key (unlike some older external loaders).

Use :func:`parse_tilemap_file` or :func:`parse_tilemap_json` in game code after
reading bytes; use :mod:`runtime.tilemap_runtime` to load images and query pixels.
"""

from __future__ import annotations

import json
import re
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

JsonDict = Dict[str, Any]
Point = Tuple[int, int]
TType = Union[int, str]


class MapParseError(ValueError):
    """Invalid map JSON or schema violation; ``args[0]`` is a human-readable path."""


def _ctx(path: str, detail: str) -> str:
    return f"{path}: {detail}"


def _require_dict(value: Any, path: str) -> JsonDict:
    if not isinstance(value, dict):
        raise MapParseError(_ctx(path, "expected object"))
    return value


def _require_list(value: Any, path: str) -> List[Any]:
    if not isinstance(value, list):
        raise MapParseError(_ctx(path, "expected array"))
    return value


def _require_str(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise MapParseError(_ctx(path, "expected string"))
    return value


def _optional_str(value: Any, path: str) -> Optional[str]:
    if value is None:
        return None
    return _require_str(value, path)


def _coerce_int(value: Any, path: str) -> int:
    if isinstance(value, bool):
        raise MapParseError(_ctx(path, "expected int (got bool)"))
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 10)
        except ValueError as e:
            raise MapParseError(_ctx(path, "expected int")) from e
    raise MapParseError(_ctx(path, "expected int"))


def _coerce_float(value: Any, path: str) -> float:
    if isinstance(value, bool):
        raise MapParseError(_ctx(path, "expected number (got bool)"))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as e:
            raise MapParseError(_ctx(path, "expected number")) from e
    raise MapParseError(_ctx(path, "expected number"))


def _coerce_bool(value: Any, path: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    raise MapParseError(_ctx(path, "expected bool"))


def _optional_dict(value: Any, path: str) -> Optional[JsonDict]:
    if value is None:
        return None
    return _require_dict(value, path)


def _parse_point(text: str, path: str) -> Point:
    if not isinstance(text, str):
        raise MapParseError(_ctx(path, "expected point string"))
    matched = re.search(rf"(-?\d+)[{re.escape(string.punctuation)}](-?\d+)$", text.strip())
    if matched is None:
        raise MapParseError(_ctx(path, f"invalid point {text!r}"))
    return int(matched.group(1)), int(matched.group(2))


def _parse_point_field(raw: Any, path: str, default: Optional[str] = None) -> Point:
    if raw is None and default is not None:
        return _parse_point(default, path)
    if not isinstance(raw, str):
        raise MapParseError(_ctx(path, "expected serialized point string"))
    return _parse_point(raw, path)


@dataclass
class ParsedTile:
    pos: Point
    ttype: TType
    variant: int
    properties: Optional[JsonDict] = None


@dataclass
class ParsedObjectArea:
    x: int
    y: int
    w: int
    h: int


@dataclass
class ParsedObject:
    area: ParsedObjectArea
    ttype: int
    tileset_type: str
    variant: int
    properties: Optional[JsonDict] = None


@dataclass
class ParsedTileset:
    path: str
    type: str
    properties: JsonDict = field(default_factory=dict)
    tile_properties: Dict[str, JsonDict] = field(default_factory=dict)


@dataclass
class ParsedLayer:
    name: str
    layer_type: str
    visible: bool
    locked: bool
    opacity: float
    z_index: int
    properties: JsonDict = field(default_factory=dict)
    tiles: Dict[Point, ParsedTile] = field(default_factory=dict)
    objects: Dict[int, ParsedObject] = field(default_factory=dict)
    next_object_id: Optional[int] = None


@dataclass
class ParsedAutotileRule:
    name: str
    neighbors: List[Point]
    tileset_path: str
    tileset_index: Optional[int]
    variant_ids: List[int]
    group_id: Optional[Any] = None
    raw: JsonDict = field(default_factory=dict)


@dataclass
class ParsedAutotileGroup:
    name: str
    rules: List[ParsedAutotileRule]


@dataclass
class ParsedMeta:
    tile_size: Point
    map_size: Point
    initial_map_size: Point
    zoom_level: float
    scroll: Point
    version: str


@dataclass
class ParsedProjectState:
    rules: List[ParsedAutotileRule]
    groups: List[ParsedAutotileGroup]
    automap_rules: Any


@dataclass
class ParsedTilemap:
    meta: ParsedMeta
    layers: List[ParsedLayer]
    tilesets: List[ParsedTileset]
    project_state: ParsedProjectState
    raw: JsonDict


def _parse_tile(tile_data: JsonDict, ctx: str) -> ParsedTile:
    pos_raw = tile_data.get("pos")
    if not isinstance(pos_raw, str):
        raise MapParseError(_ctx(f"{ctx}.pos", "expected string"))
    pos = _parse_point(pos_raw, f"{ctx}.pos")
    variant = _coerce_int(tile_data.get("variant"), f"{ctx}.variant")
    ttype_raw = tile_data.get("ttype", 0)
    if isinstance(ttype_raw, str):
        ttype: TType = ttype_raw
    else:
        ttype = _coerce_int(ttype_raw, f"{ctx}.ttype")
    props = _optional_dict(tile_data.get("properties"), f"{ctx}.properties")
    return ParsedTile(pos=pos, ttype=ttype, variant=variant, properties=props)


def _parse_tiles(tiles_obj: JsonDict, ctx: str) -> Dict[Point, ParsedTile]:
    result: Dict[Point, ParsedTile] = {}
    for key, value in tiles_obj.items():
        tile_dict = _require_dict(value, f"{ctx}[{key!r}]")
        tile = _parse_tile(tile_dict, f"{ctx}[{key!r}]")
        result[tile.pos] = tile
    return result


def _parse_object_area(area_obj: JsonDict, ctx: str) -> ParsedObjectArea:
    return ParsedObjectArea(
        x=_coerce_int(area_obj.get("x"), f"{ctx}.x"),
        y=_coerce_int(area_obj.get("y"), f"{ctx}.y"),
        w=_coerce_int(area_obj.get("w"), f"{ctx}.w"),
        h=_coerce_int(area_obj.get("h"), f"{ctx}.h"),
    )


def _parse_objects(objs_obj: JsonDict, ctx: str) -> Dict[int, ParsedObject]:
    result: Dict[int, ParsedObject] = {}
    for key, value in objs_obj.items():
        oid = _coerce_int(key, f"{ctx}.<id>")
        obj_dict = _require_dict(value, f"{ctx}.{key}")
        area_dict = _require_dict(obj_dict.get("area"), f"{ctx}.{key}.area")
        area = _parse_object_area(area_dict, f"{ctx}.{key}.area")
        ttype = _coerce_int(obj_dict.get("ttype"), f"{ctx}.{key}.ttype")
        tst = obj_dict.get("tileset_type", "object")
        if not isinstance(tst, str):
            raise MapParseError(_ctx(f"{ctx}.{key}.tileset_type", "expected string"))
        variant = _coerce_int(obj_dict.get("variant"), f"{ctx}.{key}.variant")
        props = _optional_dict(obj_dict.get("properties"), f"{ctx}.{key}.properties")
        result[oid] = ParsedObject(
            area=area, ttype=ttype, tileset_type=tst, variant=variant, properties=props
        )
    return result


def _parse_layer(layer_obj: JsonDict, ctx: str) -> ParsedLayer:
    name = _require_str(layer_obj.get("name"), f"{ctx}.name")
    ltype = _require_str(layer_obj.get("type"), f"{ctx}.type")
    visible = _coerce_bool(layer_obj.get("visible", True), f"{ctx}.visible")
    locked = _coerce_bool(layer_obj.get("locked", False), f"{ctx}.locked")
    opacity = _coerce_float(layer_obj.get("opacity", 1.0), f"{ctx}.opacity")
    z_index = _coerce_int(layer_obj.get("z_index", 0), f"{ctx}.z_index")
    props = _optional_dict(layer_obj.get("properties"), f"{ctx}.properties") or {}

    layer = ParsedLayer(
        name=name,
        layer_type=ltype,
        visible=visible,
        locked=locked,
        opacity=opacity,
        z_index=z_index,
        properties=props,
    )

    tiles_obj = _require_dict(layer_obj.get("tiles", {}), f"{ctx}.tiles")
    layer.tiles = _parse_tiles(tiles_obj, f"{ctx}.tiles")

    if ltype == "object":
        objs_obj = _require_dict(layer_obj.get("objects", {}), f"{ctx}.objects")
        layer.objects = _parse_objects(objs_obj, f"{ctx}.objects")
        if "next_object_id" in layer_obj and layer_obj["next_object_id"] is not None:
            layer.next_object_id = _coerce_int(layer_obj["next_object_id"], f"{ctx}.next_object_id")

    return layer


def _parse_rule(rule_obj: JsonDict, ctx: str) -> ParsedAutotileRule:
    neighbors_raw = _require_list(rule_obj.get("neighbors", []), f"{ctx}.neighbors")
    neighbors: List[Point] = []
    for idx, pair in enumerate(neighbors_raw):
        pair_list = _require_list(pair, f"{ctx}.neighbors[{idx}]")
        if len(pair_list) != 2:
            raise MapParseError(_ctx(f"{ctx}.neighbors[{idx}]", "expected [x, y]"))
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
    tsp = rule_obj.get("tileset_path", "") or ""
    if not isinstance(tsp, str):
        raise MapParseError(_ctx(f"{ctx}.tileset_path", "expected string"))
    tidx = rule_obj.get("tileset_index")
    tileset_index = _coerce_int(tidx, f"{ctx}.tileset_index") if tidx is not None else None
    name = _require_str(rule_obj.get("name"), f"{ctx}.name")
    gid = rule_obj.get("group_id")
    return ParsedAutotileRule(
        name=name,
        neighbors=neighbors,
        tileset_path=tsp,
        tileset_index=tileset_index,
        variant_ids=variant_ids,
        group_id=gid,
        raw=dict(rule_obj),
    )


def _parse_group(group_obj: JsonDict, ctx: str) -> ParsedAutotileGroup:
    rules_raw = _require_list(group_obj.get("rules", []), f"{ctx}.rules")
    rules = [
        _parse_rule(_require_dict(r, f"{ctx}.rules[{i}]"), f"{ctx}.rules[{i}]")
        for i, r in enumerate(rules_raw)
    ]
    return ParsedAutotileGroup(name=_require_str(group_obj.get("name"), f"{ctx}.name"), rules=rules)


def _parse_tilesets_list(tilesets_raw: List[Any], ctx: str) -> List[ParsedTileset]:
    out: List[ParsedTileset] = []
    for i, ts in enumerate(tilesets_raw):
        if isinstance(ts, str):
            out.append(ParsedTileset(path=ts, type="tile"))
            continue
        ts_obj = _require_dict(ts, f"{ctx}[{i}]")
        path = _require_str(ts_obj.get("path"), f"{ctx}[{i}].path")
        tst = ts_obj.get("type", "tile")
        if not isinstance(tst, str):
            raise MapParseError(_ctx(f"{ctx}[{i}].type", "expected string"))
        props = _optional_dict(ts_obj.get("properties"), f"{ctx}[{i}].properties") or {}
        tp_raw = ts_obj.get("tile_properties")
        tile_props: Dict[str, JsonDict] = {}
        if tp_raw is not None:
            tp_dict = _require_dict(tp_raw, f"{ctx}[{i}].tile_properties")
            for k, v in tp_dict.items():
                if not isinstance(k, str):
                    k = str(k)
                tile_props[k] = _require_dict(v, f"{ctx}[{i}].tile_properties[{k!r}]")
        out.append(
            ParsedTileset(path=path, type=tst, properties=props, tile_properties=tile_props)
        )
    return out


def _parse_resources(resources_raw: Any, ctx: str) -> List[ParsedTileset]:
    if isinstance(resources_raw, list):
        return _parse_tilesets_list(resources_raw, f"{ctx} (list form)")
    res_obj = _require_dict(resources_raw, ctx)
    tilesets_raw = _require_list(res_obj.get("tilesets", []), f"{ctx}.tilesets")
    return _parse_tilesets_list(tilesets_raw, f"{ctx}.tilesets")


def _expand_ongrid_to_layer(data_obj: JsonDict, ctx: str) -> List[ParsedLayer]:
    raw_ongrid = _require_dict(data_obj.get("ongrid", {}), f"{ctx}.ongrid")
    layer = ParsedLayer(
        name="Terrain",
        layer_type="tile",
        visible=True,
        locked=False,
        opacity=1.0,
        z_index=0,
        properties={},
    )
    for loc_str, tile_data in raw_ongrid.items():
        tile_dict = _require_dict(tile_data, f"{ctx}.ongrid[{loc_str!r}]")
        if "pos" not in tile_dict:
            tile_dict = {**tile_dict, "pos": str(loc_str)}
        key = str(loc_str)
        chunk = _parse_tiles({key: tile_dict}, f"{ctx}.ongrid")
        layer.tiles.update(chunk)
    return [layer]


def parse_tilemap_dict(root: JsonDict) -> ParsedTilemap:
    """Parse a map dict (the JSON root object). Raises :exc:`MapParseError` on failure."""
    root = _require_dict(root, "root")

    meta_obj = _require_dict(root.get("meta"), "meta")
    tile_size = _parse_point_field(meta_obj.get("tile_size"), "meta.tile_size")
    map_size = _parse_point_field(meta_obj.get("map_size"), "meta.map_size", default=f"{tile_size[0]};{tile_size[1]}")
    init_raw = meta_obj.get("initial_map_size")
    if init_raw is None:
        initial_map_size = map_size
    else:
        initial_map_size = _parse_point_field(init_raw, "meta.initial_map_size")
    zoom_level = _coerce_float(meta_obj.get("zoom_level", 1.0), "meta.zoom_level")
    scroll = _parse_point_field(meta_obj.get("scroll"), "meta.scroll", default="0;0")
    version = _require_str(meta_obj.get("version", "1.1"), "meta.version")

    meta = ParsedMeta(
        tile_size=tile_size,
        map_size=map_size,
        initial_map_size=initial_map_size,
        zoom_level=zoom_level,
        scroll=scroll,
        version=version,
    )

    data_obj = _require_dict(root.get("data"), "data")
    layers_raw = data_obj.get("layers")
    if layers_raw is None:
        layers: List[ParsedLayer] = []
    else:
        layers = [
            _parse_layer(
                _require_dict(layer, f"data.layers[{i}]"),
                f"data.layers[{i}]",
            )
            for i, layer in enumerate(_require_list(layers_raw, "data.layers"))
        ]

    if not layers:
        layers = _expand_ongrid_to_layer(data_obj, "data")

    ps_obj = _require_dict(root.get("project_state", {}), "project_state")
    rules = [
        _parse_rule(_require_dict(r, f"project_state.rules[{i}]"), f"project_state.rules[{i}]")
        for i, r in enumerate(_require_list(ps_obj.get("rules", []), "project_state.rules"))
    ]
    groups = [
        _parse_group(_require_dict(g, f"project_state.groups[{i}]"), f"project_state.groups[{i}]")
        for i, g in enumerate(_require_list(ps_obj.get("groups", []), "project_state.groups"))
    ]
    automap = ps_obj.get("automap_rules")

    project_state = ParsedProjectState(rules=rules, groups=groups, automap_rules=automap)

    tilesets = _parse_resources(root.get("resources", {}), "resources")

    return ParsedTilemap(
        meta=meta,
        layers=layers,
        tilesets=tilesets,
        project_state=project_state,
        raw=root,
    )


def parse_tilemap_json(text: str) -> ParsedTilemap:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        raise MapParseError(f"Invalid JSON: {e}") from e
    return parse_tilemap_dict(_require_dict(payload, "root"))


def parse_tilemap_file(path: Union[str, Path]) -> ParsedTilemap:
    p = Path(path)
    if not p.is_file():
        raise MapParseError(f"Not a file: {p}")
    if p.suffix.lower() != ".json":
        raise MapParseError(f"Expected .json map file, got {p.suffix!r}")
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        raise MapParseError(f"Cannot read {p}: {e}") from e
    return parse_tilemap_json(text)
