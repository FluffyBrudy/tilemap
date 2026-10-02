"""Tests for SpriteAnimationEditor tile-clip export (``*.tanim.json``).

The export path is additive: it must convert the in-memory sprite library
to the tile-clip schema, store relative sheet refs, enforce ``.tanim.json``
via the dialog, and never touch ``*.anim.json`` save state.
"""

import pygame
import pytest
from pygame import Rect


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


def _make_editor(tile_size=(16, 16)):
    from plugins.sprite_animation.editor import SpriteAnimationEditor

    surf = pygame.Surface((512, 512))
    surf.fill((80, 80, 80))
    rect = Rect(0, 0, 900, 600)
    return SpriteAnimationEditor(rect=rect, surface=surf, tile_size=tile_size)


def _water_library(sheet_ref):
    from plugins.sprite_animation.models import Animation, AnimationLibrary

    lib = AnimationLibrary(tile_size=(16, 16), spritesheet_path=sheet_ref)
    anim = Animation(name="green_water_1")
    anim.add_frame(298, duration_ms=100.0)
    anim.add_frame(397, duration_ms=100.0)
    lib.add_animation(anim)
    return lib


def test_export_writes_relative_sheet_ref(tmp_path):
    from utils.tile_anim import load_tile_anim_file

    sheet = tmp_path / "assets" / "tileset.png"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.write_bytes(b"")
    out = tmp_path / "data" / "animations" / "tileset.tanim.json"

    ed = _make_editor()
    ed.library = _water_library(str(sheet.resolve()))
    ed._data_root = tmp_path / "data"

    ed._on_export_tanim_selected(out)

    assert out.is_file()
    clips = load_tile_anim_file(out)
    assert set(clips) == {"green_water_1"}
    assert [f.variant for f in clips["green_water_1"].frames] == [298, 397]
    # Always relative — never an absolute path in data files.
    assert clips["green_water_1"].frames[0].sheet == "../../assets/tileset.png"
    # Existing anim save state untouched.
    assert ed._last_saved_path is None


def test_export_desync_toggle_sets_clip_mode(tmp_path):
    from utils.tile_anim import load_tile_anim_file

    sheet = tmp_path / "assets" / "tileset.png"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.write_bytes(b"")
    out = tmp_path / "data" / "animations" / "tileset.tanim.json"

    ed = _make_editor()
    assert ed._export_desync is False
    ed.library = _water_library(str(sheet.resolve()))
    ed._data_root = tmp_path / "data"
    ed._export_desync = True

    ed._on_export_tanim_selected(out)

    clips = load_tile_anim_file(out)
    assert clips["green_water_1"].mode == "random_start_times"


def test_export_synced_by_default(tmp_path):
    from utils.tile_anim import load_tile_anim_file

    sheet = tmp_path / "assets" / "tileset.png"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.write_bytes(b"")
    out = tmp_path / "data" / "animations" / "tileset.tanim.json"

    ed = _make_editor()
    ed.library = _water_library(str(sheet.resolve()))
    ed._data_root = tmp_path / "data"

    ed._on_export_tanim_selected(out)

    clips = load_tile_anim_file(out)
    assert clips["green_water_1"].mode == "default"


