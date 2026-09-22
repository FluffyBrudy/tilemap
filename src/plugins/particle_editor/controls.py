"""Sidebar controls for the particle editor.

Event protocol (undo-friendly, shared by all controls): ``handle_event``
returns ``"change"`` when the value changed (apply live, stash the
pre-gesture snapshot) and ``"commit"`` when a gesture finished (push one
undo entry). Discrete widgets emit both back-to-back; the editor
coalesces commits close in time per key, so wheel ticks and arrow taps
don't flood the undo stack.

``Dropdown`` is reused from the legacy dialog; numeric tracks are drawn
here because mapped semantics (log/angle) and an owned value readout
don't fit the legacy ``Slider``'s embedded text.
"""

from __future__ import annotations

import math
import time

import pygame
from pygame import Rect

from widgets.ui.particle_config_dialog import Dropdown
from widgets.ui.theme import COLORS, FONTS, SHAPE

TRACK_H = 6
THUMB_R = 7
DOUBLE_CLICK_MS = 400


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


class NumberControl:
    """Label + mapped slider track + clickable value readout.

    kinds: ``"linear"`` or ``"log"`` (requires ``lo > 0``).
    ``integer=True`` rounds to whole steps (rates, counts).
    """

    ROW_H = 26

    def __init__(
        self,
        key: str,
        label: str,
        lo: float,
        hi: float,
        value: float,
        kind: str = "linear",
        integer: bool = False,
    ):
        assert hi > lo, f"{key}: hi must exceed lo"
        if kind == "log":
            assert lo > 0, f"{key}: log mapping needs lo > 0"
        self.key = key
        self.label = label
        self.lo = float(lo)
        self.hi = float(hi)
        self.kind = kind
        self.integer = integer
        self._value = self._clamp(value)
        self.rect = Rect(0, 0, 100, self.ROW_H)
        self._track_rect = Rect(0, 0, 10, self.ROW_H)
        self._readout_rect = Rect(0, 0, 10, self.ROW_H)
        self._dragging = False
        self._typing: str | None = None
        self._last_click_ms = 0

        self.focused = False

    # value #

    @property
    def value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = self._clamp(value)
        self._typing = None

    def _clamp(self, value: float) -> float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = self.lo
        if self.integer:
            v = round(v)
        if not math.isfinite(v):
            v = self.lo
        return max(self.lo, min(self.hi, v))

    def _to_t(self, value: float) -> float:
        if self.kind == "log":
            return (math.log(value) - math.log(self.lo)) / (math.log(self.hi) - math.log(self.lo))
        return (value - self.lo) / (self.hi - self.lo)

    def _from_t(self, t: float) -> float:
        t = max(0.0, min(1.0, t))
        if self.kind == "log":
            return self.lo * (self.hi / self.lo) ** t
        return self.lo + t * (self.hi - self.lo)

    def _step(self, mods: int) -> float:
        base = 1.0 if self.integer else (self.hi - self.lo) / 100.0
        if mods & pygame.KMOD_SHIFT:
            base *= 10.0
        if mods & (pygame.KMOD_CTRL | pygame.KMOD_META):
            base *= 0.1
        if self.integer:
            base = max(1.0, round(base))
        return base

    def format_value(self) -> str:
        if self.integer:
            return str(int(round(self._value)))
        if self.hi - self.lo <= 10.0:
            return f"{self._value:.2f}"
        return f"{self._value:.1f}"

    # layout #

    def set_rect(self, x: int, y: int, w: int) -> None:
        self.rect = Rect(x, y, w, self.ROW_H)
        readout_w = 58
        label_w = 92
        self._readout_rect = Rect(x + w - readout_w, y + 3, readout_w, self.ROW_H - 6)
        tx = x + label_w
        self._track_rect = Rect(tx, y, x + w - readout_w - 6 - tx, self.ROW_H)

    # events #

    def is_typing(self) -> bool:
        return self._typing is not None

    def cancel_typing(self) -> None:
        self._typing = None

    def _value_at(self, mx: int) -> float:
        w = self._track_rect.width - 4
        if w <= 0:
            return self.lo
        t = (mx - self._track_rect.x - 2) / w
        return self._from_t(t)

    def handle_event(self, event: pygame.event.Event) -> str | None:
        mouse = pygame.mouse.get_pos()

        if self._typing is not None:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    try:
                        self._value = self._clamp(float(self._typing))
                    except ValueError:
                        pass
                    self._typing = None
                    return "change"
                if event.key == pygame.K_ESCAPE:
                    self._typing = None
                    return None
                if event.key == pygame.K_BACKSPACE:
                    self._typing = self._typing[:-1]
                    return None
                if event.unicode and (event.unicode.isdigit() or event.unicode in ".-"):
                    self._typing += event.unicode
                    return None
                return True  # type: ignore[return-value]
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not self._readout_rect.collidepoint(mouse):
                    self._typing = None
                return None
            return None

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._readout_rect.collidepoint(mouse):
                now = _now_ms()
                if now - self._last_click_ms < DOUBLE_CLICK_MS:
                    self._typing = self.format_value()
                    self._last_click_ms = 0
                else:
                    self._last_click_ms = now
                return None
            if self._track_rect.collidepoint(mouse):
                self._dragging = True
                new = self._clamp(self._value_at(mouse[0]))
                if new != self._value:
                    self._value = new
                    return "change"
                return None
        if event.type == pygame.MOUSEMOTION and self._dragging:
            new = self._clamp(self._value_at(mouse[0]))
            if new != self._value:
                self._value = new
                return "change"
            return None
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                self._dragging = False
                return "commit"
            return None
        if event.type == pygame.MOUSEWHEEL and self.focused and self._typing is None and self.rect.collidepoint(mouse):
            mods = pygame.key.get_mods()
            self._value = self._clamp(self._value + event.y * self._step(mods))
            return "change-commit"
        if event.type == pygame.KEYDOWN and self.rect.collidepoint(mouse):
            mods = pygame.key.get_mods()
            if event.key in (pygame.K_UP, pygame.K_RIGHT):
                self._value = self._clamp(self._value + self._step(mods))
                return "change-commit"
            if event.key in (pygame.K_DOWN, pygame.K_LEFT):
                self._value = self._clamp(self._value - self._step(mods))
                return "change-commit"
        return None

    # -- draw -------------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        font = FONTS.get_font(12)
        small = FONTS.get_small_font()
        lbl = font.render(self.label, True, COLORS.text_dim)
        screen.blit(lbl, (self.rect.x, self.rect.y + 6))

        tr = self._track_rect
        pygame.draw.rect(screen, COLORS.bg, tr, border_radius=SHAPE.radius_sm)
        t = self._to_t(self._value)
        fill_w = int(t * (tr.width - 4))
        if fill_w > 0:
            fr = Rect(tr.x + 2, tr.y + (tr.height - TRACK_H) // 2, fill_w, TRACK_H)
            pygame.draw.rect(screen, COLORS.accent, fr, border_radius=SHAPE.radius_sm)
        thumb_x = tr.x + 2 + fill_w
        thumb_y = tr.y + tr.height // 2
        pygame.draw.circle(screen, COLORS.text_dim, (thumb_x, thumb_y), THUMB_R)
        pygame.draw.circle(screen, COLORS.text, (thumb_x, thumb_y), THUMB_R - 2)

        rr = self._readout_rect
        pygame.draw.rect(screen, COLORS.panel_alt, rr, border_radius=SHAPE.radius_sm)
        pygame.draw.rect(screen, COLORS.border_soft, rr, 1, border_radius=SHAPE.radius_sm)
        if self._typing is not None:
            caret = "|" if (_now_ms() // 500) % 2 == 0 else ""
            txt = small.render(self._typing + caret, True, COLORS.text)
        else:
            txt = small.render(self.format_value(), True, COLORS.text_muted)
        screen.blit(txt, (rr.x + 5, rr.y + 4))


class TextField:
    """Single-line text input. Click to edit, Enter commits, Esc cancels."""

    def __init__(self, text: str = "", width: int = 180):
        self.text = text
        self.rect = Rect(0, 0, width, 24)
        self._editing: str | None = None

    @property
    def value(self) -> str:
        return self.text

    def set_value(self, text: str) -> None:
        self.text = text
        self._editing = None

    def is_typing(self) -> bool:
        return self._editing is not None

    def handle_event(self, event: pygame.event.Event) -> str | None:
        mouse = pygame.mouse.get_pos()
        if self._editing is not None:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    self.text = self._editing.strip()
                    self._editing = None
                    return "change-commit"
                if event.key == pygame.K_ESCAPE:
                    self._editing = None
                    return None
                if event.key == pygame.K_BACKSPACE:
                    self._editing = self._editing[:-1]
                    return None
                if event.unicode and event.unicode.isprintable():
                    self._editing += event.unicode
                    return None
                return True  # type: ignore[return-value]
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not self.rect.collidepoint(mouse):
                    self._editing = None
                return None
            return None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(mouse):
            self._editing = self.text
            return None
        return None

    def draw(self, screen: pygame.Surface) -> None:
        small = FONTS.get_small_font()
        pygame.draw.rect(screen, COLORS.panel_alt, self.rect, border_radius=SHAPE.radius_sm)
        pygame.draw.rect(screen, COLORS.border_soft, self.rect, 1, border_radius=SHAPE.radius_sm)
        if self._editing is not None:
            caret = "|" if (_now_ms() // 500) % 2 == 0 else ""
            txt = small.render(self._editing + caret, True, COLORS.text)
        else:
            txt = small.render(self.text, True, COLORS.text_muted)
        screen.blit(txt, (self.rect.x + 6, self.rect.y + 5))


class ToggleControl:
    """Labeled checkbox. Emits change+commit back-to-back on flip."""

    ROW_H = 22

    def __init__(self, key: str, label: str, value: bool):
        self.key = key
        self.label = label
        self.value = bool(value)
        self.rect = Rect(0, 0, 100, self.ROW_H)
        self._box = Rect(0, 0, 16, 16)

    def set_value(self, value: bool) -> None:
        self.value = bool(value)

    def set_rect(self, x: int, y: int, w: int) -> None:
        self.rect = Rect(x, y, w, self.ROW_H)
        self._box = Rect(x + 92, y + 3, 16, 16)

    def handle_event(self, event: pygame.event.Event) -> str | None:
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(pygame.mouse.get_pos())
        ):
            self.value = not self.value
            return "change-commit"
        return None

    def draw(self, screen: pygame.Surface) -> None:
        font = FONTS.get_font(12)
        screen.blit(
            font.render(self.label, True, COLORS.text_dim),
            (self.rect.x, self.rect.y + 3),
        )
        bg = COLORS.selected if self.value else COLORS.bg
        pygame.draw.rect(screen, bg, self._box, border_radius=3)
        pygame.draw.rect(screen, COLORS.border, self._box, 1, border_radius=3)
        if self.value:
            f = FONTS.get_bold_font(12)
            tick = f.render("x", True, COLORS.text_on_selected)
            screen.blit(tick, tick.get_rect(center=self._box.center))


class ChoiceControl:
    """Dropdown wrapper. Emits change+commit on selection."""

    ROW_H = 26

    def __init__(self, key: str, label: str, options: list[str], value: str):
        self.key = key
        self.label = label
        self.rect = Rect(0, 0, 100, 22)
        self._dd = Dropdown(Rect(0, 0, 100, 22), options, value)

    @property
    def value(self) -> str:
        return self._dd.selected

    def set_value(self, value: str) -> None:
        if value in self._dd.options:
            self._dd.selected = value

    def set_rect(self, x: int, y: int, w: int) -> None:
        self.rect = Rect(x, y, w, self.ROW_H)
        self._dd.rect = Rect(x + 92, y + 2, w - 92, 22)

    def handle_event(self, event: pygame.event.Event) -> str | None:
        result = self._dd.handle_event(event)
        if result is not None:
            return "change-commit"
        return None

    def draw(self, screen: pygame.Surface) -> None:
        font = FONTS.get_font(12)
        screen.blit(
            font.render(self.label, True, COLORS.text_dim),
            (self.rect.x, self.rect.y + 5),
        )
        self._dd.draw(screen, COLORS.header, COLORS.border)

    def draw_options(self, screen: pygame.Surface) -> None:
        self._dd.draw_options(screen)

    @property
    def is_open(self) -> bool:
        return self._dd.open


class DirectionDial:
    """Compass direction picker. Degrees (0=right, 90=down) or Random.

    The serialized ``-1`` sentinel never appears; Random is a mode with
    its own toggle. Drag on the dial sets the angle; the toggle flips
    random mode.
    """

    ROW_H = 94

    def __init__(self, value: float):
        self.key = "direction"
        self.degrees = 270.0
        self.random = True
        self.rect = Rect(0, 0, 100, self.ROW_H)
        self._dial = Rect(0, 0, 64, 64)
        self._dragging = False
        self._toggle = ToggleControl("direction_random", "Random", True)
        self.set_value(value)

    def set_value(self, value: float) -> None:
        try:
            v = float(value)
        except (TypeError, ValueError):
            v = -1.0
        if v < 0:
            self.random = True
        else:
            self.random = False
            self.degrees = v % 360.0
        self._toggle.value = self.random

    @property
    def value(self) -> float:
        return -1.0 if self.random else self.degrees

    def set_rect(self, x: int, y: int, w: int) -> None:
        self.rect = Rect(x, y, w, self.ROW_H)
        self._dial = Rect(x + 92, y + 26, 64, 64)
        self._toggle.set_rect(x, y, w)

    def _angle_at(self, mx: int, my: int) -> float:
        cx, cy = self._dial.center
        # Screen y grows downward; compass 0=right, 90=down.
        return (math.degrees(math.atan2(my - cy, mx - cx))) % 360.0

    def handle_event(self, event: pygame.event.Event) -> str | None:
        result = self._toggle.handle_event(event)
        if result is not None:
            self.random = self._toggle.value
            return result
        mouse = pygame.mouse.get_pos()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self._dial.collidepoint(mouse):
            self._dragging = True
            self.random = False
            self._toggle.value = False
            self.degrees = self._angle_at(mouse[0], mouse[1])
            return "change"
        if event.type == pygame.MOUSEMOTION and self._dragging:
            self.degrees = self._angle_at(mouse[0], mouse[1])
            return "change"
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self._dragging:
            self._dragging = False
            return "commit"
        return None

    def draw(self, screen: pygame.Surface) -> None:
        font = FONTS.get_font(12)
        screen.blit(
            font.render("Direction", True, COLORS.text_dim),
            (self.rect.x, self.rect.y + 30),
        )
        cx, cy = self._dial.center
        r = 30
        pygame.draw.circle(screen, COLORS.bg, (cx, cy), r)
        pygame.draw.circle(screen, COLORS.border, (cx, cy), r, 1)
        for deg in range(0, 360, 45):
            rad = math.radians(deg)
            x1, y1 = (
                cx + int((r - 5) * math.cos(rad)),
                cy + int((r - 5) * math.sin(rad)),
            )
            x2, y2 = cx + int(r * math.cos(rad)), cy + int(r * math.sin(rad))
            pygame.draw.line(screen, COLORS.border_soft, (x1, y1), (x2, y2), 1)
        if self.random:
            f = FONTS.get_bold_font(13)
            txt = f.render("?", True, COLORS.text_dim)
            screen.blit(txt, txt.get_rect(center=(cx, cy)))
        else:
            rad = math.radians(self.degrees)
            ex, ey = (
                cx + int((r - 4) * math.cos(rad)),
                cy + int((r - 4) * math.sin(rad)),
            )
            pygame.draw.line(screen, COLORS.accent_hover, (cx, cy), (ex, ey), 3)
            pygame.draw.circle(screen, COLORS.accent_hover, (ex, ey), 4)
        small = FONTS.get_small_font()
        label = "Random" if self.random else f"{self.degrees:.0f}deg"
        screen.blit(small.render(label, True, COLORS.text_muted), (self._dial.right + 8, cy - 6))
        self._toggle.draw(screen)
