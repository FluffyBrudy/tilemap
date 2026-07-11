import pygame
from typing import Optional
from pygame import Rect

from .widget_base import WidgetBase
from .ui.theme import COLORS, FONTS, SHAPE
from .ui.draw_utils import draw_panel


class InputBox(WidgetBase):
    def __init__(self, rect, *, font=None, padding=3, allowed_chars=None):
        super().__init__(rect, padding=padding, border_width=1)
        self._text = ""
        self.is_focused = False
        self.cursor_pos = 0
        self.selection_start: Optional[int] = None
        self.allowed_chars = allowed_chars
        self.font = font or FONTS.get_font(16)

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, val: str):
        self._text = val
        self.cursor_pos = len(val)

    def is_char_allowed(self, char: str) -> bool:
        if self.allowed_chars is not None:
            return char in self.allowed_chars
        return char.isprintable()

    def insert_text(self, text: str) -> None:
        filtered = "".join(c for c in text if self.is_char_allowed(c))
        if self.selection_start is not None:
            start = min(self.selection_start, self.cursor_pos)
            end = max(self.selection_start, self.cursor_pos)
            self._text = self._text[:start] + filtered + self._text[end:]
            self.cursor_pos = start + len(filtered)
        else:
            self._text = (
                self._text[: self.cursor_pos] + filtered + self._text[self.cursor_pos :]
            )
            self.cursor_pos += len(filtered)
        self.selection_start = None

    def delete_char(self, forward: bool = False) -> None:
        if self.selection_start is not None:
            start = min(self.selection_start, self.cursor_pos)
            end = max(self.selection_start, self.cursor_pos)
            self._text = self._text[:start] + self._text[end:]
            self.cursor_pos = start
            self.selection_start = None
        elif forward:
            if self.cursor_pos < len(self._text):
                self._text = (
                    self._text[: self.cursor_pos] + self._text[self.cursor_pos + 1 :]
                )
        else:
            if self.cursor_pos > 0:
                self._text = (
                    self._text[: self.cursor_pos - 1] + self._text[self.cursor_pos :]
                )
                self.cursor_pos -= 1

    def move_cursor(self, delta: int) -> None:
        new_pos = max(0, min(len(self._text), self.cursor_pos + delta))
        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
            if self.selection_start is None:
                self.selection_start = self.cursor_pos
        else:
            self.selection_start = None
        self.cursor_pos = new_pos

    def select_all(self) -> None:
        self.selection_start = 0
        self.cursor_pos = len(self._text)

    def clear_selection(self) -> None:
        self.selection_start = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.is_focused = self.rect.collidepoint(event.pos)
            if self.is_focused:
                mouse_x = event.pos[0] - self.content_rect.x
                self.cursor_pos = 0
                for i, char in enumerate(self._text):
                    if self.font.size(self._text[: i + 1])[0] > mouse_x:
                        self.cursor_pos = i
                        break
                else:
                    self.cursor_pos = len(self._text)
                self.selection_start = None
            return self.is_focused

        if self.is_focused and event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)

            if ctrl_held and event.key == pygame.K_a:
                self.select_all()
                return True

            if event.key == pygame.K_LEFT:
                self.move_cursor(-1)
                return True
            elif event.key == pygame.K_RIGHT:
                self.move_cursor(1)
                return True
            elif event.key == pygame.K_HOME:
                self.move_cursor(-self.cursor_pos)
                return True
            elif event.key == pygame.K_END:
                self.move_cursor(len(self._text) - self.cursor_pos)
                return True
            elif event.key == pygame.K_BACKSPACE:
                self.delete_char(forward=False)
                return True
            elif event.key == pygame.K_DELETE:
                self.delete_char(forward=True)
                return True
            elif event.key == pygame.K_RETURN:
                return False
            elif event.key == pygame.K_TAB:
                return False
            elif event.unicode:
                self.insert_text(event.unicode)
                return True

        if self.is_focused and event.type == pygame.KEYUP:
            if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                self.selection_start = None

        return False

    def draw(self, surface):
        bw = 2 if self.is_focused else 1
        self.bw = bw
        self._update_content_rect()

        border_color = COLORS.accent if self.is_focused else COLORS.border
        pygame.draw.rect(
            surface, COLORS.panel_alt, self.rect, border_radius=SHAPE.radius_sm
        )
        pygame.draw.rect(
            surface, border_color, self.rect, bw, border_radius=SHAPE.radius_sm
        )

        clip = surface.get_clip()
        if clip:
            clipped_content = self.content_rect.clip(clip)
            surface.set_clip(clipped_content)
        else:
            surface.set_clip(self.content_rect)

        if self.selection_start is not None:
            start = min(self.selection_start, self.cursor_pos)
            end = max(self.selection_start, self.cursor_pos)
            if start != end:
                prefix = self._text[:start]
                selected = self._text[start:end]
                prefix_w = self.font.size(prefix)[0]
                select_w = self.font.size(selected)[0]
                sel_rect = Rect(
                    self.content_rect.x + prefix_w,
                    self.content_rect.y,
                    select_w,
                    self.content_rect.height,
                )
                pygame.draw.rect(surface, COLORS.selected, sel_rect)

        txt_surf = self.font.render(self._text, True, COLORS.text)
        surface.blit(txt_surf, (self.content_rect.x, self.content_rect.y))

        if self.is_focused:
            cursor_x = (
                self.content_rect.x + self.font.size(self._text[: self.cursor_pos])[0]
            )
            if cursor_x < self.content_rect.right - 1:
                pygame.draw.line(
                    surface,
                    COLORS.text,
                    (cursor_x, self.content_rect.y),
                    (cursor_x, self.content_rect.bottom - 1),
                    1,
                )
        surface.set_clip(clip)


