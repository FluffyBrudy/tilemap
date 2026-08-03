import json
import os
from collections.abc import Callable
from pathlib import Path

import pygame

from constants import BASE_PATH, IGNORE_DIRS, INTELLISENSE_DEPTH
from utils.error_handler import error_handler
from utils.icon_manager import icon_manager
from utils.icons_cache import prewarm_common_icons
from utils.natural_sort import natural_key
from utils.standalone import launch_standalone

from .input import InputBox
from .ui.theme import COLORS, FONTS, SHAPE


class FileItem:
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.is_dir = path.is_dir()
        self.ext = path.suffix.lower()


class DimensionPersistence:
    """Handles saving and loading FileManager dimension preferences."""

    def __init__(self, pref_file: Path):
        """Initialize with path to preference file.

        Args:
            pref_file: Path to JSON file for storing dimension preferences
        """
        self.pref_file = pref_file

    def save_dimensions(self, width: int, height: int):
        """Persist dimensions to JSON file.

        Args:
            width: Widget width in pixels
            height: Widget height in pixels
        """
        try:
            self.pref_file.parent.mkdir(parents=True, exist_ok=True)

            data = {"filemanager_width": width, "filemanager_height": height}

            with open(self.pref_file, "w") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            print(f"Warning: Could not save FileManager dimensions: {e}")

    def load_dimensions(self) -> tuple[int, int] | None:
        """Load dimensions from JSON file.

        Returns:
            Tuple of (width, height) if found, None otherwise
        """
        try:
            if not self.pref_file.exists():
                return None

            with open(self.pref_file) as f:
                data = json.load(f)

            width = data.get("filemanager_width")
            height = data.get("filemanager_height")

            if width is not None and height is not None:
                if isinstance(width, int) and isinstance(height, int):
                    if width > 0 and height > 0:
                        return (width, height)

            return None

        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Could not load FileManager dimensions: {e}")
            return None


class ResizeHandler:
    """Handles resize operations for the FileManager widget."""

    def __init__(self, widget_rect: pygame.Rect, min_width: int = 400, min_height: int = 300):
        """Initialize resize handler with widget rect and constraints.

        Args:
            widget_rect: The pygame.Rect of the widget to resize
            min_width: Minimum allowed width in pixels (default: 400)
            min_height: Minimum allowed height in pixels (default: 300)
        """
        self.widget_rect = widget_rect
        self.min_width = min_width
        self.min_height = min_height
        self.is_dragging = False
        self.drag_handle = None
        self.drag_start_pos = None
        self.drag_start_rect = None

    def get_handle_at_pos(self, pos: tuple[int, int]) -> str | None:
        """Returns handle type if pos is over a resize handle, else None.

        Args:
            pos: Mouse position as (x, y) tuple

        Returns:
            'right', 'bottom', 'corner', or None
        """
        x, y = pos

        right_edge = self.widget_rect.right
        bottom_edge = self.widget_rect.bottom
        left_edge = self.widget_rect.left
        top_edge = self.widget_rect.top

        corner_rect = pygame.Rect(right_edge - 10, bottom_edge - 10, 10, 10)
        if corner_rect.collidepoint(x, y):
            return "corner"

        if right_edge - 5 <= x <= right_edge and top_edge <= y <= bottom_edge:
            return "right"

        if bottom_edge - 5 <= y <= bottom_edge and left_edge <= x <= right_edge:
            return "bottom"

        return None

    def start_drag(self, handle: str, pos: tuple[int, int]):
        """Initiates resize drag operation.

        Args:
            handle: Handle type ('right', 'bottom', 'corner')
            pos: Mouse position as (x, y) tuple
        """
        self.is_dragging = True
        self.drag_handle = handle
        self.drag_start_pos = pos

        self.drag_start_rect = pygame.Rect(self.widget_rect)

    def update_drag(self, pos: tuple[int, int]) -> pygame.Rect:
        """Updates widget rect during drag, returns new rect.

        Args:
            pos: Current mouse position as (x, y) tuple

        Returns:
            Updated pygame.Rect with constraints applied
        """
        if not self.is_dragging or not self.drag_start_pos or not self.drag_start_rect:
            return self.widget_rect

        dx = pos[0] - self.drag_start_pos[0]
        dy = pos[1] - self.drag_start_pos[1]

        if self.drag_handle == "right":
            new_width = max(self.min_width, self.drag_start_rect.width + dx)
            self.widget_rect.width = new_width
        elif self.drag_handle == "bottom":
            new_height = max(self.min_height, self.drag_start_rect.height + dy)
            self.widget_rect.height = new_height
        elif self.drag_handle == "corner":
            new_width = max(self.min_width, self.drag_start_rect.width + dx)
            new_height = max(self.min_height, self.drag_start_rect.height + dy)
            self.widget_rect.width = new_width
            self.widget_rect.height = new_height

        return self.widget_rect

    def end_drag(self):
        """Completes resize drag operation."""
        self.is_dragging = False
        self.drag_handle = None
        self.drag_start_pos = None
        self.drag_start_rect = None

    def draw_handles(self, surface: pygame.Surface):
        """Renders resize handles on the widget.

        Args:
            surface: pygame.Surface to draw on
        """

        handle_color = COLORS.border
        handle_hover_color = COLORS.accent

        mouse_pos = pygame.mouse.get_pos()
        hovered_handle = self.get_handle_at_pos(mouse_pos)

        right_handle_rect = pygame.Rect(self.widget_rect.right - 5, self.widget_rect.top, 5, self.widget_rect.height)
        color = handle_hover_color if hovered_handle == "right" else handle_color
        pygame.draw.rect(surface, color, right_handle_rect)

        bottom_handle_rect = pygame.Rect(
            self.widget_rect.left,
            self.widget_rect.bottom - 5,
            self.widget_rect.width,
            5,
        )
        color = handle_hover_color if hovered_handle == "bottom" else handle_color
        pygame.draw.rect(surface, color, bottom_handle_rect)

        corner_handle_rect = pygame.Rect(self.widget_rect.right - 10, self.widget_rect.bottom - 10, 10, 10)
        color = handle_hover_color if hovered_handle == "corner" else handle_color
        pygame.draw.rect(surface, color, corner_handle_rect)


