from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

import pygame
from pygame import Rect, Surface

PARTICLE_TEXTURE_SIZE = 24
MAX_PREVIEW_PARTICLES = 200
# Base texture is 24px; dividing by this factor normalizes it to ~4px,
# matching the middle of the particle_size_min..particle_size_max range.
PARTICLE_TEXTURE_SCALE_FACTOR = 6
MAX_DT = 0.05


DEFAULT_PARTICLE_CONFIG: Dict[str, object] = {
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
}

EMISSION_SHAPES = ["point", "rect", "circle", "line"]
PARTICLE_SHAPES = ["circle", "square", "diamond", "star", "sparkle", "smoke", "heart", "line"]
ALPHA_FADE_MODES = ["none", "fade_out", "fade_in", "fade_both"]

FLOAT_FIELDS = {
    "particle_size_min": (1, 32, "Min Size"),
    "particle_size_max": (1, 32, "Max Size"),
    "spawn_rate": (1, 300, "Rate/s"),
    "max_particles": (1, 500, "Max #"),
    "lifetime_min": (0.1, 5.0, "Min Life"),
    "lifetime_max": (0.1, 5.0, "Max Life"),
    "speed_min": (0, 300, "Min Speed"),
    "speed_max": (0, 300, "Max Speed"),
    "direction": (-1, 360, "Direction"),
    "spread": (0, 180, "Spread"),
    "gravity_x": (-200, 200, "Gravity X"),
    "gravity_y": (-200, 200, "Gravity Y"),
    "start_scale": (0.1, 3.0, "Start Scale"),
    "end_scale": (0.1, 3.0, "End Scale"),
    "rotation_speed": (-360, 360, "Rot Speed"),
}

COLOR_FIELDS = [
    ("start_color_r", "R"),
    ("start_color_g", "G"),
    ("start_color_b", "B"),
    ("start_color_a", "A"),
    ("end_color_r", "R"),
    ("end_color_g", "G"),
    ("end_color_b", "B"),
    ("end_color_a", "A"),
]


_TEXTURE_CACHE: Dict[str, Surface] = {}


def _make_circle_texture() -> Surface:
    s = Surface((PARTICLE_TEXTURE_SIZE, PARTICLE_TEXTURE_SIZE), pygame.SRCALPHA)
    cx = cy = PARTICLE_TEXTURE_SIZE // 2
    r = PARTICLE_TEXTURE_SIZE // 2 - 1
    for i in range(r, 0, -1):
        t = i / r
        alpha = int(255 * (1 - t * t))
        pygame.draw.circle(s, (255, 255, 255, alpha), (cx, cy), i)
    return s


def _make_square_texture() -> Surface:
    s = Surface((PARTICLE_TEXTURE_SIZE, PARTICLE_TEXTURE_SIZE), pygame.SRCALPHA)
    pygame.draw.rect(
        s,
        (255, 255, 255, 255),
        Rect(2, 2, PARTICLE_TEXTURE_SIZE - 4, PARTICLE_TEXTURE_SIZE - 4),
        border_radius=2,
    )
    return s


def _make_diamond_texture() -> Surface:
    s = Surface((PARTICLE_TEXTURE_SIZE, PARTICLE_TEXTURE_SIZE), pygame.SRCALPHA)
    cx = PARTICLE_TEXTURE_SIZE // 2
    cy = PARTICLE_TEXTURE_SIZE // 2
    r = PARTICLE_TEXTURE_SIZE // 2 - 2
    points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    pygame.draw.polygon(s, (255, 255, 255, 255), points)
    return s


def _make_star_texture() -> Surface:
    s = Surface((PARTICLE_TEXTURE_SIZE, PARTICLE_TEXTURE_SIZE), pygame.SRCALPHA)
    cx = cy = PARTICLE_TEXTURE_SIZE // 2
    r = PARTICLE_TEXTURE_SIZE // 2 - 2
    points: List[Tuple[float, float]] = []
    for i in range(8):
        angle = math.pi * 2 * i / 8 - math.pi / 2
        radius = r if i % 2 == 0 else r * 0.4
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    pygame.draw.polygon(s, (255, 255, 255, 255), points)
    return s


def _make_sparkle_texture() -> Surface:
    s = Surface((PARTICLE_TEXTURE_SIZE, PARTICLE_TEXTURE_SIZE), pygame.SRCALPHA)
    cx = cy = PARTICLE_TEXTURE_SIZE // 2
    half = PARTICLE_TEXTURE_SIZE // 2
    for dx in range(-half, half):
        dist = abs(dx)
        alpha = max(0, int(180 * (1 - dist / half)))
        if alpha > 0:
            s.set_at((cx + dx, cy), (255, 255, 255, alpha))
            s.set_at((cx, cy + dx), (255, 255, 255, alpha))
    for r in range(2, 0, -1):
        alpha = int(200 * (1 - r / 3))
        pygame.draw.circle(s, (255, 255, 255, alpha), (cx, cy), r)
    return s


