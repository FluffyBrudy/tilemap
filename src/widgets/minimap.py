"""Corner minimap: bird's-eye view, viewport rect, click/drag navigate.

Bakes visible tile layers to a cached surface (rebuilt when dirty),
draws the live viewport rectangle every frame, and pans the main view
on click/drag. Tile layers only; objects/images join later.
"""

import pygame
from pygame import Rect

from widgets.ui.theme import COLORS, FONTS

PANEL_W = 200
PANEL_MIN_H = 100
PANEL_MAX_H = 200
PANEL_PAD = 10
MAX_BAKE_DIM = 2048


class MinimapWidget:
    """Always-on corner overlay owned by the editor."""

    def __init__(self, editor):
        self.editor = editor
        self.cache: pygame.Surface | None = None
        self.dirty = True
        self.scale = 1.0
        self.origin = (0, 0)
        self.collapsed = False
        self._dragging = False
        self._sig = None
        self.font = FONTS.get_small_font()

    # ------------------------------------------------------------------ layout

    def _panel_rect(self) -> Rect | None:
        grid = getattr(self.editor, "tile_grid_widget", None)
        if grid is None:
            return None
        r = grid.rect
        tm = self.editor.tilemap
        tw, th = getattr(tm, "map_size", (1, 1))
        aspect = (th / tw) if tw else 1.0
        h = min(PANEL_MAX_H, max(PANEL_MIN_H, int(PANEL_W * aspect)))
        return Rect(r.right - PANEL_W - PANEL_PAD, r.bottom - h - PANEL_PAD,
                    PANEL_W, h)

    def _toggle_rect(self, panel: Rect) -> Rect:
        return Rect(panel.right - 20, panel.y + 2, 16, 16)

    # ------------------------------------------------------------------ state

    def mark_dirty(self):
        self.dirty = True

    def _signature(self):
        tm = self.editor.tilemap
        manager = getattr(tm, "layer_manager", None)
        layers = manager.get_rendered_layers() if manager else []
        try:
            tilesets = getattr(getattr(self.editor, "tileset_widget", None),
                               "tilesets", []) or []
            ts_sig = tuple(getattr(ts, "path", "") for ts in tilesets)
        except Exception:
            ts_sig = ()
        return (tuple(getattr(tm, "map_size", (0, 0))),
                tuple(getattr(tm, "tile_size", (0, 0))),
                len(layers), ts_sig)

    # ------------------------------------------------------------------ bake

    def _rebuild(self, panel: Rect):
        tm = self.editor.tilemap
        tile_w, tile_h = tm.tile_size
        map_w, map_h = tm.map_size
        full_w, full_h = map_w * tile_w, map_h * tile_h
        if full_w <= 0 or full_h <= 0:
            self.cache = None
            self.dirty = False
            self._sig = self._signature()
            return

        step = 1.0
        biggest = max(full_w, full_h)
        if biggest > MAX_BAKE_DIM:
            step = MAX_BAKE_DIM / biggest
        bw, bh = max(1, int(full_w * step)), max(1, int(full_h * step))
        full = pygame.Surface((bw, bh), pygame.SRCALPHA)

        ts_widget = getattr(self.editor, "tileset_widget", None)
        tileset_map = dict(getattr(ts_widget, "tileset_map", {}) or {})
        manager = tm.layer_manager
        sheet_cols_cache: dict = {}
        for layer in manager.get_rendered_layers():
            if layer.layer_type != "tile":
                continue
            for (gx, gy), tile in layer.tiles.items():
                ttype = tile["ttype"]
                ts = tileset_map.get(ttype)
                if ts is None:
                    continue
                vid = tile["variant"]
                if ttype not in sheet_cols_cache:
                    sheet_cols_cache[ttype] = max(
                        1, ts.surface.get_width() // tile_w) if tile_w else 1
                cols = sheet_cols_cache[ttype]
                src = Rect((vid % cols) * tile_w, (vid // cols) * tile_h,
                           tile_w, tile_h)
                if not ts.surface.get_rect().contains(src):
                    continue
                dest = Rect(int(gx * tile_w * step), int(gy * tile_h * step),
                            max(1, int(tile_w * step)), max(1, int(tile_h * step)))
                try:
                    if step == 1.0:
                        full.blit(ts.surface, dest, src)
                    else:
                        cell = ts.surface.subsurface(src).copy()
                        full.blit(pygame.transform.scale(cell, dest.size), dest)
                except (ValueError, pygame.error):
                    continue

        self.scale = min(panel.width / bw, panel.height / bh)
        dw, dh = int(bw * self.scale), int(bh * self.scale)
        try:
            self.cache = pygame.transform.smoothscale(full, (dw, dh))
        except (ValueError, pygame.error):
            self.cache = None
        self.origin = (panel.x + (panel.width - dw) // 2,
                       panel.y + (panel.height - dh) // 2)
        self.dirty = False
        self._sig = self._signature()

    # ------------------------------------------------------------------ viewport

    def _viewport_rect(self) -> Rect | None:
        grid = getattr(self.editor, "tile_grid_widget", None)
        if grid is None or self.cache is None:
            return None
        tm = self.editor.tilemap
        (tw, th) = (tm.tile_size[0], tm.tile_size[1])
        eff_w, eff_h = tw, th
        try:
            rs = tm.render_scale
            eff_w, eff_h = tw * rs, th * rs
        except Exception:
            pass
        ox, oy = tm.offset
        zoom = grid.zoom_level or 1.0
        vw = grid.rect.width / zoom
        vh = grid.rect.height / zoom
        x = self.origin[0] + (grid.scroll_x - ox * eff_w) * self.scale
        y = self.origin[1] + (grid.scroll_y - oy * eff_h) * self.scale
        return Rect(x, y, vw * self.scale, vh * self.scale)

    # ------------------------------------------------------------------ events

    def _navigate(self, pos):
        grid = getattr(self.editor, "tile_grid_widget", None)
        if grid is None or self.cache is None:
            return
        tm = self.editor.tilemap
        tw, th = tm.tile_size
        try:
            rs = tm.render_scale
            tw, th = tw * rs, th * rs
        except Exception:
            pass
        ox, oy = tm.offset
        zoom = grid.zoom_level or 1.0
        wx = (pos[0] - self.origin[0]) / self.scale + ox * tw
        wy = (pos[1] - self.origin[1]) / self.scale + oy * th
        grid.scroll_x = wx - (grid.rect.width / zoom) / 2
        grid.scroll_y = wy - (grid.rect.height / zoom) / 2
        grid.clamp_scroll()

    def handle_event(self, event) -> bool:
        panel = self._panel_rect()
        if panel is None:
            self._dragging = False
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._toggle_rect(panel).collidepoint(event.pos):
                self.collapsed = not self.collapsed
                return True
            if not self.collapsed and panel.collidepoint(event.pos):
                self._dragging = True
                self._navigate(event.pos)
                return True
            return False
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                self._dragging = False
                return True
            return False
        if event.type == pygame.MOUSEMOTION and self._dragging:
            if self.collapsed:
                self._dragging = False
                return False
            self._navigate(event.pos)
            return True
        return False

    # ------------------------------------------------------------------ draw

    def draw(self, screen):
        panel = self._panel_rect()
        if panel is None:
            return
        pygame.draw.rect(screen, COLORS.panel, panel, border_radius=4)
        pygame.draw.rect(screen, COLORS.border, panel, 1, border_radius=4)
        toggle = self._toggle_rect(panel)
        mark = self.font.render("+" if self.collapsed else "-", True, COLORS.text_dim)
        screen.blit(mark, mark.get_rect(center=toggle.center))
        if self.collapsed:
            return
        tm = self.editor.tilemap
        if not getattr(tm, "initialized", False):
            txt = self.font.render("No map", True, COLORS.text_dim)
            screen.blit(txt, txt.get_rect(center=panel.center))
            return
        if self.dirty or self._sig != self._signature() or self.cache is None:
            try:
                self._rebuild(panel)
            except Exception:
                self.cache = None
                self.dirty = False
        if self.cache is not None:
            screen.blit(self.cache, self.origin)
            vp = self._viewport_rect()
            if vp is not None:
                pygame.draw.rect(screen, COLORS.accent, vp, 1)