class ImagePreview:
    """Handles image preview display with loading, scaling, and error handling."""

    def __init__(self, max_file_size_mb: int = 50):
        """Initialize image preview component.

        Args:
            max_file_size_mb: Maximum file size in MB to load (default: 50)
        """
        self.current_image = None
        self.current_path = None
        self.image_dimensions = None
        self.error_message = None
        self.max_file_size_mb = max_file_size_mb
        self.is_visible = False
        self.scaled_cache = None
        self.cached_target_size = None

    def load_image(self, path: Path) -> bool:
        """Loads image from path, returns success status.

        Args:
            path: Path to image file

        Returns:
            True if image loaded successfully, False otherwise
        """

        self.current_image = None
        self.current_path = None
        self.image_dimensions = None
        self.error_message = None
        self.scaled_cache = None
        self.cached_target_size = None

        if not path.exists():
            self.error_message = "File not found"
            return False

        try:
            file_size_mb = path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                self.error_message = f"File too large ({file_size_mb:.1f}MB > {self.max_file_size_mb}MB)"
                return False
        except OSError as e:
            self.error_message = f"Cannot read file: {e}"
            return False

        try:
            self.current_image = pygame.image.load(str(path))
            self.current_path = path
            self.image_dimensions = self.current_image.get_size()
            self.is_visible = True
            return True
        except pygame.error as e:
            self.error_message = f"Corrupted or unsupported image: {e}"
            return False

    def clear(self):
        """Clears current preview."""
        self.current_image = None
        self.current_path = None
        self.image_dimensions = None
        self.error_message = None
        self.is_visible = False
        self.scaled_cache = None
        self.cached_target_size = None

    def scale_to_fit(self, target_width: int, target_height: int) -> pygame.Surface | None:
        """Returns scaled image surface maintaining aspect ratio.

        Args:
            target_width: Target width in pixels
            target_height: Target height in pixels

        Returns:
            Scaled pygame.Surface or None if no image loaded
        """
        if not self.current_image:
            return None

        if self.scaled_cache and self.cached_target_size == (
            target_width,
            target_height,
        ):
            return self.scaled_cache

        if self.image_dimensions is None:
            error_handler.capture(Exception("Image dimensions are None"), "scale_to_fit", "info")
            return None

        image_width, image_height = self.image_dimensions
        aspect_ratio = image_width / image_height
        target_aspect = target_width / target_height

        if aspect_ratio > target_aspect:
            new_width = target_width
            new_height = int(target_width / aspect_ratio)
        else:
            new_height = target_height
            new_width = int(target_height * aspect_ratio)

        try:
            image = self.current_image.convert_alpha()
        except Exception:
            image = self.current_image

        try:
            scaled_surface = pygame.transform.smoothscale(image, (new_width, new_height))
        except ValueError:
            scaled_surface = pygame.transform.scale(image, (new_width, new_height))

        self.scaled_cache = scaled_surface
        self.cached_target_size = (target_width, target_height)

        return scaled_surface

    def draw(self, surface: pygame.Surface, rect: pygame.Rect):
        """Renders preview panel with image, metadata, and close button.

        Args:
            surface: pygame.Surface to draw on
            rect: pygame.Rect defining the preview panel area
        """

        pygame.draw.rect(surface, COLORS.panel, rect)
        pygame.draw.rect(surface, COLORS.border, rect, SHAPE.border)

        close_button_size = 24
        close_button_margin = 8
        close_button_rect = pygame.Rect(
            rect.right - close_button_size - close_button_margin,
            rect.top + close_button_margin,
            close_button_size,
            close_button_size,
        )

        mouse_pos = pygame.mouse.get_pos()
        is_hovering = close_button_rect.collidepoint(mouse_pos)
        close_bg_color = COLORS.hover if is_hovering else COLORS.panel_alt

        pygame.draw.rect(surface, close_bg_color, close_button_rect, border_radius=SHAPE.radius_sm)

        x_color = COLORS.text
        margin = 6
        pygame.draw.line(
            surface,
            x_color,
            (close_button_rect.left + margin, close_button_rect.top + margin),
            (close_button_rect.right - margin, close_button_rect.bottom - margin),
            2,
        )
        pygame.draw.line(
            surface,
            x_color,
            (close_button_rect.right - margin, close_button_rect.top + margin),
            (close_button_rect.left + margin, close_button_rect.bottom - margin),
            2,
        )

        self.close_button_rect = close_button_rect

        if self.error_message:
            error_lines = self.error_message.split("\n")
            y_offset = rect.centery - (len(error_lines) * 20) // 2

            for line in error_lines:
                text_surf = FONTS.get_medium_font().render(line, True, COLORS.text_dim)
                text_rect = text_surf.get_rect(center=(rect.centerx, y_offset))
                surface.blit(text_surf, text_rect)
                y_offset += 20
            return

        if not self.current_image:
            text_surf = FONTS.get_medium_font().render("No preview available", True, COLORS.text_dim)
            text_rect = text_surf.get_rect(center=rect.center)
            surface.blit(text_surf, text_rect)
            return

        button_height = 35
        text_height = 25
        image_area_height = rect.height - close_button_size - close_button_margin * 2 - text_height - button_height
        image_area_width = rect.width - 20

        scaled_image = self.scale_to_fit(image_area_width, image_area_height)
        if scaled_image:
            image_rect = scaled_image.get_rect()
            image_rect.centerx = rect.centerx
            image_rect.top = rect.top + close_button_size + close_button_margin * 2

            surface.blit(scaled_image, image_rect)

            if self.image_dimensions:
                dim_text = f"{self.image_dimensions[0]} × {self.image_dimensions[1]} px"
                text_surf = FONTS.get_small_font().render(dim_text, True, COLORS.text_dim)
                text_rect = text_surf.get_rect(centerx=rect.centerx, top=image_rect.bottom + 5)
                surface.blit(text_surf, text_rect)

            button_width = 140
            button_height = 28
            self.open_viewer_button_rect = pygame.Rect(
                rect.centerx - button_width // 2,
                rect.bottom - button_height - 8,
                button_width,
                button_height,
            )

            button_hover = self.open_viewer_button_rect.collidepoint(mouse_pos)
            button_color = COLORS.accent if button_hover else COLORS.selected
            pygame.draw.rect(surface, button_color, self.open_viewer_button_rect, border_radius=SHAPE.radius_sm)

            button_text = FONTS.get_bold_font().render("Open in Viewer", True, COLORS.text)
            text_rect = button_text.get_rect(center=self.open_viewer_button_rect.center)
            surface.blit(button_text, text_rect)


