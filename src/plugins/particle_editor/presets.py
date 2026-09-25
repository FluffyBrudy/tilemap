"""Curated particle presets -- the single source of preset data.

18 curated essentials + Blank (11 originals, 3 continuous fields,
4 showcase pieces). Every entry fits the
editor slider ranges and reads as visibly alive at 1x/60fps.
Range repairs vs the legacy set are noted per entry.

``widgets.particle_presets`` is a deprecated shim over this module.
"""

from __future__ import annotations

import copy

PresetEntry = dict[str, object]

BLANK_NAME = "Blank"


def _blank_config() -> dict[str, object]:
    from widgets.particle_system import get_default_config

    return get_default_config()


def _entry(name: str, category: str, description: str, config: dict) -> PresetEntry:
    return {
        "name": name,
        "category": category,
        "description": description,
        "config": config,
    }


def _build_presets() -> list[PresetEntry]:
    presets: list[PresetEntry] = []
    presets.append(
        _entry(
            BLANK_NAME,
            "Starter",
            "Empty starting point: steady glow, tweak from here",
            _blank_config(),
        )
    )
    presets.append(
        _entry(
            "Campfire",
            "Fire & Heat",
            "Classic warm fire, orange->red, upward",
            {
                "emission_shape": "point",
                "particle_shape": "circle",
                "particle_size_min": 3,
                "particle_size_max": 7,
                "spawn_rate": 30,
                "max_particles": 70,
                "lifetime_min": 0.4,
                "lifetime_max": 1.2,
                "speed_min": 25,
                "speed_max": 65,
                "direction": 270,
                "spread": 28,
                "gravity_x": 0,
                "gravity_y": -12,
                "start_color_r": 255,
                "start_color_g": 200,
                "start_color_b": 50,
                "start_color_a": 255,
                "end_color_r": 180,
                "end_color_g": 40,
                "end_color_b": 10,
                "end_color_a": 0,
                "start_scale": 1.0,
                "end_scale": 0.2,
                "rotation_speed": 0,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
            },
        )
    )
    presets.append(
        _entry(
            "Smoke",
            "Smoke & Gas",
            "Thick gray smoke billowing upward",
            {
                "emission_shape": "point",
                "particle_shape": "smoke",
                "particle_size_min": 8,
                "particle_size_max": 14,
                "spawn_rate": 8,
                "max_particles": 40,
                "lifetime_min": 2.0,
                "lifetime_max": 4.0,
                "speed_min": 10,
                "speed_max": 30,
                "direction": 270,
                "spread": 20,
                "gravity_x": -3,
                "gravity_y": -10,
                "start_color_r": 180,
                "start_color_g": 180,
                "start_color_b": 180,
                "start_color_a": 130,
                "end_color_r": 100,
                "end_color_g": 100,
                "end_color_b": 100,
                "end_color_a": 0,
                "start_scale": 0.5,
                "end_scale": 1.8,
                "rotation_speed": 4,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
            },
        )
    )
    presets.append(
        _entry(
            "Rain",
            "Water & Liquid",
            "Fast falling rain streaks",
            {
                "emission_shape": "rect",
                "particle_shape": "line",
                "particle_size_min": 1,
                "particle_size_max": 2,
                "spawn_rate": 80,
                "max_particles": 250,
                "lifetime_min": 0.3,
                "lifetime_max": 0.8,
                "speed_min": 180,
                "speed_max": 280,
                "direction": 90,
                "spread": 6,
                "gravity_x": 0,
                "gravity_y": 0,
                "start_color_r": 180,
                "start_color_g": 210,
                "start_color_b": 255,
                "start_color_a": 200,
                "end_color_r": 140,
                "end_color_g": 180,
                "end_color_b": 255,
                "end_color_a": 30,
                "start_scale": 1.0,
                "end_scale": 1.0,
                "rotation_speed": 0,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
            },
        )
    )
    presets.append(
        _entry(
            "Snow",
            "Ice & Cold",
            "Gentle falling snowflakes",
            {
                "emission_shape": "rect",
                "particle_shape": "circle",
                "particle_size_min": 2,
                "particle_size_max": 5,
                "spawn_rate": 20,
                "max_particles": 120,
                "lifetime_min": 2.5,
                "lifetime_max": 5.0,
                "speed_min": 10,
                "speed_max": 30,
                "direction": 90,
                "spread": 35,
                "gravity_x": 3,
                "gravity_y": 12,
                "start_color_r": 255,
                "start_color_g": 255,
                "start_color_b": 255,
                "start_color_a": 230,
                "end_color_r": 200,
                "end_color_g": 220,
                "end_color_b": 255,
                "end_color_a": 80,
                "start_scale": 1.0,
                "end_scale": 0.9,
                "rotation_speed": 20,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
            },
        )
    )
    presets.append(
        _entry(
            "Explosion",
            "Combat",
            "Burst of fire and debris, short-lived",
            {
                "emission_shape": "point",
                "particle_shape": "star",
                "particle_size_min": 3,
                "particle_size_max": 7,
                "spawn_rate": 200,
                "max_particles": 80,
                "lifetime_min": 0.2,
                "lifetime_max": 0.7,
                "speed_min": 80,
                "speed_max": 220,
                "direction": -1,
                "spread": 360,
                "gravity_x": 0,
                "gravity_y": 0,
                "start_color_r": 255,
                "start_color_g": 220,
                "start_color_b": 80,
                "start_color_a": 255,
                "end_color_r": 120,
                "end_color_g": 50,
                "end_color_b": 20,
                "end_color_a": 0,
                "start_scale": 1.0,
                "end_scale": 0.1,
                "rotation_speed": 150,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
                "mode": "burst",
                "burst_count": 60,
                "timing": {
                    "emitter_duration": 0.0,
                    "start_delay": 0.0,
                    "loop": True,
                    "burst_interval": 0.08,
                },
            },
        )
    )
    presets.append(
        _entry(
            "Magic Sparkles",
            "Magic",
            "Purple->cyan sparkling burst",
            {
                "emission_shape": "point",
                "particle_shape": "sparkle",
                "particle_size_min": 2,
                "particle_size_max": 5,
                "spawn_rate": 30,
                "max_particles": 70,
                "lifetime_min": 0.5,
                "lifetime_max": 1.5,
                "speed_min": 40,
                "speed_max": 110,
                "direction": -1,
                "spread": 360,
                "gravity_x": 0,
                "gravity_y": -18,
                "start_color_r": 200,
                "start_color_g": 100,
                "start_color_b": 255,
                "start_color_a": 255,
                "end_color_r": 80,
                "end_color_g": 200,
                "end_color_b": 255,
                "end_color_a": 0,
                "start_scale": 1.0,
                "end_scale": 0.2,
                "rotation_speed": 200,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
            },
        )
    )
    presets.append(
        _entry(
            "Fountain",
            "Water & Liquid",
            "Water fountain arc with gravity pull",
            {
                "emission_shape": "point",
                "particle_shape": "circle",
                "particle_size_min": 2,
                "particle_size_max": 5,
                "spawn_rate": 40,
                "max_particles": 90,
                "lifetime_min": 1.0,
                "lifetime_max": 2.5,
                "speed_min": 80,
                "speed_max": 150,
                "direction": 270,
                "spread": 30,
                "gravity_x": 0,
                "gravity_y": 90,
                "start_color_r": 140,
                "start_color_g": 200,
                "start_color_b": 255,
                "start_color_a": 255,
                "end_color_r": 80,
                "end_color_g": 160,
                "end_color_b": 255,
                "end_color_a": 0,
                "start_scale": 1.0,
                "end_scale": 0.4,
                "rotation_speed": 0,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
            },
        )
    )
    presets.append(
        _entry(
            "Dust Cloud",
            "Smoke & Gas",
            "Brown dust kicked up",
            {
                "emission_shape": "rect",
                "particle_shape": "circle",
                "particle_size_min": 3,
                "particle_size_max": 8,
                "spawn_rate": 20,
                "max_particles": 60,
                "lifetime_min": 1.0,
                "lifetime_max": 3.0,
                "speed_min": 15,
                "speed_max": 45,
                "direction": -1,
                "spread": 360,
                "gravity_x": 5,
                "gravity_y": 5,
                "start_color_r": 180,
                "start_color_g": 160,
                "start_color_b": 130,
                "start_color_a": 100,
                "end_color_r": 140,
                "end_color_g": 120,
                "end_color_b": 100,
                "end_color_a": 0,
                "start_scale": 0.5,
                "end_scale": 1.5,
                "rotation_speed": 10,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
            },
        )
    )
    presets.append(
        _entry(
            "Fireflies",
            "Nature",
            "Glowing yellow-green dots at night",
            {
                "emission_shape": "point",
                "particle_shape": "circle",
                "particle_size_min": 2,
                "particle_size_max": 4,
                "spawn_rate": 8,
                "max_particles": 25,
                "lifetime_min": 2.5,
                "lifetime_max": 5.0,
                "speed_min": 5,
                "speed_max": 20,
                "direction": -1,
                "spread": 360,
                "gravity_x": -5,
                "gravity_y": -5,
                "start_color_r": 200,
                "start_color_g": 255,
                "start_color_b": 80,
                "start_color_a": 255,
                "end_color_r": 150,
                "end_color_g": 220,
                "end_color_b": 40,
                "end_color_a": 0,
                "start_scale": 1.0,
                "end_scale": 0.3,
                "rotation_speed": 10,
                "alpha_fade": "fade_both",
                "wrap": False,
                "fade_peak_alpha": None,
            },
        )
    )
    presets.append(
        _entry(
            "Confetti",
            "Celebration",
            "Colorful falling squares",
            {
                "emission_shape": "rect",
                "particle_shape": "square",
                "particle_size_min": 3,
                "particle_size_max": 6,
                "spawn_rate": 35,
                "max_particles": 120,
                "lifetime_min": 2.0,
                "lifetime_max": 4.5,
                "speed_min": 20,
                "speed_max": 60,
                "direction": 270,
                "spread": 50,
                "gravity_x": 5,
                "gravity_y": 35,
                "start_color_r": 255,
                "start_color_g": 180,
                "start_color_b": 80,
                "start_color_a": 255,
                "end_color_r": 100,
                "end_color_g": 220,
                "end_color_b": 255,
                "end_color_a": 80,
                "start_scale": 1.0,
                "end_scale": 0.8,
                "rotation_speed": 120,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
            },
        )
    )
    presets.append(
        _entry(
            "Bubbles",
            "Water & Liquid",
            "Rising translucent bubbles",
            {
                "emission_shape": "point",
                "particle_shape": "circle",
                "particle_size_min": 3,
                "particle_size_max": 8,
                "spawn_rate": 10,
                "max_particles": 30,
                "lifetime_min": 2.0,
                "lifetime_max": 4.0,
                "speed_min": 10,
                "speed_max": 30,
                "direction": 270,
                "spread": 20,
                "gravity_x": 3,
                "gravity_y": -12,
                "start_color_r": 200,
                "start_color_g": 230,
                "start_color_b": 255,
                "start_color_a": 120,
                "end_color_r": 180,
                "end_color_g": 220,
                "end_color_b": 255,
                "end_color_a": 30,
                "start_scale": 1.0,
                "end_scale": 1.2,
                "rotation_speed": 5,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
            },
        )
    )
    presets.append(
        _entry(
            "Mist Bed",
            "Atmospheric",
            "Low hanging haze that never dies, slow sideways drift",
            {
                "emission_shape": "rect",
                "particle_shape": "fog",
                "particle_size_min": 20,
                "particle_size_max": 34,
                "spawn_rate": 0,
                "max_particles": 150,
                "lifetime_min": 60.0,
                "lifetime_max": 120.0,
                "speed_min": 6,
                "speed_max": 14,
                "direction": 0,
                "spread": 30,
                "gravity_x": 0,
                "gravity_y": 0,
                "start_color_r": 200,
                "start_color_g": 205,
                "start_color_b": 215,
                "start_color_a": 16,
                "end_color_r": 200,
                "end_color_g": 205,
                "end_color_b": 215,
                "end_color_a": 16,
                "start_scale": 0.9,
                "end_scale": 1.2,
                "rotation_speed": 0,
                "alpha_fade": "none",
                "wrap": True,
                "fade_peak_alpha": None,
                "mode": "field",
                "burst_count": 0,
                "coverage": 1.0,
                "field_quality": "medium",
                "ground_bias": True,
            },
        )
    )
    presets.append(
        _entry(
            "Poison Haze",
            "Atmospheric",
            "Toxic green hang, omnidirectional drift, no source point",
            {
                "emission_shape": "rect",
                "particle_shape": "fog",
                "particle_size_min": 24,
                "particle_size_max": 40,
                "spawn_rate": 0,
                "max_particles": 120,
                "lifetime_min": 60.0,
                "lifetime_max": 120.0,
                "speed_min": 4,
                "speed_max": 10,
                "direction": -1,
                "spread": 360,
                "gravity_x": 0,
                "gravity_y": 0,
                "start_color_r": 90,
                "start_color_g": 190,
                "start_color_b": 110,
                "start_color_a": 26,
                "end_color_r": 60,
                "end_color_g": 150,
                "end_color_b": 80,
                "end_color_a": 26,
                "start_scale": 0.9,
                "end_scale": 1.2,
                "rotation_speed": 0,
                "alpha_fade": "none",
                "wrap": True,
                "fade_peak_alpha": None,
                "mode": "field",
                "burst_count": 0,
                "coverage": 1.0,
                "field_quality": "medium",
                "ground_bias": False,
            },
        )
    )
    presets.append(
        _entry(
            "Fire Flare",
            "Fire & Heat",
            "Warm upward shimmer that wraps instead of dying",
            {
                "emission_shape": "point",
                "particle_shape": "smoke",
                "particle_size_min": 8,
                "particle_size_max": 16,
                "spawn_rate": 25,
                "max_particles": 60,
                "lifetime_min": 1.5,
                "lifetime_max": 3.0,
                "speed_min": 15,
                "speed_max": 35,
                "direction": 270,
                "spread": 25,
                "gravity_x": 0,
                "gravity_y": -6,
                "start_color_r": 255,
                "start_color_g": 170,
                "start_color_b": 60,
                "start_color_a": 150,
                "end_color_r": 220,
                "end_color_g": 90,
                "end_color_b": 20,
                "end_color_a": 110,
                "start_scale": 1.0,
                "end_scale": 1.6,
                "rotation_speed": 0,
                "alpha_fade": "none",
                "wrap": True,
                "fade_peak_alpha": None,
                "mode": "continuous",
                "burst_count": 30,
                "coverage": 1.0,
                "field_quality": "medium",
                "ground_bias": False,
            },
        )
    )
    presets.append(
        _entry(
            "Aurora Veil",
            "Atmospheric",
            "Breathing teal-to-violet sheets drifting sideways, never dies",
            {
                "emission_shape": "rect",
                "particle_shape": "fog",
                "particle_size_min": 30,
                "particle_size_max": 50,
                "spawn_rate": 0,
                "max_particles": 40,
                "lifetime_min": 60.0,
                "lifetime_max": 120.0,
                "speed_min": 8,
                "speed_max": 18,
                "direction": 0,
                "spread": 25,
                "gravity_x": 0,
                "gravity_y": 0,
                "start_color_r": 80,
                "start_color_g": 255,
                "start_color_b": 190,
                "start_color_a": 22,
                "end_color_r": 150,
                "end_color_g": 110,
                "end_color_b": 255,
                "end_color_a": 22,
                "start_scale": 0.8,
                "end_scale": 1.6,
                "rotation_speed": 6,
                "alpha_fade": "fade_both",
                "wrap": True,
                "fade_peak_alpha": 70,
                "mode": "field",
                "burst_count": 0,
                "coverage": 1.0,
                "field_quality": "medium",
                "ground_bias": False,
            },
        )
    )
    presets.append(
        _entry(
            "Ember Storm",
            "Fire & Heat",
            "Dense rising ember swarm, accelerating upward, white-hot cores",
            {
                "emission_shape": "rect",
                "particle_shape": "sparkle",
                "particle_size_min": 2,
                "particle_size_max": 5,
                "spawn_rate": 120,
                "max_particles": 220,
                "lifetime_min": 0.8,
                "lifetime_max": 2.0,
                "speed_min": 60,
                "speed_max": 140,
                "direction": 270,
                "spread": 35,
                "gravity_x": 0,
                "gravity_y": -25,
                "start_color_r": 255,
                "start_color_g": 190,
                "start_color_b": 60,
                "start_color_a": 255,
                "end_color_r": 220,
                "end_color_g": 60,
                "end_color_b": 10,
                "end_color_a": 0,
                "start_scale": 1.0,
                "end_scale": 0.2,
                "rotation_speed": 90,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
                "mode": "continuous",
                "burst_count": 30,
                "coverage": 1.0,
                "field_quality": "medium",
                "ground_bias": False,
            },
        )
    )
    presets.append(
        _entry(
            "Abyssal Nebula",
            "Magic",
            "Immortal deep-space drift, purple coals breathing into cyan",
            {
                "emission_shape": "rect",
                "particle_shape": "smoke",
                "particle_size_min": 14,
                "particle_size_max": 28,
                "spawn_rate": 10,
                "max_particles": 70,
                "lifetime_min": 2.0,
                "lifetime_max": 4.5,
                "speed_min": 5,
                "speed_max": 15,
                "direction": -1,
                "spread": 360,
                "gravity_x": 0,
                "gravity_y": 0,
                "start_color_r": 120,
                "start_color_g": 60,
                "start_color_b": 220,
                "start_color_a": 100,
                "end_color_r": 60,
                "end_color_g": 200,
                "end_color_b": 230,
                "end_color_a": 40,
                "start_scale": 0.6,
                "end_scale": 1.4,
                "rotation_speed": 8,
                "alpha_fade": "fade_both",
                "wrap": True,
                "fade_peak_alpha": 110,
                "mode": "continuous",
                "burst_count": 30,
                "coverage": 1.0,
                "field_quality": "medium",
                "ground_bias": False,
            },
        )
    )
    presets.append(
        _entry(
            "Volcano's Heart",
            "Combat",
            "Sustained eruption in rolling pops, debris arcs and falls back",
            {
                "emission_shape": "point",
                "particle_shape": "star",
                "particle_size_min": 4,
                "particle_size_max": 9,
                "spawn_rate": 60,
                "max_particles": 200,
                "lifetime_min": 1.0,
                "lifetime_max": 2.5,
                "speed_min": 120,
                "speed_max": 260,
                "direction": 270,
                "spread": 30,
                "gravity_x": 0,
                "gravity_y": 120,
                "start_color_r": 255,
                "start_color_g": 120,
                "start_color_b": 20,
                "start_color_a": 255,
                "end_color_r": 120,
                "end_color_g": 20,
                "end_color_b": 10,
                "end_color_a": 60,
                "start_scale": 1.0,
                "end_scale": 0.5,
                "rotation_speed": 120,
                "alpha_fade": "fade_out",
                "wrap": False,
                "fade_peak_alpha": None,
                "mode": "burst",
                "burst_count": 150,
                "coverage": 1.0,
                "field_quality": "medium",
                "ground_bias": False,
                "timing": {
                    "emitter_duration": 0.0,
                    "start_delay": 0.0,
                    "loop": True,
                    "burst_interval": 0.1,
                },
            },
        )
    )
    for p in presets:
        cfg = p["config"]
        assert isinstance(cfg, dict)
        cfg.setdefault("mode", "continuous")
        cfg.setdefault("burst_count", 30)
        cfg.setdefault("coverage", 1.0)
        cfg.setdefault("field_quality", "medium")
        cfg.setdefault("ground_bias", False)
        # Fresh dict per preset: never alias one timing block across entries.
        if "timing" not in cfg:
            cfg["timing"] = {
                "emitter_duration": 0.0,
                "start_delay": 0.0,
                "loop": True,
                "burst_interval": 0.0,
            }
    return presets


PRESETS: list[PresetEntry] = _build_presets()


def get_presets_by_category() -> dict[str, list[PresetEntry]]:
    cats: dict[str, list[PresetEntry]] = {}
    for p in PRESETS:
        cat = str(p["category"])
        cats.setdefault(cat, []).append(p)
    return cats


def get_preset_names() -> list[str]:
    return [str(p["name"]) for p in PRESETS]


def find_preset(name: str) -> PresetEntry:
    for p in PRESETS:
        if p["name"] == name:
            return p
    raise KeyError(f"Preset {name!r} not found")


def get_preset_config(name: str) -> dict:
    return copy.deepcopy(find_preset(name)["config"])  # type: ignore[arg-type]
