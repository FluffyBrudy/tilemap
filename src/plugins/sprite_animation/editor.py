"""
SpriteAnimationEditor — main composite widget.

Combines FramePicker, Timeline, and AnimationPreview into a single
panel with a toolbar for animation management and file I/O.

Usage modes:
    1. **Standalone** — SpriteAnimationEditor.from_surface(surf).run()
    2. **Widget**     — Instantiate with a rect, call handle_event / draw
    3. **Protocol**   — Pass a SpriteSheetProvider for duck-typed integration
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple, Union, cast

import pygame
from pygame import Rect, Surface, Color
from utils.font_manager import font_manager, FontWeight, FontStyle
from utils.icon_manager import icon_manager
from utils.project_paths import resolve_project_path
from utils import error_handler
from widgets.input import InlineTextInput
from .clipboard_util import copy_plain_text
from .frame_picker import FramePicker
from .models import Animation, AnimationLibrary, AnimationMarker
from .preview import AnimationPreview
from .protocols import AnimationConsumer, SpriteSheetProvider
from .timeline import Timeline
from .validation import collect_clip_warnings


if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
_COLORS = {
    "bg": (28, 30, 34),
    "toolbar": (36, 39, 45),
    "toolbar_border": (55, 58, 64),
    "border": (60, 62, 65),
    "text": (230, 230, 230),
    "text_dim": (140, 140, 140),
    "accent": (80, 120, 200),
    "accent_hover": (100, 140, 220),
    "btn": (50, 54, 62),
    "btn_hover": (65, 70, 80),
    "btn_active": (50, 70, 110),
    "btn_danger": (120, 50, 50),
    "btn_danger_hover": (160, 60, 60),
    "success": (80, 180, 120),
    "dropdown_bg": (38, 41, 48),
    "dropdown_hover": (55, 60, 72),
    "dropdown_border": (70, 74, 80),
    "input_bg": (30, 32, 38),
    "text_edit": (255, 220, 100),
}

TOOLBAR_ROW1_H = 36
TOOLBAR_ROW2_H = 26
TOOLBAR_H = TOOLBAR_ROW1_H + TOOLBAR_ROW2_H
PREVIEW_W = 220
TIMELINE_H = 132
META_PANEL_W = 268
META_PANEL_H = 212
META_ROW_H = 22


def _parse_metadata_value(text: str):
    """Parse a metadata field string into a JSON-friendly Python value."""
    s = text.strip()
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low == "null":
        return None
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    try:
        if "." in s or "e" in low:
            return float(s)
        return int(s)
    except ValueError:
        return s


def _metadata_value_repr(value: object) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(value)


class SpriteAnimationEditor:
    """Godot-like sprite animation editor panel.

    Layout::

        +----------------------------------------------------+
        | Toolbar: [idle] [+] [X] | [Save] [Load]           |
        +---------------+------------------------------------+
        |   Preview     |     Spritesheet Frame Picker       |
        |   (220px w)   |     (pan/zoom, click to add)       |
        +---------------+------------------------------------+
        | Timeline (frame strip, 130px h)                    |
        +----------------------------------------------------+
    """

    def __init__(
        self,
        rect: Rect,
        surface: Optional[pygame.Surface] = None,
        tile_size: Tuple[int, int] = (64, 64),
        *,
        provider: Optional[SpriteSheetProvider] = None,
        consumer: Optional[AnimationConsumer] = None,
    ):
        self.rect = rect
        self.consumer = consumer
        self.visible = True

        # Resolve surface from provider or direct arg
        if provider is not None:
            self._provider = provider
            self._surface = provider.get_surface()
            self._tile_size = provider.get_tile_size()
            self._sheet_name = provider.get_name()
        elif surface is not None:
            self._provider = None
            self._surface = surface
            self._tile_size = tile_size
            self._sheet_name = "Spritesheet"
        else:
            # Allow initialization without surface - user will load spritesheet later
            self._provider = None
            self._surface = cast(Surface, None)
            self._tile_size = tile_size
            self._sheet_name = "No Spritesheet"

        # Animation library (holds all named animations)
        self.library = AnimationLibrary(tile_size=self._tile_size)
        self._active_anim_name: Optional[str] = None

        # Create dummy surface if none provided (will be replaced when spritesheet is loaded)
        if self._surface is None:
            dummy_surface = pygame.Surface((64, 64), pygame.SRCALPHA)
            dummy_surface.fill((50, 50, 50, 128))  # Semi-transparent gray
        else:
            dummy_surface = self._surface

        # Sub-widgets (must be created before any animation sync)
        fp_rect, pv_rect, tl_rect = self._layout_rects()
        self.frame_picker = FramePicker(fp_rect, dummy_surface, self._tile_size)
        self.preview = AnimationPreview(pv_rect, dummy_surface, self._tile_size)
        self.timeline = Timeline(tl_rect, dummy_surface, self._tile_size)

        # Wire callbacks
        self.frame_picker.on_frame_clicked = self._on_tile_clicked
        self.timeline.on_frame_selected = self._on_timeline_frame_selected
        self.timeline.on_frames_changed = self._on_frames_changed
        self.timeline.on_markers_changed = self._on_markers_changed
        self.preview.on_playback_fps_changed = self._on_preview_fps_changed

        # Create a default animation (now safe — widgets exist)
        self._create_new_animation("idle")

        # Dropdown state
        self._dropdown_open = False
        self._dropdown_rect = Rect(0, 0, 0, 0)
        self._dropdown_items_rects: List[Rect] = []

        # Rename state
        self._renaming = False
        self._rename_input = InlineTextInput("anim_rename", "")

        # Toolbar button rects (calculated in draw)
        self._btn_new = Rect(0, 0, 0, 0)
        self._btn_del = Rect(0, 0, 0, 0)
        self._btn_save = Rect(0, 0, 0, 0)
        self._btn_load = Rect(0, 0, 0, 0)
        self._btn_load_spritesheet = Rect(0, 0, 0, 0)
        self._btn_meta = Rect(0, 0, 0, 0)
        self._btn_anim_selector = Rect(0, 0, 0, 0)
        self._btn_rename = Rect(0, 0, 0, 0)
        self._btn_info = Rect(0, 0, 0, 0)
        self._btn_dup = Rect(0, 0, 0, 0)
        self._btn_mk = Rect(0, 0, 0, 0)
        self._btn_copyjson = Rect(0, 0, 0, 0)

        self._clip_warnings: List[str] = []

        # Metadata side panel (generic JSON-friendly key/value pairs on the active clip)
        self._meta_panel_open = False
        self._meta_panel_rect = Rect(0, 0, 0, 0)
        self._meta_scroll = 0
        self._meta_key_input = ""
        self._meta_value_input = ""
        self._editing_meta_key = False
        self._editing_meta_value = False
        self._btn_meta_add = Rect(0, 0, 0, 0)
        self._btn_meta_key = Rect(0, 0, 0, 0)
        self._btn_meta_value = Rect(0, 0, 0, 0)
        self._meta_delete_btn_rects: List[Rect] = []
        self._meta_row_pick_rects: List[Tuple[str, str, Rect]] = []

        # Spritesheet / clip info card (hover or click-to-pin; drawn after widgets so it is visible)
        self._show_info_tooltip = False
        self._info_tooltip_pinned = False
        self._info_tooltip_screen_rect = Rect(0, 0, 0, 0)

        # Frame size controls
        self._frame_width_input = str(self._tile_size[0])
        self._frame_height_input = str(self._tile_size[1])
        self._editing_frame_width = False
        self._editing_frame_height = False
        self._btn_frame_width = Rect(0, 0, 0, 0)
        self._btn_frame_height = Rect(0, 0, 0, 0)

        # Grid offset controls
        self._offset_x_input = "0"
        self._offset_y_input = "0"
        self._editing_offset_x = False
        self._editing_offset_y = False
        self._btn_offset_x = Rect(0, 0, 0, 0)
        self._btn_offset_y = Rect(0, 0, 0, 0)
        self._grid_offset_x = 0
        self._grid_offset_y = 0

        self._ensure_fonts()

        # For standalone mode
        self._clock: Optional[pygame.time.Clock] = None

        # File manager dialog
        self._file_manager = None

        # Track the last saved path for quick save (Ctrl+S)
        self._last_saved_path: Optional[Path] = None
        self._data_root: Optional[Path] = Path.cwd() / "data"

        # Sync sub-widgets
        self._sync_active_animation()

    # ------------------------------------------------------------------
    # Class-level convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_surface(
        cls,
        surface: pygame.Surface,
        tile_size: Tuple[int, int] = (32, 32),
        window_size: Tuple[int, int] = (1100, 720),
        consumer: Optional[AnimationConsumer] = None,
    ) -> SpriteAnimationEditor:
        """Create an editor configured for standalone execution."""
        rect = Rect(0, 0, *window_size)
        return cls(rect, surface=surface, tile_size=tile_size, consumer=consumer)

    @classmethod
    def from_path(
        cls,
        image_path: Path,
        tile_size: Tuple[int, int] = (32, 32),
        window_size: Tuple[int, int] = (1100, 720),
        data_root: Path = None,
    ) -> SpriteAnimationEditor:
        """Load a spritesheet from disk and create a standalone editor."""
        pygame.init()
        pygame.display.set_mode(window_size, pygame.RESIZABLE)
        surf = pygame.image.load(str(image_path)).convert_alpha()
        ed = cls.from_surface(surf, tile_size, window_size)
        ed.library.spritesheet_path = str(image_path)
        ed._sheet_name = image_path.name
        ed._data_root = data_root
        return ed

    # ------------------------------------------------------------------
    # Standalone main loop
    # ------------------------------------------------------------------

    def run(self, fps: int = 60) -> None:
        """Block and run the editor as a standalone window."""
        if not pygame.get_init():
            pygame.init()
        screen = pygame.display.set_mode((self.rect.w, self.rect.h), pygame.RESIZABLE)
        pygame.display.set_caption(f"Sprite Animation Editor — {self._sheet_name}")
        self._clock = pygame.time.Clock()
        running = True

        while running:
            dt = self._clock.tick(fps)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    self.rect = Rect(0, 0, event.w, event.h)
                    self._relayout()
                    screen = pygame.display.set_mode(
                        (event.w, event.h), pygame.RESIZABLE
                    )
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self._info_tooltip_pinned:
                            self._info_tooltip_pinned = False
                            continue
                        # Don't close editor if file manager is open - let file manager handle ESC
                        if self._file_manager is None:
                            running = False
                        continue
                self.handle_event(event)

            self.update(dt)
            screen.fill(_COLORS["bg"])
            self.draw(screen)
            pygame.display.flip()

        pygame.quit()

    # ------------------------------------------------------------------
    # Widget interface (for embedding)
    # ------------------------------------------------------------------

    def update(self, dt_ms: float = 16.0) -> None:
        """Advance animation playback. Call every frame."""
        self.preview.update(dt_ms)
        self.timeline.scrubber_frac = self.preview.scrubber_frac

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Route event to sub-widgets. Returns True if consumed."""
        if not self.visible:
            return False

        # File manager takes priority
        if self._file_manager:
            return self._file_manager.handle_event(event)

        if self.frame_picker.is_filter_input_active() and event.type == pygame.KEYDOWN:
            if self.frame_picker.handle_filter_keydown(event):
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse = pygame.mouse.get_pos()
            if (
                self.preview.is_fps_input_active()
                and not self.preview.fps_input_contains(mouse)
            ):
                self.preview.commit_fps_input()
            if self._info_tooltip_pinned:
                if not self._btn_info.collidepoint(
                    mouse
                ) and not self._info_tooltip_screen_rect.collidepoint(mouse):
                    self._info_tooltip_pinned = False

        # Metadata panel: Esc closes or unfocuses fields
        if (
            self._meta_panel_open
            and event.type == pygame.KEYDOWN
            and event.key == pygame.K_ESCAPE
        ):
            if self._editing_meta_key or self._editing_meta_value:
                self._editing_meta_key = False
                self._editing_meta_value = False
                return True
            self._meta_panel_open = False
            return True

        if (
            not self._meta_panel_open
            and event.type == pygame.KEYDOWN
            and event.key == pygame.K_ESCAPE
            and self._info_tooltip_pinned
        ):
            self._info_tooltip_pinned = False
            return True

        if self._meta_panel_open and self._route_meta_panel_event(event):
            return True

        # Global keyboard shortcuts (when not editing text)
        if (
            event.type == pygame.KEYDOWN
            and not self._renaming
            and not self._editing_frame_width
            and not self._editing_frame_height
            and not self._editing_offset_x
            and not self._editing_offset_y
            and not self._editing_meta_key
            and not self._editing_meta_value
            and not self.preview.is_fps_input_active()
            and not self.frame_picker.is_filter_input_active()
        ):
            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
            shift_held = mods & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT)

            # Ctrl+S: Quick save
            if ctrl_held and event.key == pygame.K_s and not shift_held:
                self._quick_save()
                return True

            # Ctrl+Shift+S: Save as
            elif ctrl_held and shift_held and event.key == pygame.K_s:
                self._save_dialog()
                return True

            # Ctrl+O: Open/Load
            elif ctrl_held and event.key == pygame.K_o:
                self._load_dialog()
                return True

            elif ctrl_held and shift_held and event.key == pygame.K_c:
                self._copy_active_clip_json()
                return True

            # F2: Rename active animation
            elif event.key == pygame.K_F2:
                self._start_rename()
                return True

        # Close dropdown on outside click
        if event.type == pygame.MOUSEBUTTONDOWN and self._dropdown_open:
            mouse = pygame.mouse.get_pos()
            if not self._dropdown_rect.collidepoint(mouse):
                self._dropdown_open = False

        # Renaming text input
        if self._renaming:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._commit_rename()
                    return True
                elif event.key == pygame.K_ESCAPE:
                    self._renaming = False
                    self._rename_input.is_focused = False
                    return True
                elif self._rename_input.handle_event(event, self._font):
                    return True

        # Frame width input
        elif self._editing_frame_width:
            if event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)

                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._apply_frame_size()
                    self._editing_frame_width = False
                    return True
                elif event.key == pygame.K_TAB:
                    self._apply_frame_size()
                    self._editing_frame_width = False
                    self._editing_frame_height = True
                    return True
                elif event.key == pygame.K_ESCAPE:
                    self._frame_width_input = str(self._tile_size[0])
                    self._editing_frame_width = False
                    return True
                elif event.key == pygame.K_BACKSPACE:
                    if ctrl_held:
                        # Ctrl+Backspace clears entire field
                        self._frame_width_input = ""
                    else:
                        self._frame_width_input = self._frame_width_input[:-1]
                    return True
                elif (
                    event.unicode
                    and event.unicode.isdigit()
                    and len(self._frame_width_input) < 5
                ):
                    # Smart zero handling: if input is "0" and user types non-zero, replace it
                    if self._frame_width_input == "0" and event.unicode != "0":
                        self._frame_width_input = event.unicode
                    else:
                        self._frame_width_input += event.unicode
                    return True

        # Frame height input
        elif self._editing_frame_height:
            if event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)

                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._apply_frame_size()
                    self._editing_frame_height = False
                    return True
                elif event.key == pygame.K_TAB:
                    self._apply_frame_size()
                    self._editing_frame_height = False
                    self._editing_offset_x = True
                    return True
                elif event.key == pygame.K_ESCAPE:
                    self._frame_height_input = str(self._tile_size[1])
                    self._editing_frame_height = False
                    return True
                elif event.key == pygame.K_BACKSPACE:
                    if ctrl_held:
                        self._frame_height_input = ""
                    else:
                        self._frame_height_input = self._frame_height_input[:-1]
                    return True
                elif (
                    event.unicode
                    and event.unicode.isdigit()
                    and len(self._frame_height_input) < 5
                ):
                    # Smart zero handling
                    if self._frame_height_input == "0" and event.unicode != "0":
                        self._frame_height_input = event.unicode
                    else:
                        self._frame_height_input += event.unicode
                    return True

        # Offset X input
        elif self._editing_offset_x:
            if event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)

                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._apply_grid_offset()
                    self._editing_offset_x = False
                    return True
                elif event.key == pygame.K_TAB:
                    self._apply_grid_offset()
                    self._editing_offset_x = False
                    self._editing_offset_y = True
                    return True
                elif event.key == pygame.K_ESCAPE:
                    self._offset_x_input = str(self._grid_offset_x)
                    self._editing_offset_x = False
                    return True
                elif event.key == pygame.K_BACKSPACE:
                    if ctrl_held:
                        self._offset_x_input = ""
                    else:
                        self._offset_x_input = self._offset_x_input[:-1]
                    return True
                elif (
                    event.unicode
                    and (
                        event.unicode.isdigit()
                        or (event.unicode == "-" and len(self._offset_x_input) == 0)
                    )
                    and len(self._offset_x_input) < 5
                ):
                    # Smart zero handling for offset (can be negative)
                    if (
                        self._offset_x_input == "0"
                        and event.unicode != "0"
                        and event.unicode != "-"
                    ):
                        self._offset_x_input = event.unicode
                    else:
                        self._offset_x_input += event.unicode
                    return True

        # Offset Y input
        elif self._editing_offset_y:
            if event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)

                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self._apply_grid_offset()
                    self._editing_offset_y = False
                    return True
                elif event.key == pygame.K_TAB:
                    self._apply_grid_offset()
                    self._editing_offset_y = False
                    # Cycle back to frame width
                    self._editing_frame_width = True
                    return True
                elif event.key == pygame.K_ESCAPE:
                    self._offset_y_input = str(self._grid_offset_y)
                    self._editing_offset_y = False
                    return True
                elif event.key == pygame.K_BACKSPACE:
                    if ctrl_held:
                        self._offset_y_input = ""
                    else:
                        self._offset_y_input = self._offset_y_input[:-1]
                    return True
                elif (
                    event.unicode
                    and (
                        event.unicode.isdigit()
                        or (event.unicode == "-" and len(self._offset_y_input) == 0)
                    )
                    and len(self._offset_y_input) < 5
                ):
                    # Smart zero handling for offset
                    if (
                        self._offset_y_input == "0"
                        and event.unicode != "0"
                        and event.unicode != "-"
                    ):
                        self._offset_y_input = event.unicode
                    else:
                        self._offset_y_input += event.unicode
                    return True

        # Toolbar clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse = pygame.mouse.get_pos()

            # Animation selector dropdown
            if self._btn_anim_selector.collidepoint(mouse):
                self._dropdown_open = not self._dropdown_open
                return True

            # Rename button
            if self._btn_rename.collidepoint(mouse):
                self._start_rename()
                return True

            # Dropdown item selection
            if self._dropdown_open:
                for i, item_rect in enumerate(self._dropdown_items_rects):
                    if item_rect.collidepoint(mouse):
                        names = self.library.animation_names()
                        if i < len(names):
                            self._active_anim_name = names[i]
                            self._sync_active_animation()
                        self._dropdown_open = False
                        return True

            # New animation
            if self._btn_new.collidepoint(mouse):
                base = "anim"
                n = len(self.library.animations)
                name = f"{base}_{n}"
                while name in self.library.animations:
                    n += 1
                    name = f"{base}_{n}"
                self._create_new_animation(name)
                return True

            # Delete animation
            if self._btn_del.collidepoint(mouse):
                self._delete_active_animation()
                return True

            # Save
            if self._btn_save.collidepoint(mouse):
                self._save_dialog()
                return True

            # Load
            if self._btn_load.collidepoint(mouse):
                self._load_dialog()
                return True

            # Load Spritesheet
            if self._btn_load_spritesheet.collidepoint(mouse):
                self._load_spritesheet_dialog()
                return True

            if self._btn_dup.collidepoint(mouse):
                self._duplicate_active_animation()
                return True
            if self._btn_mk.collidepoint(mouse):
                self._add_marker_at_selection()
                return True
            if self._btn_copyjson.collidepoint(mouse):
                self._copy_active_clip_json()
                return True

            # Metadata panel toggle
            if self._btn_meta.collidepoint(mouse):
                self._meta_panel_open = not self._meta_panel_open
                self._editing_meta_key = False
                self._editing_meta_value = False
                return True

            # Spritesheet / clip info (toggle pinned card; hover still works)
            if self._btn_info.collidepoint(mouse):
                self._info_tooltip_pinned = not self._info_tooltip_pinned
                return True

            # Frame width input
            if self._btn_frame_width.collidepoint(mouse):
                self._editing_frame_width = True
                self._editing_frame_height = False
                self._editing_offset_x = False
                self._editing_offset_y = False
                self._renaming = False
                return True

            # Frame height input
            if self._btn_frame_height.collidepoint(mouse):
                self._editing_frame_height = True
                self._editing_frame_width = False
                self._editing_offset_x = False
                self._editing_offset_y = False
                self._renaming = False
                return True

            # Offset X input
            if self._btn_offset_x.collidepoint(mouse):
                self._editing_offset_x = True
                self._editing_offset_y = False
                self._editing_frame_width = False
                self._editing_frame_height = False
                self._renaming = False
                return True

            # Offset Y input
            if self._btn_offset_y.collidepoint(mouse):
                self._editing_offset_y = True
                self._editing_offset_x = False
                self._editing_frame_width = False
                self._editing_frame_height = False
                self._renaming = False
                return True

        # Double-click on animation selector area -> rename (secondary method)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse = pygame.mouse.get_pos()
            if self._btn_anim_selector.collidepoint(mouse):
                # Check for double-click
                if hasattr(self, "_last_click_time"):
                    now = pygame.time.get_ticks()
                    if now - self._last_click_time < 350:
                        self._start_rename()
                        return True
                self._last_click_time = pygame.time.get_ticks()

        # Sub-widgets (order matters for event priority)
        if self.preview.handle_event(event):
            return True
        if self.timeline.handle_event(event):
            return True
        if self.frame_picker.handle_event(event):
            return True

        return False

    def draw(self, screen: pygame.Surface) -> None:
        """Draw the full editor panel."""
        if not self.visible:
            return

        self._refresh_clip_warnings()

        # Toolbar
        self._draw_toolbar(screen)

        # Sub-widgets
        self.preview.draw(screen)
        self.frame_picker.draw(screen)
        self.timeline.draw(screen)

        if self._meta_panel_open:
            self._draw_meta_panel(screen)

        if self._show_info_tooltip:
            self._draw_info_tooltip(screen)

        # Dropdown overlay (drawn last, on top)
        if self._dropdown_open:
            self._draw_dropdown(screen)

        # File manager overlay (drawn on top of everything)
        if self._file_manager:
            self._file_manager.draw(screen)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _layout_rects(self) -> Tuple[Rect, Rect, Rect]:
        """Calculate rects for frame_picker, preview, timeline."""
        x, y, w, h = self.rect.x, self.rect.y, self.rect.w, self.rect.h

        # Preview: top-left
        pv_rect = Rect(x, y + TOOLBAR_H, PREVIEW_W, h - TOOLBAR_H - TIMELINE_H)

        # Frame picker: top-right (fills remaining width)
        fp_rect = Rect(
            x + PREVIEW_W, y + TOOLBAR_H, w - PREVIEW_W, h - TOOLBAR_H - TIMELINE_H
        )

        # Timeline: bottom full width
        tl_rect = Rect(x, y + h - TIMELINE_H, w, TIMELINE_H)

        return fp_rect, pv_rect, tl_rect

    def _relayout(self) -> None:
        fp_rect, pv_rect, tl_rect = self._layout_rects()
        self.frame_picker.resize(fp_rect)
        self.preview.resize(pv_rect)
        self.timeline.resize(tl_rect)

    # ------------------------------------------------------------------
    # Toolbar drawing
    # ------------------------------------------------------------------

    def _draw_toolbar(self, screen: pygame.Surface) -> None:
        mouse = pygame.mouse.get_pos()
        tb = Rect(self.rect.x, self.rect.y, self.rect.w, TOOLBAR_ROW1_H)
        pygame.draw.rect(screen, _COLORS["toolbar"], tb)
        pygame.draw.line(
            screen,
            _COLORS["toolbar_border"],
            (tb.x, tb.bottom - 1),
            (tb.right, tb.bottom - 1),
        )

        bh = 26
        pad = 6
        x = tb.x + pad
        cy = tb.y + (TOOLBAR_ROW1_H - bh) // 2

        # Animation selector
        sel_w = 140
        self._btn_anim_selector = Rect(x, cy, sel_w, bh)
        is_hover = self._btn_anim_selector.collidepoint(mouse)
        bg = _COLORS["btn_hover"] if is_hover else _COLORS["btn"]
        pygame.draw.rect(screen, bg, self._btn_anim_selector, border_radius=3)
        pygame.draw.rect(
            screen, _COLORS["border"], self._btn_anim_selector, 1, border_radius=3
        )

        if self._renaming:
            if self._renaming:
                display_name = self._rename_input.text
                cursor_offset = self._rename_input.cursor_pos

                # Draw selection highlight
                if self._rename_input.selection_start is not None:
                    start = min(self._rename_input.selection_start, cursor_offset)
                    end = max(self._rename_input.selection_start, cursor_offset)
                    if start != end:
                        prefix = display_name[:start]
                        selected = display_name[start:end]
                        prefix_w = self._font.size(prefix)[0]
                        select_w = self._font.size(selected)[0]
                        sel_rect = Rect(
                            self._btn_anim_selector.x + 4 + prefix_w,
                            self._btn_anim_selector.y + 5,
                            select_w,
                            self._btn_anim_selector.height - 10,
                        )
                        pygame.draw.rect(screen, (60, 100, 160), sel_rect)

                # Blinking cursor
                if (pygame.time.get_ticks() // 400) % 2:
                    display_name = display_name[:cursor_offset] + "|" + display_name[cursor_offset:]

                lbl = self._font.render(display_name, True, (255, 220, 100))
        else:
            display_name = self._active_anim_name or "(none)"
            if len(display_name) > 16:
                display_name = display_name[:14] + ".."
            lbl = self._font.render(f"  {display_name}", True, _COLORS["text"])
            # Dropdown arrow icon
            arrow_icon = icon_manager.get_icon("arrow-down", 10, _COLORS["text"])
            screen.blit(
                arrow_icon,
                (self._btn_anim_selector.right - 16, self._btn_anim_selector.y + 8),
            )
        screen.blit(lbl, (self._btn_anim_selector.x + 4, self._btn_anim_selector.y + 5))
        x += sel_w + pad

        # [✏️ Rename] button
        rename_btn_w = 24
        self._btn_rename = Rect(x, cy, rename_btn_w, bh)
        rename_hover = self._btn_rename.collidepoint(mouse)
        rename_bg = _COLORS["btn_hover"] if rename_hover else _COLORS["btn"]
        pygame.draw.rect(screen, rename_bg, self._btn_rename, border_radius=3)
        pygame.draw.rect(
            screen, _COLORS["border"], self._btn_rename, 1, border_radius=3
        )
        # Pencil icon for rename
        pencil_icon = icon_manager.get_icon("pencil", 14, _COLORS["text"])
        screen.blit(pencil_icon, (self._btn_rename.x + 5, self._btn_rename.y + 6))
        x += rename_btn_w + pad

        # [+ New]
        self._btn_new = Rect(x, cy, 28, bh)
        self._draw_toolbar_btn(screen, self._btn_new, "+", mouse)
        x += 32

        # Delete
        self._btn_del = Rect(x, cy, 28, bh)
        # Close/X icon for delete
        close_icon = icon_manager.get_icon("close", 14, _COLORS["btn_danger_hover"])
        screen.blit(close_icon, (self._btn_del.x + 7, self._btn_del.y + 6))
        x += 36

        # Separator
        pygame.draw.line(
            screen, _COLORS["toolbar_border"], (x, cy + 2), (x, cy + bh - 2)
        )
        x += pad + 4

        # [Save]
        self._btn_save = Rect(x, cy, 48, bh)
        self._draw_toolbar_btn(screen, self._btn_save, "Save", mouse)
        x += 52

        # [Load]
        self._btn_load = Rect(x, cy, 48, bh)
        self._draw_toolbar_btn(screen, self._btn_load, "Load", mouse)
        x += 52

        # [Load Spritesheet]
        self._btn_load_spritesheet = Rect(x, cy, 80, bh)
        self._draw_toolbar_btn(screen, self._btn_load_spritesheet, "Sheet", mouse)
        x += 84

        # Separator
        pygame.draw.line(
            screen, _COLORS["toolbar_border"], (x, cy + 2), (x, cy + bh - 2)
        )
        x += pad + 4

        # Metadata
        self._btn_meta = Rect(x, cy, 36, bh)
        self._draw_toolbar_btn(
            screen,
            self._btn_meta,
            "{ }",
            mouse,
            active=self._meta_panel_open,
        )
        x += 40

        # Separator
        pygame.draw.line(
            screen, _COLORS["toolbar_border"], (x, cy + 2), (x, cy + bh - 2)
        )
        x += pad + 4

        # Frame size label
        size_label = self._font_sm.render("Frame:", True, _COLORS["text_dim"])
        screen.blit(size_label, (x, cy + 7))
        x += size_label.get_width() + 4

        # Width input
        input_w = 42
        self._btn_frame_width = Rect(x, cy, input_w, bh)
        width_bg = (
            _COLORS["input_bg"]
            if not self._editing_frame_width
            else _COLORS["btn_active"]
        )
        pygame.draw.rect(screen, width_bg, self._btn_frame_width, border_radius=3)
        pygame.draw.rect(
            screen, _COLORS["border"], self._btn_frame_width, 1, border_radius=3
        )

        width_text = self._frame_width_input
        if self._editing_frame_width and (pygame.time.get_ticks() // 400) % 2:
            width_text += "|"
        width_surf = self._font_sm.render(width_text, True, _COLORS["text"])
        screen.blit(
            width_surf, (self._btn_frame_width.x + 4, self._btn_frame_width.y + 6)
        )
        x += input_w + 2

        # x separator
        # Multiplication sign as icon
        x_icon = icon_manager.get_icon("close", 10, _COLORS["text_dim"])
        screen.blit(x_icon, (x, cy + 5))
        x += 12

        # Height input
        self._btn_frame_height = Rect(x, cy, input_w, bh)
        height_bg = (
            _COLORS["input_bg"]
            if not self._editing_frame_height
            else _COLORS["btn_active"]
        )
        pygame.draw.rect(screen, height_bg, self._btn_frame_height, border_radius=3)
        pygame.draw.rect(
            screen, _COLORS["border"], self._btn_frame_height, 1, border_radius=3
        )

        height_text = self._frame_height_input
        if self._editing_frame_height and (pygame.time.get_ticks() // 400) % 2:
            height_text += "|"
        height_surf = self._font_sm.render(height_text, True, _COLORS["text"])
        screen.blit(
            height_surf, (self._btn_frame_height.x + 4, self._btn_frame_height.y + 6)
        )
        x += input_w + 4

        # px label
        px_label = self._font_sm.render("px", True, _COLORS["text_dim"])
        screen.blit(px_label, (x, cy + 7))
        x += px_label.get_width() + 4

        # Info icon button
        self._btn_info = Rect(x, cy + 2, 20, 20)
        info_hover = self._btn_info.collidepoint(mouse)
        info_bg = _COLORS["btn_hover"] if info_hover else _COLORS["toolbar"]
        pygame.draw.circle(screen, info_bg, self._btn_info.center, 10)
        ring = _COLORS["accent"] if self._info_tooltip_pinned else _COLORS["border"]
        pygame.draw.circle(screen, ring, self._btn_info.center, 10, 1)

        # Draw "i" icon
        info_text = self._font_bold.render("i", True, _COLORS["text"])
        info_text_rect = info_text.get_rect(center=self._btn_info.center)
        screen.blit(info_text, info_text_rect)

        self._show_info_tooltip = info_hover or self._info_tooltip_pinned

        x += 28

        # Separator
        pygame.draw.line(
            screen, _COLORS["toolbar_border"], (x, cy + 2), (x, cy + bh - 2)
        )
        x += pad + 4

        # Offset label
        offset_label = self._font_sm.render("Offset:", True, _COLORS["text_dim"])
        screen.blit(offset_label, (x, cy + 7))
        x += offset_label.get_width() + 4

        # Offset X input
        offset_input_w = 38
        self._btn_offset_x = Rect(x, cy, offset_input_w, bh)
        offset_x_bg = (
            _COLORS["input_bg"] if not self._editing_offset_x else _COLORS["btn_active"]
        )
        pygame.draw.rect(screen, offset_x_bg, self._btn_offset_x, border_radius=3)
        pygame.draw.rect(
            screen, _COLORS["border"], self._btn_offset_x, 1, border_radius=3
        )

        offset_x_text = self._offset_x_input
        if self._editing_offset_x and (pygame.time.get_ticks() // 400) % 2:
            offset_x_text += "|"
        offset_x_surf = self._font_sm.render(offset_x_text, True, _COLORS["text"])
        screen.blit(offset_x_surf, (self._btn_offset_x.x + 4, self._btn_offset_x.y + 6))
        x += offset_input_w + 2

        # comma separator
        comma_label = self._font_sm.render(",", True, _COLORS["text_dim"])
        screen.blit(comma_label, (x, cy + 6))
        x += comma_label.get_width() + 2

        # Offset Y input
        self._btn_offset_y = Rect(x, cy, offset_input_w, bh)
        offset_y_bg = (
            _COLORS["input_bg"] if not self._editing_offset_y else _COLORS["btn_active"]
        )
        pygame.draw.rect(screen, offset_y_bg, self._btn_offset_y, border_radius=3)
        pygame.draw.rect(
            screen, _COLORS["border"], self._btn_offset_y, 1, border_radius=3
        )

        offset_y_text = self._offset_y_input
        if self._editing_offset_y and (pygame.time.get_ticks() // 400) % 2:
            offset_y_text += "|"
        offset_y_surf = self._font_sm.render(offset_y_text, True, _COLORS["text"])
        screen.blit(offset_y_surf, (self._btn_offset_y.x + 4, self._btn_offset_y.y + 6))
        x += offset_input_w + 4

        # Right-aligned info
        info = f"{self._sheet_name}"
        info_surf = self._font_sm.render(info, True, _COLORS["text_dim"])
        screen.blit(info_surf, (tb.right - info_surf.get_width() - 8, cy + 6))

        tb2 = Rect(
            self.rect.x, self.rect.y + TOOLBAR_ROW1_H, self.rect.w, TOOLBAR_ROW2_H
        )
        pygame.draw.rect(screen, _COLORS["toolbar"], tb2)
        pygame.draw.line(
            screen,
            _COLORS["toolbar_border"],
            (tb2.x, tb2.bottom - 1),
            (tb2.right, tb2.bottom - 1),
        )
        bh2 = 22
        cy2 = tb2.y + (TOOLBAR_ROW2_H - bh2) // 2
        x2 = tb2.x + 6
        # Duplicate button (icon)
        self._btn_dup = Rect(x2, cy2, 24, bh2)
        self._draw_toolbar_btn(screen, self._btn_dup, "", mouse)
        dup_icon = icon_manager.get_icon("duplicate", 12, _COLORS["text"])
        screen.blit(dup_icon, dup_icon.get_rect(center=self._btn_dup.center))
        x2 += 28

        # Marker button (icon - using radio as marker symbol)
        self._btn_mk = Rect(x2, cy2, 24, bh2)
        self._draw_toolbar_btn(screen, self._btn_mk, "", mouse)
        marker_icon = icon_manager.get_icon("radio", 12, _COLORS["text"])
        screen.blit(marker_icon, marker_icon.get_rect(center=self._btn_mk.center))
        x2 += 28

        # Copy JSON button (icon - using file symbol)
        self._btn_copyjson = Rect(x2, cy2, 24, bh2)
        self._draw_toolbar_btn(screen, self._btn_copyjson, "", mouse)
        json_icon = icon_manager.get_icon("file", 12, _COLORS["text"])
        screen.blit(json_icon, json_icon.get_rect(center=self._btn_copyjson.center))
        x2 += 28
        if self._clip_warnings:
            # Warning icon
            warning_icon = icon_manager.get_icon(
                "warning", 12, _COLORS["btn_danger_hover"]
            )
            screen.blit(warning_icon, (x2, cy2 + 4))
            wtxt = f"{len(self._clip_warnings)} clip issue(s)"
            screen.blit(
                self._font_sm.render(wtxt, True, _COLORS["btn_danger_hover"]),
                (x2 + 14, cy2 + 4),
            )
        else:
            screen.blit(
                self._font_sm.render("Clip checks OK", True, _COLORS["text_dim"]),
                (x2, cy2 + 4),
            )
        hint = self._font_sm.render(
            "F2 rename  ·  Ctrl+Shift+C copy JSON", True, _COLORS["text_dim"]
        )
        screen.blit(hint, (tb2.right - hint.get_width() - 8, cy2 + 4))

    def _draw_toolbar_btn(self, screen, rect, label, mouse, danger=False, active=False):
        hover = rect.collidepoint(mouse)
        if danger:
            bg = _COLORS["btn_danger_hover"] if hover else _COLORS["btn_danger"]
        elif active:
            bg = _COLORS["btn_active"]
        elif hover:
            bg = _COLORS["btn_hover"]
        else:
            bg = _COLORS["btn"]
        pygame.draw.rect(screen, bg, rect, border_radius=3)
        pygame.draw.rect(screen, _COLORS["border"], rect, 1, border_radius=3)
        lbl = self._font_sm.render(label, True, _COLORS["text"])
        screen.blit(lbl, lbl.get_rect(center=rect.center))

    def _draw_info_tooltip(self, screen: pygame.Surface) -> None:
        """Draw card with spritesheet grid info and current clip summary."""
        sheet_w, sheet_h = self._surface.get_size()
        frame_w, frame_h = self._tile_size
        cols = self.frame_picker.cols
        rows = self.frame_picker.rows
        total_frames = self.frame_picker.total_frames
        offset_x, offset_y = self._grid_offset_x, self._grid_offset_y

        lines: List[str] = [
            "Spritesheet",
            f"  Size: {sheet_w} × {sheet_h} px",
            f"  File: {self._sheet_name}",
        ]
        if self.library.spritesheet_path:
            sp = self.library.spritesheet_path
            if len(sp) > 46:
                sp = sp[:44] + "…"
            lines.append(f"  Path: {sp}")
        lines.extend(
            [
                f"  Cell: {frame_w} × {frame_h} px",
                f"  Grid: {cols}×{rows} ({total_frames} tiles)",
                f"  Origin offset: {offset_x}, {offset_y}",
            ]
        )

        anim = self._get_active()
        if anim:
            lines.append("Current animation")
            lines.append(f"  Name: {anim.name}")
            lines.append(f"  Clip frames: {anim.frame_count()}  ·  loop: {anim.loop}")
            lines.append(f"  FPS: {anim.fps:g}")
            n_meta = len(anim.metadata)
            lines.append(f"  Metadata keys: {n_meta}")
            if n_meta:
                keys = sorted(anim.metadata.keys(), key=str.lower)[:5]
                lines.append(f"  Keys: {', '.join(keys)}{'…' if n_meta > 5 else ''}")
            if anim.markers:
                lines.append(f"  Markers ({len(anim.markers)}):")
                for m in sorted(anim.markers, key=lambda x: (x.frame_index, x.name))[
                    :10
                ]:
                    lines.append(f"    · {m.name} → cel {m.frame_index + 1}")
                if len(anim.markers) > 10:
                    lines.append("    …")
        if self._clip_warnings:
            lines.append("Clip checks")
            for w in self._clip_warnings[:14]:
                lines.append(f"  • {w}")
            if len(self._clip_warnings) > 14:
                lines.append(f"  … +{len(self._clip_warnings) - 14} more")
        if self._info_tooltip_pinned:
            lines.append("Esc or click outside card to close")
        else:
            lines.append("Click info to pin this panel")

        padding = 8
        line_height = 16
        max_width = max(
            self._font_sm.render(line, True, _COLORS["text"]).get_width()
            for line in lines
        )
        tooltip_w = max(220, max_width + padding * 2)
        tooltip_h = len(lines) * line_height + padding * 2

        tooltip_x = self._btn_info.centerx - tooltip_w // 2
        tooltip_y = self._btn_info.bottom + 4
        tooltip_x = max(
            self.rect.x + 6, min(tooltip_x, self.rect.right - tooltip_w - 6)
        )
        if tooltip_y + tooltip_h > self.rect.bottom - 6:
            tooltip_y = max(self.rect.y + 6, self._btn_info.top - tooltip_h - 4)

        tooltip_rect = Rect(tooltip_x, tooltip_y, tooltip_w, tooltip_h)
        self._info_tooltip_screen_rect = tooltip_rect

        # Draw tooltip background with shadow
        shadow_rect = tooltip_rect.copy()
        shadow_rect.x += 2
        shadow_rect.y += 2
        shadow_surf = pygame.Surface((shadow_rect.w, shadow_rect.h), pygame.SRCALPHA)
        shadow_surf.fill((0, 0, 0, 100))
        screen.blit(shadow_surf, shadow_rect.topleft)

        # Draw tooltip
        pygame.draw.rect(screen, _COLORS["dropdown_bg"], tooltip_rect, border_radius=4)
        pygame.draw.rect(screen, _COLORS["border"], tooltip_rect, 1, border_radius=4)

        # Draw text lines
        y = tooltip_rect.y + padding
        for line in lines:
            text_surf = self._font_sm.render(line, True, _COLORS["text"])
            screen.blit(text_surf, (tooltip_rect.x + padding, y))
            y += line_height

    def _draw_dropdown(self, screen: pygame.Surface) -> None:
        names = self.library.animation_names()
        if not names:
            return

        item_h = 26
        dd_w = self._btn_anim_selector.w
        dd_h = len(names) * item_h + 4
        dd_x = self._btn_anim_selector.x
        dd_y = self._btn_anim_selector.bottom + 2

        self._dropdown_rect = Rect(dd_x, dd_y, dd_w, dd_h)
        # Shadow
        shadow = pygame.Surface((dd_w + 4, dd_h + 4), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 80))
        screen.blit(shadow, (dd_x + 2, dd_y + 2))

        pygame.draw.rect(
            screen, _COLORS["dropdown_bg"], self._dropdown_rect, border_radius=4
        )
        pygame.draw.rect(
            screen, _COLORS["dropdown_border"], self._dropdown_rect, 1, border_radius=4
        )

        mouse = pygame.mouse.get_pos()
        self._dropdown_items_rects = []
        for i, name in enumerate(names):
            item_rect = Rect(dd_x + 2, dd_y + 2 + i * item_h, dd_w - 4, item_h)
            self._dropdown_items_rects.append(item_rect)

            is_active = name == self._active_anim_name
            is_hover = item_rect.collidepoint(mouse)
            if is_active:
                pygame.draw.rect(
                    screen, _COLORS["btn_active"], item_rect, border_radius=3
                )
            elif is_hover:
                pygame.draw.rect(
                    screen, _COLORS["dropdown_hover"], item_rect, border_radius=3
                )

            display = name if len(name) < 18 else name[:16] + ".."
            color = _COLORS["accent"] if is_active else _COLORS["text"]
            lbl = self._font.render(display, True, color)
            screen.blit(lbl, (item_rect.x + 8, item_rect.y + 4))

            # Frame count badge
            anim = self.library.get_animation(name)
            if anim:
                badge = self._font_sm.render(
                    f"{anim.frame_count()}f", True, _COLORS["text_dim"]
                )
                screen.blit(
                    badge, (item_rect.right - badge.get_width() - 6, item_rect.y + 6)
                )

    # ------------------------------------------------------------------
    # Animation management
    # ------------------------------------------------------------------

    def _create_new_animation(self, name: str) -> None:
        anim = Animation(name=name)
        self.library.add_animation(anim)
        self._active_anim_name = name
        self._sync_active_animation()

    def _delete_active_animation(self) -> None:
        if self._active_anim_name and self._active_anim_name in self.library.animations:
            if self.consumer:
                self.consumer.on_animation_deleted(self._active_anim_name)
            self.library.remove_animation(self._active_anim_name)
            names = self.library.animation_names()
            self._active_anim_name = names[0] if names else None
            if not self._active_anim_name:
                self._create_new_animation("idle")
            self._sync_active_animation()

    def _start_rename(self) -> None:
        if self._active_anim_name:
            self._renaming = True
            self._rename_input.text = self._active_anim_name
            self._rename_input.cursor_pos = len(self._active_anim_name)
            self._rename_input.selection_start = None
            self._rename_input.is_focused = True
            self._editing_frame_width = False
            self._editing_frame_height = False
            self._editing_offset_x = False
            self._editing_offset_y = False
            self._dropdown_open = False

    def _commit_rename(self) -> None:
        new_name = self._rename_input.text.strip()
        if new_name and self._active_anim_name and new_name != self._active_anim_name:
            if self.library.rename_animation(self._active_anim_name, new_name):
                self._active_anim_name = new_name
        self._renaming = False
        self._rename_input.is_focused = False

    def _apply_frame_size(self) -> None:
        """Apply the frame size from input fields and update the frame picker."""
        try:
            width = (
                int(self._frame_width_input)
                if self._frame_width_input
                else self._tile_size[0]
            )
            height = (
                int(self._frame_height_input)
                if self._frame_height_input
                else self._tile_size[1]
            )

            # Clamp to reasonable values
            width = max(1, min(width, self._surface.get_width()))
            height = max(1, min(height, self._surface.get_height()))

            # Update tile size
            self._tile_size = (width, height)
            self.library.tile_size = (width, height)

            # Update frame picker
            self.frame_picker.set_surface(self._surface, self._tile_size)
            self._apply_grid_offset()  # Reapply offset with new tile size

            # Update preview and timeline
            self.preview.set_surface(self._surface, self._tile_size)
            self.timeline.surface = self._surface
            self.timeline.tile_size = self._tile_size
            self.timeline.invalidate_cache()

            # Update input fields to show clamped values
            self._frame_width_input = str(width)
            self._frame_height_input = str(height)

        except ValueError:
            # Reset to current values on invalid input
            self._frame_width_input = str(self._tile_size[0])
            self._frame_height_input = str(self._tile_size[1])

    def _apply_grid_offset(self) -> None:
        """Apply the grid offset from input fields and update the frame picker."""
        try:
            offset_x = int(self._offset_x_input) if self._offset_x_input else 0
            offset_y = int(self._offset_y_input) if self._offset_y_input else 0

            # Clamp to reasonable values (can be negative or positive)
            offset_x = max(
                -self._surface.get_width(), min(offset_x, self._surface.get_width())
            )
            offset_y = max(
                -self._surface.get_height(), min(offset_y, self._surface.get_height())
            )

            # Update grid offset
            self._grid_offset_x = offset_x
            self._grid_offset_y = offset_y

            # Update frame picker with offset
            if hasattr(self.frame_picker, "set_grid_offset"):
                self.frame_picker.set_grid_offset(offset_x, offset_y)

            # Update timeline with offset
            if hasattr(self.timeline, "grid_offset_x"):
                self.timeline.grid_offset_x = offset_x
                self.timeline.grid_offset_y = offset_y
                self.timeline.invalidate_cache()

            # Update preview with offset (if it has the attribute)
            if hasattr(self.preview, "grid_offset_x"):
                self.preview.grid_offset_x = offset_x  # type: ignore
                self.preview.grid_offset_y = offset_y  # type: ignore

            # Update input fields to show clamped values
            self._offset_x_input = str(offset_x)
            self._offset_y_input = str(offset_y)

        except ValueError:
            # Reset to current values on invalid input
            self._offset_x_input = str(self._grid_offset_x)
            self._offset_y_input = str(self._grid_offset_y)

    def _apply_library_grid_settings(self) -> None:
        """Sync tile_size and grid_offset from the loaded library to all widgets."""
        tw, th = self.library.tile_size
        self._tile_size = (tw, th)
        self.library.tile_size = (tw, th)

        # Update frame picker
        self.frame_picker.set_surface(self._surface, self._tile_size)

        # Update preview and timeline
        self.preview.set_surface(self._surface, self._tile_size)
        self.timeline.surface = self._surface
        self.timeline.tile_size = self._tile_size
        self.timeline.invalidate_cache()

        # Update frame size input fields
        self._frame_width_input = str(tw)
        self._frame_height_input = str(th)

        # Sync grid offset from library
        gx, gy = self.library.grid_offset
        self._grid_offset_x = gx
        self._grid_offset_y = gy
        self._offset_x_input = str(gx)
        self._offset_y_input = str(gy)

        # Propagate offset to all widgets
        if hasattr(self.frame_picker, "set_grid_offset"):
            self.frame_picker.set_grid_offset(gx, gy)
        if hasattr(self.timeline, "grid_offset_x"):
            self.timeline.grid_offset_x = gx
            self.timeline.grid_offset_y = gy
            self.timeline.invalidate_cache()
        if hasattr(self.preview, "grid_offset_x"):
            self.preview.grid_offset_x = gx
            self.preview.grid_offset_y = gy

    def _sync_active_animation(self) -> None:
        """Push current animation data to sub-widgets."""
        anim = self._get_active()
        if anim:
            self.timeline.set_frames(anim.frames)
            self.timeline.set_markers(anim.markers)
            self.preview.set_frames(anim.frames)
            self.preview.loop = anim.loop
            self.preview.playback_fps = float(anim.fps)
            self.preview.authoring_fps = float(anim.fps)
            self.preview.sync_playback_fps_field()
            # Highlight used frames in frame picker
            used = {f.variant_id for f in anim.frames}
            self.frame_picker.set_highlighted(used)
        else:
            self.timeline.set_frames([])
            self.timeline.set_markers([])
            self.preview.set_frames([])
            self.frame_picker.set_highlighted(set())
        self._meta_key_input = ""
        self._meta_value_input = ""
        self._editing_meta_key = False
        self._editing_meta_value = False
        self._meta_scroll = 0
        self._apply_timeline_focus_to_sheet(scroll=False)

    def _apply_timeline_focus_to_sheet(self, scroll: bool) -> None:
        """Show which spritesheet cel matches the selected timeline frame."""
        anim = self._get_active()
        si = self.timeline.selected_index
        if anim is None or si < 0 or si >= len(anim.frames):
            self.frame_picker.set_focus_variant(-1)
            return
        vid = anim.frames[si].variant_id
        self.frame_picker.set_focus_variant(vid)
        if scroll:
            self.frame_picker.scroll_variant_into_view(vid)

    def _notify_animation_modified(self) -> None:
        if self.consumer:
            anim = self._get_active()
            if anim:
                self.consumer.on_animation_saved(anim.name, anim.to_dict())

    def _refresh_clip_warnings(self) -> None:
        anim = self._get_active()
        if not anim:
            self._clip_warnings = []
            return
        max_v = max(0, self.frame_picker.total_frames - 1)
        self._clip_warnings = collect_clip_warnings(anim, max_v)

    def _duplicate_active_animation(self) -> None:
        anim = self._get_active()
        if anim is None:
            return
        base = anim.name + "_copy"
        name = base
        n = 0
        while name in self.library.animations:
            n += 1
            name = f"{base}_{n}"
        self.library.add_animation(anim.copy_as_new_name(name))
        self._active_anim_name = name
        self._sync_active_animation()
        self._notify_animation_modified()

    def _add_marker_at_selection(self) -> None:
        anim = self._get_active()
        if anim is None or not anim.frames:
            return
        si = self.timeline.selected_index
        if si < 0:
            si = 0
        si = min(si, len(anim.frames) - 1)
        prefix = "marker"
        k = len(anim.markers)
        name = f"{prefix}_{k}"
        existing = {m.name for m in anim.markers}
        while name in existing:
            k += 1
            name = f"{prefix}_{k}"
        anim.markers.append(AnimationMarker(name, si))
        anim.clamp_markers()
        self._notify_animation_modified()

    def _copy_active_clip_json(self) -> None:
        anim = self._get_active()
        if anim is None:
            return
        payload = json.dumps(anim.to_dict(), indent=2)
        if copy_plain_text(payload):
            print("Copied current animation JSON to clipboard.")
        else:
            print("Clipboard unavailable; JSON printed below:\n", payload[:2000])

    def _on_markers_changed(self) -> None:
        anim = self._get_active()
        if anim:
            anim.clamp_markers()
            self._notify_animation_modified()

    def _on_preview_fps_changed(self, fps: float) -> None:
        anim = self._get_active()
        if anim:
            anim.fps = float(fps)
            self.preview.authoring_fps = float(fps)
            self._notify_animation_modified()

    def _metadata_apply_add(self, anim: Animation) -> None:
        key = self._meta_key_input.strip()
        if not key:
            return
        anim.metadata[key] = _parse_metadata_value(self._meta_value_input)
        self._notify_animation_modified()

    def _route_meta_panel_event(self, event: pygame.event.Event) -> bool:
        """True if the metadata panel consumed the event (it overlays the sheet view)."""
        anim = self._get_active()
        if anim is None:
            return False

        if event.type == pygame.KEYDOWN:
            if self._editing_meta_key:
                return self._handle_meta_key_keydown(event)
            if self._editing_meta_value:
                return self._handle_meta_value_keydown(event)
            return False

        mouse = pygame.mouse.get_pos()
        if not self._meta_panel_rect.collidepoint(mouse):
            return False

        if event.type == pygame.MOUSEWHEEL:
            self._meta_scroll = max(0, self._meta_scroll - event.y)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            return self._handle_meta_panel_mouse_down(anim, mouse)

        return False

    def _handle_meta_panel_mouse_down(
        self, anim: Animation, mouse: Tuple[int, int]
    ) -> bool:
        for i, del_rect in enumerate(self._meta_delete_btn_rects):
            if del_rect.collidepoint(mouse):
                keys = sorted(anim.metadata.keys())
                idx = self._meta_scroll + i
                if 0 <= idx < len(keys):
                    del anim.metadata[keys[idx]]
                    self._notify_animation_modified()
                return True

        for key, _val, pick_rect in self._meta_row_pick_rects:
            if pick_rect.collidepoint(mouse):
                self._meta_key_input = key
                self._meta_value_input = _metadata_value_repr(anim.metadata[key])
                self._editing_meta_value = True
                self._editing_meta_key = False
                return True

        if self._btn_meta_add.collidepoint(mouse):
            self._metadata_apply_add(anim)
            return True
        if self._btn_meta_key.collidepoint(mouse):
            self._clear_text_editing_focus()
            self._editing_meta_key = True
            self._editing_meta_value = False
            return True
        if self._btn_meta_value.collidepoint(mouse):
            self._clear_text_editing_focus()
            self._editing_meta_value = True
            self._editing_meta_key = False
            return True

        return True

    def _clear_text_editing_focus(self) -> None:
        self._renaming = False
        self._editing_frame_width = False
        self._editing_frame_height = False
        self._editing_offset_x = False
        self._editing_offset_y = False
        self._editing_meta_key = False
        self._editing_meta_value = False

    def _handle_meta_key_keydown(self, event: pygame.event.Event) -> bool:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
            self._editing_meta_key = False
            self._editing_meta_value = True
            return True
        if event.key == pygame.K_ESCAPE:
            self._editing_meta_key = False
            return True
        if event.key == pygame.K_BACKSPACE:
            self._meta_key_input = self._meta_key_input[:-1]
            return True
        if event.unicode and len(self._meta_key_input) < 48:
            ch = event.unicode
            if ch.isalnum() or ch in ("_", "-", ".", " "):
                self._meta_key_input += ch
            return True
        return True

    def _handle_meta_value_keydown(self, event: pygame.event.Event) -> bool:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            anim = self._get_active()
            if anim:
                self._metadata_apply_add(anim)
            self._editing_meta_value = False
            return True
        if event.key == pygame.K_TAB:
            self._editing_meta_value = False
            self._editing_meta_key = True
            return True
        if event.key == pygame.K_ESCAPE:
            self._editing_meta_value = False
            return True
        if event.key == pygame.K_BACKSPACE:
            self._meta_value_input = self._meta_value_input[:-1]
            return True
        if event.unicode and len(self._meta_value_input) < 240:
            self._meta_value_input += event.unicode
            return True
        return True

    def _draw_meta_panel(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()
        anim = self._get_active()
        if anim is None:
            return

        fp_rect, _, _ = self._layout_rects()
        panel = Rect(
            max(fp_rect.x + 6, fp_rect.right - META_PANEL_W - 8),
            fp_rect.y + 8,
            META_PANEL_W,
            META_PANEL_H,
        )
        self._meta_panel_rect = panel
        self._meta_delete_btn_rects = []
        self._meta_row_pick_rects = []

        items = sorted(anim.metadata.items(), key=lambda kv: kv[0].lower())
        visible_rows = 5
        max_scroll = max(0, len(items) - visible_rows)
        self._meta_scroll = max(0, min(self._meta_scroll, max_scroll))

        shadow = pygame.Surface((panel.w + 4, panel.h + 4), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 90))
        screen.blit(shadow, (panel.x + 2, panel.y + 2))
        pygame.draw.rect(screen, _COLORS["dropdown_bg"], panel, border_radius=6)
        pygame.draw.rect(screen, _COLORS["dropdown_border"], panel, 1, border_radius=6)

        title = self._font.render("Metadata", True, _COLORS["text"])
        screen.blit(title, (panel.x + 10, panel.y + 8))
        hint = self._font_sm.render(
            "(per animation · JSON-safe values)", True, _COLORS["text_dim"]
        )
        screen.blit(hint, (panel.x + 10, panel.y + 26))

        list_top = panel.y + 46
        list_h = visible_rows * META_ROW_H + 4
        list_rect = Rect(panel.x + 8, list_top, panel.w - 16, list_h)
        pygame.draw.rect(screen, _COLORS["input_bg"], list_rect, border_radius=4)
        pygame.draw.rect(screen, _COLORS["border"], list_rect, 1, border_radius=4)

        slice_items = items[self._meta_scroll : self._meta_scroll + visible_rows]
        row_y = list_rect.y + 2
        for key, val in slice_items:
            del_w = 22
            pick_w = list_rect.w - del_w - 6
            pick_rect = Rect(list_rect.x + 3, row_y, pick_w, META_ROW_H - 2)
            del_rect = Rect(pick_rect.right + 2, row_y, del_w, META_ROW_H - 2)
            self._meta_row_pick_rects.append((key, val, pick_rect))
            self._meta_delete_btn_rects.append(del_rect)

            pygame.draw.rect(screen, _COLORS["btn"], pick_rect, border_radius=3)
            pygame.draw.rect(screen, _COLORS["border"], pick_rect, 1, border_radius=3)
            disp = f"{key}  =  {_metadata_value_repr(val)}"
            if len(disp) > 42:
                disp = disp[:40] + "…"
            screen.blit(
                self._font_sm.render(disp, True, _COLORS["text"]),
                (pick_rect.x + 4, pick_rect.y + 4),
            )

            pygame.draw.rect(screen, _COLORS["btn_danger"], del_rect, border_radius=3)
            pygame.draw.rect(screen, _COLORS["border"], del_rect, 1, border_radius=3)
            close_icon = icon_manager.get_icon("close", 12, _COLORS["text"])
            screen.blit(close_icon, close_icon.get_rect(center=del_rect.center))

            row_y += META_ROW_H

        if not slice_items:
            empty = self._font_sm.render(
                "No entries — add a key below", True, _COLORS["text_dim"]
            )
            screen.blit(empty, (list_rect.x + 6, list_rect.centery - 6))

        form_y = list_rect.bottom + 10
        kw, vw, add_w = 100, panel.w - 16 - 100 - 8 - 44, 40
        self._btn_meta_key = Rect(panel.x + 8, form_y, kw, 24)
        self._btn_meta_value = Rect(self._btn_meta_key.right + 4, form_y, vw, 24)
        self._btn_meta_add = Rect(self._btn_meta_value.right + 4, form_y, add_w, 24)

        for rect, text, editing, placeholder in (
            (self._btn_meta_key, self._meta_key_input, self._editing_meta_key, "key"),
            (
                self._btn_meta_value,
                self._meta_value_input,
                self._editing_meta_value,
                "value",
            ),
        ):
            bg = _COLORS["btn_active"] if editing else _COLORS["input_bg"]
            pygame.draw.rect(screen, bg, rect, border_radius=3)
            pygame.draw.rect(screen, _COLORS["border"], rect, 1, border_radius=3)
            if not text and not editing:
                surf = self._font_sm.render(placeholder, True, _COLORS["text_dim"])
            else:
                shown = text + (
                    "|" if editing and (pygame.time.get_ticks() // 400) % 2 else ""
                )
                col = _COLORS["text_edit"] if editing else _COLORS["text"]
                surf = self._font_sm.render(shown, True, col)
            if surf.get_width() > rect.w - 8:
                surf = self._font_sm.render(
                    "…",
                    True,
                    _COLORS["text"] if text or editing else _COLORS["text_dim"],
                )
            screen.blit(surf, (rect.x + 4, rect.y + 5))

        self._draw_toolbar_btn(screen, self._btn_meta_add, "+", pygame.mouse.get_pos())

        if len(items) > visible_rows:
            scroll_hint = self._font_sm.render(
                f"scroll {self._meta_scroll + 1}-{self._meta_scroll + len(slice_items)} / {len(items)}",
                True,
                _COLORS["text_dim"],
            )
            screen.blit(scroll_hint, (panel.x + 10, panel.bottom - 18))

    def _get_active(self) -> Optional[Animation]:
        if self._active_anim_name:
            return self.library.get_animation(self._active_anim_name)
        return None

    # ------------------------------------------------------------------
    # Callbacks from sub-widgets
    # ------------------------------------------------------------------

    def _on_tile_clicked(self, variant_id: int) -> None:
        """Spritesheet click: toggle cel in clip, or Ctrl+click to select its keyframe on the strip."""
        anim = self._get_active()
        if anim is None:
            return
        mods = pygame.key.get_mods()
        ctrl = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
        if ctrl and anim.frames:
            for i, fr in enumerate(anim.frames):
                if fr.variant_id == variant_id:
                    self.timeline.select_frame(i)
                    return
            return

        in_clip = any(fr.variant_id == variant_id for fr in anim.frames)
        if in_clip:
            si = self.timeline.selected_index
            if 0 <= si < len(anim.frames) and anim.frames[si].variant_id == variant_id:
                anim.remove_frame(si)
            else:
                for ri in range(len(anim.frames) - 1, -1, -1):
                    if anim.frames[ri].variant_id == variant_id:
                        anim.remove_frame(ri)
                        break
            anim.clamp_markers()
            self._sync_active_animation()
            self._notify_animation_modified()
            return

        anim.add_frame(variant_id)
        self._sync_active_animation()
        self._notify_animation_modified()

    def _on_timeline_frame_selected(self, index: int) -> None:
        """User selected a frame in the timeline."""
        self.preview.current_frame = index
        self.preview._elapsed = 0.0
        self._apply_timeline_focus_to_sheet(scroll=True)

    def _on_frames_changed(self) -> None:
        """Timeline modified frames (reorder, delete, duration change)."""
        anim = self._get_active()
        if anim:
            anim.clamp_markers()
            used = {f.variant_id for f in anim.frames}
            self.frame_picker.set_highlighted(used)
            if self.consumer:
                self.consumer.on_animation_saved(anim.name, anim.to_dict())
        self._apply_timeline_focus_to_sheet(scroll=False)

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def _save_dialog(self) -> None:
        """Open file manager to save animation library.

        This is called when clicking the Save button or pressing Ctrl+Shift+S (Save As).
        """
        from pathlib import Path

        # Import FileManager
        try:
            from widgets.filemanager import FileManager
        except ImportError as e:
            # Fallback to old behavior if FileManager not available
            print(f"Warning: Could not import FileManager: {e}")
            path = self._default_save_path()
            try:
                self.library.grid_offset = (self._grid_offset_x, self._grid_offset_y)
                self.library.save(path, base_path=path.parent)
                self._last_saved_path = path
                print(f"Animations saved to {path}")
            except Exception as e:
                error_handler.capture(e, context="save_animations_quick_save")
            return

        # Get initial directory and default name
        if self._last_saved_path:
            # Use last saved location
            initial_dir = self._last_saved_path.parent
            default_name = self._last_saved_path.name
        elif self.library.spritesheet_path:
            initial_dir = self._data_root / "animations"
            default_name = Path(self.library.spritesheet_path).stem + ".anim.json"
        else:
            initial_dir = self._data_root / "animations"
            default_name = "animations.anim.json"
        initial_dir.mkdir(parents=True, exist_ok=True)

        # Create file manager for save
        screen = pygame.display.get_surface()
        w, h = 600, 400
        screen_w, screen_h = screen.get_size()  # type: ignore
        rect = pygame.Rect((screen_w - w) // 2, (screen_h - h) // 2, w, h)

        self._file_manager = FileManager(
            rect=rect,
            initial_dir=initial_dir,
            allowed_exts=[".json"],
            on_save=self._on_save_file_selected,
            mode="save",
            default_name=default_name,
            on_cancel=self._close_file_manager,
            data_root=self._data_root,
        )

    def _quick_save(self) -> None:
        """Quick save to last saved path (Ctrl+S).

        If no path exists, opens save dialog.
        """
        if self._last_saved_path:
            # Save to existing path
            try:
                self.library.grid_offset = (self._grid_offset_x, self._grid_offset_y)
                self.library.save(
                    self._last_saved_path,
                    base_path=self._last_saved_path.parent,
                )
                print(f"Animations saved to {self._last_saved_path}")
            except Exception as e:
                error_handler.capture(e, context="save_animations_quick")
        else:
            # No saved path yet, open save dialog
            self._save_dialog()

    def _load_dialog(self) -> None:
        """Load animation library from JSON using file manager."""
        from pathlib import Path

        # Import FileManager
        try:
            from widgets.filemanager import FileManager
        except ImportError:
            # Fallback to old behavior if FileManager not available
            path = self._default_save_path()
            if path.exists():
                try:
                    self.library = AnimationLibrary.load(path)
                    self._resolve_library_paths(path)
                    self._apply_library_grid_settings()
                    names = self.library.animation_names()
                    self._active_anim_name = names[0] if names else None
                    if not names:
                        self._create_new_animation("idle")
                    self._sync_active_animation()
                    print(f"Animations loaded from {path}")
                except Exception as e:
                    error_handler.capture(e, context="load_animations")
            else:
                print(f"No animation file found at {path}")
            return

        # Load project animation files from the configured data folder.
        initial_dir = self._data_root / "animations"
        initial_dir.mkdir(parents=True, exist_ok=True)

        # Create file manager for load
        screen = pygame.display.get_surface()
        w, h = 600, 400
        screen_w, screen_h = screen.get_size()  # type: ignore
        rect = pygame.Rect((screen_w - w) // 2, (screen_h - h) // 2, w, h)

        self._file_manager = FileManager(
            rect=rect,
            initial_dir=initial_dir,
            allowed_exts=[".json"],
            on_select=self._on_load_file_selected,
            mode="open",
            on_cancel=self._close_file_manager,
            data_root=self._data_root,
        )

    def _on_save_file_selected(self, path: Path) -> None:
        """Callback when user selects a file to save to."""
        try:
            # Sync current grid offset into library before saving
            self.library.grid_offset = (self._grid_offset_x, self._grid_offset_y)
            self.library.save(path, base_path=path.parent)
            self._last_saved_path = path  # Track for quick save
            print(f"Animations saved to {path}")
        except Exception as e:
            error_handler.capture(e, context="save_animations_dialog")
        self._close_file_manager()

    def _on_load_file_selected(self, path: Path | List[Path]) -> None:
        """Callback when user selects a file to load from."""
        # Handle both single Path and List[Path] cases
        if isinstance(path, list):
            if not path:  # Empty list
                return
            path = path[0]  # Take first file for single-file mode

        if path.exists():
            try:
                self.library = AnimationLibrary.load(path)
                self._resolve_library_paths(path)
                self._last_saved_path = path  # Track loaded file as save location
                self._apply_library_grid_settings()
                names = self.library.animation_names()
                self._active_anim_name = names[0] if names else None
                if not names:
                    self._create_new_animation("idle")
                self._sync_active_animation()
                print(f"Animations loaded from {path}")
            except Exception as e:
                error_handler.capture(e, context="load_animations_dialog")
        else:
            print(f"No animation file found at {path}")
        self._close_file_manager()

    def _close_file_manager(self) -> None:
        """Close the file manager dialog."""
        self._file_manager = None

    def _load_spritesheet_dialog(self) -> None:
        """Load spritesheet image using file manager."""
        from pathlib import Path

        # Import FileManager
        try:
            from widgets.filemanager import FileManager
        except ImportError as e:
            print(f"Warning: Could not import FileManager: {e}")
            return

        initial_dir = self._data_root
        initial_dir.mkdir(parents=True, exist_ok=True)

        # Create file manager for loading spritesheet
        screen = cast(Surface, pygame.display.get_surface())
        w, h = 600, 400
        screen_w, screen_h = screen.get_size()
        rect = pygame.Rect((screen_w - w) // 2, (screen_h - h) // 2, w, h)

        self._file_manager = FileManager(
            rect=rect,
            initial_dir=initial_dir,
            allowed_exts=[".png", ".jpg", ".jpeg", ".bmp", ".gif"],
            on_select=self._on_spritesheet_selected,
            mode="open",
            on_cancel=self._close_file_manager,
            data_root=self._data_root,
        )

    def _on_spritesheet_selected(self, path: Union[Path, List[Path]]) -> None:
        """Callback when user selects a spritesheet image to load."""
        try:
            # Handle both single Path and List[Path] cases
            if isinstance(path, list):
                if not path:
                    return  # No files selected
                selected_path = path[0]  # Take the first file for single selection mode
            else:
                selected_path = path

            # Load the image
            pygame.init()
            new_surface = pygame.image.load(str(selected_path)).convert_alpha()

            # Update the editor with the new spritesheet
            self._surface = new_surface
            self.library.spritesheet_path = str(selected_path)
            self._sheet_name = selected_path.name

            # Update all sub-widgets with the new surface
            self.frame_picker.set_surface(new_surface, self._tile_size)
            self.preview.set_surface(new_surface, self._tile_size)
            self.timeline.set_surface(new_surface, self._tile_size)

            # Clear existing animations since we're loading a new spritesheet
            self.library = AnimationLibrary(tile_size=self._tile_size)
            self.library.spritesheet_path = str(selected_path)
            self._active_anim_name = None
            self._sync_active_animation()

            print(f"Loaded spritesheet: {selected_path}")
            self._close_file_manager()

        except Exception as e:
            error_handler.capture(e, context="load_spritesheet")
            self._close_file_manager()

    def _default_save_path(self) -> Path:
        if self.library.spritesheet_path:
            base = Path(self.library.spritesheet_path).stem
            return Path(self.library.spritesheet_path).parent / f"{base}.anim.json"
        return Path.cwd() / "animations.anim.json"

    def _project_base_path(self) -> Optional[Path]:
        if self._data_root is None:
            return None
        return Path(self._data_root).parent

    def _resolve_library_paths(self, json_path: Path) -> None:
        if not self.library.spritesheet_path:
            return
        project_root = self._project_base_path()
        self.library.spritesheet_path = str(
            resolve_project_path(
                self.library.spritesheet_path,
                json_path.parent,
                fallback_roots=[project_root] if project_root else None,
                must_exist=True,
            )
        )

    # ------------------------------------------------------------------
    # Integration helpers
    # ------------------------------------------------------------------

    def set_surface(
        self, surface: pygame.Surface, tile_size: Optional[Tuple[int, int]] = None
    ) -> None:
        """Hot-swap the spritesheet (e.g. when user switches tilesets)."""
        self._surface = surface
        if tile_size:
            self._tile_size = tile_size
        self.frame_picker.set_surface(surface, tile_size)
        self.timeline.set_surface(surface, tile_size)
        self.preview.set_surface(surface, tile_size)

    def set_provider(self, provider: SpriteSheetProvider) -> None:
        """Switch to a different spritesheet provider."""
        self._provider = provider
        self.set_surface(provider.get_surface(), provider.get_tile_size())
        self._sheet_name = provider.get_name()

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def get_animation_data(self) -> dict:
        """Return the full animation library as a serializable dict."""
        return self.library.to_dict()

    def load_animation_data(self, data: dict) -> None:
        """Load animation library from a dict (e.g. from project JSON)."""
        self.library = AnimationLibrary.from_dict(data)
        self._apply_library_grid_settings()
        names = self.library.animation_names()
        self._active_anim_name = names[0] if names else None
        if not names:
            self._create_new_animation("idle")
        self._sync_active_animation()

    def get_image(self, variant: int) -> Optional[pygame.Surface]:
        """Return a **copy** of the spritesheet cel for ``variant`` (frame size + grid offset)."""
        tw, th = self._tile_size
        if tw < 1 or th < 1:
            return None
        ox, oy = self._grid_offset_x, self._grid_offset_y
        surf = self._surface
        avail_w = surf.get_width() - ox
        avail_h = surf.get_height() - oy
        if avail_w < tw or avail_h < th:
            return None
        cols = max(1, avail_w // tw)
        col = variant % cols
        row = variant // cols
        src = Rect(ox + col * tw, oy + row * th, tw, th)
        if not surf.get_rect().contains(src):
            return None
        return surf.subsurface(src).copy()

    # ------------------------------------------------------------------
    # Fonts
    # ------------------------------------------------------------------

    def _auto_select_font(self) -> str:
        """Returns the best available coding font using centralized font manager."""
        candidates = [
            "jetbrainsmono",
            "firacode",
            "consolas",
            "robotomono",
            "monospace",
        ]
        for c in candidates:
            if font_manager.get_font_info(c):
                return c
        return "monospace"

    def _ensure_fonts(self) -> None:
        """Initialize fonts using bold weight for better clarity like the console."""
        font_family = self._auto_select_font()
        if getattr(self, "_font", None) is None:
            self._font = font_manager.get_font(font_family, 13, FontWeight.BOLD)
        if getattr(self, "_font_sm", None) is None:
            self._font_sm = font_manager.get_font(font_family, 11, FontWeight.BOLD)
        if getattr(self, "_font_bold", None) is None:
            self._font_bold = font_manager.get_font(font_family, 13, FontWeight.BOLD)
