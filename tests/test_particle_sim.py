"""Unit tests for the particle simulation layer.

Transport, severity tiers, wrap/field physics, the emitter clock, and
engine shapes. Slow soak and determinism live here; UI journeys live
in e2e/.
"""

import math

import pygame
import pytest

from plugins.particle_editor.editor import ParticleEditor
from plugins.particle_editor.models import builtin_library, builtin_library_path
from plugins.particle_editor.presets import get_preset_config
from plugins.particle_editor.sim import FIXED_DT, PreviewSim
from widgets.particle_system import Particle, ParticlePreview

AREA = (0.0, 0.0, 240.0, 240.0)


def _campfire_config() -> dict:
    return get_preset_config("Campfire")


def _make_editor(tmp_path, name="Campfire"):
    library, _ = builtin_library()
    editor = ParticleEditor(
        pygame.Rect(0, 0, 1180, 760),
        library,
        builtin_library_path(),
        tmp_path,
    )
    editor.load_entry(name, get_preset_config(name))
    return editor


def _timed(base: dict, **overrides) -> dict:
    cfg = dict(base)
    timing = {
        "emitter_duration": 0.0,
        "start_delay": 0.0,
        "loop": True,
        "burst_interval": 0.0,
    }
    timing.update(overrides)
    cfg["timing"] = timing
    return cfg


class TestTransportLifecycle:
    def test_pause_restart_and_step(self):
        sim = PreviewSim(_campfire_config())
        sim.seed(7)
        for _ in range(30):
            sim.update(FIXED_DT)
        assert sim.count > 0 and sim.elapsed > 0

        sim.playing = False
        frozen = (sim.count, sim.elapsed)
        for _ in range(30):
            sim.update(FIXED_DT)
        assert (sim.count, sim.elapsed) == frozen
        assert sim.state == "paused"

        sim.step_frame()
        assert sim.elapsed == pytest.approx(frozen[1] + FIXED_DT)

        sim.playing = True
        sim.restart()
        assert sim.count == 0 and sim.elapsed == 0.0

    def test_burst_fires_even_while_paused(self):
        sim = PreviewSim(_campfire_config())
        sim.seed(7)
        sim.playing = False
        n = sim.trigger_burst(25)
        assert n == 25 and sim.count == 25

    def test_speed_scales_sim_time(self):
        slow = PreviewSim(_campfire_config())
        fast = PreviewSim(_campfire_config())
        slow.seed(7)
        fast.seed(7)
        slow.speed = 0.5
        fast.speed = 2.0
        for _ in range(30):
            slow.update(FIXED_DT)
            fast.update(FIXED_DT)
        assert fast.elapsed == pytest.approx(slow.elapsed * 4)

    def test_fixed_step_determinism(self):
        def run():
            sim = PreviewSim(_campfire_config())
            sim.seed(42)
            for _ in range(120):
                sim.update(FIXED_DT)
            return sim

        a, b = run(), run()
        assert a.count == b.count
        assert [(p.x, p.y) for p in a.preview.particles] == [
            (p.x, p.y) for p in b.preview.particles
        ]

    def test_huge_dt_flags_clamped(self):
        sim = PreviewSim(_campfire_config())
        sim.update(10.0)
        assert sim.dt_clamped


class TestSeverityTiers:
    def test_live_edit_keeps_particles(self, tmp_path):
        editor = _make_editor(tmp_path)
        editor.sim.seed(7)
        for _ in range(30):
            editor.update(FIXED_DT)
        assert editor.sim.count > 0
        before = [id(p) for p in editor.sim.preview.particles]
        editor.controls["gravity_x"].set_value(50)
        editor._apply_change("gravity_x")
        assert [id(p) for p in editor.sim.preview.particles] == before

    def test_reset_tier_clears_particles(self, tmp_path):
        editor = _make_editor(tmp_path)
        editor.sim.seed(7)
        for _ in range(30):
            editor.update(FIXED_DT)
        assert editor.sim.count > 0
        editor.controls["particle_shape"].set_value("square")
        editor._apply_change("particle_shape")
        assert editor.sim.count == 0
        assert editor.sim.elapsed == 0.0

    def test_respawn_tier_clears_but_keeps_clock(self, tmp_path):
        editor = _make_editor(tmp_path)
        editor.sim.seed(7)
        for _ in range(30):
            editor.update(FIXED_DT)
        elapsed = editor.sim.elapsed
        assert elapsed > 0
        editor.controls["speed_max"].set_value(90)
        editor._apply_change("speed_max")
        assert editor.sim.count == 0
        assert editor.sim.elapsed == pytest.approx(elapsed)


