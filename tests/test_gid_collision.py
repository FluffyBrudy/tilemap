"""Tests for GID-based collision resolution (no firstgid in collision library)."""

from plugins.tileset_collision.models import (
    CollisionPolygon,
    TileCollisionData,
    TilesetCollisionLibrary,
)


class TestTilesetCollisionLibraryNoFirstgid:
    def test_to_dict_no_firstgid(self):
        lib = TilesetCollisionLibrary(
            tileset_name="test", tile_size=(32, 32),
            tiles={5: TileCollisionData(tile_id=5, shapes=[
                CollisionPolygon(vertices=[(0, 0), (32, 0), (32, 32), (0, 32)]),
            ])},
        )
        d = lib.to_dict()
        assert "firstgid" not in d
        assert d["tileset_name"] == "test"
        assert "5" in d["tiles"]

    def test_roundtrip_ignores_firstgid(self):
        d = {
            "tileset_name": "test",
            "tile_size": [16, 16],
            "firstgid": 100,
            "tiles": {"0": {"tile_id": 0, "shapes": []}},
        }
        lib = TilesetCollisionLibrary.from_dict(d)
        assert not hasattr(lib, "firstgid")
        assert 0 in lib.tiles

    def test_keeps_existing_fields(self):
        lib = TilesetCollisionLibrary(
            tileset_name="test", tile_size=(32, 32),
            tiles={0: TileCollisionData(tile_id=0)},
        )
        d = lib.to_dict()
        restored = TilesetCollisionLibrary.from_dict(d)
        assert restored.tileset_name == "test"
        assert restored.tile_size == (32, 32)
        assert 0 in restored.tiles
