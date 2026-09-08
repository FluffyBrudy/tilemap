"""Alias Composer — standalone grid painter for tile-pattern brushes.

Layout: toolbar (top), alias list (left), canvas (center), tileset
strip (bottom). The canvas is the plot preview: paint/erase exactly
as the pattern will plot on the map.

Keys: paint LMB-drag, erase RMB-drag, wheel zoom, middle-drag/space pan,
N new alias, F2 rename, Delete remove, [/] canvas width, ;/' height,
Ctrl+S save, Ctrl+L reload, Esc quit.
"""

from __future__ import annotations

from pathlib import Path

import pygame
from pygame import Rect

from aliases import AliasFile, AliasPattern, alias_path_for
from utils.error_handler import error_handler
from utils.font_manager import FontWeight, font_manager
from widgets.ui.button import Button
from widgets.ui.splitter import Splitter
from widgets.ui.theme import COLORS, FONTS
from widgets.ui.toast import ToastManager
from widgets.ui.tooltip import TooltipManager

TOOLBAR_H = 40
LIST_W = 220
STRIP_H = 200
STATUS_H = 26
MIN_CANVAS = 1
MAX_CANVAS = 32
UNDO_LIMIT = 50


class AliasComposerEditor:
    """Standalone alias authoring editor (see standalone.py)."""

    def __init__(
        self,
        rect: Rect,
        tileset_surface: pygame.Surface,
        tile_size: tuple[int, int] = (32, 32),
    ):
        self.rect = Rect(rect)
        self.tileset_surface = tileset_surface.convert_alpha()
        self.tile_size = (int(tile_size[0]), int(tile_size[1]))
        tw, th = self.tile_size
        sw, sh = self.tileset_surface.get_size()
        self.sheet_cols = max(1, sw // tw)
        self.sheet_rows = max(1, sh // th)

        self.brush_rect = (0, 0, 1, 1)  # tileset-tile rect (sx, sy, w, h)
        self.canvas_w, self.canvas_h = 8, 8
        self.cells: dict[tuple[int, int], int] = {}
        self.aliases: list[AliasPattern] = []
        self.selected_alias_idx = -1
        self.dirty = False

        self.canvas_zoom = 1.0
        self.canvas_pan = [0.0, 0.0]
        self._panning = False
        self.strip_h = STRIP_H
        self.ts_zoom = 1.0
        self.ts_scroll_x = 0
        self.ts_scroll_y = 0
        self._ts_panning = False
        self._splitter = Splitter(orientation="horizontal")
        self._splitter.on_drag = self._on_splitter_drag
        self._undo: list = []
        self._redo: list = []
        self._stroke_checkpointed = False
        self._esc_armed = False
        self._brush_anchor: tuple[int, int] | None = None
        self.list_scroll = 0
        self._renaming = False
        self._rename_buf = ""
        self._status = ""
        self._space_held = False

        self._data_root: Path | None = None
        self._save_path: Path | None = None
        self._tileset_ref = ""
        self._tileset_stem = ""

        self._font = font_manager.get_font(FONTS.name, FONTS.size_md, FontWeight.REGULAR)
        self._font_sm = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)
        self.toasts = ToastManager()
        self.tooltip = TooltipManager()
        self.show_help = False

        self._toolbar_buttons: list[tuple[Button, int]] = []
        self._setup_toolbar_buttons()
        self._update_layout()

    # ------------------------------------------------------------------ setup
    def start_rename(self) -> bool:
        """Begin inline rename of the selected alias."""
        if 0 <= self.selected_alias_idx < len(self.aliases):
            self._renaming = True
            self._rename_buf = self.aliases[self.selected_alias_idx].name
            return True
        self.toasts.warning("Select an alias to rename")
        return False

    HELP_LINES = (
        "Paint the pattern exactly as it will plot.",
        "",
        "Canvas: drag paint, right-drag erase.",
        "Tileset sheet below: drag selects the brush.",
        "W-/W+/H-/H+ resize the grid (kept per alias).",
        "N new alias, F2 or double-click renames,",
        "Delete removes, Ctrl+Z / Ctrl+Y undo.",
        "Ctrl+S saves the alias file, Esc quits.",
    )

    def toggle_help(self) -> None:
        self.show_help = not self.show_help

    def _setup_toolbar_buttons(self) -> None:
        self._toolbar_buttons = []
        tips = {
            "Save": "Save alias file (Ctrl+S)",
            "New": "New alias (N)",
            "Rename": "Rename selected (F2)",
            "Delete": "Delete selected (Del)",
            "Clear": "Clear canvas",
            "W-": "Grid narrower", "W+": "Grid wider",
            "H-": "Grid shorter", "H+": "Grid taller",
        }
        for label, width, action in [
            ("Save", 80, self.save_to_save_path),
            ("New", 80, self.new_alias),
            ("Rename", 80, self.start_rename),
            ("Delete", 80, self.delete_selected_alias),
            ("Clear", 80, self.clear_canvas),
            ("W-", 44, lambda: self.resize_canvas(self.canvas_w - 1, self.canvas_h)),
            ("W+", 44, lambda: self.resize_canvas(self.canvas_w + 1, self.canvas_h)),
            ("H-", 44, lambda: self.resize_canvas(self.canvas_w, self.canvas_h - 1)),
            ("H+", 44, lambda: self.resize_canvas(self.canvas_w, self.canvas_h + 1)),
        ]:
            self._toolbar_buttons.append((Button(
                Rect(0, 0, width, 28), label,
                tooltip_text=tips.get(label, ""),
                on_click=action), width))
        self._toolbar_buttons.append((Button(
            Rect(0, 0, 30, 28), "", icon_key="info",
            tooltip_text="Composer help",
            on_click=self.toggle_help), 30))

    def _update_layout(self) -> None:
        r = self.rect
        self.toolbar_rect = Rect(r.x, r.y, r.w, TOOLBAR_H)
        self.status_rect = Rect(r.x, r.bottom - STATUS_H, r.w, STATUS_H)
        self.strip_rect = Rect(r.x, r.bottom - STATUS_H - self.strip_h,
                               r.w, self.strip_h)
        self._splitter.resize(r.x, self.strip_rect.y - 4, r.w, 8)
        self.list_rect = Rect(r.x, r.y + TOOLBAR_H, LIST_W,
                              self.strip_rect.y - 4 - (r.y + TOOLBAR_H))
        self.canvas_rect = Rect(
            r.x + LIST_W, r.y + TOOLBAR_H,
            r.w - LIST_W, self.strip_rect.y - 4 - (r.y + TOOLBAR_H))
        gap = 8
        total = sum(w for _, w in self._toolbar_buttons) + gap * (len(self._toolbar_buttons) - 1)
        bx = self.toolbar_rect.right - total - 10
        by = self.toolbar_rect.y + (TOOLBAR_H - 28) // 2
        for btn, w in self._toolbar_buttons:
            btn.resize(bx, by, w, 28)
            bx += w + gap

    def _on_splitter_drag(self, pos_y: int) -> None:
        r = self.rect
        self.strip_h = max(80, min(r.h - 200, r.bottom - STATUS_H - pos_y))
        self._update_layout()

    # ------------------------------------------------------------- model ops
    def _mark_dirty(self) -> None:
        self.dirty = True
        self._esc_armed = False

    def _has_alias(self) -> bool:
        """An alias exists and is selected — the only state that can plot."""
        return 0 <= self.selected_alias_idx < len(self.aliases)

    def _need_alias(self) -> bool:
        """Toast + status guidance when plotting without an alias."""
        if self._has_alias():
            return True
        self._status = "Create an alias first (New button or N)"
        self.toasts.warning("Create an alias first (New button or N)")
        return False

    def new_alias(self, name: str | None = None) -> AliasPattern:
        # keep current work where it belongs before switching away
        self.store_canvas_to_selected()
        base = name or f"Alias {len(self.aliases) + 1}"
        taken = {a.name for a in self.aliases}
        candidate, n = base, 2
        while candidate in taken:
            candidate = f"{base} {n}"
            n += 1
        alias = AliasPattern(name=candidate, w=8, h=8, cells=[])
        self.aliases.append(alias)
        self.selected_alias_idx = len(self.aliases) - 1
        # fresh canvas: a new alias must never inherit previous tiles
        self.canvas_w, self.canvas_h = 8, 8
        self.cells = {}
        self._fit_canvas()
        self._status = f"New alias '{candidate}' — fresh canvas, paint, then Save"
        self.toasts.success(f"New alias '{candidate}' — paint, then Save")
        return alias

    def delete_selected_alias(self) -> bool:
        if 0 <= self.selected_alias_idx < len(self.aliases):
            gone = self.aliases.pop(self.selected_alias_idx)
            self.selected_alias_idx = min(self.selected_alias_idx, len(self.aliases) - 1)
            # canvas must follow the selection, never show the deleted alias
            if self.aliases:
                self.load_alias_to_canvas(self.selected_alias_idx)
            else:
                self.canvas_w, self.canvas_h = 8, 8
                self.cells = {}
                self._fit_canvas()
            self._mark_dirty()
            self._status = f"Deleted '{gone.name}' (Save to persist)"
            self.toasts.warning(f"Deleted '{gone.name}' — Save to persist")
            return True
        return False

    def load_alias_to_canvas(self, idx: int) -> bool:
        if not (0 <= idx < len(self.aliases)):
            return False
        alias = self.aliases[idx]
        self.selected_alias_idx = idx
        self.canvas_w, self.canvas_h = alias.w, alias.h
        self.cells = {(dx, dy): v for dx, dy, v in alias.cells}
        self._fit_canvas()
        return True

    def store_canvas_to_selected(self) -> bool:
        """Write the canvas back into the selected alias (dirty, unsaved)."""
        if not (0 <= self.selected_alias_idx < len(self.aliases)):
            return False
        alias = self.aliases[self.selected_alias_idx]
        alias.w, alias.h = self.canvas_w, self.canvas_h
        alias.cells = sorted(
            (x, y, v) for (x, y), v in self.cells.items())
        self._mark_dirty()
        return True

    def clear_canvas(self) -> None:
        if not self._need_alias():
            return
        if not self.cells:
            return
        self._checkpoint()
        self.cells = {}
        self._mark_dirty()

    def resize_canvas(self, w: int, h: int) -> None:
        w = max(MIN_CANVAS, min(MAX_CANVAS, w))
        h = max(MIN_CANVAS, min(MAX_CANVAS, h))
        if (w, h) == (self.canvas_w, self.canvas_h):
            return
        self._checkpoint()
        self.canvas_w, self.canvas_h = w, h
        self.cells = {(x, y): v for (x, y), v in self.cells.items()
                      if x < w and y < h}
        self._mark_dirty()

    # ------------------------------------------------------------- undo/redo
    def _snapshot(self) -> tuple[dict, int, int]:
        return (dict(self.cells), self.canvas_w, self.canvas_h)

    def _restore(self, snap: tuple[dict, int, int]) -> None:
        cells, w, h = snap
        self.cells = dict(cells)
        self.canvas_w, self.canvas_h = w, h
        self._mark_dirty()

    def _checkpoint(self) -> None:
        """Push pre-mutation canvas state; called once per stroke."""
        self._undo.append(self._snapshot())
        if len(self._undo) > UNDO_LIMIT:
            self._undo.pop(0)
        self._redo.clear()

    def undo_canvas(self) -> bool:
        if not self._undo:
            self._status = "Nothing to undo"
            self.toasts.warning("Nothing to undo")
            return False
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        self._status = "Undone"
        return True

    def redo_canvas(self) -> bool:
        if not self._redo:
            self._status = "Nothing to redo"
            self.toasts.warning("Nothing to redo")
            return False
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        self._status = "Redone"
        return True

    def get_alias_file(self) -> AliasFile:
        return AliasFile(tileset=self._tileset_ref, aliases=list(self.aliases))

    # ------------------------------------------------------------ persistence
    def _default_save_path(self) -> Path | None:
        if self._data_root is None:
            return None
        return alias_path_for(Path(self._data_root) / "aliases", self._tileset_stem)

    def confirm_quit(self) -> bool:
        """Two-step quit: renaming cancels, dirty warns once, else quits."""
        if self._renaming:
            self._renaming = False
            return False
        if self.dirty and not self._esc_armed:
            self._esc_armed = True
            self._status = "Unsaved changes — Ctrl+S to save, Esc again to discard"
            self.toasts.warning("Unsaved changes — Ctrl+S to save, Esc again to discard")
            return False
        return True

    def save_to_file(self, path: str | Path) -> None:
        # canvas edits belong to the selected alias on save
        self.store_canvas_to_selected()
        path = Path(path)
        self.get_alias_file().save(path)
        self._save_path = path
        self.dirty = False
        self._esc_armed = False
        self._status = f"Saved {path.name}"
        self.toasts.success(f"Saved {path.name}")

    def save_to_save_path(self) -> None:
        path = self._save_path or self._default_save_path()
        if path is None:
            self._status = "No save path (need --load or --data-root)"
            return
        try:
            self.save_to_file(path)
        except OSError as e:
            error_handler.capture(e, context="alias_composer_save")
            self._status = f"Save failed: {e}"
            self.toasts.error(f"Save failed: {e}")

    def load_from_file(self, path: str | Path) -> bool:
        path = Path(path)
        if not path.exists():
            return False
        af = AliasFile.load(path)
        self.aliases = af.aliases
        if af.tileset:
            self._tileset_ref = af.tileset
        self._save_path = path
        self.selected_alias_idx = -1
        self.cells = {}
        if self.aliases:
            self.load_alias_to_canvas(0)
        self.dirty = False
        self._esc_armed = False
        self._status = f"Loaded {path.name} ({len(self.aliases)} aliases)"
        self.toasts.success(f"Loaded {path.name}")
        return True

    @classmethod
    def from_path(
        cls,
        tileset_path: Path,
        tile_size: tuple[int, int] = (32, 32),
        window_size: tuple[int, int] = (1200, 800),
        data_root: Path | None = None,
        tileset_ref: str = "",
    ) -> AliasComposerEditor:
        surface = pygame.image.load(tileset_path).convert_alpha()
        editor = cls(Rect(0, 0, window_size[0], window_size[1]), surface, tile_size)
        editor._data_root = Path(data_root) if data_root else None
        editor._tileset_stem = Path(tileset_path).stem
        editor._tileset_ref = tileset_ref or Path(tileset_path).name
        editor._fit_canvas()
        sw, sh = editor.tileset_surface.get_size()
        if sw > 0 and editor.strip_rect.w > 32:
            editor.ts_zoom = max(0.25, min(2.0, (editor.strip_rect.w - 16) / sw))
            editor._clamp_ts_scroll()
        return editor

    # ------------------------------------------------------------------ view
    def _fit_canvas(self) -> None:
        tw, th = self.tile_size
        if self.canvas_rect.w <= 0 or self.canvas_rect.h <= 0:
            return
        self.canvas_zoom = min(self.canvas_rect.w / max(1, self.canvas_w * tw),
                               self.canvas_rect.h / max(1, self.canvas_h * th))
        self.canvas_zoom = max(0.25, min(4.0, self.canvas_zoom))
        self.canvas_pan = [0.0, 0.0]

    def _canvas_origin(self) -> tuple[float, float]:
        tw, th = self.tile_size
        cw, ch = self.canvas_w * tw * self.canvas_zoom, self.canvas_h * th * self.canvas_zoom
        ox = self.canvas_rect.x + (self.canvas_rect.w - cw) / 2 + self.canvas_pan[0]
        oy = self.canvas_rect.y + (self.canvas_rect.h - ch) / 2 + self.canvas_pan[1]
        return ox, oy

    def _canvas_cell_at(self, pos) -> tuple[int, int] | None:
        ox, oy = self._canvas_origin()
        tw, th = self.tile_size
        step_x, step_y = tw * self.canvas_zoom, th * self.canvas_zoom
        cx = int((pos[0] - ox) // step_x)
        cy = int((pos[1] - oy) // step_y)
        if 0 <= cx < self.canvas_w and 0 <= cy < self.canvas_h:
            return cx, cy
        return None

    def _sheet_scale(self) -> float:
        tw, th = self.tile_size
        return (tw * self.ts_zoom, th * self.ts_zoom)

    def _sheet_origin(self) -> tuple[float, float]:
        return (self.strip_rect.x + 8 - self.ts_scroll_x,
                self.strip_rect.y + 34 - self.ts_scroll_y)

    def _sheet_size(self) -> tuple[int, int]:
        sw, sh = self.tileset_surface.get_size()
        return (max(1, int(sw * self.ts_zoom)), max(1, int(sh * self.ts_zoom)))

    def _clamp_ts_scroll(self) -> None:
        cw, ch = self._sheet_size()
        max_x = max(0, cw + 16 - self.strip_rect.w)
        max_y = max(0, ch + 40 - self.strip_rect.h)
        self.ts_scroll_x = max(0, min(self.ts_scroll_x, max_x))
        self.ts_scroll_y = max(0, min(self.ts_scroll_y, max_y))

    def _sheet_tile_at(self, pos) -> tuple[int, int] | None:
        """Tileset-tile (col, row) under a mouse pos, or None."""
        if not self.strip_rect.collidepoint(pos):
            return None
        stw, sth = self._sheet_scale()
        ox, oy = self._sheet_origin()
        col = int((pos[0] - ox) // stw)
        row = int((pos[1] - oy) // sth)
        if 0 <= col < self.sheet_cols and 0 <= row < self.sheet_rows:
            return col, row
        return None

    def _brush_variant_at(self, bx: int, by: int) -> int:
        """Sheet variant id of a brush-local cell (clamped into the brush)."""
        sx, sy, w, h = self.brush_rect
        bx = max(0, min(w - 1, bx))
        by = max(0, min(h - 1, by))
        return (sy + by) * self.sheet_cols + (sx + bx)

    def _stamp_brush_at(self, ax: int, ay: int) -> bool:
        """Stamp the brush rect anchored at a canvas cell. Returns changed."""
        changed = False
        _, _, w, h = self.brush_rect
        for by in range(h):
            for bx in range(w):
                cx, cy = ax + bx, ay + by
                if not (0 <= cx < self.canvas_w and 0 <= cy < self.canvas_h):
                    continue
                v = self._brush_variant_at(bx, by)
                if self.cells.get((cx, cy)) != v:
                    self.cells[(cx, cy)] = v
                    changed = True
        if changed:
            self._mark_dirty()
        return changed

    def _tile_surface(self, variant: int) -> pygame.Surface:
        tw, th = self.tile_size
        surf = pygame.Surface((tw, th), pygame.SRCALPHA)
        sx = (variant % self.sheet_cols) * tw
        sy = (variant // self.sheet_cols) * th
        src = Rect(sx, sy, tw, th)
        if self.tileset_surface.get_rect().contains(src):
            surf.blit(self.tileset_surface, (0, 0), src)
        return surf

    # ------------------------------------------------------------------ events
    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.VIDEORESIZE:
            self.rect = Rect(0, 0, event.w, event.h)
            self._update_layout()
            return True
        for btn, _ in self._toolbar_buttons:
            if btn.handle_event(event):
                return True
        if self._splitter.handle_event(event):
            return True
        if event.type == pygame.KEYDOWN:
            return self._handle_key(event)
        if event.type == pygame.KEYUP:
            if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                pass
            if event.key == pygame.K_SPACE:
                self._space_held = False
            return False
        mouse = pygame.mouse.get_pos()
        if event.type == pygame.MOUSEWHEEL:
            mods = pygame.key.get_mods()
            if self.strip_rect.collidepoint(mouse):
                if mods & (pygame.KMOD_CTRL | pygame.KMOD_META):
                    self.ts_zoom = max(0.25, min(3.0, self.ts_zoom * (1.15 if event.y > 0 else 1 / 1.15)))
                    self._clamp_ts_scroll()
                elif mods & pygame.KMOD_SHIFT:
                    self.ts_scroll_x = max(0, self.ts_scroll_x + event.y * -40)
                    self._clamp_ts_scroll()
                else:
                    self.ts_scroll_y = max(0, self.ts_scroll_y + event.y * -40)
                    self._clamp_ts_scroll()
                return True
            if self.list_rect.collidepoint(mouse):
                self.list_scroll = max(0, self.list_scroll + event.y * -28)
                return True
            if self.canvas_rect.collidepoint(mouse):
                self.canvas_zoom = max(0.25, min(4.0, self.canvas_zoom * (1.1 if event.y > 0 else 1 / 1.1)))
                return True
            return False
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 2 and self.strip_rect.collidepoint(mouse):
                self._ts_panning = True
                self._ts_pan_start = mouse
                self._ts_pan_base = (self.ts_scroll_x, self.ts_scroll_y)
                return True
            if event.button == 2 or (event.button == 1 and self._space_held
                                     and self.canvas_rect.collidepoint(mouse)):
                self._panning = True
                self._pan_start = mouse
                self._pan_base = list(self.canvas_pan)
                return True
            if event.button == 1:
                if self.strip_rect.collidepoint(mouse):
                    if self._space_held:
                        self._ts_panning = True
                        self._ts_pan_start = mouse
                        self._ts_pan_base = (self.ts_scroll_x, self.ts_scroll_y)
                        return True
                    tile = self._sheet_tile_at(mouse)
                    if tile is not None:
                        self._brush_anchor = tile
                        self._brushing = True
                        self.brush_rect = (tile[0], tile[1], 1, 1)
                        return True
                if self.list_rect.collidepoint(mouse):
                    idx = (mouse[1] - self.list_rect.y + self.list_scroll - 26) // 28
                    if 0 <= idx < len(self.aliases):
                        now = pygame.time.get_ticks()
                        last = getattr(self, "_last_click_at", None)
                        if (idx == self.selected_alias_idx and last is not None
                                and now - last < 400):
                            self._last_click_at = None
                            self.start_rename()
                            return True
                        self._last_click_at = now
                        self.store_canvas_to_selected()
                        self.load_alias_to_canvas(idx)
                        self._status = f"Editing '{self.aliases[idx].name}'"
                        return True
                if self.canvas_rect.collidepoint(mouse):
                    cell = self._canvas_cell_at(mouse)
                    if cell is not None:
                        if not self._need_alias():
                            return True
                        if not self._stroke_checkpointed:
                            self._stroke_checkpointed = True
                            pre = self._snapshot()
                            if self._stamp_brush_at(*cell):
                                self._undo.append(pre)
                                if len(self._undo) > UNDO_LIMIT:
                                    self._undo.pop(0)
                                self._redo.clear()
                        self._painting = True
                        return True
            if event.button == 3 and self.canvas_rect.collidepoint(mouse):
                if not self._need_alias():
                    return True
                cell = self._canvas_cell_at(mouse)
                if cell is not None and cell in self.cells:
                    if not self._stroke_checkpointed:
                        self._checkpoint()
                        self._stroke_checkpointed = True
                    del self.cells[cell]
                    self._mark_dirty()
                self._erasing = True
                return True
        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 2 and self._ts_panning:
                self._ts_panning = False
                return True
            if event.button == 2 and self._panning:
                self._panning = False
                return True
            if event.button == 1:
                self._painting = False
                self._stroke_checkpointed = False
                self._brushing = False
                self._brush_anchor = None
                if self._panning:
                    self._panning = False
                    return True
            if event.button == 3:
                self._erasing = False
                self._stroke_checkpointed = False
                return True
        if event.type == pygame.MOUSEMOTION:
            if self._ts_panning:
                self.ts_scroll_x = max(0, self._ts_pan_base[0] - (mouse[0] - self._ts_pan_start[0]))
                self.ts_scroll_y = max(0, self._ts_pan_base[1] - (mouse[1] - self._ts_pan_start[1]))
                self._clamp_ts_scroll()
                return True
            if getattr(self, "_brushing", False) and self._brush_anchor is not None:
                t = self._sheet_tile_at(mouse)
                if t is not None:
                    x0, y0 = self._brush_anchor
                    self.brush_rect = (min(x0, t[0]), min(y0, t[1]),
                                       abs(t[0] - x0) + 1, abs(t[1] - y0) + 1)
                return True
            if self._panning:
                self.canvas_pan[0] = self._pan_base[0] + mouse[0] - self._pan_start[0]
                self.canvas_pan[1] = self._pan_base[1] + mouse[1] - self._pan_start[1]
                return True
            if getattr(self, "_painting", False) and self.canvas_rect.collidepoint(mouse):
                cell = self._canvas_cell_at(mouse)
                if cell is not None:
                    self._stamp_brush_at(*cell)
                return True
            if getattr(self, "_erasing", False) and self.canvas_rect.collidepoint(mouse):
                cell = self._canvas_cell_at(mouse)
                if cell is not None and cell in self.cells:
                    del self.cells[cell]
                    self._mark_dirty()
                return True
        return False

    def _handle_key(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_SPACE:
            self._space_held = True
            return True
        mods = pygame.key.get_mods()
        ctrl = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)
        if self._renaming:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                name = self._rename_buf.strip()
                if name and 0 <= self.selected_alias_idx < len(self.aliases):
                    names = {a.name for i, a in enumerate(self.aliases)
                             if i != self.selected_alias_idx}
                    if name not in names:
                        self.aliases[self.selected_alias_idx].name = name
                        self._mark_dirty()
                        self._status = f"Renamed to '{name}'"
                    else:
                        self.toasts.warning(f"Name '{name}' is already used")
                self._renaming = False
                return True
            if event.key == pygame.K_ESCAPE:
                self._renaming = False
                return True
            if event.key == pygame.K_BACKSPACE:
                self._rename_buf = self._rename_buf[:-1]
                return True
            if event.unicode and event.unicode.isprintable() and len(self._rename_buf) < 40:
                self._rename_buf += event.unicode
                return True
            return True
        if ctrl and event.key == pygame.K_s:
            self.save_to_save_path()
            return True
        if ctrl and event.key == pygame.K_z:
            if mods & pygame.KMOD_SHIFT:
                return self.redo_canvas()
            return self.undo_canvas()
        if ctrl and event.key == pygame.K_y:
            return self.redo_canvas()
        if ctrl and event.key == pygame.K_l:
            path = self._save_path or self._default_save_path()
            if path is not None and self.load_from_file(path):
                return True
            self._status = "Nothing to load"
            self.toasts.warning("Nothing to load")
            return True
        if event.key == pygame.K_n:
            self.store_canvas_to_selected()
            self.new_alias()
            return True
        if event.key == pygame.K_F2:
            self.start_rename()
            return True
        if event.key in (pygame.K_DELETE, pygame.K_BACKSPACE):
            return self.delete_selected_alias()
        if event.key == pygame.K_LEFTBRACKET:
            self.resize_canvas(self.canvas_w - 1, self.canvas_h)
            return True
        if event.key == pygame.K_RIGHTBRACKET:
            self.resize_canvas(self.canvas_w + 1, self.canvas_h)
            return True
        if event.key == pygame.K_SEMICOLON:
            self.resize_canvas(self.canvas_w, self.canvas_h - 1)
            return True
        if event.key == pygame.K_QUOTE:
            self.resize_canvas(self.canvas_w, self.canvas_h + 1)
            return True
        return False

    # ------------------------------------------------------------------ draw
    def draw(self, screen: pygame.Surface) -> None:
        screen.fill(COLORS.bg)
        pygame.draw.rect(screen, COLORS.header, self.toolbar_rect)
        title = self._font.render("Alias Composer", True, COLORS.text)
        screen.blit(title, (self.toolbar_rect.x + 10, self.toolbar_rect.y + 10))
        for btn, _ in self._toolbar_buttons:
            btn.draw(screen)
        self._draw_list(screen)
        self._draw_canvas(screen)
        self._draw_strip(screen)
        self._splitter.draw(screen)
        self._hover_tooltips()
        if self.show_help:
            self._draw_help(screen)
        pygame.draw.rect(screen, COLORS.header, self.status_rect)
        dirty = " • modified" if self.dirty else ""
        msg = self._status if self._status else (
            "LMB paint • RMB erase • wheel zoom • N new • F2 rename • Del delete • "
            "Ctrl+Z/Y undo/redo • drag bar above tileset to resize")
        txt = self._font_sm.render(f"{msg}{dirty}", True, COLORS.text_dim)
        screen.blit(txt, (self.status_rect.x + 8, self.status_rect.y + 6))

    def _hover_tooltips(self) -> None:
        mouse = pygame.mouse.get_pos()
        for btn, _ in self._toolbar_buttons:
            if btn.rect.collidepoint(mouse) and getattr(btn, "tooltip_text", ""):
                self.tooltip.show(btn.tooltip_text, (mouse[0] + 10, mouse[1] + 10))
                return

    def _draw_help(self, screen: pygame.Surface) -> None:
        box = Rect(0, 0, 460, len(self.HELP_LINES) * 17 + 52)
        box.center = self.canvas_rect.center
        box.clamp_ip(self.rect)
        pygame.draw.rect(screen, COLORS.panel_alt, box, border_radius=6)
        pygame.draw.rect(screen, COLORS.border, box, 1, border_radius=6)
        title = self._font.render("Alias Composer  (? to close)", True, COLORS.text)
        screen.blit(title, (box.x + 12, box.y + 10))
        y = box.y + 34
        for line in self.HELP_LINES:
            if line:
                txt = self._font_sm.render(line, True, COLORS.text_dim)
                screen.blit(txt, (box.x + 12, y))
            y += 17

    def _draw_list(self, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, COLORS.panel, self.list_rect)
        head = self._font_sm.render("ALIASES", True, COLORS.text_dim)
        screen.blit(head, (self.list_rect.x + 8, self.list_rect.y + 8))
        clip = screen.get_clip()
        screen.set_clip(Rect(self.list_rect.x, self.list_rect.y + 26,
                             self.list_rect.w, self.list_rect.h - 26))
        try:
            y = self.list_rect.y + 26 - self.list_scroll
            for i, alias in enumerate(self.aliases):
                row = Rect(self.list_rect.x + 4, y, self.list_rect.w - 8, 26)
                if row.bottom < self.list_rect.y or row.y > self.list_rect.bottom:
                    y += 28
                    continue
                if i == self.selected_alias_idx:
                    pygame.draw.rect(screen, COLORS.accent_active, row, border_radius=4)
                renaming_here = self._renaming and i == self.selected_alias_idx
                label = self._rename_buf if renaming_here else alias.name
                if renaming_here:
                    pygame.draw.rect(screen, COLORS.accent, row, 2, border_radius=4)
                    label += "|"
                txt = self._font_sm.render(
                    f"{label} ({alias.w}x{alias.h})", True, COLORS.text)
                screen.blit(txt, (row.x + 8, row.y + 5))
                y += 28
        finally:
            screen.set_clip(clip)

    def _draw_canvas(self, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, COLORS.bg, self.canvas_rect)
        pygame.draw.rect(screen, COLORS.border, self.canvas_rect, 1)
        if not self.aliases:
            hint = self._font.render("Press N or New for your first alias", True, COLORS.text_dim)
            screen.blit(hint, hint.get_rect(center=self.canvas_rect.center))
            return
        ox, oy = self._canvas_origin()
        tw, th = self.tile_size
        step_x, step_y = tw * self.canvas_zoom, th * self.canvas_zoom
        for (cx, cy), variant in self.cells.items():
            dest = Rect(ox + cx * step_x, oy + cy * step_y,
                        max(1, int(step_x)), max(1, int(step_y)))
            try:
                tile = self._tile_surface(variant)
                if dest.size != (tw, th):
                    tile = pygame.transform.scale(tile, dest.size)
                screen.blit(tile, dest)
            except (ValueError, pygame.error):
                continue
        for gx in range(self.canvas_w + 1):
            x = ox + gx * step_x
            pygame.draw.line(screen, COLORS.border, (x, oy), (x, oy + self.canvas_h * step_y))
        for gy in range(self.canvas_h + 1):
            y = oy + gy * step_y
            pygame.draw.line(screen, COLORS.border, (ox, y), (ox + self.canvas_w * step_x, y))
        sx, sy, bw, bh = self.brush_rect
        info = self._font_sm.render(
            f"{self.canvas_w}x{self.canvas_h}  brush={bw}x{bh}", True, COLORS.text_dim)
        screen.blit(info, (self.canvas_rect.x + 8, self.canvas_rect.y + 8))

    def _draw_strip(self, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, COLORS.panel, self.strip_rect)
        sx, sy, bw, bh = self.brush_rect
        head = self._font_sm.render(
            f"TILESET  brush {bw}x{bh} @ {sx},{sy}  "
            "(drag select, wheel scroll, ctrl+wheel zoom, space/middle drag pan)",
            True, COLORS.text_dim)
        screen.blit(head, (self.strip_rect.x + 8, self.strip_rect.y + 8))
        stw, sth = self._sheet_scale()
        ox, oy = self._sheet_origin()
        clip = screen.get_clip()
        screen.set_clip(self.strip_rect)
        try:
            cw, ch = self._sheet_size()
            try:
                sheet = pygame.transform.scale(self.tileset_surface, (cw, ch))
                screen.blit(sheet, (ox, oy))
            except (ValueError, pygame.error):
                pass
            for gx in range(self.sheet_cols + 1):
                x = ox + gx * stw
                pygame.draw.line(screen, COLORS.border, (x, oy), (x, oy + ch))
            for gy in range(self.sheet_rows + 1):
                y = oy + gy * sth
                pygame.draw.line(screen, COLORS.border, (ox, y), (ox + cw, y))
            brush = Rect(ox + sx * stw, oy + sy * sth, bw * stw, bh * sth)
            pygame.draw.rect(screen, COLORS.accent, brush, 2)
        finally:
            screen.set_clip(clip)

    # ------------------------------------------------------------------ run
    def run(self) -> None:
        screen = pygame.display.get_surface()
        if screen is None:
            raise RuntimeError("pygame display not initialized")
        clock = pygame.time.Clock()
        running = True
        while running:
            dt = clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.show_help:
                        self.show_help = False
                    elif self.confirm_quit():
                        running = False
                self.handle_event(event)
            self.tooltip.hide()
            self.draw(screen)
            self.toasts.update(screen, dt)
            self.toasts.draw(screen)
            pygame.display.flip()
