"""Headless transport core for the particle editor preview."""

from __future__ import annotations

import math
import random

from widgets.particle_system import MAX_DT, ParticlePreview

from .models import QUALITY_DENSITY, count_for_coverage

FIXED_DT = 1.0 / 60.0
MAX_STEPS_PER_FRAME = 8
SPEEDS = (0.25, 0.5, 1.0, 2.0)
BURST_POPS = 10
# tolerance for clock boundary comparisons
CLOCK_EPS = 1e-9


def _timing_of(config: dict) -> dict[str, float | bool]:
    """Read the timing block defensively (never raises on data)."""
    raw = config.get("timing")
    block = raw if isinstance(raw, dict) else {}
    if not isinstance(block, dict):
        block = {}

    def num(key: str, default: float) -> float:
        try:
            value = float(block.get(key, default))
        except (TypeError, ValueError):
            return default
        if isinstance(block.get(key), bool) or not math.isfinite(value):
            return default
        return max(0.0, value)

    return {
        "emitter_duration": num("emitter_duration", 0.0),
        "start_delay": num("start_delay", 0.0),
        "loop": block.get("loop", True) is True,
        "burst_interval": num("burst_interval", 0.0),
    }


class PreviewSim:
    """Transport + clock over a ``ParticlePreview`` in a fixed area."""

    def __init__(
        self,
        config: dict,
        area: tuple[float, float, float, float] = (0.0, 0.0, 240.0, 240.0),
    ):
        self.area = tuple(area)
        self.preview = ParticlePreview(dict(config))
        self.elapsed: float = 0.0
        self.playing: bool = True
        self.speed: float = 1.0
        self.fixed_step: bool = True
        self.dt_clamped: bool = False
        self._acc: float = 0.0

        self.clock: float = 0.0
        self._burst_pending: int = 0
        self._burst_total: int = 0
        self._burst_tick: float = 0.0
        self._timing = _timing_of(self.preview.config)
        self.refill_if_field()

    @property
    def config(self) -> dict:
        return self.preview.config

    def live_set(self, config: dict) -> None:
        """Live-editable keys: swap config, keep particles and clock."""
        self.preview.config = dict(config)
        self._timing = _timing_of(self.preview.config)

    def clear_particles(self) -> None:
        """Respawn-tier change: drop live particles, keep the clock.

        On a field contract this re-fills immediately (fresh particles
        under the new params) so the canvas never goes empty.
        """
        self.preview.clear()
        self.refill_if_field()

    def reset(self, config: dict) -> None:
        """Reset-tier change: new config, cleared particles, zero clock."""
        self.preview.reset(dict(config))
        self.elapsed = 0.0
        self._acc = 0.0
        self.clock = 0.0
        self._burst_pending = 0
        self._burst_total = 0
        self._burst_tick = 0.0
        self._timing = _timing_of(self.preview.config)
        self.refill_if_field()

    def restart(self) -> None:
        self.preview.clear()
        self.elapsed = 0.0
        self._acc = 0.0
        self.clock = 0.0
        self._burst_pending = 0
        self._burst_total = 0
        self._burst_tick = 0.0
        self.refill_if_field()

    def is_field_contract(self) -> bool:
        """Fill-once contract holds: wrap on, spawn rate zero."""
        try:
            spawn = int(self.preview.config.get("spawn_rate", 0))
        except (TypeError, ValueError):
            return False
        return bool(self.preview.config.get("wrap")) and spawn == 0

    def field_fill_count(self) -> int:
        """Coverage-derived fill count for the current config and area."""
        cfg = self.preview.config
        density = QUALITY_DENSITY.get(str(cfg.get("field_quality", "medium")), 1.0)
        raw = count_for_coverage(
            cfg,
            float(cfg.get("coverage", 1.0)) * density,
            self.area[2],
            self.area[3],
        )
        return max(0, raw)

    def refill_if_field(self) -> int:
        """Auto-fill after load/restart/undo when the field contract holds.

        Returns the filled count (0 when not a field). Loading a field
        preset must show the field immediately -- never an empty canvas.
        """
        if not self.is_field_contract():
            return 0
        try:
            count = self.field_fill_count()
        except (ValueError, TypeError):
            return 0
        return self._burst_fill(count)

    @property
    def count(self) -> int:
        return len(self.preview.particles)

    @property
    def state(self) -> str:
        return "live" if self.playing else "paused"

    @property
    def phase(self) -> str:
        """Emitter phase: ``delay`` | ``active`` | ``expired``."""
        delay = float(self._timing["start_delay"])
        duration = float(self._timing["emitter_duration"])
        if self.clock + CLOCK_EPS < delay:
            return "delay"
        if duration > 0 and self.clock + CLOCK_EPS >= delay + duration:
            return "expired"
        return "active"

    def status_text(self) -> str:
        """One-line transport state for the canvas header."""
        if not self.playing:
            return "paused"
        phase = self.phase
        if phase == "delay":
            remaining = float(self._timing["start_delay"]) - self.clock
            return f"delay {max(0.0, remaining):.1f}s"
        if phase == "expired":
            return "idle" if self.count == 0 else "ending"
        return "live"

    def trigger_burst(self, count: int | None = None) -> int:
        """Fire one burst, even while paused or outside the window.

        With ``burst_interval > 0`` the burst goes out in up to
        ``BURST_POPS`` pops spaced by the interval (first pop
        immediate); returns particles emitted *now*, remainder pending.
        Otherwise everything fires at once, as before.
        """
        if count is None:
            try:
                count = int(self.preview.config.get("burst_count", 30))
            except (TypeError, ValueError):
                count = 30
        count = max(0, count)
        interval = float(self._timing["burst_interval"])
        if interval > 0 and count > 0:
            self._burst_total = count
            self._burst_pending = count
            self._burst_tick = 0.0
            return self._emit_burst_pop()  # first pop immediate
        self._burst_pending = 0
        self._burst_total = 0
        return self.preview.burst(count, *self.area)

    def _emit_burst_pop(self) -> int:
        chunk = max(1, math.ceil(self._burst_total / BURST_POPS))
        want = min(chunk, self._burst_pending)
        n = self.preview.burst(want, *self.area)
        self._burst_pending -= n
        if n < want:
            self._burst_pending = 0
        return n

    def fill(self, count: int) -> int:
        """Fill-once: clear to a fresh clock, then burst ``count``.

        The caller derives ``count`` (coverage x quality); ``burst``
        caps at max particles. Used by field mode. Manual action:
        bypasses the emitter clock (which restarts from zero).
        """
        self.preview.clear()
        self.elapsed = 0.0
        self._acc = 0.0
        self.clock = 0.0
        self._burst_pending = 0
        self._burst_total = 0
        self._burst_tick = 0.0
        return self._burst_fill(count)

    def _burst_fill(self, count: int) -> int:
        """Burst ``count`` without touching the clock (internal)."""
        return self.preview.burst(max(0, int(count)), *self.area)

    def step_frame(self) -> None:
        """Advance exactly one fixed step (works paused or playing)."""
        self._advance(FIXED_DT)

    def update(self, real_dt: float) -> None:
        """Advance by scaled real time. No-op while paused."""
        self.dt_clamped = False
        if not self.playing:
            return
        scaled = max(0.0, real_dt) * self.speed
        if self.fixed_step:
            self._acc += scaled
            steps = 0
            while self._acc >= FIXED_DT and steps < MAX_STEPS_PER_FRAME:
                self._advance(FIXED_DT)
                self._acc -= FIXED_DT
                steps += 1
            if self._acc >= FIXED_DT:
                self._acc = 0.0
                self.dt_clamped = True
            if scaled > MAX_DT * MAX_STEPS_PER_FRAME:
                self.dt_clamped = True
        else:
            if scaled > MAX_DT:
                self.dt_clamped = True
            self._advance(min(scaled, MAX_DT))

    def _advance(self, dt: float) -> None:
        self.clock += dt
        self._pump_clock()
        spawn_open = self.phase == "active"
        self._pump_burst_pops(dt)
        ax, ay, aw, ah = self.area
        self.preview.update(dt, ax, ay, aw, ah, spawn_enabled=spawn_open)
        self.elapsed += dt

    def _pump_clock(self) -> None:
        """Handle delay window and duration expiry (loop wraps)."""
        delay = float(self._timing["start_delay"])
        duration = float(self._timing["emitter_duration"])
        if duration <= 0 or self.clock + CLOCK_EPS < delay + duration:
            return
        if self._timing["loop"]:
            self.preview.clear()
            self.clock = 0.0
            self._burst_pending = 0
            self._burst_total = 0
            self._burst_tick = 0.0
            self.refill_if_field()

    def _pump_burst_pops(self, dt: float) -> None:
        """Emit scheduled interval-spread pops. Manual pops fire in any
        phase -- a trigger is an explicit user action, not stream spawn."""
        if self._burst_pending <= 0:
            return
        interval = float(self._timing["burst_interval"])
        if interval <= 0:
            self._burst_pending = 0
            return
        self._burst_tick += dt
        while self._burst_tick + CLOCK_EPS >= interval and self._burst_pending > 0:
            self._burst_tick -= interval
            self._emit_burst_pop()

    def seed(self, value: int) -> None:
        """Pin randomness for deterministic tests/screenshots."""
        random.seed(value)
