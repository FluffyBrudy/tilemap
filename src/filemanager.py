import pygame
import pygame_gui
from pathlib import Path
from typing import Optional

pygame.init()


class PygameFileManager:
    _instance = None

    @staticmethod
    def get_instance():
        if PygameFileManager._instance is None:
            PygameFileManager._instance = PygameFileManager()
        return PygameFileManager._instance

    def __init__(self):
        if PygameFileManager._instance is not None:
            raise Exception("Singleton already exists")

        self.WIDTH, self.HEIGHT = 800, 600
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Select a file")
        self.clock = pygame.time.Clock()

        self.manager = pygame_gui.UIManager((self.WIDTH, self.HEIGHT))

        self.running = True
        self.selected_file: Optional[Path] = None
        self.current_path = Path.cwd()
        self.items: list[Path] = []

        self.container = pygame_gui.elements.UIPanel(
            relative_rect=pygame.Rect(0, 40, self.WIDTH, self.HEIGHT - 40),
            starting_height=1,
            manager=self.manager,
        )

        self.scroll_bar = pygame_gui.elements.UIVerticalScrollBar(
            relative_rect=pygame.Rect(self.WIDTH - 20, 0, 20, self.HEIGHT - 40),
            visible_percentage=1.0,
            manager=self.manager,
            container=self.container,
        )

        self.item_buttons = []

        self.font = pygame.font.SysFont("consolas", 20)

    def list_dir(self):
        self.items = []
        if self.current_path.parent != self.current_path:
            self.items.append(self.current_path.parent)

        self.items += sorted(
            [
                p
                for p in self.current_path.iterdir()
                if not p.name.startswith(".")
                and (p.is_dir() or p.suffix.lower() in (".json",))
            ]
        )

    def create_buttons(self):
        for btn in self.item_buttons:
            btn.kill()
        self.item_buttons.clear()

        y_offset = 0
        for i, item in enumerate(self.items):
            if i == 0 and self.current_path.parent != self.current_path:
                text = "[← BACK]"
            else:
                text = "[DIR] " + item.name if item.is_dir() else "[FILE] " + item.name

            btn = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect(0, y_offset, self.WIDTH - 40, 30),
                text=text,
                manager=self.manager,
                container=self.container,
                object_id=pygame_gui.core.ObjectID(class_id="@file_button"),
            )
            btn.path = item
            self.item_buttons.append(btn)
            y_offset += 35

        content_height = max(y_offset, self.container.get_relative_rect().height)
        visible_height = self.container.get_relative_rect().height

        self.scroll_bar.rebuild()

    def run(self) -> Optional[Path]:
        self.list_dir()
        self.create_buttons()

        while self.running:
            time_delta = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                if event.type == pygame_gui.UI_BUTTON_PRESSED:
                    for btn in self.item_buttons:
                        if event.ui_element == btn:
                            clicked = btn.path
                            if btn.text == "[← BACK]":
                                self.current_path = clicked
                                self.list_dir()
                                self.create_buttons()
                            elif clicked.is_dir():
                                self.current_path = clicked
                                self.list_dir()
                                self.create_buttons()
                            else:
                                self.selected_file = clicked
                                self.running = False
                self.manager.process_events(event)

            self.container.set_relative_position((0, -self.scroll_bar.scroll_position))

            self.manager.update(time_delta)
            self.screen.fill((30, 30, 30))
            path_surface = self.font.render(
                str(self.current_path), True, (200, 200, 200)
            )
            self.screen.blit(path_surface, (10, 10))
            self.manager.draw_ui(self.screen)

            pygame.display.update()

        pygame.display.quit()
        return self.selected_file


if __name__ == "__main__":
    file_manager = PygameFileManager.get_instance()
    file_path = file_manager.run()
    if file_path:
        print("Selected file:", file_path)
    else:
        print("No file selected")
