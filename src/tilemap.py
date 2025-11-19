from typing import TYPE_CHECKING, Any, Dict, Sequence, Set, Tuple
from pygame.typing import RectLike

from pygame import Rect, Surface
from json import load as JSONLoad, dump as JSONDump

from constants import BASE_PATH
from ttypes.tilemap import TOngridParsedTile, TypeTile
from utils.load_utils import deserialize_point, serialize_point

if TYPE_CHECKING:
    from src.ttypes import TTile, TCoor

# fmt: off
NEAREST_NEIGHBOUR_OFFSET = (
    (-1, -1), (0, -1), (1, -1),
    (-1, 0),  (0, 0),  (1, 0),
    (-1, 1),  (0, 1),  (1, 1)
)
# fmt: on


class Tilemap:
    """
    Note: must call init_size before using tilemap
    """

    def __init__(self):
        self.ongrid_tiles: TTile = {}
        self.offgrid_tiles: Set[TypeTile] = set()

    def init_size(self, tile_size: "TCoor", map_size: "TCoor"):
        self.tile_size = tile_size
        self.map_size = map_size

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

    def collision_tiles_around(
        self, tile_location: "TCoor", collision_rect: RectLike
    ) -> Tuple[Rect]:
        assert len(tile_location) == 2

        nearest_tiles = self.get_nearest_tiles(tile_location)

        collided_rect = []
        for loc_x, loc_y in nearest_tiles:
            pos_x = loc_x * self.tile_size[0]
            pos_y = loc_y * self.tile_size[1]
            rect = Rect(pos_x, pos_y, *self.tile_size)
            if rect.colliderect(collision_rect):
                collided_rect.append(rect)

        return tuple(collided_rect)

    def load_map(self, id: int = 0):
        data_path = BASE_PATH / "data"
        filepath = data_path / str(id)
        if not filepath.exists():
            raise FileNotFoundError("map not found")

        self.offgrid_tiles = set()
        self.ongrid_tiles = {}
        with open(filepath, "r") as datafile:
            data = JSONLoad(datafile)
            raw_ongrid_tiles: TOngridParsedTile = data["ongrid_tiles"]
            offgrid_tiles = data["offgrid_tiles"]
            tilesize = deserialize_point(data["tile_size"])

            self.tile_size = tilesize
            for loc, tile in raw_ongrid_tiles.items():
                pos = deserialize_point(loc)
                tile["pos"] = pos  # type: ignore
                self.ongrid_tiles[pos] = tile  # type: ignore

            for tile in offgrid_tiles:
                tile_copy = tile.copy()
                tile_copy["pos"] = deserialize_point(tile["pos"])  # type: ignore
                self.offgrid_tiles.add(tile_copy)

    def save_map(self, filename: str, tile_size: "TCoor"):
        if ".." in filename or "/" in filename or "\\" in filename:
            raise ValueError("Invalid filename")

        data_path = BASE_PATH / "data"
        if not data_path.exists():
            data_path.mkdir()

        map_data: Dict[str, Any] = {"tile_size": serialize_point(tile_size)}
        map_data["ongrid_tiles"] = {}
        map_data["offgrid_tiles"] = []

        for loc, tile in self.ongrid_tiles.items():
            key = serialize_point(loc)
            tile_copy = tile.copy()
            tile_copy["pos"] = key  # type: ignore
            map_data["ongrid_tiles"][key] = tile_copy

        for tile in self.offgrid_tiles:
            tile_copy = tile.copy()
            tile_copy["pos"] = serialize_point(tile["pos"])  # type: ignore
            map_data["offgrid_tiles"].append(tile_copy)

        path = data_path / filename
        with open(path, "w") as mapfile:
            JSONDump(map_data, mapfile, indent=1)

    def update(self, dt: float):
        pass

    def render(self, surface: Surface):
        pass
