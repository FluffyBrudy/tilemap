"""
Layer selector widget for the tilemap editor.
Displays list of layers with ability to select, reorder, and manage them.
"""

import pygame
from pygame import Rect, Surface, Color
from typing import TYPE_CHECKING, Optional, List
from layers import Layer

if TYPE_CHECKING:
    from editor import Editor


class LayerSelector:
    """Widget for selecting and managing tile layers."""

    def __init__(self, editor: "Editor", x: int, y: int, w: int, h: int):
        self.editor = editor
        self.rect = Rect(x, y, w, h)

        # Layout
        self.header_h = 30
        self.item_h = 28
        self.footer_h = 35

        self.header_rect = Rect(x, y, w, self.header_h)
        self.list_rect = Rect(
            x, y + self.header_h, w, h - self.header_h - self.footer_h
        )
        self.footer_rect = Rect(x, y + h - self.footer_h, w, self.footer_h)

        # Scrolling
        self.scroll_offset = 0  # Vertical scroll offset in pixels
        self.scroll_speed = self.item_h  # Scroll by one item at a time

        # Interaction
        self.dragging_layer_idx: Optional[int] = None
        self.drag_start_y: int = 0
        self.drag_offset_y: int = 0  # Offset from layer top when dragging
        self.hover_idx: Optional[int] = None

        # Rename mode
        self.renaming_layer_idx: Optional[int] = None
        self.rename_text: str = ""
        self.rename_original_name: str = ""

        # Buttons
        btn_h = 25
        btn_w = 25
        btn_y = self.footer_rect.y + 5
        self.btn_add = Rect(x + 5, btn_y, btn_w, btn_h)
        self.btn_remove = Rect(x + 35, btn_y, btn_w, btn_h)

        # Rendering
        self.font_header = pygame.font.SysFont("Arial", 12, bold=True)
        self.font_layer = pygame.font.SysFont("Arial", 11)

        self.bg_color = (40, 40, 40)
        self.header_color = (44, 132, 250)
        self.item_color = (60, 60, 60)
        self.item_hover_color = (80, 80, 80)
        self.item_active_color = (65, 70, 80)
        self.item_drag_color = (100, 120, 200)  # Color when dragging
        self.text_color = (220, 220, 220)
        self.text_muted = (140, 140, 140)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle pygame events. Returns True if event was consumed."""
        mouse_pos = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                # Add layer button
                if self.btn_add.collidepoint(mouse_pos):
                    self._add_layer()
                    return True

                # Remove layer button
                if self.btn_remove.collidepoint(mouse_pos):
                    self._remove_layer()
                    return True

                # Layer item click
                if self.list_rect.collidepoint(mouse_pos):
                    layer_idx = self._get_layer_at_pos(mouse_pos)
                    if layer_idx is not None:
                        self.dragging_layer_idx = layer_idx
                        self.drag_start_y = mouse_pos[1]
                        # Store offset within the item
                        self.drag_offset_y = mouse_pos[1] - (
                            self.list_rect.y
                            + (layer_idx * self.item_h)
                            - self.scroll_offset
                        )

                        # Select the layer
                        self.editor.tilemap.layer_manager.set_active_layer(layer_idx)
                        return True

            elif event.button == 4:  # Scroll wheel up
                if self.list_rect.collidepoint(mouse_pos):
                    self._scroll(-self.scroll_speed)
                    return True

            elif event.button == 5:  # Scroll wheel down
                if self.list_rect.collidepoint(mouse_pos):
                    self._scroll(self.scroll_speed)
                    return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.dragging_layer_idx is not None:
                # Drop layer
                layer_idx = self._get_layer_at_pos(mouse_pos)
                if layer_idx is not None and layer_idx != self.dragging_layer_idx:
                    self.editor.tilemap.layer_manager.reorder_layer(
                        self.dragging_layer_idx, layer_idx
                    )

                self.dragging_layer_idx = None
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.list_rect.collidepoint(mouse_pos):
                # Don't update hover when dragging
                if self.dragging_layer_idx is None:
                    self.hover_idx = self._get_layer_at_pos(mouse_pos)
            else:
                self.hover_idx = None

            if self.dragging_layer_idx is not None:
                # Visual feedback for dragging is handled in draw
                return True

        elif event.type == pygame.KEYDOWN:
            # F2 to rename focused layer
            if event.key == pygame.K_F2:
                active_idx = self.editor.tilemap.layer_manager.active_layer_idx
                if active_idx >= 0:
                    self._start_rename(active_idx)
                    return True

            # Handle rename mode input
            if self.renaming_layer_idx is not None:
                if event.key == pygame.K_RETURN:
                    # Confirm rename
                    self._confirm_rename()
                    return True
                elif event.key == pygame.K_ESCAPE:
                    # Cancel rename
                    self._cancel_rename()
                    return True
                elif event.key == pygame.K_BACKSPACE:
                    self.rename_text = self.rename_text[:-1]
                    return True
                else:
                    # Add character if printable
                    if event.unicode.isprintable():
                        self.rename_text += event.unicode
                    return True

            # Arrow keys for scrolling
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

        # Validate: name must be alphanumeric + spaces, or empty reverts to original
        import string

        valid_chars = set(string.ascii_letters + string.digits + " ")

        if not self.rename_text:
            # Empty name reverts to original
            self._cancel_rename()
            return

        if all(c in valid_chars for c in self.rename_text):
            # Valid name - apply it
            layer = self.editor.tilemap.layer_manager.get_layer(self.renaming_layer_idx)
            if layer:
                layer.name = self.rename_text
        else:
            # Invalid characters - revert
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

    def draw(self, screen: Surface) -> None:
        """Draw the layer selector widget."""
        # Background
        pygame.draw.rect(screen, self.bg_color, self.rect)
        pygame.draw.rect(screen, (100, 100, 100), self.rect, 1)

        # Header
        pygame.draw.rect(screen, self.header_color, self.header_rect)
        header_txt = self.font_header.render("LAYERS", True, Color("white"))
        screen.blit(header_txt, (self.header_rect.x + 5, self.header_rect.y + 8))

        # Layer list
        self._draw_layer_list(screen)

        # Footer with buttons
        self._draw_footer(screen)

    def _draw_layer_list(self, screen: Surface) -> None:
        """Draw the list of layers with scrolling support."""
        layer_manager = self.editor.tilemap.layer_manager
        active_idx = layer_manager.active_layer_idx

        pygame.draw.rect(screen, (30, 30, 30), self.list_rect)

        # Clip to list area
        clip = screen.get_clip()
        screen.set_clip(self.list_rect)

        for i, layer in enumerate(layer_manager.layers):
            # Calculate y position considering scroll
            item_y = self.list_rect.y + (i * self.item_h) - self.scroll_offset

            # Skip if out of view
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

            # Determine color
            if i == self.dragging_layer_idx:
                # Highlight while dragging
                color = self.item_drag_color
            elif i == active_idx:
                color = self.item_active_color
            elif i == self.hover_idx:
                color = self.item_hover_color
            else:
                color = self.item_color

            pygame.draw.rect(screen, color, item_rect)
            pygame.draw.rect(screen, (50, 50, 50), item_rect, 1)

            # Draw layer name
            if i == self.renaming_layer_idx:
                # Show editable text field for rename mode
                pygame.draw.rect(
                    screen,
                    (80, 100, 150),
                    Rect(item_rect.x + 4, item_rect.y + 4, 100, 20),
                )
                name_txt = self.font_layer.render(
                    self.rename_text + "|", True, self.text_color
                )
                screen.blit(name_txt, (item_rect.x + 5, item_rect.y + 5))
            else:
                name_txt = self.font_layer.render(layer.name, True, self.text_color)
                screen.blit(name_txt, (item_rect.x + 5, item_rect.y + 5))

            # Draw visibility icon (eye)
            eye_x = item_rect.right - 25
            eye_y = item_rect.y + 7
            if layer.visible:
                pygame.draw.circle(screen, (100, 200, 100), (eye_x, eye_y), 3)
            else:
                pygame.draw.circle(screen, (100, 100, 100), (eye_x, eye_y), 3)

            # Draw lock icon
            lock_x = item_rect.right - 10
            lock_y = item_rect.y + 7
            if layer.locked:
                pygame.draw.rect(
                    screen, (200, 100, 100), Rect(lock_x - 3, lock_y - 3, 6, 6)
                )
            else:
                pygame.draw.rect(
                    screen, (100, 100, 100), Rect(lock_x - 3, lock_y - 3, 6, 6), 1
                )

        # Draw dragging layer as floating preview
        if self.dragging_layer_idx is not None:
            mouse_y = pygame.mouse.get_pos()[1]
            dragging_layer = layer_manager.layers[self.dragging_layer_idx]

            # Draw floating preview at mouse position
            preview_rect = Rect(
                self.list_rect.x + 2,
                mouse_y - self.drag_offset_y,
                self.list_rect.width - 4,
                self.item_h - 2,
            )

            # Draw with semi-transparent effect (dragging)
            drag_surf = pygame.Surface((preview_rect.width, preview_rect.height))
            drag_surf.fill(self.item_drag_color)
            drag_surf.set_alpha(200)
            screen.blit(drag_surf, preview_rect)

            # Draw dragging layer name
            name_txt = self.font_layer.render(
                dragging_layer.name, True, self.text_color
            )
            screen.blit(name_txt, (preview_rect.x + 5, preview_rect.y + 5))

            # Border around floating layer
            pygame.draw.rect(screen, (150, 150, 255), preview_rect, 2)

        screen.set_clip(clip)

    def _draw_footer(self, screen: Surface) -> None:
        """Draw the footer with buttons."""
        pygame.draw.rect(screen, (50, 50, 50), self.footer_rect)
        pygame.draw.line(
            screen,
            (70, 70, 70),
            (self.footer_rect.x, self.footer_rect.y),
            (self.footer_rect.right, self.footer_rect.y),
            1,
        )

        # Add button
        pygame.draw.rect(screen, (70, 130, 180), self.btn_add)
        add_txt = self.font_layer.render("+", True, Color("white"))
        screen.blit(add_txt, (self.btn_add.x + 8, self.btn_add.y + 5))

        # Remove button
        pygame.draw.rect(screen, (180, 100, 100), self.btn_remove)
        rem_txt = self.font_layer.render("-", True, Color("white"))
        screen.blit(rem_txt, (self.btn_remove.x + 8, self.btn_remove.y + 5))

        # Info text
        count = self.editor.tilemap.layer_manager.get_layer_count()
        info_txt = self.font_layer.render(f"{count} layer(s)", True, self.text_muted)
        screen.blit(info_txt, (self.btn_remove.right + 10, self.footer_rect.y + 8))
