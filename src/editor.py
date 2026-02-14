import pygame
from typing import Optional, List, Callable, Tuple
from pathlib import Path
from pygame import Rect

from constants import BASE_PATH
from tilemap import Tilemap
from widgets.autotiler import AutotileRuleDesigner
from widgets.filemanager import FileManager
from widgets.mapsetup import MapSetup
from widgets.tile_selector import TileSelector
from widgets.tile_grid import TileGrid
from widgets.layer_selector import LayerSelector
from widgets.ui.fileinput import FilenameInput
from widgets.ui.tileset_type_dialog import TilesetTypeDialog
from widgets.ui.layer_type_dialog import LayerTypeDialog
from widgets.ui.menubar import MenuBar
from widgets.ui.toolbar import Toolbar


class Editor:
    def __init__(self, size: Optional[Tuple[int, int]] = None, fps=60):
        pygame.init()
        pygame.display.set_caption("Pure Pygame Editor")

        self.fps = fps
        self.running = False
        self.pan_mode = False

        if isinstance(size, tuple) and len(size) == 2:
            self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        else:
            self.screen = pygame.display.set_mode()
        
        width, height = self.screen.get_size()
        self.width, self.height = width, height

        self.clock = pygame.time.Clock()

        self.tilemap = Tilemap(self)

        self.selector_w = 300
        self.tileset_h = 300
        self.layer_h = 150
        self.map_setup_widget: Optional[MapSetup] = None
        self.tileset_widget: Optional[TileSelector] = None
        self.layer_widget: Optional[LayerSelector] = None
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
        self.tileset_type_dialog = TilesetTypeDialog(editor_rect)
        self.layer_type_dialog = LayerTypeDialog(editor_rect)

        self.menubar = MenuBar(self, self.width, 30)
        self.toolbar = Toolbar(self, 0, 30, self.width, 35)

        # Initialize with defaults to avoid immediate prompt
        # Use a dynamic initial map size if preferred, otherwise stick to 50x50
        self.tilemap.init_size((32, 32), (50, 50))
        
        # Explicit initialization of widgets
        menu_h = 30
        self.tileset_widget = TileSelector(
            self, self.width - self.selector_w, menu_h, self.selector_w, self.tileset_h
        )
        self.layer_widget = LayerSelector(
            self,
            self.width - self.selector_w,
            menu_h + self.tileset_h,
            self.selector_w,
            self.layer_h,
        )
        self.tile_grid_widget = TileGrid(
            self, Rect(0, menu_h, self.width - self.selector_w, self.height - menu_h - 25)
        )

        self.post_map_setup()
        
        # Create map setup widget but keep it hidden
        center_x = (self.width - 400) // 2
        center_y = (self.height - 400) // 2
        self.map_setup_widget = MapSetup(self, Rect(center_x, center_y, 400, 400))
        self.map_setup_widget.visible = False

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
            # First initialize widgets with default or current map settings
            self.post_map_setup()
            # Then load the map data (this will also apply view state to the widgets)
            self.tilemap.load_map(path)
        except Exception as e:
            print(f"Error loading map: {e}")

    def post_map_setup(self):
        self.handle_resize(self.width, self.height)

    def handle_resize(self, width: int, height: int):
        self.width = width
        self.height = height
        menu_h = 30
        toolbar_h = 35

        if hasattr(self, "menubar") and self.menubar:
            self.menubar.resize(width)
            
        if hasattr(self, "toolbar") and self.toolbar:
            self.toolbar.resize(width)

        if hasattr(self, "tileset_widget") and self.tileset_widget:
            self.tileset_widget.resize(
                width - self.selector_w, menu_h + toolbar_h, self.selector_w, self.tileset_h
            )

        if hasattr(self, "layer_widget") and self.layer_widget:
            # Let layer widget take up the remaining vertical space
            layer_y = menu_h + toolbar_h + self.tileset_h
            layer_h = max(100, height - layer_y - 25) # 25 for status bar
            self.layer_widget.resize(
                width - self.selector_w, layer_y, self.selector_w, layer_h
            )

        if hasattr(self, "tile_grid_widget") and self.tile_grid_widget:
            self.tile_grid_widget.rect = Rect(
                0, menu_h + toolbar_h, width - self.selector_w, height - menu_h - toolbar_h - 25
            )

        # Update modal dialogs
        rect_full = Rect(0, 0, width, height)
        if hasattr(self, "save_input") and self.save_input:
            self.save_input.editor_rect = rect_full
        if hasattr(self, "tileset_type_dialog") and self.tileset_type_dialog:
            self.tileset_type_dialog.editor_rect = rect_full
        if hasattr(self, "layer_type_dialog") and self.layer_type_dialog:
            self.layer_type_dialog.editor_rect = rect_full

        if hasattr(self, "map_setup_widget") and self.map_setup_widget:
            center_x = (width - 400) // 2
            center_y = (height - 400) // 2
            self.map_setup_widget.resize(Rect(center_x, center_y, 400, 400))

    def open_map_setup(self):
        self.map_setup_widget.visible = True

    def toggle_autotiler(self):
        if self.autotiler.visible:
            self.autotiler.hide()
        else:
            self.autotiler.show()

    def undo(self):
        self.tilemap.undo()

    def redo(self):
        self.tilemap.redo()

    def toggle_grid(self):
        if self.tile_grid_widget:
            self.tile_grid_widget.show_grid = not self.tile_grid_widget.show_grid

    def launch_external_automap(self):
        if hasattr(self.autotiler, "_launch_external_viewer"):
            self.autotiler._launch_external_viewer()

    def autotile_active(self):
        active_layer = self.tilemap.layer_manager.get_active_layer()
        if active_layer and hasattr(self, "autotiler"):
            rules = getattr(self.autotiler, "rules", [])
            active_layer.autotile_layer(rules)
            print(f"Autotiling layer: {active_layer.name}")

    def flood_fill_active(self):
        # Flood fill usually requires a target cell (mouse position)
        print("Flood Fill: Press 'F' while hovering over the target cell in the grid.")

    def exit_editor(self):
        self.running = False

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            if event.type == pygame.VIDEORESIZE:
                self.handle_resize(event.w, event.h)

            # 1. Handle Modal Dialogs first (they block everything else)
            if self.file_manager:
                self.file_manager.handle_event(event)
                continue

            if self.save_input.active:
                self.save_input.handle_event(event)
                continue

            if self.tileset_type_dialog.active:
                self.tileset_type_dialog.handle_event(event)
                continue

            if self.layer_type_dialog.active:
                self.layer_type_dialog.handle_event(event)
                continue

            if self.map_setup_widget and self.map_setup_widget.visible:
                if self.map_setup_widget.handle_event(event):
                    continue

            # 2. Handle Menu Bar (blocks widgets, but we fixed it to not block shortcuts)
            if self.menubar.handle_event(event):
                continue

            # 3. Handle Keyboard Shortcuts (Ctrl+O, Ctrl+S, etc.)
            if event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
                meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)
                shift_held = mods & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT)
                
                if event.key == pygame.K_r and (ctrl_held or meta_held):
                    self.toggle_autotiler()
                    continue
                elif event.key == pygame.K_s and (ctrl_held or meta_held):
                    if shift_held:
                        self.open_save_as_dialog()
                    else:
                        self.perform_quick_save()
                    continue
                elif event.key == pygame.K_z and (ctrl_held or meta_held):
                    if shift_held:
                        self.tilemap.redo()
                    else:
                        self.tilemap.undo()
                    continue
                elif event.key == pygame.K_y and (ctrl_held or meta_held):
                    self.tilemap.redo()
                    continue
                elif event.key == pygame.K_n and (ctrl_held or meta_held):
                    self.open_map_setup()
                    continue
                elif event.key == pygame.K_o and (ctrl_held or meta_held):
                    self.perform_load()
                    continue
                elif event.key == pygame.K_SPACE:
                    self.pan_mode = not self.pan_mode
                    continue
                elif event.key == pygame.K_g:
                    self.toggle_grid()
                    continue
                elif pygame.K_1 <= event.key <= pygame.K_9:
                    idx = event.key - pygame.K_1
                    if idx < self.tilemap.layer_manager.get_layer_count():
                        self.tilemap.layer_manager.set_active_layer(idx)
                    continue

            # 4. Handle Toolbar
            if self.toolbar and self.toolbar.handle_event(event):
                continue

            # 5. Handle Side Panels/Tools
            if self.autotiler.visible:
                if self.autotiler.handle_event(event):
                    continue

            # 5. Handle Main Editor Widgets
            consumed = False
            if self.tileset_widget and self.tileset_widget.handle_event(event):
                consumed = True
            if (
                not consumed
                and self.layer_widget
                and self.layer_widget.handle_event(event)
            ):
                consumed = True
            if not consumed and self.tile_grid_widget:
                self.tile_grid_widget.handle_event(event)

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
            if self.layer_widget:
                self.layer_widget.draw(self.screen)
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
            if self.tileset_type_dialog.active:
                overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                self.screen.blit(overlay, (0, 0))
                self.tileset_type_dialog.draw(self.screen)
            if self.layer_type_dialog.active:
                overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                self.screen.blit(overlay, (0, 0))
                self.layer_type_dialog.draw(self.screen)

            self.menubar.draw(self.screen)
            if self.toolbar:
                self.toolbar.draw(self.screen)

            pygame.display.update()
            self.clock.tick(self.fps)

        pygame.quit()


if __name__ == "__main__":
    editor = Editor()
    editor.run()
