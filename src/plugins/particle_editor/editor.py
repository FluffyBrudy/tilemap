from __future__ import annotations

import copy
import time
from pathlib import Path

import pygame
from pygame import Rect

from node_manager import TRANSIENT_PROPERTY_KEYS
from widgets.ui.button import Button
from widgets.ui.context_menu import ContextMenu
from widgets.ui.menubar import MenuAction
from widgets.ui.particle_config_dialog import ColorPicker
from widgets.ui.scrollbar import Scrollbar
from widgets.ui.theme import COLORS, FONTS
from widgets.ui.toast import ToastManager
from widgets.ui.toolbar_layout import ToolbarLayout

from .controls import (
    ChoiceControl,
    DirectionDial,
    NumberControl,
    TextField,
    ToggleControl,
)
from .models import (
    LIBRARY_DIRNAME,
    ParticleLibrary,
    ParticleSystemEntry,
    builtin_library,
    builtin_library_path,
    identify,
    list_libraries,
    normalize_config,
)
from .presets import BLANK_NAME
from .preview import BACKGROUNDS, PreviewCanvas
from .sim import FIXED_DT, SPEEDS, PreviewSim

TOOLBAR_H = 38
TRANSPORT_H = 42
STRIP_H = 126
STATUS_H = 24
SIDEBAR_W = 304
HEADER_H = 40
UNDO_COALESCE_MS = 800
THUMB_W = 108
THUMB_H = 78
THUMB_BUDGET = 8
SIM_AREA = (0.0, 0.0, 240.0, 240.0)
THUMB_AREA = (0.0, 0.0, 120.0, 90.0)
FIELDBOX_H = 64

# config key -> edit-severity tier (see plan section Phase B).
_LIVE_KEYS = {
    "spawn_rate",
    "max_particles",
    "burst_count",
    "gravity_x",
    "gravity_y",
    "coverage",
    "field_quality",
    "timing.burst_interval",
}
_RESPAWN_KEYS = {
    "spread",
    "direction",
    "speed_min",
    "speed_max",
    "particle_size_min",
    "particle_size_max",
    "start_scale",
    "end_scale",
    "rotation_speed",
    "alpha_fade",
    "fade_peak_alpha",
    "wrap",
    "ground_bias",
}
_RESET_KEYS = {
    "particle_shape",
    "emission_shape",
    "mode",
    "timing.emitter_duration",
    "timing.start_delay",
    "timing.loop",
}

# Auto-applied (with visible confirmation) when switching to field mode.
FIELD_AUTO_SETS: dict[str, object] = {
    "wrap": True,
    "spawn_rate": 0,
    "emission_shape": "rect",
    "alpha_fade": "none",
}

_COLOR_KEYS = (
    "start_color_r",
    "start_color_g",
    "start_color_b",
    "start_color_a",
    "end_color_r",
    "end_color_g",
    "end_color_b",
    "end_color_a",
)


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


