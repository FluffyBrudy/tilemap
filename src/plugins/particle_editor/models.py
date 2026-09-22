"""Particle library model -- pygame-free by design.
Editor-owned schema for particle systems: load/save/repair
``*.particles.json`` libraries, normalize configs, and derive preset
identity (``"Fire" | "Fire * Modified" | "Custom"``).

Authority lives here and in ``presets.py``. The parser is a separate
package and a tolerant consumer: it must accept whatever this module
writes. This module must never import pygame (a test pins that) and
never import parser code; rendering truth lives in
``widgets.particle_system``.

Library file shape (deliberately parser-readable)::

    {"particle_systems": [{"name": "Campfire", "config": {...}}]}
"""

from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

LIBRARY_SUFFIX = ".particles.json"
LIBRARY_DIRNAME = "particles"

EMISSION_SHAPES = ("point", "rect", "circle", "line")
EMISSION_MODES = ("continuous", "burst", "field")
FIELD_QUALITIES = ("low", "medium", "high")
# Density scale per quality (caps are runtime business; the editor fills
# up to max_particles). Mirrors the parser's quality density factors.
QUALITY_DENSITY = {"low": 0.72, "medium": 1.0, "high": 1.25}
PARTICLE_SHAPES = (
    "circle",
    "square",
    "diamond",
    "star",
    "sparkle",
    "smoke",
    "fog",
    "heart",
    "line",
)
ALPHA_FADE_MODES = ("none", "fade_out", "fade_in", "fade_both")

# Keys the editor schema owns. Must stay in sync with
# ``widgets.particle_system.DEFAULT_PARTICLE_CONFIG`` (a test pins the
# key sets equal); unknown keys in loaded data are preserved verbatim
# (forward tolerance) rather than dropped.
SCHEMA_KEYS: tuple[str, ...] = (
    "emission_shape",
    "particle_shape",
    "particle_size_min",
    "particle_size_max",
    "spawn_rate",
    "max_particles",
    "lifetime_min",
    "lifetime_max",
    "speed_min",
    "speed_max",
    "direction",
    "spread",
    "gravity_x",
    "gravity_y",
    "start_color_r",
    "start_color_g",
    "start_color_b",
    "start_color_a",
    "end_color_r",
    "end_color_g",
    "end_color_b",
    "end_color_a",
    "start_scale",
    "end_scale",
    "rotation_speed",
    "alpha_fade",
    "wrap",
    "fade_peak_alpha",
    # Phase B: emission mode + burst size (field mode arrives Phase C).
    "mode",
    "burst_count",
    # Phase C: persistent-field authoring.
    "coverage",
    "field_quality",
    "ground_bias",
    # Phase D: emitter clock. `mode`/`burst_count` stay top-level (the UI
    # gates on them); `timing` holds only the clock itself.
    "timing",
)

TIMING_DEFAULTS: dict[str, object] = {
    "emitter_duration": 0.0,
    "start_delay": 0.0,
    "loop": True,
    "burst_interval": 0.0,
}

SCHEMA_DEFAULTS: dict[str, object] = {
    "emission_shape": "point",
    "particle_shape": "circle",
    "particle_size_min": 2,
    "particle_size_max": 6,
    "spawn_rate": 20,
    "max_particles": 100,
    "lifetime_min": 0.5,
    "lifetime_max": 2.0,
    "speed_min": 20,
    "speed_max": 60,
    "direction": -1,
    "spread": 45,
    "gravity_x": 0,
    "gravity_y": 30,
    "start_color_r": 255,
    "start_color_g": 200,
    "start_color_b": 100,
    "start_color_a": 255,
    "end_color_r": 255,
    "end_color_g": 100,
    "end_color_b": 50,
    "end_color_a": 0,
    "start_scale": 1.0,
    "end_scale": 0.3,
    "rotation_speed": 0,
    "alpha_fade": "fade_out",
    "wrap": False,
    "fade_peak_alpha": None,
    "mode": "continuous",
    "burst_count": 30,
    "coverage": 1.0,
    "field_quality": "medium",
    "ground_bias": False,
    "timing": dict(TIMING_DEFAULTS),
}

_COLOR_KEYS = tuple(k for k in SCHEMA_KEYS if k.endswith(("_r", "_g", "_b", "_a")))


def _warn(warnings: list[str], msg: str) -> None:
    warnings.append(msg)


def _to_float(raw: object, default: float, key: str, warnings: list[str]) -> float:
    if isinstance(raw, bool):
        _warn(warnings, f"{key}: bool is not a number, using {default}")
        return default
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        _warn(warnings, f"{key}: {raw!r} is not a number, using {default}")
        return default
    if value != value:  # NaN survives JSON round-trips; never valid here
        _warn(warnings, f"{key}: NaN is not a number, using {default}")
        return default
    return value