class BaseTextInput:
    def __init__(
        self,
        rect: Rect,
        label: str,
        key: str,
        default_val: str = "",
        tab_index: Optional[int] = None,
        allowed_chars: Optional[str] = None,
    ):
        self.rect_area = rect
        self.label = label
        self.key = key
        self.tab_index = tab_index

        input_rect = Rect(rect.x, rect.y + 20, rect.width, 30)
        self.input_box = InputBox(input_rect, allowed_chars=allowed_chars)
        self.input_box.text = default_val
        self.input_box.cursor_pos = len(default_val)

        self.font_lbl = FONTS.get_font(14)

    @property
    def is_focused(self):
        return self.input_box.is_focused

    @is_focused.setter
    def is_focused(self, val):
        self.input_box.is_focused = val

    @property
    def text(self):
        return self.input_box.text

    @text.setter
    def text(self, val):
        self.input_box.text = val

    @property
    def cursor_pos(self):
        return self.input_box.cursor_pos

    @cursor_pos.setter
    def cursor_pos(self, val):
        self.input_box.cursor_pos = val

    @property
    def selection_start(self):
        return self.input_box.selection_start

    @selection_start.setter
    def selection_start(self, val):
        self.input_box.selection_start = val

    def is_char_allowed(self, char: str) -> bool:
        return self.input_box.is_char_allowed(char)

    def insert_text(self, text: str) -> None:
        self.input_box.insert_text(text)

    def delete_char(self, forward: bool = False) -> None:
        self.input_box.delete_char(forward)

    def move_cursor(self, delta: int) -> None:
        self.input_box.move_cursor(delta)

    def select_all(self) -> None:
        self.input_box.select_all()

    def clear_selection(self) -> None:
        self.input_box.clear_selection()

    def resize(self, rect_area: Rect):
        self.rect_area = rect_area
        self.input_box.resize(rect_area.x, rect_area.y + 20, rect_area.width, 30)

    def handle_event(self, event: pygame.event.Event) -> bool:
        return self.input_box.handle_event(event)

    def get_value(self):
        return self.input_box.text

    def get_int_value(self) -> int:
        txt = self.input_box.text
        return int(txt) if txt else 0

    def draw(self, screen: pygame.Surface):
        screen.blit(
            self.font_lbl.render(self.label, True, COLORS.text_dim),
            (self.rect_area.x, self.rect_area.y),
        )
        self.input_box.draw(screen)


class TextInput(BaseTextInput):
    def __init__(
        self,
        rect: Rect,
        label: str,
        key: str,
        default_val: str = "",
        tab_index: Optional[int] = None,
    ):
        super().__init__(rect, label, key, default_val, tab_index, allowed_chars=None)