class FileManager:
    def __init__(
        self,
        rect: pygame.Rect,
        initial_dir: Path | None = None,
        allowed_exts: list[str] = None,
        on_select: Callable[[Path | list[Path]], None] = lambda p: None,
        on_save: Callable[[Path], None] | None = None,
        mode: str = "open",
        default_name: str = "",
        on_cancel: Callable[[], None] = lambda: None,
        multi_select: bool = False,
        draw_overlay: bool = True,
        enable_window_drag: bool = True,
        enable_resize_handles: bool = True,
        data_root: Path = None,
    ):
        if allowed_exts is None:
            allowed_exts = [".png", ".jpg"]
        self.data_root = data_root
        self.rect = rect
        self.allowed_exts = allowed_exts
        self.on_select_callback = on_select
        self.on_save_callback = on_save
        self.mode = mode
        self.on_cancel_callback = on_cancel
        self.multi_select = multi_select
        self.draw_overlay = draw_overlay
        self.enable_window_drag = enable_window_drag
        self.enable_resize_handles = enable_resize_handles

        self.current_path = initial_dir if initial_dir else Path.home()
        self.history: list[Path] = []
        self.items: list[FileItem] = []

        self.selected_index: int = -1
        self.selected_indices: list[int] = []
        self.scroll_y = 0
        self.scroll_speed = 30
        self.hover_index = -1
        self.double_click_timer = 0
        self.clicked_item_index = -1

        self.sidebar_width = 140
        self.header_height = 40
        self.footer_height = 50
        self.item_height = 30
        self._item_icon_size = 20
        self._item_text_left = 35
        self._item_text_right = 10
        self._rename_vpad = 2
        self._text_offset_y = 7

        self.font_main = FONTS.get_medium_font()
        self.font_bold = FONTS.get_bold_font()
        self.font_small = FONTS.get_small_font()
        self.font_icon = FONTS.get_mono_font(20)

        self.search_input = InputBox(pygame.Rect(0, 0, 0, 0), font=FONTS.get_medium_font())
        self.search_rect = pygame.Rect(
            self.rect.x + self.sidebar_width + 10,
            self.rect.y + self.header_height + 5,
            self.rect.width - self.sidebar_width - 20,
            25,
        )
        self.search_header_height = 35
        self.is_searching = False

        self.save_input = InputBox(pygame.Rect(0, 0, 0, 0), font=FONTS.get_medium_font())
        self.save_input.text = default_name
        self.save_input.cursor_pos = len(default_name)
        self.save_name_rect = pygame.Rect(0, 0, 0, 0)
        self.new_folder_button_rect = pygame.Rect(0, 0, 0, 0)

        self.rename_input = InputBox(pygame.Rect(0, 0, 0, 0), font=FONTS.get_medium_font())
        self.renaming_item_idx: int | None = None

        self.recents_path = self.data_root / "recents.json" if self.data_root else BASE_PATH / "data" / "recents.json"
        self.recents: list[Path] = self._load_recents()
        self.view_mode = "files"

        self.resize_handler = ResizeHandler(self.rect, min_width=400, min_height=300)
        self.image_preview = ImagePreview(max_file_size_mb=50)
        self.dimension_persistence = DimensionPersistence(
            self.data_root / "filemanager_prefs.json"
            if self.data_root
            else BASE_PATH / "data" / "filemanager_prefs.json"
        )

        self.is_dragging_window = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

        if self.enable_resize_handles:
            saved_dims = self.dimension_persistence.load_dimensions()
            if saved_dims:
                width, height = saved_dims
                self.rect.width = width
                self.rect.height = height
                self.resize_handler.widget_rect = self.rect

        prewarm_common_icons(sizes=[(16, 16), (32, 32)])

        self.refresh_items()

    def refresh_items(self):
        self.items.clear()
        self.scroll_y = 0
        self.selected_index = -1
        self.selected_indices = []

        if self.view_mode == "recents":
            for p in self.recents:
                if p.exists():
                    self.items.append(FileItem(p))
            return

        if self.search_input.text:
            self.is_searching = True

            self._search_local_files(self.current_path, self.search_input.text)

            self._recursive_search(self.current_path, self.search_input.text, INTELLISENSE_DEPTH)

            unique_items = {str(item.path): item for item in self.items}
            self.items = sorted(unique_items.values(), key=lambda x: (not x.is_dir, natural_key(x.name)))
            return

        self.is_searching = False
        try:
            all_entries = list(self.current_path.iterdir())

            folders = sorted([p for p in all_entries if p.is_dir()], key=lambda p: natural_key(p.name))

            files = [p for p in all_entries if p.is_file() and p.suffix.lower() in self.allowed_exts]
            files = sorted(files, key=lambda p: natural_key(p.name))

            for p in folders:
                self.items.append(FileItem(p))
            for p in files:
                self.items.append(FileItem(p))

        except PermissionError:
            print(f"Permission denied: {self.current_path}")
            self.go_up()

    def _search_local_files(self, path: Path, query: str):
        try:
            for p in path.iterdir():
                if p.name.startswith("."):
                    continue
                if p.is_file() and query.lower() in p.name.lower():
                    if p.suffix.lower() in self.allowed_exts:
                        self.items.append(FileItem(p))
                elif p.is_dir() and query.lower() in p.name.lower():
                    if p.name not in IGNORE_DIRS:
                        self.items.append(FileItem(p))
        except PermissionError:
            pass

    def _recursive_search(self, path: Path, query: str, depth: int):
        if depth < 0:
            return

        try:
            for p in path.iterdir():
                if p.name.startswith("."):
                    continue

                if p.is_dir():
                    if p.name in IGNORE_DIRS:
                        continue

                    if query.lower() in p.name.lower():
                        self.items.append(FileItem(p))

                    self._recursive_search(p, query, depth - 1)
        except (PermissionError, OSError, Exception):
            pass

    def _load_recents(self) -> list[Path]:
        if not self.recents_path.exists():
            return []
        try:
            with open(self.recents_path) as f:
                data = json.load(f)
                return [Path(p) for p in data if Path(p).exists()]
        except Exception as e:
            error_handler.capture(e, context="filemanager_load_recents")
        return []

    def _save_recents(self):
        try:
            if not self.recents_path.parent.exists():
                self.recents_path.parent.mkdir(parents=True)
            with open(self.recents_path, "w") as f:
                json.dump([str(p) for p in self.recents], f)
        except Exception as e:
            error_handler.capture(e, context="filemanager_save_recents")

    def _add_to_recents(self, path: Path):
        if path in self.recents:
            self.recents.remove(path)
        self.recents.insert(0, path)
        self.recents = self.recents[:20]
        self._save_recents()

    def _assert_within_data_root(self, path: Path) -> None:
        """Ensure path is within data_root boundary to prevent arbitrary filesystem writes.

        Args:
            path: Path to validate

        Raises:
            ValueError: If path is outside data_root when data_root is set
        """
        if self.data_root is None:
            return

        try:
            resolved_path = path.resolve()
            resolved_root = self.data_root.resolve()

            resolved_path.relative_to(resolved_root)
        except ValueError:
            raise ValueError(f"Operation denied: path '{path}' is outside data_root '{self.data_root}'")

    def go_up(self):
        self.view_mode = "files"
        if self.current_path.parent != self.current_path:
            self.current_path = self.current_path.parent
            self.refresh_items()

    def navigate_to(self, path: Path, record_recent: bool = False):
        self.view_mode = "files"
        if path.is_dir():
            if record_recent:
                self._add_to_recents(path)
            self.current_path = path
            self.refresh_items()

    def _create_folder(self):
        if self.view_mode != "files" or not self.current_path.exists():
            return

        base_name = "New Folder"
        candidate = self.current_path / base_name
        idx = 2
        while candidate.exists():
            candidate = self.current_path / f"{base_name} {idx}"
            idx += 1

        try:
            self._assert_within_data_root(candidate)

            candidate.mkdir()
            self.refresh_items()
            for i, item in enumerate(self.items):
                if item.path == candidate:
                    self.selected_index = i
                    self.selected_indices = [i]

                    self._start_rename(i)
                    break
        except ValueError as e:
            print(f"Security error: {e}")
            error_handler.capture(e, context="filemanager_create_folder_security")
        except Exception as e:
            error_handler.capture(e, context="filemanager_create_folder")

    def _start_rename(self, item_idx: int) -> None:
        """Start renaming a file or folder."""
        if item_idx < 0 or item_idx >= len(self.items):
            return

        item = self.items[item_idx]
        self.renaming_item_idx = item_idx
        self.rename_input.text = item.name
        self.rename_input.cursor_pos = len(item.name)
        self.rename_input.is_focused = True

        self.search_input.is_focused = False
        self.save_input.is_focused = False

    def _confirm_rename(self) -> None:
        """Confirm and apply the rename."""
        if self.renaming_item_idx is None:
            return

        if self.renaming_item_idx < 0 or self.renaming_item_idx >= len(self.items):
            self._cancel_rename()
            return

        item = self.items[self.renaming_item_idx]
        old_path = item.path
        new_name = self.rename_input.text.strip()

        if not new_name:
            self._cancel_rename()
            return

        invalid_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
        if any(char in new_name for char in invalid_chars):
            print(f"Invalid characters in filename: {new_name}")
            self._cancel_rename()
            return

        if new_name == item.name:
            self._cancel_rename()
            return

        new_path = old_path.parent / new_name

        if new_path.exists():
            print(f"File or folder already exists: {new_name}")
            self._cancel_rename()
            return

        try:
            self._assert_within_data_root(old_path)
            self._assert_within_data_root(new_path)

            old_path.rename(new_path)

            if old_path in self.recents:
                idx = self.recents.index(old_path)
                self.recents[idx] = new_path
                self._save_recents()

            self.refresh_items()

            for i, refreshed_item in enumerate(self.items):
                if refreshed_item.path == new_path:
                    self.selected_index = i
                    self.selected_indices = [i]
                    break

        except ValueError as e:
            print(f"Security error: {e}")
            error_handler.capture(e, context="filemanager_rename_security")
        except Exception as e:
            error_handler.capture(e, context="filemanager_rename")
            print(f"Failed to rename: {e}")

        self.renaming_item_idx = None
        self.rename_input.is_focused = False

    def _cancel_rename(self) -> None:
        """Cancel rename and revert to original name."""
        self.renaming_item_idx = None
        self.rename_input.text = ""
        self.rename_input.is_focused = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse_pos = getattr(event, 'pos', pygame.mouse.get_pos())

        lx = mouse_pos[0] - self.rect.x
        ly = mouse_pos[1] - self.rect.y

        self.search_rect.x = self.rect.x + self.sidebar_width + 10
        self.new_folder_button_rect = pygame.Rect(self.rect.right - 110, self.rect.y + 6, 100, 28)

        file_list_rect = self._get_file_list_rect()

        footer_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.bottom - self.footer_height,
            self.rect.width - self.sidebar_width,
            self.footer_height,
        )
        self._update_save_name_rect(footer_rect)

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if not self.search_input.is_focused and not self.save_input.is_focused:
                if self.renaming_item_idx is not None:
                    self._cancel_rename()
                    return True

                self.on_cancel_callback()
                return True

            if self.search_input.is_focused:
                self.search_input.is_focused = False
                return True
            if self.save_input.is_focused:
                self.save_input.is_focused = False
                return True

        if event.type == pygame.MOUSEMOTION:
            if self.enable_window_drag and self.is_dragging_window:
                self.rect.x = mouse_pos[0] - self.drag_offset_x
                self.rect.y = mouse_pos[1] - self.drag_offset_y
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.enable_window_drag and self.is_dragging_window:
                self.is_dragging_window = False
                return True

        if event.type == pygame.MOUSEMOTION:
            handle = self.resize_handler.get_handle_at_pos(mouse_pos)
            if self.enable_resize_handles and handle:
                if handle == "right":
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_SIZEWE)
                elif handle == "bottom":
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_SIZENS)
                elif handle == "corner":
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_SIZENWSE)
            elif not self.resize_handler.is_dragging and not self.is_dragging_window:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)

            if self.enable_resize_handles and self.resize_handler.is_dragging:
                self.resize_handler.update_drag(mouse_pos)
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            handle = self.resize_handler.get_handle_at_pos(mouse_pos)
            if self.enable_resize_handles and handle:
                self.resize_handler.start_drag(handle, mouse_pos)
                return True

            header_rect = pygame.Rect(
                self.rect.x + self.sidebar_width,
                self.rect.y,
                self.rect.width - self.sidebar_width,
                self.header_height,
            )

            up_button_rect = pygame.Rect(self.rect.x + self.sidebar_width, self.rect.y, 40, self.header_height)
            if (
                self.enable_window_drag
                and header_rect.collidepoint(mouse_pos)
                and not up_button_rect.collidepoint(mouse_pos)
                and not self.new_folder_button_rect.collidepoint(mouse_pos)
            ):
                self.is_dragging_window = True
                self.drag_offset_x = mouse_pos[0] - self.rect.x
                self.drag_offset_y = mouse_pos[1] - self.rect.y
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.enable_resize_handles and self.resize_handler.is_dragging:
                self.resize_handler.end_drag()
                self.dimension_persistence.save_dimensions(self.rect.width, self.rect.height)
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
                return True

        if event.type == pygame.MOUSEWHEEL:
            if file_list_rect.collidepoint(mouse_pos):
                max_scroll = max(0, len(self.items) * self.item_height - file_list_rect.height)
                self.scroll_y = max(0, min(self.scroll_y - (event.y * self.scroll_speed), max_scroll))
                return True

        if event.type == pygame.MOUSEMOTION:
            if file_list_rect.collidepoint(mouse_pos):
                rel_y = ly - self.header_height - self.search_header_height + self.scroll_y
                idx = int(rel_y // self.item_height)
                if 0 <= idx < len(self.items):
                    self.hover_index = idx
                else:
                    self.hover_index = -1
            else:
                self.hover_index = -1

            return True

        if event.type == pygame.KEYDOWN and self.save_input.is_focused:
            if event.key == pygame.K_ESCAPE:
                self.save_input.is_focused = False
                return True
            if event.key == pygame.K_RETURN:
                self._attempt_save()
                return True

            if self.save_input.handle_event(event):
                return True

        if event.type == pygame.KEYDOWN and self.renaming_item_idx is not None:
            if event.key == pygame.K_RETURN:
                self._confirm_rename()
                return True
            if event.key == pygame.K_ESCAPE:
                self._cancel_rename()
                return True
            if self.rename_input.handle_event(event):
                return True

        if event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
            if self.selected_index >= 0 and self.renaming_item_idx is None:
                if not self.search_input.is_focused and not self.save_input.is_focused:
                    self._start_rename(self.selected_index)
                    return True

        if event.type == pygame.KEYDOWN and self.search_input.is_focused:
            if event.key == pygame.K_ESCAPE:
                self.search_input.is_focused = False
                return True

            if self.search_input.handle_event(event):
                self.refresh_items()
                return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                if self.image_preview.is_visible and hasattr(self.image_preview, "close_button_rect"):
                    if self.image_preview.close_button_rect and self.image_preview.close_button_rect.collidepoint(
                        mouse_pos
                    ):
                        self._hide_preview()
                        return True

                if self.image_preview.is_visible and hasattr(self.image_preview, "open_viewer_button_rect"):
                    if (
                        self.image_preview.open_viewer_button_rect
                        and self.image_preview.open_viewer_button_rect.collidepoint(mouse_pos)
                    ):
                        self._open_image_viewer()
                        return True

                if lx < self.sidebar_width:
                    self._handle_sidebar_click(ly)
                    return True

                if self.search_rect.collidepoint(mouse_pos):
                    self.save_input.is_focused = False
                    self.search_input.is_focused = True
                    return True
                self.search_input.is_focused = False
                if self.mode == "save" and self.save_name_rect.collidepoint(mouse_pos):
                    self.search_input.is_focused = False
                    self.save_input.is_focused = True
                    return True
                self.save_input.is_focused = False

                if ly < self.header_height:
                    if lx < self.sidebar_width + 40:
                        self.go_up()
                    elif self.new_folder_button_rect.collidepoint(mouse_pos):
                        self._create_folder()
                    return True

                if ly > self.rect.height - self.footer_height:
                    self._handle_footer_click(lx)
                    return True

                if file_list_rect.collidepoint(mouse_pos) and self.hover_index != -1:
                    idx = self.hover_index
                    item = self.items[idx]

                    if self.renaming_item_idx is not None and idx != self.renaming_item_idx:
                        self._confirm_rename()

                        return True

                    current_time = pygame.time.get_ticks()

                    if self.clicked_item_index == idx and (current_time - self.double_click_timer) < 500:
                        if item.is_dir:
                            self.navigate_to(item.path, record_recent=True)
                        else:
                            if self.mode == "save":
                                self.save_input.text = item.name
                                self.save_input.cursor_pos = len(item.name)
                                self._attempt_save()
                            else:
                                if self.multi_select and self.selected_indices:
                                    paths = []
                                    for sidx in self.selected_indices:
                                        if 0 <= sidx < len(self.items):
                                            sitem = self.items[sidx]
                                            if not sitem.is_dir:
                                                self._add_to_recents(sitem.path)
                                                paths.append(sitem.path)
                                    if paths:
                                        self.on_select_callback(paths)
                                else:
                                    self._add_to_recents(item.path)
                                    self.on_select_callback(item.path)
                    else:
                        mods = pygame.key.get_mods()
                        ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
                        meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)
                        shift_held = mods & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT)
                        if self.multi_select:
                            if shift_held and self.selected_indices:
                                start = self.selected_index if self.selected_index != -1 else idx
                                lo = min(start, idx)
                                hi = max(start, idx)
                                self.selected_indices = list(range(lo, hi + 1))
                            elif ctrl_held or meta_held:
                                if idx in self.selected_indices:
                                    self.selected_indices.remove(idx)
                                else:
                                    self.selected_indices.append(idx)
                            else:
                                self.selected_indices = [idx]
                            self.selected_index = idx
                        else:
                            self.selected_index = idx
                            self.selected_indices = [idx]
                        self.clicked_item_index = idx
                        self.double_click_timer = current_time
                        if not item.is_dir and self.mode == "save":
                            self.save_input.text = item.name
                            self.save_input.cursor_pos = len(item.name)

                        if not item.is_dir:
                            if item.ext in [".png", ".jpg", ".jpeg"]:
                                self._show_preview(item.path)
                            else:
                                self._hide_preview()
                        else:
                            self._hide_preview()

                    return True

        return True

    def _handle_sidebar_click(self, ly):
        shortcuts = [
            ("Home", Path.home()),
            ("Documents", Path.home() / "Documents"),
            ("Desktop", Path.home() / "Desktop"),
            ("Downloads", Path.home() / "Downloads"),
            ("Recents", None),
            ("Root", Path(os.path.abspath(os.sep))),
        ]

        start_y = 10
        gap = 40

        for i, (name, path) in enumerate(shortcuts):
            btn_y = start_y + (i * gap)
            if btn_y <= ly <= btn_y + 30:
                if name == "Recents":
                    self.view_mode = "recents"
                    self.refresh_items()
                elif path and path.exists():
                    self.navigate_to(path)
                return

    def _handle_footer_click(self, lx):
        btn_w = 80
        pad = 10

        footer_lx = lx - self.sidebar_width

        file_list_rect = self._get_file_list_rect()
        footer_width = file_list_rect.width

        cancel_x = footer_width - btn_w - pad
        open_x = cancel_x - btn_w - pad

        if cancel_x <= footer_lx <= cancel_x + btn_w:
            self.on_cancel_callback()
        elif open_x <= footer_lx <= open_x + btn_w:
            if self.mode == "save":
                self._attempt_save()
            else:
                if self.multi_select and self.selected_indices:
                    paths: list[Path] = []
                    for idx in self.selected_indices:
                        if 0 <= idx < len(self.items):
                            item = self.items[idx]
                            if not item.is_dir:
                                self._add_to_recents(item.path)
                                paths.append(item.path)
                    if paths:
                        self.on_select_callback(paths)
                elif self.selected_index != -1:
                    item = self.items[self.selected_index]
                    if not item.is_dir:
                        self._add_to_recents(item.path)
                        self.on_select_callback(item.path)

    def _update_save_name_rect(self, footer_rect: pygame.Rect):
        if self.mode != "save":
            self.save_name_rect = pygame.Rect(0, 0, 0, 0)
            return
        btn_w = 80
        pad = 10
        label_w = 80
        input_x = footer_rect.x + label_w
        input_y = footer_rect.y + 10
        input_w = footer_rect.width - (btn_w * 2) - (pad * 3) - label_w
        input_h = 30
        self.save_name_rect = pygame.Rect(input_x, input_y, max(60, input_w), input_h)

    def _resolve_save_path(self) -> Path | None:
        name = self.save_input.text.strip()
        if not name and self.selected_index != -1:
            item = self.items[self.selected_index]
            if not item.is_dir:
                name = item.name

        if not name:
            return None

        candidate = Path(name)
        if candidate.suffix == "" and self.allowed_exts:
            name = f"{name}{self.allowed_exts[0]}"
            candidate = Path(name)

        if candidate.suffix and self.allowed_exts and candidate.suffix.lower() not in self.allowed_exts:
            print(f"Invalid extension: {candidate.suffix}")
            return None

        target = self.current_path / candidate
        if target.exists() and target.is_dir():
            print("Cannot save: selected name is a directory")
            return None
        return target

    def _attempt_save(self):
        path = self._resolve_save_path()
        if not path:
            return
        self._add_to_recents(path)
        if self.on_save_callback:
            self.on_save_callback(path)
        else:
            self.on_select_callback(path)

    def _get_file_list_rect(self) -> pygame.Rect:
        """Returns rect for file list, accounting for preview panel.

        When preview is visible, file list gets 60% of content area width.
        When preview is hidden, file list gets full content area width.

        Returns:
            pygame.Rect defining the file list area
        """
        content_width = self.rect.width - self.sidebar_width
        content_x = self.rect.x + self.sidebar_width
        content_y = self.rect.y + self.header_height + self.search_header_height
        content_height = self.rect.height - self.header_height - self.footer_height - self.search_header_height

        if self.image_preview.is_visible:
            file_list_width = int(content_width * 0.6)

            min_file_list_width = int(content_width * 0.4)
            file_list_width = max(file_list_width, min_file_list_width)
        else:
            file_list_width = content_width

        return pygame.Rect(content_x, content_y, file_list_width, content_height)

    def _get_preview_rect(self) -> pygame.Rect:
        """Returns rect for preview panel.

        Preview panel occupies remaining content area width (40% when visible).

        Returns:
            pygame.Rect defining the preview panel area
        """
        content_width = self.rect.width - self.sidebar_width
        content_y = self.rect.y + self.header_height + self.search_header_height
        content_height = self.rect.height - self.header_height - self.footer_height - self.search_header_height

        file_list_width = int(content_width * 0.6)
        preview_x = self.rect.x + self.sidebar_width + file_list_width
        preview_width = content_width - file_list_width

        return pygame.Rect(preview_x, content_y, preview_width, content_height)

    def _show_preview(self, file_path: Path):
        """Activates preview panel for given image file.

        Checks file extension and loads image if it's a supported format.

        Args:
            file_path: Path to the image file to preview
        """

        supported_extensions = [".png", ".jpg", ".jpeg"]
        if file_path.suffix.lower() not in supported_extensions:
            return

        self.image_preview.load_image(file_path)

    def _hide_preview(self):
        """Deactivates preview panel and restores full-width file list."""
        self.image_preview.clear()

    def _open_image_viewer(self):
        """Open the standalone image viewer for the current preview image."""
        if not self.image_preview.current_path:
            return

        try:
            launch_standalone(
                "standalone_image_viewer",
                [str(self.image_preview.current_path)],
                cwd=BASE_PATH,
            )
        except Exception as e:
            print(f"Error opening image viewer: {e}")

    def draw(self, screen: pygame.Surface):

        if self.draw_overlay:
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            overlay.fill((*COLORS.bg, 200))
            screen.blit(overlay, (0, 0))

        shadow_rect = self.rect.inflate(6, 6)
        shadow_surf = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(shadow_surf, (0, 0, 0, 60), shadow_surf.get_rect(), border_radius=SHAPE.radius)
        screen.blit(shadow_surf, shadow_rect)

        pygame.draw.rect(screen, COLORS.panel, self.rect, border_radius=SHAPE.radius)

        sidebar_rect = pygame.Rect(self.rect.x, self.rect.y, self.sidebar_width, self.rect.height)
        pygame.draw.rect(screen, COLORS.panel_alt, sidebar_rect)
        pygame.draw.line(
            screen,
            COLORS.border,
            (sidebar_rect.right, sidebar_rect.top),
            (sidebar_rect.right, sidebar_rect.bottom),
            SHAPE.border,
        )

        self._draw_sidebar_items(screen, sidebar_rect)

        header_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.y,
            self.rect.width - self.sidebar_width,
            self.header_height,
        )
        pygame.draw.rect(screen, COLORS.header, header_rect)
        pygame.draw.line(
            screen,
            COLORS.border,
            (header_rect.left, header_rect.bottom),
            (header_rect.right, header_rect.bottom),
            SHAPE.border,
        )

        self._draw_header(screen, header_rect)

        search_bg_rect = pygame.Rect(
            header_rect.left,
            header_rect.bottom,
            header_rect.width,
            self.search_header_height,
        )
        pygame.draw.rect(screen, COLORS.panel, search_bg_rect)

        self.search_rect.x = search_bg_rect.x + 10
        self.search_rect.y = search_bg_rect.y + 5
        self.search_rect.width = search_bg_rect.width - 20

        self.search_input.resize(
            self.search_rect.x,
            self.search_rect.y,
            self.search_rect.w,
            self.search_rect.h,
        )
        self.search_input.draw(screen)

        if not self.search_input.text and not self.search_input.is_focused:
            placeholder = FONTS.get_medium_font().render("Search files...", True, COLORS.text_dim)
            screen.blit(
                placeholder,
                (self.search_input.content_rect.x, self.search_input.content_rect.y),
            )

        file_list_rect = self._get_file_list_rect()
        self._draw_file_list(screen, file_list_rect)

        footer_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.bottom - self.footer_height,
            file_list_rect.width,
            self.footer_height,
        )
        self._update_save_name_rect(footer_rect)
        pygame.draw.rect(screen, COLORS.header, footer_rect)
        pygame.draw.line(
            screen,
            COLORS.border,
            (footer_rect.left, footer_rect.top),
            (footer_rect.right, footer_rect.top),
            SHAPE.border,
        )

        self._draw_footer(screen, footer_rect)

        if self.image_preview.is_visible:
            preview_rect = self._get_preview_rect()
            self.image_preview.draw(screen, preview_rect)

        pygame.draw.rect(screen, COLORS.border, self.rect, 2, border_radius=SHAPE.radius)

        if self.enable_resize_handles:
            self.resize_handler.draw_handles(screen)

    def _draw_sidebar_items(self, screen, rect):
        shortcuts = ["Home", "Documents", "Desktop", "Downloads", "Recents", "Root"]
        start_y = rect.y + 10
        gap = 40

        for i, name in enumerate(shortcuts):
            y = start_y + (i * gap)

            mx, my = pygame.mouse.get_pos()
            btn_rect = pygame.Rect(rect.x + 5, y, rect.width - 10, 30)

            is_active = False
            if name == "Recents" and self.view_mode == "recents":
                is_active = True

            col = (
                COLORS.selected if is_active else (COLORS.hover if btn_rect.collidepoint(mx, my) else COLORS.panel_alt)
            )
            pygame.draw.rect(screen, col, btn_rect, border_radius=SHAPE.radius_sm)

            txt = self.font_bold.render(name, True, COLORS.text)
            screen.blit(txt, (rect.x + 15, y + 7))

    def _draw_header(self, screen, rect):
        up_btn = pygame.Rect(rect.x + 5, rect.y + 5, 30, 30)

        up_icon = icon_manager.get_icon("arrow-down", 16, COLORS.text)

        up_icon = pygame.transform.rotate(up_icon, 180)
        screen.blit(up_icon, up_icon.get_rect(center=up_btn.center))
        parts = self.current_path.parts
        display_parts = ["..."] + list(parts[-3:]) if len(parts) > 4 else list(parts)
        path_str = " / ".join(display_parts)
        self.new_folder_button_rect = pygame.Rect(rect.right - 110, rect.y + 6, 100, 28)
        mx, my = pygame.mouse.get_pos()
        folder_bg = COLORS.selected if self.new_folder_button_rect.collidepoint(mx, my) else COLORS.hover
        pygame.draw.rect(screen, folder_bg, self.new_folder_button_rect, border_radius=SHAPE.radius_sm)
        folder_icon = icon_manager.get_icon("folder", 16, COLORS.warning)
        screen.blit(
            folder_icon,
            folder_icon.get_rect(
                midleft=(
                    self.new_folder_button_rect.x + 8,
                    self.new_folder_button_rect.centery,
                )
            ),
        )
        folder_text = self.font_bold.render("New", True, COLORS.text)
        screen.blit(
            folder_text,
            folder_text.get_rect(
                midleft=(
                    self.new_folder_button_rect.x + 30,
                    self.new_folder_button_rect.centery,
                )
            ),
        )

        path_max_w = max(30, self.new_folder_button_rect.x - (rect.x + 45) - 10)
        while path_str and self.font_main.size(path_str)[0] > path_max_w:
            path_str = "..." + path_str[4:]
        txt = self.font_main.render(path_str, True, COLORS.text_dim)
        screen.blit(txt, (rect.x + 45, rect.y + 12))

    def _draw_file_list(self, screen, rect):
        clip = screen.get_clip()
        screen.set_clip(rect)

        start_y = rect.y - self.scroll_y

        for i, item in enumerate(self.items):
            y = start_y + (i * self.item_height)

            if y + self.item_height < rect.y:
                continue
            if y > rect.bottom:
                break

            row_rect = pygame.Rect(rect.x, y, rect.width, self.item_height)

            if i == self.selected_index or (self.multi_select and i in self.selected_indices):
                pygame.draw.rect(screen, COLORS.selected, row_rect)
            elif i == self.hover_index:
                pygame.draw.rect(screen, COLORS.hover, row_rect)

            if i == self.renaming_item_idx:
                pygame.draw.rect(screen, COLORS.selected, row_rect)

            icon_size = (20, 20)
            icon_x = rect.x + 10
            icon_y = y + (self.item_height - icon_size[1]) // 2

            if item.is_dir:
                icon = icon_manager.get_icon("folder", 20, COLORS.warning)
            elif item.ext in [".png", ".jpg", ".jpeg"]:
                icon = icon_manager.get_icon("image", 20, COLORS.success)
            else:
                icon = icon_manager.get_icon("file", 20, COLORS.text_dim)

            screen.blit(icon, (icon_x, icon_y))

            if i == self.renaming_item_idx:
                text_x = rect.x + self._item_text_left
                text_y = y + self._rename_vpad
                text_w = rect.width - self._item_text_left - self._item_text_right
                text_h = self.item_height - self._rename_vpad * 2
                self.rename_input.resize(text_x, text_y, text_w, text_h)
                self.rename_input.draw(screen)
            else:
                col = COLORS.accent if i == self.selected_index else COLORS.text
                txt = self.font_main.render(item.name, True, col)
                screen.blit(txt, (rect.x + self._item_text_left, y + self._text_offset_y))

        screen.set_clip(clip)

        total_h = len(self.items) * self.item_height
        if total_h > rect.height:
            scroll_pct = self.scroll_y / (total_h - rect.height)
            bar_h = max(20, rect.height * (rect.height / total_h))
            bar_y = rect.y + scroll_pct * (rect.height - bar_h)

            bar_rect = pygame.Rect(rect.right - 6, bar_y, 4, bar_h)
            pygame.draw.rect(screen, COLORS.border, bar_rect, border_radius=SHAPE.radius_sm)

    def _draw_footer(self, screen, rect):
        sel_txt: str
        if self.multi_select and len(self.selected_indices) > 1:
            sel_txt = f"{len(self.selected_indices)} files selected"
        elif self.selected_index != -1:
            sel_txt = self.items[self.selected_index].name
        else:
            sel_txt = "No file selected"

        if self.mode == "open":
            txt_surf = self.font_main.render(sel_txt, True, COLORS.text_dim)
            screen.blit(txt_surf, (rect.x + 10, rect.y + 12))
            if self.multi_select:
                hint = "[Ctrl+Click] toggle  [Shift+Click] range  [Open] confirm"
                hint_surf = self.font_small.render(hint, True, COLORS.text_dim)
                screen.blit(hint_surf, (rect.x + 10, rect.y + 28))

        btn_w, btn_h = 80, 30
        margin = 10

        def draw_btn(x, label, accent=False):
            r = pygame.Rect(x, rect.y + 10, btn_w, btn_h)
            bg = COLORS.accent if accent else COLORS.hover

            mx, my = pygame.mouse.get_pos()
            if r.collidepoint(mx, my):
                bg = COLORS.accent_hover if accent else COLORS.selected

            pygame.draw.rect(screen, bg, r, border_radius=SHAPE.radius_sm)
            lbl = self.font_bold.render(label, True, COLORS.text)
            lbl_r = lbl.get_rect(center=r.center)
            screen.blit(lbl, lbl_r)

        cancel_x = rect.right - btn_w - margin
        open_x = cancel_x - btn_w - margin

        draw_btn(cancel_x, "Cancel")
        draw_btn(open_x, "Save" if self.mode == "save" else "Open", accent=True)

        if self.mode == "save":
            label = self.font_bold.render("File name:", True, COLORS.text_dim)
            screen.blit(label, (rect.x + 10, rect.y + 16))

            self.save_input.resize(
                self.save_name_rect.x,
                self.save_name_rect.y,
                self.save_name_rect.w,
                self.save_name_rect.h,
            )
            self.save_input.draw(screen)

    def _draw_icon_arrow_up(self, surface, cx, cy, color):
        points = [(cx, cy - 5), (cx - 5, cy + 2), (cx + 5, cy + 2)]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.rect(surface, color, (cx - 2, cy + 2, 4, 4))
