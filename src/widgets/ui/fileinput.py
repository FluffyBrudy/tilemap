import pygame
from pygame import Rect, Surface, Color
from pathlib import Path
from typing import List, Callable, Optional
import os

from constants import BASE_PATH


INPUT_BG = (30, 30, 30)
INPUT_BORDER = (100, 100, 100)
TEXT_COLOR = (255, 255, 255)
SUGGESTION_BG = (40, 44, 52)
SUGGESTION_HL = (60, 100, 180)


class FilenameInput:
    def __init__(
        self,
        editor_rect: Rect,
        on_confirm: Callable[[str], None],
        on_cancel: Callable[[], None],
    ):
        self.rect = Rect(0, 0, 400, 40)
        self.rect.center = editor_rect.center

        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

        self.text = ""
        self.active = False
        self.font = pygame.font.SysFont("Consolas", 14)

        self.suggestions: List[str] = []
        self.selected_suggestion_idx = -1
        self.data_root = BASE_PATH / "data"

    def show(self):
        self.active = True
        self.text = ""
        self.suggestions = []
        self.selected_suggestion_idx = -1

        self._update_suggestions()

    def hide(self):
        self.active = False

    def _update_suggestions(self):
        if not self.data_root.exists():
            self.data_root.mkdir(parents=True, exist_ok=True)

        candidates = []

        try:
            for root, dirs, files in os.walk(self.data_root):
                rel_path = Path(root).relative_to(self.data_root)
                depth = len(rel_path.parts)

                if str(rel_path) == ".":
                    depth = 0

                if depth > 1:
                    continue

                for f in files:
                    if f.endswith(".json"):
                        full_p = rel_path / f
                        candidates.append(str(full_p).replace("\\", "/"))

                for d in dirs:
                    full_p = rel_path / d
                    candidates.append(str(full_p).replace("\\", "/") + "/")
        except Exception:
            pass

        self.suggestions = [c for c in candidates if c.startswith(self.text)]
        self.suggestions.sort()

        self.suggestions = self.suggestions[:5]

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.active:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.on_cancel()
                self.hide()

            elif event.key == pygame.K_RETURN:
                if self.selected_suggestion_idx >= 0 and self.suggestions:
                    self.text = self.suggestions[self.selected_suggestion_idx]
                    self.selected_suggestion_idx = -1
                    self._update_suggestions()
                else:
                    self.on_confirm(self.text)
                    self.hide()

            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                self.selected_suggestion_idx = -1
                self._update_suggestions()

            elif event.key == pygame.K_UP:
                self.selected_suggestion_idx = max(-1, self.selected_suggestion_idx - 1)

            elif event.key == pygame.K_DOWN:
                self.selected_suggestion_idx = min(
                    len(self.suggestions) - 1, self.selected_suggestion_idx + 1
                )

            elif event.key == pygame.K_TAB:
                if self.suggestions:
                    self.text = self.suggestions[0]
                    self._update_suggestions()

            else:
                if len(event.unicode) > 0 and event.unicode.isprintable():
                    self.text += event.unicode
                    self.selected_suggestion_idx = -1
                    self._update_suggestions()

            return True

        return True

    def draw(self, screen: Surface):
        if not self.active:
            return

        pygame.draw.rect(screen, INPUT_BG, self.rect)
        pygame.draw.rect(screen, INPUT_BORDER, self.rect, 2)

        txt_surf = self.font.render(self.text + "_", True, TEXT_COLOR)
        screen.blit(
            txt_surf, (self.rect.x + 10, self.rect.centery - txt_surf.get_height() // 2)
        )

        title_surf = self.font.render(
            "Save Map As: (relative to data/)", True, (255, 255, 255)
        )
        screen.blit(title_surf, (self.rect.x, self.rect.y - 20))

        if self.suggestions:
            box_h = 25
            total_h = len(self.suggestions) * box_h
            sugg_rect = Rect(self.rect.x, self.rect.bottom, self.rect.width, total_h)

            pygame.draw.rect(screen, SUGGESTION_BG, sugg_rect)
            pygame.draw.rect(screen, INPUT_BORDER, sugg_rect, 1)

            for i, suggestion in enumerate(self.suggestions):
                row_rect = Rect(
                    sugg_rect.x, sugg_rect.y + i * box_h, sugg_rect.width, box_h
                )

                if i == self.selected_suggestion_idx:
                    pygame.draw.rect(screen, SUGGESTION_HL, row_rect)

                s_txt = self.font.render(suggestion, True, (180, 180, 180))
                screen.blit(s_txt, (row_rect.x + 10, row_rect.y + 4))
