"""SpriteEditor facade — chrome, hotkeys, dialogs, tool wiring.

The only place that talks to the StatusBar / Toast / toolbar. All canvas
mutations go through Commands; the viewport is draw-only.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import pygame
from pygame import Rect, Surface

from utils.natural_sort import natural_key
from widgets.ui.button import Button
from widgets.ui.context_menu import ContextMenu
from widgets.ui.draw_utils import draw_panel
from widgets.ui.menubar import Menu, MenuAction, MenuBar, MenuSeparator
from widgets.ui.mode_indicator import Mode, ModeIndicator
from widgets.ui.notification import NotificationManager
from widgets.ui.status_bar import StatusBar
from widgets.ui.theme import COLORS, FONTS

from .camera import Camera
from .clipboard import Clipboard
from .commands import (
    AppendSheetCommand,
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
from .tools import PasteTool, RegionTool, SelectTool, TextTool, Tool, ToolContext
from .viewport import Viewport

MENU_H = 30
TOOLBAR_H = 44
STATUS_H = 26
BTN_W = 52
BTN_H = 28
BTN_GAP = 4
SEP_W = 10
IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".bmp", ".gif"]


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
        self._pending_drops: list[Path] | None = None
        self._drop_hover = False

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
        self._text_tool = TextTool(self.ctx)
        self._tools: dict[str, Tool] = {
            "select": self._select_tool,
            "paste": self._paste_tool,
            "regions": self._region_tool,
            "text": self._text_tool,
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
        self._sort_natural = True
        self._build_toolbar()

        self._context_menu = ContextMenu()
        self._show_shortcuts = False
        self._rmb_press_pos: tuple[int, int] | None = None
        self.menubar = MenuBar(None, rect.w, MENU_H, menus=self._build_menus())

        self._status_bar.info("Ready", "")
        self._update_button_states()

    # -- geometry ---------------------------------------------------------
    def _content_rect(self) -> Rect:
        return Rect(
            self.rect.x,
            self.rect.y + MENU_H + TOOLBAR_H,
            self.rect.w,
            self.rect.h - MENU_H - TOOLBAR_H - STATUS_H,
        )

    def resize(self, x: int, y: int, w: int, h: int) -> None:
        self.rect = Rect(x, y, w, h)
        self.menubar.resize(self.rect.x, self.rect.y, w, MENU_H)
        self.viewport.resize(self._content_rect())
        self._status_bar.resize(Rect(self.rect.x, self.rect.bottom - STATUS_H, self.rect.w, STATUS_H))
        self._scale_dialog.editor_rect = self.rect
        self._grid_dialog.editor_rect = self.rect
        self._build_toolbar()

    # -- toolbar -----------------------------------------------------------
    def _build_menus(self) -> list[Menu]:
        vp = self.viewport
        return [
            Menu(
                "File",
                [
                    MenuAction("Open...", self._on_open, "Ctrl+O"),
                    MenuAction(
                        "Save",
                        self._on_save,
                        "Ctrl+S",
                        is_enabled=lambda: self.doc.has_canvas,
                    ),
                    MenuAction("Save As...", self._on_save_as),
                    MenuSeparator(),
                    MenuAction(
                        "Export Regions to PNG...",
                        self._on_export_all,
                        "Ctrl+E",
                        is_enabled=lambda: bool(self.doc.regions)
                        and self.doc.has_canvas,
                    ),
                    MenuSeparator(),
                    MenuAction(
                        "Stack Horizontally",
                        self._toggle_stack,
                        is_checked=lambda: self._stack_horizontal,
                    ),
                    MenuAction(
                        "Natural Sort on Open",
                        self._toggle_sort_natural,
                        is_checked=lambda: self._sort_natural,
                    ),
                    MenuSeparator(),
                    MenuAction("Close", self._on_close, "Ctrl+Q"),
                ],
            ),
            Menu(
                "Edit",
                [
                    MenuAction(
                        "Undo",
                        self._on_undo,
                        "Ctrl+Z",
                        is_enabled=lambda: self.commands.can_undo,
                    ),
                    MenuAction(
                        "Redo",
                        self._on_redo,
                        "Ctrl+Shift+Z",
                        is_enabled=lambda: self.commands.can_redo,
                    ),
                    MenuSeparator(),
                    MenuAction("Cut", self._on_cut, "Ctrl+X"),
                    MenuAction("Copy", self._on_copy, "Ctrl+C"),
                    MenuAction("Paste", self._on_paste_smart, "Ctrl+V"),
                    MenuSeparator(),
                    MenuAction(
                        "Select All",
                        self._on_select_all,
                        "Ctrl+A",
                        is_enabled=lambda: self.doc.has_canvas,
                    ),
                    MenuAction(
                        "Deselect",
                        self._on_deselect,
                        "Esc",
                        is_enabled=lambda: bool(self.selection),
                    ),
                ],
            ),
            Menu(
                "View",
                [
                    MenuAction(
                        "Show Grid",
                        self._toggle_grid,
                        "G",
                        is_checked=lambda: vp.show_grid,
                    ),
                    MenuAction(
                        "Show Regions",
                        self._toggle_regions,
                        is_checked=lambda: vp.show_regions,
                    ),
                    MenuSeparator(),
                    MenuAction("Zoom 50%", lambda: self._set_zoom(0.5)),
                    MenuAction("Zoom 100%", lambda: self._set_zoom(1.0)),
                    MenuAction("Zoom 200%", lambda: self._set_zoom(2.0)),
                    MenuSeparator(),
                    MenuAction("Fit to Window", self._on_fit, "F"),
                    MenuAction("Reset Zoom", self._on_reset_zoom, "0"),
                ],
            ),
            Menu(
                "Sprite",
                [
                    MenuAction(
                        "Flip Horizontal",
                        self._on_flip_x,
                        is_enabled=lambda: self.doc.has_canvas,
                    ),
                    MenuAction(
                        "Flip Vertical",
                        self._on_flip_y,
                        is_enabled=lambda: self.doc.has_canvas,
                    ),
                    MenuAction(
                        "Scale...",
                        self._on_scale,
                        is_enabled=lambda: self.doc.has_canvas,
                    ),
                    MenuSeparator(),
                    MenuAction("Tile Size...", self._on_grid),
                ],
            ),
            Menu(
                "Help",
                [MenuAction("Keyboard Shortcuts", self._toggle_shortcuts)],
            ),
        ]

    # -- menu actions -------------------------------------------------------
    def _on_save_as(self) -> None:
        if not self.doc.has_canvas:
            self._status_bar.warning("No spritesheet loaded")
            return
        self._open_save_dialog()

    def _on_close(self) -> None:
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _on_select_all(self) -> None:
        if not self.doc.has_canvas:
            return
        self.selection.select_all(self.doc)
        self._status_bar.info(f"Selected {len(self.selection)} cells")

    def _on_deselect(self) -> None:
        if self.selection:
            self.selection.replace([], anchor=None)

    def _toggle_grid(self) -> None:
        self.viewport.show_grid = not self.viewport.show_grid

    def _toggle_regions(self) -> None:
        self.viewport.show_regions = not self.viewport.show_regions

    def _toggle_shortcuts(self) -> None:
        self._show_shortcuts = not self._show_shortcuts

    def _set_zoom(self, zoom: float) -> None:
        content = self.viewport.content_rect
        self.camera.zoom_at(content.center, zoom / max(self.camera.zoom, 0.0001))

    def _popup_menu(self, items: list, pos: tuple[int, int]) -> None:
        self._context_menu.popup(items, pos, (self.rect.right, self.rect.bottom))

    def _transform_menu_items(self) -> list:
        return [
            MenuAction(
                "Flip Horizontal",
                self._on_flip_x,
                is_enabled=lambda: self.doc.has_canvas,
            ),
            MenuAction(
                "Flip Vertical",
                self._on_flip_y,
                is_enabled=lambda: self.doc.has_canvas,
            ),
            MenuAction(
                "Scale...",
                self._on_scale,
                is_enabled=lambda: self.doc.has_canvas,
            ),
        ]

    def _build_toolbar(self) -> None:
        self._buttons.clear()
        self._separators.clear()

        row_y = self.rect.y + MENU_H + 8
        x = self.rect.x + BTN_GAP + 2

        def add_btn(text: str, *, tooltip: str = "", on_click=None, tag: str = "") -> Button:
            nonlocal x
            # width fits the label so longer captions never clip
            w = max(BTN_W, FONTS.get_small_font().size(text)[0] + 14)
            btn = Button(
                Rect(x, row_y, w, BTN_H),
                text=text,
                tooltip_text=tooltip or text,
                border_radius=3,
                on_click=on_click or (lambda: None),
            )
            btn._tag = tag or text.lower().replace(" ", "_")
            self._buttons.append(btn)
            x += w + BTN_GAP
            return btn

        def sep() -> None:
            nonlocal x
            self._separators.append((x + SEP_W // 2, row_y + BTN_H // 2))
            x += SEP_W

        # icon-only for file ops to reduce clutter (matches main Toolbar 28px style)
        def add_icon(icon: str, tooltip: str, on_click, tag: str) -> Button:
            nonlocal x
            btn = Button(
                Rect(x, row_y, BTN_H, BTN_H),
                icon_key=icon,
                tooltip_text=tooltip,
                border_radius=3,
                on_click=on_click,
            )
            btn._tag = tag
            btn.icon_size = 16
            self._buttons.append(btn)
            x += BTN_H + BTN_GAP
            return btn

        add_icon("load", "Open spritesheets (Ctrl+O)", self._on_open, "open")
        add_icon("save", "Save PNG (Ctrl+S)", self._on_save, "save")
        sep()

        add_icon("undo", "Undo (Ctrl+Z)", self._on_undo, "undo")
        add_icon("redo", "Redo (Ctrl+Shift+Z)", self._on_redo, "redo")
        sep()

        add_btn(
            "Transform",
            tooltip="Flip / Scale",
            on_click=self._open_transform_menu,
            tag="transform",
        )
        add_btn("Tile Size", tooltip="Change tile size", on_click=self._on_grid, tag="grid")
        # Text as icon button (flameshot-like) — avoids text clutter; active while editing
        t_btn = Button(
            Rect(x, row_y, BTN_H, BTN_H),
            icon_key="text",
            tooltip_text="Text label (T) — drag anywhere, Enter to bake, drag ○ to rotate",
            border_radius=3,
            on_click=self._on_text,
        )
        t_btn._tag = "text"
        t_btn.icon_size = 16
        self._buttons.append(t_btn)
        x += BTN_H + BTN_GAP
        sep()

        self._mode_indicator = ModeIndicator(
            Rect(x, row_y, 150, BTN_H),
            modes=[
                Mode(id="grid", label="Grid"),
                Mode(id="regions", label="Regions"),
            ],
            active_mode="grid",
        )
        self._mode_indicator.on_mode_changed = self._on_mode_changed
        x += 150 + SEP_W
        sep()

        add_icon("zoomout", "Zoom out (−)", self._on_zoom_out, "zoom_out")
        self._zoom_btn = add_btn(
            "100%",
            tooltip="Click to reset zoom",
            on_click=self._on_reset_zoom,
            tag="zoom_pct",
        )
        add_icon("zoomin", "Zoom in (+)", self._on_zoom_in, "zoom_in")
        add_icon("fit", "Fit sheet to window (F)", self._on_fit, "fit")

        export_x = self.rect.right - BTN_W - BTN_GAP - 2
        export = Button(
            Rect(export_x, row_y, BTN_W, BTN_H),
            text="Export",
            tooltip_text="Export all regions to PNG (Ctrl+E)",
            border_radius=3,
            accent=True,
            on_click=self._on_export_all,
        )
        export._tag = "export_all"
        self._buttons.append(export)

    def _open_transform_menu(self) -> None:
        btn = self._get_btn("transform")
        pos = (btn.rect.x, btn.rect.bottom + 2) if btn else (self.rect.x + 200, self.rect.y + MENU_H + TOOLBAR_H)
        self._popup_menu(self._transform_menu_items(), pos)

    def _toggle_stack(self) -> None:
        self._stack_horizontal = not self._stack_horizontal
        self._toast(f"Stacking: {'horizontal' if self._stack_horizontal else 'vertical'}")
        self._update_button_states()

    def _on_paste_smart(self) -> None:
        """Clipboard holding image paths loads sheets; otherwise pixel-paste."""
        if self._paste_paths_from_clipboard():
            return
        self._on_paste()

    def _toggle_sort_natural(self) -> None:
        self._sort_natural = not self._sort_natural
        mode = "natural order" if self._sort_natural else "click order"
        self._toast(f"Open sort: {mode}")

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
        # flameshot-like text tool is modal — switching mode cancels it
        if self._active_tool is self._text_tool:
            self._text_tool.exit()
            self._toast("Text canceled")
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

    def _on_text(self) -> None:
        if self._active_tool is self._text_tool:
            # toggling off while editing keeps draft — exit cleanly
            if getattr(self._text_tool, "_mode", "idle") != "idle":
                self._text_tool.cancel()
            self._set_tool("select" if self.mode == "grid" else "regions")
            return
        # leaving paste/region etc.
        if self._active_tool is self._paste_tool:
            self._toast("Paste canceled")
        self._set_tool("text")

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
        text_btn = self._get_btn("text")
        if text_btn:
            text_btn.active = self._active_tool is self._text_tool
        export_btn = self._get_btn("export_all")
        if export_btn:
            export_btn.enabled = bool(self.doc.regions) and self.doc.has_canvas
        if self._mode_indicator is not None:
            self._mode_indicator.active_mode_id = self.mode
        if getattr(self, "_zoom_btn", None):
            self._zoom_btn.text = f"{self.camera.zoom * 100:.0f}%"

    # -- events ------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        if self._handle_drop_event(event):
            return True

        if self._context_menu.is_open:
            return self._context_menu.handle_event(event)

        if self._show_shortcuts:
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                self._show_shortcuts = False
                return True

        if self._file_manager is not None:
            return self._file_manager.handle_event(event)

        if self._scale_dialog.active:
            return self._scale_dialog.handle_event(event)
        if self._grid_dialog.active:
            return self._grid_dialog.handle_event(event)

        if self.menubar.handle_event(event):
            self._update_button_states()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            pos = getattr(event, "pos", pygame.mouse.get_pos())
            if self.viewport.rect.collidepoint(pos):
                self._rmb_press_pos = pos

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            press = self._rmb_press_pos
            self._rmb_press_pos = None
            up_pos = getattr(event, "pos", pygame.mouse.get_pos())
            stationary = (
                press is not None
                and abs(up_pos[0] - press[0]) <= 4
                and abs(up_pos[1] - press[1]) <= 4
            )
            # the tool owns panning state on button 3 — it must always see
            # the release, even when a popup is about to open
            if self._event_in_viewport(event):
                self._active_tool.handle_event(event)
            if stationary:
                self._popup_canvas_menu(up_pos)
                return True

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)
            if ctrl:
                # shift-modified Z must win over plain Z or Ctrl+Shift+Z
                # would undo instead of redo
                if event.key == pygame.K_z and mods & pygame.KMOD_SHIFT:
                    self._on_redo()
                    return True
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
                    self._on_cut()
                    return True
                if event.key == pygame.K_v:
                    self._on_paste_smart()
                    return True
                if event.key == pygame.K_s:
                    self._on_save()
                    return True
                if event.key == pygame.K_o:
                    self._on_open()
                    return True
                if event.key == pygame.K_e:
                    self._on_export_all()
                    return True
                if event.key == pygame.K_q:
                    self._on_close()
                    return True
                if event.key == pygame.K_a:
                    self._on_select_all()
                    return True
            else:
                # while the text tool input is focused every unmodified
                # keypress belongs to the label — skipping these shortcuts
                # lets them fall through to the tool's InputBox instead
                typing_in_text_input = (
                    self._active_tool is self._text_tool
                    and getattr(self._text_tool, "_input", None) is not None
                    and self._text_tool._input.is_focused
                )
                if not typing_in_text_input:
                    if event.key == pygame.K_f:
                        self._on_fit()
                        return True
                    if event.key == pygame.K_g:
                        self._toggle_grid()
                        return True
                    if event.key == pygame.K_t:
                        self._on_text()
                        return True
                    if event.key == pygame.K_0:
                        self._on_reset_zoom()
                        return True
                    if event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                        self._on_zoom_in()
                        return True
                    if event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                        self._on_zoom_out()
                        return True

        for btn in self._buttons:
            if btn.handle_event(event):
                self._update_button_states()
                return True

        if self._mode_indicator is not None and self._mode_indicator.handle_event(event):
            self._update_button_states()
            return True

        if self._event_in_viewport(event) and self._active_tool.handle_event(event):
            return True

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self._active_tool is self._text_tool and getattr(self._text_tool, "_mode", "idle") == "idle":
                self._set_tool("select" if self.mode == "grid" else "regions")
                return True
            if self.selection:
                self._on_deselect()
                return True

        return False

    def _popup_canvas_menu(self, pos: tuple[int, int]) -> None:
        self._popup_menu(
            [
                MenuAction(
                    "Undo",
                    self._on_undo,
                    "Ctrl+Z",
                    is_enabled=lambda: self.commands.can_undo,
                ),
                MenuAction(
                    "Redo",
                    self._on_redo,
                    "Ctrl+Shift+Z",
                    is_enabled=lambda: self.commands.can_redo,
                ),
                MenuSeparator(),
                MenuAction("Copy", self._on_copy, "Ctrl+C"),
                MenuAction("Paste", self._on_paste_smart, "Ctrl+V"),
                MenuSeparator(),
                MenuAction(
                    "Show Grid",
                    self._toggle_grid,
                    "G",
                    is_checked=lambda: self.viewport.show_grid,
                ),
                MenuAction(
                    "Show Regions",
                    self._toggle_regions,
                    is_checked=lambda: self.viewport.show_regions,
                ),
                MenuSeparator(),
                MenuAction("Fit to Window", self._on_fit, "F"),
                MenuAction("Zoom 100%", lambda: self._set_zoom(1.0)),
            ],
            pos,
        )

    @staticmethod
    def _event_in_viewport(event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEWHEEL:
            # wheel events carry x/y, not pos — still canvas gestures
            return True
        return event.type == pygame.KEYDOWN or getattr(event, "pos", None) is not None

    # -- system file drop -----------------------------------------------------
    def _handle_drop_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.DROPBEGIN:
            self._flush_pending_drops()
            self._pending_drops = []
            self._drop_hover = True
            return True
        if event.type == pygame.DROPFILE:
            if self._pending_drops is None:
                self._pending_drops = []
                self._drop_hover = True
            self._pending_drops.append(Path(event.file))
            return True
        if event.type == pygame.DROPCOMPLETE:
            self._drop_hover = False
            self._flush_pending_drops()
            return True
        if event.type == pygame.DROPTEXT:
            paths = self._paths_from_drop_text(getattr(event, "text", ""))
            if paths:
                standalone = self._pending_drops is None
                if standalone:
                    self._pending_drops = []
                    self._drop_hover = True
                self._pending_drops.extend(paths)
                if standalone:
                    self._flush_pending_drops()
            return True
        return False

    @staticmethod
    def _paths_from_drop_text(text: str) -> list[Path]:
        paths: list[Path] = []
        for line in (text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("file://"):
                parsed = urlparse(line)
                # Preserve host for UNC (file://server/share/...)
                raw = unquote(parsed.path)
                if parsed.netloc:
                    # Keep localhost as local, otherwise UNC
                    if parsed.netloc not in ("", "localhost", "127.0.0.1"):
                        raw = f"//{parsed.netloc}{raw}"
                # OS-aware conversion; fixes Windows drive-letter leading slash
                try:
                    raw = url2pathname(raw)
                except Exception:
                    pass
                # Strip erroneous leading slash for Windows drive letters
                # (url2pathname on POSIX leaves "/C:/..." intact)
                if (
                    len(raw) >= 3
                    and raw[0] == "/"
                    and raw[2] == ":"
                    and raw[1].isalpha()
                ):
                    raw = raw[1:]
                paths.append(Path(raw))
            elif line.startswith("/") or (len(line) > 2 and line[1] == ":"):
                paths.append(Path(unquote(line)))
        return paths

    @staticmethod
    def _clipboard_text() -> str:
        try:
            import pygame.scrap

            try:
                text = pygame.scrap.get_text()
            except Exception:
                pygame.scrap.init()
                text = pygame.scrap.get_text()
            if text:
                return text
        except Exception:
            pass
        import shutil
        import subprocess

        for cmd in (
            ["pbpaste"],
            ["xclip", "-selection", "clipboard", "-o"],
            ["wl-paste", "--no-newline"],
            ["powershell", "-NoProfile", "-command", "Get-Clipboard"],
        ):
            try:
                if not shutil.which(cmd[0]):
                    continue
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if out.returncode == 0 and out.stdout:
                    return out.stdout
            except Exception:
                continue
        return ""

    def _paste_paths_from_clipboard(self) -> bool:
        paths = self._paths_from_drop_text(self._clipboard_text())
        if not paths:
            return False
        loaded_names: list[str] = []
        surfaces: list[Surface] = []
        for p in paths:
            try:
                surfaces.append(pygame.image.load(str(p)).convert_alpha())
                loaded_names.append(p.name)
            except Exception as e:
                self._status_bar.error(f"Failed: {p.name}: {e}")
        if not surfaces:
            return True
        names = loaded_names
        combined = self._build_combined_surface(
            surfaces, horizontal=self._stack_horizontal
        )
        if self.doc.has_canvas:
            self.commands.push(
                AppendSheetCommand(
                    combined, names=names, horizontal=self._stack_horizontal
                ),
                self.doc,
                self.selection,
            )
            n = len(surfaces)
            msg = f"Appended {n} sheet{'s' if n != 1 else ''}"
        else:
            self._load_surface(combined, names)
            self.doc.tile_size = self._detect_tile_size(surfaces[0])
            msg = f"Loaded {len(surfaces)} sheet{'s' if len(surfaces) != 1 else ''}"
        self._status_bar.success(msg)
        self._toast(msg)
        return True

    def _flush_pending_drops(self) -> None:
        paths, self._pending_drops = self._pending_drops, None
        if not paths:
            return
        valid = [p for p in paths if p.suffix.lower() in IMAGE_EXTS and p.is_file()]
        skipped = len(paths) - len(valid)
        if not valid:
            self._status_bar.warning("Drop ignored — no supported image files")
            return
        if skipped:
            self._status_bar.info(
                f"Skipped {skipped} unsupported file{'s' if skipped != 1 else ''}"
            )
        self._on_add_sheets(valid)

    def _draw_drop_overlay(self, screen: Surface) -> None:
        area = self._content_rect()
        overlay = Surface(area.size, pygame.SRCALPHA)
        overlay.fill((*COLORS.accent_active[:3], 28))
        screen.blit(overlay, area.topleft)
        pygame.draw.rect(screen, COLORS.accent_active, area, 2, border_radius=4)
        surf = FONTS.get_small_font().render("Drop image sheets to load", True, COLORS.text)
        screen.blit(surf, surf.get_rect(center=area.center))

    # -- draw ----------------------------------------------------------------
    def draw(self, screen: Surface) -> None:
        draw_panel(screen, self.rect, COLORS.bg, COLORS.border)

        toolbar_rect = Rect(self.rect.x, self.rect.y + MENU_H, self.rect.w, TOOLBAR_H)
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

        # menubar last among chrome so open dropdowns sit above the toolbar,
        # viewport and status bar (they span past the 30px bar into canvas)
        self.menubar.draw(screen)

        self._notifications.draw(screen)

        if self._drop_hover:
            self._draw_drop_overlay(screen)

        if self._context_menu.is_open:
            self._context_menu.draw(screen)

        if self._show_shortcuts:
            self._draw_shortcuts(screen)

        mouse_pos = pygame.mouse.get_pos()
        for btn in self._buttons:
            if btn.rect.collidepoint(mouse_pos) and btn.tooltip_text:
                self._draw_tooltip(screen, btn.tooltip_text, mouse_pos)
                break

    SHORTCUTS = [
        ("Open", "Ctrl+O"), ("Save", "Ctrl+S"), ("Export PNGs", "Ctrl+E"),
        ("Undo", "Ctrl+Z"), ("Redo", "Ctrl+Shift+Z"),
        ("Cut / Copy / Paste", "Ctrl+X/C/V"), ("Select All", "Ctrl+A"),
        ("Deselect", "Esc"), ("Text label", "T → drag, Enter bake, drag ○ rotate"),
        ("Fit to window", "F"), ("Toggle grid", "G"),
        ("Reset zoom", "0"), ("Zoom in / out", "+ / -"),
    ]

    def _draw_shortcuts(self, screen: Surface) -> None:
        overlay = Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
        overlay.fill((*COLORS.overlay, 140))
        screen.blit(overlay, self.rect.topleft)

        row_h = 24
        w, h = 360, len(self.SHORTCUTS) * row_h + 60
        panel = Rect(0, 0, w, h)
        panel.center = self.rect.center
        pygame.draw.rect(screen, COLORS.panel, panel, border_radius=6)
        pygame.draw.rect(screen, COLORS.border, panel, 1, border_radius=6)

        title = FONTS.get_bold_font(15).render("Keyboard Shortcuts", True, COLORS.text)
        screen.blit(title, (panel.x + 20, panel.y + 14))

        lbl_font = FONTS.get_font(13)
        key_font = FONTS.get_small_font()
        y = panel.y + 46
        for label, keys in self.SHORTCUTS:
            screen.blit(lbl_font.render(label, True, COLORS.text), (panel.x + 20, y))
            ksurf = key_font.render(keys, True, COLORS.text_dim)
            screen.blit(ksurf, (panel.right - ksurf.get_width() - 20, y + 2))
            y += row_h

        hint = key_font.render("Click anywhere to close", True, COLORS.text_muted)
        screen.blit(hint, hint.get_rect(midtop=(panel.centerx, panel.bottom - 22)))

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
            allowed_exts=list(IMAGE_EXTS),
            on_select=self._on_add_sheets,
            mode="open",
            on_cancel=self._close_file_manager,
            multi_select=True,
            data_root=self._data_root,
        )

    def _on_add_sheets(self, selection: Path | list[Path]) -> None:
        if isinstance(selection, Path):
            selection = [selection]
        if self._sort_natural:
            selection = sorted(selection, key=lambda p: natural_key(p.name))
        loaded_names: list[str] = []
        surfaces: list[Surface] = []
        for path in selection:
            try:
                surfaces.append(pygame.image.load(str(path)).convert_alpha())
                loaded_names.append(path.name)
            except Exception as e:
                self._status_bar.error(f"Failed: {path.name}: {e}")
        if surfaces:
            was_empty = not self.doc.has_canvas
            combined = self._build_combined_surface(surfaces, horizontal=self._stack_horizontal)
            if was_empty:
                self._load_surface(combined, loaded_names)
                detected = self._detect_tile_size(surfaces[0])
                self.doc.tile_size = detected
            else:
                # never clobber existing content: each import pass appends
                # its block (undoable) per the current stacking direction
                self.commands.push(
                    AppendSheetCommand(
                        combined,
                        names=loaded_names,
                        horizontal=self._stack_horizontal,
                    ),
                    self.doc,
                    self.selection,
                )
            n = len(surfaces)
            plural = "s" if n != 1 else ""
            msg = f"Loaded {n} sheet{plural}" if was_empty else f"Appended {n} sheet{plural}"
            self._status_bar.success(msg)
            self._toast(msg)
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
