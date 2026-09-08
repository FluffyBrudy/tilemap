"""Alias Palette — sidebar tab for the reusable pattern-brush library.

Persistent panel (not a dropdown): brush-mode radio (Tileset | Alias),
scope picker, search filter, structural thumbnail grid with arrow-key
navigation. Selecting an alias arms it; it stays active until the user
switches back to Tileset mode. Reloads sidecar files by mtime so the
standalone composer needs no IPC.
"""

from __future__ import annotations

from pathlib import Path

import pygame
from pygame import Rect

from aliases import AliasPattern, AliasScope
from widgets.input import InlineTextInput
from widgets.ui.button import Button
from widgets.ui.theme import COLORS, FONTS

THUMB_BOX = 64
COLS = 3


class AliasPalette:
    """Sidebar widget. Owned by the editor, registered as 'Aliases' tab."""

    def __init__(self, editor, x: int, y: int, w: int, h: int):
        self.editor = editor
        self.rect = Rect(x, y, w, h)
        self.font = FONTS.get_small_font()
        self.font_bold = FONTS.get_bold_font()

        self.search = InlineTextInput("alias_search", "")
        self.search_rect = Rect(0, 0, 0, 0)
        self.btn_tileset = Button(Rect(0, 0, 0, 0), "Tileset",
                                  tooltip_text="Normal single-tile brush",
                                  on_click=lambda: self.set_brush_mode("tileset"))
        self.btn_alias = Button(Rect(0, 0, 0, 0), "Alias",
                                tooltip_text="Paint the armed multi-tile pattern",
                                on_click=lambda: self.set_brush_mode("alias"))
        self.btn_scope = Button(Rect(0, 0, 0, 0), "",
                                tooltip_text="Switch alias file set",
                                on_click=self.cycle_scope)
        self.btn_composer = Button(Rect(0, 0, 0, 0), "Composer…",
                                   tooltip_text="Author patterns in the standalone Composer",
                                   on_click=self.open_composer)
        self.btn_help = Button(Rect(0, 0, 0, 0), "",
                               icon_key="info",
                               tooltip_text="Alias help",
                               on_click=self.toggle_help)
        self.show_help = False

        self.scope_name: str | None = None
        self.scope: AliasScope | None = None
        self.items: list[tuple[str, str, AliasPattern]] = []  # (stem, tileset, pattern)
        self.filtered: list[tuple[str, str, AliasPattern]] = []
        self.selected = 0
        self.scroll = 0
        self.focused = False
        self._thumbs: dict[tuple[str, str], pygame.Surface] = {}
        self.resize(x, y, w, h)
        self.reload_scope_list()
        self.set_brush_mode("tileset")

    # ------------------------------------------------------------------ state
    def aliases_dir(self) -> Path:
        return Path(self.editor.data_root) / self.editor.config.get("aliases_path", "aliases")

    def configured_scopes(self) -> dict[str, list[str]]:
        scopes = self.editor.config.get("alias_scopes", {}) or {}
        return {k: list(v) for k, v in scopes.items() if isinstance(v, list)}

    def reload_scope_list(self) -> None:
        """Rebuild scope from config; fall back to every alias file on disk."""
        scopes = self.configured_scopes()
        if not scopes:
            try:
                stems = sorted(p.stem.replace(".alias", "")
                               for p in self.aliases_dir().glob("*.alias.json"))
            except OSError:
                stems = []
            scopes = {"All": stems} if stems else {}
        if self.scope_name not in scopes:
            self.scope_name = next(iter(scopes), None)
        self.scope = None
        self._thumbs = {}
        if self.scope_name is not None:
            self.scope = AliasScope(self.aliases_dir(), scopes[self.scope_name])
            self.refresh_items(force=True)

    def refresh_items(self, force: bool = False) -> None:
        if self.scope is None:
            self.items, self.filtered = [], []
            return
        if force or self._poll_due():
            if self.scope.changed():
                self.scope.refresh()
                self._thumbs = {}
            self._poll_at = pygame.time.get_ticks()
        self.items = self.scope.all_aliases()
        self.apply_filter()

    def _poll_due(self) -> bool:
        return pygame.time.get_ticks() - getattr(self, "_poll_at", 0) >= 500

    def apply_filter(self) -> None:
        q = self.search.text.strip().lower()
        self.filtered = [it for it in self.items if q in it[2].name.lower()]
        self.selected = max(0, min(self.selected, len(self.filtered) - 1))
        self.scroll = max(0, self.scroll)

    def cycle_scope(self) -> None:
        notes = getattr(self.editor, "notifications", None)
        scopes = list(self.configured_scopes())
        if not scopes:
            self.reload_scope_list()
            if notes is not None:
                if self.scope_name is None:
                    notes.notify("No alias files found in data/aliases")
                else:
                    notes.success(
                        f"Scope: {self.scope_name} ({len(self.filtered)} aliases)")
            return
        if len(scopes) == 1 and self.scope_name in scopes:
            self.refresh_items(force=True)
            if notes is not None:
                notes.notify(
                    f"Only one scope: {scopes[0]} ({len(self.filtered)} aliases)")
            return
        if self.scope_name not in scopes:
            self.scope_name = scopes[0]
        else:
            self.scope_name = scopes[(scopes.index(self.scope_name) + 1) % len(scopes)]
        self.scope = AliasScope(self.aliases_dir(),
                                self.configured_scopes()[self.scope_name])
        self.selected, self.scroll = 0, 0
        self.refresh_items(force=True)
        if notes is not None:
            notes.success(f"Scope: {self.scope_name} ({len(self.filtered)} aliases)")

    def set_brush_mode(self, mode: str) -> None:
        self.editor.brush_mode = mode
        if mode == "alias" and self.filtered:
            self.arm_selected()
        elif mode == "tileset":
            self.editor.active_alias = None

    def arm_selected(self) -> bool:
        """Arm the highlighted alias as the active brush."""
        if not self.filtered:
            return False
        stem, tileset_ref, pattern = self.filtered[self.selected]
        self.editor.brush_mode = "alias"
        self.editor.active_alias = (stem, tileset_ref, pattern)
        return True

    def open_composer(self) -> None:
        self.editor.launch_alias_composer()

    # ------------------------------------------------------------------ tileset
    def _tileset_surface(self, tileset_ref: str):
        """Match an alias tileset ref to a loaded tileset (surface, index)."""
        tw = getattr(self.editor, "tileset_widget", None)
        if tw is None:
            return None, None
        ref = Path(tileset_ref)
        for idx, ts in enumerate(getattr(tw, "tilesets", []) or []):
            p = Path(getattr(ts, "path", "") or "")
            if not p.name:
                continue
            if p.name == ref.name or p.stem == ref.stem:
                return getattr(ts, "surface", None), idx
        return None, None

    def _thumbnail(self, stem: str, tileset_ref: str, pattern: AliasPattern):
        key = (stem, pattern.name)
        if key in self._thumbs:
            return self._thumbs[key]
        surf = pygame.Surface((THUMB_BOX, THUMB_BOX), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        ts_surf, _ = self._tileset_surface(tileset_ref)
        tw, th = self.editor.tilemap.tile_size
        if ts_surf is not None and tw > 0 and th > 0:
            scale = min((THUMB_BOX - 8) / max(1, pattern.w * tw),
                        (THUMB_BOX - 8) / max(1, pattern.h * th))
            cell = max(2, int(min(tw, th) * scale))
            sheet_cols = max(1, ts_surf.get_width() // tw)
            for dx, dy, variant in pattern.cells:
                sx, sy = (variant % sheet_cols) * tw, (variant // sheet_cols) * th
                src = Rect(sx, sy, tw, th)
                if not ts_surf.get_rect().contains(src):
                    continue
                try:
                    tile = pygame.transform.scale(
                        ts_surf.subsurface(src), (cell, cell))
                    surf.blit(tile, (4 + dx * cell, 4 + dy * cell))
                except (ValueError, pygame.error):
                    continue
        else:
            pygame.draw.rect(surf, COLORS.text_dim, surf.get_rect(), 1)
            q = self.font.render("?", True, COLORS.text_dim)
            surf.blit(q, q.get_rect(center=surf.get_rect().center))
        self._thumbs[key] = surf
        return surf

    # ------------------------------------------------------------------ layout
    def resize(self, x: int, y: int, w: int, h: int) -> None:
        self.rect = Rect(x, y, w, h)
        pad = 6
        bw = (w - pad * 3) // 2
        self.btn_tileset.resize(x + pad, y + 22, bw, 24)
        self.btn_alias.resize(x + pad * 2 + bw, y + 22, bw, 24)
        # active-alias label owns y+50; scope/search/grid shift below it
        self.alias_label_rect = Rect(x + pad, y + 50, w - pad * 2, 16)
        self.btn_scope.resize(x + pad, y + 70, w - pad * 2, 24)
        self.search_rect = Rect(x + pad, y + 100, w - pad * 2, 24)
        self.grid_top = y + 130
        self.btn_composer.resize(x + pad, y + h - 30, w - pad * 2 - 40, 24)
        self.btn_help.resize(x + w - pad - 34, y + h - 30, 28, 24)

    def toggle_help(self) -> None:
        self.show_help = not self.show_help

    HELP_LINES = (
        "Alias patterns paint many tiles at once.",
        "",
        "BRUSH Tileset = normal tile brush.",
        "BRUSH Alias = the armed pattern below.",
        "",
        "Top Tilesets tab manages source sheets.",
        "Scope picks which alias files are listed.",
        "Click a pattern to arm it, then paint.",
        "Composer authors new patterns.",
    )

    def _row_of(self, idx: int) -> int:
        return idx // COLS

    # ------------------------------------------------------------------ events
    def handle_event(self, event: pygame.event.Event) -> bool:
        self.refresh_items()
        if self.btn_tileset.handle_event(event):
            return True
        if self.btn_alias.handle_event(event):
            return True
        if self.btn_scope.handle_event(event):
            return True
        if self.btn_composer.handle_event(event):
            return True
        if self.btn_help.handle_event(event):
            return True
        if (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                and self.show_help):
            self.show_help = False
            return True
        mouse = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.search_rect.collidepoint(mouse):
                self.search.is_focused = True
                self.focused = True
                return True
            self.search.is_focused = False
            if self._grid_rect().collidepoint(mouse):
                self.focused = True
                idx = self._index_at(mouse)
                if idx is not None:
                    self.selected = idx
                    self.arm_selected()
                    return True
                return True
            self.focused = False
            return False

        if event.type == pygame.MOUSEWHEEL and self._grid_rect().collidepoint(mouse):
            self.scroll = max(0, self.scroll + (-event.y) * 3 * (THUMB_BOX + 18))
            return True

        if (event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5)
                and self._grid_rect().collidepoint(mouse)):
            step = 3 * (THUMB_BOX + 18)
            self.scroll = max(0, self.scroll + (step if event.button == 5 else -step))
            return True

        if event.type == pygame.KEYDOWN:
            if self.search.is_focused:
                if event.key == pygame.K_ESCAPE:
                    self.search.is_focused = False
                    return True
                if self.search.handle_event(event, self.font):
                    self.apply_filter()
                    return True
                return True
            if not self.focused:
                return False
            if event.key == pygame.K_UP:
                self.selected = max(0, self.selected - COLS)
                self._ensure_visible()
                return True
            if event.key == pygame.K_DOWN:
                self.selected = min(len(self.filtered) - 1, self.selected + COLS)
                self._ensure_visible()
                return True
            if event.key == pygame.K_LEFT:
                self.selected = max(0, self.selected - 1)
                self._ensure_visible()
                return True
            if event.key == pygame.K_RIGHT:
                self.selected = min(len(self.filtered) - 1, self.selected + 1)
                self._ensure_visible()
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self.arm_selected()
            if event.key == pygame.K_ESCAPE:
                self.focused = False
                return True
        return False

    def _grid_rect(self) -> Rect:
        return Rect(self.rect.x, self.grid_top, self.rect.w,
                    self.rect.h - (self.grid_top - self.rect.y) - 36)

    def _index_at(self, pos) -> int | None:
        grid = self._grid_rect()
        cell_w = grid.w // COLS
        lx, ly = pos[0] - grid.x, pos[1] - grid.y + self.scroll
        col, row = lx // cell_w, ly // (THUMB_BOX + 18)
        idx = row * COLS + col
        if 0 <= col < COLS and 0 <= idx < len(self.filtered):
            return idx
        return None

    def _ensure_visible(self) -> None:
        grid = self._grid_rect()
        top = self._row_of(self.selected) * (THUMB_BOX + 18)
        if top < self.scroll:
            self.scroll = top
        elif top + THUMB_BOX + 18 > self.scroll + grid.h:
            self.scroll = top + THUMB_BOX + 18 - grid.h

    # ------------------------------------------------------------------ draw
    def draw(self, screen: pygame.Surface) -> None:
        self.refresh_items()
        mode = getattr(self.editor, "brush_mode", "tileset")
        self.btn_tileset.active = mode == "tileset"
        self.btn_alias.active = mode == "alias"
        head = self.font_bold.render("BRUSH", True, COLORS.text_dim)
        screen.blit(head, (self.rect.x + 6, self.rect.y + 4))
        self.btn_tileset.draw(screen)
        self.btn_alias.draw(screen)
        self.btn_tileset.text, self.btn_alias.text = "Tileset", "Alias"
        if mode == "alias":
            active = getattr(self.editor, "active_alias", None)
            if active:
                lbl = self.font.render(f"Alias: {active[2].name}", True, COLORS.accent)
                screen.blit(lbl, (self.alias_label_rect.x, self.alias_label_rect.y))
        self.btn_scope.text = f"Scope: {self.scope_name or '-'}"
        self.btn_scope.draw(screen)
        pygame.draw.rect(screen, COLORS.panel, self.search_rect, border_radius=4)
        pygame.draw.rect(screen, COLORS.border, self.search_rect, 1, border_radius=4)
        hint = self.search.text if self.search.text or self.search.is_focused else "Search…"
        txt = self.font.render(hint, True, COLORS.text if self.search.text else COLORS.text_dim)
        screen.blit(txt, (self.search_rect.x + 6, self.search_rect.y + 5))
        if self.search.is_focused:
            cx = self.search_rect.x + 6 + txt.get_width() + 1
            pygame.draw.line(screen, COLORS.text,
                             (cx, self.search_rect.y + 5), (cx, self.search_rect.bottom - 5))

        grid = self._grid_rect()
        clip = screen.get_clip()
        screen.set_clip(grid)
        try:
            if not self.filtered:
                empty = self.font.render("No aliases", True, COLORS.text_dim)
                screen.blit(empty, (grid.x + 6, grid.y + 6))
            cell_w = grid.w // COLS
            for i, (stem, ref, pattern) in enumerate(self.filtered):
                row, col = self._row_of(i), i % COLS
                bx = grid.x + col * cell_w + (cell_w - THUMB_BOX) // 2
                by = grid.y + row * (THUMB_BOX + 18) - self.scroll
                if by + THUMB_BOX + 18 < grid.y or by > grid.bottom:
                    continue
                thumb = self._thumbnail(stem, ref, pattern)
                screen.blit(thumb, (bx, by))
                if i == self.selected:
                    pygame.draw.rect(screen, COLORS.accent,
                                     Rect(bx - 2, by - 2, THUMB_BOX + 4, THUMB_BOX + 4), 2)
                name = pattern.name if len(pattern.name) <= 12 else pattern.name[:11] + "…"
                lbl = self.font.render(name, True,
                                       COLORS.text if i == self.selected else COLORS.text_dim)
                screen.blit(lbl, lbl.get_rect(centerx=bx + THUMB_BOX // 2, top=by + THUMB_BOX + 2))
        finally:
            screen.set_clip(clip)
        self.btn_composer.draw(screen)
        self.btn_help.draw(screen)
        self._hover_tooltips()
        if self.show_help:
            self._draw_help(screen)

    def _hover_tooltips(self) -> None:
        tooltip = getattr(self.editor, "tooltip", None)
        if tooltip is None:
            return
        mouse = pygame.mouse.get_pos()
        for btn in (self.btn_tileset, self.btn_alias, self.btn_scope,
                    self.btn_composer, self.btn_help):
            if btn.rect.collidepoint(mouse) and getattr(btn, "tooltip_text", ""):
                tooltip.show(btn.tooltip_text, (mouse[0] + 10, mouse[1] + 10))
                return
        if self.search_rect.collidepoint(mouse):
            tooltip.show("Filter patterns by name", (mouse[0] + 10, mouse[1] + 10))

    def _draw_help(self, screen: pygame.Surface) -> None:
        grid = self._grid_rect()
        box = Rect(grid.x + 4, grid.y + 4, grid.w - 8,
                   len(self.HELP_LINES) * 17 + 30)
        box.h = min(box.h, grid.h - 8)
        pygame.draw.rect(screen, COLORS.panel_alt, box, border_radius=6)
        pygame.draw.rect(screen, COLORS.border, box, 1, border_radius=6)
        title = self.font_bold.render("Alias help  (? to close)", True, COLORS.text)
        screen.blit(title, (box.x + 10, box.y + 8))
        y = box.y + 28
        for line in self.HELP_LINES:
            if line:
                txt = self.font.render(line, True, COLORS.text_dim)
                screen.blit(txt, (box.x + 10, y))
            y += 17