def _write_tanim(path, sheet="assets/tileset.png"):
    from utils.tile_anim import TileAnimClip, TileAnimFile, TileClipFrame

    f = TileAnimFile(
        tileset=sheet,
        clips=[
            TileAnimClip(
                name="green_water_1",
                frames=(
                    TileClipFrame(sheet=sheet, variant=298, duration_ms=100.0),
                    TileClipFrame(sheet=sheet, variant=397, duration_ms=100.0),
                ),
                loop=True,
                mode="random_start_times",
            )
        ],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    f.save(path)
    return f


def test_load_tanim_populates_library_and_source(tmp_path):
    tanim_path = tmp_path / "data" / "animations" / "tileset.tanim.json"
    _write_tanim(tanim_path)

    ed = _make_editor()
    ed._data_root = tmp_path / "data"

    assert ed.load_tanim_file(tanim_path) is True
    assert ed.library.animation_names() == ["green_water_1"]
    assert [f.variant_id for f in ed.library.get_animation("green_water_1").frames] == [298, 397]
    assert ed._tanim_source["path"] == tanim_path
    assert ed._tanim_source["sheets"] == {"green_water_1": ["assets/tileset.png"] * 2}
    assert ed._tanim_source["modes"] == {"green_water_1": "random_start_times"}
    assert ed._last_saved_path == tanim_path


def test_load_tanim_empty_file_refused(tmp_path):
    tanim_path = tmp_path / "data" / "animations" / "empty.tanim.json"
    tanim_path.parent.mkdir(parents=True, exist_ok=True)
    tanim_path.write_text('{"version": 1, "tileset": "s.png", "clips": {}}')

    ed = _make_editor()
    before = ed.library
    assert ed.load_tanim_file(tanim_path) is False
    assert ed.library is before
    assert ed._tanim_source is None


def test_quick_save_round_trips_tanim(tmp_path):
    from utils.tile_anim import TileAnimFile, load_tile_anim_file

    tanim_path = tmp_path / "data" / "animations" / "tileset.tanim.json"
    original = _write_tanim(tanim_path)

    ed = _make_editor()
    ed._data_root = tmp_path / "data"
    assert ed.load_tanim_file(tanim_path) is True

    ed._quick_save()

    assert TileAnimFile.load(tanim_path).to_dict() == original.to_dict()
    assert set(load_tile_anim_file(tanim_path)) == {"green_water_1"}


def test_load_sprite_clears_tanim_source(tmp_path):
    from plugins.sprite_animation.models import AnimationLibrary

    tanim_path = tmp_path / "data" / "animations" / "tileset.tanim.json"
    _write_tanim(tanim_path)
    sprite_path = tmp_path / "data" / "animations" / "idle.anim.json"
    AnimationLibrary(tile_size=(16, 16)).save(sprite_path)

    ed = _make_editor()
    ed._data_root = tmp_path / "data"
    assert ed.load_tanim_file(tanim_path) is True
    ed._on_load_file_selected(sprite_path)
    assert ed._tanim_source is None


def test_unknown_schema_leaves_library_alone(tmp_path):
    junk = tmp_path / "notes.json"
    junk.write_text('{"foo": 1}')

    ed = _make_editor()
    before_names = ed.library.animation_names()
    ed._on_load_file_selected(junk)
    assert ed.library.animation_names() == before_names
    assert ed._tanim_source is None
    assert ed._last_saved_path is None


def test_save_as_tanim_extension_writes_clips(tmp_path):
    from utils.tile_anim import load_tile_anim_file

    sheet = tmp_path / "assets" / "tileset.png"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.write_bytes(b"")

    ed = _make_editor()
    ed.library = _water_library(str(sheet.resolve()))
    ed._data_root = tmp_path / "data"
    out = tmp_path / "data" / "animations" / "tileset.tanim.json"

    ed._on_save_file_selected(out)

    assert set(load_tile_anim_file(out)) == {"green_water_1"}
    assert ed._tanim_source["path"] == out
    assert ed._last_saved_path == out


def test_export_empty_library_writes_nothing(tmp_path):
    from plugins.sprite_animation.models import AnimationLibrary

    out = tmp_path / "data" / "animations" / "tiles.tanim.json"
    ed = _make_editor()
    ed.library = AnimationLibrary(tile_size=(16, 16), spritesheet_path=str(tmp_path / "s.png"))
    ed._data_root = tmp_path / "data"

    ed._on_export_tanim_selected(out)

    assert not out.exists()


def test_export_without_spritesheet_writes_nothing(tmp_path):
    from plugins.sprite_animation.models import Animation, AnimationLibrary

    out = tmp_path / "data" / "animations" / "tiles.tanim.json"
    lib = AnimationLibrary(tile_size=(16, 16))
    anim = Animation(name="w")
    anim.add_frame(1)
    lib.add_animation(anim)
    ed = _make_editor()
    ed.library = lib
    ed._data_root = tmp_path / "data"

    ed._on_export_tanim_selected(out)

    assert not out.exists()
