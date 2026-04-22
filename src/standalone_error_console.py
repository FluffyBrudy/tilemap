#!/usr/bin/env python3
"""
Standalone Error Console - Professional Version
Fixes: Text overlapping, compact layout, font clarity, and unicode support.
Updated: Improved keyboard shortcut handling for Ctrl+Left, Ctrl+Backspace, etc.
"""

import json
import sys
import os
import time
import threading
import textwrap
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Optional
from datetime import datetime

import pygame
from pygame import Rect, Surface, Color, KEYDOWN, K_ESCAPE
from utils.font_manager import font_manager, FontWeight, FontStyle
from utils.icon_manager import icon_manager
import logging

from utils.error_handler import error_handler

# Setup logging for font debugging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))
try:
    from constants import BASE_PATH
except ImportError:
    BASE_PATH = Path(".").absolute()

# ---------------------------------------------------------------------------
# Professional Dev-Tools Palette
# ---------------------------------------------------------------------------
PALETTE_DARK = {
    "bg_primary": (18, 18, 18),  # Deeper dark
    "bg_secondary": (28, 28, 30),  # Elevated surfaces
    "bg_tertiary": (42, 42, 45),  # Hover states
    "border": (45, 45, 48),  # Subtle dividers
    "border_focus": (0, 120, 212),  # VS Code Blue
    "text_primary": (255, 255, 255),  # High emphasis - pure white for max contrast
    "text_secondary": (220, 220, 220),  # Medium emphasis - much brighter
    "text_tertiary": (170, 170, 170),  # Low emphasis - significantly brighter
    "error_stripe": (248, 81, 73),
    "error_bg": (62, 20, 20),
    "warning_stripe": (210, 153, 34),
    "warning_bg": (53, 40, 10),
    "info_stripe": (88, 166, 255),
    "info_bg": (20, 30, 60),
    "dot_live": (35, 209, 96),
    "scrollbar_thumb": (80, 80, 80),
}

C = PALETTE_DARK


