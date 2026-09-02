from typing import Any, NotRequired, TypedDict


class TypeTile(TypedDict, total=True):
    pos: tuple[int, int]
    ttype: int
    variant: int
    autotile_group: NotRequired[str]
    gid: NotRequired[int]
    properties: NotRequired[dict[str, Any]]


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
    properties: NotRequired[dict[str, Any]]
    animation: NotRequired[dict[str, Any]]


class TypeTileSerealized(TypedDict, total=True):
    pos: str
    ttype: str
    variant: int
    autotile_group: NotRequired[str]
    gid: NotRequired[int]
    properties: NotRequired[dict[str, Any]]


class TypeObjectSerialized(TypedDict, total=True):
    area: TypeArea
    ttype: int
    tileset_type: str
    variant: int
    properties: NotRequired[dict[str, Any]]
    animation: NotRequired[dict[str, Any]]


class TypeLayerSerialized(TypedDict, total=True):
    name: str
    type: str
    visible: bool
    locked: bool
    opacity: float
    z_index: int
    tiles: dict[str, TypeTileSerealized]
    objects: NotRequired[dict[str, TypeObjectSerialized]]
    next_object_id: NotRequired[int]
    properties: NotRequired[dict[str, Any]]
    image_path: NotRequired[str | None]
    image_rect: NotRequired[TypeArea | None]


class TypeTilesetSerialized(TypedDict, total=True):
    path: str
    type: str
    tile_count: NotRequired[int]
    firstgid: NotRequired[int]
    properties: NotRequired[dict[str, Any]]
    tile_properties: NotRequired[dict[str, dict[str, Any]]]
    animation: NotRequired[dict]


TTile = dict[tuple[int, int], TypeTile]
TObject = dict[int, TypeObject]
TOngridParsedTile = dict[str, TypeTileSerealized]
TOngridParsedObject = dict[str, TypeObjectSerialized]
