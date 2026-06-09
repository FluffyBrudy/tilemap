"""
Simple dialog for selecting tileset type (tile vs object) and configuring animation.
"""

import pygame
from pygame import Rect, Surface
from typing import Callable, Optional


class TilesetTypeDialog:
    """Dialog to select whether a tileset is tile-based or object-based."""

    def __init__(self, editor_rect: Rect):
        self.editor_rect = editor_rect
        self.rect = Rect(0, 0, 400, 420)
        self.rect.center = editor_rect.center

        self.active = False
        self.selected_type: Optional[str] = None
        self.on_confirm: Optional[Callable[[str], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        self.bg_color = (40, 40, 40)
        self.border_color = (100, 100, 100)
        self.text_color = (255, 255, 255)
        self.field_color = (55, 55, 55)
        self.field_border = (80, 80, 80)
        self.radio_color = (100, 150, 255)
        self.button_color = (60, 100, 180)
        self.button_hover_color = (80, 120, 200)

        self.radio_tile_rect = Rect(0, 0, 20, 20)
        self.radio_object_rect = Rect(0, 0, 20, 20)
        self.radio_tile_label_rect = Rect(0, 0, 0, 0)
        self.radio_object_label_rect = Rect(0, 0, 0, 0)
        self.radio_tile_row_rect = Rect(0, 0, 0, 0)
        self.radio_object_row_rect = Rect(0, 0, 0, 0)

        self.btn_ok = Rect(0, 0, 80, 30)
        self.btn_cancel = Rect(0, 0, 80, 30)

        self.font_title = pygame.font.SysFont("Arial", 18, bold=True)
        self.font_text = pygame.font.SysFont("Arial", 14)
        self.font_field = pygame.font.SysFont("Arial", 13)

        self.btn_ok_hover = False
        self.btn_cancel_hover = False

        # Animation state
        self.animated = False
        self.anim_frame_count = 4
        self.anim_frame_duration_ms = 200
        self.anim_loop = True
        self.anim_mode_index = 0  # 0=default, 1=random_start_times
        self.anim_modes = ["default", "random_start_times"]
        self.anim_mode_labels = ["Sync", "Random"]

        # Inline editing state
        self._editing_field: Optional[str] = None
        self._edit_buffer = ""

        # Animation field rects (set by _layout)
        self.anim_check_rect = Rect(0, 0, 16, 16)
        self.anim_fields_rects: dict = {}
        self.anim_loop_check_rect = Rect(0, 0, 16, 16)
        self.anim_mode_rect = Rect(0, 0, 0, 0)

        self._layout()

    def _layout(self):
        """Position child controls from the current dialog rect."""
        self.rect.center = self.editor_rect.center

        h = 260
        if self.animated or self._editing_field is not None:
            h = 420
        self.rect.h = h

        radio_x = self.rect.x + 42
        row_w = self.rect.w - 84
        row_h = 38
        first_y = self.rect.y + 58
        gap = 12

        self.radio_tile_row_rect = Rect(radio_x - 10, first_y - 9, row_w, row_h)
        self.radio_object_row_rect = Rect(
            radio_x - 10, first_y + row_h + gap - 9, row_w, row_h
        )

        self.radio_tile_rect = Rect(radio_x, first_y, 20, 20)
        self.radio_object_rect = Rect(radio_x, first_y + row_h + gap, 20, 20)

        label_x = radio_x + 34
        self.radio_tile_label_rect = Rect(label_x, first_y - 4, row_w - 44, 28)
        self.radio_object_label_rect = Rect(
            label_x, first_y + row_h + gap - 4, row_w - 44, 28
        )

        # Animated checkbox
        anim_y = first_y + (row_h + gap) * 2 + 16
        self.anim_check_rect = Rect(radio_x, anim_y, 16, 16)

        # Animation fields (collapsible)
        field_y = anim_y + 30
        field_h = 22
        field_gap = 4
        field_label_w = 100
        field_value_w = 80
        field_x = self.rect.x + 42

        self.anim_fields_rects = {}
        anim_fields = [
            ("frame_count", "Frame Count", str(self.anim_frame_count)),
            ("frame_duration_ms", "Duration (ms)", str(self.anim_frame_duration_ms)),
        ]
        for key, label, _ in anim_fields:
            label_rect = Rect(field_x, field_y, field_label_w, field_h)
            value_rect = Rect(field_x + field_label_w + 8, field_y, field_value_w, field_h)
            self.anim_fields_rects[key] = {
                "label": label_rect,
                "value": value_rect,
                "label_text": label,
            }
            field_y += field_h + field_gap

        # Loop checkbox
        self.anim_loop_check_rect = Rect(field_x, field_y, 16, 16)
        field_y += 26

        # Animation mode
        mode_label_rect = Rect(field_x, field_y, field_label_w, field_h)
        mode_value_rect = Rect(field_x + field_label_w + 8, field_y, field_value_w, field_h)
        self.anim_fields_rects["mode"] = {
            "label": mode_label_rect,
            "value": mode_value_rect,
            "label_text": "Animation Mode",
        }

        # Stride hint (read-only, auto-computed)
        self._stride_hint_rect = Rect(field_x, field_y + 36, field_label_w + field_value_w + 8, field_h)

        btn_y = self.rect.y + h - 44
        self.btn_ok = Rect(self.rect.centerx - 94, btn_y, 80, 30)
        self.btn_cancel = Rect(self.rect.centerx + 14, btn_y, 80, 30)

    def get_animation_config(self) -> Optional[dict]:
        if not self.animated:
            return None
        return {
            "frame_count": self.anim_frame_count,
            "frame_duration_ms": self.anim_frame_duration_ms,
            "loop": self.anim_loop,
            "animation_mode": self.anim_modes[self.anim_mode_index],
        }

    def _get_display_value(self, key: str) -> str:
        if self._editing_field == key:
            return self._edit_buffer
        map = {
            "frame_count": str(self.anim_frame_count),
            "frame_duration_ms": str(self.anim_frame_duration_ms),
            "mode": self.anim_mode_labels[self.anim_mode_index],
        }
        return map.get(key, "")

    def _commit_edit(self):
        if self._editing_field is None:
            return
        try:
            if self._editing_field == "frame_count":
                self.anim_frame_count = max(1, int(self._edit_buffer))
                self._update_computed_stride()
            elif self._editing_field == "frame_duration_ms":
                self.anim_frame_duration_ms = max(1, int(self._edit_buffer))
        except ValueError:
            pass
        self._editing_field = None
        self._edit_buffer = ""

    def set_sheet_dimensions(self, sheet_cols: int, sheet_rows: int):
        self._sheet_cols = sheet_cols
        self._sheet_rows = sheet_rows
        if self.anim_frame_count > 0:
            self._update_computed_stride()

    def _update_computed_stride(self):
        fc = self.anim_frame_count
        if fc < 1:
            return
        if hasattr(self, '_sheet_cols') and self._sheet_cols % fc == 0:
            self._computed_stride = self._sheet_cols // fc
        elif hasattr(self, '_sheet_rows') and self._sheet_rows % fc == 0:
            self._computed_stride = (self._sheet_rows // fc) * getattr(self, '_sheet_cols', 1)
        else:
            self._computed_stride = 1

    def show(self, on_confirm: Callable[[str], None], on_cancel: Callable[[], None]):
        """Show the dialog."""
        if self.active:
            self.hide()
        self.active = True
        self.selected_type = "tile"
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.btn_ok_hover = False
        self.btn_cancel_hover = False
        self.animated = False
        self.anim_frame_count = 4
        self.anim_frame_duration_ms = 200
        self.anim_loop = True
        self.anim_mode_index = 0
        self._computed_stride = 1
        self._editing_field = None
        self._edit_buffer = ""

    def hide(self):
        """Hide the dialog."""
        self.active = False
        self._editing_field = None
        self._edit_buffer = ""

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle events. Returns True if event was consumed."""
        if not self.active:
            return False

        self._layout()
        mouse_pos = pygame.mouse.get_pos()

        if event.type == pygame.KEYDOWN:
            if self._editing_field is not None:
                if event.key == pygame.K_RETURN:
                    self._commit_edit()
                    return True
                elif event.key == pygame.K_ESCAPE:
                    self._editing_field = None
                    self._edit_buffer = ""
                    return True
                elif event.key == pygame.K_BACKSPACE:
                    self._edit_buffer = self._edit_buffer[:-1]
                    return True
                else:
                    ch = event.unicode
                    if ch.isdigit() or ch == "-":
                        self._edit_buffer += ch
                    return True
            else:
                if event.key == pygame.K_ESCAPE:
                    if self.on_cancel:
                        self.on_cancel()
                    self.hide()
                    return True
                elif event.key == pygame.K_RETURN:
                    if self.on_confirm and self.selected_type:
                        self.on_confirm(self.selected_type)
                    self.hide()
                    return True

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.radio_tile_row_rect.collidepoint(mouse_pos):
                self.selected_type = "tile"
                return True
            if self.radio_object_row_rect.collidepoint(mouse_pos):
                self.selected_type = "object"
                return True

            # Animated checkbox toggle
            if self.anim_check_rect.collidepoint(mouse_pos):
                self.animated = not self.animated
                self._editing_field = None
                self._edit_buffer = ""
                return True

            if self.animated:
                # Animation field clicks
                if self.anim_loop_check_rect.collidepoint(mouse_pos):
                    self.anim_loop = not self.anim_loop
                    return True

                for key, rects in self.anim_fields_rects.items():
                    if key == "mode":
                        if rects["value"].collidepoint(mouse_pos):
                            self.anim_mode_index = (self.anim_mode_index + 1) % len(self.anim_modes)
                            return True
                    else:
                        if rects["value"].collidepoint(mouse_pos):
                            self._commit_edit()
                            self._editing_field = key
                            self._edit_buffer = self._get_display_value(key)
                            return True

            if self.btn_ok.collidepoint(mouse_pos):
                self._commit_edit()
                if self.on_confirm and self.selected_type:
                    self.on_confirm(self.selected_type)
                self.hide()
                return True
            if self.btn_cancel.collidepoint(mouse_pos):
                self._editing_field = None
                self._edit_buffer = ""
                if self.on_cancel:
                    self.on_cancel()
                self.hide()
                return True

        elif event.type == pygame.MOUSEMOTION:
            self.btn_ok_hover = self.btn_ok.collidepoint(mouse_pos)
            self.btn_cancel_hover = self.btn_cancel.collidepoint(mouse_pos)

        return False

    def draw(self, surface: Surface):
        """Draw the dialog on the given surface."""
        if not self.active:
            return

        self._layout()
        pygame.draw.rect(surface, self.bg_color, self.rect)
        pygame.draw.rect(surface, self.border_color, self.rect, 2)

        title = self.font_title.render("Tileset Type", True, self.text_color)
        title_rect = title.get_rect(topleft=(self.rect.x + 20, self.rect.y + 15))
        surface.blit(title, title_rect)

        self._draw_radio(
            surface,
            self.radio_tile_rect,
            self.radio_tile_row_rect,
            self.selected_type == "tile",
            "Tile Tileset (grid-based)",
            self.radio_tile_label_rect,
        )

        self._draw_radio(
            surface,
            self.radio_object_rect,
            self.radio_object_row_rect,
            self.selected_type == "object",
            "Object Tileset (free-positioned)",
            self.radio_object_label_rect,
        )

        self._draw_checkbox(
            surface,
            self.anim_check_rect,
            self.animated,
            "Animated Tileset",
            self.rect.x + 62,
        )

        if self.animated:
            self._draw_animation_fields(surface)

        ok_color = self.button_hover_color if self.btn_ok_hover else self.button_color
        cancel_color = (
            self.button_hover_color if self.btn_cancel_hover else self.button_color
        )

        pygame.draw.rect(surface, ok_color, self.btn_ok)
        pygame.draw.rect(surface, cancel_color, self.btn_cancel)

        ok_text = self.font_text.render("OK", True, self.text_color)
        cancel_text = self.font_text.render("Cancel", True, self.text_color)

        ok_text_rect = ok_text.get_rect(center=self.btn_ok.center)
        cancel_text_rect = cancel_text.get_rect(center=self.btn_cancel.center)

        surface.blit(ok_text, ok_text_rect)
        surface.blit(cancel_text, cancel_text_rect)

    def _draw_animation_fields(self, surface: Surface):
        """Draw the animation configuration fields."""
        numeric_keys = ["frame_count", "frame_duration_ms"]
        for key in numeric_keys:
            rects = self.anim_fields_rects.get(key)
            if rects is None:
                continue
            label_surf = self.font_text.render(rects["label_text"], True, self.text_color)
            surface.blit(label_surf, rects["label"])

            value_str = self._get_display_value(key)
            value_color = self.radio_color if self._editing_field == key else self.text_color
            border = self.field_border if self._editing_field != key else self.radio_color
            pygame.draw.rect(surface, self.field_color, rects["value"])
            pygame.draw.rect(surface, border, rects["value"], 1)
            val_surf = self.font_field.render(value_str, True, value_color)
            val_rect = val_surf.get_rect(midleft=(rects["value"].x + 4, rects["value"].centery))
            surface.blit(val_surf, val_rect)

        # Loop checkbox — label to the right of the box, not at field_x
        loop_label_x = self.anim_loop_check_rect.right + 6
        self._draw_checkbox(
            surface,
            self.anim_loop_check_rect,
            self.anim_loop,
            "Loop",
            loop_label_x,
        )

        # Animation mode (below loop)
        mode_rects = self.anim_fields_rects.get("mode")
        if mode_rects:
            label_surf = self.font_text.render(mode_rects["label_text"], True, self.text_color)
            surface.blit(label_surf, mode_rects["label"])
            mode_border = self.field_border
            pygame.draw.rect(surface, self.field_color, mode_rects["value"])
            pygame.draw.rect(surface, mode_border, mode_rects["value"], 1)
            mode_text = self.anim_mode_labels[self.anim_mode_index]
            val_surf = self.font_field.render(mode_text, True, self.text_color)
            val_rect = val_surf.get_rect(midleft=(mode_rects["value"].x + 4, mode_rects["value"].centery))
            surface.blit(val_surf, val_rect)

        # Stride hint (auto-computed, below mode)
        hint_color = (160, 160, 160)
        hint_surf = self.font_field.render(f"Stride: {self._computed_stride}  (auto)", True, hint_color)
        surface.blit(hint_surf, self._stride_hint_rect)

    def _draw_checkbox(self, surface: Surface, rect: Rect, checked: bool, label: str, label_x: int):
        pygame.draw.rect(surface, self.field_color, rect)
        pygame.draw.rect(surface, self.field_border, rect, 1)
        if checked:
            pygame.draw.line(surface, self.radio_color, (rect.x + 3, rect.centery), (rect.centerx - 2, rect.bottom - 3), 2)
            pygame.draw.line(surface, self.radio_color, (rect.centerx - 2, rect.bottom - 3), (rect.right - 3, rect.y + 3), 2)
        label_surf = self.font_text.render(label, True, self.text_color)
        label_pos = label_surf.get_rect(midleft=(label_x, rect.centery))
        surface.blit(label_surf, label_pos)

    def _draw_radio(
        self,
        surface: Surface,
        radio_rect: Rect,
        row_rect: Rect,
        is_selected: bool,
        label: str,
        label_rect: Rect,
    ):
        """Draw a radio button with label."""
        pygame.draw.rect(surface, (48, 48, 48), row_rect, border_radius=6)
        pygame.draw.rect(surface, self.border_color, row_rect, 1, border_radius=6)

        center = (radio_rect.centerx, radio_rect.centery)
        radius = radio_rect.width // 2

        pygame.draw.circle(surface, self.border_color, center, radius, 2)

        if is_selected:
            pygame.draw.circle(surface, self.radio_color, center, radius - 4)

        label_surf = self.font_text.render(label, True, self.text_color)
        label_pos = label_surf.get_rect(midleft=(label_rect.x, radio_rect.centery))
        surface.blit(label_surf, label_pos)
