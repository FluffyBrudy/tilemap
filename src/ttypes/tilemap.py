from typing import Dict, Tuple, TypedDict


class TypeTile(TypedDict, total=True):
    pos: Tuple[int, int]
    ttype: int
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

    area: TypeArea
    ttype: int
    tileset_type: str
    variant: int


class TypeTileSerealized(TypedDict, total=True):
    pos: str
    ttype: str
    variant: int


class TypeObjectSerialized(TypedDict, total=True):
    area: TypeArea
    ttype: int
    tileset_type: str
    variant: int


TTile = Dict[Tuple[int, int], TypeTile]
TObject = Dict[int, TypeObject]
TOngridParsedTile = Dict[str, TypeTileSerealized]
TOngridParsedObject = Dict[str, TypeObjectSerialized]
