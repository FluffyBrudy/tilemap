import os
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
from utils.font_manager import font_manager, FontWeight, FontStyle

# Fix HiDPI/Retina blur on macOS
if sys.platform == "darwin":
    os.environ.setdefault("SDL_VIDEO_MAC_SCREEN_SCALE", "1")

from constants import BASE_PATH
from tilemap import Tilemap
from widgets.autotiler import AutotileRuleDesigner
from widgets.regex_automap_designer import RegexAutomapDesigner
from widgets.mapsetup import MapSetup
from widgets.map_properties import MapPropertiesDialog
from widgets.tile_selector import TileSelector
from widgets.tile_grid import TileGrid
from widgets.layer_selector import LayerSelector
from widgets.ui.fileinput import FilenameInput
from widgets.ui.tileset_type_dialog import TilesetTypeDialog
from widgets.ui.confirm_dialog import ConfirmDialog
from widgets.ui.layer_type_dialog import LayerTypeDialog
from widgets.ui.menubar import MenuBar
from widgets.ui.toolbar import Toolbar
from widgets.ui.node_selector import NodeSelector
from widgets.ui.node_editor import NodeEditor
from widgets.ui.notification import NotificationManager
from widgets.ui.property_editor import PropertyEditor
from widgets.ui.tooltip import TooltipManager
from widgets.ui.theme import get_theme_manager, set_theme, THEMES
from utils.log_capture import setup_console_log
from utils.standalone import launch_standalone
from utils import error_handler, error_context
from node_manager import NodeManager

if TYPE_CHECKING:
    from plugins.sprite_animation import SpriteAnimationEditor
    from plugins.sprite_editor import SpriteEditor


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


def _load_project_config() -> tuple[Path, Path, dict]:
    """Load and validate settings.json from current working directory.

    Returns:
        Tuple of (base_path, data_root, config)

    Raises:
        RuntimeError: If settings.json is invalid or missing
    """
    settings_file = Path.cwd() / "settings.json"

    if not settings_file.exists():
        raise RuntimeError(
            "settings.json not found. Run 'tilemap-editor init' first."
        )

    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid settings.json: {e}")

    # Validate required fields
    required_fields = ["base_path", "data_path", "error_handler"]
    for field in required_fields:
        if field not in config:
            raise RuntimeError(f"Invalid settings.json: missing '{field}'")

    base_path = Path(config["base_path"]).expanduser()

    if not base_path.is_absolute():
        raise RuntimeError("base_path must be absolute")

    base_path = base_path.resolve()

    venv_path = Path(sys.prefix).resolve()
    if venv_path in base_path.parents:
        raise RuntimeError("base_path cannot be inside virtual environment")

    # Validate data_path is relative, not absolute
    data_path = config["data_path"]
    if Path(data_path).is_absolute():
        raise RuntimeError("data_path must be relative, not absolute")

    data_root = base_path / data_path

    if not data_root.exists():
        raise RuntimeError(f"Data directory not found: {data_root}. Run 'tilemap-editor init' to create the project structure.")

    # Initialize error_handler with proper paths
    log_root = data_root / "logs"

    # Create logs directory only, don't create data root
    log_root.mkdir(parents=True, exist_ok=True)

    from utils.error_handler import init_error_handler
    init_error_handler(log_root=log_root, config=config["error_handler"])

    return base_path, data_root, config


# Backwards-compatible alias for existing editor.py call sites
_launch_standalone_module = launch_standalone