class TestWrapBranch:
    def test_wrap_never_dies_and_stays_bounded(self):
        sim = PreviewSim(get_preset_config("Mist Bed"))
        sim.seed(11)
        filled = sim.fill(79)
        assert filled == 79
        for _ in range(600):
            sim.update(FIXED_DT)
        assert sim.count == filled
        ax, ay, aw, ah = AREA
        margin = 40.0  # half max size + drift slack
        for p in sim.preview.particles:
            assert ax - margin <= p.x <= ax + aw + margin
            assert ay - margin <= p.y <= ay + ah + margin

        non_wrap = PreviewSim(_campfire_config())
        non_wrap.seed(7)
        for _ in range(600):
            non_wrap.update(FIXED_DT)
        assert 0 < non_wrap.count < 70  # control: streams settle below cap

    def test_progress_clamps_past_death(self):
        p = Particle(
            x=0,
            y=0,
            vx=0,
            vy=0,
            lifetime=0.01,
            size=4,
            start_color=(255, 0, 0, 255),
            end_color=(0, 0, 255, 10),
            start_scale=1.0,
            end_scale=2.0,
            rotation_speed=0,
            alpha_fade="fade_out",
        )
        assert p.update(0.05, 0, 0) is False
        assert p.progress == 1.0
        assert p.current_color == (0, 0, 255, 10)
        assert p.current_size == pytest.approx(8.0)

    def test_ground_bias_concentrates_low_band(self):
        base = {
            "emission_shape": "rect",
            "particle_shape": "circle",
            "particle_size_min": 4,
            "particle_size_max": 4,
            "spawn_rate": 0,
            "max_particles": 600,
            "lifetime_min": 60.0,
            "lifetime_max": 60.0,
            "speed_min": 0,
            "speed_max": 0,
            "direction": 0,
            "spread": 0,
            "gravity_x": 0,
            "gravity_y": 0,
        }
        plain = ParticlePreview(dict(base))
        import random

        random.seed(5)
        plain.burst(500, *AREA)
        low_plain = sum(1 for p in plain.particles if p.y >= AREA[1] + AREA[3] * 0.35)

        biased = ParticlePreview(dict(base, ground_bias=True))
        random.seed(5)
        spawned = biased.burst(500, *AREA)
        low_biased = sum(1 for p in biased.particles if p.y >= AREA[1] + AREA[3] * 0.35)

        assert low_biased == spawned  # all in the lower 65% band
        assert low_biased > low_plain

    def test_direction_sign_is_deterministic(self):
        left = PreviewSim(
            {
                "emission_shape": "point",
                "particle_shape": "circle",
                "spawn_rate": 60,
                "max_particles": 50,
                "direction": 0,
                "spread": 30,
            }
        )
        left.seed(3)
        for _ in range(30):
            left.update(FIXED_DT)
        mean_vx = sum(p.vx for p in left.preview.particles) / left.count
        assert mean_vx > 0

        right = PreviewSim(
            {
                "emission_shape": "point",
                "particle_shape": "circle",
                "spawn_rate": 60,
                "max_particles": 50,
                "direction": 180,
                "spread": 30,
            }
        )
        right.seed(3)
        for _ in range(30):
            right.update(FIXED_DT)
        mean_vx = sum(p.vx for p in right.preview.particles) / right.count
        assert mean_vx < 0


class TestFill:
    def test_fill_caps_and_resets_clock(self):
        sim = PreviewSim(get_preset_config("Mist Bed"))
        assert sim.fill(10000) == 150
        assert sim.count == 150
        sim.seed(1)
        for _ in range(60):
            sim.update(FIXED_DT)
        assert sim.elapsed > 0
        sim.fill(10)
        assert sim.elapsed == 0.0
        assert sim.count == 10


class TestSoak:
    def test_mist_bed_60s_stable_and_spread(self):
        sim = PreviewSim(get_preset_config("Mist Bed"))
        sim.seed(11)
        filled = sim.fill(79)
        for _ in range(3600):
            sim.update(FIXED_DT)
        assert sim.count == filled  # zero deaths: pool stable
        ax, ay, aw, ah = AREA
        quadrants = [0, 0, 0, 0]
        for p in sim.preview.particles:
            qx = 0 if p.x < ax + aw / 2 else 1
            qy = 0 if p.y < ay + ah / 2 else 2
            quadrants[qx + qy] += 1
        assert all(q > 0 for q in quadrants)  # no clumping into one corner


