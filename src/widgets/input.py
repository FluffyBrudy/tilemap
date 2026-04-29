import pygame
from typing import Optional
from pygame import Rect


COLOR_TEXT = (220, 220, 220)
COLOR_BORDER = (80, 80, 80)
COLOR_ACCENT = (60, 100, 160)
COLOR_BG_INPUT = (20, 20, 20)
COLOR_SELECTION = (60, 100, 160)
COLOR_LABEL = (150, 150, 150)


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
        self.text = default_val
        self.is_focused = False
        self.tab_index = tab_index
        self.cursor_pos = len(default_val)
        self.selection_start: Optional[int] = None
        self.allowed_chars = allowed_chars
        self._cursor_visible = True
        self._cursor_timer = 0

        self.rect_input = Rect(rect.x, rect.y + 20, rect.width, 30)
        self.font = pygame.font.SysFont("Arial", 16)
        self.font_lbl = pygame.font.SysFont("Arial", 14)

    def is_char_allowed(self, char: str) -> bool:
        if self.allowed_chars is not None:
            return char in self.allowed_chars
        return True

    def insert_text(self, text: str) -> None:
        if self.selection_start is not None:
            start = min(self.selection_start, self.cursor_pos)
            end = max(self.selection_start, self.cursor_pos)
            self.text = self.text[:start] + text + self.text[end:]
            self.cursor_pos = start + len(text)
        else:
            filtered = "".join(c for c in text if self.is_char_allowed(c))
            self.text = self.text[:self.cursor_pos] + filtered + self.text[self.cursor_pos:]
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
                self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos + 1 :]
        else:
            if self.cursor_pos > 0:
                self.text = self.text[: self.cursor_pos - 1] + self.text[self.cursor_pos :]
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

    def clear_selection(self) -> None:
        self.selection_start = None

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.is_focused = self.rect_input.collidepoint(event.pos)
            if self.is_focused:
                mouse_x = event.pos[0] - self.rect_input.x - 5
                self.cursor_pos = 0
                for i, char in enumerate(self.text):
                    if self.font.size(self.text[:i + 1])[0] > mouse_x:
                        self.cursor_pos = i
                        break
                else:
                    self.cursor_pos = len(self.text)
                self.selection_start = None
            return self.is_focused

        if self.is_focused and event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)
            shift_held = mods & pygame.KMOD_SHIFT

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

        if self.is_focused and event.type == pygame.KEYUP:
            if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                self.selection_start = None

        return False

    def get_value(self) -> str:
        return self.text

    def get_int_value(self) -> int:
        return int(self.text) if self.text else 0

    def draw(self, screen: pygame.Surface):
        screen.blit(
            self.font_lbl.render(self.label, True, COLOR_LABEL),
            (self.rect_area.x, self.rect_area.y),
        )

        col = COLOR_ACCENT if self.is_focused else COLOR_BORDER
        pygame.draw.rect(screen, COLOR_BG_INPUT, self.rect_input)
        pygame.draw.rect(screen, col, self.rect_input, 2 if self.is_focused else 1)

        if self.selection_start is not None:
            start = min(self.selection_start, self.cursor_pos)
            end = max(self.selection_start, self.cursor_pos)
            if start != end:
                prefix = self.text[:start]
                selected = self.text[start:end]
                prefix_w = self.font.size(prefix)[0]
                select_w = self.font.size(selected)[0]
                sel_rect = Rect(
                    self.rect_input.x + 5 + prefix_w,
                    self.rect_input.y + 2,
                    select_w,
                    self.rect_input.height - 4,
                )
                pygame.draw.rect(screen, COLOR_SELECTION, sel_rect)

        txt_surf = self.font.render(self.text, True, COLOR_TEXT)
        screen.blit(txt_surf, (self.rect_input.x + 5, self.rect_input.y + 5))

        if self.is_focused:
            cursor_x = self.rect_input.x + 5 + self.font.size(self.text[:self.cursor_pos])[0]
            if cursor_x < self.rect_input.x + self.rect_input.width - 5:
                pygame.draw.line(
                    screen,
                    COLOR_TEXT,
                    (cursor_x, self.rect_input.y + 5),
                    (cursor_x, self.rect_input.y + self.rect_input.height - 5),
                    1,
                )


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

    def is_char_allowed(self, char: str) -> bool:
        return char.isprintable()


class InlineTextInput:
    """Text input handler for inline use (no rect-based positioning)."""

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
        if self.selection_start is not None:
            start = min(self.selection_start, self.cursor_pos)
            end = max(self.selection_start, self.cursor_pos)
            self.text = self.text[:start] + text + self.text[end:]
            self.cursor_pos = start + len(text)
        else:
            filtered = "".join(c for c in text if self.is_char_allowed(c))
            self.text = self.text[:self.cursor_pos] + filtered + self.text[self.cursor_pos:]
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
                self.text = self.text[:self.cursor_pos] + self.text[self.cursor_pos + 1:]
        else:
            if self.cursor_pos > 0:
                self.text = self.text[: self.cursor_pos - 1] + self.text[self.cursor_pos :]
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

    def handle_event(self, event: pygame.event.Event, font: pygame.font.Font) -> bool:
        if not self.is_focused:
            return False

        if event.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_CTRL | pygame.KMOD_META)
            shift_held = mods & pygame.KMOD_SHIFT

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
        super().__init__(rect, label, key, default_val, tab_index, allowed_chars="0123456789")

    def is_char_allowed(self, char: str) -> bool:
        return char.isdigit()

    def get_value(self) -> int:
        return self.get_int_value()