def _to_int(raw: object, default: int, key: str, warnings: list[str]) -> int:
    if isinstance(raw, bool):
        _warn(warnings, f"{key}: bool is not a number, using {default}")
        return default
    try:
        value = int(float(raw))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        _warn(warnings, f"{key}: {raw!r} is not a number, using {default}")
        return default
    return value


def _clamp_int(
    raw: object,
    lo: int,
    hi: int,
    default: int,
    key: str,
    warnings: list[str],
) -> int:
    value = _to_int(raw, default, key, warnings)
    if value < lo or value > hi:
        _warn(warnings, f"{key}: {value} clamped to [{lo}, {hi}]")
    return max(lo, min(hi, value))


def _clamp_float(
    raw: object,
    lo: float,
    hi: float,
    default: float,
    key: str,
    warnings: list[str],
) -> float:
    value = _to_float(raw, default, key, warnings)
    if value < lo or value > hi:
        _warn(warnings, f"{key}: {value} clamped to [{lo}, {hi}]")
    return max(lo, min(hi, value))


def normalize_config(raw: dict | None) -> tuple[dict, list[str]]:
    """Return ``(normalized, warnings)`` for an arbitrary config dict.

    Missing keys gain editor defaults; out-of-range values are clamped;
    ``*_max`` is raised to ``*_min`` when inverted (with a warning);
    unknown shape/mode strings fall back (with a warning); unknown keys
    are preserved verbatim for forward tolerance. Never raises on data.
    """
    warnings: list[str] = []
    src: dict = raw if isinstance(raw, dict) else {}
    if not isinstance(raw, dict):
        _warn(warnings, "config is not a dict, using defaults")

    def g(key: str) -> object:
        return src.get(key, SCHEMA_DEFAULTS[key])

    out: dict[str, object] = {}

    emission = str(g("emission_shape"))
    if emission not in EMISSION_SHAPES:
        _warn(warnings, f"emission_shape: {emission!r} unknown, using 'point'")
        emission = "point"
    out["emission_shape"] = emission

    shape = str(g("particle_shape"))
    if shape not in PARTICLE_SHAPES:
        _warn(warnings, f"particle_shape: {shape!r} unknown, using 'circle'")
        shape = "circle"
    out["particle_shape"] = shape

    fade = str(g("alpha_fade"))
    if fade not in ALPHA_FADE_MODES:
        _warn(warnings, f"alpha_fade: {fade!r} unknown, using 'fade_out'")
        fade = "fade_out"
    out["alpha_fade"] = fade

    size_min = max(1, _to_int(g("particle_size_min"), 2, "particle_size_min", warnings))
    size_max = max(1, _to_int(g("particle_size_max"), 6, "particle_size_max", warnings))
    if size_max < size_min:
        _warn(warnings, f"particle_size_max ({size_max}) < min ({size_min}), raised")
        size_max = size_min
    out["particle_size_min"] = size_min
    out["particle_size_max"] = size_max

    out["spawn_rate"] = max(0, _to_int(g("spawn_rate"), 20, "spawn_rate", warnings))
    out["max_particles"] = max(
        1, _to_int(g("max_particles"), 100, "max_particles", warnings)
    )

    life_min = max(0.1, _to_float(g("lifetime_min"), 0.5, "lifetime_min", warnings))
    life_max = max(0.1, _to_float(g("lifetime_max"), 2.0, "lifetime_max", warnings))
    if life_max < life_min:
        _warn(warnings, f"lifetime_max ({life_max}) < min ({life_min}), raised")
        life_max = life_min
    out["lifetime_min"] = life_min
    out["lifetime_max"] = life_max

    speed_min = max(0.0, _to_float(g("speed_min"), 20.0, "speed_min", warnings))
    speed_max = max(0.0, _to_float(g("speed_max"), 60.0, "speed_max", warnings))
    if speed_max < speed_min:
        _warn(warnings, f"speed_max ({speed_max}) < min ({speed_min}), raised")
        speed_max = speed_min
    out["speed_min"] = speed_min
    out["speed_max"] = speed_max

    out["direction"] = _to_float(g("direction"), -1.0, "direction", warnings)
    out["spread"] = _clamp_float(g("spread"), 0.0, 360.0, 45.0, "spread", warnings)
    out["gravity_x"] = _to_float(g("gravity_x"), 0.0, "gravity_x", warnings)
    out["gravity_y"] = _to_float(g("gravity_y"), 30.0, "gravity_y", warnings)

    for key in _COLOR_KEYS:
        default = int(SCHEMA_DEFAULTS[key])  # type: ignore[arg-type]
        out[key] = _clamp_int(g(key), 0, 255, default, key, warnings)

    out["start_scale"] = max(
        0.1, _to_float(g("start_scale"), 1.0, "start_scale", warnings)
    )
    out["end_scale"] = max(0.1, _to_float(g("end_scale"), 0.3, "end_scale", warnings))
    out["rotation_speed"] = _to_float(
        g("rotation_speed"), 0.0, "rotation_speed", warnings
    )

    out["wrap"] = bool(g("wrap"))

    mode = str(g("mode"))
    if mode not in EMISSION_MODES:
        _warn(warnings, f"mode: {mode!r} unknown, using 'continuous'")
        mode = "continuous"
    out["mode"] = mode
    out["burst_count"] = max(0, _to_int(g("burst_count"), 30, "burst_count", warnings))

    cov = _to_float(g("coverage"), 1.0, "coverage", warnings)
    if cov < 0.05:
        _warn(warnings, f"coverage: {cov} below minimum 0.05, floored")
        cov = 0.05
    out["coverage"] = cov
    quality = str(g("field_quality"))
    if quality not in FIELD_QUALITIES:
        _warn(warnings, f"field_quality: {quality!r} unknown, using 'medium'")
        quality = "medium"
    out["field_quality"] = quality
    out["ground_bias"] = bool(g("ground_bias"))

    out["timing"] = _normalize_timing(src.get("timing"), warnings)

    raw_peak = src.get("fade_peak_alpha")
    if raw_peak is None:
        out["fade_peak_alpha"] = None
    else:
        out["fade_peak_alpha"] = _clamp_int(
            raw_peak, 0, 255, 255, "fade_peak_alpha", warnings
        )

    for key, value in src.items():
        if key not in SCHEMA_KEYS:
            out[key] = copy.deepcopy(value)

    return out, warnings


