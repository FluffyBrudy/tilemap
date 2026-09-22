"""Unit tests for the curated preset library: data contracts."""

import pytest

from plugins.particle_editor.models import builtin_library, builtin_library_path
from plugins.particle_editor.presets import BLANK_NAME, PRESETS


def test_blank_matches_default_config():
    from plugins.particle_editor.presets import get_preset_config
    from widgets.particle_system import get_default_config

    assert get_preset_config(BLANK_NAME) == get_default_config()


def test_shipped_essentials_library_loads_clean():
    assert builtin_library_path().is_file()
    library, warnings = builtin_library()
    assert warnings == []
    assert len(library.systems) == len(PRESETS) == 19
    assert library.names()[0] == BLANK_NAME
    assert library.names() == [str(p["name"]) for p in PRESETS]
    for system, preset in zip(library.systems, PRESETS, strict=True):
        assert system.config == preset["config"]
    assert library.names()[-4:] == [
        "Aurora Veil",
        "Ember Storm",
        "Abyssal Nebula",
        "Volcano's Heart",
    ]


def test_presets_within_slider_ranges():
    from widgets.particle_system import FLOAT_FIELDS

    assert len(PRESETS) == 19
    for preset in PRESETS:
        config = preset["config"]
        assert isinstance(config, dict)
        field_mode = config.get("mode") == "field"
        for key, (lo, hi, _label) in FLOAT_FIELDS.items():
            if key == "fade_peak_alpha":
                continue
            if field_mode and key in ("spawn_rate", "lifetime_min", "lifetime_max"):
                continue  # fill-once contract: spawn 0, persistence lifetimes
            value = config[key]
            assert lo <= value <= hi, (
                f"{preset['name']}.{key}={value} outside [{lo}, {hi}]"
            )
        if field_mode:
            assert config["spawn_rate"] == 0, preset["name"]
            assert config["wrap"] is True, preset["name"]
            assert config["lifetime_max"] >= 30, preset["name"]


def test_presets_read_visibly_alive():
    for preset in PRESETS:
        c = preset["config"]
        if c.get("mode") == "field":
            # Sheets are subtle by design; coverage math keeps them present.
            assert c["start_color_a"] >= 8, preset["name"]
            assert c["coverage"] >= 0.5, preset["name"]
            continue
        assert c["lifetime_max"] >= 0.3, preset["name"]
        assert c["particle_size_max"] >= 2, preset["name"]
        assert c["start_color_a"] >= 100, preset["name"]
        assert c["spawn_rate"] >= 5, preset["name"]
        assert c["max_particles"] >= 15, preset["name"]
        assert c["end_scale"] >= 0.1, preset["name"]


def test_field_trio_present_and_contracted():
    from plugins.particle_editor.presets import get_preset_config

    names = [str(p["name"]) for p in PRESETS]
    assert {"Mist Bed", "Poison Haze", "Fire Flare"} <= set(names)
    mist = get_preset_config("Mist Bed")
    assert mist["mode"] == "field" and mist["spawn_rate"] == 0
    assert mist["wrap"] is True and mist["ground_bias"] is True
    poison = get_preset_config("Poison Haze")
    assert poison["direction"] == -1  # omnidirectional
    flare = get_preset_config("Fire Flare")
    assert flare["wrap"] is True and flare["mode"] == "continuous"


def test_every_preset_carries_full_timing():
    for preset in PRESETS:
        timing = preset["config"]["timing"]
        assert set(timing) == {
            "emitter_duration",
            "start_delay",
            "loop",
            "burst_interval",
        }
    from plugins.particle_editor.presets import get_preset_config

    assert get_preset_config("Explosion")["timing"]["burst_interval"] == 0.08


def test_library_round_trips_timing(tmp_path):
    from plugins.particle_editor.models import ParticleLibrary

    out = tmp_path / "t.particles.json"
    builtin_library()[0].save(out)
    reloaded, warnings = ParticleLibrary.load(out)
    assert warnings == []
    assert reloaded.find("Explosion").config["timing"]["burst_interval"] == 0.08


def test_legacy_shim_reexports_plugin():
    import widgets.particle_presets as shim
    from plugins.particle_editor import presets

    assert shim.PRESETS is presets.PRESETS
    assert shim.get_preset_names() == presets.get_preset_names()
    assert shim.get_preset_config("Campfire") == presets.get_preset_config("Campfire")
    with pytest.raises(KeyError):
        shim.get_preset_config("Nope")
