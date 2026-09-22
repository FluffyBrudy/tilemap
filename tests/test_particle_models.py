"""Unit tests for the particle data model: schema, normalize, library."""

import ast
import json
from pathlib import Path

import pytest

from plugins.particle_editor import models
from plugins.particle_editor.models import (
    ParticleLibrary,
    ParticleSystemEntry,
    identify,
    list_libraries,
    modified_from,
    normalize_config,
)

SRC = Path(__file__).parent.parent / "src"


def test_models_has_no_pygame_import():
    src = (SRC / "plugins" / "particle_editor" / "models.py").read_text()
    tree = ast.parse(src)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any("pygame" in name for name in imports)


def test_schema_keys_match_default_config():
    from widgets.particle_system import DEFAULT_PARTICLE_CONFIG

    assert set(models.SCHEMA_KEYS) == set(DEFAULT_PARTICLE_CONFIG)
    assert set(models.SCHEMA_DEFAULTS) == set(DEFAULT_PARTICLE_CONFIG)


def test_normalize_legacy_config_gains_defaults():
    legacy = {"spawn_rate": 40}  # pre-schema node properties
    normalized, warnings = normalize_config(legacy)
    assert normalized["spawn_rate"] == 40
    assert normalized["wrap"] is False
    assert normalized["fade_peak_alpha"] is None
    assert normalized["particle_shape"] == "circle"
    assert not warnings


def test_normalize_repairs_with_warnings():
    raw = {
        "particle_shape": "plasma",
        "emission_shape": "vortex",
        "alpha_fade": "shimmer",
        "particle_size_min": 8,
        "particle_size_max": 3,
        "lifetime_min": 4.0,
        "lifetime_max": 1.0,
        "spread": 999,
        "start_color_r": 300,
        "spawn_rate": "lots",
    }
    normalized, warnings = normalize_config(raw)
    assert normalized["particle_shape"] == "circle"
    assert normalized["emission_shape"] == "point"
    assert normalized["alpha_fade"] == "fade_out"
    assert normalized["particle_size_max"] == 8
    assert normalized["lifetime_max"] == 4.0
    assert normalized["spread"] == 360.0
    assert normalized["start_color_r"] == 255
    assert normalized["spawn_rate"] == 20
    assert len(warnings) >= 7


def test_normalize_preserves_unknown_keys():
    normalized, _ = normalize_config({"future_field": 123, "spawn_rate": 5})
    assert normalized["future_field"] == 123


def test_normalize_never_raises_on_junk():
    for junk in (None, "nope", [1, 2], 42):
        normalized, warnings = normalize_config(junk)  # type: ignore[arg-type]
        assert normalized["spawn_rate"] == 20
        assert warnings


def test_nan_values_fall_back_to_defaults():
    normalized, warnings = normalize_config(
        {"spawn_rate": float("nan"), "lifetime_min": float("nan")}
    )
    assert normalized["spawn_rate"] == 20
    assert normalized["lifetime_min"] == 0.5
    assert any("NaN" in w for w in warnings)


def test_timing_defaults_mean_infinite_continuous():
    normalized, warnings = normalize_config({"spawn_rate": 5})
    assert normalized["timing"] == {
        "emitter_duration": 0.0,
        "start_delay": 0.0,
        "loop": True,
        "burst_interval": 0.0,
    }
    assert warnings == []


def test_timing_repairs_and_fallback():
    normalized, warnings = normalize_config(
        {
            "timing": {
                "emitter_duration": -2,
                "start_delay": "soon",
                "loop": "yes",
                "burst_interval": -0.5,
            }
        }
    )
    assert normalized["timing"]["emitter_duration"] == 0.0
    assert normalized["timing"]["start_delay"] == 0.0
    assert normalized["timing"]["loop"] is True
    assert normalized["timing"]["burst_interval"] == 0.0
    assert len(warnings) == 4
    fallback, fallback_warnings = normalize_config({"timing": "forever"})
    assert fallback["timing"]["loop"] is True
    assert len(fallback_warnings) == 1


def test_unknown_timing_subkeys_preserved():
    normalized, _ = normalize_config({"timing": {"future": 1}})
    assert normalized["timing"]["future"] == 1


def test_no_aliasing_across_calls():
    from widgets.particle_system import get_default_config

    a = get_default_config()
    b = get_default_config()
    a["timing"]["loop"] = False
    assert b["timing"]["loop"] is True


def test_library_round_trip(tmp_path):
    lib = ParticleLibrary(
        systems=[
            ParticleSystemEntry(name="A", config={"spawn_rate": 10}),
            ParticleSystemEntry(name="B", config={"particle_shape": "junk"}),
        ]
    )
    path = tmp_path / "test.particles.json"
    lib.save(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert [s["name"] for s in payload["particle_systems"]] == ["A", "B"]
    loaded, warnings = ParticleLibrary.load(path)
    assert loaded.names() == ["A", "B"]
    assert loaded.find("A").config["spawn_rate"] == 10
    assert loaded.find("B").config["particle_shape"] == "circle"
    assert warnings == []  # save() already normalized; stored file is clean
    _, entry_warnings = ParticleSystemEntry(
        name="B", config={"particle_shape": "junk"}
    ).normalized()
    assert any("junk" in w for w in entry_warnings)


def test_library_load_errors_are_warnings(tmp_path):
    missing, warnings = ParticleLibrary.load(tmp_path / "nope.particles.json")
    assert missing.systems == [] and warnings
    bad = tmp_path / "bad.particles.json"
    bad.write_text("{oops", encoding="utf-8")
    _, warnings = ParticleLibrary.load(bad)
    assert warnings
    noname = tmp_path / "noname.particles.json"
    noname.write_text(
        json.dumps({"particle_systems": [{"config": {}}]}), encoding="utf-8"
    )
    loaded, warnings = ParticleLibrary.load(noname)
    assert loaded.systems == [] and warnings


def test_list_libraries(tmp_path):
    assert list_libraries(tmp_path) == []
    (tmp_path / "particles").mkdir()
    (tmp_path / "particles" / "b.particles.json").write_text("{}")
    (tmp_path / "particles" / "a.particles.json").write_text("{}")
    (tmp_path / "particles" / "notes.txt").write_text("x")
    assert [p.name for p in list_libraries(tmp_path)] == [
        "a.particles.json",
        "b.particles.json",
    ]


def test_identify_exact_modified_custom():
    library = ParticleLibrary(
        systems=[
            ParticleSystemEntry(name="Fire", config={"spawn_rate": 30}),
        ]
    )
    assert identify({"spawn_rate": 30}, library) == "Fire"
    assert identify({"spawn_rate": 31}, library) == "Fire (modified)"
    assert modified_from({"spawn_rate": 31}, library) == "Fire"
    other = {
        "spawn_rate": 1,
        "particle_shape": "heart",
        "emission_shape": "circle",
        "max_particles": 5,
        "gravity_y": -100,
    }
    assert identify(other, library) == "Custom"
    assert modified_from(other, library) is None