class InlineTextInput:
    def __init__(
        self,
        key: str,
        default_val: str = "",
        allowed_chars: Optional[str] = None,
    ):
        self.key = key
        self.text = default_val
        self.is_focused = False
        self.cursor_pos = len(default_val)
        self.selection_start: Optional[int] = None
        self.allowed_chars = allowed_chars

    def is_char_allowed(self, char: str) -> bool:
        if self.allowed_chars is not None:
            return char in self.allowed_chars
        return char.isprintable()

    def insert_text(self, text: str) -> None:
        filtered = "".join(c for c in text if self.is_char_allowed(c))
        if self.selection_start is not None:
            start = min(self.selection_start, self.cursor_pos)
            end = max(self.selection_start, self.cursor_pos)
            self.text = self.text[:start] + filtered + self.text[end:]
            self.cursor_pos = start + len(filtered)
        else:
            self.text = (
                self.text[: self.cursor_pos] + filtered + self.text[self.cursor_pos :]
            )
            self.cursor_pos += len(filtered)
        self.selection_start = None

    def delete_char(self, forward: bool = False) -> None:
        if self.selection_start is not None:
            start = min(self.selection_start, self.cursor_pos)
            end = max(self.selection_start, self.cursor_pos)
            self.text = self.text[:start] + self.text[end:]
            self.cursor_pos = start
            self.selection_start = None
        elif forward:
            if self.cursor_pos < len(self.text):
                self.text = (
                    self.text[: self.cursor_pos] + self.text[self.cursor_pos + 1 :]
                )
        else:
            if self.cursor_pos > 0:
                self.text = (
                    self.text[: self.cursor_pos - 1] + self.text[self.cursor_pos :]
                )
                self.cursor_pos -= 1

    def move_cursor(self, delta: int) -> None:
        new_pos = max(0, min(len(self.text), self.cursor_pos + delta))
        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
            if self.selection_start is None:
                self.selection_start = self.cursor_pos
        else:
            self.selection_start = None
        self.cursor_pos = new_pos

    def select_all(self) -> None:
        self.selection_start = 0
        self.cursor_pos = len(self.text)

    def clear(self) -> None:
        self.text = ""
        self.cursor_pos = 0
        self.selection_start = None

    def delete_word_left(self) -> None:
        if self.selection_start is not None:
            start = min(self.selection_start, self.cursor_pos)
            end = max(self.selection_start, self.cursor_pos)
            self.text = self.text[:start] + self.text[end:]
            self.cursor_pos = start
            self.selection_start = None
            return
        if self.cursor_pos == 0:
            return
        idx = self.cursor_pos - 1
        while idx >= 0 and self.text[idx] == " ":
            idx -= 1
        while idx >= 0 and self.text[idx] != " ":
            idx -= 1
        self.text = self.text[: idx + 1] + self.text[self.cursor_pos :]
        self.cursor_pos = idx + 1

    def handle_event(self, event: pygame.event.Event, font: pygame.font.Font) -> bool:
        if not self.is_focused:
            return False

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)
            mods & pygame.KMOD_SHIFT

            if ctrl_held and event.key == pygame.K_a:
                self.select_all()
                return True
            if ctrl_held and event.key == pygame.K_BACKSPACE:
                self.delete_word_left()
                return True

            if event.key == pygame.K_LEFT:
                self.move_cursor(-1)
                return True
            elif event.key == pygame.K_RIGHT:
                self.move_cursor(1)
                return True
            elif event.key == pygame.K_HOME:
                self.move_cursor(-self.cursor_pos)
                return True
            elif event.key == pygame.K_END:
                self.move_cursor(len(self.text) - self.cursor_pos)
                return True
            elif event.key == pygame.K_BACKSPACE:
                self.delete_char(forward=False)
                return True
            elif event.key == pygame.K_DELETE:
                self.delete_char(forward=True)
                return True
            elif event.key == pygame.K_RETURN:
                return False
            elif event.key == pygame.K_TAB:
                return False
            elif event.unicode:
                self.insert_text(event.unicode)
                return True

        if event.type == pygame.KEYUP:
            if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                self.selection_start = None

        return False

    def get_value(self) -> str:
        return self.text


class DigitInput(BaseTextInput):
    def __init__(
        self,
        rect: Rect,
        label: str,
        key: str,
        default_val: str = "",
        tab_index: Optional[int] = None,
    ):
        super().__init__(
            rect, label, key, default_val, tab_index, allowed_chars="0123456789"
        )

    def is_char_allowed(self, char: str) -> bool:
        return char.isdigit()

    def get_value(self) -> int:
        return self.get_int_value()
