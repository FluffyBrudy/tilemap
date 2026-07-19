from __future__ import annotations

from pathlib import Path

import pygame
from pygame import SRCALPHA, Rect, Surface

from widgets.spritesheet_grid import SpritesheetGrid
from widgets.ui.button import Button
from widgets.ui.draw_utils import draw_panel
from widgets.ui.region_selector import Region, RegionSelector
from widgets.ui.status_bar import StatusBar, StatusType
from widgets.ui.theme import COLORS, FONTS

from .dialogs import GridSizeDialog, ScaleDialog
from .region_export import (
    export_all_regions,
    load_regions_json,
    regions_sidecar_path,
    save_regions_json,
)

TOOLBAR_H = 42
STATUS_H = 26
BTN_W = 60
BTN_H = 28
BTN_GAP = 5
SEP_W = 8


class SpriteEditor:
    def __init__(
        self,
        rect: Rect,
        surface: Surface | None = None,
        tile_size: tuple[int, int] = (32, 32),
        image_path: Path | None = None,
        data_root: Path | None = None,
    ):
        self.rect = rect
        self.image_path = image_path
        self._data_root = data_root or (image_path.parent if image_path else Path.cwd())

        self._content_rect = self._calc_content_rect()
        if surface is None:
            placeholder = Surface((1, 1), SRCALPHA)
            self._sheet_surfaces: list[Surface] = []
        else:
            placeholder = surface
            self._sheet_surfaces = [surface]

        self.grid = SpritesheetGrid(Rect(self._content_rect), placeholder, tile_size)

        self._clipboard: dict[int, Surface] = {}
        self._paste_mode: bool = False

        self._save_path: Path | None = None
        self._file_manager: object | None = None

        
        self._mode: str = "grid"

        
        self._region_selector = RegionSelector(
            Rect(self._content_rect),
            image=placeholder if self._sheet_surfaces else None,
        )

        
        self._scale_dialog = ScaleDialog(self.rect)
        self._grid_dialog = GridSizeDialog(self.rect)

        
        self._status_bar = StatusBar(
            Rect(rect.x, rect.bottom - STATUS_H, rect.w, STATUS_H),
        )
        self._update_status()

        
        self._buttons: list[Button] = []
        self._separator_xs: list[int] = []
        self._build_toolbar()

    
    
    

    def _calc_content_rect(self) -> Rect:
        return Rect(
            self.rect.x,
            self.rect.y + TOOLBAR_H,
            self.rect.w,
            self.rect.h - TOOLBAR_H - STATUS_H,
        )

    def resize(self, x: int, y: int, w: int, h: int) -> None:
        """Resize the editor and cascade to all child widgets."""
        self.rect = Rect(x, y, w, h)
        self._content_rect = self._calc_content_rect()
        self.grid.rect = Rect(self._content_rect)
        self._region_selector.resize(Rect(self._content_rect))
        self._status_bar.resize(Rect(self.rect.x, self.rect.bottom - STATUS_H, self.rect.w, STATUS_H))
        self._scale_dialog.editor_rect = self.rect
        self._grid_dialog.editor_rect = self.rect
        self._build_toolbar()

    def _build_toolbar(self) -> None:
        """Create toolbar Button instances with separators."""
        self._buttons.clear()
        self._separator_xs.clear()

        ty = self.rect.y + (TOOLBAR_H - BTN_H) // 2
        x = self.rect.x + BTN_GAP + 2

        def add_btn(text: str, *, icon_key: str = "", tooltip: str = "", on_click=None, tag: str = "") -> Button:
            nonlocal x
            btn = Button(
                Rect(x, ty, BTN_W, BTN_H),
                text=text if not icon_key else "",
                icon_key=icon_key or None,
                tooltip_text=tooltip or text,
                border_radius=3,
                on_click=on_click or (lambda: None),
            )
            btn._tag = tag or text.lower().replace(" ", "_")
            self._buttons.append(btn)
            x += BTN_W + BTN_GAP
            return btn

        def sep() -> None:
            nonlocal x
            self._separator_xs.append(x + SEP_W // 2)
            x += SEP_W

        
        add_btn("Flip X", tooltip="Flip Horizontal", on_click=self._on_flip_x, tag="flip_x")
        add_btn("Flip Y", tooltip="Flip Vertical", on_click=self._on_flip_y, tag="flip_y")
        sep()

        
        add_btn("Copy", icon_key="duplicate", tooltip="Copy (Ctrl+C)", on_click=self._on_copy, tag="copy")
        add_btn("Paste", tooltip="Paste (Ctrl+V)", on_click=self._on_paste, tag="paste")
        sep()

        
        add_btn("Undo", tooltip="Undo (Ctrl+Z)", on_click=self._on_undo, tag="undo")
        add_btn("Redo", tooltip="Redo (Ctrl+Y)", on_click=self._on_redo, tag="redo")
        sep()

        
        add_btn("Scale", tooltip="Scale spritesheet", on_click=self._on_scale, tag="scale")
        add_btn("Grid", tooltip="Change tile size", on_click=self._on_grid, tag="grid")
        sep()

        
        add_btn("Open", tooltip="Open spritesheets", on_click=self._on_open, tag="open")
        add_btn("Save", icon_key="save", tooltip="Save PNG", on_click=self._on_save, tag="save")
        sep()

        
        add_btn("Regions", tooltip="Toggle region mode", on_click=self._on_toggle_regions, tag="regions")
        add_btn("Export", tooltip="Export all regions", on_click=self._on_export_all, tag="export_all")

    def _get_btn(self, tag: str) -> Button | None:
        for btn in self._buttons:
            if getattr(btn, "_tag", "") == tag:
                return btn
        return None

    
    
    

    def _on_flip_x(self) -> None:
        if self.grid.has_selection():
            self.grid.flip_selected(True, False)
            self._status_bar.success("Flipped horizontally")

    def _on_flip_y(self) -> None:
        if self.grid.has_selection():
            self.grid.flip_selected(False, True)
            self._status_bar.success("Flipped vertically")

    def _on_copy(self) -> None:
        if self.grid.has_selection():
            self._clipboard = self.grid.copy_selected()
            self._paste_mode = False
            self.grid.paste_preview_idx = -1
            n = len(self._clipboard)
            self._status_bar.info(f"Copied {n} tile{'s' if n != 1 else ''}")

    def _on_paste(self) -> None:
        if self._clipboard:
            self._paste_mode = not self._paste_mode
            if not self._paste_mode:
                self.grid.paste_preview_idx = -1
                self._status_bar.clear()
            else:
                self._status_bar.info("Click grid to paste", detail="Esc to cancel")

    def _on_undo(self) -> None:
        if self.grid.undo():
            self.grid.selected_indices.clear()
            self._status_bar.info("Undo")

    def _on_redo(self) -> None:
        if self.grid.redo():
            self.grid.selected_indices.clear()
            self._status_bar.info("Redo")

    def _on_scale(self) -> None:
        self._scale_dialog.show_scale(
            on_apply=self._apply_scale,
        )

    def _apply_scale(self, factor: float) -> None:
        self.grid.scale(factor)
        self._status_bar.success(f"Scaled ×{factor:.2f}")

    def _on_grid(self) -> None:
        self._grid_dialog.show_grid(
            on_apply=self._apply_grid_size,
            current_size=self.grid.tile_size,
        )

    def _apply_grid_size(self, tw: int, th: int) -> None:
        self.grid.set_tile_size(tw, th)
        self._status_bar.success(f"Tile size: {tw}×{th}")

    def _on_open(self) -> None:
        self._open_add_sheets_dialog()

    def _on_save(self) -> None:
        self._open_save_dialog()

    def _on_toggle_regions(self) -> None:
        if self._mode == "grid":
            self._mode = "regions"
            
            if self._sheet_surfaces:
                self._region_selector.set_image(self.grid.surface)
            self._status_bar.info("Region mode", detail="Draw regions to export")
        else:
            self._mode = "grid"
            self._status_bar.clear()

    def _on_export_all(self) -> None:
        regions = self._region_selector.get_regions()
        if not regions:
            self._status_bar.warning("No regions defined")
            return
        if not self._sheet_surfaces:
            self._status_bar.warning("No spritesheet loaded")
            return
        self._open_export_dir_dialog(regions)

    
    
    

    def _update_status(self) -> None:
        """Update status bar with current editor state."""
        n = len(self._sheet_surfaces)
        if n == 0:
            self._status_bar.set_status(
                "No spritesheets loaded",
                StatusType.NEUTRAL,
                detail="Click [Open] to load",
            )
            return

        tw, th = self.grid.tile_size
        parts = [f"Tile: {tw}×{th}", f"Zoom: {self.grid.zoom:.1f}x"]
        if n > 1:
            parts.append(f"Sheets: {n}")
        sel = len(self.grid.selected_indices)
        if sel:
            parts.append(f"Sel: {sel}")
        if self._paste_mode:
            parts.append("Paste mode")
        if self._mode == "regions":
            nr = len(self._region_selector.regions)
            parts.append(f"Regions: {nr}")

        self._status_bar.set_status(
            "  |  ".join(parts),
            StatusType.INFO,
        )

    
    
    

    def _update_button_states(self) -> None:
        """Sync active/enabled states for toolbar buttons."""
        paste_btn = self._get_btn("paste")
        if paste_btn:
            paste_btn.active = self._paste_mode

        undo_btn = self._get_btn("undo")
        if undo_btn:
            undo_btn.enabled = self.grid.can_undo

        redo_btn = self._get_btn("redo")
        if redo_btn:
            redo_btn.enabled = self.grid.can_redo

        regions_btn = self._get_btn("regions")
        if regions_btn:
            regions_btn.active = self._mode == "regions"

        export_btn = self._get_btn("export_all")
        if export_btn:
            export_btn.enabled = (
                self._mode == "regions" and len(self._region_selector.regions) > 0 and len(self._sheet_surfaces) > 0
            )

    
    
    

    def handle_event(self, event: pygame.event.Event) -> bool:

        
        if self._file_manager is not None:
            return self._file_manager.handle_event(event)

        
        if self._scale_dialog.active:
            return self._scale_dialog.handle_event(event)
        if self._grid_dialog.active:
            return self._grid_dialog.handle_event(event)

        
        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & (pygame.KMOD_LCTRL | pygame.KMOD_LMETA)

            if ctrl:
                if event.key == pygame.K_z:
                    self._on_undo()
                    return True
                if event.key == pygame.K_y:
                    self._on_redo()
                    return True
                if event.key == pygame.K_c:
                    self._on_copy()
                    return True
                if event.key == pygame.K_x:
                    if self.grid.has_selection():
                        self._clipboard = self.grid.cut_selected()
                        self._status_bar.info("Cut")
                    return True
                if event.key == pygame.K_v:
                    self._on_paste()
                    return True

            
            if event.key == pygame.K_ESCAPE:
                if self._paste_mode:
                    self._paste_mode = False
                    self.grid.paste_preview_idx = -1
                    self._status_bar.clear()
                    return True
                if self._mode == "regions":
                    self._mode = "grid"
                    self._status_bar.clear()
                    return True

        
        for btn in self._buttons:
            if btn.handle_event(event):
                return True

        
        mouse = pygame.mouse.get_pos()
        if self._paste_mode:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                idx = self.grid.index_at_pos(mouse)
                if idx >= 0 and self.grid.rect.collidepoint(mouse):
                    self.grid.paste_at(idx, self._clipboard)
                    self._status_bar.success("Pasted")
                self._paste_mode = False
                self.grid.paste_preview_idx = -1
                return True
            if event.type == pygame.MOUSEMOTION:
                idx = self.grid.index_at_pos(mouse)
                self.grid.paste_preview_idx = idx if idx >= 0 else -1
                return True

        
        if self._mode == "regions":
            return self._region_selector.handle_event(event)
        return self.grid.handle_event(event)

    
    
    

    def draw(self, screen: Surface) -> None:
        
        draw_panel(screen, self.rect, COLORS.bg, COLORS.border)

        
        toolbar_rect = Rect(self.rect.x, self.rect.y, self.rect.w, TOOLBAR_H)
        draw_panel(screen, toolbar_rect, COLORS.header, COLORS.border)

        
        sep_h = 16
        sep_y = toolbar_rect.centery - sep_h // 2
        for sx in self._separator_xs:
            pygame.draw.line(
                screen,
                COLORS.border_soft,
                (sx, sep_y),
                (sx, sep_y + sep_h),
                2,
            )

        
        self._update_button_states()
        for btn in self._buttons:
            btn.draw(screen)

        
        if self._file_manager is None:
            if self._mode == "regions":
                self._region_selector.draw(screen)
            else:
                self.grid.draw(screen)

        
        self._update_status()
        self._status_bar.draw(screen)

        
        if self._scale_dialog.active:
            self._scale_dialog.draw(screen)
        if self._grid_dialog.active:
            self._grid_dialog.draw(screen)

        
        if self._file_manager is not None:
            self._file_manager.draw(screen)

        
        mouse_pos = pygame.mouse.get_pos()
        for btn in self._buttons:
            if btn.rect.collidepoint(mouse_pos) and btn.tooltip_text:
                self._draw_tooltip(screen, btn.tooltip_text, mouse_pos)
                break

    def _draw_tooltip(self, screen: Surface, text: str, pos: tuple[int, int]) -> None:
        """Draw a simple tooltip near the cursor."""
        font = FONTS.get_small_font()
        surf = font.render(text, True, COLORS.text)
        tw, th = surf.get_size()
        pad = 4
        tx = pos[0] + 12
        ty = pos[1] + 16
        
        if tx + tw + pad * 2 > screen.get_width():
            tx = pos[0] - tw - pad * 2 - 4
        bg = Rect(tx - pad, ty - pad, tw + pad * 2, th + pad * 2)
        pygame.draw.rect(screen, COLORS.panel, bg, border_radius=3)
        pygame.draw.rect(screen, COLORS.border_soft, bg, 1, border_radius=3)
        screen.blit(surf, (tx, ty))

    
    
    

    @staticmethod
    def _detect_tile_size(surface: Surface) -> tuple[int, int]:
        w, h = surface.get_size()
        candidates = [8, 12, 16, 24, 32, 48, 64, 128]
        best = 8
        for s in candidates:
            if w % s == 0 and h % s == 0:
                best = s
        return (best, best)

    def _file_manager_rect(self) -> Rect:
        w, h = 600, 400
        cx, cy = self.rect.center
        return Rect(cx - w // 2, cy - h // 2, w, h)

    def _close_file_manager(self) -> None:
        self._file_manager = None

    def _open_save_dialog(self) -> None:
        """Open FileManager in save mode to pick a PNG path."""
        from widgets.filemanager import FileManager

        initial_dir = self._save_path.parent if self._save_path else self._data_root
        default_name = (
            self._save_path.name
            if self._save_path
            else (f"{self.image_path.stem}_edited.png" if self.image_path else "spritesheet.png")
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
            pygame.image.save(self.grid.surface, str(path))
            self.set_save_path(path)
            self._status_bar.success(f"Saved {path.name}")
        except Exception as e:
            self._status_bar.error(f"Save failed: {e}")
        self._close_file_manager()

    def _open_add_sheets_dialog(self) -> None:
        """Open FileManager in multi-select mode to pick one or more sheets."""
        from widgets.filemanager import FileManager

        fm_rect = self._file_manager_rect()
        self._file_manager = FileManager(
            rect=fm_rect,
            initial_dir=self._data_root,
            allowed_exts=[".png", ".jpg", ".jpeg", ".bmp", ".gif"],
            on_select=self._on_add_sheets,
            mode="open",
            on_cancel=self._close_file_manager,
            multi_select=True,
            data_root=self._data_root,
        )

    def _on_add_sheets(self, selection: Path | list[Path]) -> None:
        if isinstance(selection, Path):
            selection = [selection]
        was_empty = len(self._sheet_surfaces) == 0
        loaded = 0
        for path in selection:
            try:
                surf = pygame.image.load(str(path)).convert_alpha()
                self._sheet_surfaces.append(surf)
                loaded += 1
            except Exception as e:
                self._status_bar.error(f"Failed: {path.name}: {e}")
        if loaded:
            if was_empty:
                detected = self._detect_tile_size(self._sheet_surfaces[0])
                self.grid.set_tile_size(*detected)
            self._build_combined_surface()
            self._status_bar.success(f"Loaded {loaded} sheet{'s' if loaded != 1 else ''}")
        self._close_file_manager()

    def _build_combined_surface(self) -> None:
        """Rebuild the combined surface from all loaded sheets (stacked vertically)."""
        n = len(self._sheet_surfaces)
        if n == 0:
            return
        if n == 1:
            self.grid.set_surface(self._sheet_surfaces[0])
            self._region_selector.set_image(self._sheet_surfaces[0])
            return

        max_w = max(s.get_width() for s in self._sheet_surfaces)
        total_h = sum(s.get_height() for s in self._sheet_surfaces)
        combined = Surface((max_w, total_h), SRCALPHA)
        combined.fill((0, 0, 0, 0))
        y = 0
        for surf in self._sheet_surfaces:
            combined.blit(surf, (0, y))
            y += surf.get_height()
        self.grid.set_surface(combined)
        self._region_selector.set_image(combined)

    def set_save_path(self, path: Path) -> None:
        self._save_path = path

    
    
    

    def _open_export_dir_dialog(self, regions: list[Region]) -> None:
        """Open FileManager in save mode to pick an output directory for bulk export."""
        from widgets.filemanager import FileManager

        default_name = "export"
        if self.image_path:
            default_name = self.image_path.stem

        fm_rect = self._file_manager_rect()
        self._file_manager = FileManager(
            rect=fm_rect,
            initial_dir=self._data_root,
            allowed_exts=[".png"],
            on_save=lambda path: self._do_export_all(path.parent, path.stem, regions),
            mode="save",
            default_name=f"{default_name}.png",
            on_cancel=self._close_file_manager,
            data_root=self._data_root,
        )

    def _do_export_all(self, output_dir: Path, prefix: str, regions: list[Region]) -> None:
        """Execute bulk region export."""
        try:
            saved = export_all_regions(
                self.grid.surface,
                regions,
                output_dir,
                prefix=prefix,
            )
            self._status_bar.success(f"Exported {len(saved)} region{'s' if len(saved) != 1 else ''}")
            
            if self.image_path:
                sidecar = regions_sidecar_path(self.image_path)
                save_regions_json(regions, sidecar)
        except Exception as e:
            self._status_bar.error(f"Export failed: {e}")
        self._close_file_manager()

    def load_regions_for_image(self) -> None:
        """Load regions from sidecar JSON if it exists."""
        if self.image_path:
            sidecar = regions_sidecar_path(self.image_path)
            regions = load_regions_json(sidecar)
            if regions:
                self._region_selector.set_regions(regions)
