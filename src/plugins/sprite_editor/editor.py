"""SpriteEditor facade — chrome, hotkeys, dialogs, tool wiring.

The only place that talks to the StatusBar / Toast / toolbar. All canvas
mutations go through Commands; the viewport is draw-only.
"""

from __future__ import annotations

from pathlib import Path

import pygame
from pygame import Rect, Surface

from utils.natural_sort import natural_key
from widgets.ui.button import Button
from widgets.ui.draw_utils import draw_panel
from widgets.ui.mode_indicator import Mode, ModeIndicator
from widgets.ui.notification import NotificationManager
from widgets.ui.status_bar import StatusBar
from widgets.ui.theme import COLORS, FONTS

from .camera import Camera
from .clipboard import Clipboard
from .commands import (
    ClearCommand,
    CommandStack,
    FlipCommand,
    GridResizeCommand,
    ScaleCommand,
)
from .dialogs import GridSizeDialog, ScaleDialog
from .document import Document, Region
from .region_export import (
    export_all_regions,
    load_regions_json,
    regions_sidecar_path,
    save_regions_json,
)
from .selection import Selection
from .tools import PasteTool, RegionTool, SelectTool, Tool, ToolContext
from .viewport import Viewport

TOOLBAR_H = 76
STATUS_H = 26
BTN_W = 52
BTN_H = 28
BTN_GAP = 4
SEP_W = 10


