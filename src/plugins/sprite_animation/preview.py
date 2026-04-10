"""
Animation Preview — real-time playback of the current animation.

Shows a zoomed-up view of the animation playing with optional
onion-skin ghosting. Provides Play / Pause / Stop / Speed / Loop controls.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import pygame
from pygame import Rect

from .models import AnimationFrame

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
}

HEADER_H = 22
CONTROLS_H = 32
SPEED_PRESETS = [0.25, 0.5, 1.0, 1.5, 2.0, 3.0]


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
        self.speed = 1.0
        self.show_onion = False

        self.current_frame: int = 0
        self._elapsed: float = 0.0

        self._zoom = 3.0

        # Buttons (recalculated in draw)
        self._btn_play = Rect(0, 0, 0, 0)
        self._btn_stop = Rect(0, 0, 0, 0)
        self._btn_loop = Rect(0, 0, 0, 0)
        self._btn_speed = Rect(0, 0, 0, 0)
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

    def set_surface(self, surface: pygame.Surface, tile_size: Optional[Tuple[int, int]] = None) -> None:
        self.surface = surface
        if tile_size:
            self.tile_size = tile_size

    def resize(self, rect: Rect) -> None:
        self.rect = rect

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

        self._elapsed += dt_ms * self.speed
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
            elapsed_to_cur = sum(f.duration_ms for f in self.frames[: self.current_frame]) + self._elapsed
            self.scrubber_frac = elapsed_to_cur / total
        else:
            self.scrubber_frac = 0.0

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse = pygame.mouse.get_pos()
        if not self.rect.collidepoint(mouse):
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
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
                return True
            if self._btn_speed.collidepoint(mouse):
                self._cycle_speed()
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
        screen.blit(self._font.render(title, True, _COLORS["text"]), (hdr.x + 6, hdr.y + 3))

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
                        (int(self.tile_size[0] * self._zoom), int(self.tile_size[1] * self._zoom)),
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
        play_label = "⏸" if self.playing else "▶"
        self._draw_btn(screen, self._btn_play, play_label, mouse, active=self.playing)
        x += bw + pad

        # Stop
        self._btn_stop = Rect(x, y, bw, bh)
        self._draw_btn(screen, self._btn_stop, "⏹", mouse)
        x += bw + pad

        # >>| (next)
        self._btn_next = Rect(x, y, bw, bh)
        self._draw_btn(screen, self._btn_next, "▶|", mouse)
        x += bw + pad + 4

        # Loop toggle
        self._btn_loop = Rect(x, y, bw + 4, bh)
        self._draw_btn(screen, self._btn_loop, "🔁", mouse, active=self.loop)
        x += bw + pad + 8

        # Speed
        self._btn_speed = Rect(x, y, 44, bh)
        self._draw_btn(screen, self._btn_speed, f"{self.speed:.1f}x", mouse)
        x += 48 + pad

        # Onion skin
        if x + bw + 12 < ctrl_rect.right:
            self._btn_onion = Rect(x, y, bw + 4, bh)
            self._draw_btn(screen, self._btn_onion, "👻", mouse, active=self.show_onion)

    def _draw_btn(self, screen: pygame.Surface, rect: Rect, label: str, mouse, active=False) -> None:
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
        cols = max(1, self.surface.get_width() // tw)
        col = variant_id % cols
        row = variant_id // cols
        src = Rect(col * tw, row * th, tw, th)
        if self.surface.get_rect().contains(src):
            return self.surface.subsurface(src).copy()
        return None

    def _cycle_speed(self) -> None:
        try:
            idx = SPEED_PRESETS.index(self.speed)
            self.speed = SPEED_PRESETS[(idx + 1) % len(SPEED_PRESETS)]
        except ValueError:
            self.speed = 1.0

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

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("Arial", 13)
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("Arial", 11)
