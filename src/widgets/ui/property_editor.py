from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pygame
from pygame import Rect, Surface

from utils.context_dispatch import PropertyContext

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
        context: PropertyContext,
        on_close: Callable[[], None] | None = None,
    ):
        self.editor = editor
        self.title = title
        self.properties = properties.copy()
        self.context = context
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
        self._ghost_text: str = ""
        self.editor.suggestion_registry.refresh(self.editor)

        btn_h = 30
        btn_w = 100
        btn_y = self.rect.bottom - 40
        self.btn_cancel = Button(
            Rect(self.rect.x + 10, btn_y, btn_w, btn_h),
            "Cancel",
            font=self.font_label,
            on_click=self._on_cancel_click,
        )
        self.btn_remove = Button(
            Rect(self.rect.centerx - btn_w // 2, btn_y, btn_w, btn_h),
            "Remove",
            font=self.font_label,
            danger=True,
            on_click=self._on_remove_click,
        )
        self.btn_add = Button(
            Rect(self.rect.right - 10 - btn_w, btn_y, btn_w, btn_h),
            "Add Prop",
            font=self.font_label,
            on_click=self._on_add_click,
        )
        self.btn_remove.enabled = False

    def _commit_save(self):
        """Dispatch the staged properties to the context target, then close."""
        if not self.editor.context_dispatch.save(self.context, self.properties):
            self.editor.notifications.notify(
                "Cannot save: no property handler for this target"
            )
            return
        self.active = False
        self._ghost_text = ""
        if self.on_close:
            self.on_close()

    def _on_cancel_click(self):
        self.active = False
        if self.on_close:
            self.on_close()

    def _on_add_click(self):
        self.is_entering_new_key = True
        self.new_key_input = ""
        self.selected_key = None
        self.editing_value = False
        self._ghost_text = self.editor.suggestion_registry.key_ghost("")
        self._update_remove_enabled()

    def _on_remove_click(self):
        if self.is_entering_new_key or not self.selected_key:
            return
        if self.selected_key in self.properties:
            del self.properties[self.selected_key]
        self.selected_key = None
        self.editing_value = False
        self.input_text = ""
        self.is_entering_new_key = False
        self._ghost_text = ""
        self._update_remove_enabled()

    def _update_remove_enabled(self):
        self.btn_remove.enabled = (
            self.selected_key is not None and not self.is_entering_new_key
        )

    def _title_display(self) -> tuple[str, bool]:
        max_w = self.rect.right - (self.rect.x + 20) - 20
        return truncate_text(self.title, self.font_title, max_w)

    def _update_hovered_tooltip(self, mouse_pos):
        self._hovered_truncated = None
        _, title_truncated = self._title_display()
        if title_truncated:
            title_rect = Rect(
                self.rect.x + 20,
                self.rect.y + 8,
                self.rect.right - (self.rect.x + 20) - 20,
                28,
            )
            if title_rect.collidepoint(mouse_pos):
                self._hovered_truncated = self.title
                return
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

        if self.btn_cancel.handle_event(event):
            return True
        if self.btn_remove.handle_event(event):
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
                        self._ghost_text = self.editor.suggestion_registry.ghost_text(
                            self.selected_key, self.input_text
                        )
                        self.is_entering_new_key = False
                        self._update_remove_enabled()
                        return True
                    self.selected_key = None
                    self.editing_value = False
                    self._ghost_text = ""
                    self.is_entering_new_key = False
                    self._update_remove_enabled()

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
                if self.on_close:
                    self.on_close()
                return True

            if self.is_entering_new_key:
                if event.key == pygame.K_RETURN:
                    if self.new_key_input and self.new_key_input not in self.properties:
                        self.properties[self.new_key_input] = ""
                        self.selected_key = self.new_key_input
                        self.editing_value = True
                        self.input_text = ""
                        self._ghost_text = self.editor.suggestion_registry.ghost_text(
                            self.selected_key, self.input_text
                        )
                        self.is_entering_new_key = False
                        self._update_remove_enabled()
                    return True
                if event.key == pygame.K_TAB:
                    if self._ghost_text:
                        self.new_key_input = self.new_key_input + self._ghost_text
                        self._ghost_text = self.editor.suggestion_registry.key_ghost(
                            self.new_key_input
                        )
                    return True
                if event.key == pygame.K_BACKSPACE:
                    self.new_key_input = self.new_key_input[:-1]
                    self._ghost_text = self.editor.suggestion_registry.key_ghost(
                        self.new_key_input
                    )
                else:
                    self.new_key_input += event.unicode
                    if self._ghost_text and event.unicode:
                        if self._ghost_text[0].lower() == event.unicode.lower():
                            self._ghost_text = self._ghost_text[1:]
                        else:
                            self._ghost_text = self.editor.suggestion_registry.key_ghost(
                                self.new_key_input
                            )
                    else:
                        self._ghost_text = self.editor.suggestion_registry.key_ghost(
                            self.new_key_input
                        )
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
                    self._ghost_text = ""
                    self._commit_save()
                    return True
                if event.key == pygame.K_TAB:
                    if self._ghost_text:
                        self.input_text = self.input_text + self._ghost_text
                        self._ghost_text = ""
                elif event.key == pygame.K_BACKSPACE:
                    self.input_text = self.input_text[:-1]
                    self._ghost_text = self.editor.suggestion_registry.ghost_text(
                        self.selected_key, self.input_text
                    )
                elif event.key == pygame.K_DELETE:
                    if self.selected_key in self.properties:
                        del self.properties[self.selected_key]
                        self.selected_key = None
                        self.editing_value = False
                        self._ghost_text = ""
                else:
                    self.input_text += event.unicode
                    if self._ghost_text and event.unicode:
                        if self._ghost_text[0].lower() == event.unicode.lower():
                            self._ghost_text = self._ghost_text[1:]
                        else:
                            self._ghost_text = self.editor.suggestion_registry.ghost_text(
                                self.selected_key, self.input_text
                            )
                    else:
                        self._ghost_text = self.editor.suggestion_registry.ghost_text(
                            self.selected_key, self.input_text
                        )
                return True

            if event.key == pygame.K_RETURN:
                self._commit_save()
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

        title_text, _ = self._title_display()
        title_surf = self.font_title.render(title_text, True, COLORS.text)
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

            key_surf = self.font_label.render(
                f"{key}:",
                True,
                COLORS.text_on_accent if is_selected else COLORS.text,
            )
            screen.blit(key_surf, (row_rect.x + 10, row_rect.y + 10))

            value_x = row_rect.x + 120
            max_width = row_rect.right - value_x - 10

            if is_selected and self.editing_value:
                if self._ghost_text:
                    display_input, was_truncated = truncate_text(self.input_text, self.font_label, max_width)
                    user_surf = self.font_label.render(display_input, True, COLORS.text)
                    screen.blit(user_surf, (value_x, row_rect.y + 10))
                    cursor_x = value_x + user_surf.get_width()
                    if not was_truncated:
                        ghost_surf = self.font_label.render(self._ghost_text, True, COLORS.text_dim)
                        ghost_w = ghost_surf.get_width()
                        if cursor_x + ghost_w <= row_rect.right - 10:
                            screen.blit(ghost_surf, (cursor_x, row_rect.y + 10))
                    if pygame.time.get_ticks() // 500 % 2 == 0:
                        pygame.draw.line(
                            screen, COLORS.text,
                            (cursor_x, row_rect.y + 8),
                            (cursor_x, row_rect.y + 28), 2,
                        )
                else:
                    val_text = self.input_text + ("|" if pygame.time.get_ticks() // 500 % 2 == 0 else " ")
                    display_val, _ = truncate_text(val_text, self.font_label, max_width)
                    val_surf = self.font_label.render(display_val, True, COLORS.text)
                    screen.blit(val_surf, (value_x, row_rect.y + 10))
            else:
                raw_val = str(self.properties[key])
                if raw_val == "":
                    val_text = "(empty)"
                    val_col = COLORS.text_dim
                else:
                    val_text = raw_val
                    if isinstance(self.properties[key], bool):
                        val_col = COLORS.warning
                    elif isinstance(self.properties[key], (int, float)):
                        val_col = COLORS.success
                    else:
                        val_col = COLORS.text
                display_val, _ = truncate_text(val_text, self.font_label, max_width)
                val_surf = self.font_label.render(display_val, True, val_col)
                screen.blit(val_surf, (value_x, row_rect.y + 10))

        if self.is_entering_new_key:
            y = self.rect.y + 40 + len(keys) * self.item_height - self.scroll_y
            row_rect = Rect(
                self.rect.x + 5, y + 2, self.width - 10, self.item_height - 4
            )
            pygame.draw.rect(screen, COLORS.selected, row_rect, border_radius=4)
            label_w = self.font_label.size("New Key: ")[0]
            lbl_surf = self.font_label.render("New Key: ", True, COLORS.text_on_accent)
            screen.blit(lbl_surf, (row_rect.x + 10, row_rect.y + 10))
            input_x = row_rect.x + 10 + label_w
            key_input = self.new_key_input
            max_kw = row_rect.right - input_x - 10
            display_key, _ = truncate_text(key_input, self.font_label, max_kw)
            input_surf = self.font_label.render(display_key, True, COLORS.text)
            screen.blit(input_surf, (input_x, row_rect.y + 10))
            cursor_x = input_x + input_surf.get_width()
            if self._ghost_text:
                ghost_surf = self.font_label.render(self._ghost_text, True, COLORS.text_dim)
                max_gw = row_rect.right - cursor_x - 10
                if ghost_surf.get_width() <= max_gw:
                    screen.blit(ghost_surf, (cursor_x, row_rect.y + 10))
                if pygame.time.get_ticks() // 500 % 2 == 0:
                    pygame.draw.line(
                        screen, COLORS.text,
                        (cursor_x, row_rect.y + 8),
                        (cursor_x, row_rect.y + 28), 2,
                    )
            else:
                if pygame.time.get_ticks() // 500 % 2 == 0:
                    cursor_char = "|"
                else:
                    cursor_char = " "
                cur_surf = self.font_label.render(cursor_char, True, COLORS.text)
                screen.blit(cur_surf, (cursor_x, row_rect.y + 10))

        screen.set_clip(clip)

        self._update_remove_enabled()
        self.btn_cancel.draw(screen)
        self.btn_remove.draw(screen)
        self.btn_add.draw(screen)

        if self._hovered_truncated:
            mx, my = pygame.mouse.get_pos()
            self.editor.tooltip.show(self._hovered_truncated, (mx + 10, my + 10))
