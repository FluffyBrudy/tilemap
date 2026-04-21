import pygame
import threading
import queue
import logging
import sys
import subprocess
import json
from typing import Optional, List, Callable, Tuple, Dict, Any
from pathlib import Path
from pygame import Rect
from typing import TYPE_CHECKING

from constants import BASE_PATH
from tilemap import Tilemap
from widgets.autotiler import AutotileRuleDesigner
from widgets.regex_automap_designer import RegexAutomapDesigner
from widgets.mapsetup import MapSetup
from widgets.tile_selector import TileSelector
from widgets.tile_grid import TileGrid
from widgets.layer_selector import LayerSelector
from widgets.ui.fileinput import FilenameInput
from widgets.ui.tileset_type_dialog import TilesetTypeDialog
from widgets.ui.layer_type_dialog import LayerTypeDialog
from widgets.ui.menubar import MenuBar
from widgets.ui.toolbar import Toolbar
from widgets.ui.notification import NotificationManager
from widgets.ui.property_editor import PropertyEditor
from widgets.ui.tooltip import TooltipManager
from widgets.ui.error_console import ErrorConsole
from utils.log_capture import setup_console_log
from utils.standalone import launch_standalone
from utils import error_handler, error_context

if TYPE_CHECKING:
    from plugins.sprite_animation import SpriteAnimationEditor


