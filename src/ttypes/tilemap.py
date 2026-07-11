from typing import Dict, Tuple, TypedDict, Any, NotRequired


class TypeTile(TypedDict, total=True):
    pos: Tuple[int, int]
    ttype: int
    variant: int
    properties: NotRequired[Dict[str, Any]]


class TypeArea(TypedDict, total=True):
    """Area/bounds of an object: x, y, width, height in pixels"""

    x: int
    y: int
    w: int
    h: int


class TypeObject(TypedDict, total=True):
    """Object sprite on a layer (free pixel placement, draggable)

    For single objects: area defines the bounds
    For tiled regions: area defines the total region, variant defines top-left tile
    """

    area: TypeArea
    ttype: int
    tileset_type: str
    variant: int
    properties: NotRequired[Dict[str, Any]]


class TypeTileSerealized(TypedDict, total=True):
    pos: str
    ttype: str
    variant: int
    properties: NotRequired[Dict[str, Any]]


class TypeObjectSerialized(TypedDict, total=True):
    area: TypeArea
    ttype: int
    tileset_type: str
    variant: int
    properties: NotRequired[Dict[str, Any]]


class TypeLayerSerialized(TypedDict, total=True):
    name: str
    type: str
    visible: bool
    locked: bool
    opacity: float
    z_index: int
    tiles: Dict[str, TypeTileSerealized]
    objects: NotRequired[Dict[str, TypeObjectSerialized]]
    next_object_id: NotRequired[int]
    properties: NotRequired[Dict[str, Any]]


class TypeTilesetSerialized(TypedDict, total=True):
    path: str
    type: str
    properties: NotRequired[Dict[str, Any]]
    tile_properties: NotRequired[Dict[str, Dict[str, Any]]]
    animation: NotRequired[dict]


TTile = Dict[Tuple[int, int], TypeTile]
TObject = Dict[int, TypeObject]
TOngridParsedTile = Dict[str, TypeTileSerealized]
TOngridParsedObject = Dict[str, TypeObjectSerialized]
