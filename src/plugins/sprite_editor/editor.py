"""
SpriteEditor — standalone widget wrapping SpritesheetGrid with editing toolbar.

Toolbar:
  [Flip X] [Flip Y] [Copy] [Paste] [Undo] [Redo] [Scale...] [Save PNG]
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import pygame
from pygame import Rect, Surface

from widgets.spritesheet_grid import SpritesheetGrid
from widgets.ui.theme import COLORS
from widgets.ui.draw_utils import draw_panel, draw_button
from utils.font_manager import font_manager, FontWeight
from utils.icon_manager import icon_manager


TOOLBAR_H = 42
STATUS_H = 22
BTN_W = 64
BTN_H = 28

# Map toolbar labels to icon_manager keys (None = text only)
_BUTTON_ICONS: dict[str, str | None] = {
    "Flip X": None,
    "Flip Y": None,
    "Copy": "duplicate",
    "Paste": None,
    "Undo": None,
    "Redo": None,
    "Scale": None,
    "Save": "save",
}


class SpriteEditor:
    def __init__(
        self,
        rect: Rect,
        surface: Surface,
        tile_size: tuple[int, int],
        image_path: Optional[Path] = None,
        data_root: Optional[Path] = None,
    ):
        self.rect = rect
        self.image_path = image_path
        self._data_root = data_root or (image_path.parent if image_path else Path.cwd())

        # Grid
        grid_rect = Rect(rect.x, rect.y + TOOLBAR_H, rect.w, rect.h - TOOLBAR_H - STATUS_H)
        self.grid = SpritesheetGrid(grid_rect, surface, tile_size)

        # Clipboard for copy/paste
        self._clipboard: Dict[int, Surface] = {}
        self._paste_mode: bool = False

        # Scale dialog state
        self._scale_active: bool = False
        self._scale_text: str = "2.0"
        self._scale_error: Optional[str] = None

        # Save path — never auto-overwrite original
        self._save_path: Optional[Path] = None

        # File manager modal
        self._file_manager: Optional[object] = None

        # Toolbar button rects
        self._btn_rects: dict[str, Rect] = {}
        self._layout_toolbar()

        self._font = font_manager.get_font("monospace", 13, FontWeight.BOLD)
        self._font_sm = font_manager.get_font("monospace", 11, FontWeight.BOLD)

    def _layout_toolbar(self) -> None:
        ty = self.rect.y + (TOOLBAR_H - BTN_H) // 2
        gap = 6
        x = self.rect.x + gap
        labels = ["Flip X", "Flip Y", "Copy", "Paste", "Undo", "Redo", "Scale", "Save"]
        for lbl in labels:
            self._btn_rects[lbl] = Rect(x, ty, BTN_W, BTN_H)
            x += BTN_W + gap

    def _get_status_text(self) -> str:
        parts = [f"Zoom: {self.grid.zoom:.1f}x"]
        sel = len(self.grid.selected_indices)
        if sel:
            parts.append(f"Selected: {sel}")
        if self._paste_mode:
            parts.append("Click grid to paste")
        if self.grid.can_undo:
            parts.append(f"Undo ({len(self.grid._undo_stack)})")
        return "  |  ".join(parts)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        # File manager modal blocks everything
        if self._file_manager is not None:
            return self._file_manager.handle_event(event)

        if self._scale_active:
            return self._handle_scale_dialog(event)

        mouse = pygame.mouse.get_pos()

        # Keyboard shortcuts
        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA)

            if ctrl:
                if event.key == pygame.K_z:
                    if self.grid.undo():
                        self.grid.selected_indices.clear()
                    return True
                elif event.key == pygame.K_y:
                    if self.grid.redo():
                        self.grid.selected_indices.clear()
                    return True

        # Toolbar clicks
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for lbl, r in self._btn_rects.items():
                if r.collidepoint(mouse):
                    return self._handle_tool(lbl)

        # Paste mode: next grid click pastes
        if self._paste_mode and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            idx = self.grid.index_at_pos(mouse)
            if idx >= 0 and self.grid.rect.collidepoint(mouse):
                self.grid.paste_at(idx, self._clipboard)
                self._paste_mode = False
                self.grid.paste_preview_idx = -1
                return True

        # Paste preview on hover
        if self._paste_mode and event.type == pygame.MOUSEMOTION:
            idx = self.grid.index_at_pos(mouse)
            self.grid.paste_preview_idx = idx if idx >= 0 else -1

        return self.grid.handle_event(event)

    def _handle_tool(self, lbl: str) -> bool:
        if lbl == "Flip X":
            if self.grid.has_selection():
                self.grid.flip_selected(True, False)
            return True
        elif lbl == "Flip Y":
            if self.grid.has_selection():
                self.grid.flip_selected(False, True)
            return True
        elif lbl == "Copy":
            if self.grid.has_selection():
                self._clipboard = self.grid.copy_selected()
                self._paste_mode = False
                self.grid.paste_preview_idx = -1
            return True
        elif lbl == "Paste":
            if self._clipboard:
                self._paste_mode = not self._paste_mode
                if not self._paste_mode:
                    self.grid.paste_preview_idx = -1
            return True
        elif lbl == "Undo":
            self.grid.undo()
            self.grid.selected_indices.clear()
            return True
        elif lbl == "Redo":
            self.grid.redo()
            self.grid.selected_indices.clear()
            return True
        elif lbl == "Scale":
            self._scale_active = True
            self._scale_text = "2.0"
            self._scale_error = None
            return True
        elif lbl == "Save":
            self._open_save_dialog()
            return True
        return False

    def _handle_scale_dialog(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                try:
                    factor = float(self._scale_text)
                    if factor <= 0:
                        self._scale_error = "Must be > 0"
                    else:
                        self.grid.scale(factor)
                        self._scale_active = False
                        self._scale_error = None
                except ValueError:
                    self._scale_error = "Invalid number"
                return True
            elif event.key == pygame.K_ESCAPE:
                self._scale_active = False
                self._scale_error = None
                return True
            elif event.key == pygame.K_BACKSPACE:
                self._scale_text = self._scale_text[:-1]
                return True
            elif event.unicode and event.unicode in "0123456789." and len(self._scale_text) < 8:
                self._scale_text += event.unicode
                return True
        return False

    def _open_save_dialog(self) -> None:
        """Open FileManager in save mode to pick a PNG path."""
        from widgets.filemanager import FileManager

        initial_dir = self._save_path.parent if self._save_path else self._data_root
        default_name = self._save_path.name if self._save_path else (
            f"{self.image_path.stem}_edited.png" if self.image_path else "spritesheet.png"
        )

        fm_rect = self._file_manager_rect()
        self._file_manager = FileManager(
            rect=fm_rect,
            initial_dir=initial_dir,
            allowed_exts=[".png"],
            on_save=self._on_save_path_selected,
            mode="save",
            default_name=default_name,
            on_cancel=self._close_file_manager,
            data_root=self._data_root,
        )

    def _on_save_path_selected(self, path: Path) -> None:
        try:
            self.grid.save_png(path)
            self._save_path = path
        except Exception as e:
            print(f"Save failed: {e}")
        self._close_file_manager()

    def _close_file_manager(self) -> None:
        self._file_manager = None

    def _file_manager_rect(self) -> Rect:
        w, h = 600, 400
        cx, cy = self.rect.center
        return Rect(cx - w // 2, cy - h // 2, w, h)

    def set_save_path(self, path: Path) -> None:
        self._save_path = path

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, screen: Surface) -> None:
        draw_panel(screen, self.rect, COLORS.bg, COLORS.border)

        # Toolbar
        toolbar_rect = Rect(self.rect.x, self.rect.y, self.rect.w, TOOLBAR_H)
        draw_panel(screen, toolbar_rect, COLORS.header, COLORS.border)

        mouse = pygame.mouse.get_pos()
        for lbl, r in self._btn_rects.items():
            hover = r.collidepoint(mouse)
            active = (lbl == "Paste" and self._paste_mode)
            disable = (lbl in ("Undo",) and not self.grid.can_undo) or \
                      (lbl in ("Redo",) and not self.grid.can_redo)

            icon_key = _BUTTON_ICONS.get(lbl)
            if icon_key and icon_manager.has_icon(icon_key):
                color = COLORS.text_dim if disable else COLORS.text
                icon = icon_manager.get_icon(icon_key, 18, color)
                draw_button(screen, r, icon, hover=hover and not disable, active=active and not disable)
            else:
                label_surf = self._font_sm.render(lbl, True, COLORS.text_dim if disable else COLORS.text)
                draw_button(screen, r, label_surf, hover=hover and not disable, active=active and not disable)

        # Grid
        if self._file_manager is None:
            self.grid.draw(screen)

        # Status bar
        status_rect = Rect(self.rect.x, self.rect.bottom - STATUS_H, self.rect.w, STATUS_H)
        draw_panel(screen, status_rect, COLORS.header, COLORS.border)
        st = self._get_status_text()
        screen.blit(
            self._font_sm.render(st, True, COLORS.text_dim),
            (status_rect.x + 6, status_rect.y + 4),
        )

        if self._scale_active:
            self._draw_scale_dialog(screen)

        # File manager overlay
        if self._file_manager is not None:
            self._file_manager.draw(screen)

    def _draw_scale_dialog(self, screen: Surface) -> None:
        dw, dh = 260, 100
        cx, cy = self.rect.center
        dlg = Rect(cx - dw // 2, cy - dh // 2, dw, dh)
        draw_panel(screen, dlg, COLORS.panel, COLORS.border)

        title = self._font.render("Scale Factor", True, COLORS.text)
        screen.blit(title, title.get_rect(centerx=dlg.centerx, top=dlg.top + 10))

        inp = Rect(dlg.x + 20, dlg.top + 36, dw - 40, 28)
        pygame.draw.rect(screen, COLORS.selected, inp, border_radius=4)
        pygame.draw.rect(screen, COLORS.accent, inp, 2, border_radius=4)
        txt = self._scale_text + ("|" if (pygame.time.get_ticks() // 400) % 2 else "")
        screen.blit(self._font_sm.render(txt, True, COLORS.text), (inp.x + 6, inp.y + 5))

        if self._scale_error:
            err = self._font_sm.render(self._scale_error, True, COLORS.danger)
            screen.blit(err, (dlg.x + 20, dlg.bottom - 22))

        hint = self._font_sm.render("Enter / Esc", True, COLORS.text_dim)
        screen.blit(hint, (dlg.right - 90, dlg.bottom - 22))