def _make_smoke_texture() -> Surface:
    s = Surface((PARTICLE_TEXTURE_SIZE, PARTICLE_TEXTURE_SIZE), pygame.SRCALPHA)
    cx = cy = PARTICLE_TEXTURE_SIZE // 2
    r_max = PARTICLE_TEXTURE_SIZE // 2 - 1
    for r in range(r_max, 0, -1):
        t = r / r_max
        alpha = int(100 * (1 - t ** 1.5))
        if alpha > 0:
            pygame.draw.circle(s, (255, 255, 255, alpha), (cx, cy), r)
    return s


def _make_heart_texture() -> Surface:
    s = Surface((PARTICLE_TEXTURE_SIZE, PARTICLE_TEXTURE_SIZE), pygame.SRCALPHA)
    cx = PARTICLE_TEXTURE_SIZE // 2
    cy = PARTICLE_TEXTURE_SIZE // 2
    points: List[Tuple[float, float]] = []
    for i in range(60):
        t = math.pi * 2 * i / 60
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        points.append((cx + x * 0.7, cy - y * 0.7))
    pygame.draw.polygon(s, (255, 255, 255, 255), points)
    return s


def _make_line_texture() -> Surface:
    s = Surface((PARTICLE_TEXTURE_SIZE, PARTICLE_TEXTURE_SIZE), pygame.SRCALPHA)
    cx = PARTICLE_TEXTURE_SIZE // 2
    thickness = 3
    half = thickness // 2
    pygame.draw.rect(s, (255, 255, 255, 255), Rect(cx - half, 2, thickness, PARTICLE_TEXTURE_SIZE - 4))
    return s


def get_particle_texture(shape: str) -> Surface:
    if shape not in _TEXTURE_CACHE:
        makers = {
            "circle": _make_circle_texture,
            "square": _make_square_texture,
            "diamond": _make_diamond_texture,
            "star": _make_star_texture,
            "sparkle": _make_sparkle_texture,
            "smoke": _make_smoke_texture,
            "heart": _make_heart_texture,
            "line": _make_line_texture,
        }
        maker = makers.get(shape, _make_circle_texture)
        _TEXTURE_CACHE[shape] = maker()
    return _TEXTURE_CACHE[shape]


def get_default_config() -> Dict[str, object]:
    return dict(DEFAULT_PARTICLE_CONFIG)


class Particle:
    __slots__ = (
        "alpha_fade", "end_color", "end_size",
        "life", "max_life",
        "rotation", "rotation_speed",
        "size", "start_color", "start_size",
        "vx", "vy", "x", "y",
    )

    def __init__(
        self,
        x: float, y: float,
        vx: float, vy: float,
        lifetime: float,
        size: float,
        start_color: Tuple[int, int, int, int],
        end_color: Tuple[int, int, int, int],
        start_scale: float, end_scale: float,
        rotation_speed: float,
        alpha_fade: str,
    ):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = lifetime
        self.max_life = lifetime
        self.size = size
        self.start_size = size * start_scale
        self.end_size = size * end_scale
        self.start_color = start_color
        self.end_color = end_color
        self.rotation = random.uniform(0, 360)
        self.rotation_speed = rotation_speed
        self.alpha_fade = alpha_fade

    def update(self, dt: float, grav_x: float, grav_y: float) -> bool:
        self.life -= dt
        if self.life <= 0:
            return False
        self.vx += grav_x * dt
        self.vy += grav_y * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rotation += self.rotation_speed * dt
        return True

    @property
    def progress(self) -> float:
        if self.max_life <= 0:
            return 1.0
        return max(0.0, 1.0 - self.life / self.max_life)

    @property
    def current_size(self) -> float:
        t = self.progress
        return self.start_size + (self.end_size - self.start_size) * t

    @property
    def current_color(self) -> Tuple[int, int, int, int]:
        t = self.progress
        r = int(self.start_color[0] + (self.end_color[0] - self.start_color[0]) * t)
        g = int(self.start_color[1] + (self.end_color[1] - self.start_color[1]) * t)
        b = int(self.start_color[2] + (self.end_color[2] - self.start_color[2]) * t)
        a_start = self.start_color[3]
        a_end = self.end_color[3]
        if self.alpha_fade == "none":
            a = a_start
        elif self.alpha_fade == "fade_out":
            a = int(a_start + (a_end - a_start) * t)
        elif self.alpha_fade == "fade_in":
            a = int(a_end + (a_start - a_end) * t)
        else:
            mid = 0.5
            if t < mid:
                a = int(a_start + (255 - a_start) * (t / mid))
            else:
                a = int(255 + (a_end - 255) * ((t - mid) / mid))
        return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)), max(0, min(255, a)))