class TestEmitterClock:
    def test_delay_stages_spawning(self):
        sim = PreviewSim(_timed(get_preset_config("Campfire"), start_delay=1.0))
        sim.seed(1)
        for _ in range(30):
            sim.update(FIXED_DT)
        assert sim.count == 0
        assert sim.phase == "delay"
        assert sim.status_text().startswith("delay")
        for _ in range(60):
            sim.update(FIXED_DT)
        assert sim.count > 0
        assert sim.phase == "active"
        assert sim.status_text() == "live"

    def test_duration_expiry_ends_then_idles(self):
        sim = PreviewSim(
            _timed(get_preset_config("Campfire"), emitter_duration=2.0, loop=False)
        )
        sim.seed(1)
        for _ in range(120):  # exactly the 2 s window
            sim.update(FIXED_DT)
        assert sim.phase == "expired"
        assert sim.count > 0
        assert sim.status_text() == "ending"
        for _ in range(600):  # live particles finish, nothing replaces them
            sim.update(FIXED_DT)
        assert sim.count == 0
        assert sim.status_text() == "idle"

    def test_loop_wraps_clear_and_reenters_delay(self):
        sim = PreviewSim(
            _timed(get_preset_config("Campfire"), emitter_duration=2.0, loop=True)
        )
        sim.seed(1)
        for _ in range(150):  # 2.5 s: one wrap at 2 s
            sim.update(FIXED_DT)
        assert sim.phase == "active"
        assert sim.clock == pytest.approx(0.5, abs=FIXED_DT * 2)
        # Fresh clock means only ~0.5 s of spawns are alive.
        assert sim.count < 40

        delayed = PreviewSim(
            _timed(
                get_preset_config("Campfire"),
                emitter_duration=1.0,
                start_delay=0.5,
                loop=True,
            )
        )
        delayed.seed(1)
        for _ in range(110):  # 1.83 s: wrapped at 1.5 s, clock 0.33 < delay
            delayed.update(FIXED_DT)
        assert delayed.phase == "delay"

    def test_pause_and_step_freeze_and_advance_clock(self):
        sim = PreviewSim(_timed(get_preset_config("Campfire"), start_delay=0.5))
        sim.playing = False
        for _ in range(120):
            sim.update(FIXED_DT)
        assert sim.clock == 0.0
        assert sim.status_text() == "paused"
        for _ in range(30):
            sim.step_frame()
        assert sim.clock == pytest.approx(0.5, abs=1e-9)
        assert sim.phase == "active"

    def test_determinism_with_clock(self):
        def run():
            sim = PreviewSim(
                _timed(
                    get_preset_config("Campfire"),
                    emitter_duration=2.0,
                    start_delay=0.5,
                    loop=True,
                )
            )
            sim.seed(9)
            for _ in range(200):
                sim.update(FIXED_DT)
            return sim

        a, b = run(), run()
        assert (a.count, round(a.clock, 9)) == (b.count, round(b.clock, 9))
        assert [(p.x, p.y) for p in a.preview.particles] == [
            (p.x, p.y) for p in b.preview.particles
        ]


class TestBurstPops:
    def _quiet(self, **overrides):
        cfg = _timed(get_preset_config("Explosion"), **overrides)
        cfg["spawn_rate"] = 0  # isolate pops from the stream
        cfg["lifetime_min"] = 5.0  # outlive every test window
        cfg["lifetime_max"] = 10.0
        return PreviewSim(cfg)

    def test_instant_burst_without_interval(self):
        sim = self._quiet(burst_interval=0.0)
        sim.seed(1)
        assert sim.trigger_burst(60) == 60
        assert sim.count == 60

    def test_interval_spreads_pops(self):
        sim = self._quiet(burst_interval=0.1)
        sim.seed(1)
        first = sim.trigger_burst(60)
        assert 0 < first < 60  # first of up to 10 pops, rest pending
        for _ in range(70):  # 9 more pops need 0.9 s
            sim.update(FIXED_DT)
        assert sim._burst_pending == 0
        assert sim.count == 60
        # ...while paused, stepping still advances scheduled pops.
        sim.playing = False
        sim.trigger_burst(60)
        started = sim.count
        for _ in range(12):
            sim.step_frame()
        assert sim.count > started

    def test_full_pool_drops_remainder(self):
        sim = self._quiet(burst_interval=0.1)
        sim.seed(1)
        sim.fill(80)  # pool at cap
        sim.trigger_burst(60)
        for _ in range(120):
            sim.update(FIXED_DT)
        assert sim._burst_pending == 0


class TestSpawnGate:
    def test_preview_suppresses_spawn_directly(self):
        preview = ParticlePreview(get_preset_config("Campfire"))
        import random

        random.seed(2)
        preview.update(FIXED_DT, 0, 0, 240, 240, spawn_enabled=False)
        assert preview.particles == []
        preview.update(FIXED_DT, 0, 0, 240, 240)
        # spawn_rate 30/s needs ~2 frames per particle; run a while
        for _ in range(60):
            preview.update(FIXED_DT, 0, 0, 240, 240)
        assert len(preview.particles) > 0


class TestEngineShapes:
    def test_fog_texture_registered(self):
        from widgets.particle_system import PARTICLE_SHAPES, get_particle_texture

        assert "fog" in PARTICLE_SHAPES
        tex = get_particle_texture("fog")
        assert tex.get_size() == (24, 24)
        assert tex.get_at((12, 12)).a > 0

    def test_peak_alpha_reaches_preview(self):
        preview = ParticlePreview(
            {
                "particle_shape": "circle",
                "fade_peak_alpha": 120,
                "alpha_fade": "fade_both",
            }
        )
        preview._spawn_particle(0, 0, 64, 64)
        assert preview.particles[0].peak_alpha == 120