def _normalize_timing(raw: object, warnings: list[str]) -> dict[str, object]:
    """Normalize the optional ``timing`` block (never raises on data).

    Absent/non-dict -> defaults (infinite continuous emission, today's
    behavior). Negative clock values floor at 0 with a warning; unknown
    sub-keys are preserved verbatim for forward tolerance.
    """
    if raw is None:
        return dict(TIMING_DEFAULTS)
    if not isinstance(raw, dict):
        _warn(warnings, "timing: not a dict, using defaults")
        return dict(TIMING_DEFAULTS)
    out: dict[str, object] = {}
    for key, default in (
        ("emitter_duration", 0.0),
        ("start_delay", 0.0),
        ("burst_interval", 0.0),
    ):
        value = _to_float(raw.get(key, default), default, f"timing.{key}", warnings)
        if value < 0:
            _warn(warnings, f"timing.{key}: {value} below 0, floored")
            value = 0.0
        out[key] = value
    loop = raw.get("loop", True)
    if not isinstance(loop, bool):
        _warn(warnings, f"timing.loop: {loop!r} is not a bool, using True")
        loop = True
    out["loop"] = loop
    for key, value in raw.items():
        if key not in TIMING_DEFAULTS:
            out[key] = copy.deepcopy(value)
    return out


def validate_config(raw: dict | None) -> list[str]:
    """Return warnings for ``raw`` without keeping the normalized copy."""
    _, warnings = normalize_config(raw)
    return warnings


def fill_area(emission_shape: str, w: float, h: float) -> float:
    """Effective fill area of an emission shape over a ``w x h`` rect.

    Rect and line fill their whole band; circle fills the inscribed disc;
    point has no area and raises. Editor-owned math; consumers implement
    their own equivalent.
    """
    if emission_shape == "circle":
        radius = min(w, h) / 2
        return math.pi * radius * radius
    if emission_shape == "point":
        raise ValueError(
            "emission_shape 'point' has no fill area; use rect/circle/line"
        )
    return w * h


def count_for_coverage(config: dict | None, coverage: float, w: float, h: float) -> int:
    """Particles needed so sheets cover ``coverage`` of a ``w x h`` area.

    ``coverage`` is dimensionless (1.0 = one full layer). Count is
    ``coverage * fill_area / mean_particle_area`` with the circle-sheet
    fill factor (``pi/4`` of the bounding square, everything else full).
    Not capped -- callers cap at ``max_particles`` (``PreviewSim.fill``
    does). Raises ``ValueError`` for non-positive coverage or point
    emission, mirroring the failure contract consumers enforce.
    """
    normalized, _ = normalize_config(config)
    if coverage <= 0:
        raise ValueError(f"coverage must be > 0, got {coverage}")
    mean_size = (
        float(normalized["particle_size_min"]) + float(normalized["particle_size_max"])
    ) / 2
    if mean_size <= 0:
        return 0
    fill = math.pi / 4 if normalized["particle_shape"] == "circle" else 1.0
    area = fill_area(str(normalized["emission_shape"]), w, h)
    return max(0, round(coverage * area / (mean_size * mean_size * fill)))