class ParticlePreview:
    def __init__(self, config: Dict[str, object]):
        self.config = dict(config)
        self.particles: List[Particle] = []
        self.spawn_timer: float = 0.0
        self.texture = get_particle_texture(str(self.config.get("particle_shape", "circle")))
        self._current_shape = str(self.config.get("particle_shape", "circle"))

    def _get(self, key: str, default: object = 0) -> float:
        val = self.config.get(key, default)
        return float(val) if val is not None else float(default)

    def update(self, dt: float, area_x: int, area_y: int, area_w: int, area_h: int):
        cfg = self.config
        max_particles = int(self._get("max_particles", 100))
        spawn_rate = self._get("spawn_rate", 20)

        if self._get("particle_size_min", 2) > self._get("particle_size_max", 6):
            return

        if "particle_shape" in cfg:
            shape = str(cfg["particle_shape"])
            if shape != self._current_shape:
                self.texture = get_particle_texture(shape)
                self._current_shape = shape

        capped_max = min(max_particles, MAX_PREVIEW_PARTICLES)
        self.spawn_timer += dt * spawn_rate

        while self.spawn_timer >= 1.0 and len(self.particles) < capped_max:
            self.spawn_timer -= 1.0
            self._spawn_particle(area_x, area_y, area_w, area_h)

        grav_x = self._get("gravity_x", 0)
        grav_y = self._get("gravity_y", 30)

        for p in self.particles[:]:
            if not p.update(dt, grav_x, grav_y):
                self.particles.remove(p)

    def _spawn_particle(self, area_x: int, area_y: int, area_w: int, area_h: int):
        cfg = self.config
        emission = str(cfg.get("emission_shape", "point"))

        if emission == "point":
            x = area_x + area_w / 2
            y = area_y + area_h / 2
        elif emission == "rect":
            x = area_x + random.uniform(0, area_w)
            y = area_y + random.uniform(0, area_h)
        elif emission == "circle":
            cx, cy = area_x + area_w / 2, area_y + area_h / 2
            radius = min(area_w, area_h) / 2
            angle = random.uniform(0, math.pi * 2)
            dist = random.uniform(0, radius)
            x = cx + math.cos(angle) * dist
            y = cy + math.sin(angle) * dist
        else:
            x = area_x + random.uniform(0, area_w)
            y = area_y

        dir_val = self._get("direction", -1)
        spread = self._get("spread", 45)
        speed_min = self._get("speed_min", 20)
        speed_max = self._get("speed_max", 60)

        if dir_val < 0:
            angle = random.uniform(0, math.pi * 2)
        else:
            half = spread / 2
            angle = math.radians(dir_val + random.uniform(-half, half))

        speed = random.uniform(speed_min, speed_max)
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed

        lifetime = random.uniform(
            self._get("lifetime_min", 0.5),
            self._get("lifetime_max", 2.0),
        )
        size = random.uniform(
            self._get("particle_size_min", 2),
            self._get("particle_size_max", 6),
        )

        sc = (
            int(self._get("start_color_r", 255)),
            int(self._get("start_color_g", 200)),
            int(self._get("start_color_b", 100)),
            int(self._get("start_color_a", 255)),
        )
        ec = (
            int(self._get("end_color_r", 255)),
            int(self._get("end_color_g", 100)),
            int(self._get("end_color_b", 50)),
            int(self._get("end_color_a", 0)),
        )

        particle = Particle(
            x=x, y=y,
            vx=vx, vy=vy,
            lifetime=lifetime,
            size=size,
            start_color=sc,
            end_color=ec,
            start_scale=self._get("start_scale", 1.0),
            end_scale=self._get("end_scale", 0.3),
            rotation_speed=self._get("rotation_speed", 0),
            alpha_fade=str(cfg.get("alpha_fade", "fade_out")),
        )
        self.particles.append(particle)

    def draw(
        self,
        screen: Surface,
        scroll_x: float, scroll_y: float,
        zoom: float,
        grid_rect: Rect,
    ):
        tex = self.texture
        tex_w, tex_h = tex.get_size()
        for p in self.particles:
            sx = int((p.x - scroll_x) * zoom + grid_rect.x)
            sy = int((p.y - scroll_y) * zoom + grid_rect.y)
            s = max(1, int(p.current_size * zoom))
            color = p.current_color

            if color[3] <= 0:
                continue

            scaled_w = max(1, int(tex_w * p.current_size * zoom / PARTICLE_TEXTURE_SCALE_FACTOR))
            scaled_h = max(1, int(tex_h * p.current_size * zoom / PARTICLE_TEXTURE_SCALE_FACTOR))
            draw_surf = pygame.transform.scale(tex, (scaled_w, scaled_h))
            cw, ch = draw_surf.get_width(), draw_surf.get_height()

            tint = pygame.Surface(draw_surf.get_size(), pygame.SRCALPHA)
            tint.fill((color[0], color[1], color[2], color[3]))
            draw_surf.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

            if p.rotation_speed != 0:
                draw_surf = pygame.transform.rotate(draw_surf, p.rotation)

            dr = draw_surf.get_rect(center=(sx, sy))
            screen.blit(draw_surf, dr)

    def clear(self):
        self.particles.clear()
        self.spawn_timer = 0.0

    def reset(self, config: Dict[str, object]):
        self.config = dict(config)
        self.clear()
        shape = str(config.get("particle_shape", "circle"))
        self.texture = get_particle_texture(shape)
        self._current_shape = shape