class StandaloneErrorConsole:
    def __init__(self, window_size: tuple[int, int] = (1280, 500)):
        pygame.init()
        # Enable better font rendering
        pygame.font.init()
        # Use centralized font manager
        self.font_family = self._auto_select_font()

        self.window_size = window_size
        self.screen = pygame.display.set_mode(window_size, pygame.RESIZABLE)
        pygame.display.set_caption("System Error Console")
        self.clock = pygame.time.Clock()
        self.running = True

        # UI Geometry
        self.x, self.y = 0, 0
        self.width, self.height = window_size
        self.TITLEBAR_H = 35
        self.TOOLBAR_H = 45
        self.STATUSBAR_H = 25
        self.STRIPE_W = 4
        self.LINE_SPACING = 4
        self.CELL_PADDING = 12

        # Initialize Fonts using improved font manager with bold weights for better visibility
        self.f_main = font_manager.get_font(self.font_family, 14, FontWeight.BOLD)
        self.f_bold = font_manager.get_font(self.font_family, 14, FontWeight.BOLD)
        self.f_small = font_manager.get_font(self.font_family, 12, FontWeight.BOLD)
        self.f_code = font_manager.get_font(self.font_family, 13, FontWeight.BOLD)

        # State
        self.search_text = ""
        self.search_active = False
        self.search_focused = False
        self.cursor_pos = 0
        self.selection_start = 0
        self.selection_end = 0
        self.active_filters = {"error", "warning", "info"}
        self._all_entries = []
        self._visible_entries = []
        self._expanded_ids = set()
        self._scroll_offset = 0
        self.mouse_pos = (0, 0)

        self.log_file = BASE_PATH / "data" / "logs" / "errors.log"
        self.last_file_size = 0
        self._load_errors_from_file()

        self._update_layout()

        # Threading
        self.monitor_thread = threading.Thread(target=self._monitor_file, daemon=True)
        self.monitor_thread.start()

    def _get_text_selection(self) -> tuple[int, int]:
        """Get normalized selection start and end positions."""
        if self.selection_start <= self.selection_end:
            return self.selection_start, self.selection_end
        else:
            return self.selection_end, self.selection_start

    def _select_all(self):
        """Select all text in search box."""
        self.selection_start = 0
        self.selection_end = len(self.search_text)
        self.cursor_pos = self.selection_end

    def _delete_selected(self):
        """Delete selected text."""
        start, end = self._get_text_selection()
        if start != end:
            self.search_text = self.search_text[:start] + self.search_text[end:]
            self.cursor_pos = start
            self.selection_start = self.selection_end = self.cursor_pos
            self._refresh_entries()
            return True
        return False

    def _delete_word_left(self):
        """Delete word to the left of cursor."""
        if self._delete_selected():
            return

        # Find start of word
        pos = self.cursor_pos
        while (
            pos > 0
            and pos <= len(self.search_text)
            and self.search_text[pos - 1].isspace()
        ):
            pos -= 1
        while (
            pos > 0
            and pos <= len(self.search_text)
            and not self.search_text[pos - 1].isspace()
        ):
            pos -= 1

        # Only delete if we actually moved the cursor
        if pos < self.cursor_pos:
            self.search_text = (
                self.search_text[:pos] + self.search_text[self.cursor_pos :]
            )
            self.cursor_pos = pos
            self.selection_start = self.selection_end = self.cursor_pos
            self._refresh_entries()

    def _move_cursor_word_left(self, shift_held: bool = False):
        """Move cursor one word left."""
        pos = self.cursor_pos
        while (
            pos > 0
            and pos <= len(self.search_text)
            and self.search_text[pos - 1].isspace()
        ):
            pos -= 1
        while (
            pos > 0
            and pos <= len(self.search_text)
            and not self.search_text[pos - 1].isspace()
        ):
            pos -= 1
        self.cursor_pos = pos
        if not shift_held:
            self.selection_start = self.selection_end = self.cursor_pos
        else:
            self.selection_end = self.cursor_pos

    def _move_cursor_word_right(self, shift_held: bool = False):
        """Move cursor one word right."""
        pos = self.cursor_pos
        while pos < len(self.search_text) and self.search_text[pos].isspace():
            pos += 1
        while pos < len(self.search_text) and not self.search_text[pos].isspace():
            pos += 1
        self.cursor_pos = pos
        if not shift_held:
            self.selection_start = self.selection_end = self.cursor_pos
        else:
            self.selection_end = self.cursor_pos

    def _auto_select_font(self):
        """Returns the best available coding font using centralized font manager."""
        # Try prioritized fonts
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

    def _update_layout(self):
        """Recalculate UI Rects."""
        w = self.width
        # Search Box
        self._search_rect = Rect(15, self.TITLEBAR_H + 10, 250, 26)

        # Filter Buttons
        bx = self._search_rect.right + 15
        self._filter_btns = []
        for sev in ["error", "warning", "info"]:
            bw = 70
            self._filter_btns.append([sev, Rect(bx, self.TITLEBAR_H + 10, bw, 26)])
            bx += bw + 8

        # Clear Button
        self._clear_btn = Rect(w - 90, self.TITLEBAR_H + 10, 75, 26)

        # Content Area
        content_top = self.TITLEBAR_H + self.TOOLBAR_H
        content_h = self.height - content_top - self.STATUSBAR_H
        self.content_rect = Rect(0, content_top, w, content_h)

    def _load_errors_from_file(self):
        if not self.log_file.exists():
            return
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                self._all_entries = []
                for i, line in enumerate(lines):
                    try:
                        data = json.loads(line.strip())
                        data["id"] = i
                        self._all_entries.insert(0, data)
                    except Exception as e:
                        error_handler.capture(
                            e,
                            context=line,
                            severity="warning",
                        )
        except Exception as e:
            error_handler.capture(e, severity="error")
        self._refresh_entries()

    def _monitor_file(self):
        while self.running:
            try:
                if self.log_file.exists():
                    curr = self.log_file.stat().st_size
                    if curr > self.last_file_size:
                        self._load_errors_from_file()
                        self.last_file_size = curr
            except Exception as e:
                error_handler.capture(e, severity="warning")
            time.sleep(1)

    def _refresh_entries(self):
        q = self.search_text.lower()
        self._visible_entries = [
            e
            for e in self._all_entries
            if e.get("severity") in self.active_filters
            and (
                not q
                or q in e.get("message", "").lower()
                or q in e.get("context", "").lower()
            )
        ]

    def _get_entry_layout(self, entry: Dict, width: int) -> Dict[str, Any]:
        """Calculates dynamic height and text wrapping for a specific entry."""
        wrap_w = width - 200  # Space for timestamp and tags
        msg_text = entry.get("message", "No message")
        ctx_text = entry.get("context", "")

        # Wrap message
        msg_lines = textwrap.wrap(msg_text, width=int(wrap_w // 8))
        if not msg_lines:
            msg_lines = [" "]

        # Determine Height
        h = self.CELL_PADDING * 2
        h += len(msg_lines) * 18  # Message height

        if ctx_text:
            h += 18  # Context line

        if entry.get("id") in self._expanded_ids:
            stack = entry.get("stack_trace", "")
            if stack:
                h += (stack.count("\n") + 1) * 16 + 20

        return {"msg_lines": msg_lines, "total_h": max(50, h), "ctx": ctx_text}

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        if event.type == pygame.VIDEORESIZE:
            self.width, self.height = event.w, event.h
            self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            self._update_layout()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left Click
                # Handle search box focus
                if self._search_rect.collidepoint(event.pos):
                    self.search_focused = True
                    # Set cursor position based on click
                    text_surface = self.f_main.render(
                        self.search_text, True, C["text_primary"]
                    )
                    text_width = text_surface.get_width()
                    click_x = (
                        event.pos[0] - self._search_rect.x - 8
                    )  # Account for padding

                    # Approximate cursor position based on click
                    if click_x <= 0:
                        self.cursor_pos = 0
                    elif click_x >= text_width:
                        self.cursor_pos = len(self.search_text)
                    else:
                        # Estimate character position
                        avg_char_width = (
                            text_width / len(self.search_text)
                            if self.search_text
                            else 0
                        )
                        self.cursor_pos = (
                            int(click_x / avg_char_width) if avg_char_width > 0 else 0
                        )
                        self.cursor_pos = max(
                            0, min(self.cursor_pos, len(self.search_text))
                        )

                    self.selection_start = self.selection_end = self.cursor_pos
                else:
                    # Unfocus search if clicking elsewhere
                    self.search_focused = False

                # Handle filter toggles
                for sev, rect in self._filter_btns:
                    if rect.collidepoint(event.pos):
                        if sev in self.active_filters:
                            self.active_filters.discard(sev)
                        else:
                            self.active_filters.add(sev)
                        self._refresh_entries()

                # Handle Clear
                if self._clear_btn.collidepoint(event.pos):
                    self._all_entries = []
                    self._refresh_entries()

                # Handle Entry Expansion
                if self.content_rect.collidepoint(event.pos):
                    rel_y = event.pos[1] - self.content_rect.y + self._scroll_offset
                    curr_y = 0
                    for entry in self._visible_entries:
                        layout = self._get_entry_layout(entry, self.width)
                        if curr_y <= rel_y <= curr_y + layout["total_h"]:
                            eid = entry["id"]
                            if eid in self._expanded_ids:
                                self._expanded_ids.discard(eid)
                            else:
                                self._expanded_ids.add(eid)
                            break
                        curr_y += layout["total_h"]

            if event.button == 4:
                self._scroll_offset = max(0, self._scroll_offset - 40)
            if event.button == 5:
                self._scroll_offset += 40

        if event.type == KEYDOWN:
            # Better mod detection using event.mod
            ctrl_held = event.mod & pygame.KMOD_CTRL
            cmd_held = event.mod & pygame.KMOD_META
            shift_held = event.mod & pygame.KMOD_SHIFT

            # Handle Ctrl+F for search focus
            if event.key == pygame.K_f and ctrl_held:
                self.search_focused = True
                self._select_all()
                return

            # Only handle text input if search is focused
            if self.search_focused:
                # Ctrl+A / Cmd+A - Select all
                if event.key == pygame.K_a and (ctrl_held or cmd_held):
                    self._select_all()
                    return

                # Ctrl+Backspace / Cmd+Backspace - Delete word left
                if event.key == pygame.K_BACKSPACE and (ctrl_held or cmd_held):
                    self._delete_word_left()
                    return

                # Ctrl+Left / Cmd+Left - Move cursor word left
                if event.key == pygame.K_LEFT and (ctrl_held or cmd_held):
                    self._move_cursor_word_left(shift_held)
                    return

                # Ctrl+Right / Cmd+Right - Move cursor word right
                if event.key == pygame.K_RIGHT and (ctrl_held or cmd_held):
                    self._move_cursor_word_right(shift_held)
                    return

                # Regular Backspace - Delete character or selection
                if event.key == pygame.K_BACKSPACE:
                    if not self._delete_selected():
                        if self.cursor_pos > 0:
                            self.search_text = (
                                self.search_text[: self.cursor_pos - 1]
                                + self.search_text[self.cursor_pos :]
                            )
                            self.cursor_pos -= 1
                            self.selection_start = self.selection_end = self.cursor_pos
                    self._refresh_entries()
                    return

                # Left/Right arrows - Move cursor
                if event.key == pygame.K_LEFT:
                    if self.cursor_pos > 0:
                        self.cursor_pos -= 1
                        if not shift_held:
                            self.selection_start = self.selection_end = self.cursor_pos
                        else:
                            self.selection_end = self.cursor_pos
                    return
                elif event.key == pygame.K_RIGHT:
                    if self.cursor_pos < len(self.search_text):
                        self.cursor_pos += 1
                        if not shift_held:
                            self.selection_start = self.selection_end = self.cursor_pos
                        else:
                            self.selection_end = self.cursor_pos
                    return

                # Home/End - Move to start/end
                if event.key == pygame.K_HOME:
                    self.cursor_pos = 0
                    if not shift_held:
                        self.selection_start = self.selection_end = self.cursor_pos
                    else:
                        self.selection_end = self.cursor_pos
                    return
                elif event.key == pygame.K_END:
                    self.cursor_pos = len(self.search_text)
                    if not shift_held:
                        self.selection_start = self.selection_end = self.cursor_pos
                    else:
                        self.selection_end = self.cursor_pos
                    return

                # Printable characters - Insert at cursor position
                if event.unicode.isprintable() and len(event.unicode) > 0:
                    # Ignore control characters that might have escaped filters
                    if not (ctrl_held or cmd_held):
                        if not self._delete_selected():
                            self.search_text = (
                                self.search_text[: self.cursor_pos]
                                + event.unicode
                                + self.search_text[self.cursor_pos :]
                            )
                            self.cursor_pos += 1
                        self.selection_start = self.selection_end = self.cursor_pos
                        self._refresh_entries()
                        return

    def _draw_entries(self):
        """Draws entries with dynamic spacing to prevent overlapping."""
        # Use a list to store entry surfaces to avoid huge surface allocation issues
        # Actually, let's just draw directly to screen with clipping
        content_y = self.content_rect.y
        curr_y = content_y - self._scroll_offset

        for entry in self._visible_entries:
            layout = self._get_entry_layout(entry, self.width)
            eh = layout["total_h"]

            # Clipping: only draw if in view
            if curr_y + eh > self.content_rect.y and curr_y < self.content_rect.bottom:
                sev = entry.get("severity", "info")

                # Row Background
                row_rect = Rect(0, curr_y, self.width, eh)
                if row_rect.collidepoint(self.mouse_pos):
                    pygame.draw.rect(self.screen, C["bg_secondary"], row_rect)

                # Severity Stripe with icon
                pygame.draw.rect(
                    self.screen, C[f"{sev}_stripe"], Rect(0, curr_y, self.STRIPE_W, eh)
                )
                # Severity icon
                icon_name = {
                    "error": "error",
                    "warning": "warning",
                    "info": "info",
                }.get(sev, "info")
                icon_color = C[f"{sev}_stripe"]
                sev_icon = icon_manager.get_icon(icon_name, 14, icon_color)
                self.screen.blit(sev_icon, (8, curr_y + self.CELL_PADDING))

                # 1. Timestamp
                ts = entry.get("timestamp", "")[11:19]
                ts_surf = self.f_small.render(ts, True, C["text_tertiary"])
                self.screen.blit(ts_surf, (15, curr_y + self.CELL_PADDING))

                # 2. Tag
                tag_col = C[f"{sev}_stripe"]
                tag_rect = Rect(85, curr_y + self.CELL_PADDING - 2, 65, 18)
                pygame.draw.rect(self.screen, tag_col, tag_rect, 1, border_radius=3)
                tag_txt = self.f_small.render(sev.upper(), True, tag_col)
                self.screen.blit(
                    tag_txt,
                    (
                        tag_rect.centerx - tag_txt.get_width() // 2,
                        tag_rect.centery - tag_txt.get_height() // 2,
                    ),
                )

                # 3. Message (Wrapped)
                text_x = 165
                text_y = curr_y + self.CELL_PADDING
                for i, line in enumerate(layout["msg_lines"]):
                    m_surf = self.f_main.render(line, True, C["text_primary"])
                    self.screen.blit(m_surf, (text_x, text_y))
                    text_y += 18

                # 4. Context (Below Message)
                if layout["ctx"]:
                    # Arrow icon for context
                    arrow_icon = icon_manager.get_icon(
                        "arrow-down", 10, C["text_secondary"]
                    )
                    self.screen.blit(arrow_icon, (text_x, text_y + 2))
                    c_surf = self.f_small.render(
                        f" {layout['ctx']}", True, C["text_secondary"]
                    )
                    self.screen.blit(c_surf, (text_x + 12, text_y))
                    text_y += 18

                # 5. Expanded Stack Trace
                if entry["id"] in self._expanded_ids:
                    stack = entry.get("stack_trace", "")
                    if stack:
                        pygame.draw.rect(
                            self.screen,
                            (10, 10, 10),
                            Rect(
                                text_x,
                                text_y + 5,
                                self.width - text_x - 20,
                                eh - (text_y - curr_y) - 10,
                            ),
                            border_radius=4,
                        )
                        for s_line in stack.split("\n"):
                            st_surf = self.f_code.render(
                                s_line, True, C["text_secondary"]
                            )
                            self.screen.blit(st_surf, (text_x + 10, text_y + 10))
                            text_y += 16

                # Divider
                pygame.draw.line(
                    self.screen,
                    C["border"],
                    (0, curr_y + eh - 1),
                    (self.width, curr_y + eh - 1),
                )

            curr_y += eh

    def draw(self):
        self.screen.fill(C["bg_primary"])
        self.mouse_pos = pygame.mouse.get_pos()

        # 1. Main Content (drawn first so it's behind overlays)
        self._draw_entries()

        # 2. Header Overlay (Title Bar + Toolbar)
        # Background for header
        pygame.draw.rect(
            self.screen,
            C["bg_primary"],
            (0, 0, self.width, self.TITLEBAR_H + self.TOOLBAR_H),
        )

        # Title Bar
        pygame.draw.rect(
            self.screen, C["bg_secondary"], (0, 0, self.width, self.TITLEBAR_H)
        )
        title = self.f_bold.render("ERROR CONSOLE", True, C["text_secondary"])
        self.screen.blit(title, (self.width // 2 - title.get_width() // 2, 10))

        # Search Box
        bg_color = C["bg_primary"] if self.search_focused else C["bg_secondary"]
        border_color = C["border_focus"] if self.search_focused else C["border"]

        pygame.draw.rect(self.screen, bg_color, self._search_rect, border_radius=4)
        pygame.draw.rect(
            self.screen, border_color, self._search_rect, 1, border_radius=4
        )

        # Draw selection highlight if any
        if self.search_focused and self.selection_start != self.selection_end:
            start, end = self._get_text_selection()
            if start < end:
                before_text = self.search_text[:start]
                selected_text = self.search_text[start:end]

                before_surface = self.f_main.render(
                    before_text, True, C["text_primary"]
                )
                selected_surface = self.f_main.render(
                    selected_text, True, C["text_primary"]
                )

                sel_x = self._search_rect.x + 8 + before_surface.get_width()
                sel_width = selected_surface.get_width()
                sel_rect = Rect(
                    sel_x,
                    self._search_rect.y + 2,
                    sel_width,
                    self._search_rect.height - 4,
                )
                pygame.draw.rect(self.screen, (60, 90, 150), sel_rect, border_radius=2)

        # Draw text
        display_text = self.search_text if self.search_text else "Filter logs (type...)"
        text_color = C["text_primary"] if self.search_text else C["text_tertiary"]
        text_surface = self.f_main.render(display_text, True, text_color)
        self.screen.blit(
            text_surface, (self._search_rect.x + 8, self._search_rect.y + 5)
        )

        # Draw cursor
        if self.search_focused:
            cursor_text = self.search_text[: self.cursor_pos]
            cursor_surface = self.f_main.render(cursor_text, True, C["text_primary"])
            cursor_x = self._search_rect.x + 8 + cursor_surface.get_width()
            if int(time.time() * 2) % 2 == 0:
                pygame.draw.line(
                    self.screen,
                    C["text_primary"],
                    (cursor_x, self._search_rect.y + 4),
                    (cursor_x, self._search_rect.y + self._search_rect.height - 4),
                    2,
                )

        # Filters
        for sev, rect in self._filter_btns:
            active = sev in self.active_filters
            bg = C[f"{sev}_bg"] if active else C["bg_secondary"]
            pygame.draw.rect(self.screen, bg, rect, border_radius=4)
            pygame.draw.rect(
                self.screen,
                C[f"{sev}_stripe"] if active else C["border"],
                rect,
                1,
                border_radius=4,
            )
            color = C["text_primary"] if active else C["text_tertiary"]
            txt = self.f_small.render(sev, True, color)
            self.screen.blit(
                txt,
                (
                    rect.centerx - txt.get_width() // 2,
                    rect.centery - txt.get_height() // 2,
                ),
            )

        # Clear
        pygame.draw.rect(
            self.screen, C["bg_secondary"], self._clear_btn, border_radius=4
        )
        ctxt = self.f_small.render("Clear All", True, C["text_secondary"])
        self.screen.blit(
            ctxt,
            (
                self._clear_btn.centerx - ctxt.get_width() // 2,
                self._clear_btn.centery - ctxt.get_height() // 2,
            ),
        )

        # 3. Status Bar
        pygame.draw.rect(
            self.screen,
            C["bg_secondary"],
            (0, self.height - self.STATUSBAR_H, self.width, self.STATUSBAR_H),
        )
        pygame.draw.circle(self.screen, C["dot_live"], (15, self.height - 12), 4)
        stat_txt = self.f_small.render(
            f"Monitoring: {self.log_file.name} | Shown: {len(self._visible_entries)}",
            True,
            C["text_secondary"],
        )
        self.screen.blit(stat_txt, (30, self.height - 18))

        pygame.display.flip()

    def run(self):
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)
            self.draw()
            self.clock.tick(60)
        pygame.quit()


if __name__ == "__main__":
    console = StandaloneErrorConsole()
    console.run()
