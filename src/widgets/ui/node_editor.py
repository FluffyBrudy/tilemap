import pygame
from pygame import Rect
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from editor import Editor
from nodes import NodeRect
from widgets.ui.theme import COLORS, FONTS, SHAPE
from widgets.ui.draw_utils import draw_panel
from widgets.ui.property_editor import PropertyEditor
from widgets.ui.particle_config_dialog import ParticleConfigDialog, Dropdown
from widgets.particle_presets import PRESETS, get_preset_names, get_preset_config
from utils.font_manager import font_manager, FontWeight


class NodeEditor:
    def __init__(self, editor: "Editor", x: int, y: int, w: int = 260, h: int = 180):
        self.editor = editor
        self.rect = Rect(x, y, w, h)

        self.font = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)
        self.font_bold = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.BOLD)
        self.font_input = font_manager.get_font(FONTS.name, 11, FontWeight.REGULAR)

        self._editing_field: Optional[str] = None
        self._input_text: str = ""
        self.text_selected: bool = False

        self._is_dragging = False
        self._drag_offset = (0, 0)
        self._last_node_id: Optional[str] = None

        self._preset_dd: Optional[Dropdown] = None
        self._preset_names: List[str] = get_preset_names()
        self._is_particle = False

    def resize(self, x: int, y: int, w: int):
        self.rect = Rect(x, y, w, self.rect.height)

    def _header_rect(self) -> Rect:
        return Rect(self.rect.x, self.rect.y, self.rect.width, 24)

    def reposition_near_node(self):
        node = self.editor.node_manager.get_active_node()
        if node is None:
            return
        grid = self.editor.tile_grid_widget
        if not grid:
            self.rect.x = max(10, self.rect.x)
            self.rect.y = max(10, self.rect.y)
            return
        sx, sy = grid._node_to_screen(node.area.x, node.area.y)
        sw, sh = grid._node_screen_size(node.area.w, node.area.h)
        screen_w = self.editor.screen.get_width()
        screen_h = self.editor.screen.get_height()
        panel_w = self.rect.width
        panel_h = self.rect.height
        px = sx + sw + 8
        py = sy + sh + 8
        if px + panel_w > screen_w - 10:
            px = max(10, sx - panel_w - 8)
        if py + panel_h > screen_h - 10:
            py = max(10, sy - panel_h - 8)
        self.rect.x = max(10, min(px, screen_w - panel_w - 10))
        self.rect.y = max(10, min(py, screen_h - panel_h - 10))

    @property
    def editing_field(self) -> bool:
        return self._editing_field is not None

    @property
    def visible(self) -> bool:
        return (
            self.editor.node_editing_mode
            and (
                self.editor.node_manager.active_node_id is not None
                or self.editor.node_manager.active_group_name is not None
            )
        )

    def _fields(self) -> List[Tuple[str, str, str]]:
        mgr = self.editor.node_manager
        if mgr.active_group_name is not None:
            return [("group_name", "Group", mgr.active_group_name)]
        node = mgr.get_active_node()
        if node is None:
            return []
        return [
            ("name", "Name", node.name),
            ("layer", "Layer", node.layer_name),
            ("x", "X", str(node.area.x)),
            ("y", "Y", str(node.area.y)),
            ("w", "W", str(node.area.w)),
            ("h", "H", str(node.area.h)),
        ]

    def _get_field_rects(self) -> List[Tuple[str, Rect]]:
        x = self.rect.x + 8
        y = self.rect.y + 24
        results = []
        for key, label, _ in self._fields():
            label_w = 40
            label_rect = Rect(x, y, label_w, 18)
            input_rect = Rect(x + label_w + 2, y, self.rect.width - label_w - 16, 18)
            results.append((key, label_rect, input_rect))
            y += 22
        return results

    def _get_input_at(self, pos) -> Optional[str]:
        for key, _, input_rect in self._get_field_rects():
            if input_rect.collidepoint(pos):
                return key
        return None

    def _preset_rect(self) -> Optional[Rect]:
        if not self._is_particle:
            return None
        y = self.rect.y + 24 + len(self._fields()) * 22 + 4
        w = self.rect.width - 74
        return Rect(self.rect.x + 64, y, w, 22)

    def _buttons(self):
        if not self.visible or self.editor.node_manager.active_group_name is not None:
            return []
        node = self.editor.node_manager.get_active_node()
        if not node:
            return []
        rows = len(self._fields())
        if node.node_type == "particle_emitter":
            rows += 1
        y_base = self.rect.y + 24 + rows * 22 + 4
        buttons = []
        self._is_particle = node.node_type == "particle_emitter"
        if self._is_particle:
            r = Rect(self.rect.x + 8, y_base, self.rect.width - 16, 22)
            buttons.append((r, "particle"))
            r2 = Rect(self.rect.x + 8, y_base + 26, self.rect.width - 16, 22)
            buttons.append((r2, "props"))
        else:
            r = Rect(self.rect.x + 8, y_base, self.rect.width - 16, 22)
            buttons.append((r, "props"))
        return buttons

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        mgr = self.editor.node_manager
        node = mgr.get_active_node()
        is_group_active = mgr.active_group_name is not None
        if node is None and not is_group_active:
            return False

        mouse_pos = pygame.mouse.get_pos()

        # Check preset dropdown first (before field commit logic)
        if self._is_particle and self._preset_dd is not None:
            result = self._preset_dd.handle_event(event)
            if result is not None:
                if result != "Custom":
                    cfg = get_preset_config(result)
                    node.properties.clear()
                    node.properties.update(cfg)
                    self.editor.tile_grid_widget.reset_particle_preview(node.node_id, cfg)
                self._preset_dd.selected = result
                return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if not self.rect.collidepoint(mouse_pos):
                if self._editing_field is not None:
                    self._commit_field()
                return False

            if event.button == 1:
                if self._header_rect().collidepoint(mouse_pos):
                    self._is_dragging = True
                    self._drag_offset = (
                        mouse_pos[0] - self.rect.x,
                        mouse_pos[1] - self.rect.y,
                    )
                    return True

                key = self._get_input_at(mouse_pos)
                if key is not None:
                    if self._editing_field is not None and self._editing_field != key:
                        self._commit_field()
                    self._editing_field = key
                    self._input_text = self._get_field_value(key)
                    self.text_selected = True
                else:
                    if self._editing_field is not None:
                        self._commit_field()
                        self._editing_field = None
                        self.text_selected = False

                for rect, action in self._buttons():
                    if rect and rect.collidepoint(mouse_pos):
                        if action == "props":
                            node = mgr.get_active_node()
                            if node:
                                self.editor.property_editor = PropertyEditor(
                                    self.editor,
                                    f"Node Properties: {node.name}",
                                    dict(node.properties),
                                    on_save=lambda props: self._save_props(props),
                                    on_close=lambda: None,
                                )
                        elif action == "particle":
                            node = mgr.get_active_node()
                            if node:
                                self.editor.particle_config_dialog = ParticleConfigDialog(
                                    self.editor,
                                    dict(node.properties),
                                    node.node_id,
                                    on_save=lambda cfg: self._save_particle_config(cfg),
                                )
                        return True

                return True

        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self._is_dragging:
                self._is_dragging = False
                return True

        if event.type == pygame.MOUSEMOTION:
            if self._is_dragging:
                self.rect.x = mouse_pos[0] - self._drag_offset[0]
                self.rect.y = mouse_pos[1] - self._drag_offset[1]
                screen_w = self.editor.screen.get_width()
                screen_h = self.editor.screen.get_height()
                self.rect.x = max(0, min(self.rect.x, screen_w - self.rect.width))
                self.rect.y = max(0, min(self.rect.y, screen_h - self.rect.height))
                return True

        if event.type == pygame.KEYDOWN and self._editing_field is not None:
            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
            meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)
            cmd_held = ctrl_held or meta_held

            if cmd_held and event.key == pygame.K_a:
                self.text_selected = True
                return True
            elif event.key == pygame.K_BACKSPACE:
                pressed = pygame.key.get_pressed()
                meta_down = pressed[pygame.K_LMETA] or pressed[pygame.K_RMETA]
                ctrl_down = pressed[pygame.K_LCTRL] or pressed[pygame.K_RCTRL]
                if meta_down or ctrl_down or self.text_selected:
                    self._input_text = ""
                    self.text_selected = False
                else:
                    self._input_text = self._input_text[:-1]
                return True
            elif event.key == pygame.K_RETURN:
                self._commit_field()
                self._editing_field = None
                self.text_selected = False
                return True
            elif event.key == pygame.K_ESCAPE:
                self._editing_field = None
                self.text_selected = False
                return True
            elif event.unicode.isprintable() and event.unicode != "":
                if self.text_selected:
                    self._input_text = event.unicode
                    self.text_selected = False
                else:
                    self._input_text += event.unicode
                return True

        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(mouse_pos):
                return True

        return False

    def _get_field_value(self, key: str) -> str:
        mgr = self.editor.node_manager
        if mgr.active_group_name is not None:
            if key == "group_name":
                return mgr.active_group_name
            return ""
        node = mgr.get_active_node()
        if node is None:
            return ""
        if key == "name":
            return node.name
        if key == "layer":
            return node.layer_name
        if key == "x":
            return str(node.area.x)
        if key == "y":
            return str(node.area.y)
        if key == "w":
            return str(node.area.w)
        if key == "h":
            return str(node.area.h)
        return ""

    def _commit_field(self):
        if self._editing_field is None:
            return
        mgr = self.editor.node_manager
        val = self._input_text
        if mgr.active_group_name is not None:
            if self._editing_field == "group_name":
                old_name = mgr.active_group_name
                if mgr.rename_group(old_name, val):
                    self.editor.node_selector._rebuild_filter()
                    self.editor.tilemap.capture_history("Rename Group")
            return
        node = mgr.get_active_node()
        if node is None:
            return
        if self._editing_field == "name":
            node.name = val
        elif self._editing_field == "layer":
            node.layer_name = val
        elif self._editing_field == "x":
            node.area.x = self._parse_int(val, node.area.x)
        elif self._editing_field == "y":
            node.area.y = self._parse_int(val, node.area.y)
        elif self._editing_field == "w":
            node.area.w = max(1, self._parse_int(val, node.area.w))
        elif self._editing_field == "h":
            node.area.h = max(1, self._parse_int(val, node.area.h))

    def _parse_int(self, s: str, default: int) -> int:
        try:
            return int(s)
        except (ValueError, TypeError):
            return default

    def _save_props(self, props: dict):
        node = self.editor.node_manager.get_active_node()
        if node:
            node.properties = props

    def _save_particle_config(self, cfg: dict):
        node = self.editor.node_manager.get_active_node()
        if node:
            node.properties.clear()
            node.properties.update(cfg)

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return

        mgr = self.editor.node_manager
        active_id = mgr.active_node_id
        if active_id != self._last_node_id:
            self._last_node_id = active_id
            self.reposition_near_node()

        draw_panel(screen, self.rect, bg=COLORS.panel, border=COLORS.border, radius=SHAPE.radius_sm)

        title = "Group Editor" if mgr.active_group_name is not None else "Node Editor"
        header = self.font_bold.render(title, True, COLORS.text)
        screen.blit(header, (self.rect.x + 8, self.rect.y + 6))

        fields = self._fields()
        field_data = self._get_field_rects()

        for (key, label_rect, input_rect), (fkey, flabel, fvalue) in zip(field_data, fields):
            lbl = self.font.render(flabel, True, COLORS.text_dim)
            screen.blit(lbl, (label_rect.x, label_rect.y + 2))

            pygame.draw.rect(screen, COLORS.panel_alt, input_rect, border_radius=SHAPE.radius_sm)
            pygame.draw.rect(screen, COLORS.border_soft, input_rect, 1, border_radius=SHAPE.radius_sm)

            if self._editing_field == key:
                if self.text_selected:
                    base_txt = self.font_input.render(self._input_text, True, COLORS.text)
                    txt_w = base_txt.get_width()
                    txt_h = base_txt.get_height()
                    highlight_rect = Rect(input_rect.x + 3, input_rect.y + 2, max(4, txt_w), txt_h)
                    pygame.draw.rect(screen, (50, 100, 200), highlight_rect)
                    txt = self.font_input.render(self._input_text, True, (255, 255, 255))
                else:
                    display = self._input_text + ("|" if pygame.time.get_ticks() % 1000 < 500 else "")
                    txt = self.font_input.render(display, True, COLORS.text)
            else:
                txt = self.font_input.render(fvalue, True, COLORS.text_muted)

            screen.blit(txt, (input_rect.x + 3, input_rect.y + 2))

        # Preset dropdown for particle emitters
        node = mgr.get_active_node()
        is_particle = node is not None and node.node_type == "particle_emitter"
        self._is_particle = is_particle

        if is_particle:
            pr = self._preset_rect()
            if pr:
                lbl = self.font.render("Preset", True, COLORS.text_dim)
                screen.blit(lbl, (pr.x - 58, pr.y + 2))

                # Build or update the dropdown
                if self._preset_dd is None or self._preset_dd.rect != pr:
                    current = "Custom"
                    if node and node.properties:
                        for p in PRESETS:
                            if node.properties == p["config"]:
                                current = p["name"]
                                break
                    opts = ["Custom"] + self._preset_names
                    self._preset_dd = Dropdown(pr, opts, current, max_visible=12)

                self._preset_dd.draw(screen, (40, 44, 50), (60, 64, 69))

        for rect, action in self._buttons():
            if action == "particle":
                pygame.draw.rect(screen, (200, 100, 160), rect, border_radius=SHAPE.radius_sm)
                txt = self.font.render("Particle Config...", True, COLORS.text)
            else:
                pygame.draw.rect(screen, COLORS.accent, rect, border_radius=SHAPE.radius_sm)
                txt = self.font.render("Properties...", True, COLORS.text)
            screen.blit(txt, txt.get_rect(center=rect.center))

        # Draw dropdown options on top
        if self._preset_dd is not None and self._preset_dd.open:
            self._preset_dd.draw_options(screen)
