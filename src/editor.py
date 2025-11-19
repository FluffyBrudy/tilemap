import pygame
import pygame_gui
from pygame_gui.core import ObjectID

from configs.themes import DEFAULT_THEME
from event_map import EventMap
from tilemap import Tilemap
from constants import MAIN_PANEL_ID
from widgets.mapsetup import MapSetup


class Editor:
    def __init__(self, width=1920, height=1080, fps=60):
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

        MapSetup(self, (0, 0, 500, 524))

        self.tilemap = Tilemap()
        self.event_map = EventMap(self)

        self.scroll_direction = {
            "up": False,
            "down": False,
            "left": False,
            "right": False,
        }
        self.map_scroll = pygame.Vector2(0, 0)

    def handle_events(self):
        for event in pygame.event.get():
            self.manager.process_events(event)
            # fmt: off
            event_key_or_btn = getattr(event, "key", None) or \
                               getattr(event, "button", None)
            # fmt: on
            handler = self.event_map.get_event((event.type, event_key_or_btn))
            if handler is not None:
                handler(event)

    def run(self):
        self.running = True

        while self.running:
            time_delta = self.clock.tick() / 1000.0

            self.handle_events()
            self.tilemap.update(time_delta)
            self.manager.update(time_delta)

            self.tilemap.render(self.screen)
            self.manager.draw_ui(self.screen)
            pygame.display.update()

        pygame.quit()


def main():
    game = Editor()
    game.run()


if __name__ == "__main__":
    main()
