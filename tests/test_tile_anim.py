import json
from pathlib import Path

import pytest

from utils.tile_anim import (
    ANIM_CLIP_KEY,
    TileAnimCache,
    TileAnimClip,
    TileAnimFile,
    TileClipFrame,
    clip_frame_at,
    clip_phase_for_cell,
    generate_strip_clips,
    load_tile_anim_file,
    resolve_clip_sheet,
    resolve_tanim_for_tileset,
    sprite_library_to_tanim,
)


def _clip():
    return TileAnimClip(
        name="fresh1",
        frames=(
            TileClipFrame(sheet="tileset.png", variant=297, duration_ms=100.0),
            TileClipFrame(sheet="tileset.png", variant=396, duration_ms=100.0),
            TileClipFrame(sheet="tileset.png", variant=495, duration_ms=100.0),
            TileClipFrame(sheet="tileset.png", variant=594, duration_ms=100.0),
        ),
        loop=True,
    )


def test_anim_clip_key_is_canonical():
    assert ANIM_CLIP_KEY == "anim_clip"


def test_tanim_resolution_is_data_animations_only(tmp_path):
    p = tmp_path / "assets" / "tileset.png"
    assert resolve_tanim_for_tileset(p, tmp_path) == tmp_path / "animations" / "tileset.tanim.json"
    assert resolve_tanim_for_tileset(p, None) is None
    # never resolves inside assets/
    assert "assets" not in str(resolve_tanim_for_tileset(p, tmp_path))


def test_load_valid_file(tmp_path):
    p = tmp_path / "water.tanim.json"
    p.write_text(
        '{"version": 1, "tileset": "tiles/water.png", "clips": '
        '{"waves": {"loop": true, "mode": "default", "frames": '
        '[{"sheet": "tiles/water.png", "variant": 5, "duration_ms": 120}]}}}'
    )
    clips = load_tile_anim_file(p)
    assert set(clips) == {"waves"}
    assert clips["waves"].frames[0].duration_ms == 120.0


def test_load_bad_file_returns_empty(tmp_path):
    assert load_tile_anim_file(tmp_path / "missing.tanim.json") == {}
    bad = tmp_path / "bad.tanim.json"
    bad.write_text("{not json")
    assert load_tile_anim_file(bad) == {}


def test_malformed_leaves_skipped(tmp_path):
    p = tmp_path / "x.tanim.json"
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "tileset": "t.png",
                "clips": {
                    "ok": {"frames": [{"sheet": "t.png", "variant": 1}]},
                    "empty": {"frames": []},
                    "bad-variant": {"frames": [{"sheet": "t.png", "variant": -1}]},
                    "": {"frames": [{"sheet": "t.png", "variant": 2}]},
                },
            }
        )
    )
    clips = load_tile_anim_file(p)
    assert set(clips) == {"ok"}


def test_clip_timing_uniform():
    c = _clip()
    assert clip_frame_at(c, 0).variant == 297
    assert clip_frame_at(c, 99).variant == 297
    assert clip_frame_at(c, 100).variant == 396
    assert clip_frame_at(c, 399).variant == 594
    assert clip_frame_at(c, 400).variant == 297  # loop


def test_clip_non_loop_holds_last():
    c = TileAnimClip(
        name="once",
        frames=(
            TileClipFrame(sheet="s", variant=1, duration_ms=100.0),
            TileClipFrame(sheet="s", variant=2, duration_ms=100.0),
        ),
        loop=False,
    )
    assert clip_frame_at(c, 500).variant == 2


def test_resolve_clip_sheet_exact_then_basename():
    paths = ["../../assets/tileset/tileset.png", "other.png"]
    assert resolve_clip_sheet(paths, "../../assets/tileset/tileset.png") == 0
    assert resolve_clip_sheet(paths, "tileset.png") == 0
    assert resolve_clip_sheet(paths, "nope.png") is None


def test_cache_mtime_invalidation(tmp_path):
    anim_dir = tmp_path / "animations"
    anim_dir.mkdir()
    side = anim_dir / "tileset.tanim.json"
    sheet = tmp_path / "assets" / "tileset.png"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.write_bytes(b"")
    side.write_text(
        json.dumps({"version": 1, "tileset": "tileset.png", "clips": {"a": {"frames": [{"sheet": "tileset.png", "variant": 1}]}}})
    )
    cache = TileAnimCache()
    tanim, c1 = cache.get_clips(sheet, tmp_path)
    assert tanim == side
    assert set(c1) == {"a"}
    side.write_text(
        json.dumps(
            {
                "version": 1,
                "tileset": "tileset.png",
                "clips": {
                    "a": {"frames": [{"sheet": "tileset.png", "variant": 1}]},
                    "b": {"frames": [{"sheet": "tileset.png", "variant": 2}]},
                },
            }
        )
    )
    _, c2 = cache.get_clips(sheet, tmp_path)
    assert set(c2) == {"a", "b"}
    assert cache.get_clips(sheet, None) == (None, {})