@dataclass
class ParticleSystemEntry:
    name: str
    config: dict = field(default_factory=dict)

    def normalized(self) -> tuple[dict, list[str]]:
        return normalize_config(self.config)

    def to_dict(self) -> dict:
        config, _ = normalize_config(self.config)
        return {"name": self.name, "config": config}

    @classmethod
    def from_dict(
        cls, raw: object, ctx: str = "entry"
    ) -> tuple[ParticleSystemEntry | None, list[str]]:
        warnings: list[str] = []
        if not isinstance(raw, dict):
            return None, [f"{ctx}: not a dict, skipped"]
        name = raw.get("name", "")
        if not isinstance(name, str) or not name:
            return None, [f"{ctx}: missing/empty name, skipped"]
        config, norm_warnings = normalize_config(raw.get("config"))
        warnings.extend(f"{ctx} '{name}': {w}" for w in norm_warnings)
        return cls(name=name, config=config), warnings


@dataclass
class ParticleLibrary:
    systems: list[ParticleSystemEntry] = field(default_factory=list)

    def names(self) -> list[str]:
        return [s.name for s in self.systems]

    def find(self, name: str) -> ParticleSystemEntry | None:
        for system in self.systems:
            if system.name == name:
                return system
        return None

    def to_dict(self) -> dict:
        return {"particle_systems": [s.to_dict() for s in self.systems]}

    @classmethod
    def from_dict(
        cls, raw: object, source: str = "<memory>"
    ) -> tuple[ParticleLibrary, list[str]]:
        warnings: list[str] = []
        if not isinstance(raw, dict):
            return cls(), [f"{source}: root is not a dict"]
        items = raw.get("particle_systems", [])
        if not isinstance(items, list):
            return cls(), [f"{source}: 'particle_systems' is not a list"]
        systems: list[ParticleSystemEntry] = []
        for i, item in enumerate(items):
            entry, entry_warnings = ParticleSystemEntry.from_dict(
                item, ctx=f"particle_systems[{i}]"
            )
            warnings.extend(entry_warnings)
            if entry is not None:
                systems.append(entry)
        return cls(systems=systems), warnings

    @classmethod
    def load(cls, path: str | Path) -> tuple[ParticleLibrary, list[str]]:
        p = Path(path)
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except OSError as e:
            return cls(), [f"{p}: cannot read ({e})"]
        except json.JSONDecodeError as e:
            return cls(), [f"{p}: invalid JSON ({e})"]
        library, warnings = cls.from_dict(raw, source=str(p))
        return library, warnings

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")


def list_libraries(data_root: str | Path) -> list[Path]:
    """Sorted ``*.particles.json`` files under ``<data_root>/particles``."""
    root = Path(data_root) / LIBRARY_DIRNAME
    if not root.is_dir():
        return []
    return sorted(root.glob(f"*{LIBRARY_SUFFIX}"))


def builtin_library_path() -> Path:
    """Packaged ``essentials`` library (``data/`` is gitignored, so the
    shippable canonical copy lives next to this module)."""
    return Path(__file__).with_name("essentials.particles.json")


def builtin_library() -> tuple[ParticleLibrary, list[str]]:
    """Load the packaged essentials library."""
    return ParticleLibrary.load(builtin_library_path())


def diff_keys(a: dict, b: dict) -> list[str]:
    """Schema keys whose normalized values differ between two configs."""
    na, _ = normalize_config(a)
    nb, _ = normalize_config(b)
    keys: set[str] = set(na) | set(nb)
    return sorted(k for k in keys if na.get(k) != nb.get(k))


def modified_from(
    config: dict | None, library: ParticleLibrary, max_changed: int = 3
) -> str | None:
    """Name of the library entry ``config`` looks modified from, if any.

    Exact matches are not "modified" (returns ``None``); otherwise the
    first entry differing in at most ``max_changed`` schema keys wins.
    """
    normalized, _ = normalize_config(config)
    for system in library.systems:
        entry_config, _ = normalize_config(system.config)
        if normalized == entry_config:
            return None
    for system in library.systems:
        if len(diff_keys(normalized, system.config)) <= max_changed:
            return system.name
    return None


def identify(config: dict | None, library: ParticleLibrary) -> str:
    """Derived preset identity: ``"Name" | "Name * Modified" | "Custom"``.

    Computed on every call from the config itself -- never stored -- so it
    cannot go stale.
    """
    normalized, _ = normalize_config(config)
    for system in library.systems:
        entry_config, _ = normalize_config(system.config)
        if normalized == entry_config:
            return system.name
    base = modified_from(normalized, library)
    if base is not None:
        return f"{base} (modified)"
    return "Custom"
