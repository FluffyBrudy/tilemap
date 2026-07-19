from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pygame
from pygame import Rect, Surface

from .button import Button
from .draw_utils import truncate_text
from .theme import COLORS, FONTS

if TYPE_CHECKING:
    from editor import Editor


class PropertyEditor:
    def __init__(
        self,
        editor: "Editor",
        title: str,
        properties: dict[str, Any],
        on_save: Callable[[dict[str, Any]], None],
        on_close: Callable[[], None],
    ):
        self.editor = editor
        self.title = title
        self.properties = properties.copy()
        self.on_save = on_save
        self.on_close = on_close

        self.active = True
        self.width = 400
        self.height = 500
        self.rect = Rect(
            (editor.width - self.width) // 2,
            (editor.height - self.height) // 2,
            self.width,
            self.height,
        )

        self.font_title = FONTS.get_title_font()
        self.font_label = FONTS.get_medium_font()
        self.font_input = FONTS.get_medium_font()

        self.scroll_y = 0
        self.item_height = 40

        self.selected_key: str | None = None
        self.editing_value = False
        self.input_text = ""

        self.new_key_input = ""
        self.is_entering_new_key = False

        self._hovered_truncated: str | None = None

        btn_h = 30
        btn_w = 100
        btn_y = self.rect.bottom - 40
        self.btn_save = Button(
            Rect(self.rect.right - btn_w - 10, btn_y, btn_w, btn_h),
            "Save",
            font=self.font_label,
            on_click=self._on_save_click,
        )
        self.btn_cancel = Button(
            Rect(self.rect.x + 10, btn_y, btn_w, btn_h),
            "Cancel",
            font=self.font_label,
            on_click=self._on_cancel_click,
        )
        self.btn_add = Button(
            Rect(self.rect.centerx - btn_w // 2, btn_y, btn_w, btn_h),
            "Add Prop",
            font=self.font_label,
            on_click=self._on_add_click,
        )

    def _on_save_click(self):
        self.on_save(self.properties)
        self.active = False
        self.on_close()

    def _on_cancel_click(self):
        self.active = False
        self.on_close()

    def _on_add_click(self):
        self.is_entering_new_key = True
        self.new_key_input = ""
        self.selected_key = None
        self.editing_value = False

    def _update_hovered_tooltip(self, mouse_pos):
        self._hovered_truncated = None
        content_rect = Rect(self.rect.x, self.rect.y + 40, self.width, self.height - 90)
        if content_rect.collidepoint(mouse_pos):
            rel_y = mouse_pos[1] - content_rect.y + self.scroll_y
            idx = rel_y // self.item_height
            keys = sorted(self.properties.keys())
            if 0 <= idx < len(keys):
                key = keys[idx]
                val_text = str(self.properties[key])
                value_x = self.rect.x + 125
                max_w = self.rect.right - value_x - 15
                _, truncated = truncate_text(val_text, self.font_input, max_w)
                if truncated:
                    self._hovered_truncated = f"{key}: {val_text}"

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False

        mouse_pos = pygame.mouse.get_pos()

        if self.btn_save.handle_event(event):
            return True
        if self.btn_cancel.handle_event(event):
            return True
        if self.btn_add.handle_event(event):
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                content_rect = Rect(
                    self.rect.x, self.rect.y + 40, self.width, self.height - 90
                )
                if content_rect.collidepoint(mouse_pos):
                    rel_y = mouse_pos[1] - content_rect.y + self.scroll_y
                    idx = rel_y // self.item_height
                    keys = sorted(self.properties.keys())
                    if 0 <= idx < len(keys):
                        self.selected_key = keys[idx]
                        self.editing_value = True
                        self.input_text = str(self.properties[self.selected_key])
                        self.is_entering_new_key = False
                        return True
                    self.selected_key = None
                    self.editing_value = False
                    self.is_entering_new_key = False

            elif event.button == 4:
                self.scroll_y = max(0, self.scroll_y - 20)
                self._update_hovered_tooltip(mouse_pos)
                return True
            elif event.button == 5:
                keys = sorted(self.properties.keys())
                content_height = len(keys) * self.item_height
                content_rect = Rect(
                    self.rect.x, self.rect.y + 40, self.width, self.height - 90
                )
                max_scroll = max(0, content_height - content_rect.height)
                self.scroll_y = min(self.scroll_y + 20, max_scroll)
                self._update_hovered_tooltip(mouse_pos)
                return True

        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(mouse_pos):
                if event.y > 0:
                    self.scroll_y = max(0, self.scroll_y - 20)
                elif event.y < 0:
                    keys = sorted(self.properties.keys())
                    content_height = len(keys) * self.item_height
                    content_rect = Rect(
                        self.rect.x, self.rect.y + 40, self.width, self.height - 90
                    )
                    max_scroll = max(0, content_height - content_rect.height)
                    self.scroll_y = min(self.scroll_y + 20, max_scroll)
                self._update_hovered_tooltip(mouse_pos)
                return True

        if event.type == pygame.MOUSEMOTION:
            self._update_hovered_tooltip(mouse_pos)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.active = False
                self.on_close()
                return True

            if self.is_entering_new_key:
                if event.key == pygame.K_RETURN:
                    if self.new_key_input and self.new_key_input not in self.properties:
                        self.properties[self.new_key_input] = ""
                        self.selected_key = self.new_key_input
                        self.editing_value = True
                        self.input_text = ""
                        self.is_entering_new_key = False
                    return True
                if event.key == pygame.K_BACKSPACE:
                    self.new_key_input = self.new_key_input[:-1]
                else:
                    self.new_key_input += event.unicode
                return True

            if self.editing_value and self.selected_key:
                if event.key == pygame.K_RETURN:
                    val = self.input_text
                    if val.lower() == "true":
                        val = True
                    elif val.lower() == "false":
                        val = False
                    else:
                        try:
                            val = float(val) if "." in val else int(val)
                        except ValueError:
                            pass
                    self.properties[self.selected_key] = val
                    self.editing_value = False
                elif event.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                elif event.key == pygame.K_DELETE:
                    if self.selected_key in self.properties:
                        del self.properties[self.selected_key]
                        self.selected_key = None
                        self.editing_value = False
                else:
                    self.input_text += event.unicode
                return True

        return True

    def draw(self, screen: Surface):
        if not self.active:
            return

        overlay = pygame.Surface(
            (self.editor.width, self.editor.height), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        pygame.draw.rect(screen, COLORS.panel, self.rect, border_radius=8)
        pygame.draw.rect(screen, COLORS.border, self.rect, 2, border_radius=8)

        title_surf = self.font_title.render(self.title, True, COLORS.text)
        screen.blit(title_surf, (self.rect.x + 20, self.rect.y + 10))

        content_rect = Rect(self.rect.x, self.rect.y + 40, self.width, self.height - 90)
        pygame.draw.line(
            screen,
            COLORS.border,
            (self.rect.x, self.rect.y + 40),
            (self.rect.right, self.rect.y + 40),
        )

        keys = sorted(self.properties.keys())
        clip = screen.get_clip()
        screen.set_clip(content_rect)

        for i, key in enumerate(keys):
            y = self.rect.y + 40 + i * self.item_height - self.scroll_y
            if y + self.item_height < content_rect.top or y > content_rect.bottom:
                continue

            is_selected = self.selected_key == key
            bg_col = COLORS.selected if is_selected else COLORS.panel_alt
            row_rect = Rect(
                self.rect.x + 5, y + 2, self.width - 10, self.item_height - 4
            )
            pygame.draw.rect(screen, bg_col, row_rect, border_radius=4)

            key_surf = self.font_label.render(f"{key}:", True, COLORS.text)
            screen.blit(key_surf, (row_rect.x + 10, row_rect.y + 10))

            if is_selected and self.editing_value:
                val_text = self.input_text + "|"
                val_col = COLORS.text
            else:
                val_text = str(self.properties[key])
                if isinstance(self.properties[key], bool):
                    val_col = COLORS.warning
                elif isinstance(self.properties[key], (int, float)):
                    val_col = COLORS.success
                else:
                    val_col = COLORS.text

            value_x = row_rect.x + 120
            max_width = row_rect.right - value_x - 10
            display_val, _ = truncate_text(val_text, self.font_label, max_width)
            val_surf = self.font_label.render(display_val, True, val_col)
            screen.blit(val_surf, (value_x, row_rect.y + 10))

        if self.is_entering_new_key:
            y = self.rect.y + 40 + len(keys) * self.item_height - self.scroll_y
            row_rect = Rect(
                self.rect.x + 5, y + 2, self.width - 10, self.item_height - 4
            )
            pygame.draw.rect(screen, COLORS.selected, row_rect, border_radius=4)
            key_surf = self.font_label.render(
                "New Key: " + self.new_key_input + "|", True, COLORS.text
            )
            screen.blit(key_surf, (row_rect.x + 10, row_rect.y + 10))

        screen.set_clip(clip)

        self.btn_save.draw(screen)
        self.btn_cancel.draw(screen)
        self.btn_add.draw(screen)

        if self._hovered_truncated:
            mx, my = pygame.mouse.get_pos()
            self.editor.tooltip.show(self._hovered_truncated, (mx + 10, my + 10))