class Editor:
    def __init__(self, size: Optional[Tuple[int, int]] = None, fps=60):
        self.base_path, self.data_root, self.config = _load_project_config()
        logger.info(f"Project base_path: {self.base_path}")
        logger.info(f"Data root: {self.data_root}")

        pygame.init()
        pygame.display.set_caption("Pure Pygame Editor")

        self.fps = fps
        self.running = False
        self.pan_mode = False
        self.autotile_mode = False
        self.eraser_mode = False
        self.select_mode = False
        self.node_editing_mode = False
        self._prev_tool = None

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
        self.map_properties_dialog: Optional[MapPropertiesDialog] = None
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
        self.error_console_process: Optional[subprocess.Popen] = None
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
        self.confirm_dialog = ConfirmDialog(editor_rect)
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
        self.map_properties_dialog = MapPropertiesDialog(self, Rect(center_x, center_y, 400, 260))
        self.node_manager = NodeManager(self)
        self.node_selector = NodeSelector(self, 0, 65, 260, 240)
        self.node_editor = NodeEditor(self, 0, 310, 260, 190)

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
            # Ensure directory exists before resolving to avoid errors
            if initial_dir.exists():
                args.extend(["--initial-dir", str(initial_dir.resolve())])
            else:
                # Pass as-is if it doesn't exist; StandaloneFileManager will handle the error
                args.extend(["--initial-dir", str(initial_dir)])
        else:
            # Ensure data_root exists before resolving
            if self.data_root.exists():
                args.extend(["--initial-dir", str(self.data_root.resolve())])
            else:
                # Create data_root if it doesn't exist
                self.data_root.mkdir(parents=True, exist_ok=True)
                args.extend(["--initial-dir", str(self.data_root.resolve())])
        
        # Ensure data_root exists before resolving
        if self.data_root.exists():
            args.extend(["--data-root", str(self.data_root.resolve())])
        else:
            # Create data_root if it doesn't exist
            self.data_root.mkdir(parents=True, exist_ok=True)
            args.extend(["--data-root", str(self.data_root.resolve())])

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
                cwd=self.base_path,
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
            initial_dir=self.data_root,
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
            initial_dir=self.data_root,
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
        if hasattr(self, "confirm_dialog") and self.confirm_dialog:
            self.confirm_dialog.editor_rect = rect_full
        if hasattr(self, "layer_type_dialog") and self.layer_type_dialog:
            self.layer_type_dialog.editor_rect = rect_full

        if hasattr(self, "map_setup_widget") and self.map_setup_widget:
            center_x = (width - 400) // 2
            center_y = (height - 400) // 2
            self.map_setup_widget.resize(Rect(center_x, center_y, 400, 400))
            if self.map_properties_dialog:
                self.map_properties_dialog.resize(Rect(center_x, center_y, 400, 260))

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

    def open_map_properties(self):
        if self.map_properties_dialog is None:
            logger.warning({"msg": "map_properties_dialog is not initialized"})
            return
        self.map_properties_dialog.open()

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
        else:
            self.left_panel_visible = False


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
            self.animation_panel._data_root = self.data_root
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

    def cycle_theme(self):
        """Cycle through available themes."""
        theme_names = list(THEMES.keys())
        current = get_theme_manager().name
        current_idx = theme_names.index(current) if current in theme_names else 0
        next_idx = (current_idx + 1) % len(theme_names)
        new_theme = theme_names[next_idx]
        set_theme(new_theme)
        self.notifications.notify(f"Theme: {new_theme}")

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

        Always asks for a spritesheet instead of assuming the active tileset is
        the animation source.
        """
        self.open_file_manager(
            on_select=self._launch_animation_editor_with_image,
            initial_dir=self.data_root,
            allowed_exts=[".png", ".jpg", ".jpeg", ".json"],
            mode="open",
        )

    def _launch_animation_editor_with_image(self, path: Path):
        """Launch animation editor subprocess with selected image or JSON."""
        try:
            if path.suffix.lower() == ".json":
                self._launch_animation_editor_with_json(path)
                return

            tile_size = "32x32"
            if hasattr(self.tilemap, "tile_size") and self.tilemap.tile_size:
                tw, th = self.tilemap.tile_size
                tile_size = f"{tw}x{th}"

            args = [str(path), "--tile-size", tile_size, "--data-root", str(self.data_root)]
            process = launch_standalone(
                "plugins.sprite_animation.standalone",
                args,
                cwd=self.base_path,
                text=True,
            )
            self.child_processes.append(process)

            print(
                f"Launched animation editor with: {path.name} (tile size: {tile_size})"
            )
        except Exception as e:
            error_handler.capture(e, context="launch_animation_editor")

    def _launch_animation_editor_with_json(self, path: Path) -> None:
        """Launch animation editor from a saved .anim.json file."""
        try:
            from plugins.sprite_animation.models import AnimationLibrary
            from utils.project_paths import resolve_project_path

            lib = AnimationLibrary.load(path)
            spritesheet_path = lib.spritesheet_path
            tile_size = lib.tile_size

            if spritesheet_path:
                resolved = resolve_project_path(
                    spritesheet_path,
                    path.parent,
                    fallback_roots=[self.base_path] if self.base_path else None,
                    must_exist=True,
                )
            else:
                resolved = None

            if not resolved or not resolved.exists():
                print(f"Could not locate spritesheet for animation file: {path.name}")
                return

            args = [
                str(resolved),
                "--tile-size", f"{tile_size[0]}x{tile_size[1]}",
                "--load", str(path),
                "--data-root", str(self.data_root),
            ]
            process = launch_standalone(
                "plugins.sprite_animation.standalone",
                args,
                cwd=self.base_path,
                text=True,
            )
            self.child_processes.append(process)
            print(f"Launched animation editor with: {path.name} (spritesheet: {resolved.name})")
        except Exception as e:
            error_handler.capture(e, context="launch_animation_editor")

    def launch_sprite_editor(self):
        """Launch the sprite editor in a new window."""
        self.open_file_manager(
            on_select=self._launch_sprite_editor_with_image,
            initial_dir=self.data_root,
            allowed_exts=[".png", ".jpg", ".jpeg"],
            mode="open",
        )

    def _launch_sprite_editor_with_image(self, path: Path):
        """Launch sprite editor subprocess with selected image."""
        try:
            tile_size = "32x32"
            if hasattr(self.tilemap, "tile_size") and self.tilemap.tile_size:
                tw, th = self.tilemap.tile_size
                tile_size = f"{tw}x{th}"

            args = [str(path), "--tile-size", tile_size, "--data-root", str(self.data_root)]
            process = launch_standalone(
                "plugins.sprite_editor.standalone",
                args,
                cwd=self.base_path,
                text=True,
            )
            self.child_processes.append(process)
        except Exception as e:
            error_handler.capture(e, context="launch_sprite_editor")

    def launch_collision_editor(self, tileset_type: str = "tile"):
        """Launch the collision editor in a new window.

        Uses the active tileset image when one is loaded. If no tileset is
        selected, shows a notification.

        Args:
            tileset_type: "tile" for tileset collision editor, "object" for object tileset collision editor
        """
        sheet = self._active_tileset_image_path()
        if sheet is not None:
            self._launch_collision_editor_with_image(sheet, tileset_type)
            return

        self.notifications.notify("No tileset loaded. Please load a tileset first.")

    def _launch_collision_editor_with_image(self, path: Path, tileset_type: str = "tile"):
        """Launch collision editor subprocess with selected tileset."""
        try:
            if tileset_type == "object":
                self._launch_object_tileset_collision_editor_with_image(path)
            else:
                self._launch_tileset_collision_editor_with_image(path)
        except Exception as e:
            error_handler.capture(e, context="launch_collision_editor")

    def _launch_tileset_collision_editor_with_image(self, path: Path):
        """Launch tileset collision editor (tile-based)."""
        logger = self.logger if hasattr(self, 'logger') else None
        tile_size = "32x32"
        if hasattr(self.tilemap, "tile_size") and self.tilemap.tile_size:
            tw, th = self.tilemap.tile_size
            tile_size = f"{tw}x{th}"

        args = [str(path), "--tile-size", tile_size, "--data-root", str(self.data_root)]

        # Collect auto-tile variant groups for this tileset and pass as --propagation-groups
        propagation_groups_path = self._write_propagation_groups(path)
        if propagation_groups_path:
            args.extend(["--propagation-groups", str(propagation_groups_path)])

        collision_dir = self.data_root / self.config.get("collision_paths", {}).get("tileset", "collision")
        collision_path = collision_dir / f"{path.stem}.collision.json"
        if collision_path.exists():
            args.extend(["--load", str(collision_path)])

        process = launch_standalone(
            "plugins.tileset_collision.standalone",
            args,
            cwd=self.base_path,
            text=True,
        )
        self.child_processes.append(process)

        msg = f"[COLLISION] Launched tileset collision editor for: {path.name} (tile size: {tile_size}) | Save path: {collision_path}"
        print(msg)
        if logger:
            logger.info(msg)

    def _write_propagation_groups(self, tileset_path: Path) -> Optional[Path]:
        """Collect auto-tile variant groups for a tileset and write to temp JSON.

        Returns the path to the temp file, or None if no autotiler data is available.
        """
        if not hasattr(self, "autotiler") or not self.autotiler:
            return None

        tw = getattr(self, "tileset_widget", None)
        if not tw or not tw.tilesets:
            return None

        # Find the tileset index matching the given path
        resolved_path = Path(tileset_path).resolve()
        tileset_index = None
        for idx, ts in enumerate(tw.tilesets):
            try:
                if Path(ts.path).resolve() == resolved_path:
                    tileset_index = idx
                    break
            except (OSError, ValueError):
                continue

        if tileset_index is None:
            return None

        # Collect variant_ids grouped by group_id from autotile rules matching this tileset
        groups: Dict[str, List[int]] = {}
        for group in self.autotiler.groups:
            for rule in group.rules:
                if rule.tileset_index == tileset_index and rule.variant_ids:
                    gid = rule.group_id or group.name
                    if gid not in groups:
                        groups[gid] = []
                    groups[gid].extend(rule.variant_ids)

        if not groups:
            return None

        import json
        import tempfile
        fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="propagation_groups_")
        with os.fdopen(fd, "w") as f:
            json.dump(groups, f)

        print(f"[COLLISION] Wrote {len(groups)} propagation groups to {tmp_path}")
        return Path(tmp_path)

    def _launch_object_tileset_collision_editor_with_image(self, path: Path):
        """Launch object tileset collision editor (region-based)."""
        logger = self.logger if hasattr(self, 'logger') else None

        collision_dir = self.data_root / self.config.get("collision_paths", {}).get("object_tileset", "collision")
        collision_path = collision_dir / f"{path.stem}.object_collision.json"

        args = [str(path), "--data-root", str(self.data_root), "--collision-dir", str(collision_dir)]
        if collision_path.exists():
            args.extend(["--load", str(collision_path)])

        process = launch_standalone(
            "plugins.object_tileset_collision.standalone",
            args,
            cwd=self.base_path,
            text=True,
        )
        self.child_processes.append(process)

        msg = f"[COLLISION] Launched object tileset collision editor for: {path.name} | Save path: {collision_path}"
        print(msg)
        if logger:
            logger.info(msg)

    def launch_character_collision_editor(self):
        """Launch the character collision editor in a new window.

        Opens a file picker to select a character sprite image.
        """
        self.open_file_manager(
            on_select=self._launch_character_collision_editor_with_image,
            initial_dir=self.data_root,
            allowed_exts=[".png", ".jpg", ".jpeg"],
            mode="open",
        )

    def _launch_character_collision_editor_with_image(self, path: Path):
        """Launch character collision editor subprocess with selected image."""
        try:
            # Use filename (without extension) as default character name
            character_name = path.stem

            args = [str(path), "--name", character_name, "--data-root", str(self.data_root)]
            
            # Check if collision data file exists and load it
            collision_dir = self.data_root / self.config.get("collision_paths", {}).get("character", "character_collision")
            collision_path = collision_dir / f"{character_name}.collision.json"
            if collision_path.exists():
                args.extend(["--load", str(collision_path)])

            process = launch_standalone(
                "plugins.character_collision.standalone",
                args,
                cwd=self.base_path,
                text=True,
            )
            self.child_processes.append(process)

            print(
                f"Launched character collision editor with: {path.name} (character: {character_name})"
            )
        except Exception as e:
            error_handler.capture(e, context="launch_character_collision_editor")

    def launch_error_console(self):
        """Launch the error console as a subprocess."""
        if self.error_console_process and self.error_console_process.poll() is None:
            print("Error console is already running")
            return

        try:
            # Calculate window size with better aspect ratio
            editor_width, editor_height = self.screen.get_size()

            # Default to 80% of editor width, 40% of editor height for good aspect ratio
            console_width = max(800, int(editor_width * 0.8))
            console_height = max(400, int(editor_height * 0.4))

            window_size = f"{console_width}x{console_height}"

            log_file = self.data_root / "logs" / "errors.log"
            args = ["--window-size", window_size, "--log-file", str(log_file)]
            process = launch_standalone(
                "standalone_error_console",
                args,
                cwd=self.base_path,
                text=True,
            )
            self.child_processes.append(process)
            self.error_console_process = process
            print(f"Launched error console ({console_width}x{console_height})")
        except Exception as e:
            error_handler.capture(e, context="launch_error_console")

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
        # Read output from finished processes
        for process in self.child_processes:
            if process.poll() is not None:
                try:
                    stdout, stderr = process.communicate(timeout=1)
                    if stdout:
                        print(f"[SUBPROCESS OUTPUT] {stdout}")
                    if stderr:
                        print(f"[SUBPROCESS ERROR] {stderr}")
                except Exception:
                    pass
        self.child_processes = [p for p in self.child_processes if p.poll() is None]

    def handle_events(self):
        """Process all pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            if event.type == pygame.VIDEORESIZE:
                self.handle_resize(event.w, event.h)

            # Priority 1: Modal dialogs and inputs (highest priority)
            if self.save_input.active:
                self.save_input.handle_event(event)
                continue

            if self.tileset_type_dialog.active:
                self.tileset_type_dialog.handle_event(event)
                continue

            if self.confirm_dialog.active:
                self.confirm_dialog.handle_event(event)
                continue

            if self.layer_type_dialog.active:
                self.layer_type_dialog.handle_event(event)
                continue

            if self.map_setup_widget and self.map_setup_widget.visible:
                if self.map_setup_widget.handle_event(event):
                    continue

            if self.map_properties_dialog and self.map_properties_dialog.visible:
                if self.map_properties_dialog.handle_event(event):
                    continue

            if self.property_editor and self.property_editor.active:
                if self.property_editor.handle_event(event):
                    continue

            # Priority 2: Autotiler and Regex Designer (block all events when visible)
            if self.autotiler.visible:
                if self.autotiler.handle_event(event):
                    continue

            if self.regex_automap_designer.visible:
                if self.regex_automap_designer.handle_event(event):
                    continue

            # Priority 3: Menu bar
            if self.menubar.handle_event(event):
                continue

            # Priority 4: Keyboard shortcuts
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
                elif event.key == pygame.K_BACKQUOTE and ctrl_held:
                    self.launch_error_console()
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
                elif event.key == pygame.K_SPACE and (ctrl_held or meta_held):
                    if self.pan_mode:
                        # Restoring: turn off pan, re-enable previous tool
                        self.pan_mode = False
                        if getattr(self, "_prev_tool", None) == "select":
                            self.select_mode = True
                        elif getattr(self, "_prev_tool", None) == "eraser":
                            self.eraser_mode = True
                        elif getattr(self, "_prev_tool", None) == "nodes":
                            self.node_editing_mode = True
                    else:
                        # Entering pan: save current tool, turn off others
                        if self.select_mode:
                            self._prev_tool = "select"
                        elif self.eraser_mode:
                            self._prev_tool = "eraser"
                        elif self.node_editing_mode:
                            self._prev_tool = "nodes"
                        else:
                            self._prev_tool = None
                        self.pan_mode = True
                        self.select_mode = False
                        self.eraser_mode = False
                        self.node_editing_mode = False
                    continue
                elif event.mod & pygame.KMOD_CTRL and event.key == pygame.K_g:
                    self.toggle_grid()
                    continue
                elif event.key == pygame.K_t and (ctrl_held or meta_held):
                    self.cycle_theme()
                    continue
                elif event.key == pygame.K_b and (ctrl_held or meta_held):
                    self.toggle_animation_panel()
                    continue
                elif pygame.K_1 <= event.key <= pygame.K_9:
                    if not (self.node_editor and self.node_editor.visible and self.node_editor.editing_field):
                        idx = event.key - pygame.K_1
                        if idx < self.tilemap.layer_manager.get_layer_count():
                            self.tilemap.layer_manager.set_active_layer(idx)
                        continue

            # Priority 5: Toolbar
            if self.toolbar and self.toolbar.handle_event(event):
                continue

            # Priority 5.5: Node selector & editor (when node mode active)
            if self.node_selector and self.node_selector.handle_event(event):
                continue
            if self.node_editor and self.node_editor.handle_event(event):
                continue

            # Priority 6: Dockable animation panel
            if self.left_panel_visible and self.animation_panel:
                if hasattr(self.animation_panel, "handle_event"):
                    if self.animation_panel.handle_event(event):
                        continue

            # Priority 7: Side panels (tileset and layer widgets)
            consumed = False
            if self.tileset_widget and self.tileset_widget.handle_event(event):
                consumed = True
            if (
                not consumed
                and self.layer_widget
                and self.layer_widget.handle_event(event)
            ):
                consumed = True
            
            # Priority 8: Main tile grid (lowest priority)
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
            
            # Draw autotiler and regex designer with modal overlay
            if self.autotiler:
                if self.autotiler.visible:
                    # Dim background when autotiler is open
                    overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 100))
                    self.screen.blit(overlay, (0, 0))
                self.autotiler.draw(self.screen)
            
            if self.regex_automap_designer:
                if self.regex_automap_designer.visible:
                    # Dim background when regex designer is open
                    overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 100))
                    self.screen.blit(overlay, (0, 0))
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

            if self.map_properties_dialog and self.map_properties_dialog.visible:
                self.map_properties_dialog.draw(self.screen)

            if self.save_input.active:
                self.save_input.draw(self.screen)
            if self.tileset_type_dialog.active:
                overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                self.screen.blit(overlay, (0, 0))
                self.tileset_type_dialog.draw(self.screen)
            if self.confirm_dialog.active:
                overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                self.screen.blit(overlay, (0, 0))
                self.confirm_dialog.draw(self.screen)
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
                font = font_manager.get_font("noto", 18, FontWeight.BOLD)
                text = font.render(msg, True, (230, 230, 230))
                text_rect = text.get_rect(center=(self.width // 2, self.height // 2))
                self.screen.blit(text, text_rect)

                dot_font = font_manager.get_font("noto", 16, FontWeight.REGULAR)
                dots = "." * ((pygame.time.get_ticks() // 400) % 4)
                dot_surf = dot_font.render(dots, True, (180, 180, 180))
                dot_rect = dot_surf.get_rect(
                    center=(self.width // 2, self.height // 2 + 30)
                )
                self.screen.blit(dot_surf, dot_rect)

            if self.toolbar:
                self.toolbar.draw(self.screen)
            if self.node_selector:
                self.node_selector.draw(self.screen)
            if self.node_editor:
                self.node_editor.draw(self.screen)
            self.menubar.draw(self.screen)
            self.tooltip.draw(self.screen)

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
        with error_context("editor_main"):
            editor = Editor(size=(1500, 900))
            editor.run()
    except KeyboardInterrupt:
        print("\nEditor interrupted by user")
    except Exception as e:
        error_handler.capture(e, context="editor_main")
        print(f"Failed to start editor: {e}")
        sys.exit(1)
