import pygame
from pygame import Rect
from typing import TYPE_CHECKING, Dict, Tuple

if TYPE_CHECKING:
    from editor import Editor
from widgets.ui.theme import COLORS, FONTS, SHAPE
from widgets.ui.draw_utils import draw_panel
from utils.icon_manager import icon_manager


class Toolbar:
    def __init__(self, editor: "Editor", x: int, y: int, w: int, h: int = 35):
        self.editor = editor
        self.rect = Rect(x, y, w, h)
        self.font = pygame.font.SysFont(FONTS.name, FONTS.size_sm)
        self.buttons: Dict[str, Tuple[Rect, str]] = {}
        self._layout_buttons()

    def resize(self, width: int):
        self.rect.width = width
        self._layout_buttons()

    def _layout_buttons(self):
        pad = 8
        x = self.rect.x + pad
        y = self.rect.y + 5
        h = self.rect.height - 10
        btn_w = 74
        gap = 6

        def add_btn(key: str, label: str):
            nonlocal x
            self.buttons[key] = (Rect(x, y, btn_w, h), label)
            x += btn_w + gap

        add_btn("pan", "Pan")
        add_btn("select", "Select")
        add_btn("eraser", "Eraser")
        add_btn("grid", "Grid")
        add_btn("auto", "Auto")
        add_btn("nodes", "Nodes")
        x += 6
        add_btn("zoom_out", "Zoom -")
        add_btn("zoom_in", "Zoom +")
        add_btn("reset", "Reset")
        add_btn("fit", "Fit")

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, (r, label) in self.buttons.items():
                if r.collidepoint(event.pos):
                    if key == "pan":
                        self.editor.pan_mode = not self.editor.pan_mode
                        if self.editor.pan_mode:
                            self.editor.select_mode = False
                            self.editor.eraser_mode = False
                    elif key == "select":
                        self.editor.select_mode = not self.editor.select_mode
                        if self.editor.select_mode:
                            self.editor.pan_mode = False
                            self.editor.eraser_mode = False
                    elif key == "eraser":
                        self.editor.eraser_mode = not self.editor.eraser_mode
                        if self.editor.eraser_mode:
                            self.editor.pan_mode = False
                            self.editor.select_mode = False
                    elif key == "grid":
                        self.editor.toggle_grid()
                    elif key == "auto":
                        self.editor.toggle_auto_autotile()
                    elif key == "nodes":
                        self.editor.show_nodes = not self.editor.show_nodes
                        if self.editor.show_nodes:
                            self.editor.node_editing_mode = False
                    elif key == "zoom_in":
                        if self.editor.tile_grid_widget:
                            self.editor.tile_grid_widget.zoom_by(0.1)
                    elif key == "zoom_out":
                        if self.editor.tile_grid_widget:
                            self.editor.tile_grid_widget.zoom_by(-0.1)
                    elif key == "reset":
                        if self.editor.tile_grid_widget:
                            self.editor.tile_grid_widget.reset_view()
                    elif key == "fit":
                        if self.editor.tile_grid_widget:
                            self.editor.tile_grid_widget.fit_to_map()
                    return True
        return False

    def draw(self, screen: pygame.Surface):
        draw_panel(
            screen, self.rect, bg=COLORS.header, border=COLORS.border_soft, radius=0
        )
        mouse_pos = pygame.mouse.get_pos()

        for key, (r, label) in self.buttons.items():
            is_active = False
            is_show = False
            if key == "pan":
                is_active = self.editor.pan_mode
            elif key == "select":
                is_active = self.editor.select_mode
            elif key == "eraser":
                is_active = self.editor.eraser_mode
            elif key == "grid":
                is_active = bool(
                    self.editor.tile_grid_widget
                    and self.editor.tile_grid_widget.show_grid
                )
            elif key == "auto":
                is_active = self.editor.autotile_mode
            elif key == "nodes":
                is_active = self.editor.show_nodes
                is_show = False

            hover = r.collidepoint(mouse_pos)
            if is_active:
                bg = COLORS.accent_active
            elif is_show:
                bg = COLORS.selected
            elif hover:
                bg = COLORS.hover
            else:
                bg = COLORS.panel_alt
            pygame.draw.rect(screen, bg, r, border_radius=SHAPE.radius_sm)
            pygame.draw.rect(
                screen, COLORS.border_soft, r, 1, border_radius=SHAPE.radius_sm
            )

            if icon_manager.has_icon(key):
                icon = icon_manager.get_icon(key, 16, COLORS.text)
                screen.blit(icon, icon.get_rect(center=r.center))
            else:
                txt = self.font.render(label, True, COLORS.text)
                screen.blit(txt, txt.get_rect(center=r.center))

            if hover:
                tip = label
                if key == "pan":
                    tip = "Pan Mode (Ctrl+Space)"
                elif key == "select":
                    tip = "Select/Move Tool (Rect select, drag to move)"
                elif key == "eraser":
                    tip = "Eraser Tool (Left-click to erase)"
                elif key == "grid":
                    tip = "Toggle Grid (G)"
                elif key == "auto":
                    tip = "Auto-Autotile"
                elif key == "nodes":
                    tip = (
                        "Show Nodes (Ctrl+Shift+N for Edit mode)"
                        if not self.editor.show_nodes
                        else "Hide Nodes"
                    )
                elif key == "zoom_in":
                    tip = "Zoom In (Ctrl+Wheel)"
                elif key == "zoom_out":
                    tip = "Zoom Out (Ctrl+Wheel)"
                elif key == "reset":
                    tip = "Reset View"
                elif key == "fit":
                    tip = "Fit Map to View"
                self.editor.tooltip.show(tip, (mouse_pos[0] + 10, mouse_pos[1] + 10))
