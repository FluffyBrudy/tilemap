from typing import Dict, Tuple, TypedDict


class TypeTile(TypedDict, total=True):
    pos: Tuple[int, int]
    ttype: str
    variant: int


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

    area: TypeArea  # Bounding box: x, y, w, h in pixels
    ttype: int  # Tileset index (which tileset this came from)
    tileset_type: str  # "tile" or "object" - type of tileset used
    variant: int  # Which sprite in tileset (or top-left tile for multi-tile objects)


class TypeTileSerealized(TypedDict, total=True):
    pos: str
    ttype: str
    variant: int


class TypeObjectSerialized(TypedDict, total=True):
    area: TypeArea  # area dict is already serializable
    ttype: int  # Tileset index
    tileset_type: str  # "tile" or "object"
    variant: int


TTile = Dict[Tuple[int, int], TypeTile]
TObject = Dict[int, TypeObject]  # object_id -> TypeObject
TOngridParsedTile = Dict[str, TypeTileSerealized]
TOngridParsedObject = Dict[str, TypeObjectSerialized]
