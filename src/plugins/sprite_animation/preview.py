"""
Animation Preview — real-time playback of the current animation.

Shows a zoomed-up view of the animation playing with optional
onion-skin ghosting. Provides Play / Pause / Stop / FPS field / Loop controls.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import pygame
from pygame import Rect

from .models import AnimationFrame
from utils.font_manager import font_manager, FontWeight, FontStyle
from utils.icon_manager import icon_manager

# ---------------------------------------------------------------------------
_COLORS = {
    "bg": (25, 27, 30),
    "panel": (35, 38, 44),
    "border": (60, 62, 65),
    "header": (40, 42, 46),
    "text": (230, 230, 230),
    "text_dim": (140, 140, 140),
    "accent": (80, 120, 200),
    "accent_hover": (100, 140, 220),
    "success": (80, 180, 120),
    "danger": (200, 80, 80),
    "warning": (220, 180, 80),
    "btn": (50, 54, 62),
    "btn_hover": (65, 70, 80),
    "btn_active": (50, 70, 110),
    "onion": (180, 120, 255),
    "input_bg": (30, 32, 38),
    "text_edit": (255, 220, 100),
}

HEADER_H = 36
CONTROLS_H = 32
# Preview timing vs a 60 Hz editor tick: elapsed += dt_ms * (playback_fps / 60).


class AnimationPreview:
    """Live playback panel with transport controls."""

    def __init__(
        self,
        rect: Rect,
        surface: pygame.Surface,
        tile_size: Tuple[int, int],
    ):
        self.rect = rect
        self.surface = surface
        self.tile_size = tile_size

        self.frames: List[AnimationFrame] = []
        self.playing = False
        self.loop = True
        self.grid_offset_x: int = 0
        self.grid_offset_y: int = 0
        self.playback_fps: float = 60.0
        self.show_onion = False

        self.on_playback_fps_changed: Optional[Callable[[float], None]] = None
        self.on_loop_changed: Optional[Callable[[bool], None]] = None
        self.authoring_fps: float = 60.0

        self.current_frame: int = 0
        self._elapsed: float = 0.0

        self._zoom = 3.0

        self._fps_input_text = "60"
        self._editing_fps = False
        self._fps_input_rect = Rect(0, 0, 0, 0)

        # Buttons (recalculated in draw)
        self._btn_play = Rect(0, 0, 0, 0)
        self._btn_stop = Rect(0, 0, 0, 0)
        self._btn_loop = Rect(0, 0, 0, 0)
        self._btn_onion = Rect(0, 0, 0, 0)
        self._btn_prev = Rect(0, 0, 0, 0)
        self._btn_next = Rect(0, 0, 0, 0)

        # Scrubber fraction output (read by timeline)
        self.scrubber_frac: float = 0.0

        self._font: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None
        self._checker: Optional[pygame.Surface] = None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def set_frames(self, frames: List[AnimationFrame]) -> None:
        self.frames = frames
        self.current_frame = 0
        self._elapsed = 0.0

    def set_surface(
        self, surface: pygame.Surface, tile_size: Optional[Tuple[int, int]] = None
    ) -> None:
        self.surface = surface
        if tile_size:
            self.tile_size = tile_size

    def resize(self, rect: Rect) -> None:
        self.rect = rect

    def is_fps_input_active(self) -> bool:
        return self._editing_fps

    def fps_input_contains(self, pos: Tuple[int, int]) -> bool:
        return self._fps_input_rect.collidepoint(pos)

    def sync_playback_fps_field(self) -> None:
        """Reset the FPS text field from ``playback_fps`` (e.g. after switching clip)."""
        self._editing_fps = False
        self._fps_input_text = self._format_fps_display(self.playback_fps)

    def commit_fps_input(self) -> None:
        """Apply the FPS field to ``playback_fps`` and notify; no-op if not editing."""
        if not self._editing_fps:
            return
        self._editing_fps = False
        try:
            v = float(self._fps_input_text.strip().replace(",", "."))
            v = max(0.1, min(v, 1000.0))
            self.playback_fps = v
            self._fps_input_text = self._format_fps_display(v)
            if self.on_playback_fps_changed:
                self.on_playback_fps_changed(v)
        except ValueError:
            self._fps_input_text = self._format_fps_display(self.playback_fps)

    @staticmethod
    def _format_fps_display(fps: float) -> str:
        if abs(fps - round(fps)) < 1e-4:
            return str(int(round(fps)))
        return f"{fps:.4g}"

    def play(self) -> None:
        self.playing = True

    def pause(self) -> None:
        self.playing = False

    def stop(self) -> None:
        self.playing = False
        self.current_frame = 0
        self._elapsed = 0.0
        self.scrubber_frac = 0.0

    # ------------------------------------------------------------------
    # Update (call every frame with dt in milliseconds)
    # ------------------------------------------------------------------

    def update(self, dt_ms: float) -> None:
        if not self.playing or not self.frames:
            return

        scale = self.playback_fps / 60.0
        self._elapsed += dt_ms * scale
        cur = self.frames[self.current_frame]

        while self._elapsed >= cur.duration_ms:
            self._elapsed -= cur.duration_ms
            self.current_frame += 1
            if self.current_frame >= len(self.frames):
                if self.loop:
                    self.current_frame = 0
                else:
                    self.current_frame = len(self.frames) - 1
                    self.playing = False
                    break
            cur = self.frames[self.current_frame]

        # Compute scrubber fraction
        total = sum(f.duration_ms for f in self.frames)
        if total > 0:
            elapsed_to_cur = (
                sum(f.duration_ms for f in self.frames[: self.current_frame])
                + self._elapsed
            )
            self.scrubber_frac = elapsed_to_cur / total
        else:
            self.scrubber_frac = 0.0

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN and self._editing_fps:
            return self._handle_fps_keydown(event)

        mouse = pygame.mouse.get_pos()
        if not self.rect.collidepoint(mouse):
            if (
                event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self._editing_fps
            ):
                self.commit_fps_input()
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._editing_fps and not self._fps_input_rect.collidepoint(mouse):
                self.commit_fps_input()
            if self._fps_input_rect.collidepoint(mouse):
                self._editing_fps = True
                return True
            if self._btn_play.collidepoint(mouse):
                if self.playing:
                    self.pause()
                else:
                    self.play()
                return True
            if self._btn_stop.collidepoint(mouse):
                self.stop()
                return True
            if self._btn_loop.collidepoint(mouse):
                self.loop = not self.loop
                if self.on_loop_changed:
                    self.on_loop_changed(self.loop)
                return True
            if self._btn_onion.collidepoint(mouse):
                self.show_onion = not self.show_onion
                return True
            if self._btn_prev.collidepoint(mouse):
                self._step(-1)
                return True
            if self._btn_next.collidepoint(mouse):
                self._step(1)
                return True

        # Scroll to adjust zoom
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(mouse):
            self._zoom *= 1.15 if event.y > 0 else 0.87
            self._zoom = max(1.0, min(self._zoom, 12.0))
            return True

        return False

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, screen: pygame.Surface) -> None:
        self._ensure_fonts()
        clip = screen.get_clip()
        screen.set_clip(self.rect)

        pygame.draw.rect(screen, _COLORS["panel"], self.rect)
        pygame.draw.rect(screen, _COLORS["border"], self.rect, 1)

        # Header
        hdr = Rect(self.rect.x, self.rect.y, self.rect.w, HEADER_H)
        pygame.draw.rect(screen, _COLORS["header"], hdr)
        title = "Preview"
        if self.frames:
            title += f"  {self.current_frame + 1}/{len(self.frames)}"
        screen.blit(
            self._font.render(title, True, _COLORS["text"]), (hdr.x + 6, hdr.y + 2)
        )
        if self.frames and 0 <= self.current_frame < len(self.frames):
            fr = self.frames[self.current_frame]
            auth = max(0.001, float(self.authoring_fps))
            equiv = fr.duration_ms * auth / 1000.0
            sub = f"{fr.duration_ms:g} ms  ·  {equiv:.2f} frames @ {auth:g} FPS (clip rate)"
            screen.blit(
                self._font_sm.render(sub, True, _COLORS["text_dim"]),
                (hdr.x + 6, hdr.y + 18),
            )

        # Preview area
        preview_y = self.rect.y + HEADER_H
        preview_h = self.rect.h - HEADER_H - CONTROLS_H
        preview_rect = Rect(self.rect.x, preview_y, self.rect.w, preview_h)

        # Checkerboard background
        self._draw_checker(screen, preview_rect)

        # Draw current frame
        if self.frames and 0 <= self.current_frame < len(self.frames):
            frame = self.frames[self.current_frame]

            # Onion skin (previous frame)
            if self.show_onion and self.current_frame > 0:
                prev_frame = self.frames[self.current_frame - 1]
                prev_surf = self._extract_tile(prev_frame.variant_id)
                if prev_surf:
                    zoomed = pygame.transform.scale(
                        prev_surf,
                        (
                            int(self.tile_size[0] * self._zoom),
                            int(self.tile_size[1] * self._zoom),
                        ),
                    )
                    zoomed.set_alpha(60)
                    dx = preview_rect.centerx - zoomed.get_width() // 2
                    dy = preview_rect.centery - zoomed.get_height() // 2
                    screen.blit(zoomed, (dx, dy))

            # Current frame
            tile_surf = self._extract_tile(frame.variant_id)
            if tile_surf:
                zw = int(self.tile_size[0] * self._zoom)
                zh = int(self.tile_size[1] * self._zoom)
                zoomed = pygame.transform.scale(tile_surf, (zw, zh))
                dx = preview_rect.centerx - zw // 2
                dy = preview_rect.centery - zh // 2
                screen.blit(zoomed, (dx, dy))

        elif not self.frames:
            no_anim = self._font.render("No frames", True, _COLORS["text_dim"])
            screen.blit(no_anim, no_anim.get_rect(center=preview_rect.center))

        # Controls bar
        ctrl_y = self.rect.bottom - CONTROLS_H
        ctrl_rect = Rect(self.rect.x, ctrl_y, self.rect.w, CONTROLS_H)
        pygame.draw.rect(screen, _COLORS["header"], ctrl_rect)

        self._draw_controls(screen, ctrl_rect)

        screen.set_clip(clip)

    # ------------------------------------------------------------------
    # Controls drawing
    # ------------------------------------------------------------------

    def _draw_controls(self, screen: pygame.Surface, ctrl_rect: Rect) -> None:
        mouse = pygame.mouse.get_pos()
        bw, bh = 28, 24
        pad = 4
        x = ctrl_rect.x + pad
        y = ctrl_rect.y + (ctrl_rect.h - bh) // 2

        # |<< (prev)
        self._btn_prev = Rect(x, y, bw, bh)
        self._draw_btn(screen, self._btn_prev, "|◀", mouse)
        x += bw + pad

        # Play / Pause
        self._btn_play = Rect(x, y, bw, bh)
        self._draw_btn(screen, self._btn_play, "", mouse, active=self.playing)
        play_icon = icon_manager.get_icon(
            "pause" if self.playing else "play", 12, _COLORS["text"]
        )
        screen.blit(play_icon, play_icon.get_rect(center=self._btn_play.center))
        x += bw + pad

        # Stop
        self._btn_stop = Rect(x, y, bw, bh)
        self._draw_btn(screen, self._btn_stop, "", mouse)
        stop_icon = icon_manager.get_icon("stop", 12, _COLORS["text"])
        screen.blit(stop_icon, stop_icon.get_rect(center=self._btn_stop.center))
        x += bw + pad

        # >>| (next)
        self._btn_next = Rect(x, y, bw, bh)
        self._draw_btn(screen, self._btn_next, "▶|", mouse)
        x += bw + pad + 4

        # Loop toggle
        self._btn_loop = Rect(x, y, bw + 4, bh)
        self._draw_btn(screen, self._btn_loop, "", mouse, active=self.loop)
        loop_icon = icon_manager.get_icon("loop", 12, _COLORS["text"])
        screen.blit(loop_icon, loop_icon.get_rect(center=self._btn_loop.center))
        x += bw + pad + 8

        # Playback FPS (editable; timing vs 60 Hz tick — see update())
        fps_tag = self._font_sm.render("FPS", True, _COLORS["text_dim"])
        screen.blit(fps_tag, (x, y + (bh - fps_tag.get_height()) // 2))
        x += fps_tag.get_width() + 3
        self._fps_input_rect = Rect(x, y, 44, bh)
        fps_bg = _COLORS["btn_active"] if self._editing_fps else _COLORS["input_bg"]
        pygame.draw.rect(screen, fps_bg, self._fps_input_rect, border_radius=3)
        pygame.draw.rect(
            screen, _COLORS["border"], self._fps_input_rect, 1, border_radius=3
        )
        shown = self._fps_input_text
        if self._editing_fps and (pygame.time.get_ticks() // 400) % 2:
            shown += "|"
        col = _COLORS["text_edit"] if self._editing_fps else _COLORS["text"]
        fps_surf = self._font_sm.render(shown or " ", True, col)
        screen.blit(fps_surf, (self._fps_input_rect.x + 4, self._fps_input_rect.y + 5))
        x += 44 + pad

        # Onion skin
        if x + bw + 12 < ctrl_rect.right:
            self._btn_onion = Rect(x, y, bw + 4, bh)
            self._draw_btn(screen, self._btn_onion, "👻", mouse, active=self.show_onion)

    def _draw_btn(
        self, screen: pygame.Surface, rect: Rect, label: str, mouse, active=False
    ) -> None:
        hover = rect.collidepoint(mouse)
        if active:
            bg = _COLORS["btn_active"]
        elif hover:
            bg = _COLORS["btn_hover"]
        else:
            bg = _COLORS["btn"]
        pygame.draw.rect(screen, bg, rect, border_radius=3)
        pygame.draw.rect(screen, _COLORS["border"], rect, 1, border_radius=3)
        lbl = self._font_sm.render(label, True, _COLORS["text"])
        screen.blit(lbl, lbl.get_rect(center=rect.center))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_tile(self, variant_id: int) -> Optional[pygame.Surface]:
        tw, th = self.tile_size
        ox, oy = self.grid_offset_x, self.grid_offset_y
        available_w = self.surface.get_width() - ox
        cols = max(1, available_w // tw)
        col = variant_id % cols
        row = variant_id // cols
        src = Rect(ox + col * tw, oy + row * th, tw, th)
        if self.surface.get_rect().contains(src):
            return self.surface.subsurface(src).copy()
        return None

    def _handle_fps_keydown(self, event: pygame.event.Event) -> bool:
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.commit_fps_input()
            return True
        if event.key == pygame.K_ESCAPE:
            self._editing_fps = False
            self._fps_input_text = self._format_fps_display(self.playback_fps)
            return True
        if event.key == pygame.K_BACKSPACE:
            self._fps_input_text = self._fps_input_text[:-1]
            return True
        if event.unicode and len(self._fps_input_text) < 8:
            ch = event.unicode
            if ch.isdigit():
                self._fps_input_text += ch
                return True
            if ch in ".," and "." not in self._fps_input_text.replace(",", "."):
                self._fps_input_text += "."
                return True
        return True

    def _step(self, direction: int) -> None:
        if not self.frames:
            return
        self.playing = False
        self.current_frame = (self.current_frame + direction) % len(self.frames)
        self._elapsed = 0.0

    def _draw_checker(self, screen: pygame.Surface, rect: Rect) -> None:
        if self._checker is None:
            sz = 10
            self._checker = pygame.Surface((sz * 2, sz * 2))
            c1, c2 = (30, 30, 30), (42, 42, 42)
            self._checker.fill(c1)
            pygame.draw.rect(self._checker, c2, (sz, 0, sz, sz))
            pygame.draw.rect(self._checker, c2, (0, sz, sz, sz))
        for y in range(rect.y, rect.bottom, self._checker.get_height()):
            for x in range(rect.x, rect.right, self._checker.get_width()):
                screen.blit(self._checker, (x, y))

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
        if self._font is None:
            self._font = font_manager.get_font(font_family, 13, FontWeight.BOLD)
        if self._font_sm is None:
            self._font_sm = font_manager.get_font(font_family, 11, FontWeight.BOLD)
