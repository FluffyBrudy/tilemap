import pygame
import pygame_gui
from pygame_gui.core import ObjectID

from configs.themes import DEFAULT_THEME
from tilemap import Tilemap
from constants import MAIN_PANEL_ID


class GameApp:
    def __init__(self, width=800, height=600, fps=60):
        pygame.init()
        pygame.display.set_caption("Pygame GUI Template")

        self.width = width
        self.height = height
        self.fps = fps

        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()

        self.manager = pygame_gui.UIManager(
            (self.width, self.height), DEFAULT_THEME, enable_live_theme_updates=True
        )
        self.background = pygame_gui.elements.UIPanel(
            relative_rect=(0, 0, self.screen.width, self.screen.height),
            manager=self.manager,
            object_id=ObjectID(object_id=MAIN_PANEL_ID),
        )

        self.tilemap = Tilemap()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            self.manager.process_events(event)
        return True

    def run(self):
        running = True

        while running:
            time_delta = self.clock.tick() / 1000.0

            running = self.handle_events()

            self.tilemap.update(time_delta)
            self.manager.update(time_delta)

            self.tilemap.render(self.screen)
            self.manager.draw_ui(self.screen)
            pygame.display.update()

        pygame.quit()


def main():
    game = GameApp()
    game.run()


if __name__ == "__main__":
    main()
