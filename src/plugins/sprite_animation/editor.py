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
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

import pygame
from pygame import Rect

from .frame_picker import FramePicker
from .models import Animation, AnimationFrame, AnimationLibrary
from .preview import AnimationPreview
from .protocols import AnimationConsumer, SpriteSheetProvider
from .timeline import Timeline

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
}

TOOLBAR_H = 36
PREVIEW_W = 220
TIMELINE_H = 130


class SpriteAnimationEditor:
    """Godot-like sprite animation editor panel.

    Layout::

        +----------------------------------------------------+
        | Toolbar: [idle ▾] [+] [✕] | [Save] [Load]         |
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
        tile_size: Tuple[int, int] = (64,64),
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
            raise ValueError("Must supply either `surface` or `provider`")

        # Animation library (holds all named animations)
        self.library = AnimationLibrary(tile_size=self._tile_size)
        self._active_anim_name: Optional[str] = None

        # Sub-widgets (must be created before any animation sync)
        fp_rect, pv_rect, tl_rect = self._layout_rects()
        self.frame_picker = FramePicker(fp_rect, self._surface, self._tile_size)
        self.preview = AnimationPreview(pv_rect, self._surface, self._tile_size)
        self.timeline = Timeline(tl_rect, self._surface, self._tile_size)

        # Wire callbacks
        self.frame_picker.on_frame_clicked = self._on_tile_clicked
        self.timeline.on_frame_selected = self._on_timeline_frame_selected
        self.timeline.on_frames_changed = self._on_frames_changed

        # Create a default animation (now safe — widgets exist)
        self._create_new_animation("idle")

        # Dropdown state
        self._dropdown_open = False
        self._dropdown_rect = Rect(0, 0, 0, 0)
        self._dropdown_items_rects: List[Rect] = []

        # Rename state
        self._renaming = False
        self._rename_text = ""

        # Toolbar button rects (calculated in draw)
        self._btn_new = Rect(0, 0, 0, 0)
        self._btn_del = Rect(0, 0, 0, 0)
        self._btn_save = Rect(0, 0, 0, 0)
        self._btn_load = Rect(0, 0, 0, 0)
        self._btn_anim_selector = Rect(0, 0, 0, 0)
        self._btn_info = Rect(0, 0, 0, 0)
        
        # Tooltip state
        self._show_info_tooltip = False
        
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

        # Fonts
        self._font: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None
        self._font_bold: Optional[pygame.font.Font] = None

        # For standalone mode
        self._clock: Optional[pygame.time.Clock] = None
        
        # File manager dialog
        self._file_manager = None
        
        # Track the last saved path for quick save (Ctrl+S)
        self._last_saved_path: Optional[Path] = None

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
    ) -> SpriteAnimationEditor:
        """Load a spritesheet from disk and create a standalone editor."""
        pygame.init()
        pygame.display.set_mode(window_size, pygame.RESIZABLE)
        surf = pygame.image.load(str(image_path)).convert_alpha()
        ed = cls.from_surface(surf, tile_size, window_size)
        ed.library.spritesheet_path = str(image_path)
        ed._sheet_name = image_path.name
        return ed

    # ------------------------------------------------------------------
    # Standalone main loop
    # ------------------------------------------------------------------

    def run(self, fps: int = 60) -> None:
        """Block and run the editor as a standalone window."""
        if not pygame.get_init():
            pygame.init()
        screen = pygame.display.set_mode(
            (self.rect.w, self.rect.h), pygame.RESIZABLE
        )
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
        
        # Global keyboard shortcuts (when not editing text)
        if event.type == pygame.KEYDOWN and not self._renaming and not self._editing_frame_width and not self._editing_frame_height and not self._editing_offset_x and not self._editing_offset_y:
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
                    return True
                elif event.key == pygame.K_BACKSPACE:
                    self._rename_text = self._rename_text[:-1]
                    return True
                elif event.unicode and len(self._rename_text) < 30:
                    self._rename_text += event.unicode
                    return True
        
        # Frame width input
        if self._editing_frame_width:
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
                elif event.unicode and event.unicode.isdigit() and len(self._frame_width_input) < 5:
                    # Smart zero handling: if input is "0" and user types non-zero, replace it
                    if self._frame_width_input == "0" and event.unicode != "0":
                        self._frame_width_input = event.unicode
                    else:
                        self._frame_width_input += event.unicode
                    return True
        
        # Frame height input
        if self._editing_frame_height:
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
                elif event.unicode and event.unicode.isdigit() and len(self._frame_height_input) < 5:
                    # Smart zero handling
                    if self._frame_height_input == "0" and event.unicode != "0":
                        self._frame_height_input = event.unicode
                    else:
                        self._frame_height_input += event.unicode
                    return True
        
        # Offset X input
        if self._editing_offset_x:
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
                elif event.unicode and (event.unicode.isdigit() or (event.unicode == '-' and len(self._offset_x_input) == 0)) and len(self._offset_x_input) < 5:
                    # Smart zero handling for offset (can be negative)
                    if self._offset_x_input == "0" and event.unicode != "0" and event.unicode != "-":
                        self._offset_x_input = event.unicode
                    else:
                        self._offset_x_input += event.unicode
                    return True
        
        # Offset Y input
        if self._editing_offset_y:
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
                elif event.unicode and (event.unicode.isdigit() or (event.unicode == '-' and len(self._offset_y_input) == 0)) and len(self._offset_y_input) < 5:
                    # Smart zero handling for offset
                    if self._offset_y_input == "0" and event.unicode != "0" and event.unicode != "-":
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
            
            # Frame width input
            if self._btn_frame_width.collidepoint(mouse):
                self._editing_frame_width = True
                self._editing_frame_height = False
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

            # Double-click on animation selector -> rename
            # (We treat any click on the name area as potential rename start)

        # Double-click to rename
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

        self._ensure_fonts()

        # Toolbar
        self._draw_toolbar(screen)

        # Sub-widgets
        self.preview.draw(screen)
        self.frame_picker.draw(screen)
        self.timeline.draw(screen)

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
        fp_rect = Rect(x + PREVIEW_W, y + TOOLBAR_H, w - PREVIEW_W, h - TOOLBAR_H - TIMELINE_H)

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
        tb = Rect(self.rect.x, self.rect.y, self.rect.w, TOOLBAR_H)
        pygame.draw.rect(screen, _COLORS["toolbar"], tb)
        pygame.draw.line(
            screen, _COLORS["toolbar_border"],
            (tb.x, tb.bottom - 1), (tb.right, tb.bottom - 1),
        )

        bh = 26
        pad = 6
        x = tb.x + pad
        cy = tb.y + (TOOLBAR_H - bh) // 2

        # Animation selector
        sel_w = 140
        self._btn_anim_selector = Rect(x, cy, sel_w, bh)
        is_hover = self._btn_anim_selector.collidepoint(mouse)
        bg = _COLORS["btn_hover"] if is_hover else _COLORS["btn"]
        pygame.draw.rect(screen, bg, self._btn_anim_selector, border_radius=3)
        pygame.draw.rect(screen, _COLORS["border"], self._btn_anim_selector, 1, border_radius=3)

        if self._renaming:
            display_text = self._rename_text + ("|" if (pygame.time.get_ticks() // 400) % 2 else "")
            lbl = self._font.render(display_text, True, (255, 220, 100))
        else:
            display_name = self._active_anim_name or "(none)"
            if len(display_name) > 16:
                display_name = display_name[:14] + ".."
            lbl = self._font.render(f"  {display_name} ▾", True, _COLORS["text"])
        screen.blit(lbl, (self._btn_anim_selector.x + 4, self._btn_anim_selector.y + 5))
        x += sel_w + pad

        # [+ New]
        self._btn_new = Rect(x, cy, 28, bh)
        self._draw_toolbar_btn(screen, self._btn_new, "+", mouse)
        x += 32

        # [✕ Delete]
        self._btn_del = Rect(x, cy, 28, bh)
        self._draw_toolbar_btn(screen, self._btn_del, "✕", mouse, danger=True)
        x += 36

        # Separator
        pygame.draw.line(screen, _COLORS["toolbar_border"], (x, cy + 2), (x, cy + bh - 2))
        x += pad + 4

        # [Save]
        self._btn_save = Rect(x, cy, 48, bh)
        self._draw_toolbar_btn(screen, self._btn_save, "Save", mouse)
        x += 52

        # [Load]
        self._btn_load = Rect(x, cy, 48, bh)
        self._draw_toolbar_btn(screen, self._btn_load, "Load", mouse)
        x += 56

        # Separator
        pygame.draw.line(screen, _COLORS["toolbar_border"], (x, cy + 2), (x, cy + bh - 2))
        x += pad + 4

        # Frame size label
        size_label = self._font_sm.render("Frame:", True, _COLORS["text_dim"])
        screen.blit(size_label, (x, cy + 7))
        x += size_label.get_width() + 4

        # Width input
        input_w = 42
        self._btn_frame_width = Rect(x, cy, input_w, bh)
        width_bg = _COLORS["input_bg"] if not self._editing_frame_width else _COLORS["btn_active"]
        pygame.draw.rect(screen, width_bg, self._btn_frame_width, border_radius=3)
        pygame.draw.rect(screen, _COLORS["border"], self._btn_frame_width, 1, border_radius=3)
        
        width_text = self._frame_width_input
        if self._editing_frame_width and (pygame.time.get_ticks() // 400) % 2:
            width_text += "|"
        width_surf = self._font_sm.render(width_text, True, _COLORS["text"])
        screen.blit(width_surf, (self._btn_frame_width.x + 4, self._btn_frame_width.y + 6))
        x += input_w + 2

        # x separator
        x_label = self._font_sm.render("×", True, _COLORS["text_dim"])
        screen.blit(x_label, (x, cy + 6))
        x += x_label.get_width() + 2

        # Height input
        self._btn_frame_height = Rect(x, cy, input_w, bh)
        height_bg = _COLORS["input_bg"] if not self._editing_frame_height else _COLORS["btn_active"]
        pygame.draw.rect(screen, height_bg, self._btn_frame_height, border_radius=3)
        pygame.draw.rect(screen, _COLORS["border"], self._btn_frame_height, 1, border_radius=3)
        
        height_text = self._frame_height_input
        if self._editing_frame_height and (pygame.time.get_ticks() // 400) % 2:
            height_text += "|"
        height_surf = self._font_sm.render(height_text, True, _COLORS["text"])
        screen.blit(height_surf, (self._btn_frame_height.x + 4, self._btn_frame_height.y + 6))
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
        pygame.draw.circle(screen, _COLORS["border"], self._btn_info.center, 10, 1)
        
        # Draw "i" icon
        info_text = self._font_bold.render("i", True, _COLORS["text"])
        info_text_rect = info_text.get_rect(center=self._btn_info.center)
        screen.blit(info_text, info_text_rect)
        
        # Show tooltip on hover
        if info_hover:
            self._show_info_tooltip = True
        else:
            self._show_info_tooltip = False
        
        x += 28

        # Separator
        pygame.draw.line(screen, _COLORS["toolbar_border"], (x, cy + 2), (x, cy + bh - 2))
        x += pad + 4

        # Offset label
        offset_label = self._font_sm.render("Offset:", True, _COLORS["text_dim"])
        screen.blit(offset_label, (x, cy + 7))
        x += offset_label.get_width() + 4

        # Offset X input
        offset_input_w = 38
        self._btn_offset_x = Rect(x, cy, offset_input_w, bh)
        offset_x_bg = _COLORS["input_bg"] if not self._editing_offset_x else _COLORS["btn_active"]
        pygame.draw.rect(screen, offset_x_bg, self._btn_offset_x, border_radius=3)
        pygame.draw.rect(screen, _COLORS["border"], self._btn_offset_x, 1, border_radius=3)
        
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
        offset_y_bg = _COLORS["input_bg"] if not self._editing_offset_y else _COLORS["btn_active"]
        pygame.draw.rect(screen, offset_y_bg, self._btn_offset_y, border_radius=3)
        pygame.draw.rect(screen, _COLORS["border"], self._btn_offset_y, 1, border_radius=3)
        
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
        
        # Draw info tooltip if hovering
        if self._show_info_tooltip:
            self._draw_info_tooltip(screen)

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
        """Draw tooltip showing spritesheet information."""
        # Gather info
        sheet_w, sheet_h = self._surface.get_size()
        frame_w, frame_h = self._tile_size
        cols = self.frame_picker.cols
        rows = self.frame_picker.rows
        total_frames = self.frame_picker.total_frames
        offset_x, offset_y = self._grid_offset_x, self._grid_offset_y
        
        # Build tooltip lines
        lines = [
            f"Spritesheet: {sheet_w} × {sheet_h} px",
            f"Frame Size: {frame_w} × {frame_h} px",
            f"Grid: {cols} cols × {rows} rows",
            f"Total Frames: {total_frames}",
            f"Offset: {offset_x}, {offset_y}",
        ]
        
        # Calculate tooltip size
        padding = 8
        line_height = 16
        max_width = max(self._font_sm.render(line, True, _COLORS["text"]).get_width() for line in lines)
        tooltip_w = max_width + padding * 2
        tooltip_h = len(lines) * line_height + padding * 2
        
        # Position tooltip below info button
        tooltip_x = self._btn_info.centerx - tooltip_w // 2
        tooltip_y = self._btn_info.bottom + 4
        
        # Clamp to screen bounds
        tooltip_x = max(10, min(tooltip_x, self.rect.right - tooltip_w - 10))
        
        tooltip_rect = Rect(tooltip_x, tooltip_y, tooltip_w, tooltip_h)
        
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

        pygame.draw.rect(screen, _COLORS["dropdown_bg"], self._dropdown_rect, border_radius=4)
        pygame.draw.rect(screen, _COLORS["dropdown_border"], self._dropdown_rect, 1, border_radius=4)

        mouse = pygame.mouse.get_pos()
        self._dropdown_items_rects = []
        for i, name in enumerate(names):
            item_rect = Rect(dd_x + 2, dd_y + 2 + i * item_h, dd_w - 4, item_h)
            self._dropdown_items_rects.append(item_rect)

            is_active = name == self._active_anim_name
            is_hover = item_rect.collidepoint(mouse)
            if is_active:
                pygame.draw.rect(screen, _COLORS["btn_active"], item_rect, border_radius=3)
            elif is_hover:
                pygame.draw.rect(screen, _COLORS["dropdown_hover"], item_rect, border_radius=3)

            display = name if len(name) < 18 else name[:16] + ".."
            color = _COLORS["accent"] if is_active else _COLORS["text"]
            lbl = self._font.render(display, True, color)
            screen.blit(lbl, (item_rect.x + 8, item_rect.y + 4))

            # Frame count badge
            anim = self.library.get_animation(name)
            if anim:
                badge = self._font_sm.render(f"{anim.frame_count()}f", True, _COLORS["text_dim"])
                screen.blit(badge, (item_rect.right - badge.get_width() - 6, item_rect.y + 6))

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
            self._rename_text = self._active_anim_name
            self._dropdown_open = False

    def _commit_rename(self) -> None:
        new_name = self._rename_text.strip()
        if new_name and self._active_anim_name and new_name != self._active_anim_name:
            if self.library.rename_animation(self._active_anim_name, new_name):
                self._active_anim_name = new_name
        self._renaming = False
    
    def _apply_frame_size(self) -> None:
        """Apply the frame size from input fields and update the frame picker."""
        try:
            width = int(self._frame_width_input) if self._frame_width_input else self._tile_size[0]
            height = int(self._frame_height_input) if self._frame_height_input else self._tile_size[1]
            
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
            self.timeline._thumb_cache.clear()
            
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
            offset_x = max(-self._surface.get_width(), min(offset_x, self._surface.get_width()))
            offset_y = max(-self._surface.get_height(), min(offset_y, self._surface.get_height()))
            
            # Update grid offset
            self._grid_offset_x = offset_x
            self._grid_offset_y = offset_y
            
            # Update frame picker with offset
            if hasattr(self.frame_picker, 'set_grid_offset'):
                self.frame_picker.set_grid_offset(offset_x, offset_y)
            
            # Update timeline with offset
            if hasattr(self.timeline, 'grid_offset_x'):
                self.timeline.grid_offset_x = offset_x
                self.timeline.grid_offset_y = offset_y
                self.timeline._thumb_cache.clear()
            
            # Update preview with offset (if it has the attribute)
            if hasattr(self.preview, 'grid_offset_x'):
                self.preview.grid_offset_x = offset_x
                self.preview.grid_offset_y = offset_y
            
            # Update input fields to show clamped values
            self._offset_x_input = str(offset_x)
            self._offset_y_input = str(offset_y)
            
        except ValueError:
            # Reset to current values on invalid input
            self._offset_x_input = str(self._grid_offset_x)
            self._offset_y_input = str(self._grid_offset_y)

    def _sync_active_animation(self) -> None:
        """Push current animation data to sub-widgets."""
        anim = self._get_active()
        if anim:
            self.timeline.set_frames(anim.frames)
            self.preview.set_frames(anim.frames)
            self.preview.loop = anim.loop
            # Highlight used frames in frame picker
            used = {f.variant_id for f in anim.frames}
            self.frame_picker.set_highlighted(used)
        else:
            self.timeline.set_frames([])
            self.preview.set_frames([])
            self.frame_picker.set_highlighted(set())

    def _get_active(self) -> Optional[Animation]:
        if self._active_anim_name:
            return self.library.get_animation(self._active_anim_name)
        return None

    # ------------------------------------------------------------------
    # Callbacks from sub-widgets
    # ------------------------------------------------------------------

    def _on_tile_clicked(self, variant_id: int) -> None:
        """User clicked a tile in the spritesheet — add as a frame."""
        anim = self._get_active()
        if anim is None:
            return
        anim.add_frame(variant_id)
        self._sync_active_animation()

    def _on_timeline_frame_selected(self, index: int) -> None:
        """User selected a frame in the timeline."""
        # Jump preview to that frame
        self.preview.current_frame = index
        self.preview._elapsed = 0.0

    def _on_frames_changed(self) -> None:
        """Timeline modified frames (reorder, delete, duration change)."""
        anim = self._get_active()
        if anim:
            used = {f.variant_id for f in anim.frames}
            self.frame_picker.set_highlighted(used)
            if self.consumer:
                self.consumer.on_animation_saved(anim.name, anim.to_dict())

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
            from constants import BASE_PATH
        except ImportError as e:
            # Fallback to old behavior if FileManager not available
            print(f"Warning: Could not import FileManager: {e}")
            path = self._default_save_path()
            try:
                self.library.save(path)
                self._last_saved_path = path
                print(f"Animations saved to {path}")
            except Exception as e:
                print(f"Error saving animations: {e}")
            return
        
        # Get initial directory and default name
        if self._last_saved_path:
            # Use last saved location
            initial_dir = self._last_saved_path.parent
            default_name = self._last_saved_path.name
        elif self.library.spritesheet_path:
            # Use spritesheet location
            initial_dir = Path(self.library.spritesheet_path).parent
            default_name = Path(self.library.spritesheet_path).stem + ".anim.json"
        else:
            # Use data folder
            initial_dir = BASE_PATH / "data"
            default_name = "animations.anim.json"
        
        # Create file manager for save
        screen = pygame.display.get_surface()
        w, h = 600, 400
        screen_w, screen_h = screen.get_size()
        rect = pygame.Rect((screen_w - w) // 2, (screen_h - h) // 2, w, h)
        
        self._file_manager = FileManager(
            rect=rect,
            initial_dir=initial_dir,
            allowed_exts=[".json"],
            on_save=self._on_save_file_selected,
            mode="save",
            default_name=default_name,
            on_cancel=self._close_file_manager,
        )
    
    def _quick_save(self) -> None:
        """Quick save to last saved path (Ctrl+S).
        
        If no path exists, opens save dialog.
        """
        if self._last_saved_path:
            # Save to existing path
            try:
                self.library.save(self._last_saved_path)
                print(f"Animations saved to {self._last_saved_path}")
            except Exception as e:
                print(f"Error saving animations: {e}")
        else:
            # No saved path yet, open save dialog
            self._save_dialog()

    def _load_dialog(self) -> None:
        """Load animation library from JSON using file manager."""
        from pathlib import Path
        
        # Import FileManager
        try:
            from widgets.filemanager import FileManager
            from constants import BASE_PATH
        except ImportError:
            # Fallback to old behavior if FileManager not available
            path = self._default_save_path()
            if path.exists():
                try:
                    self.library = AnimationLibrary.load(path)
                    names = self.library.animation_names()
                    self._active_anim_name = names[0] if names else None
                    if not names:
                        self._create_new_animation("idle")
                    self._sync_active_animation()
                    print(f"Animations loaded from {path}")
                except Exception as e:
                    print(f"Error loading animations: {e}")
            else:
                print(f"No animation file found at {path}")
            return
        
        # Get initial directory from spritesheet path or use data folder
        if self.library.spritesheet_path:
            initial_dir = Path(self.library.spritesheet_path).parent
        else:
            initial_dir = BASE_PATH / "data"
        
        # Create file manager for load
        screen = pygame.display.get_surface()
        w, h = 600, 400
        screen_w, screen_h = screen.get_size()
        rect = pygame.Rect((screen_w - w) // 2, (screen_h - h) // 2, w, h)
        
        self._file_manager = FileManager(
            rect=rect,
            initial_dir=initial_dir,
            allowed_exts=[".json"],
            on_select=self._on_load_file_selected,
            mode="open",
            on_cancel=self._close_file_manager,
        )
    
    def _on_save_file_selected(self, path: Path) -> None:
        """Callback when user selects a file to save to."""
        try:
            self.library.save(path)
            self._last_saved_path = path  # Track for quick save
            print(f"Animations saved to {path}")
        except Exception as e:
            print(f"Error saving animations: {e}")
        self._close_file_manager()
    
    def _on_load_file_selected(self, path: Path) -> None:
        """Callback when user selects a file to load from."""
        if path.exists():
            try:
                self.library = AnimationLibrary.load(path)
                self._last_saved_path = path  # Track loaded file as save location
                names = self.library.animation_names()
                self._active_anim_name = names[0] if names else None
                if not names:
                    self._create_new_animation("idle")
                self._sync_active_animation()
                print(f"Animations loaded from {path}")
            except Exception as e:
                print(f"Error loading animations: {e}")
        else:
            print(f"No animation file found at {path}")
        self._close_file_manager()
    
    def _close_file_manager(self) -> None:
        """Close the file manager dialog."""
        self._file_manager = None

    def _default_save_path(self) -> Path:
        if self.library.spritesheet_path:
            base = Path(self.library.spritesheet_path).stem
            return Path(self.library.spritesheet_path).parent / f"{base}.anim.json"
        return Path.cwd() / "animations.anim.json"

    # ------------------------------------------------------------------
    # Integration helpers
    # ------------------------------------------------------------------

    def set_surface(self, surface: pygame.Surface, tile_size: Optional[Tuple[int, int]] = None) -> None:
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
        names = self.library.animation_names()
        self._active_anim_name = names[0] if names else None
        if not names:
            self._create_new_animation("idle")
        self._sync_active_animation()

    # ------------------------------------------------------------------
    # Fonts
    # ------------------------------------------------------------------

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("Arial", 13)
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("Arial", 11)
        if self._font_bold is None:
            self._font_bold = pygame.font.SysFont("Arial", 13, bold=True)
