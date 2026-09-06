from typing import TYPE_CHECKING

import pygame
from pygame import Rect

if TYPE_CHECKING:
    from editor import Editor
from utils.context_dispatch import ContextKind, PropertyContext
from utils.font_manager import FontWeight, font_manager
from widgets.particle_presets import PRESETS, get_preset_config, get_preset_names
from widgets.ui.draw_utils import draw_panel
from widgets.ui.node_selector import NodeSelector
from widgets.ui.particle_config_dialog import Dropdown, ParticleConfigDialog
from widgets.ui.property_editor import PropertyEditor
from widgets.ui.theme import COLORS, FONTS, SHAPE


class NodeEditor:
    HEADER_H = 24
    FIELDS_TOP = 32
    FIELD_H = 22
    FIELD_PITCH = 27
    SECTION_GAP = 10
    PRESET_H = 26
    BUTTON_H = 28
    BUTTON_GAP = 10
    SIDE_PAD = 12
    BOTTOM_PAD = 12

    def __init__(self, editor: "Editor", x: int, y: int, w: int = 260, h: int = 180):
        self.editor = editor
        self.rect = Rect(x, y, w, h)

        self._dock_x = x
        self._dock_y = y

        self.font = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.REGULAR)
        self.font_bold = font_manager.get_font(FONTS.name, FONTS.size_sm, FontWeight.BOLD)
        self.font_input = font_manager.get_font(FONTS.name, 11, FontWeight.REGULAR)

        self._editing_field: str | None = None
        self._input_text: str = ""
        self.text_selected: bool = False

        self._is_dragging = False
        self._drag_offset = (0, 0)
        self._last_node_id: str | None = None

        self._preset_dd: Dropdown | None = None
        self._preset_owner: str | None = None
        self._preset_names: list[str] = get_preset_names()
        self._is_particle = False

        d = self.editor.context_dispatch
        d.register_opener(ContextKind.NODE, self._open_node_properties)
        d.register_saver(ContextKind.NODE, self._save_props)

    def resize(self, x: int, y: int, w: int):
        self.rect = Rect(x, y, w, self.rect.height)

    def _header_rect(self) -> Rect:
        return Rect(self.rect.x, self.rect.y, self.rect.width, 24)

    def _sidebar_avoid_rects(self, screen_w: int) -> list[Rect]:
        """Panels the floating editor must not cover (besides the node)."""
        avoid: list[Rect] = [Rect(0, 0, screen_w, 65)]  # menu + toolbar strip
        selector = getattr(self.editor, "node_selector", None)
        if selector is not None and getattr(selector, "visible", False):
            try:
                avoid.append(selector.rect.copy())
            except Exception:
                pass
        return avoid

    @staticmethod
    def _pick_position(
        positions: list[tuple[int, int]],
        panel_w: int,
        panel_h: int,
        screen_w: int,
        screen_h: int,
        avoid: list[Rect],
    ) -> tuple[int, int]:
        """First candidate (screen-clamped) clear of all avoid rects.

        Falls back to the first candidate clamped on-screen when every
        candidate overlaps something (tiny screens).
        """
        fallback: tuple[int, int] | None = None
        for px, py in positions:
            cx = max(10, min(px, screen_w - panel_w - 10))
            cy = max(10, min(py, screen_h - panel_h - 10))
            if fallback is None:
                fallback = (cx, cy)
            if not any(Rect(cx, cy, panel_w, panel_h).colliderect(a) for a in avoid):
                return (cx, cy)
        if fallback is None:
            # No candidates at all: stay at the clamp floor.
            return (10, 10)
        return fallback

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
        pad = 24

        node_rect = Rect(sx, sy, sw, sh)
        positions = [
            (sx + sw + pad, sy),
            (sx - panel_w - pad, sy),
            (sx, sy + sh + pad),
            (sx, sy - panel_h - pad),
        ]
        avoid = [node_rect] + self._sidebar_avoid_rects(screen_w)
        best = self._pick_position(positions, panel_w, panel_h, screen_w, screen_h, avoid)

        dock = Rect(self._dock_x, self._dock_y, panel_w, panel_h)
        probe = Rect(best[0], best[1], panel_w, panel_h)
        if any(probe.colliderect(a) for a in avoid[1:]) and not any(dock.colliderect(a) for a in avoid[1:]):
            best = (self._dock_x, self._dock_y)
        self.rect.x, self.rect.y = best

    def _nudge_out_of_sidebar(self):
        """After a manual drag, shift out of the node list if overlapping."""
        selector = getattr(self.editor, "node_selector", None)
        if selector is None or not getattr(selector, "visible", False):
            return
        try:
            sel_rect = selector.rect
        except Exception:
            return
        if not self.rect.colliderect(sel_rect):
            return
        try:
            screen_w = self.editor.screen.get_width()
        except Exception:
            screen_w = 800
        cand_x = sel_rect.right + 10
        if cand_x + self.rect.width <= screen_w - 10:
            self.rect.x = cand_x
        else:
            self.rect.x, self.rect.y = self._dock_x, self._dock_y

    @property
    def editing_field(self) -> bool:
        return self._editing_field is not None

    @property
    def visible(self) -> bool:
        return self.editor.node_editing_mode and (
            self.editor.node_manager.active_node_id is not None
            or self.editor.node_manager.active_group_name is not None
        )

    def _fields(self) -> list[tuple[str, str, str]]:
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

    def _get_field_rects(self) -> list[tuple[str, Rect, Rect]]:
        x = self.rect.x + self.SIDE_PAD
        y = self.rect.y + self.FIELDS_TOP
        results = []
        for key, _label, _ in self._fields():
            label_w = 44
            label_rect = Rect(x, y, label_w, self.FIELD_H)
            input_rect = Rect(
                x + label_w + 4,
                y,
                self.rect.width - label_w - 2 * self.SIDE_PAD - 4,
                self.FIELD_H,
            )
            results.append((key, label_rect, input_rect))
            y += self.FIELD_PITCH
        return results

    def _get_input_at(self, pos) -> str | None:
        for key, _, input_rect in self._get_field_rects():
            if input_rect.collidepoint(pos):
                return key
        return None

    def _fields_end_y(self) -> int:
        return self.rect.y + self.FIELDS_TOP + len(self._fields()) * self.FIELD_PITCH

    def _active_node_is_particle(self) -> bool:
        node = self.editor.node_manager.get_active_node()
        return node is not None and node.node_type == "particle_emitter"

    def _preset_rect(self) -> Rect | None:
        if not self._active_node_is_particle():
            return None
        y = self._fields_end_y() + self.SECTION_GAP
        w = self.rect.width - 76
        return Rect(self.rect.x + 64, y, w, self.PRESET_H)

    def _buttons_top(self) -> int:
        y = self._fields_end_y() + self.SECTION_GAP
        if self._active_node_is_particle():
            y += self.PRESET_H + self.SECTION_GAP
        return y

    def _buttons(self):
        if not self.visible or self.editor.node_manager.active_group_name is not None:
            return []
        node = self.editor.node_manager.get_active_node()
        if not node:
            return []
        y_base = self._buttons_top()
        buttons = []
        self._is_particle = node.node_type == "particle_emitter"
        if self._is_particle:
            r = Rect(self.rect.x + self.SIDE_PAD, y_base, self.rect.width - 2 * self.SIDE_PAD, self.BUTTON_H)
            buttons.append((r, "particle"))
            r2 = Rect(
                self.rect.x + self.SIDE_PAD,
                y_base + self.BUTTON_H + self.BUTTON_GAP,
                self.rect.width - 2 * self.SIDE_PAD,
                self.BUTTON_H,
            )
            buttons.append((r2, "props"))
        else:
            r = Rect(self.rect.x + self.SIDE_PAD, y_base, self.rect.width - 2 * self.SIDE_PAD, self.BUTTON_H)
            buttons.append((r, "props"))
        return buttons

    def _content_height(self) -> int:
        """Full panel height for current content + bottom padding."""
        bottom = self._fields_end_y()
        buttons = self._buttons()
        if buttons:
            bottom = buttons[-1][0].bottom
        return bottom - self.rect.y + self.BOTTOM_PAD

    def _fit_height_to_content(self):
        self.rect.height = max(80, self._content_height())

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        mgr = self.editor.node_manager
        node = mgr.get_active_node()
        is_group_active = mgr.active_group_name is not None
        if node is None and not is_group_active:
            return False

        mouse_pos = pygame.mouse.get_pos()

        if self._active_node_is_particle() and self._preset_dd is not None:
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
                                self.editor.context_dispatch.open(PropertyContext(ContextKind.NODE, node))
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
                self._nudge_out_of_sidebar()
                return True

        if event.type == pygame.MOUSEMOTION and self._is_dragging:
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
            if event.key == pygame.K_BACKSPACE:
                pressed = pygame.key.get_pressed()
                meta_down = pressed[pygame.K_LMETA] or pressed[pygame.K_RMETA]
                ctrl_down = pressed[pygame.K_LCTRL] or pressed[pygame.K_RCTRL]
                if meta_down or ctrl_down or self.text_selected:
                    self._input_text = ""
                    self.text_selected = False
                else:
                    self._input_text = self._input_text[:-1]
                return True
            if event.key == pygame.K_RETURN:
                self._commit_field()
                self._editing_field = None
                self.text_selected = False
                return True
            if event.key == pygame.K_ESCAPE:
                self._editing_field = None
                self.text_selected = False
                return True
            if event.unicode.isprintable() and event.unicode != "":
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

    def _open_node_properties(self, ctx: PropertyContext) -> None:
        node = ctx.target
        if node is None:
            return
        self.editor.property_editor = PropertyEditor(
            self.editor,
            f"Node Properties: {node.name}",
            dict(node.properties),
            context=ctx,
        )

    def _save_props(self, ctx: PropertyContext, props: dict):
        node = ctx.target
        if node:
            node.properties = props
            self.editor.suggestion_registry.refresh(self.editor)

    def _save_particle_config(self, cfg: dict):
        node = self.editor.node_manager.get_active_node()
        if node:
            node.properties.clear()
            node.properties.update(cfg)
            self.editor.suggestion_registry.refresh(self.editor)
            self.editor.tile_grid_widget.reset_particle_preview(node.node_id, cfg)

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return

        self._fit_height_to_content()

        mgr = self.editor.node_manager
        active_id = mgr.active_node_id
        if active_id != self._last_node_id:
            self._last_node_id = active_id
            self.reposition_near_node()

        draw_panel(
            screen,
            self.rect,
            bg=COLORS.panel,
            border=COLORS.border,
            radius=SHAPE.radius_sm,
        )

        title = "Group Editor" if mgr.active_group_name is not None else "Node Editor"
        header = self.font_bold.render(title, True, COLORS.text)
        screen.blit(header, (self.rect.x + self.SIDE_PAD, self.rect.y + 7))

        fields = self._fields()
        field_data = self._get_field_rects()

        for (key, label_rect, input_rect), (_fkey, flabel, fvalue) in zip(field_data, fields, strict=False):
            lbl = self.font.render(flabel, True, COLORS.text_dim)
            screen.blit(lbl, (label_rect.x, label_rect.y + 4))

            pygame.draw.rect(screen, COLORS.panel_alt, input_rect, border_radius=SHAPE.radius_sm)
            pygame.draw.rect(screen, COLORS.border_soft, input_rect, 1, border_radius=SHAPE.radius_sm)

            if self._editing_field == key:
                if self.text_selected:
                    base_txt = self.font_input.render(self._input_text, True, COLORS.text)
                    txt_w = base_txt.get_width()
                    txt_h = base_txt.get_height()
                    highlight_rect = Rect(input_rect.x + 4, input_rect.y + 3, max(4, txt_w), txt_h)
                    pygame.draw.rect(screen, (50, 100, 200), highlight_rect)
                    txt = self.font_input.render(self._input_text, True, (255, 255, 255))
                else:
                    display = self._input_text + ("|" if pygame.time.get_ticks() % 1000 < 500 else "")
                    txt = self.font_input.render(display, True, COLORS.text)
            else:
                txt = self.font_input.render(fvalue, True, COLORS.text_muted)

            screen.blit(txt, (input_rect.x + 4, input_rect.y + 5))

        node = mgr.get_active_node()
        is_particle = node is not None and node.node_type == "particle_emitter"
        self._is_particle = is_particle

        if is_particle:
            pr = self._preset_rect()
            if pr:
                lbl = self.font.render("Preset", True, COLORS.text_dim)
                screen.blit(lbl, (pr.x - 58, pr.y + 6))

                owner = node.node_id if node else None
                if self._preset_dd is None or self._preset_dd.rect != pr or self._preset_owner != owner:
                    current = "Custom"
                    if node and node.properties:
                        for p in PRESETS:
                            if node.properties == p["config"]:
                                current = p["name"]
                                break
                    opts = ["Custom"] + self._preset_names
                    self._preset_dd = Dropdown(pr, opts, current, max_visible=12)
                    self._preset_owner = owner

                self._preset_dd.draw(screen, COLORS.header, COLORS.border)

        for rect, action in self._buttons():
            if action == "particle":
                pygame.draw.rect(
                    screen,
                    NodeSelector.NODE_TYPE_COLORS["particle_emitter"],
                    rect,
                    border_radius=SHAPE.radius_sm,
                )
                txt = self.font.render("Particle Config...", True, COLORS.text)
            else:
                pygame.draw.rect(screen, COLORS.accent, rect, border_radius=SHAPE.radius_sm)
                txt = self.font.render("Properties...", True, COLORS.text)
            screen.blit(txt, txt.get_rect(center=rect.center))

        if self._preset_dd is not None and self._preset_dd.open:
            self._preset_dd.draw_options(screen)
