"""
Layer selector widget for the tilemap editor.
Displays list of layers with ability to select, reorder, and manage them.
"""

from typing import TYPE_CHECKING

import pygame
from pygame import Rect, Surface

from utils.context_dispatch import ContextKind, PropertyContext
from widgets.input import InlineTextInput
from widgets.ui.button import Button
from widgets.ui.property_editor import PropertyEditor
from widgets.ui.theme import COLORS, FONTS, SHAPE

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

        self.dragging_layer_idx: int | None = None
        self.drag_start_y: int = 0
        self.drag_offset_y: int = 0
        self.hover_idx: int | None = None

        self.renaming_layer_idx: int | None = None
        self.rename_input = InlineTextInput("layer_rename", "")

        self._adjusting_opacity_idx: int | None = None

        btn_h = 25
        btn_w = 25
        btn_y = self.footer_rect.y + 5
        self.btn_add = Button(
            Rect(x + 5, btn_y, btn_w, btn_h),
            "+",
            on_click=self._add_layer,
        )
        self.btn_remove = Button(
            Rect(x + 35, btn_y, btn_w, btn_h),
            "-",
            on_click=self._remove_layer,
        )

        self.font_header = FONTS.get_bold_font(FONTS.size_md)
        self.font_layer = FONTS.get_small_font()

        d = self.editor.context_dispatch
        d.register_opener(ContextKind.LAYER, self._open_layer_properties)
        d.register_saver(ContextKind.LAYER, self._save_layer_properties)

    def resize(self, x: int, y: int, w: int, h: int):
        self.rect = Rect(x, y, w, h)
        self.header_rect = Rect(x, y, w, self.header_h)
        self.list_rect = Rect(
            x, y + self.header_h, w, h - self.header_h - self.footer_h
        )
        self.footer_rect = Rect(x, y + h - self.footer_h, w, self.footer_h)

        btn_y = self.footer_rect.y + 5
        self.btn_add.resize(x + 5, btn_y, 25, 25)
        self.btn_remove.resize(x + 35, btn_y, 25, 25)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events. Returns True if event was consumed."""
        mouse_pos = pygame.mouse.get_pos()

        # Rename takes priority over every other mouse target (footer
        # buttons included): confirming needs the edited row, anything else
        # cancels, and the click is always consumed so selection or button
        # actions can never fire mid-rename and shift indices out from
        # under _confirm_rename.
        if event.type == pygame.MOUSEBUTTONDOWN and self.renaming_layer_idx is not None:
            if (
                self.list_rect.collidepoint(mouse_pos)
                and self._get_layer_at_pos(mouse_pos) == self.renaming_layer_idx
            ):
                self._confirm_rename()
            else:
                self._cancel_rename()
            return True

        if self.btn_add.handle_event(event):
            return True
        if self.btn_remove.handle_event(event):
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
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

                        ysort_rect = self._get_ysort_icon_rect(layer_idx)
                        if ysort_rect and ysort_rect.collidepoint(mouse_pos):
                            layer = self.editor.tilemap.layer_manager.get_layer(
                                layer_idx
                            )
                            if layer:
                                layer.y_sort = not layer.y_sort
                                return True

                        opacity_rect = self._get_opacity_bar_rect(layer_idx)
                        if opacity_rect and opacity_rect.collidepoint(mouse_pos):
                            layer = self.editor.tilemap.layer_manager.get_layer(
                                layer_idx
                            )
                            if layer:
                                self._adjusting_opacity_idx = layer_idx
                                rel_x = mouse_pos[0] - opacity_rect.x
                                layer.opacity = max(
                                    0.0, min(1.0, rel_x / opacity_rect.width)
                                )
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

            elif event.button == 3:
                if self.list_rect.collidepoint(mouse_pos):
                    layer_idx = self._get_layer_at_pos(mouse_pos)
                    if layer_idx is not None:
                        layer = self.editor.tilemap.layer_manager.get_layer(layer_idx)
                        if layer:
                            self.editor.context_dispatch.open(
                                PropertyContext(ContextKind.LAYER, layer)
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
            if event.button == 1:
                self._adjusting_opacity_idx = None

            if event.button == 1 and self.dragging_layer_idx is not None:
                layer_idx = self._get_layer_at_pos(mouse_pos)
                if layer_idx is not None and layer_idx != self.dragging_layer_idx:
                    self.editor.tilemap.layer_manager.reorder_layer(
                        self.dragging_layer_idx, layer_idx
                    )

                self.dragging_layer_idx = None
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self._adjusting_opacity_idx is not None:
                layer = self.editor.tilemap.layer_manager.get_layer(
                    self._adjusting_opacity_idx
                )
                if layer:
                    opacity_rect = self._get_opacity_bar_rect(
                        self._adjusting_opacity_idx
                    )
                    if opacity_rect:
                        rel_x = max(
                            0, min(opacity_rect.width, mouse_pos[0] - opacity_rect.x)
                        )
                        layer.opacity = max(0.0, min(1.0, rel_x / opacity_rect.width))
                return True

            if self.list_rect.collidepoint(mouse_pos):
                if self.dragging_layer_idx is None:
                    self.hover_idx = self._get_layer_at_pos(mouse_pos)
            else:
                self.hover_idx = None

            if self.dragging_layer_idx is not None:
                return True

        elif event.type == pygame.MOUSEWHEEL:
            if self.list_rect.collidepoint(mouse_pos):
                self._scroll(-event.y * self.scroll_speed)
                return True

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F2:
                active_idx = self.editor.tilemap.layer_manager.active_layer_idx
                if active_idx >= 0:
                    self._start_rename(active_idx)
                    return True

            if self.renaming_layer_idx is not None:
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    self._confirm_rename()
                    return True
                if event.key == pygame.K_ESCAPE:
                    self._cancel_rename()
                    return True
                if self.rename_input.handle_event(event, self.font_layer):
                    return True
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

    def _get_layer_at_pos(self, pos) -> int | None:
        """Get layer index at the given mouse position."""
        if not self.list_rect.collidepoint(pos):
            return None

        rel_y = pos[1] - self.list_rect.y + self.scroll_offset
        idx = rel_y // self.item_h

        if 0 <= idx < self.editor.tilemap.layer_manager.get_layer_count():
            return idx

        return None

    def _get_opacity_bar_rect(self, layer_idx: int) -> Rect | None:
        """Get the clickable rect for the opacity bar of a layer."""
        item_y = self.list_rect.y + (layer_idx * self.item_h) - self.scroll_offset

        if item_y + self.item_h < self.list_rect.y or item_y > self.list_rect.bottom:
            return None

        bar_w = 46
        bar_h = 6
        bar_x = self.list_rect.x + self.list_rect.width - 80
        bar_y = item_y + self.item_h - bar_h - 3
        return Rect(bar_x, bar_y, bar_w, bar_h)

    def _get_ysort_icon_rect(self, layer_idx: int) -> Rect | None:
        """Get the clickable rect for the y-sort toggle of a layer."""
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

        ysort_x = item_rect.x + 5
        ysort_y = item_rect.y + 4
        return Rect(ysort_x, ysort_y, 12, 20)

    def _get_eye_icon_rect(self, layer_idx: int, mouse_pos) -> Rect | None:
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

    def _get_lock_icon_rect(self, layer_idx: int, mouse_pos) -> Rect | None:
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
            self.rename_input.text = layer.name
            self.rename_input.cursor_pos = len(layer.name)
            self.rename_input.is_focused = True
            self.rename_input.select_all()

    def _confirm_rename(self) -> None:
        """Confirm and apply the rename."""
        if self.renaming_layer_idx is None:
            return

        new_name = self.rename_input.text.strip()
        layers = self.editor.tilemap.layer_manager.layers
        if self.renaming_layer_idx >= len(layers):
            # list shrank underneath the edit; nothing safe to retarget
            self._cancel_rename()
            return
        layer = layers[self.renaming_layer_idx]
        if new_name and layer:
            layer.name = new_name
        self._cancel_rename()

    def _cancel_rename(self) -> None:
        """Cancel rename and revert to original name."""
        self.renaming_layer_idx = None
        self.rename_input.text = ""
        self.rename_input.cursor_pos = 0
        self.rename_input.is_focused = False
        self.rename_input.selection_start = None

    def _open_layer_properties(self, ctx: PropertyContext) -> None:
        layer = ctx.target
        self.editor.property_editor = PropertyEditor(
            self.editor,
            f"Layer Properties: {layer.name}",
            layer.properties,
            context=ctx,
        )

    def _save_layer_properties(self, ctx: PropertyContext, props: dict):
        layer = ctx.target
        layer.properties = props
        self.editor.suggestion_registry.refresh(self.editor)
        print(f"Saved properties for layer: {layer.name}")

    def draw(self, screen: Surface) -> None:
        """Draw the layer selector widget."""

        pygame.draw.rect(screen, COLORS.panel, self.rect)
        pygame.draw.rect(screen, COLORS.border, self.rect, 1)

        pygame.draw.rect(screen, COLORS.accent, self.header_rect)
        header_txt = self.font_header.render("LAYERS", True, COLORS.text)
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
                color = COLORS.accent_active
            elif i == active_idx:
                color = COLORS.selected
            elif i == self.hover_idx:
                color = COLORS.hover
            else:
                color = COLORS.panel_alt

            pygame.draw.rect(screen, color, item_rect)
            pygame.draw.rect(screen, COLORS.border_soft, item_rect, 1)

            mx, my = pygame.mouse.get_pos()
            eye_rect = self._get_eye_icon_rect(i, (mx, my))
            lock_rect = self._get_lock_icon_rect(i, (mx, my))
            ysort_rect = self._get_ysort_icon_rect(i)
            if eye_rect and eye_rect.collidepoint(mx, my):
                self.editor.tooltip.show("Toggle Visibility", (mx + 10, my + 10))
            elif lock_rect and lock_rect.collidepoint(mx, my):
                self.editor.tooltip.show("Toggle Lock", (mx + 10, my + 10))
            elif ysort_rect and ysort_rect.collidepoint(mx, my):
                label = "On" if layer.y_sort else "Off"
                self.editor.tooltip.show(f"Y-Sort: {label}", (mx + 10, my + 10))

            if i == self.renaming_layer_idx:
                pygame.draw.rect(
                    screen,
                    COLORS.selected,
                    Rect(item_rect.x + 22, item_rect.y + 4, 120, 20),
                    border_radius=SHAPE.radius_sm,
                )
                cursor = (
                    "|"
                    if pygame.time.get_ticks() // 500 % 2 == 0
                    else ""
                )
                name_txt = self.font_layer.render(
                    self.rename_input.text[: self.rename_input.cursor_pos]
                    + cursor
                    + self.rename_input.text[self.rename_input.cursor_pos :],
                    True,
                    COLORS.text_on_selected,
                )
            else:
                on_highlight = i == active_idx or i == self.dragging_layer_idx
                name_color = COLORS.text_on_selected if on_highlight else COLORS.text
                name_txt = self.font_layer.render(layer.name, True, name_color)
            screen.blit(name_txt, (item_rect.x + 22, item_rect.y + 5))

            opacity_bar = self._get_opacity_bar_rect(i)
            if opacity_bar:
                bg_rect = Rect(
                    opacity_bar.x, opacity_bar.y, opacity_bar.width, opacity_bar.height
                )
                pygame.draw.rect(screen, COLORS.border, bg_rect, border_radius=2)
                fill_w = int(opacity_bar.width * layer.opacity)
                if fill_w > 0:
                    fill_rect = Rect(
                        opacity_bar.x, opacity_bar.y, fill_w, opacity_bar.height
                    )
                    green = int(180 * layer.opacity) + 40
                    pygame.draw.rect(
                        screen, (40, green, 40), fill_rect, border_radius=2
                    )
                pct_col = (
                    COLORS.text_on_selected
                    if i == active_idx or i == self.dragging_layer_idx
                    else COLORS.text_dim
                )
                pct_txt = self.font_layer.render(
                    f"{int(layer.opacity * 100)}%", True, pct_col
                )
                screen.blit(pct_txt, (opacity_bar.x - 32, opacity_bar.y - 2))

            eye_x = item_rect.right - 25
            eye_y = item_rect.y + 7
            if layer.visible:
                pygame.draw.circle(screen, COLORS.success, (eye_x, eye_y), 4)
                pygame.draw.circle(screen, COLORS.success, (eye_x, eye_y), 4, 1)
                pygame.draw.circle(screen, COLORS.text_on_selected, (eye_x - 1, eye_y - 1), 1)
            else:
                pygame.draw.line(screen, COLORS.text_muted, (eye_x - 4, eye_y - 4), (eye_x + 4, eye_y + 4), 2)
                pygame.draw.line(screen, COLORS.text_muted, (eye_x + 4, eye_y - 4), (eye_x - 4, eye_y + 4), 2)

            lock_x = item_rect.right - 10
            lock_y = item_rect.y + 7
            if layer.locked:
                pygame.draw.rect(screen, COLORS.danger, Rect(lock_x - 4, lock_y - 4, 8, 8), border_radius=2)
                pygame.draw.circle(screen, COLORS.danger_hover, (lock_x, lock_y - 2), 1)
            else:
                pygame.draw.rect(screen, COLORS.text_muted, Rect(lock_x - 4, lock_y - 4, 8, 8), 1, border_radius=2)

            ysort_rect = self._get_ysort_icon_rect(i)
            if ysort_rect:
                ysort_color = COLORS.accent if layer.y_sort else COLORS.text_dim
                pygame.draw.rect(
                    screen, ysort_color, ysort_rect,
                    border_radius=SHAPE.radius_sm,
                )
                ysort_txt = self.font_layer.render("Y", True, COLORS.text)
                screen.blit(ysort_txt, (ysort_rect.x + 3, ysort_rect.y + 3))

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
            drag_surf.fill(COLORS.accent_active)
            drag_surf.set_alpha(200)
            screen.blit(drag_surf, preview_rect)

            name_txt = self.font_layer.render(
                dragging_layer.name, True, COLORS.text_on_accent
            )
            screen.blit(name_txt, (preview_rect.x + 22, preview_rect.y + 5))

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
        self.btn_add.draw(screen)
        self.btn_remove.draw(screen)

        count = self.editor.tilemap.layer_manager.get_layer_count()
        info_txt = self.font_layer.render(f"{count} layer(s)", True, COLORS.text_dim)
        screen.blit(info_txt, (self.btn_remove.rect.right + 10, self.footer_rect.y + 8))
        mx, my = pygame.mouse.get_pos()
        if self.btn_add.rect.collidepoint(mx, my):
            self.editor.tooltip.show("Add Layer", (mx + 10, my + 10))
        elif self.btn_remove.rect.collidepoint(mx, my):
            self.editor.tooltip.show("Remove Layer", (mx + 10, my + 10))
