import pygame
from typing import Optional, List, Callable
from pathlib import Path
from pygame import Rect

from event_map import EventMap
from tilemap import Tilemap
from widgets.filemanager import FileManager
from widgets.mapsetup import MapSetup
from widgets.tile_selector import TileSelector
from widgets.tile_grid import TileGrid


class Editor:
    def __init__(self, width=1280, height=720, fps=60):
        pygame.init()
        pygame.display.set_caption("Pure Pygame Editor")

        self.width = width
        self.height = height
        self.fps = fps
        self.running = False

        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()

        self.tilemap = Tilemap(self)
        self.event_map = EventMap(self)

        self.map_setup_widget: Optional[MapSetup] = None
        self.tileset_widget: Optional[TileSelector] = None
        self.tile_grid_widget: Optional[TileGrid] = None

        self.file_manager: Optional[FileManager] = None

        center_x = (self.width - 400) // 2
        center_y = (self.height - 400) // 2
        self.map_setup_widget = MapSetup(self, Rect(center_x, center_y, 400, 400))

    def open_file_manager(
        self,
        on_select: Callable[[Path], None],
        initial_dir: Optional[Path] = None,
        allowed_exts: List[str] = [".png", ".jpg", ".json"],
    ):
        w, h = 600, 400
        rect = Rect((self.width - w) // 2, (self.height - h) // 2, w, h)

        self.file_manager = FileManager(
            rect=rect,
            initial_dir=initial_dir if initial_dir else Path.cwd(),
            allowed_exts=allowed_exts,
            on_select=lambda p: self._internal_file_select(p, on_select),
            on_cancel=self.close_file_manager,
        )

    def _internal_file_select(self, path: Path, user_callback):
        self.close_file_manager()
        user_callback(path)

    def close_file_manager(self):
        self.file_manager = None

    def post_map_setup(self):
        self.map_setup_widget = None

        selector_w = 300
        self.tileset_widget = TileSelector(
            self, self.width - selector_w, 0, selector_w, self.height
        )
        self.tile_grid_widget = TileGrid(
            self, Rect(0, 0, self.width - selector_w, self.height)
        )

    def handle_events(self):
        for event in pygame.event.get():
            handler = self.event_map.get_event(
                (event.type, getattr(event, "key", None))
            )
            if handler:
                handler(event)
                if not self.running:
                    return

            consumed = False

            if self.file_manager:
                self.file_manager.handle_event(event)
                consumed = True

            if not consumed and self.map_setup_widget and self.map_setup_widget.visible:
                self.map_setup_widget.handle_event(event)
                consumed = True

            if not consumed and self.tileset_widget:
                if self.tileset_widget.handle_event(event):
                    consumed = True

            if not consumed and self.tile_grid_widget:
                self.tile_grid_widget.handle_event(event)

    def run(self):
        self.running = True
        while self.running:
            time_delta = self.clock.tick(self.fps) / 1000.0

            self.handle_events()
            self.tilemap.update(time_delta)
            if self.tile_grid_widget:
                self.tile_grid_widget.update()

            self.screen.fill((30, 30, 30))

            if self.tile_grid_widget:
                self.tile_grid_widget.draw(self.screen)
            elif self.tilemap.initialized:
                self.tilemap.render(self.screen, offset=(0, 0))

            if self.tileset_widget:
                self.tileset_widget.draw(self.screen)

            if (
                self.map_setup_widget and self.map_setup_widget.visible
            ) or self.file_manager:
                overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                self.screen.blit(overlay, (0, 0))

                if self.map_setup_widget and self.map_setup_widget.visible:
                    self.map_setup_widget.draw(self.screen)

                if self.file_manager:
                    self.file_manager.draw(self.screen)
            if self.tileset_widget:
                self.tileset_widget.draw(self.screen)
            pygame.display.update()

        pygame.quit()


if __name__ == "__main__":
    editor = Editor()
    editor.run()