def setup_error_logging():
    """Setup logging to capture all errors to log file."""
    log_dir = BASE_PATH / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "errors.log"

    logging.basicConfig(
        level=logging.ERROR,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
    )

    def exception_handler(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.error(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = exception_handler

    return logging.getLogger(__name__)


logger = setup_error_logging()


# Backwards-compatible alias for existing editor.py call sites
_launch_standalone_module = launch_standalone


class Editor:
    def __init__(self, size: Optional[Tuple[int, int]] = None, fps=60):
        pygame.init()
        pygame.display.set_caption("Pure Pygame Editor")

        self.fps = fps
        self.running = False
        self.pan_mode = False
        self.autotile_mode = False

        if isinstance(size, tuple) and len(size) == 2:
            self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        else:
            self.screen = pygame.display.set_mode()

        width, height = self.screen.get_size()
        self.width, self.height = width, height

        self.clock = pygame.time.Clock()

        self.tilemap = Tilemap(self)

        self.selector_w = 300
        self.left_panel_w = 380  # Width for the dockable left sidebar
        self.tileset_h = 300
        self.layer_h = 150
        self.map_setup_widget: Optional[MapSetup] = None
        self.tileset_widget: Optional[TileSelector] = None
        self.layer_widget: Optional[LayerSelector] = None
        self.tile_grid_widget: Optional[TileGrid] = None

        # Dockable left sidebar (animation panel)
        self.left_panel_visible = False
        self.animation_panel: Optional["SpriteAnimationEditor"] = None
        self._animation_panel_surface: Optional[pygame.Surface] = None

        self.autotiler = AutotileRuleDesigner(self, 100, 100)
        self.regex_automap_designer = RegexAutomapDesigner(self, 150, 100)
        self.notifications = NotificationManager(self)
        self.tooltip = TooltipManager()
        self.error_console = ErrorConsole(Rect(0, 0, self.width, self.height))
        # Register console with error handler for real-time updates
        error_handler.register_console(self.error_console)
        self.property_editor: Optional[PropertyEditor] = None

        self.child_processes: List[subprocess.Popen] = []
        self.file_manager_process: Optional[subprocess.Popen] = None
        self._file_manager_callbacks: Dict[str, Any] = {}

        self.loading_state = {
            "active": False,
            "message": "",
            "error": None,
            "path": None,
        }
        self._load_queue: "queue.Queue" = queue.Queue()

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

        self.tilemap.init_size((32, 32), (50, 50))

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
            self,
            Rect(0, menu_h, self.width - self.selector_w, self.height - menu_h - 25),
        )

        self.post_map_setup()

        center_x = (self.width - 400) // 2
        center_y = (self.height - 400) // 2
        self.map_setup_widget = MapSetup(self, Rect(center_x, center_y, 400, 400))
        self.map_setup_widget.visible = False

    def open_file_manager(
        self,
        on_select: Callable[[Path], None] = lambda p: None,
        initial_dir: Optional[Path] = None,
        allowed_exts: List[str] = [".png", ".jpg", ".json"],
        mode: str = "open",
        on_save: Optional[Callable[[Path], None]] = None,
        default_name: str = "",
        multi_select: bool = False,
    ):
        """Launch file manager as a subprocess."""
        if self.file_manager_process and self.file_manager_process.poll() is None:
            return

        # Build command line arguments
        args = [
            "--mode",
            mode,
        ]

        if initial_dir:
            try:
                rel_path = initial_dir.relative_to(BASE_PATH)
                args.extend(["--initial-dir", str(rel_path)])
            except ValueError:
                # Not relative to BASE_PATH, use absolute
                args.extend(["--initial-dir", str(initial_dir)])
        else:
            args.extend(["--initial-dir", "data"])

        # Add allowed extensions
        if allowed_exts:
            args.extend(["--allowed-exts", ",".join(allowed_exts)])

        # Add default name for save mode
        if default_name:
            args.extend(["--default-name", default_name])

        # Add multi-select flag
        if multi_select:
            args.append("--multi-select")

        try:
            # Launch subprocess via unified launcher (stderr captured, text mode for JSON parsing)
            self.file_manager_process = launch_standalone(
                "standalone_filemanager",
                args,
                cwd=BASE_PATH,
                text=True,
            )

            # Store callbacks for later processing
            self._file_manager_callbacks = {
                "on_select": on_select,
                "on_save": on_save,
                "mode": mode,
            }

            # Track the process
            self.child_processes.append(self.file_manager_process)

            print(
                f"Launched file manager subprocess (PID: {self.file_manager_process.pid})"
            )
        except Exception as e:
            error_handler.capture(e, context="launch_file_manager")
            self.file_manager_process = None

    def _poll_file_manager_result(self):
        """Check if file manager subprocess has completed and process result."""
        if not self.file_manager_process:
            return

        if self.file_manager_process.poll() is not None:
            try:
                stdout, stderr = self.file_manager_process.communicate(timeout=0.1)

                if stdout:
                    lines = [
                        line.strip()
                        for line in stdout.strip().split("\n")
                        if line.strip()
                    ]
                    if lines:
                        result_line = lines[-1]
                        try:
                            result = json.loads(result_line)
                            status = result.get("status")

                            if status == "selected":
                                if "paths" in result:
                                    paths = [Path(p) for p in result["paths"]]
                                    if self._file_manager_callbacks["on_select"]:
                                        self._file_manager_callbacks["on_select"](paths)
                                elif "path" in result:
                                    path = Path(result["path"])
                                    if self._file_manager_callbacks["on_select"]:
                                        self._file_manager_callbacks["on_select"](path)

                            elif status == "saved":
                                path = Path(result["path"])
                                if self._file_manager_callbacks["on_save"]:
                                    self._file_manager_callbacks["on_save"](path)
                                elif self._file_manager_callbacks["on_select"]:
                                    self._file_manager_callbacks["on_select"](path)

                            elif status == "cancelled":
                                print("File manager cancelled")
                        except json.JSONDecodeError as e:
                            error_handler.capture(
                                e, context="parse_file_manager_result"
                            )
                            print(f"Output was: {result_line}")  # Keep for debugging

                if stderr:
                    error_handler.capture(
                        Exception(stderr),
                        context="file_manager_stderr",
                        severity="warning",
                    )

            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                error_handler.capture(e, context="process_file_manager_result")
            finally:
                self.file_manager_process = None
                self._file_manager_callbacks = {}

    def close_file_manager(self):
        """Terminate file manager subprocess if running."""
        if self.file_manager_process and self.file_manager_process.poll() is None:
            try:
                self.file_manager_process.terminate()
                self.file_manager_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.file_manager_process.kill()
            except Exception as e:
                error_handler.capture(e, context="close_file_manager")

        self.file_manager_process = None
        self._file_manager_callbacks = {}

    def perform_quick_save(self):
        if not self.tile_grid_widget:
            return
        if self.tilemap.active_project_path:
            try:
                self.tilemap.save_map()
            except Exception as e:
                error_handler.capture(e, context="save_map")
        else:
            self.open_save_as_dialog()

    def open_save_as_dialog(self):
        if not self.tile_grid_widget:
            return
        default_name = "untitled.json"
        if self.tilemap.active_project_path:
            default_name = self.tilemap.active_project_path.name
        self.open_file_manager(
            initial_dir=BASE_PATH / "data",
            allowed_exts=[".json"],
            mode="save",
            default_name=default_name,
            on_save=self.on_map_save_selected,
        )

    def do_save_as(self, filename: str):
        try:
            self.tilemap.save_map(filename)
        except Exception as e:
            error_handler.capture(e, context="save_map_as")

    def on_map_save_selected(self, path: Path):
        try:
            self.tilemap.save_map(path)
        except Exception as e:
            error_handler.capture(e, context="save_map_selected")

    def perform_load(self):
        self.open_file_manager(
            on_select=self.on_map_file_selected,
            initial_dir=BASE_PATH / "data",
            allowed_exts=[".json"],
        )

    def on_map_file_selected(self, path: Path):
        self.start_async_load_map(path)

    def start_async_load_map(self, path: Path):
        if self.loading_state["active"]:
            return
        self.loading_state["active"] = True
        self.loading_state["message"] = "Loading map..."
        self.loading_state["error"] = None
        self.loading_state["path"] = path

        def _worker(load_path: Path):
            try:
                payload = self.tilemap.read_map_payload(load_path)
                self._load_queue.put(("ok", load_path, payload))
            except Exception as e:
                self._load_queue.put(("error", load_path, e))

        t = threading.Thread(target=_worker, args=(path,), daemon=True)
        t.start()

    def _poll_async_load(self):
        if not self.loading_state["active"]:
            return
        try:
            status, path, payload_or_error = self._load_queue.get_nowait()
        except queue.Empty:
            return

        if status == "error":
            self.loading_state["active"] = False
            self.loading_state["error"] = payload_or_error
            error_handler.capture(
                Exception(payload_or_error), context="load_map_status"
            )
            return

        try:
            self.post_map_setup()
            self.tilemap.apply_map_payload(path, payload_or_error)
        except Exception as e:
            error_handler.capture(e, context="load_map_apply")
        finally:
            self.loading_state["active"] = False

    def post_map_setup(self):
        self.handle_resize(self.width, self.height)

    def handle_resize(self, width: int, height: int):
        self.width = width
        self.height = height

        # Update error console size
        if hasattr(self, "error_console"):
            self.error_console.editor_rect = Rect(0, 0, self.width, self.height)
            self.error_console.width = min(800, self.width - 100)
            self.error_console.height = min(400, self.height - 100)
            self.error_console.x = (self.width - self.error_console.width) // 2
            self.error_console.y = (self.height - self.error_console.height) // 2
            self.error_console._update_rects()

        menu_h = 30
        toolbar_h = 35

        # Left sidebar offset
        left_offset = self.left_panel_w if self.left_panel_visible else 0

        if hasattr(self, "menubar") and self.menubar:
            self.menubar.resize(width)

        if hasattr(self, "toolbar") and self.toolbar:
            self.toolbar.resize(width)

        if hasattr(self, "tileset_widget") and self.tileset_widget:
            self.tileset_widget.resize(
                width - self.selector_w - left_offset,
                menu_h + toolbar_h,
                self.selector_w,
                self.tileset_h,
            )

        if hasattr(self, "layer_widget") and self.layer_widget:
            self.layer_widget.resize(
                width - self.selector_w - left_offset,
                menu_h + toolbar_h + self.tileset_h,
                self.selector_w,
                height - (menu_h + toolbar_h + self.tileset_h),
            )

        if hasattr(self, "tile_grid_widget") and self.tile_grid_widget:
            self.tile_grid_widget.rect = Rect(
                left_offset,
                menu_h + toolbar_h,
                width - self.selector_w - left_offset,
                height - (menu_h + toolbar_h),
            )

        # Update animation panel rect
        if self.left_panel_visible and self.animation_panel:
            panel_rect = Rect(
                0, menu_h + toolbar_h, self.left_panel_w, height - (menu_h + toolbar_h)
            )
            if hasattr(self.animation_panel, "rect"):
                self.animation_panel.rect = panel_rect
                if hasattr(self.animation_panel, "_relayout"):
                    self.animation_panel._relayout()

        rect_full = Rect(0, 0, width, height)

        if hasattr(self, "tileset_type_dialog") and self.tileset_type_dialog:
            self.tileset_type_dialog.editor_rect = rect_full
        if hasattr(self, "layer_type_dialog") and self.layer_type_dialog:
            self.layer_type_dialog.editor_rect = rect_full

        if hasattr(self, "map_setup_widget") and self.map_setup_widget:
            center_x = (width - 400) // 2
            center_y = (height - 400) // 2
            self.map_setup_widget.resize(Rect(center_x, center_y, 400, 400))

    def toggle_auto_autotile(self):
        self.autotile_mode = not self.autotile_mode
        status = "Enabled" if self.autotile_mode else "Disabled"
        self.notifications.notify(f"Autotile Mode {status}")
        self.menubar._layout_menus()

    def open_map_setup(self):
        if self.map_setup_widget is None:
            logger.warning({"msg": "map_setup_widget is not initialized"})
            return
        self.map_setup_widget.visible = True

    def toggle_autotiler(self):
        if self.autotiler.visible:
            self.autotiler.hide()
        else:
            self.autotiler.show()

    def toggle_regex_automap(self):
        if self.regex_automap_designer.visible:
            self.regex_automap_designer.hide()
        else:
            self.regex_automap_designer.show()

    def toggle_animation_panel(self):
        """Toggle the dockable animation panel visibility (Cmd/Ctrl+B)."""
        if not self.left_panel_visible:
            # Lazy-initialize the animation panel on first toggle
            if self.animation_panel is None:
                self._init_animation_panel()
            if self.animation_panel is not None:
                self.left_panel_visible = True

    def _init_animation_panel(self):
        """Initialize the animation panel without loading any tileset."""
        from plugins.sprite_animation.editor import SpriteAnimationEditor

        try:
            # Create a simple consumer adapter that logs animation changes
            class _PanelConsumer:
                editor_instance = self

                def on_animation_saved(self, name: str, data: dict) -> None:
                    self.editor_instance.notifications.notify(
                        f"Animation saved: {name}"
                    )

                def on_animation_deleted(self, name: str) -> None:
                    self.editor_instance.notifications.notify(
                        f"Animation deleted: {name}"
                    )

            consumer = _PanelConsumer()

            # Create panel rect (will be set by handle_resize)
            panel_rect = Rect(0, 65, self.left_panel_w, self.height - 65)

            # Create animation editor without any surface - user will load spritesheet via "Sheet" button
            self.animation_panel = SpriteAnimationEditor(
                panel_rect,
                surface=None,  # No surface - user must load spritesheet
                tile_size=(32, 32),  # Default tile size
                consumer=consumer,
            )
        except Exception as e:
            error_handler.capture(e, context="init_animation_panel")
            self.notifications.notify(f"Failed to init animation panel: {e}")

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

    def _active_tileset_image_path(self) -> Optional[Path]:
        """Filesystem path of the tileset image to use for the animation editor."""
        tw = self.tileset_widget
        if not tw or not tw.tilesets:
            return None

        candidates: List[Path] = []
        if 0 <= tw.active_idx < len(tw.tilesets):
            candidates.append(tw.tilesets[tw.active_idx].path)
        candidates.append(tw.tilesets[0].path)

        seen: set = set()
        for p in candidates:
            if p is None or p in seen:
                continue
            seen.add(p)
            try:
                rp = Path(p).resolve()
                if rp.exists():
                    return rp
            except (OSError, TypeError, ValueError):
                continue
        return None

    def launch_animation_editor(self):
        """Launch the sprite animation editor in a new window.

        Uses the active tileset image when one is loaded so the editor opens
        immediately. If no tileset is selected, a file picker asks for a sheet.
        """
        sheet = self._active_tileset_image_path()
        if sheet is not None:
            self._launch_animation_editor_with_image(sheet)
            return

        self.open_file_manager(
            on_select=self._launch_animation_editor_with_image,
            initial_dir=BASE_PATH / "data",
            allowed_exts=[".png", ".jpg", ".jpeg"],
            mode="open",
        )

    def _launch_animation_editor_with_image(self, path: Path):
        """Launch animation editor subprocess with selected image."""
        try:
            tile_size = "32x32"
            if hasattr(self.tilemap, "tile_size") and self.tilemap.tile_size:
                tw, th = self.tilemap.tile_size
                tile_size = f"{tw}x{th}"

            args = [str(path), "--tile-size", tile_size]
            process = launch_standalone(
                "plugins.sprite_animation.standalone",
                args,
                cwd=BASE_PATH,
                text=True,
            )
            self.child_processes.append(process)

            print(
                f"Launched animation editor with: {path.name} (tile size: {tile_size})"
            )
        except Exception as e:
            error_handler.capture(e, context="launch_animation_editor")

    def autotile_active(self):
        active_layer = self.tilemap.layer_manager.get_active_layer()
        if active_layer and hasattr(self, "autotiler"):
            rules = getattr(self.autotiler, "rules", [])
            active_layer.autotile_layer(rules)
            print(f"Autotiling layer: {active_layer.name}")

    def flood_fill_active(self):

        print("Flood Fill: Press 'F' while hovering over the target cell in the grid.")

    def exit_editor(self):
        """Clean up and exit the editor."""

        self._cleanup_child_processes()
        self.running = False

    def _cleanup_child_processes(self):
        """Terminate all child processes before exiting."""
        for process in self.child_processes:
            if process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                except Exception as e:
                    error_handler.capture(e, context="terminate_child_process")

        self.child_processes.clear()

    def _cleanup_finished_processes(self):
        """Remove finished processes from the tracking list."""
        self.child_processes = [p for p in self.child_processes if p.poll() is None]

    def handle_events(self):
        for event in pygame.event.get():
            # Handle error console events first (it has priority for Ctrl+`)
            if self.error_console.handle_event(event):
                continue

            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.VIDEORESIZE:
                self.handle_resize(event.w, event.h)

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

            if self.property_editor and self.property_editor.active:
                if self.property_editor.handle_event(event):
                    continue

            if self.menubar.handle_event(event):
                continue

            if event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
                meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)
                shift_held = mods & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT)

                if event.key == pygame.K_r and (ctrl_held or meta_held):
                    self.toggle_autotiler()
                    continue
                elif event.key == pygame.K_m and (ctrl_held or meta_held):
                    self.toggle_regex_automap()
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
                elif event.mod & pygame.KMOD_CTRL and event.key == pygame.K_g:
                    self.toggle_grid()
                    continue
                elif event.key == pygame.K_b and (ctrl_held or meta_held):
                    self.toggle_animation_panel()
                    continue
                elif pygame.K_1 <= event.key <= pygame.K_9:
                    idx = event.key - pygame.K_1
                    if idx < self.tilemap.layer_manager.get_layer_count():
                        self.tilemap.layer_manager.set_active_layer(idx)
                    continue

            if self.toolbar and self.toolbar.handle_event(event):
                continue

            if self.autotiler.visible:
                if self.autotiler.handle_event(event):
                    continue

            if self.regex_automap_designer.visible:
                if self.regex_automap_designer.handle_event(event):
                    continue

            # Route events to the dockable animation panel
            if self.left_panel_visible and self.animation_panel:
                if hasattr(self.animation_panel, "handle_event"):
                    if self.animation_panel.handle_event(event):
                        continue

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
        frame_count = 0
        while self.running:
            self._poll_async_load()
            self._poll_file_manager_result()

            frame_count += 1
            if frame_count % 60 == 0:
                self._cleanup_finished_processes()

            self.handle_events()
            if self.tile_grid_widget:
                self.tile_grid_widget.update()

            # Update animation panel
            if self.left_panel_visible and self.animation_panel:
                if hasattr(self.animation_panel, "update"):
                    self.animation_panel.update()

            self.screen.fill((30, 30, 30))
            self.tooltip.hide()

            if self.tile_grid_widget:
                self.tile_grid_widget.draw(self.screen)
            if self.tileset_widget:
                self.tileset_widget.draw(self.screen)
            if self.layer_widget:
                self.layer_widget.draw(self.screen)
            if self.autotiler:
                self.autotiler.draw(self.screen)
            if self.regex_automap_designer:
                self.regex_automap_designer.draw(self.screen)

            # Draw the dockable animation panel
            if self.left_panel_visible and self.animation_panel:
                # Draw panel background
                panel_surf = pygame.Surface(
                    (self.left_panel_w, self.height), pygame.SRCALPHA
                )
                panel_surf.fill((28, 30, 34, 255))
                self.screen.blit(panel_surf, (0, 65))
                # Draw panel border
                pygame.draw.rect(
                    self.screen,
                    (60, 62, 65),
                    Rect(0, 65, self.left_panel_w, self.height - 65),
                    1,
                )
                if hasattr(self.animation_panel, "draw"):
                    self.animation_panel.draw(self.screen)

            self.notifications.draw(self.screen)

            if self.map_setup_widget and self.map_setup_widget.visible:
                overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                self.screen.blit(overlay, (0, 0))
                self.map_setup_widget.draw(self.screen)

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

            if self.property_editor and self.property_editor.active:
                self.property_editor.draw(self.screen)
            if self.loading_state["active"]:
                overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 180))
                self.screen.blit(overlay, (0, 0))

                msg = self.loading_state.get("message", "Loading...")
                font = pygame.font.SysFont("Arial", 18, bold=True)
                text = font.render(msg, True, (230, 230, 230))
                text_rect = text.get_rect(center=(self.width // 2, self.height // 2))
                self.screen.blit(text, text_rect)

                dot_font = pygame.font.SysFont("Arial", 16)
                dots = "." * ((pygame.time.get_ticks() // 400) % 4)
                dot_surf = dot_font.render(dots, True, (180, 180, 180))
                dot_rect = dot_surf.get_rect(
                    center=(self.width // 2, self.height // 2 + 30)
                )
                self.screen.blit(dot_surf, dot_rect)

            if self.toolbar:
                self.toolbar.draw(self.screen)
            self.menubar.draw(self.screen)
            self.tooltip.draw(self.screen)
            self.error_console.draw(self.screen)

            pygame.display.update()
            self.clock.tick(self.fps)

        self._cleanup_child_processes()
        pygame.quit()


if __name__ == "__main__":
    # Global exception handler for direct execution
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        error_handler.capture(exc_value, context="editor_main_exception")
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    try:
        log_path = setup_console_log(BASE_PATH)
        if log_path:
            print(f"Logging to {log_path}")

        with error_context("editor_main"):
            editor = Editor(size=(1500, 900))
            editor.run()
    except KeyboardInterrupt:
        print("\nEditor interrupted by user")
    except Exception as e:
        error_handler.capture(e, context="editor_main")
        print(f"Failed to start editor: {e}")
        sys.exit(1)
