from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

import pygame
from pygame import Rect, Surface

from widgets.particle_system import (
    ALPHA_FADE_MODES,
    EMISSION_SHAPES,
    FLOAT_FIELDS,
    PARTICLE_SHAPES,
    get_default_config,
)

if TYPE_CHECKING:
    from editor import Editor

SLIDER_H = 18
ROW_H = 26
LABEL_W = 80
CONTROL_L = LABEL_W + 6
CONTROL_W = 200
TRACK_H = 6
THUMB_R = 7
CONTENT_X = 10
CONTENT_W = 480


class Dropdown:
    def __init__(self, rect: Rect, options: List[str], initial: str, max_visible: int = 10):
        if not options:
            raise ValueError("options must be a non-empty list")
        self.rect = rect
        self.options = options
        self.selected = initial if initial in options else options[0]
        self.open = False
        self.hover_idx: Optional[int] = None
        self.option_h = 22
        self.max_visible = max_visible
        self.scroll_offset = 0

    def _get_option_rect(self, idx: int) -> Rect:
        visible_idx = idx - self.scroll_offset
        return Rect(self.rect.x, self.rect.y + self.rect.height + visible_idx * self.option_h, self.rect.width, self.option_h)

    def _total_height(self) -> int:
        return len(self.options) * self.option_h

    def _visible_range(self) -> Tuple[int, int]:
        last = min(len(self.options), self.scroll_offset + self.max_visible)
        return self.scroll_offset, last

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        mouse = pygame.mouse.get_pos()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse):
                self.open = not self.open
                if self.open:
                    self.scroll_offset = 0
                    if self.selected in self.options:
                        sel_idx = self.options.index(self.selected)
                        if sel_idx >= self.max_visible:
                            self.scroll_offset = sel_idx - self.max_visible + 1
                return None
            if self.open:
                lo, hi = self._visible_range()
                for i in range(lo, hi):
                    r = self._get_option_rect(i)
                    if r.collidepoint(mouse):
                        self.selected = self.options[i]
                        self.open = False
                        return self.selected
                self.open = False
                return None

        if self.open and event.type == pygame.MOUSEWHEEL:
            max_offset = max(0, len(self.options) - self.max_visible)
            if event.y > 0:
                self.scroll_offset = max(0, self.scroll_offset - 3)
            else:
                self.scroll_offset = min(max_offset, self.scroll_offset + 3)
            return None

        if event.type == pygame.MOUSEMOTION and self.open:
            self.hover_idx = None
            lo, hi = self._visible_range()
            for i in range(lo, hi):
                if self._get_option_rect(i).collidepoint(mouse):
                    self.hover_idx = i
                    break

        return None

    def draw(self, screen: Surface, bg: Tuple[int, int, int], border: Tuple[int, int, int]):
        pygame.draw.rect(screen, bg, self.rect, border_radius=3)
        pygame.draw.rect(screen, border, self.rect, 1, border_radius=3)
        font = pygame.font.SysFont("Arial", 13)
        txt = font.render(self.selected, True, (220, 220, 220))
        screen.blit(txt, (self.rect.x + 4, self.rect.y + 3))
        pygame.draw.polygon(screen, (160, 160, 160), [
            (self.rect.right - 10, self.rect.y + 6),
            (self.rect.right - 4, self.rect.y + 6),
            (self.rect.right - 7, self.rect.y + 11),
        ])

    def draw_options(self, screen: Surface):
        if not self.open:
            return
        font = pygame.font.SysFont("Arial", 13)
        lo, hi = self._visible_range()

        # clip the options area
        full_h = self._total_height()
        visible_h = min(full_h, self.max_visible * self.option_h)
        clip = Rect(self.rect.x, self.rect.y + self.rect.height, self.rect.width, visible_h)
        old_clip = screen.get_clip()
        screen.set_clip(clip)

        for i in range(lo, hi):
            r = self._get_option_rect(i)
            opt = self.options[i]
            is_selected = opt == self.selected
            opt_bg = (60, 70, 90) if self.hover_idx == i else (50, 55, 65) if is_selected else (40, 44, 50)
            pygame.draw.rect(screen, opt_bg, r, border_radius=2)
            txt = font.render(opt, True, (220, 220, 220))
            screen.blit(txt, (r.x + 4, r.y + 3))

        screen.set_clip(old_clip)

        # scroll indicators
        if self.scroll_offset > 0:
            arrow_y = clip.y
            pygame.draw.polygon(screen, (160, 160, 160), [
                (clip.x + clip.width // 2, arrow_y + 4),
                (clip.x + clip.width // 2 - 5, arrow_y + 10),
                (clip.x + clip.width // 2 + 5, arrow_y + 10),
            ])
        if hi < len(self.options):
            arrow_y = clip.bottom - 10
            pygame.draw.polygon(screen, (160, 160, 160), [
                (clip.x + clip.width // 2, arrow_y + 6),
                (clip.x + clip.width // 2 - 5, arrow_y),
                (clip.x + clip.width // 2 + 5, arrow_y),
            ])


class Slider:
    def __init__(self, rect: Rect, label: str, min_val: float, max_val: float, value: float, fmt: str = "{:.0f}"):
        self.rect = rect
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.value = max(min_val, min(max_val, value))
        self.fmt = fmt
        self.dragging = False

    def handle_event(self, event: pygame.event.Event) -> Optional[float]:
        mouse = pygame.mouse.get_pos()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(mouse):
                self.dragging = True
                return self._value_at(mouse[0])
        if event.type == pygame.MOUSEMOTION and self.dragging:
            return self._value_at(mouse[0])
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        return None

    def _value_at(self, mx: int) -> float:
        w = self.rect.width - 4
        if w <= 0:
            return self.min_val
        t = max(0.0, min(1.0, (mx - self.rect.x - 2) / w))
        return self.min_val + t * (self.max_val - self.min_val)

    def draw(self, screen: Surface, accent: Tuple[int, int, int]):
        pygame.draw.rect(screen, (35, 38, 42), self.rect, border_radius=3)
        fr = self.fill_rect
        if fr.width > 0:
            pygame.draw.rect(screen, accent, fr, border_radius=3)
        thumb_x = fr.right if fr.width > 0 else self.rect.x + 2
        thumb_y = self.rect.y + self.rect.height // 2
        pygame.draw.circle(screen, (200, 200, 220), (thumb_x, thumb_y), THUMB_R)
        pygame.draw.circle(screen, (255, 255, 255), (thumb_x, thumb_y), THUMB_R - 2)
        font = pygame.font.SysFont("Arial", 11)
        val_str = self.fmt.format(self.value)
        txt = font.render(val_str, True, (255, 255, 255))
        screen.blit(txt, (self.fill_rect.right + 6, self.rect.y + 3))

    @property
    def fill_rect(self) -> Rect:
        w = int((self.value - self.min_val) / (self.max_val - self.min_val) * (self.rect.width - 4))
        return Rect(self.rect.x + 2, self.rect.y + (self.rect.height - TRACK_H) // 2, w, TRACK_H)


class ColorField:
    def __init__(self, rect: Rect):
        self.rect = rect
        self.hue = 0
        self.sat = 1.0
        self.bri = 1.0
        self.dragging_part: Optional[str] = None
        self._cache_key: Optional[Tuple[int, int, int]] = None
        self._cache_surf: Optional[Surface] = None

    @property
    def rgb(self) -> Tuple[int, int, int]:
        return tuple(int(c * 255) for c in self._hsv_to_rgb(self.hue, self.sat, self.bri))

    def _hsv_to_rgb(self, h: float, s: float, v: float) -> Tuple[float, float, float]:
        h = h % 360
        c = v * s
        x = c * (1 - abs((h / 60) % 2 - 1))
        m = v - c
        if h < 60:
            r2, g2, b2 = c, x, 0
        elif h < 120:
            r2, g2, b2 = x, c, 0
        elif h < 180:
            r2, g2, b2 = 0, c, x
        elif h < 240:
            r2, g2, b2 = 0, x, c
        elif h < 300:
            r2, g2, b2 = x, 0, c
        else:
            r2, g2, b2 = c, 0, x
        return r2 + m, g2 + m, b2 + m

    def _rgb_to_hsv(self, r: int, g: int, b: int) -> Tuple[float, float, float]:
        rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
        mx, mn = max(rf, gf, bf), min(rf, gf, bf)
        v = mx
        s = 0 if mx == 0 else (mx - mn) / mx
        if mx == mn:
            h = 0.0
        elif mx == rf:
            h = 60 * ((gf - bf) / (mx - mn) % 6)
        elif mx == gf:
            h = 60 * ((bf - rf) / (mx - mn) + 2)
        else:
            h = 60 * ((rf - gf) / (mx - mn) + 4)
        return h % 360, s, v

    def set_rgb(self, r: int, g: int, b: int):
        self.hue, self.sat, self.bri = self._rgb_to_hsv(r, g, b)

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse = pygame.mouse.get_pos()
        field_w = self.rect.width - 20
        field_h = self.rect.height
        strip_x = field_w + 4

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.rect.collidepoint(mouse):
                return False
            lx = mouse[0] - self.rect.x
            ly = mouse[1] - self.rect.y
            if lx >= 0 and ly >= 0 and lx < self.rect.width and ly < field_h:
                if lx < strip_x and field_w > 0:
                    hue_lx = min(lx, field_w - 1)
                    self.hue = (hue_lx / field_w) * 360
                    self.sat = 1.0 - ly / field_h
                    self.dragging_part = "field"
                elif lx >= strip_x:
                    self.bri = 1.0 - ly / field_h
                    self.dragging_part = "brightness"
                else:
                    return False
                return True
        if event.type == pygame.MOUSEMOTION and self.dragging_part:
            lx = max(0, min(mouse[0] - self.rect.x, self.rect.width))
            ly = max(0, min(mouse[1] - self.rect.y, field_h))
            if self.dragging_part == "field" and field_w > 0:
                hue_lx = min(lx, field_w - 1)
                self.hue = (hue_lx / field_w) * 360
                self.sat = 1.0 - ly / field_h
            elif self.dragging_part == "brightness":
                self.bri = 1.0 - ly / field_h
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging_part = None
        return False

    def _build_hue_sat_surf(self, w: int, h: int) -> Surface:
        surf = Surface((w, h), pygame.SRCALPHA)
        for y in range(h):
            for x in range(w):
                h_val = (x / w) * 360
                s_val = 1.0 - y / h
                r, g, b = self._hsv_to_rgb(h_val, s_val, 1.0)
                surf.set_at((x, y), (int(r * 255), int(g * 255), int(b * 255), 255))
        return surf

    def draw(self, screen: Surface):
        field_w = self.rect.width - 20
        field_h = self.rect.height

        cache_key = (field_w, field_h, 0)
        if self._cache_key != cache_key or self._cache_surf is None:
            self._cache_surf = self._build_hue_sat_surf(field_w, field_h)
            self._cache_key = cache_key

        # Apply brightness overlay to a copy — never mutate the cache
        surf = self._cache_surf.copy()
        bri_surf = Surface((field_w, field_h), pygame.SRCALPHA)
        dark = int((1.0 - self.bri) * 255)
        bri_surf.fill((0, 0, 0, dark))
        surf.blit(bri_surf, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        screen.blit(surf, self.rect.topleft)

        # Cursor on field
        cx = int((self.hue / 360) * field_w)
        cy = int((1.0 - self.sat) * field_h)
        pygame.draw.circle(screen, (255, 255, 255), (self.rect.x + cx, self.rect.y + cy), 5, 1)
        pygame.draw.circle(screen, (0, 0, 0), (self.rect.x + cx, self.rect.y + cy), 4, 1)

        # Brightness strip
        strip_x = self.rect.x + field_w + 4
        strip_w = 14
        for y in range(field_h):
            t = 1.0 - y / field_h
            r, g, b = self._hsv_to_rgb(self.hue, self.sat, t)
            pygame.draw.line(screen, (int(r * 255), int(g * 255), int(b * 255)),
                (strip_x, self.rect.y + y), (strip_x + strip_w, self.rect.y + y))
        pygame.draw.rect(screen, (60, 64, 69), Rect(strip_x, self.rect.y, strip_w, field_h), 1)

        # Brightness thumb
        by = self.rect.y + int((1.0 - self.bri) * field_h)
        pygame.draw.circle(screen, (255, 255, 255), (strip_x + strip_w // 2, by), 6)
        pygame.draw.circle(screen, (0, 0, 0), (strip_x + strip_w // 2, by), 5, 1)


class ColorPicker:
    TAB_H = 24
    SWATCH_H = 30
    FIELD_H = 120
    SLIDER_H = 16

    def __init__(self, rect: Rect):
        self.rect = rect
        self.active_tab = 0  # 0=start, 1=end
        self.start_colors = {"r": 255, "g": 200, "b": 100, "a": 255}
        self.end_colors = {"r": 255, "g": 100, "b": 50, "a": 0}
        self._field_ox = 4
        self._field_oy = self.TAB_H + self.SWATCH_H + 8
        self.field = ColorField(Rect(rect.x + self._field_ox, rect.y + self._field_oy, rect.width - 8, self.FIELD_H))
        self._init_sliders()

    def _update_field_rect(self):
        self.field.rect.topleft = (self.rect.x + self._field_ox, self.rect.y + self._field_oy)

    def _tab_rect(self, idx: int) -> Rect:
        w = (self.rect.width - 4) // 2
        return Rect(self.rect.x + 2 + idx * w, self.rect.y, w, self.TAB_H)

    def _swatch_rect(self, idx: int) -> Rect:
        w = (self.rect.width - 8) // 2
        return Rect(self.rect.x + 4 + idx * w, self.rect.y + self.TAB_H + 2, w, self.SWATCH_H)

    def _slider_rects(self) -> List[Tuple[str, Rect, Tuple[int, int, int]]]:
        y0 = self.rect.y + self.TAB_H + self.SWATCH_H + 8 + self.FIELD_H + 8
        label_x = self.rect.x + 8
        slider_x = label_x + 54
        slider_w = self.rect.width - 64
        labels = [("R", (220, 80, 80)), ("G", (80, 200, 80)), ("B", (80, 80, 220)), ("A", (180, 180, 180))]
        result = []
        for i, (label, accent) in enumerate(labels):
            r = Rect(slider_x, y0 + i * 18, slider_w, self.SLIDER_H)
            result.append((label, accent, r, label_x))
        return result

    def _init_sliders(self):
        self._slider_values: List[float] = [255, 200, 100, 255]
        self._slider_dragging: List[bool] = [False, False, False, False]

    def _get_active_colors(self) -> Dict[str, int]:
        return self.start_colors if self.active_tab == 0 else self.end_colors

    def _set_active_colors(self, d: Dict[str, int]):
        if self.active_tab == 0:
            self.start_colors.update(d)
        else:
            self.end_colors.update(d)

    def handle_event(self, event: pygame.event.Event) -> bool:
        self._update_field_rect()
        mouse = pygame.mouse.get_pos()
        if not self.rect.collidepoint(mouse) and event.type == pygame.MOUSEBUTTONDOWN:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i in range(2):
                if self._tab_rect(i).collidepoint(mouse):
                    self.active_tab = i
                    colors = self._get_active_colors()
                    self.field.set_rgb(colors["r"], colors["g"], colors["b"])
                    self._slider_values = [colors["r"], colors["g"], colors["b"], colors["a"]]
                    return True
            for i in range(2):
                if self._swatch_rect(i).collidepoint(mouse):
                    self.active_tab = i
                    colors = self._get_active_colors()
                    self.field.set_rgb(colors["r"], colors["g"], colors["b"])
                    self._slider_values = [colors["r"], colors["g"], colors["b"], colors["a"]]
                    return True

        if self.field.handle_event(event):
            r, g, b = self.field.rgb
            self._slider_values[0] = r
            self._slider_values[1] = g
            self._slider_values[2] = b
            self._get_active_colors().update({"r": r, "g": g, "b": b})
            return True

        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            rects = self._slider_rects()
            for i, (label, accent, r, _lx) in enumerate(rects):
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and r.collidepoint(mouse):
                    self._slider_dragging[i] = True
                if event.type == pygame.MOUSEMOTION and self._slider_dragging[i]:
                    w = r.width - 4
                    if w > 0:
                        t = max(0.0, min(1.0, (mouse[0] - r.x - 2) / w))
                        self._slider_values[i] = int(t * 255)
                        keys = ["r", "g", "b", "a"]
                        self._get_active_colors()[keys[i]] = self._slider_values[i]
                        if i < 3:
                            self.field.set_rgb(self._slider_values[0], self._slider_values[1], self._slider_values[2])
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    self._slider_dragging[i] = False
        return False

    def sync_from_config(self, config: Dict[str, object]):
        self.start_colors = {
            "r": int(config.get("start_color_r", 255)),
            "g": int(config.get("start_color_g", 200)),
            "b": int(config.get("start_color_b", 100)),
            "a": int(config.get("start_color_a", 255)),
        }
        self.end_colors = {
            "r": int(config.get("end_color_r", 255)),
            "g": int(config.get("end_color_g", 100)),
            "b": int(config.get("end_color_b", 50)),
            "a": int(config.get("end_color_a", 0)),
        }
        colors = self._get_active_colors()
        self.field.set_rgb(colors["r"], colors["g"], colors["b"])
        self._slider_values = [colors["r"], colors["g"], colors["b"], colors["a"]]

    def sync_to_config(self, config: Dict[str, object]):
        for prefix, colors in [("start_color", self.start_colors), ("end_color", self.end_colors)]:
            config[f"{prefix}_r"] = colors["r"]
            config[f"{prefix}_g"] = colors["g"]
            config[f"{prefix}_b"] = colors["b"]
            config[f"{prefix}_a"] = colors["a"]

    def draw(self, screen: Surface):
        self._update_field_rect()
        for i, label in enumerate(["Start", "End"]):
            tr = self._tab_rect(i)
            is_active = i == self.active_tab
            tab_bg = (50, 60, 80) if is_active else (35, 38, 42)
            pygame.draw.rect(screen, tab_bg, tr, border_radius=3)
            pygame.draw.rect(screen, (60, 64, 69), tr, 1, border_radius=3)
            t = pygame.font.SysFont("Arial", 12, bold=is_active).render(label, True, (220, 220, 220))
            screen.blit(t, t.get_rect(center=tr.center))

        colors = self._get_active_colors()
        for i in range(2):
            sr = self._swatch_rect(i)
            c = self.start_colors if i == 0 else self.end_colors
            pygame.draw.rect(screen, (c["r"], c["g"], c["b"]), sr, border_radius=3)
            pygame.draw.rect(screen, (80, 84, 89), sr, 1, border_radius=3)
            if i == self.active_tab:
                pygame.draw.rect(screen, (255, 255, 255), sr, 2, border_radius=3)

        self.field.draw(screen)

        rects = self._slider_rects()
        font = pygame.font.SysFont("Arial", 11)
        for i, (label, accent, r, lx) in enumerate(rects):
            val = self._slider_values[i]
            ltxt = font.render(label, True, accent)
            screen.blit(ltxt, (lx, r.y + 2))
            vtxt = font.render(str(int(val)), True, (180, 180, 180))
            screen.blit(vtxt, (lx + 16, r.y + 2))
            pygame.draw.rect(screen, (35, 38, 42), r, border_radius=2)
            fw = int((val / 255) * (r.width - 4))
            if fw > 0:
                fr = Rect(r.x + 2, r.y + (r.height - TRACK_H) // 2, fw, TRACK_H)
                pygame.draw.rect(screen, accent, fr, border_radius=2)
            tx = r.x + 2 + fw
            ty = r.y + r.height // 2
            pygame.draw.circle(screen, (200, 200, 220), (tx, ty), 5)


class ParticleConfigDialog:
    def __init__(
        self,
        editor: Editor,
        config: Dict[str, object],
        node_id: str,
        on_save: Callable[[Dict[str, object]], None],
    ):
        self.editor = editor
        self.config = dict(config)
        self.node_id = node_id
        self.on_save = on_save
        self.active = True

        w, h = 520, 620
        self.rect = Rect(
            (editor.width - w) // 2,
            (editor.height - h) // 2,
            w, h,
        )

        self.scroll_y = 0
        self.font_title = pygame.font.SysFont("Arial", 16, bold=True)
        self.font_section = pygame.font.SysFont("Arial", 13, bold=True)
        self.font_label = pygame.font.SysFont("Arial", 12)

        self.sliders: List[Tuple[str, Slider]] = []
        self.dropdowns: List[Tuple[str, Dropdown]] = []
        self.color_picker = ColorPicker(Rect(self.rect.x + 10, 0, self.rect.width - 20, 240))
        self._slider_base_y: Dict[str, int] = {}
        self._dropdown_base_y: Dict[str, int] = {}
        self._section_positions: List[Tuple[int, str]] = []

        self._build_controls()
        self.color_picker.sync_from_config(self.config)

        self.btn_save = Rect(self.rect.right - 110, self.rect.bottom - 36, 100, 28)
        self.btn_cancel = Rect(self.rect.x + 10, self.rect.bottom - 36, 100, 28)

    def _build_controls(self):
        y = self.rect.y + 44
        x = self.rect.x + CONTENT_X
        slider_w = self.rect.width - 106

        def add_slider(key: str):
            nonlocal y
            mn, mx, lbl = FLOAT_FIELDS[key]
            val = float(self.config.get(key, (mn + mx) / 2))
            sr = Rect(x + CONTROL_L, y, slider_w, SLIDER_H)
            sl = Slider(sr, lbl, mn, mx, val, "{:.1f}" if mn < 1 else "{:.0f}")
            self.sliders.append((key, sl))
            self._slider_base_y[key] = y
            l = self.font_label.render(lbl, True, (180, 180, 180))
            y += ROW_H

        def add_dropdown(key: str, opts: List[str]):
            nonlocal y
            dr = Rect(x + CONTROL_L, y, slider_w, 22)
            dd = Dropdown(dr, opts, str(self.config.get(key, opts[0])))
            self.dropdowns.append((key, dd))
            self._dropdown_base_y[key] = y
            y += 26

        def section(text: str):
            nonlocal y
            self._section_positions.append((y, text))
            y += 24

        section("Emission")
        add_dropdown("emission_shape", EMISSION_SHAPES)
        add_slider("direction")
        add_slider("spread")

        section("Spawn")
        add_slider("spawn_rate")
        add_slider("max_particles")
        add_slider("lifetime_min")
        add_slider("lifetime_max")
        add_slider("speed_min")
        add_slider("speed_max")

        section("Physics")
        add_slider("gravity_x")
        add_slider("gravity_y")

        section("Particle")
        add_dropdown("particle_shape", PARTICLE_SHAPES)
        add_slider("particle_size_min")
        add_slider("particle_size_max")
        add_slider("start_scale")
        add_slider("end_scale")
        add_slider("rotation_speed")
        add_dropdown("alpha_fade", ALPHA_FADE_MODES)

        section("Colors")
        self._colors_y = y
        self.color_picker.rect.y = y
        y += self.color_picker.rect.height + 10

        self._control_y_end = y

    def _get_content_height(self) -> int:
        return self._control_y_end - (self.rect.y + 44)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False

        mouse = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.btn_save.collidepoint(mouse):
                    self.color_picker.sync_to_config(self.config)
                    self.on_save(self.config)
                    self.active = False
                    return True
                if self.btn_cancel.collidepoint(mouse):
                    self.active = False
                    return True
                if not self.rect.collidepoint(mouse):
                    return True

            if event.button == 4:
                max_scroll = max(0, self._get_content_height() - (self.rect.height - 80))
                self.scroll_y = max(0, self.scroll_y - 20)
                return True
            if event.button == 5:
                max_scroll = max(0, self._get_content_height() - (self.rect.height - 80))
                self.scroll_y = min(max_scroll, self.scroll_y + 20)
                return True

        for dd_key, dd in self.dropdowns:
            result = dd.handle_event(event)
            if result is not None:
                self.config[dd_key] = result

        for sl_key, sl in self.sliders:
            result = sl.handle_event(event)
            if result is not None:
                sl.value = max(sl.min_val, min(sl.max_val, result))
                self.config[sl_key] = float(f"{sl.value:.2f}")

        self.color_picker.handle_event(event)

        return True

    def draw(self, screen: Surface):
        if not self.active:
            return

        overlay = Surface((self.editor.width, self.editor.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        pygame.draw.rect(screen, (30, 34, 39), self.rect, border_radius=6)
        pygame.draw.rect(screen, (50, 54, 59), self.rect, 2, border_radius=6)

        title = self.font_title.render("Particle Emitter Config", True, (255, 255, 255))
        screen.blit(title, (self.rect.x + 14, self.rect.y + 14))

        content_rect = Rect(self.rect.x + 4, self.rect.y + 42, self.rect.width - 8, self.rect.height - 84)
        clip = screen.get_clip()
        screen.set_clip(content_rect)

        cy = self.rect.y + 44 - self.scroll_y

        for base_y, text in self._section_positions:
            sy = cy + (base_y - self.rect.y - 44)
            s = self.font_section.render(text, True, (160, 190, 240))
            screen.blit(s, (self.rect.x + CONTENT_X, sy))

        for key, dd in self.dropdowns:
            base_y = self._dropdown_base_y.get(key, dd.rect.y)
            draw_y = cy + (base_y - self.rect.y - 44)
            dd.rect.y = int(draw_y)
            lbl = key.replace("_", " ").title()
            l = self.font_label.render(lbl, True, (180, 180, 180))
            screen.blit(l, (self.rect.x + CONTENT_X, draw_y + 3))
            dd.draw(screen, (40, 44, 50), (60, 64, 69))

        for key, sl in self.sliders:
            base_y = self._slider_base_y.get(key, sl.rect.y)
            draw_y = cy + (base_y - self.rect.y - 44)
            sl.rect.y = int(draw_y)
            lbl = FLOAT_FIELDS.get(key, (0, 0, ""))[2]
            l = self.font_label.render(lbl, True, (180, 180, 180))
            screen.blit(l, (self.rect.x + CONTENT_X, draw_y + 2))
            sl.draw(screen, (70, 130, 220))

        # Draw color picker at its scrolled position
        colors_base_y = self._colors_y
        cp_y = cy + (colors_base_y - self.rect.y - 44)
        self.color_picker.rect.y = int(cp_y)
        self.color_picker.draw(screen)

        # Draw open dropdown options on top of sliders
        for _key, dd in self.dropdowns:
            dd.draw_options(screen)

        screen.set_clip(clip)

        for btn, text, col in [
            (self.btn_save, "Save", (40, 150, 80)),
            (self.btn_cancel, "Cancel", (150, 60, 60)),
        ]:
            pygame.draw.rect(screen, col, btn, border_radius=4)
            t = self.font_label.render(text, True, (255, 255, 255))
            screen.blit(t, t.get_rect(center=btn.center))