class SpriteEditor:
    def __init__(
        self,
        rect: Rect,
        surface: Surface | None = None,
        tile_size: tuple[int, int] = (32, 32),
        image_path: Path | None = None,
        data_root: Path | None = None,
    ):
        self.rect = Rect(rect)
        self.image_path = image_path
        self._data_root = data_root or (image_path.parent if image_path else Path.cwd())
        self._save_path: Path | None = None
        self._file_manager: object | None = None
        self.mode = "grid"

        self.doc = Document(tile_size=tile_size)
        self.selection = Selection()
        self.camera = Camera()
        self.clipboard = Clipboard()
        self.commands = CommandStack(50)

        self.viewport = Viewport(self._content_rect(), self.doc, self.camera, self.selection)

        self.ctx = ToolContext(
            doc=self.doc,
            selection=self.selection,
            camera=self.camera,
            viewport=self.viewport,
            clipboard=self.clipboard,
            commands=self.commands,
            status=self._tool_status,
            toast=self._toast,
            set_tool=self._set_tool,
        )
        self._select_tool = SelectTool(self.ctx)
        self._paste_tool = PasteTool(self.ctx)
        self._region_tool = RegionTool(self.ctx)
        self._tools: dict[str, Tool] = {
            "select": self._select_tool,
            "paste": self._paste_tool,
            "regions": self._region_tool,
        }
        self._active_tool: Tool = self._select_tool

        if surface is not None:
            self._load_surface(surface, [image_path.name if image_path else "sheet"])

        self._scale_dialog = ScaleDialog(self.rect)
        self._grid_dialog = GridSizeDialog(self.rect)
        self._status_bar = StatusBar(
            Rect(rect.x, rect.bottom - STATUS_H, rect.w, STATUS_H),
        )
        self._notifications = NotificationManager(self)

        self._buttons: list[Button] = []
        self._separators: list[tuple[int, int]] = []
        self._mode_indicator: ModeIndicator | None = None
        self._stack_horizontal = False
        self._build_toolbar()

        self._status_bar.info("Ready", "")
        self._update_button_states()

    # -- geometry ---------------------------------------------------------
    def _content_rect(self) -> Rect:
        return Rect(
            self.rect.x,
            self.rect.y + TOOLBAR_H,
            self.rect.w,
            self.rect.h - TOOLBAR_H - STATUS_H,
        )

    def resize(self, x: int, y: int, w: int, h: int) -> None:
        self.rect = Rect(x, y, w, h)
        self.viewport.resize(self._content_rect())
        self._status_bar.resize(Rect(self.rect.x, self.rect.bottom - STATUS_H, self.rect.w, STATUS_H))
        self._scale_dialog.editor_rect = self.rect
        self._grid_dialog.editor_rect = self.rect
        self._build_toolbar()

    # -- toolbar -----------------------------------------------------------
    def _build_toolbar(self) -> None:
        self._buttons.clear()
        self._separators.clear()

        row_y = (self.rect.y + 7, self.rect.y + 41)
        x = self.rect.x + BTN_GAP + 2

        def row(r: int) -> None:
            nonlocal x
            x = self.rect.x + BTN_GAP + 2

        def add_btn(text: str, *, tooltip: str = "", on_click=None, tag: str = "", r: int = 0) -> Button:
            nonlocal x
            btn = Button(
                Rect(x, row_y[r], BTN_W, BTN_H),
                text=text,
                tooltip_text=tooltip or text,
                border_radius=3,
                on_click=on_click or (lambda: None),
            )
            btn._tag = tag or text.lower().replace(" ", "_")
            self._buttons.append(btn)
            x += BTN_W + BTN_GAP
            return btn

        def sep(r: int = 0) -> None:
            nonlocal x
            self._separators.append((x + SEP_W // 2, row_y[r] + BTN_H // 2))
            x += SEP_W

        # ROW 1 — FILE | EDIT | TRANSFORM
        add_btn("Open", tooltip="Open spritesheets", on_click=self._on_open, tag="open")
        add_btn("Save", tooltip="Save PNG (Ctrl+S)", on_click=self._on_save, tag="save")
        add_btn(
            "Stack V",
            tooltip="Stack direction for multi-sheet loads (currently vertical)",
            on_click=self._toggle_stack,
            tag="stack",
        )
        sep()

        add_btn("Undo", tooltip="Undo (Ctrl+Z)", on_click=self._on_undo, tag="undo")
        add_btn("Redo", tooltip="Redo (Ctrl+Y)", on_click=self._on_redo, tag="redo")
        add_btn("Cut", tooltip="Cut (Ctrl+X)", on_click=self._on_cut, tag="cut")
        add_btn("Copy", tooltip="Copy (Ctrl+C)", on_click=self._on_copy, tag="copy")
        add_btn("Paste", tooltip="Paste (Ctrl+V)", on_click=self._on_paste, tag="paste")
        sep()

        add_btn("Flip X", tooltip="Flip horizontal", on_click=self._on_flip_x, tag="flip_x")
        add_btn("Flip Y", tooltip="Flip vertical", on_click=self._on_flip_y, tag="flip_y")
        add_btn("Scale", tooltip="Scale spritesheet", on_click=self._on_scale, tag="scale")

        # ROW 2 — VIEW | MODE | EXPORT
        row(1)
        add_btn("Tile Size", tooltip="Change tile size", on_click=self._on_grid, tag="grid", r=1)
        add_btn("Fit", tooltip="Fit sheet to canvas (F)", on_click=self._on_fit, tag="fit", r=1)
        add_btn("−", tooltip="Zoom out", on_click=self._on_zoom_out, tag="zoom_out", r=1)
        self._zoom_btn = add_btn("100%", tooltip="Zoom level (0 = reset)", tag="zoom_pct", r=1)
        add_btn("+", tooltip="Zoom in", on_click=self._on_zoom_in, tag="zoom_in", r=1)
        add_btn("Reset", tooltip="Reset to 100% (0)", on_click=self._on_reset_zoom, tag="zoom_0", r=1)
        sep(1)

        self._mode_indicator = ModeIndicator(
            Rect(x, row_y[1], 150, BTN_H),
            modes=[
                Mode(id="grid", label="Grid"),
                Mode(id="regions", label="Regions"),
            ],
            active_mode="grid",
        )
        self._mode_indicator.on_mode_changed = self._on_mode_changed
        x += 150 + SEP_W
        sep(1)

        # EXPORT
        add_btn("Export", tooltip="Export all regions to PNG", on_click=self._on_export_all, tag="export_all", r=1)

    def _toggle_stack(self) -> None:
        self._stack_horizontal = not self._stack_horizontal
        self._toast(f"Stacking: {'horizontal' if self._stack_horizontal else 'vertical'}")
        self._update_button_states()

    def _get_btn(self, tag: str) -> Button | None:
        for btn in self._buttons:
            if getattr(btn, "_tag", "") == tag:
                return btn
        return None

    # -- tool wiring ------------------------------------------------------
    def _set_tool(self, name: str) -> None:
        target = self._tools.get(name)
        if target is None or target is self._active_tool:
            return
        self._active_tool.exit()
        self._active_tool = target
        self._active_tool.enter()
        self._update_button_states()

    def _on_mode_changed(self, old: str, new: str) -> None:
        if new == "regions":
            if self._active_tool is self._paste_tool:
                self._toast("Paste canceled")
            self.mode = "regions"
            self._set_tool("regions")
        else:
            self.mode = "grid"
            if self._active_tool is self._paste_tool:
                self._toast("Paste canceled")
                self._set_tool("select")
            else:
                self._set_tool("select")
        self._update_button_states()

    def _tool_status(self, message: str, detail: str = "") -> None:
        self._status_bar.info(message, detail)

    def _toast(self, message: str) -> None:
        self._notifications.success(message)

    # -- toolbar actions ---------------------------------------------------
    def _on_open(self) -> None:
        self._open_add_sheets_dialog()

    def _on_save(self) -> None:
        self._open_save_dialog()

    def _on_undo(self) -> None:
        if self.commands.undo(self.doc, self.selection):
            name = self.commands.peek_redo().name if self.commands.can_redo else "Edit"
            self._status_bar.info(f"Undo {name}")
            self._toast(f"Undo {name}")

    def _on_redo(self) -> None:
        if self.commands.redo(self.doc, self.selection):
            name = self.commands.peek_undo().name if self.commands.can_undo else "Edit"
            self._status_bar.info(f"Redo {name}")
            self._toast(f"Redo {name}")

    def _on_copy(self) -> None:
        if self._active_tool is self._paste_tool:
            self._set_tool("select")
        if not self.selection:
            self._status_bar.warning("Nothing to copy")
            return
        if self.clipboard.copy_from_selection(self.doc, self.selection):
            n = len(self.clipboard)
            self._status_bar.info(f"Copied {n} tile{'s' if n != 1 else ''}")
            self._toast(f"Copied {n} tile{'s' if n != 1 else ''}")

    def _on_cut(self) -> None:
        if self._active_tool is self._paste_tool:
            self._set_tool("select")
        if not self.selection:
            self._status_bar.warning("Nothing to cut")
            return
        if self.clipboard.copy_from_selection(self.doc, self.selection):
            n = len(self.clipboard)
            self.commands.push(ClearCommand(self.selection.sorted_cells()), self.doc, self.selection)
            self._status_bar.info(f"Cut {n} tile{'s' if n != 1 else ''}")
            self._toast(f"Cut {n} tile{'s' if n != 1 else ''}")

    def _on_paste(self) -> None:
        if self.clipboard.is_empty:
            self._status_bar.warning("Nothing to paste")
            self._toast("Clipboard is empty")
            return
        if self.mode == "regions":
            self._status_bar.warning("Paste works in Grid mode")
            return
        if self._active_tool is self._paste_tool:
            self._toast("Paste canceled")
            self._set_tool("select")
            return
        self._set_tool("paste")

    def _on_flip_x(self) -> None:
        self._flip(True, False)

    def _on_flip_y(self) -> None:
        self._flip(False, True)

    def _flip(self, fx: bool, fy: bool) -> None:
        if not self.selection:
            self._status_bar.warning("Select tiles to flip")
            return
        cells = self.selection.sorted_cells()
        self.commands.push(FlipCommand(cells, fx, fy), self.doc, self.selection)
        axis = "X" if fx else "Y"
        self._status_bar.success(f"Flipped {axis}")

    def _on_scale(self) -> None:
        self._scale_dialog.show_scale(on_apply=self._apply_scale)

    def _apply_scale(self, factor: float) -> None:
        if not self.doc.has_canvas:
            self._status_bar.warning("No spritesheet loaded")
            return
        self.commands.push(ScaleCommand(factor), self.doc, self.selection)
        self._status_bar.success(f"Scaled ×{factor:.2f}")

    def _on_grid(self) -> None:
        self._grid_dialog.show_grid(on_apply=self._apply_grid_size, current_size=self.doc.tile_size)

    def _apply_grid_size(self, tw: int, th: int) -> None:
        self.commands.push(GridResizeCommand((tw, th)), self.doc, self.selection)
        self._status_bar.success(f"Tile size: {tw}×{th}")

    def _on_fit(self) -> None:
        if self.doc.has_canvas:
            content = self.viewport.content_rect
            self.camera.fit(self.doc.size, (content.w, content.h))

    def _on_zoom_in(self) -> None:
        self.camera.zoom_at(self.viewport.rect.center, 1.25)

    def _on_zoom_out(self) -> None:
        self.camera.zoom_at(self.viewport.rect.center, 1 / 1.25)

    def _on_reset_zoom(self) -> None:
        self.camera.reset()

    # -- region actions ----------------------------------------------------
    def _on_export_all(self) -> None:
        regions = self.doc.regions
        if not regions:
            self._status_bar.warning("No regions defined")
            return
        if not self.doc.has_canvas:
            self._status_bar.warning("No spritesheet loaded")
            return
        self._open_export_dir_dialog(regions)

    # -- status / button sync ----------------------------------------------
    def _update_button_states(self) -> None:
        undo_btn = self._get_btn("undo")
        if undo_btn:
            undo_btn.enabled = self.commands.can_undo
        redo_btn = self._get_btn("redo")
        if redo_btn:
            redo_btn.enabled = self.commands.can_redo
        paste_btn = self._get_btn("paste")
        if paste_btn:
            paste_btn.active = self._active_tool is self._paste_tool
        export_btn = self._get_btn("export_all")
        if export_btn:
            export_btn.enabled = bool(self.doc.regions) and self.doc.has_canvas
        stack_btn = self._get_btn("stack")
        if stack_btn:
            stack_btn.text = "Stack H" if self._stack_horizontal else "Stack V"
            stack_btn.tooltip_text = (
                "Stack direction for multi-sheet loads (currently horizontal)"
                if self._stack_horizontal
                else "Stack direction for multi-sheet loads (currently vertical)"
            )
        if self._mode_indicator is not None:
            self._mode_indicator.active_mode_id = self.mode
        if getattr(self, "_zoom_btn", None):
            self._zoom_btn.text = f"{self.camera.zoom * 100:.0f}%"

    # -- events ------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._file_manager is not None:
            return self._file_manager.handle_event(event)

        if self._scale_dialog.active:
            return self._scale_dialog.handle_event(event)
        if self._grid_dialog.active:
            return self._grid_dialog.handle_event(event)

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)
            if ctrl:
                if event.key == pygame.K_z:
                    self._on_undo()
                    return True
                if event.key == pygame.K_y or (event.key == pygame.K_z and mods & pygame.KMOD_SHIFT):
                    self._on_redo()
                    return True
                if event.key == pygame.K_c:
                    self._on_copy()
                    return True
                if event.key == pygame.K_x:
                    self._on_cut()
                    return True
                if event.key == pygame.K_v:
                    self._on_paste()
                    return True
                if event.key == pygame.K_s:
                    self._on_save()
                    return True

        for btn in self._buttons:
            if btn.handle_event(event):
                self._update_button_states()
                return True

        if self._mode_indicator is not None and self._mode_indicator.handle_event(event):
            self._update_button_states()
            return True

        return bool(
            self._event_in_viewport(event) and self._active_tool.handle_event(event)
        )

    @staticmethod
    def _event_in_viewport(event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEWHEEL:
            # wheel events carry x/y, not pos — still canvas gestures
            return True
        return event.type == pygame.KEYDOWN or getattr(event, "pos", None) is not None

    # -- draw ----------------------------------------------------------------
    def draw(self, screen: Surface) -> None:
        draw_panel(screen, self.rect, COLORS.bg, COLORS.border)

        toolbar_rect = Rect(self.rect.x, self.rect.y, self.rect.w, TOOLBAR_H)
        draw_panel(screen, toolbar_rect, COLORS.header, COLORS.border)

        sep_h = 16
        for sx, sy in self._separators:
            pygame.draw.line(screen, COLORS.border_soft, (sx, sy - sep_h // 2), (sx, sy + sep_h // 2), 2)

        self._update_button_states()
        for btn in self._buttons:
            btn.draw(screen)
        if self._mode_indicator is not None:
            self._mode_indicator.draw(screen)

        if self._file_manager is None:
            self.viewport.draw(screen, self._active_tool)

        self._status_bar.draw(screen)

        if self._scale_dialog.active:
            self._scale_dialog.draw(screen)
        if self._grid_dialog.active:
            self._grid_dialog.draw(screen)

        if self._file_manager is not None:
            self._file_manager.draw(screen)

        self._notifications.draw(screen)

        mouse_pos = pygame.mouse.get_pos()
        for btn in self._buttons:
            if btn.rect.collidepoint(mouse_pos) and btn.tooltip_text:
                self._draw_tooltip(screen, btn.tooltip_text, mouse_pos)
                break

    def _draw_tooltip(self, screen: Surface, text: str, pos: tuple[int, int]) -> None:
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

    # -- file flows -----------------------------------------------------------
    def _file_manager_rect(self) -> Rect:
        w, h = 600, 400
        cx, cy = self.rect.center
        return Rect(cx - w // 2, cy - h // 2, w, h)

    def _close_file_manager(self) -> None:
        self._file_manager = None

    def _open_save_dialog(self) -> None:
        if not self.doc.has_canvas:
            self._status_bar.warning("No spritesheet loaded")
            return
        from widgets.filemanager import FileManager

        initial_dir = self._save_path.parent if self._save_path else self._data_root
        default_name = (
            self._save_path.name
            if self._save_path
            else (f"{self.image_path.stem}_edited.png" if self.image_path else "spritesheet.png")
        )
        self._file_manager = FileManager(
            rect=self._file_manager_rect(),
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
            pygame.image.save(self.doc.surface, str(path))
            self.set_save_path(path)
            self._status_bar.success(f"Saved {path.name}")
            self._toast(f"Saved {path.name}")
        except Exception as e:
            self._status_bar.error(f"Save failed: {e}")
        self._close_file_manager()

    def _open_add_sheets_dialog(self) -> None:
        from widgets.filemanager import FileManager

        self._file_manager = FileManager(
            rect=self._file_manager_rect(),
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
        selection = sorted(selection, key=lambda p: natural_key(p.name))
        loaded = 0
        surfaces: list[Surface] = []
        for path in selection:
            try:
                surfaces.append(pygame.image.load(str(path)).convert_alpha())
                loaded += 1
            except Exception as e:
                self._status_bar.error(f"Failed: {path.name}: {e}")
        if loaded:
            was_empty = not self.doc.has_canvas
            self._load_surface(
                self._build_combined_surface(surfaces, horizontal=self._stack_horizontal),
                [p.name for p in selection],
            )
            if was_empty:
                detected = self._detect_tile_size(surfaces[0])
                self.doc.tile_size = detected
            self._status_bar.success(f"Loaded {loaded} sheet{'s' if loaded != 1 else ''}")
            self._toast(f"Loaded {loaded} sheet{'s' if loaded != 1 else ''}")
        self._close_file_manager()

    @staticmethod
    def _build_combined_surface(surfaces: list[Surface], horizontal: bool = False) -> Surface:
        if len(surfaces) == 1:
            return surfaces[0]
        if horizontal:
            total_w = sum(s.get_width() for s in surfaces)
            max_h = max(s.get_height() for s in surfaces)
            combined = Surface((total_w, max_h), pygame.SRCALPHA)
            combined.fill((0, 0, 0, 0))
            x = 0
            for surf in surfaces:
                combined.blit(surf, (x, 0))
                x += surf.get_width()
            return combined
        max_w = max(s.get_width() for s in surfaces)
        total_h = sum(s.get_height() for s in surfaces)
        combined = Surface((max_w, total_h), pygame.SRCALPHA)
        combined.fill((0, 0, 0, 0))
        y = 0
        for surf in surfaces:
            combined.blit(surf, (0, y))
            y += surf.get_height()
        return combined

    def _load_surface(self, surface: Surface, sheet_names: list[str]) -> None:
        """Replace the canvas with a new sheet; resets history and regions."""
        self.doc.set_surface(surface)
        self.doc.sheets = list(sheet_names)
        self.doc.regions = []
        self.commands.clear()
        self.selection.clear()
        self.camera.reset()

    def _open_export_dir_dialog(self, regions: list[Region]) -> None:
        from widgets.filemanager import FileManager

        default_name = self.image_path.stem if self.image_path else "export"
        self._file_manager = FileManager(
            rect=self._file_manager_rect(),
            initial_dir=self._data_root,
            allowed_exts=[".png"],
            on_save=lambda path: self._do_export_all(path.parent, path.stem, regions),
            mode="save",
            default_name=f"{default_name}.png",
            on_cancel=self._close_file_manager,
            data_root=self._data_root,
        )

    def _do_export_all(self, output_dir: Path, prefix: str, regions: list[Region]) -> None:
        try:
            saved = export_all_regions(self.doc.surface, regions, output_dir, prefix=prefix)
            self._status_bar.success(f"Exported {len(saved)} region{'s' if len(saved) != 1 else ''}")
            self._toast(f"Exported {len(saved)} region{'s' if len(saved) != 1 else ''}")
            if self.image_path:
                sidecar = regions_sidecar_path(self.image_path)
                save_regions_json(regions, sidecar)
        except Exception as e:
            self._status_bar.error(f"Export failed: {e}")
        self._close_file_manager()

    def set_save_path(self, path: Path) -> None:
        self._save_path = path

    # -- persistence ------------------------------------------------------
    def load_regions_for_image(self) -> None:
        if self.image_path:
            sidecar = regions_sidecar_path(self.image_path)
            regions = load_regions_json(sidecar)
            if regions:
                self.doc.regions = regions
                self._status_bar.info(f"Loaded {len(regions)} regions")

    @staticmethod
    def _detect_tile_size(surface: Surface) -> tuple[int, int]:
        w, h = surface.get_size()
        candidates = [8, 12, 16, 24, 32, 48, 64, 128]
        best = 8
        for s in candidates:
            if w % s == 0 and h % s == 0:
                best = s
        return (best, best)
