import pygame
from typing import TYPE_CHECKING, List
from pygame import Rect


if TYPE_CHECKING:
    from editor import Editor


COLOR_BG = (45, 45, 50)
COLOR_BORDER = (80, 80, 80)
COLOR_ACCENT = (60, 100, 160)
COLOR_TEXT = (220, 220, 220)
COLOR_ERROR = (200, 60, 60)


class FormInput:
    def __init__(self, rect: Rect, label: str, key: str, default_val: str = ""):
        self.rect_area = rect
        self.label = label
        self.key = key
        self.text = default_val
        self.is_focused = False

        self.rect_input = Rect(rect.x, rect.y + 20, rect.width, 30)
        self.font = pygame.font.SysFont("Arial", 16)
        self.font_lbl = pygame.font.SysFont("Arial", 14)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.is_focused = self.rect_input.collidepoint(event.pos)
            return self.is_focused

        if self.is_focused and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (pygame.K_RETURN, pygame.K_TAB):
                return False
            elif event.unicode.isdigit():
                self.text += event.unicode
            return True
        return False

    def get_value(self) -> int:
        return int(self.text) if self.text else 0

    def draw(self, screen: pygame.Surface):
        screen.blit(
            self.font_lbl.render(self.label, True, (150, 150, 150)),
            (self.rect_area.x, self.rect_area.y),
        )

        col = COLOR_ACCENT if self.is_focused else COLOR_BORDER
        pygame.draw.rect(screen, (20, 20, 20), self.rect_input)
        pygame.draw.rect(screen, col, self.rect_input, 2 if self.is_focused else 1)

        txt_surf = self.font.render(self.text, True, COLOR_TEXT)
        screen.blit(txt_surf, (self.rect_input.x + 5, self.rect_input.y + 5))


class MapSetup:
    def __init__(self, editor: "Editor", center_rect: Rect):
        self.editor = editor
        self.rect = center_rect
        self.visible = True
        self.error_message = ""

        self.inputs: List[FormInput] = []
        fields = [
            ("Map Width", "map_w", "30"),
            ("Map Height", "map_h", "20"),
            ("Tile Width", "tile_w", "32"),
            ("Tile Height", "tile_h", "32"),
        ]

        cols = 2
        cell_w = (self.rect.width - 40) // cols
        cell_h = 70
        start_x = self.rect.x + 20
        start_y = self.rect.y + 60

        for i, (lbl, key, default) in enumerate(fields):
            row, col = divmod(i, cols)
            r = Rect(start_x + col * cell_w, start_y + row * cell_h, cell_w - 10, 60)
            self.inputs.append(FormInput(r, lbl, key, default))

        self.btn_rect = Rect(self.rect.centerx - 60, self.rect.bottom - 50, 120, 35)
        self.font = pygame.font.SysFont("Arial", 20, bold=True)

    def resize(self, center_rect: Rect):
        self.rect = center_rect
        cols = 2
        cell_w = (self.rect.width - 40) // cols
        cell_h = 70
        start_x = self.rect.x + 20
        start_y = self.rect.y + 60

        for i, inp in enumerate(self.inputs):
            row, col = divmod(i, cols)
            r = Rect(start_x + col * cell_w, start_y + row * cell_h, cell_w - 10, 60)
            inp.rect_area = r
            inp.rect_input = Rect(r.x, r.y + 20, r.width, 30)

        self.btn_rect = Rect(self.rect.centerx - 60, self.rect.bottom - 50, 120, 35)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self.visible:
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and self.btn_rect.collidepoint(
            event.pos
        ):
            self.submit()
            return True

        for inp in self.inputs:
            if inp.handle_event(event):
                if inp.is_focused:
                    for o in self.inputs:
                        if o != inp:
                            o.is_focused = False
                return True
        return True

    def submit(self):
        try:
            vals = {i.key: i.get_value() for i in self.inputs}
            if any(v <= 0 for v in vals.values()):
                raise ValueError("Values must be > 0")

            map_size = (vals["map_w"], vals["map_h"])
            tile_size = (vals["tile_w"], vals["tile_h"])

            self.editor.tilemap.init_size(tile_size, map_size)
            self.editor.tilemap.initialized = True
            self.editor.post_map_setup()
            self.visible = False

        except ValueError as e:
            self.error_message = str(e)

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return

        pygame.draw.rect(screen, COLOR_BG, self.rect)
        pygame.draw.rect(screen, COLOR_BORDER, self.rect, 1)

        title = self.font.render("Project Setup", True, COLOR_TEXT)
        screen.blit(title, (self.rect.x + 20, self.rect.y + 15))

        for inp in self.inputs:
            inp.draw(screen)

        pygame.draw.rect(screen, COLOR_ACCENT, self.btn_rect)
        btn_txt = self.font.render("Create", True, COLOR_TEXT)
        screen.blit(btn_txt, btn_txt.get_rect(center=self.btn_rect.center))

        if self.error_message:
            err = pygame.font.SysFont("Arial", 12).render(
                self.error_message, True, COLOR_ERROR
            )
            screen.blit(err, (self.rect.x + 20, self.btn_rect.y - 20))
