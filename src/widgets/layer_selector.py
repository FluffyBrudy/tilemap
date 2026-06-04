"""
Layer selector widget for the tilemap editor.
Displays list of layers with ability to select, reorder, and manage them.
"""

import pygame
from pygame import Rect, Surface, Color
from typing import TYPE_CHECKING, Optional
from layers import Layer
from widgets.ui.property_editor import PropertyEditor
from widgets.ui.theme import COLORS, FONTS, SHAPE
from utils.font_manager import font_manager, FontWeight, FontStyle

if TYPE_CHECKING:
    from editor import Editor


class LayerSelector:
    """Widget for selecting and managing tile layers."""

    def __init__(self, editor: "Editor", x: int, y: int, w: int, h: int):
        self.editor = editor
        self.rect = Rect(x, y, w, h)

        self.header_h = 30
        self.item_h = 28
        self.footer_h = 35

        self.header_rect = Rect(x, y, w, self.header_h)
        self.list_rect = Rect(
            x, y + self.header_h, w, h - self.header_h - self.footer_h
        )
        self.footer_rect = Rect(x, y + h - self.footer_h, w, self.footer_h)

        self.scroll_offset = 0
        self.scroll_speed = self.item_h

        self.dragging_layer_idx: Optional[int] = None
        self.drag_start_y: int = 0
        self.drag_offset_y: int = 0
        self.hover_idx: Optional[int] = None

        self.renaming_layer_idx: Optional[int] = None
        self.rename_text: str = ""
        self.rename_original_name: str = ""

        btn_h = 25
        btn_w = 25
        btn_y = self.footer_rect.y + 5
        self.btn_add = Rect(x + 5, btn_y, btn_w, btn_h)
        self.btn_remove = Rect(x + 35, btn_y, btn_w, btn_h)

        self.font_header = font_manager.get_font(
            FONTS.name, FONTS.size_md, FontWeight.BOLD
        )
        self.font_layer = font_manager.get_font(
            FONTS.name, FONTS.size_sm, FontWeight.REGULAR
        )

        self.bg_color = COLORS.panel
        self.header_color = COLORS.accent
        self.item_color = COLORS.panel_alt
        self.item_hover_color = COLORS.hover
        self.item_active_color = COLORS.selected
        self.item_drag_color = COLORS.accent_active
        self.text_color = COLORS.text
        self.text_muted = COLORS.text_dim

    def resize(self, x: int, y: int, w: int, h: int):
        self.rect = Rect(x, y, w, h)
        self.header_rect = Rect(x, y, w, self.header_h)
        self.list_rect = Rect(
            x, y + self.header_h, w, h - self.header_h - self.footer_h
        )
        self.footer_rect = Rect(x, y + h - self.footer_h, w, self.footer_h)

        btn_y = self.footer_rect.y + 5
        self.btn_add = Rect(x + 5, btn_y, 25, 25)
        self.btn_remove = Rect(x + 35, btn_y, 25, 25)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events. Returns True if event was consumed."""
        mouse_pos = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.btn_add.collidepoint(mouse_pos):
                    self._add_layer()
                    return True

                if self.btn_remove.collidepoint(mouse_pos):
                    self._remove_layer()
                    return True

                if self.list_rect.collidepoint(mouse_pos):
                    layer_idx = self._get_layer_at_pos(mouse_pos)
                    if layer_idx is not None:
                        eye_rect = self._get_eye_icon_rect(layer_idx, mouse_pos)
                        if eye_rect and eye_rect.collidepoint(mouse_pos):
                            layer = self.editor.tilemap.layer_manager.get_layer(
                                layer_idx
                            )
                            if layer:
                                layer.visible = not layer.visible
                                return True

                        lock_rect = self._get_lock_icon_rect(layer_idx, mouse_pos)
                        if lock_rect and lock_rect.collidepoint(mouse_pos):
                            layer = self.editor.tilemap.layer_manager.get_layer(
                                layer_idx
                            )
                            if layer:
                                layer.locked = not layer.locked
                                return True

                        self.dragging_layer_idx = layer_idx
                        self.drag_start_y = mouse_pos[1]

                        self.drag_offset_y = mouse_pos[1] - (
                            self.list_rect.y
                            + (layer_idx * self.item_h)
                            - self.scroll_offset
                        )

                        self.editor.tilemap.layer_manager.set_active_layer(layer_idx)
                        return True

            elif event.button == 3:  # Right click
                if self.list_rect.collidepoint(mouse_pos):
                    layer_idx = self._get_layer_at_pos(mouse_pos)
                    if layer_idx is not None:
                        layer = self.editor.tilemap.layer_manager.get_layer(layer_idx)
                        if layer:
                            self.editor.property_editor = PropertyEditor(
                                self.editor,
                                f"Layer Properties: {layer.name}",
                                layer.properties,
                                on_save=lambda props: self._save_layer_properties(
                                    layer, props
                                ),
                                on_close=lambda: None,
                            )
                        return True

            elif event.button == 4:
                if self.list_rect.collidepoint(mouse_pos):
                    self._scroll(-self.scroll_speed)
                    return True

            elif event.button == 5:
                if self.list_rect.collidepoint(mouse_pos):
                    self._scroll(self.scroll_speed)
                    return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.dragging_layer_idx is not None:
                layer_idx = self._get_layer_at_pos(mouse_pos)
                if layer_idx is not None and layer_idx != self.dragging_layer_idx:
                    self.editor.tilemap.layer_manager.reorder_layer(
                        self.dragging_layer_idx, layer_idx
                    )

                self.dragging_layer_idx = None
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.list_rect.collidepoint(mouse_pos):
                if self.dragging_layer_idx is None:
                    self.hover_idx = self._get_layer_at_pos(mouse_pos)
            else:
                self.hover_idx = None

            if self.dragging_layer_idx is not None:
                return True

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F2:
                active_idx = self.editor.tilemap.layer_manager.active_layer_idx
                if active_idx >= 0:
                    self._start_rename(active_idx)
                    return True

            if self.renaming_layer_idx is not None:
                if event.key == pygame.K_RETURN:
                    self._confirm_rename()
                    return True
                elif event.key == pygame.K_ESCAPE:
                    self._cancel_rename()
                    return True
                elif event.key == pygame.K_BACKSPACE:
                    self.rename_text = self.rename_text[:-1]
                    return True
                else:
                    if event.unicode.isprintable():
                        self.rename_text += event.unicode
                    return True

            if event.key == pygame.K_UP:
                if self.list_rect.collidepoint(pygame.mouse.get_pos()):
                    self._scroll(-self.scroll_speed)
                    return True
            elif event.key == pygame.K_DOWN:
                if self.list_rect.collidepoint(pygame.mouse.get_pos()):
                    self._scroll(self.scroll_speed)
                    return True

        return False

    def _get_layer_at_pos(self, pos) -> Optional[int]:
        """Get layer index at the given mouse position."""
        if not self.list_rect.collidepoint(pos):
            return None

        rel_y = pos[1] - self.list_rect.y + self.scroll_offset
        idx = rel_y // self.item_h

        if 0 <= idx < self.editor.tilemap.layer_manager.get_layer_count():
            return idx

        return None

    def _get_eye_icon_rect(self, layer_idx: int, mouse_pos) -> Optional[Rect]:
        """Get the clickable rect for the eye icon of a layer."""
        if layer_idx is None:
            return None

        item_y = self.list_rect.y + (layer_idx * self.item_h) - self.scroll_offset

        if item_y + self.item_h < self.list_rect.y or item_y > self.list_rect.bottom:
            return None

        item_rect = Rect(
            self.list_rect.x,
            item_y,
            self.list_rect.width,
            self.item_h,
        )

        eye_x = item_rect.right - 25
        eye_y = item_rect.y + 7
        return Rect(eye_x - 5, eye_y - 5, 10, 10)

    def _get_lock_icon_rect(self, layer_idx: int, mouse_pos) -> Optional[Rect]:
        """Get the clickable rect for the lock icon of a layer."""
        if layer_idx is None:
            return None

        item_y = self.list_rect.y + (layer_idx * self.item_h) - self.scroll_offset

        if item_y + self.item_h < self.list_rect.y or item_y > self.list_rect.bottom:
            return None

        item_rect = Rect(
            self.list_rect.x,
            item_y,
            self.list_rect.width,
            self.item_h,
        )

        lock_x = item_rect.right - 10
        lock_y = item_rect.y + 7
        return Rect(lock_x - 5, lock_y - 5, 10, 10)

    def _scroll(self, delta: int) -> None:
        """Scroll the layer list. Positive delta scrolls down."""
        layer_count = self.editor.tilemap.layer_manager.get_layer_count()
        max_scroll = max(0, (layer_count * self.item_h) - self.list_rect.height)

        self.scroll_offset += delta
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

    def _add_layer(self) -> None:
        """Add a new layer - show dialog to select type."""
        self.editor.layer_type_dialog.show(
            on_confirm=self._on_layer_type_selected,
            on_cancel=lambda: None,
        )

    def _on_layer_type_selected(self, layer_type: str) -> None:
        """Callback when user selects layer type from dialog."""
        count = self.editor.tilemap.layer_manager.get_layer_count()
        name = f"Layer {count + 1}"
        self.editor.tilemap.layer_manager.create_layer(name, layer_type=layer_type)

    def _remove_layer(self) -> None:
        """Remove the currently active layer."""
        active_idx = self.editor.tilemap.layer_manager.active_layer_idx
        self.editor.tilemap.layer_manager.delete_layer(active_idx)

    def _start_rename(self, layer_idx: int) -> None:
        """Start renaming a layer."""
        layer = self.editor.tilemap.layer_manager.get_layer(layer_idx)
        if layer:
            self.renaming_layer_idx = layer_idx
            self.rename_text = layer.name
            self.rename_original_name = layer.name

    def _confirm_rename(self) -> None:
        """Confirm and apply the rename."""
        if self.renaming_layer_idx is None:
            return

        import string

        valid_chars = set(string.ascii_letters + string.digits + " ")

        if not self.rename_text:
            self._cancel_rename()
            return

        if all(c in valid_chars for c in self.rename_text):
            layer = self.editor.tilemap.layer_manager.get_layer(self.renaming_layer_idx)
            if layer:
                layer.name = self.rename_text
        else:
            self._cancel_rename()
            return

        self.renaming_layer_idx = None
        self.rename_text = ""
        self.rename_original_name = ""

    def _cancel_rename(self) -> None:
        """Cancel rename and revert to original name."""
        self.renaming_layer_idx = None
        self.rename_text = ""
        self.rename_original_name = ""

    def _save_layer_properties(self, layer: Layer, props: dict):
        layer.properties = props
        print(f"Saved properties for layer: {layer.name}")

    def draw(self, screen: Surface) -> None:
        """Draw the layer selector widget."""

        pygame.draw.rect(screen, self.bg_color, self.rect)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)

        pygame.draw.rect(screen, self.header_color, self.header_rect)
        header_txt = self.font_header.render("LAYERS", True, Color("white"))
        screen.blit(header_txt, (self.header_rect.x + 5, self.header_rect.y + 8))

        self._draw_layer_list(screen)

        self._draw_footer(screen)

    def _draw_layer_list(self, screen: Surface) -> None:
        """Draw the list of layers with scrolling support."""
        layer_manager = self.editor.tilemap.layer_manager
        active_idx = layer_manager.active_layer_idx

        pygame.draw.rect(screen, COLORS.panel_alt, self.list_rect)

        clip = screen.get_clip()
        screen.set_clip(self.list_rect)

        for i, layer in enumerate(layer_manager.layers):
            item_y = self.list_rect.y + (i * self.item_h) - self.scroll_offset

            if (
                item_y + self.item_h < self.list_rect.y
                or item_y > self.list_rect.bottom
            ):
                continue

            item_rect = Rect(
                self.list_rect.x,
                item_y,
                self.list_rect.width,
                self.item_h,
            )

            if i == self.dragging_layer_idx:
                color = self.item_drag_color
            elif i == active_idx:
                color = self.item_active_color
            elif i == self.hover_idx:
                color = self.item_hover_color
            else:
                color = self.item_color

            pygame.draw.rect(screen, color, item_rect)
            pygame.draw.rect(screen, COLORS.border_soft, item_rect, 1)

            mx, my = pygame.mouse.get_pos()
            eye_rect = self._get_eye_icon_rect(i, (mx, my))
            lock_rect = self._get_lock_icon_rect(i, (mx, my))
            if eye_rect and eye_rect.collidepoint(mx, my):
                self.editor.tooltip.show("Toggle Visibility", (mx + 10, my + 10))
            elif lock_rect and lock_rect.collidepoint(mx, my):
                self.editor.tooltip.show("Toggle Lock", (mx + 10, my + 10))

            if i == self.renaming_layer_idx:
                pygame.draw.rect(
                    screen,
                    COLORS.selected,
                    Rect(item_rect.x + 4, item_rect.y + 4, 120, 20),
                    border_radius=SHAPE.radius_sm,
                )
                name_txt = self.font_layer.render(
                    self.rename_text + "|", True, self.text_color
                )
            else:
                name_txt = self.font_layer.render(layer.name, True, self.text_color)
            screen.blit(name_txt, (item_rect.x + 5, item_rect.y + 5))

            eye_x = item_rect.right - 25
            eye_y = item_rect.y + 7
            if layer.visible:
                pygame.draw.circle(screen, (100, 200, 100), (eye_x, eye_y), 4)
                pygame.draw.circle(screen, (60, 150, 60), (eye_x, eye_y), 4, 1)
                pygame.draw.circle(screen, (200, 255, 100), (eye_x - 1, eye_y - 1), 1)
            else:
                pygame.draw.line(
                    screen,
                    (100, 100, 100),
                    (eye_x - 4, eye_y - 4),
                    (eye_x + 4, eye_y + 4),
                    2,
                )
                pygame.draw.line(
                    screen,
                    (100, 100, 100),
                    (eye_x + 4, eye_y - 4),
                    (eye_x - 4, eye_y + 4),
                    2,
                )

            lock_x = item_rect.right - 10
            lock_y = item_rect.y + 7
            if layer.locked:
                pygame.draw.rect(
                    screen, (200, 100, 100), Rect(lock_x - 4, lock_y - 4, 8, 8)
                )
                pygame.draw.circle(screen, (150, 50, 50), (lock_x, lock_y - 2), 1)
            else:
                pygame.draw.rect(
                    screen, COLORS.text_muted, Rect(lock_x - 4, lock_y - 4, 8, 8), 1
                )

        if self.dragging_layer_idx is not None:
            mouse_y = pygame.mouse.get_pos()[1]
            dragging_layer = layer_manager.layers[self.dragging_layer_idx]

            preview_rect = Rect(
                self.list_rect.x + 2,
                mouse_y - self.drag_offset_y,
                self.list_rect.width - 4,
                self.item_h - 2,
            )

            drag_surf = pygame.Surface((preview_rect.width, preview_rect.height))
            drag_surf.fill(self.item_drag_color)
            drag_surf.set_alpha(200)
            screen.blit(drag_surf, preview_rect)

            name_txt = self.font_layer.render(
                dragging_layer.name, True, self.text_color
            )
            screen.blit(name_txt, (preview_rect.x + 5, preview_rect.y + 5))

            pygame.draw.rect(screen, (150, 150, 255), preview_rect, 2)

        screen.set_clip(clip)
        total_h = len(layer_manager.layers) * self.item_h
        if total_h > self.list_rect.height:
            scroll_pct = self.scroll_offset / max(1, (total_h - self.list_rect.height))
            bar_h = max(
                18, int(self.list_rect.height * (self.list_rect.height / total_h))
            )
            bar_y = self.list_rect.y + scroll_pct * (self.list_rect.height - bar_h)
            bar_rect = Rect(self.list_rect.right - 5, bar_y, 3, bar_h)
            pygame.draw.rect(screen, COLORS.border_soft, bar_rect, border_radius=2)

    def _draw_footer(self, screen: Surface) -> None:
        """Draw the footer with buttons."""
        pygame.draw.rect(screen, COLORS.header, self.footer_rect)
        pygame.draw.line(
            screen,
            COLORS.border_soft,
            (self.footer_rect.x, self.footer_rect.y),
            (self.footer_rect.right, self.footer_rect.y),
            1,
        )
        pygame.draw.rect(
            screen, COLORS.accent, self.btn_add, border_radius=SHAPE.radius_sm
        )
        pygame.draw.rect(screen, (70, 130, 180), self.btn_add)
        add_txt = self.font_layer.render("+", True, Color("white"))
        screen.blit(add_txt, (self.btn_add.x + 8, self.btn_add.y + 5))
        pygame.draw.rect(
            screen, COLORS.danger, self.btn_remove, border_radius=SHAPE.radius_sm
        )
        pygame.draw.rect(screen, (180, 100, 100), self.btn_remove)
        rem_txt = self.font_layer.render("-", True, Color("white"))
        screen.blit(rem_txt, (self.btn_remove.x + 8, self.btn_remove.y + 5))

        count = self.editor.tilemap.layer_manager.get_layer_count()
        info_txt = self.font_layer.render(f"{count} layer(s)", True, self.text_muted)
        screen.blit(info_txt, (self.btn_remove.right + 10, self.footer_rect.y + 8))
        mx, my = pygame.mouse.get_pos()
        if self.btn_add.collidepoint(mx, my):
            self.editor.tooltip.show("Add Layer", (mx + 10, my + 10))
        elif self.btn_remove.collidepoint(mx, my):
            self.editor.tooltip.show("Remove Layer", (mx + 10, my + 10))
