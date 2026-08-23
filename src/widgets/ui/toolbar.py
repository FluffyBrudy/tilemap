from typing import TYPE_CHECKING

import pygame
from pygame import Rect

if TYPE_CHECKING:
    from editor import Editor
from widgets.ui.button import Button
from widgets.ui.draw_utils import draw_panel
from widgets.ui.theme import COLORS, SHAPE, SPACING
from widgets.ui.tool_manager import ToolKind


class Toolbar:
    def __init__(self, editor: "Editor", x: int, y: int, w: int, h: int = 35):
        self.editor = editor
        self.rect = Rect(x, y, w, h)
        self.btn_size = 28
        self.gap = SPACING["sm"] + 2
        self.sep_w = 10
        self.pad = SPACING["md"]
        self._buttons: list[Button] = []
        self._separator_centers: list[int] = []
        self._layout_buttons()

    def _build_tool_buttons(self, x: int, y: int, btn_h: int) -> int:
        def add(key, ico, tip):
            nonlocal x
            btn = Button(
                Rect(x, y, self.btn_size, btn_h),
                icon_key=ico,
                tooltip_text=tip,
                border_radius=SHAPE.radius_sm,
                on_click=lambda k=key: self._on_tool_click(k),
            )
            btn.tool_key = key
            self._buttons.append(btn)
            x += self.btn_size + self.gap

        def sep():
            nonlocal x
            self._separator_centers.append(x + self.sep_w // 2)
            x += self.sep_w

        sep()
        add("pan", "pan", "Pan Mode (Ctrl+Space)")
        add("select", "select", "Select/Move Tool")
        add("eraser", "eraser", "Eraser Tool")
        sep()
        add("grid", "grid", "Toggle Grid (G)")
        add("auto", "auto", "Auto-Autotile")
        add("nodes", "nodes", "Show Nodes (Ctrl+Shift+N)")
        sep()
        add("zoom_out", "zoomout", "Zoom Out (Ctrl+Wheel)")
        add("zoom_in", "zoomin", "Zoom In (Ctrl+Wheel)")
        add("reset", "reset", "Reset View")
        add("fit", "fit", "Fit Map to View")

        return x

    def _on_tool_click(self, key: str):
        e = self.editor
        if key == "pan":
            e.tool_manager.toggle(ToolKind.PAN)
        elif key == "select":
            e.tool_manager.toggle(ToolKind.SELECT)
        elif key == "eraser":
            e.tool_manager.toggle(ToolKind.ERASER)
        elif key == "grid":
            e.toggle_grid()
        elif key == "auto":
            e.toggle_auto_autotile()
        elif key == "nodes":
            e.show_nodes = not e.show_nodes
            if e.show_nodes:
                e.node_editing_mode = False
        elif key == "zoom_in" and e.tile_grid_widget:
            e.tile_grid_widget.zoom_by(0.1)
        elif key == "zoom_out" and e.tile_grid_widget:
            e.tile_grid_widget.zoom_by(-0.1)
        elif key == "reset" and e.tile_grid_widget:
            e.tile_grid_widget.reset_view()
        elif key == "fit" and e.tile_grid_widget:
            e.tile_grid_widget.fit_to_map()

    def _update_active_states(self):
        e = self.editor
        for btn in self._buttons:
            k = getattr(btn, "tool_key", btn.icon_key)
            if k == "pan":
                btn.active = e.tool_manager.is_active(ToolKind.PAN)
            elif k == "select":
                btn.active = e.tool_manager.is_active(ToolKind.SELECT)
            elif k == "eraser":
                btn.active = e.tool_manager.is_active(ToolKind.ERASER)
            elif k == "grid":
                btn.active = bool(e.tile_grid_widget and e.tile_grid_widget.show_grid)
            elif k == "auto":
                btn.active = e.autotile_mode
            elif k == "nodes":
                btn.active = e.show_nodes
            else:
                btn.active = False

    def resize(self, width: int):
        self.rect.width = width
        self._layout_buttons()

    def _layout_buttons(self):
        self._buttons.clear()
        self._separator_centers.clear()
        x = self.rect.x + self.pad
        y = self.rect.y + (self.rect.height - self.btn_size) // 2
        self._build_tool_buttons(x, y, self.btn_size)

    def handle_event(self, event: pygame.event.Event) -> bool:
        return any(btn.handle_event(event) for btn in self._buttons)

    def draw(self, screen: pygame.Surface):
        draw_panel(
            screen, self.rect, bg=COLORS.header, border=COLORS.border_soft, radius=0
        )
        mouse_pos = pygame.mouse.get_pos()

        self._update_active_states()

        sep_h = 16
        sep_y = self.rect.centery - sep_h // 2
        for sx in self._separator_centers:
            pygame.draw.line(
                screen, COLORS.border_soft,
                (sx, sep_y), (sx, sep_y + sep_h), 2,
            )

        for btn in self._buttons:
            btn.draw(screen)

        for btn in self._buttons:
            if btn.rect.collidepoint(mouse_pos) and btn.tooltip_text:
                self.editor.tooltip.show(
                    btn.tooltip_text,
                    (mouse_pos[0] + 10, mouse_pos[1] + 10),
                )
                break
