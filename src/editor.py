import pygame
from typing import Optional, List, Callable
from pathlib import Path
from pygame import Rect

from constants import BASE_PATH
from tilemap import Tilemap
from widgets.autotiler import AutotileRuleDesigner
from widgets.filemanager import FileManager
from widgets.mapsetup import MapSetup
from widgets.tile_selector import TileSelector
from widgets.tile_grid import TileGrid
from widgets.ui.fileinput import FilenameInput


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

        self.selector_w = 300
        self.map_setup_widget: Optional[MapSetup] = None
        self.tileset_widget: Optional[TileSelector] = None
        self.tile_grid_widget: Optional[TileGrid] = None

        self.file_manager: Optional[FileManager] = None
        self.autotiler = AutotileRuleDesigner(self, 100, 100)

        editor_rect = self.screen.get_rect()
        editor_rect.center = ((width - 300) // 2, height // 2)
        self.save_input = FilenameInput(
            editor_rect=editor_rect,
            on_confirm=self.do_save_as,
            on_cancel=lambda: None,
        )

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

    def perform_quick_save(self):
        if not self.tile_grid_widget:
            return
        if self.tilemap.active_project_path:
            try:
                self.tilemap.save_map()
            except Exception as e:
                print(f"Error saving: {e}")
        else:
            self.open_save_as_dialog()

    def open_save_as_dialog(self):
        if not self.tile_grid_widget:
            return
        self.save_input.show()

    def do_save_as(self, filename: str):
        try:
            self.tilemap.save_map(filename)
        except Exception as e:
            print(f"Error saving map: {e}")

    def perform_load(self):
        self.open_file_manager(
            on_select=self.on_map_file_selected,
            initial_dir=BASE_PATH / "data",
            allowed_exts=[".json"],
        )

    def on_map_file_selected(self, path: Path):
        try:
            self.tilemap.load_map(path)
            if self.map_setup_widget:
                self.post_map_setup()
        except Exception as e:
            print(f"Error loading map: {e}")

    def post_map_setup(self):
        self.map_setup_widget = None
        self.tileset_widget = TileSelector(
            self, self.width - self.selector_w, 0, self.selector_w, self.height
        )
        self.tile_grid_widget = TileGrid(
            self, Rect(0, 0, self.width - self.selector_w, self.height)
        )

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if self.file_manager:
                self.file_manager.handle_event(event)
                continue

            if self.save_input.active:
                self.save_input.handle_event(event)
                continue

            if self.autotiler.visible:
                if self.autotiler.handle_event(event):
                    continue

            if self.map_setup_widget:
                self.map_setup_widget.handle_event(event)
            else:
                consumed = False
                if self.tileset_widget and self.tileset_widget.handle_event(event):
                    consumed = True
                if not consumed and self.tile_grid_widget:
                    self.tile_grid_widget.handle_event(event)

            if event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                if event.key == pygame.K_r:
                    if self.autotiler.visible:
                        self.autotiler.hide()
                    else:
                        self.autotiler.show()
                elif event.key == pygame.K_s and (mods & pygame.KMOD_LCTRL):
                    if mods & pygame.KMOD_LSHIFT:
                        self.open_save_as_dialog()
                    else:
                        self.perform_quick_save()
                elif event.key == pygame.K_o and (mods & pygame.KMOD_LCTRL):
                    self.perform_load()

    def run(self):
        self.running = True
        while self.running:
            self.handle_events()
            if self.tile_grid_widget:
                self.tile_grid_widget.update()

            self.screen.fill((30, 30, 30))

            if self.tile_grid_widget:
                self.tile_grid_widget.draw(self.screen)
            if self.tileset_widget:
                self.tileset_widget.draw(self.screen)
            if self.autotiler:
                self.autotiler.draw(self.screen)
            if self.map_setup_widget and self.map_setup_widget.visible:
                overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                self.screen.blit(overlay, (0, 0))
                self.map_setup_widget.draw(self.screen)
            if self.file_manager:
                overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                self.screen.blit(overlay, (0, 0))
                self.file_manager.draw(self.screen)
            if self.save_input.active:
                self.save_input.draw(self.screen)

            pygame.display.update()
            self.clock.tick(self.fps)

        pygame.quit()


if __name__ == "__main__":
    editor = Editor()
    editor.run()
