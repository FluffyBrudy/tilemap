from typing import Dict, Tuple, TypedDict


class TypeTile(TypedDict, total=True):
    pos: Tuple[int, int]
    ttype: str
    variant: int


class TypeTileSerealized(TypedDict, total=True):
    pos: str
    ttype: str
    variant: int


TTile = Dict[Tuple[int, int], TypeTile]
TOngridParsedTile = Dict[str, TypeTileSerealized]
