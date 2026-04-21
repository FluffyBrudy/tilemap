import pygame
from typing import TYPE_CHECKING, Dict, Any, Callable, Optional, Tuple
from pygame import Rect, Surface

if TYPE_CHECKING:
    from editor import Editor


class PropertyEditor:
    def __init__(
        self,
        editor: "Editor",
        title: str,
        properties: Dict[str, Any],
        on_save: Callable[[Dict[str, Any]], None],
        on_close: Callable[[], None],
        shrink_value_font: bool = False,
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

        self.font_title = pygame.font.SysFont("Arial", 20, bold=True)
        self.font_label = pygame.font.SysFont("Arial", 16)
        self.font_input = pygame.font.SysFont("Arial", 16)
        self.shrink_value_font = shrink_value_font
        self._font_cache: Dict[int, pygame.font.Font] = {}

        self.scroll_y = 0
        self.item_height = 40
        self.padding = 10

        self.selected_key: Optional[str] = None
        self.editing_value = False
        self.input_text = ""

        self.new_key_input = ""
        self.is_entering_new_key = False

        self.btn_save = Rect(
            self.rect.x + self.width - 110, self.rect.y + self.height - 40, 100, 30
        )
        self.btn_cancel = Rect(
            self.rect.x + 10, self.rect.y + self.height - 40, 100, 30
        )
        self.btn_add = Rect(
            self.rect.x + self.width // 2 - 50, self.rect.y + self.height - 40, 100, 30
        )

    def _get_font(self, size: int) -> pygame.font.Font:
        if size not in self._font_cache:
            self._font_cache[size] = pygame.font.SysFont("Arial", size)
        return self._font_cache[size]

    def _render_value_text(
        self, text: str, color: Tuple[int, int, int], max_width: int
    ) -> pygame.Surface:
        if not self.shrink_value_font or max_width <= 0:
            return self.font_input.render(text, True, color)
        for size in range(16, 9, -1):
            font = self._get_font(size)
            surf = font.render(text, True, color)
            if surf.get_width() <= max_width:
                return surf
        return self._get_font(10).render(text, True, color)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False

        mouse_pos = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.btn_save.collidepoint(mouse_pos):
                    self.on_save(self.properties)
                    self.active = False
                    self.on_close()
                    return True
                if self.btn_cancel.collidepoint(mouse_pos):
                    self.active = False
                    self.on_close()
                    return True
                if self.btn_add.collidepoint(mouse_pos):
                    self.is_entering_new_key = True
                    self.new_key_input = ""
                    self.selected_key = None
                    self.editing_value = False
                    return True

                # Check property list
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
                    else:
                        self.selected_key = None
                        self.editing_value = False
                        self.is_entering_new_key = False

            elif event.button == 4:  # Scroll up
                self.scroll_y = max(0, self.scroll_y - 20)
                return True
            elif event.button == 5:  # Scroll down
                self.scroll_y += 20
                return True

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
                elif event.key == pygame.K_BACKSPACE:
                    self.new_key_input = self.new_key_input[:-1]
                else:
                    self.new_key_input += event.unicode
                return True

            if self.editing_value and self.selected_key:
                if event.key == pygame.K_RETURN:
                    # Basic type inference
                    val = self.input_text
                    if val.lower() == "true":
                        val = True
                    elif val.lower() == "false":
                        val = False
                    else:
                        try:
                            if "." in val:
                                val = float(val)
                            else:
                                val = int(val)
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

        # Modal overlay
        overlay = pygame.Surface(
            (self.editor.width, self.editor.height), pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        # Window
        pygame.draw.rect(screen, (30, 34, 39), self.rect, border_radius=8)
        pygame.draw.rect(screen, (50, 54, 59), self.rect, 2, border_radius=8)

        # Title
        title_surf = self.font_title.render(self.title, True, (255, 255, 255))
        screen.blit(title_surf, (self.rect.x + 20, self.rect.y + 10))

        # Content Area
        content_rect = Rect(self.rect.x, self.rect.y + 40, self.width, self.height - 90)
        pygame.draw.line(
            screen,
            (60, 64, 69),
            (self.rect.x, self.rect.y + 40),
            (self.rect.right, self.rect.y + 40),
        )

        # Render Properties
        keys = sorted(self.properties.keys())
        clip = screen.get_clip()
        screen.set_clip(content_rect)

        for i, key in enumerate(keys):
            y = self.rect.y + 40 + i * self.item_height - self.scroll_y
            if y + self.item_height < content_rect.top or y > content_rect.bottom:
                continue

            is_selected = self.selected_key == key
            bg_col = (50, 60, 80) if is_selected else (35, 39, 44)
            row_rect = Rect(
                self.rect.x + 5, y + 2, self.width - 10, self.item_height - 4
            )
            pygame.draw.rect(screen, bg_col, row_rect, border_radius=4)

            key_surf = self.font_label.render(f"{key}:", True, (200, 200, 200))
            screen.blit(key_surf, (row_rect.x + 10, row_rect.y + 10))

            if is_selected and self.editing_value:
                val_text = self.input_text + "|"
                val_col = (255, 255, 255)
            else:
                val_text = str(self.properties[key])
                val_col = (
                    (150, 255, 150)
                    if isinstance(self.properties[key], (int, float))
                    else (
                        (255, 200, 100)
                        if isinstance(self.properties[key], bool)
                        else (255, 255, 255)
                    )
                )

            value_x = row_rect.x + 120
            max_width = row_rect.right - value_x - 10
            val_surf = self._render_value_text(val_text, val_col, max_width)
            screen.blit(val_surf, (value_x, row_rect.y + 10))

        if self.is_entering_new_key:
            y = self.rect.y + 40 + len(keys) * self.item_height - self.scroll_y
            row_rect = Rect(
                self.rect.x + 5, y + 2, self.width - 10, self.item_height - 4
            )
            pygame.draw.rect(screen, (60, 70, 90), row_rect, border_radius=4)
            key_surf = self.font_label.render(
                "New Key: " + self.new_key_input + "|", True, (255, 255, 255)
            )
            screen.blit(key_surf, (row_rect.x + 10, row_rect.y + 10))

        screen.set_clip(clip)

        # Buttons
        for btn, text, col in [
            (self.btn_save, "Save", (40, 150, 80)),
            (self.btn_cancel, "Cancel", (150, 60, 60)),
            (self.btn_add, "Add Prop", (60, 100, 150)),
        ]:
            pygame.draw.rect(screen, col, btn, border_radius=4)
            txt_surf = self.font_label.render(text, True, (255, 255, 255))
            screen.blit(txt_surf, txt_surf.get_rect(center=btn.center))