def test_generate_strip_3x3_vertical():
    # 33-col sheet, 3-row frame stride -> 99, like monster-trainer tileset.
    bases = [297, 298, 299, 330, 331, 332, 363, 364, 365]
    clips = generate_strip_clips(
        sheet="tileset.png", base_variants=bases, frame_stride=99, frame_count=4,
        name_for=lambda v: f"fresh_{v}",
    )
    assert len(clips) == 9
    assert [f.variant for f in clips["fresh_297"].frames] == [297, 396, 495, 594]
    assert [f.variant for f in clips["fresh_298"].frames] == [298, 397, 496, 595]


def test_sprite_library_to_tanim():
    lib = {
        "spritesheet_path": "../../assets/tileset/tileset.png",
        "animations": {
            "fresh1": {
                "name": "fresh1",
                "frames": [
                    {"variant_id": 297, "duration_ms": 100.0},
                    {"variant_id": 396, "duration_ms": 100.0},
                ],
                "loop": True,
            },
            "bad": {"frames": []},
        },
    }
    f = sprite_library_to_tanim(lib, sheet="tileset.png")
    assert f.by_name("fresh1") is not None
    assert [fr.variant for fr in f.by_name("fresh1").frames] == [297, 396]
    assert f.by_name("bad") is None


def test_sprite_library_to_tanim_forced_mode():
    lib = {
        "animations": {
            "w": {"frames": [{"variant_id": 1}, {"variant_id": 2}], "loop": True},
        },
    }
    forced = sprite_library_to_tanim(lib, sheet="s.png", mode="random_start_times")
    assert forced.by_name("w").mode == "random_start_times"
    defaulted = sprite_library_to_tanim(lib, sheet="s.png")
    assert defaulted.by_name("w").mode == "default"
    invalid = sprite_library_to_tanim(lib, sheet="s.png", mode="bogus")
    assert invalid.by_name("w").mode == "default"


def test_detect_anim_schema():
    from utils.tile_anim import detect_anim_schema, detect_anim_schema_file

    assert detect_anim_schema({"animations": {}}) == "sprite"
    assert detect_anim_schema({"clips": {}}) == "tile"
    assert detect_anim_schema({"animations": {}, "clips": {}}) == "sprite"
    assert detect_anim_schema({}) == "unknown"
    assert detect_anim_schema([]) == "unknown"
    assert detect_anim_schema(None) == "unknown"


def test_detect_anim_schema_file(tmp_path):
    from utils.tile_anim import detect_anim_schema_file

    assert detect_anim_schema_file(tmp_path / "missing.json") == "unknown"
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert detect_anim_schema_file(bad) == "unknown"
    sprite = tmp_path / "a.anim.json"
    sprite.write_text(json.dumps({"animations": {}}))
    assert detect_anim_schema_file(sprite) == "sprite"


def test_tanim_to_library_dict():
    from utils.tile_anim import TileAnimClip, TileAnimFile, tanim_to_library_dict

    f = TileAnimFile(
        tileset="assets/tileset.png",
        clips=[
            TileAnimClip(
                name="w",
                frames=(
                    TileClipFrame(sheet="a.png", variant=3, duration_ms=120.0),
                    TileClipFrame(sheet="b.png", variant=4, duration_ms=80.0),
                ),
                loop=False,
                mode="random_start_times",
            )
        ],
    )
    d = tanim_to_library_dict(f, spritesheet="abs.png", tile_size=(16, 16))
    assert d["spritesheet_path"] == "abs.png"
    assert d["tile_size"] == [16, 16]
    assert [fr["variant_id"] for fr in d["animations"]["w"]["frames"]] == [3, 4]
    assert d["animations"]["w"]["loop"] is False
    d2 = tanim_to_library_dict(f)
    assert d2["spritesheet_path"] == "assets/tileset.png"


def test_sprite_library_to_tanim_restores_sources():
    from utils.tile_anim import sprite_library_to_tanim

    lib = {"animations": {"w": {"frames": [{"variant_id": 1}, {"variant_id": 2}]}}}
    out = sprite_library_to_tanim(
        lib,
        sheet="s.png",
        sheets={"w": ["a.png", "b.png"]},
        clip_modes={"w": "random_start_times"},
    )
    clip = out.by_name("w")
    assert [f.sheet for f in clip.frames] == ["a.png", "b.png"]
    assert clip.mode == "random_start_times"
    mismatched = sprite_library_to_tanim(lib, sheet="s.png", sheets={"w": ["only.png"]})
    assert [f.sheet for f in mismatched.by_name("w").frames] == ["s.png", "s.png"]


def test_phase_is_stable():
    assert clip_phase_for_cell(1, 2, 0, 4) == clip_phase_for_cell(1, 2, 0, 4)
    assert 0 <= clip_phase_for_cell(29, 27, 0, 4) < 4


def test_tile_anim_file_round_trip(tmp_path):
    f = TileAnimFile(tileset="t.png", clips=[_clip()])
    p = tmp_path / "r.tanim.json"
    f.save(p)
    assert set(load_tile_anim_file(p)) == {"fresh1"}