class ParticleEditor:
    def __init__(
        self,
        rect: Rect,
        library: ParticleLibrary,
        library_path: Path | None,
        data_root: Path,
        export_node: Path | None = None,
    ):
        self.rect = Rect(rect)
        self.library = library
        self.library_path = library_path
        self.data_root = Path(data_root)
        self.export_node = export_node

        self.canvas = PreviewCanvas()
        start = library.find(BLANK_NAME)
        start_name = BLANK_NAME
        start_config = dict(start.config) if start else {}
        if start is None:
            start_config, _ = normalize_config(None)
        self.sim = PreviewSim(start_config, SIM_AREA)
        self.working: dict = dict(start_config)
        self.loaded_name = start_name
        self.loaded_config: dict = dict(start_config)

        self.controls: dict[str, object] = {}
        self._sections: list[tuple[str, list[str]]] = []

        self.name_field = TextField(start_name, width=180)
        self.lib_choice = ChoiceControl("library", "Library", ["-"], "-")
        self._lib_paths: list[Path | None] = [None]
        self.color_picker = ColorPicker(Rect(0, 0, 10, 270))
        # Session-only authoring aid (never saved): end RGB follows start.
        self._link_toggle = ToggleControl("@link", "Link start/end", False)

        # Alerts (blocked switches, failures) surface as toasts, following
        # character_collision; routine confirmations stay in the status bar.
        self.toasts = ToastManager()
        self._context_menu = ContextMenu()
        self._toolbar = ToolbarLayout(gap=6, sep_w=10, margin=8)
        self._toolbar_separators: list[tuple[int, int]] = []
        self._btn_save = Button(Rect(0, 0, 64, 24), text="Save", on_click=self.save)
        self._btn_revert = Button(Rect(0, 0, 64, 24), text="Revert", on_click=self.revert)
        self._btn_blank = Button(
            Rect(0, 0, 64, 24),
            text="Blank",
            on_click=lambda: self._load_named_blocking_dirty(BLANK_NAME),
        )
        self._toolbar_buttons: list[Button] = [
            self._btn_save,
            self._btn_revert,
            self._btn_blank,
        ]
        self._overflow_btn: Button | None = None
        self._build_toolbar_entries()

        self.undo_stack: list[tuple[str, dict, dict, str, str]] = []
        self.redo_stack: list[tuple[str, dict, dict, str, str]] = []
        self._gesture_base: dict | None = None
        self._gesture_base_name: str | None = None
        self._rename_base: str | None = None
        self._picker_base: dict | None = None

        self.sidebar_scroll = 0
        self.strip_scroll = 0

        self._focused_key: str | None = None

        self._side_bar = Scrollbar("vertical", on_scroll=self._on_side_scroll)
        self._strip_bar = Scrollbar("horizontal", on_scroll=self._on_strip_scroll)
        self.message = ""
        self.message_until = 0
        self._thumb_sims: list[tuple[str, PreviewSim]] = []
        self._thumb_rects: list[tuple[str, Rect]] = []
        self._sidebar_content_h = 0

        # Layout-owned rects (recomputed in layout()).
        self.r_toolbar = Rect(0, 0, 0, 0)
        self.r_sidebar = Rect(0, 0, 0, 0)
        self.r_canvas = Rect(0, 0, 0, 0)
        self.r_header = Rect(0, 0, 0, 0)
        self.r_transport = Rect(0, 0, 0, 0)
        self.r_strip = Rect(0, 0, 0, 0)
        self.r_status = Rect(0, 0, 0, 0)
        self._buttons: dict[str, Rect] = {}

        self._build_controls()
        self.color_picker.sync_from_config(self.working)

        self._refresh_libraries()
        self._rebuild_thumbs()
        self.layout()
        self.canvas.frame_view(SIM_AREA)

    # library #

    def _refresh_libraries(self) -> None:
        paths = [builtin_library_path()] + [p for p in list_libraries(self.data_root) if p != builtin_library_path()]
        if self.library_path is not None and self.library_path not in paths:
            paths.append(self.library_path)
        self._lib_paths = paths
        options = [self._lib_label(p) for p in paths]
        self.lib_choice = ChoiceControl("library", "Library", options, self._lib_label(self.library_path))
        self.layout()

    @staticmethod
    def _lib_label(path: Path | None) -> str:
        if path is None:
            return "-"
        if path == builtin_library_path():
            return "essentials (built-in)"
        name = path.name
        if name.endswith(".particles.json"):
            name = name[: -len(".particles.json")]
        return name

    def _lib_path_for(self, label: str) -> Path | None:
        for p in self._lib_paths:
            if self._lib_label(p) == label:
                return p
        return None

    def _switch_library(self, label: str) -> None:
        if self.is_dirty():
            self.toasts.warning("Save or Revert first - library switch blocked", duration=6.0)
            self.lib_choice.set_value(self._lib_label(self.library_path))
            return
        path = self._lib_path_for(label)
        if path is None:
            return
        library, warnings = builtin_library() if path == builtin_library_path() else ParticleLibrary.load(path)
        self.library = library
        self.library_path = path
        for w in warnings:
            self.toasts.warning(w)
        first = library.systems[0] if library.systems else None
        if first is not None:
            self.load_entry(first.name, dict(first.config))
        self._rebuild_thumbs()
        self.say(f"Library: {label} ({len(library.systems)} systems)")

    # document state

    def is_dirty(self) -> bool:
        return self.working != self.loaded_config or self.name_field.value != self.loaded_name

    def say(self, message: str, duration_ms: int = 3500) -> None:
        self.message = message
        self.message_until = _now_ms() + duration_ms

    def load_entry(self, name: str, config: dict) -> None:
        normalized, warnings = normalize_config(config)
        self.working = normalized
        self.loaded_name = name
        self.loaded_config = dict(normalized)
        self.name_field.set_value(name)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._gesture_base = None
        self._gesture_base_name = None
        self._picker_base = None
        self._build_controls()
        self.color_picker.sync_from_config(self.working)
        self.sim.reset(dict(normalized))
        self.layout()
        for w in warnings:
            self.toasts.warning(w)

    def revert(self) -> None:
        self.working = dict(self.loaded_config)
        self.name_field.set_value(self.loaded_name)
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._gesture_base = None
        self._gesture_base_name = None
        self._picker_base = None
        self._build_controls()
        self.color_picker.sync_from_config(self.working)
        self.sim.reset(dict(self.working))
        self.say("Reverted")

    def _save_target(self) -> Path:
        if self.library_path is not None and self.library_path != builtin_library_path():
            return self.library_path
        return self.data_root / LIBRARY_DIRNAME / "custom.particles.json"

    def save(self) -> None:
        name = self.name_field.value.strip() or "Untitled"
        target = self._save_target()
        library = self.library
        if target != self.library_path:
            library, _ = ParticleLibrary.load(target)
        existing = library.find(name)
        if existing is not None:
            existing.config = dict(self.working)
        else:
            library.systems.append(ParticleSystemEntry(name=name, config=dict(self.working)))
        try:
            library.save(target)
        except OSError as e:
            self.toasts.error(f"Save failed: {e}")
            return
        if target != self.library_path:
            # Redirected save (e.g. built-in is read-only): the entry now
            # lives in the custom file on disk, but keep viewing the
            # current library so the strip doesn't collapse. Refresh the
            # dropdown so the custom file is one click away.
            self._refresh_libraries()
        self.loaded_name = name
        self.loaded_config = dict(self.working)
        self.name_field.set_value(name)
        if self.export_node is not None:
            try:
                import json

                self.export_node.write_text(
                    json.dumps(
                        {
                            "name": name,
                            "config": {k: v for k, v in dict(self.working).items() if k not in TRANSIENT_PROPERTY_KEYS},
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except OSError as e:
                self.toasts.error(f"Saved {name}; node export failed: {e}")
                return
        self.say(f"Saved {name} -> {target.name}")

    # undo #

    def _push_undo(self, key: str, before: dict, before_name: str) -> None:
        after = copy.deepcopy(self.working)
        after_name = self.name_field.value
        if before == after and before_name == after_name:
            return
        now = _now_ms()
        mergeable = (
            key != "rename"
            and before_name == after_name
            and self.undo_stack
            and self.undo_stack[-1][0] == key
            and self.undo_stack[-1][3] == before_name
            and self.undo_stack[-1][4] == after_name
            and now - self._last_undo_ms < UNDO_COALESCE_MS
        )
        if mergeable:
            first_before = self.undo_stack[-1][1]
            first_before_name = self.undo_stack[-1][3]
            self.undo_stack[-1] = (
                key,
                first_before,
                after,
                first_before_name,
                after_name,
            )
        else:
            self.undo_stack.append((key, before, after, before_name, after_name))
        self._last_undo_ms = now
        self.redo_stack.clear()

    _last_undo_ms: int = 0

    def undo(self) -> None:
        if not self.undo_stack:
            return
        key, before, after, before_name, after_name = self.undo_stack.pop()
        self.redo_stack.append((key, before, after, before_name, after_name))
        self._restore(before, before_name)
        self.say(f"Undo {key}")

    def redo(self) -> None:
        if not self.redo_stack:
            return
        key, before, after, before_name, after_name = self.redo_stack.pop()
        self.undo_stack.append((key, before, after, before_name, after_name))
        self._last_undo_ms = _now_ms()
        self._restore(after, after_name)
        self.say(f"Redo {key}")

    def _restore(self, config: dict, name: str) -> None:
        self.working = copy.deepcopy(config)
        self.name_field.set_value(name)
        self._gesture_base = None
        self._gesture_base_name: str | None = None
        self._sync_controls_from_working()
        self.color_picker.sync_from_config(self.working)
        self.sim.reset(dict(self.working))

    # controls #-

    def _build_controls(self) -> None:
        c = self.working

        def num(
            key: str,
            label: str,
            lo: float,
            hi: float,
            kind: str = "linear",
            integer: bool = False,
        ) -> NumberControl:
            return NumberControl(key, label, lo, hi, float(self._read_key(key, lo)), kind, integer)

        self.controls = {
            "mode": ChoiceControl(
                "mode",
                "Mode",
                ["continuous", "burst", "field"],
                str(c.get("mode", "continuous")),
            ),
            "emission_shape": ChoiceControl(
                "emission_shape",
                "Shape",
                ["point", "rect", "circle", "line"],
                str(c.get("emission_shape", "point")),
            ),
            "direction": DirectionDial(c.get("direction", -1)),
            "spawn_rate": num("spawn_rate", "Spawn rate", 1, 300, integer=True),
            "max_particles": num("max_particles", "Max count", 1, 500, integer=True),
            "burst_count": num("burst_count", "Burst count", 0, 500, integer=True),
            "coverage": num("coverage", "Coverage", 0.05, 3.0),
            "field_quality": ChoiceControl(
                "field_quality",
                "Quality",
                ["low", "medium", "high"],
                str(c.get("field_quality", "medium")),
            ),
            "ground_bias": ToggleControl("ground_bias", "Ground bias", bool(c.get("ground_bias", False))),
            "speed_min": num("speed_min", "Speed min", 0, 300),
            "speed_max": num("speed_max", "Speed max", 0, 300),
            "spread": num("spread", "Spread", 0, 360),
            "gravity_x": num("gravity_x", "Gravity X", -200, 200),
            "gravity_y": num("gravity_y", "Gravity Y", -200, 200),
            "particle_shape": ChoiceControl(
                "particle_shape",
                "Shape",
                [
                    "circle",
                    "square",
                    "diamond",
                    "star",
                    "sparkle",
                    "smoke",
                    "fog",
                    "heart",
                    "line",
                ],
                str(c.get("particle_shape", "circle")),
            ),
            "particle_size_min": num("particle_size_min", "Size min", 1, 64),
            "particle_size_max": num("particle_size_max", "Size max", 1, 64),
            "start_scale": num("start_scale", "Start scale", 0.1, 3.0),
            "end_scale": num("end_scale", "End scale", 0.1, 3.0),
            "rotation_speed": num("rotation_speed", "Rotation", -360, 360),
            "alpha_fade": ChoiceControl(
                "alpha_fade",
                "Fade",
                ["none", "fade_out", "fade_in", "fade_both"],
                str(c.get("alpha_fade", "fade_out")),
            ),
            "lifetime_min": num("lifetime_min", "Life min", 0.1, 5.0, kind="log"),
            "lifetime_max": num("lifetime_max", "Life max", 0.1, 5.0, kind="log"),
            "timing.emitter_duration": num("timing.emitter_duration", "Duration (0=inf)", 0, 10.0),
            "timing.start_delay": num("timing.start_delay", "Start delay", 0, 5.0),
            "timing.loop": ToggleControl("timing.loop", "Loop", self._read_key("timing.loop", True)),
            "timing.burst_interval": num("timing.burst_interval", "Burst interval", 0, 2.0),
            "wrap": ToggleControl("wrap", "Wrap (toroidal)", bool(c.get("wrap", False))),
        }
        self._sections = [
            (
                "Emission",
                [
                    "mode",
                    "@fieldbox",
                    "emission_shape",
                    "direction",
                    "spawn_rate",
                    "max_particles",
                    "burst_count",
                    "timing.burst_interval",
                    "coverage",
                    "field_quality",
                    "ground_bias",
                ],
            ),
            ("Motion", ["speed_min", "speed_max", "spread", "gravity_x", "gravity_y"]),
            (
                "Appearance",
                [
                    "particle_shape",
                    "particle_size_min",
                    "particle_size_max",
                    "start_scale",
                    "end_scale",
                    "rotation_speed",
                    "alpha_fade",
                ],
            ),
            ("Colors", ["@picker", "@link"]),
            (
                "Lifetime",
                [
                    "lifetime_min",
                    "lifetime_max",
                    "timing.emitter_duration",
                    "timing.start_delay",
                    "timing.loop",
                ],
            ),
            ("Advanced", ["wrap"]),
        ]
        self.layout()

    def _visible_sections(self) -> list[tuple[str, list[str]]]:
        mode = str(self.working.get("mode", "continuous"))
        out = []
        for title, keys in self._sections:
            if mode != "burst":
                keys = [k for k in keys if k not in ("burst_count", "timing.burst_interval")]
            if mode != "field":
                keys = [k for k in keys if k not in ("@fieldbox", "coverage", "field_quality", "ground_bias")]
            out.append((title, keys))
        return out

    def _read_key(self, key: str, default: object = 0) -> object:
        """Read a (possibly dotted, e.g. ``timing.loop``) working value."""
        if "." in key:
            head, tail = key.split(".", 1)
            block = self.working.get(head)
            if isinstance(block, dict):
                return block.get(tail, default)
            return default
        return self.working.get(key, default)

    def _write_key(self, key: str, value: object) -> None:
        """Write a (possibly dotted) working value, creating the block."""
        if "." in key:
            head, tail = key.split(".", 1)
            block = self.working.get(head)
            if not isinstance(block, dict):
                block = {}
                self.working[head] = block
            block[tail] = value
        else:
            self.working[key] = value

    def _sync_controls_from_working(self) -> None:
        for key, ctrl in self.controls.items():
            if isinstance(ctrl, (NumberControl, ToggleControl)):
                ctrl.set_value(self._read_key(key, 0))
            elif isinstance(ctrl, ChoiceControl):
                ctrl.set_value(str(self._read_key(key, "")))
            elif isinstance(ctrl, DirectionDial):
                ctrl.set_value(self.working.get("direction", -1))

    def _control_value(self, key: str) -> object:
        ctrl = self.controls[key]
        value = ctrl.value  # type: ignore[union-attr]
        if isinstance(ctrl, NumberControl) and ctrl.integer:
            return int(round(float(value)))
        if isinstance(ctrl, NumberControl):
            return float(value)
        return value

    def _apply_change(self, key: str) -> None:
        """Apply one control's value to working + sim by severity tier."""
        if self._gesture_base is None:
            self._gesture_base = copy.deepcopy(self.working)
        self._write_key(key, self._control_value(key))
        if key == "mode" and self.working[key] == "field":
            self._apply_field_auto_sets()
        if key in _RESET_KEYS:
            self.sim.reset(dict(self.working))
        elif key in _RESPAWN_KEYS:
            self.sim.clear_particles()
            self.sim.live_set(dict(self.working))
        else:
            self.sim.live_set(dict(self.working))
        if key == "mode":
            # Gating changed: rebuild controls + layout for the new mode.
            self._build_controls()
            self.color_picker.sync_from_config(self.working)

    def _apply_field_auto_sets(self) -> None:
        """Apply the field contract with visible confirmation (reversible).

        Everything is an ordinary working-config value from here on:
        undo restores the pre-switch config, and the field box lists
        exactly what was set.
        """
        self.working.update(copy.deepcopy(FIELD_AUTO_SETS))
        self._sync_controls_from_working()
        self.say("Field mode: wrap, fill-once, rect emitter set (see box)")

    def _commit(self, key: str) -> None:
        if self._gesture_base is not None:
            base_name = self._gesture_base_name if self._gesture_base_name is not None else self.name_field.value
            self._push_undo(key, self._gesture_base, base_name)
            self._gesture_base = None
            self._gesture_base_name = None

    def _poll_color_picker(self) -> None:
        probe: dict = {}
        self.color_picker.sync_to_config(probe)
        if self._link_toggle.value:
            # Link wins: end RGB tracks start RGB -10. Alpha stays manual.
            for channel in ("r", "g", "b"):
                start = probe.get(f"start_color_{channel}", 0)
                try:
                    probe[f"end_color_{channel}"] = max(0, min(255, int(start) - 10))
                except (TypeError, ValueError):
                    pass
            self.color_picker.sync_from_config({**self.working, **probe})
        changed = [k for k in _COLOR_KEYS if probe.get(k) != self.working.get(k)]
        if changed:
            if self._picker_base is None:
                self._picker_base = copy.deepcopy(self.working)
            for k in changed:
                self.working[k] = probe[k]
            self.sim.live_set(dict(self.working))
        elif self._picker_base is not None:
            self._push_undo("colors", self._picker_base, self.name_field.value)
            self._picker_base = None

    # thumbnails #

    def _rebuild_thumbs(self) -> None:
        self._thumb_sims = []
        for i, system in enumerate(self.library.systems):
            sim = PreviewSim(dict(system.config), THUMB_AREA)
            sim.seed(1000 + i)
            sim.refill_if_field()  # field thumbs start filled, not empty
            for _ in range(90):
                sim.step_frame()
            sim.playing = True
            self._thumb_sims.append((system.name, sim))

    def _visible_thumb_range(self) -> tuple[int, int]:
        if not self._thumb_sims:
            return (0, 0)
        slot = THUMB_W + 8
        first = max(0, int(self.strip_scroll // slot) - 1)
        count = int(self.r_strip.width // slot) + 3
        return (first, min(len(self._thumb_sims), first + max(1, count)))

    # layout #-

    def set_rect(self, rect: Rect) -> None:
        self.rect = Rect(rect)
        self.layout()

    def layout(self) -> None:
        r = self.rect
        self.r_toolbar = Rect(r.x, r.y, r.width, TOOLBAR_H)
        self.r_status = Rect(r.x, r.bottom - STATUS_H, r.width, STATUS_H)
        self.r_strip = Rect(r.x, r.bottom - STATUS_H - STRIP_H, r.width, STRIP_H)
        self.r_transport = Rect(r.x, r.bottom - STATUS_H - STRIP_H - TRANSPORT_H, r.width, TRANSPORT_H)
        side_top = r.y + TOOLBAR_H
        side_bottom = r.bottom - STATUS_H - STRIP_H - TRANSPORT_H
        self.r_sidebar = Rect(r.x, side_top, SIDEBAR_W, max(0, side_bottom - side_top))
        self.r_header = Rect(r.x + SIDEBAR_W, side_top, r.width - SIDEBAR_W, HEADER_H)
        self.r_canvas = Rect(
            r.x + SIDEBAR_W,
            side_top + HEADER_H,
            max(0, r.width - SIDEBAR_W),
            max(0, side_bottom - side_top - HEADER_H),
        )
        self.canvas.set_rect(self.r_canvas)
        self._layout_toolbar(r)

        # Sidebar control rects.
        y = self.r_sidebar.y + 8 - self.sidebar_scroll
        x = self.r_sidebar.x + 10
        w = self.r_sidebar.width - 20
        for _title, keys in self._visible_sections():
            y += 22
            for key in keys:
                if key == "@picker":
                    self.color_picker.rect = Rect(x, y, w, 270)
                    # ColorField keeps its construction size; resize it too.
                    self.color_picker.field.rect.size = (w - 8, 120)
                    y += 274
                    continue
                if key == "@fieldbox":
                    y += FIELDBOX_H + 4
                    continue
                if key == "@link":
                    self._link_toggle.set_rect(x, y, w)
                    y += ToggleControl.ROW_H + 4
                    continue
                ctrl = self.controls[key]
                ctrl.set_rect(x, y, w)  # type: ignore[union-attr]
                y += ctrl.ROW_H + 4  # type: ignore[union-attr]
            y += 6
        self._sidebar_content_h = y - (self.r_sidebar.y - self.sidebar_scroll) + 8
        # Sync the shared scrollbar (right-edge overlay, like tile_grid).
        self._side_bar.resize(self.r_sidebar.right - 12, self.r_sidebar.y, 12, self.r_sidebar.height)
        self._side_bar.set_range(self._sidebar_content_h, self.r_sidebar.height, self.sidebar_scroll)
        self.sidebar_scroll = self._side_bar.scroll_pos

        # Transport buttons.
        self._buttons["Restart"] = Rect(r.x + SIDEBAR_W + 8, self.r_transport.y + 9, 70, 24)
        self._buttons["Play"] = Rect(r.x + SIDEBAR_W + 84, self.r_transport.y + 9, 64, 24)
        self._buttons["Step"] = Rect(r.x + SIDEBAR_W + 154, self.r_transport.y + 9, 56, 24)
        self._buttons["Burst"] = Rect(r.x + SIDEBAR_W + 216, self.r_transport.y + 9, 64, 24)
        self._buttons["Speed"] = Rect(r.x + SIDEBAR_W + 286, self.r_transport.y + 9, 56, 24)
        self._buttons["Fixed"] = Rect(r.x + SIDEBAR_W + 348, self.r_transport.y + 9, 76, 24)
        vx = self.r_transport.right - 8
        for label, width in (("Frame", 64), ("Bounds", 70), ("BG", 90)):
            vx -= width + 6
            self._buttons[label] = Rect(vx, self.r_transport.y + 9, width, 24)

        # Strip slots. Range first so a shrunken library can't strand
        # the offset past the end; thumb placement uses the synced value.
        strip_content = len(self._thumb_sims) * (THUMB_W + 8) + 16
        self._strip_bar.resize(self.r_strip.x, self.r_strip.bottom - 12, self.r_strip.width, 12)
        self._strip_bar.set_range(strip_content, self.r_strip.width, self.strip_scroll)
        self.strip_scroll = self._strip_bar.scroll_pos
        self._thumb_rects = []
        slot = THUMB_W + 8
        sx = self.r_strip.x + 8 - self.strip_scroll
        sy = self.r_strip.y + 8
        for i, (name, _sim) in enumerate(self._thumb_sims):
            self._thumb_rects.append((name, Rect(sx + i * slot, sy, THUMB_W, THUMB_H + 22)))

    def _build_toolbar_entries(self) -> None:
        """Declare toolbar widgets for ToolbarLayout.

        Rebuilt on every layout so widget swaps (e.g. a fresh
        ``lib_choice`` from ``_refresh_libraries``) can never go stale.
        Widths are declared here  no hand cursor  so entries can
        neither overlap nor silently clip; low-priority groups collapse
        into the overflow popup on narrow windows.
        """
        layout = self._toolbar
        layout.clear()
        # Priorities: LOWER collapses first,
        # so actions go first and the library picker collapses last.
        layout.add_widget(
            self.lib_choice,
            262,
            group="library",
            priority=30,
            collapsible=False,
            label="Library",
        )
        layout.add_separator(group="library", priority=30)
        layout.add_widget(
            self.name_field,
            180,
            group="entry",
            priority=20,
            collapsible=False,
            label="Entry name",
        )
        layout.add_separator(group="entry", priority=20)
        for btn, label in (
            (self._btn_save, "Save"),
            (self._btn_revert, "Revert"),
            (self._btn_blank, "Blank"),
        ):
            layout.add_widget(
                btn,
                64,
                group="actions",
                priority=10,
                label=label,
                on_activate=btn.on_click,
            )

    def _open_overflow_menu(self) -> None:
        btn = self._overflow_btn
        if btn is not None:
            pos = (btn.rect.x, btn.rect.bottom + 2)
        else:
            pos = (self.rect.x + 200, self.rect.y + TOOLBAR_H)
        rows = self._toolbar.overflow_rows()
        self._context_menu.popup(
            [MenuAction(r.label, r.on_activate) for r in rows] or [MenuAction("Toolbar fits", lambda: None)],
            pos,
            (self.rect.right, self.rect.bottom),
        )

    def _layout_toolbar(self, r: Rect) -> None:
        self._build_toolbar_entries()
        row = Rect(r.x, r.y, r.width, TOOLBAR_H)
        overflow_rect = self._toolbar.reflow(row, r.y + 7, 24)
        self._toolbar_separators = list(self._toolbar.separators)
        # The engine assigns .rect directly; re-sync the ChoiceControl's
        # inner dropdown rect which set_rect derives.
        lc = self.lib_choice.rect
        self.lib_choice.set_rect(lc.x, lc.y, lc.w)
        if overflow_rect is not None:
            if self._overflow_btn is None or self._overflow_btn.rect != overflow_rect:
                self._overflow_btn = Button(
                    overflow_rect,
                    text=">>",
                    tooltip_text="More tools",
                    border_radius=3,
                    on_click=self._open_overflow_menu,
                )
        else:
            self._overflow_btn = None

    # events #-

    def _typing_somewhere(self) -> bool:
        if self.name_field.is_typing():
            return True
        return any(isinstance(c, NumberControl) and c.is_typing() for c in self.controls.values())

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._focused_key = None
            if self.r_sidebar.collidepoint(mouse):
                for key, ctrl in self.controls.items():
                    if isinstance(ctrl, NumberControl) and ctrl.rect.collidepoint(mouse):
                        self._focused_key = key
                        break
            for key, ctrl in self.controls.items():
                if isinstance(ctrl, NumberControl):
                    ctrl.focused = key == self._focused_key

        if self._context_menu.is_open:
            return self._context_menu.handle_event(event)

        if self._typing_somewhere():
            if event.type == pygame.KEYDOWN:
                if self.name_field.is_typing():
                    if self._rename_base is None:
                        self._rename_base = self.name_field.value
                    result = self.name_field.handle_event(event)
                    if result == "change-commit":
                        self._push_undo(
                            "rename",
                            copy.deepcopy(self.working),
                            self._rename_base,
                        )
                        self._rename_base = None
                    return True
                for ctrl in self.controls.values():
                    if isinstance(ctrl, NumberControl) and ctrl.is_typing():
                        key = ctrl.key
                        if self._gesture_base is None:
                            self._gesture_base = copy.deepcopy(self.working)
                            self._gesture_base_name = self.name_field.value
                        result = ctrl.handle_event(event)
                        if result == "change":
                            self._apply_change(key)
                            self._commit(key)
                        return True
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.name_field.handle_event(event)
                for ctrl in self.controls.values():
                    if isinstance(ctrl, NumberControl):
                        ctrl.handle_event(event)
                return True
            return False

        # Toolbar.
        if self.r_toolbar.collidepoint(mouse) or event.type == pygame.KEYDOWN:
            if self.lib_choice.handle_event(event):
                self._switch_library(self.lib_choice.value)
                return True
            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.name_field.rect.collidepoint(mouse)
                and not self.name_field.is_typing()
            ):
                self._rename_base = self.name_field.value
            result = self.name_field.handle_event(event)
            if result == "change-commit":
                self._push_undo(
                    "rename",
                    copy.deepcopy(self.working),
                    self._rename_base or self.name_field.value,
                )
                self._rename_base = None
                return True
            if event.type == pygame.MOUSEMOTION:
                for btn in (*self._toolbar_buttons,):
                    if getattr(btn, "visible", True):
                        btn.handle_event(event)
                if self._overflow_btn is not None:
                    self._overflow_btn.handle_event(event)

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                for btn in (*self._toolbar_buttons,):
                    btn.handle_event(event)
                if self._overflow_btn is not None:
                    self._overflow_btn.handle_event(event)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for btn in (*self._toolbar_buttons,):
                    if getattr(btn, "visible", True) and btn.handle_event(event):
                        return True
                if self._overflow_btn is not None and self._overflow_btn.handle_event(event):
                    return True

        if self.r_sidebar.collidepoint(mouse) or event.type in (
            pygame.KEYDOWN,
            pygame.MOUSEBUTTONUP,
        ):
            if self._side_bar.handle_event(event):
                self.sidebar_scroll = self._side_bar.scroll_pos
                self.layout()
                return True
            for key, ctrl in self.controls.items():
                if key not in self._flat_visible_keys():
                    continue
                result = ctrl.handle_event(event)  # type: ignore[union-attr]
                if result == "change":
                    self._apply_change(key)
                    return True
                if result == "commit":
                    self._commit(key)
                    return True
                if result == "change-commit":
                    self._apply_change(key)
                    self._commit(key)
                    return True
            if "@link" in self._flat_visible_keys():
                link_result = self._link_toggle.handle_event(event)
                if link_result == "change-commit":
                    if self._link_toggle.value:
                        self.say("End color linked to start -10")
                    return True
            picker_hit = self.color_picker.handle_event(event)
            if picker_hit:
                return True
            if event.type == pygame.MOUSEWHEEL and self.r_sidebar.collidepoint(mouse):
                self.sidebar_scroll = max(0, self.sidebar_scroll - event.y * 24)
                self._clamp_sidebar_scroll()
                self.layout()
                return True

        if self.canvas.handle_event(event):
            return True

        if event.type in (
            pygame.MOUSEMOTION,
            pygame.MOUSEBUTTONUP,
        ) and self._strip_bar.handle_event(event):
            self.strip_scroll = self._strip_bar.scroll_pos
            self.layout()
            return True

        # Transport buttons.
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.r_transport.collidepoint(mouse):
                return self._transport_click(mouse)
            if self.r_strip.collidepoint(mouse) and event.button == 1:
                if self._strip_bar.handle_event(event):
                    self.strip_scroll = self._strip_bar.scroll_pos
                    self.layout()
                    return True
                for name, trect in self._thumb_rects:
                    if trect.collidepoint(mouse):
                        self._load_named_blocking_dirty(name)
                        return True

        if event.type == pygame.MOUSEWHEEL and self.r_strip.collidepoint(mouse):
            if self._strip_bar.handle_event(event):
                self.strip_scroll = self._strip_bar.scroll_pos
                self.layout()
                return True
            max_scroll = max(0, len(self._thumb_rects) * (THUMB_W + 8) - self.r_strip.width + 16)
            self.strip_scroll = max(0, min(max_scroll, self.strip_scroll - event.y * 40))
            self.layout()
            return True

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)
            if ctrl and event.key == pygame.K_z and not (mods & pygame.KMOD_SHIFT):
                self.undo()
                return True
            if ctrl and (event.key == pygame.K_y or (event.key == pygame.K_z and (mods & pygame.KMOD_SHIFT))):
                self.redo()
                return True
            if ctrl and event.key == pygame.K_s:
                self.save()
                return True
            if event.key == pygame.K_SPACE:
                self.sim.playing = not self.sim.playing
                return True
            if event.key == pygame.K_r:
                self.sim.restart()
                return True
            if event.key == pygame.K_b:
                if self._is_field_mode():
                    self._do_fill()
                else:
                    self.sim.trigger_burst()
                    self.say(f"Burst x{self.working.get('burst_count', 30)}")
                return True
            if event.key == pygame.K_s:
                self.sim.step_frame()
                return True
            if event.key == pygame.K_f:
                self.canvas.frame_view(SIM_AREA)
                return True
        return False

    def _flat_visible_keys(self) -> list[str]:
        keys: list[str] = []
        for _title, ks in self._visible_sections():
            keys.extend(ks)
        return keys

    def _on_side_scroll(self, val: float) -> None:
        self.sidebar_scroll = val
        self.layout()

    def _on_strip_scroll(self, val: float) -> None:
        self.strip_scroll = val
        self.layout()

    def _clamp_sidebar_scroll(self) -> None:
        max_scroll = max(0, self._sidebar_content_h - self.r_sidebar.height + 8)
        self.sidebar_scroll = max(0, min(max_scroll, self.sidebar_scroll))

    def _load_named_blocking_dirty(self, name: str) -> None:
        if self.is_dirty() and name != self.loaded_name:
            self.toasts.warning("Save or Revert first - preset switch blocked", duration=6.0)
            return
        entry = self.library.find(name)
        if entry is not None:
            self.load_entry(entry.name, dict(entry.config))

    def _is_field_mode(self) -> bool:
        return str(self.working.get("mode", "continuous")) == "field"

    def _do_fill(self) -> None:
        """Fill-once: burst the coverage-derived count (capped). Soft on
        contract violations  warns instead of refusing, so authors can
        preview partial states while tuning."""
        from .models import QUALITY_DENSITY, count_for_coverage

        try:
            spawn = int(self.working.get("spawn_rate", 0))
        except (TypeError, ValueError):
            spawn = -1
        contract_ok = bool(self.working.get("wrap")) and spawn == 0
        try:
            density = QUALITY_DENSITY[str(self.working.get("field_quality", "medium"))]
        except KeyError:
            density = 1.0
        try:
            raw = count_for_coverage(
                self.working,
                float(self.working.get("coverage", 1.0)) * density,
                SIM_AREA[2],
                SIM_AREA[3],
            )
        except (ValueError, TypeError) as e:
            self.toasts.error(f"Fill failed: {e}")
            return
        n = self.sim.fill(raw)
        if contract_ok:
            self.say(f"Field filled x{n}")
        else:
            self.toasts.warning(f"Field filled x{n} - restore wrap + zero spawn (see box)")

    def _transport_click(self, mouse: tuple[int, int]) -> bool:
        b = self._buttons
        if b["Restart"].collidepoint(mouse):
            self.sim.restart()
            return True
        if b["Play"].collidepoint(mouse):
            self.sim.playing = not self.sim.playing
            return True
        if b["Step"].collidepoint(mouse):
            self.sim.step_frame()
            return True
        if b["Burst"].collidepoint(mouse):
            if self._is_field_mode():
                self._do_fill()
            else:
                n = self.sim.trigger_burst()
                self.say(f"Burst x{n}")
            return True
        if b["Speed"].collidepoint(mouse):
            i = SPEEDS.index(self.sim.speed) if self.sim.speed in SPEEDS else 2
            self.sim.speed = SPEEDS[(i + 1) % len(SPEEDS)]
            return True
        if b["Fixed"].collidepoint(mouse):
            self.sim.fixed_step = not self.sim.fixed_step
            return True
        if b["Frame"].collidepoint(mouse):
            self.canvas.frame_view(SIM_AREA)
            return True
        if b["Bounds"].collidepoint(mouse):
            self.canvas.show_bounds = not self.canvas.show_bounds
            return True
        if b["BG"].collidepoint(mouse):
            i = BACKGROUNDS.index(self.canvas.bg_mode)
            self.canvas.bg_mode = BACKGROUNDS[(i + 1) % len(BACKGROUNDS)]
            return True
        return False

    # per-frame #-

    def update(self, real_dt: float) -> None:
        self._poll_color_picker()
        self.sim.update(real_dt)
        first, last = self._visible_thumb_range()
        budget = THUMB_BUDGET
        for _name, tsim in self._thumb_sims[first:last]:
            if budget <= 0:
                break
            tsim.update(FIXED_DT * 2)
            budget -= 1
        if _now_ms() > self.message_until:
            self.message = ""

    # draw #-

    def _draw_fieldbox(self, screen: pygame.Surface, x: int, y: int) -> int:
        """Field-mode contract box: what was auto-set, and fill readiness."""
        small = FONTS.get_small_font()
        wrap_ok = bool(self.working.get("wrap"))
        try:
            spawn = int(self.working.get("spawn_rate", 0))
        except (TypeError, ValueError):
            spawn = -1
        ready = wrap_ok and spawn == 0
        lines = [
            ("Auto-configured for field emission:", COLORS.text_dim),
            (
                f"{'[x]' if wrap_ok else '[ ]'} Wrap    {'[x]' if spawn == 0 else '[ ]'} Fill-once    [x] Rect emitter",
                COLORS.text if ready else (220, 150, 80),
            ),
            (
                "Fill with the Fill button below" if ready else "Restore wrap + zero spawn to fill",
                COLORS.text_dim,
            ),
        ]
        for text, color in lines:
            screen.blit(small.render(text, True, color), (x, y))
            y += 18
        return y + 14

    def _draw_button(
        self,
        screen: pygame.Surface,
        label: str,
        active: bool = False,
        text: str | None = None,
    ) -> None:
        r = self._buttons[label]
        bg = COLORS.selected if active else COLORS.panel_alt
        pygame.draw.rect(screen, bg, r, border_radius=4)
        pygame.draw.rect(screen, COLORS.border_soft, r, 1, border_radius=4)
        font = FONTS.get_font(12)
        fg = COLORS.text_on_selected if active else COLORS.text
        txt = font.render(text or label, True, fg)
        screen.blit(txt, txt.get_rect(center=r.center))

    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(COLORS.panel, self.rect)
        font = FONTS.get_font(12)
        bold = FONTS.get_bold_font(13)
        small = FONTS.get_small_font()

        # Toolbar.
        pygame.draw.rect(screen, COLORS.header, self.r_toolbar)
        sep_h = 16
        for sx, sy in self._toolbar_separators:
            pygame.draw.line(
                screen,
                COLORS.border_soft,
                (sx, sy - sep_h // 2),
                (sx, sy + sep_h // 2),
                2,
            )
        self.lib_choice.draw(screen)
        screen.blit(
            font.render("Name", True, COLORS.text_dim),
            (self.name_field.rect.x - 42, self.r_toolbar.y + 11),
        )
        self.name_field.draw(screen)
        self._btn_save.active = self.is_dirty()
        for btn in self._toolbar_buttons:
            if getattr(btn, "visible", True):
                btn.draw(screen)
        if self._overflow_btn is not None:
            self._overflow_btn.draw(screen)

        # Sidebar.
        pygame.draw.rect(screen, COLORS.panel_alt, self.r_sidebar)
        clip = screen.get_clip()
        screen.set_clip(self.r_sidebar)
        y = self.r_sidebar.y + 8 - self.sidebar_scroll
        x = self.r_sidebar.x + 10
        for title, keys in self._visible_sections():
            screen.blit(bold.render(title, True, COLORS.accent_hover), (x, y))
            y += 22
            for key in keys:
                if key == "@picker":
                    self.color_picker.draw(screen)
                    y += 274
                    continue
                if key == "@fieldbox":
                    y = self._draw_fieldbox(screen, x, y)
                    continue
                if key == "@link":
                    self._link_toggle.draw(screen)
                    y += ToggleControl.ROW_H + 4
                    continue
                self.controls[key].draw(screen)  # type: ignore[union-attr]
                y += self.controls[key].ROW_H + 4  # type: ignore[union-attr]
            y += 6
        screen.set_clip(clip)
        self._side_bar.draw(screen)
        for _key, ctrl in self.controls.items():
            if isinstance(ctrl, ChoiceControl) and ctrl.is_open:
                ctrl.draw_options(screen)

        # Canvas header.
        pygame.draw.rect(screen, COLORS.header, self.r_header)
        identity = identify(self.working, self.library)
        mode = str(self.working.get("mode", "continuous"))
        state = "LIVE" if self.sim.playing else "PAUSED"
        state_color = (120, 220, 120) if self.sim.playing else (220, 180, 80)
        screen.blit(
            bold.render(self.name_field.value or "Untitled", True, COLORS.text),
            (self.r_header.x + 10, self.r_header.y + 3),
        )
        sub = f"{identity} | {mode} | {self.sim.status_text()} | {self.sim.elapsed:.2f}s | {self.sim.count} particles"
        screen.blit(
            small.render(sub, True, COLORS.text_dim),
            (self.r_header.x + 10, self.r_header.y + 22),
        )
        st = bold.render(state, True, state_color)
        screen.blit(st, (self.r_header.right - st.get_width() - 10, self.r_header.y + 11))

        # Canvas.
        self.canvas.draw(screen, self.sim)

        # Transport.
        pygame.draw.rect(screen, COLORS.header, self.r_transport)
        self._draw_button(screen, "Restart")
        self._draw_button(screen, "Play", active=self.sim.playing)
        self._draw_button(screen, "Step")
        self._draw_button(screen, "Burst", text="Fill" if self._is_field_mode() else None)
        spd = self._buttons["Speed"]
        pygame.draw.rect(screen, COLORS.panel_alt, spd, border_radius=4)
        pygame.draw.rect(screen, COLORS.border_soft, spd, 1, border_radius=4)
        txt = font.render(f"{self.sim.speed:g}x", True, COLORS.text)
        screen.blit(txt, txt.get_rect(center=spd.center))
        self._draw_button(screen, "Fixed", active=self.sim.fixed_step)
        self._draw_button(screen, "Frame")
        self._draw_button(screen, "Bounds", active=self.canvas.show_bounds)
        bg = self._buttons["BG"]
        pygame.draw.rect(screen, COLORS.panel_alt, bg, border_radius=4)
        pygame.draw.rect(screen, COLORS.border_soft, bg, 1, border_radius=4)
        txt = font.render(f"BG: {self.canvas.bg_mode}", True, COLORS.text)
        screen.blit(txt, txt.get_rect(center=bg.center))
        if self.sim.dt_clamped:
            warn = small.render("dt clamped", True, (220, 150, 80))
            screen.blit(warn, (self.r_transport.x + SIDEBAR_W + 432, self.r_transport.y + 14))

        # Strip.
        pygame.draw.rect(screen, COLORS.panel, self.r_strip)
        pygame.draw.rect(screen, COLORS.border_soft, self.r_strip, 1)
        clip = screen.get_clip()
        screen.set_clip(self.r_strip)
        for name, trect in self._thumb_rects:
            thumb = Rect(trect.x, trect.y, THUMB_W, THUMB_H)
            pygame.draw.rect(screen, COLORS.bg, thumb, border_radius=4)
            tsim = next((s for n, s in self._thumb_sims if n == name), None)
            if tsim is None:  # stale rect (library swapped mid-frame); skip
                continue

            inner = screen.get_clip()
            screen.set_clip(thumb)
            tsim.preview.draw(screen, 0, 0, 0.8, thumb)
            screen.set_clip(inner)
            selected = name == self.loaded_name and not self.is_dirty()
            pygame.draw.rect(
                screen,
                COLORS.selected if selected else COLORS.border_soft,
                thumb,
                2 if selected else 1,
                border_radius=4,
            )
            label = small.render(
                name if len(name) <= 16 else name[:15] + "...",
                True,
                COLORS.text if selected else COLORS.text_dim,
            )
            screen.blit(label, (trect.x + 2, trect.y + THUMB_H + 4))
        screen.set_clip(clip)
        self._strip_bar.draw(screen)

        # Status.
        pygame.draw.rect(screen, COLORS.header, self.r_status)
        dirty = "* " if self.is_dirty() else ""
        msg = f"{dirty}{self.message}" if self.message else (f"{dirty}Ready" if dirty else "Ready")
        screen.blit(
            small.render(msg, True, COLORS.text_dim),
            (self.r_status.x + 8, self.r_status.y + 5),
        )
        lib_txt = small.render(
            f"{self._lib_label(self.library_path)} | {len(self.library.systems)} systems",
            True,
            COLORS.text_dim,
        )
        screen.blit(
            lib_txt,
            (self.r_status.right - lib_txt.get_width() - 8, self.r_status.y + 5),
        )

        if self._context_menu.is_open:
            self._context_menu.draw(screen)
