import pygame
import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from constants import INTELLISENSE_DEPTH, IGNORE_DIRS, BASE_PATH


COLORS = {
    "overlay": (0, 0, 0, 180),
    "bg": (30, 32, 36),
    "sidebar": (25, 27, 30),
    "header": (40, 42, 46),
    "border": (60, 62, 65),
    "text_main": (230, 230, 230),
    "text_dim": (140, 140, 140),
    "highlight": (50, 60, 80),
    "selected": (70, 90, 130),
    "accent": (80, 120, 200),
    "folder": (220, 180, 80),
    "file": (180, 180, 180),
    "image": (100, 180, 120),
}


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
            # Ensure directory exists
            self.pref_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save dimensions to JSON
            data = {
                "filemanager_width": width,
                "filemanager_height": height
            }
            
            with open(self.pref_file, 'w') as f:
                json.dump(data, f, indent=2)
        except (OSError, IOError) as e:
            # Silently handle file write errors - not critical
            print(f"Warning: Could not save FileManager dimensions: {e}")
    
    def load_dimensions(self) -> Optional[Tuple[int, int]]:
        """Load dimensions from JSON file.
        
        Returns:
            Tuple of (width, height) if found, None otherwise
        """
        try:
            if not self.pref_file.exists():
                return None
            
            with open(self.pref_file, 'r') as f:
                data = json.load(f)
            
            width = data.get("filemanager_width")
            height = data.get("filemanager_height")
            
            # Validate that both dimensions exist and are positive integers
            if width is not None and height is not None:
                if isinstance(width, int) and isinstance(height, int):
                    if width > 0 and height > 0:
                        return (width, height)
            
            return None
            
        except (OSError, IOError, json.JSONDecodeError) as e:
            # Handle missing, unreadable, or corrupted files gracefully
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
        self.drag_handle = None  # 'right', 'bottom', 'corner', or None
        self.drag_start_pos = None  # Tuple[int, int]
        self.drag_start_rect = None  # pygame.Rect
    
    def get_handle_at_pos(self, pos: Tuple[int, int]) -> Optional[str]:
        """Returns handle type if pos is over a resize handle, else None.
        
        Args:
            pos: Mouse position as (x, y) tuple
            
        Returns:
            'right', 'bottom', 'corner', or None
        """
        x, y = pos
        
        # Define handle detection zones
        right_edge = self.widget_rect.right
        bottom_edge = self.widget_rect.bottom
        left_edge = self.widget_rect.left
        top_edge = self.widget_rect.top
        
        # Corner handle (10x10 pixel square at bottom-right)
        corner_rect = pygame.Rect(right_edge - 10, bottom_edge - 10, 10, 10)
        if corner_rect.collidepoint(x, y):
            return 'corner'
        
        # Right edge handle (5-pixel wide vertical strip)
        if (right_edge - 5 <= x <= right_edge and 
            top_edge <= y <= bottom_edge):
            return 'right'
        
        # Bottom edge handle (5-pixel tall horizontal strip)
        if (bottom_edge - 5 <= y <= bottom_edge and 
            left_edge <= x <= right_edge):
            return 'bottom'
        
        return None
    
    def start_drag(self, handle: str, pos: Tuple[int, int]):
        """Initiates resize drag operation.
        
        Args:
            handle: Handle type ('right', 'bottom', 'corner')
            pos: Mouse position as (x, y) tuple
        """
        self.is_dragging = True
        self.drag_handle = handle
        self.drag_start_pos = pos
        # Store a copy of the rect at drag start
        self.drag_start_rect = pygame.Rect(self.widget_rect)
    
    def update_drag(self, pos: Tuple[int, int]) -> pygame.Rect:
        """Updates widget rect during drag, returns new rect.
        
        Args:
            pos: Current mouse position as (x, y) tuple
            
        Returns:
            Updated pygame.Rect with constraints applied
        """
        if not self.is_dragging or not self.drag_start_pos or not self.drag_start_rect:
            return self.widget_rect
        
        # Calculate delta from drag start
        dx = pos[0] - self.drag_start_pos[0]
        dy = pos[1] - self.drag_start_pos[1]
        
        # Apply changes based on handle type
        if self.drag_handle == 'right':
            new_width = max(self.min_width, self.drag_start_rect.width + dx)
            self.widget_rect.width = new_width
        elif self.drag_handle == 'bottom':
            new_height = max(self.min_height, self.drag_start_rect.height + dy)
            self.widget_rect.height = new_height
        elif self.drag_handle == 'corner':
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
        # Use colors consistent with the widget theme
        handle_color = COLORS["border"]
        handle_hover_color = COLORS["accent"]
        
        # Get current mouse position to check for hover
        mouse_pos = pygame.mouse.get_pos()
        hovered_handle = self.get_handle_at_pos(mouse_pos)
        
        # Draw right edge handle (5-pixel wide vertical strip)
        right_handle_rect = pygame.Rect(
            self.widget_rect.right - 5,
            self.widget_rect.top,
            5,
            self.widget_rect.height
        )
        color = handle_hover_color if hovered_handle == 'right' else handle_color
        pygame.draw.rect(surface, color, right_handle_rect)
        
        # Draw bottom edge handle (5-pixel tall horizontal strip)
        bottom_handle_rect = pygame.Rect(
            self.widget_rect.left,
            self.widget_rect.bottom - 5,
            self.widget_rect.width,
            5
        )
        color = handle_hover_color if hovered_handle == 'bottom' else handle_color
        pygame.draw.rect(surface, color, bottom_handle_rect)
        
        # Draw corner handle (10x10 pixel square at bottom-right)
        corner_handle_rect = pygame.Rect(
            self.widget_rect.right - 10,
            self.widget_rect.bottom - 10,
            10,
            10
        )
        color = handle_hover_color if hovered_handle == 'corner' else handle_color
        pygame.draw.rect(surface, color, corner_handle_rect)


class ImagePreview:
    """Handles image preview display with loading, scaling, and error handling."""
    
    def __init__(self, max_file_size_mb: int = 50):
        """Initialize image preview component.

        Args:
            max_file_size_mb: Maximum file size in MB to load (default: 50)
        """
        self.current_image = None  # pygame.Surface
        self.current_path = None  # Path
        self.image_dimensions = None  # Tuple[int, int]
        self.error_message = None  # Optional[str]
        self.max_file_size_mb = max_file_size_mb
        self.is_visible = False
        self.scaled_cache = None  # Cached scaled image
        self.cached_target_size = None  # Cached target dimensions
    
    def load_image(self, path: Path) -> bool:
        """Loads image from path, returns success status.

        Args:
            path: Path to image file

        Returns:
            True if image loaded successfully, False otherwise
        """
        # Clear previous state
        self.current_image = None
        self.current_path = None
        self.image_dimensions = None
        self.error_message = None
        self.scaled_cache = None
        self.cached_target_size = None

        # Check if file exists
        if not path.exists():
            self.error_message = "File not found"
            return False

        # Check file size
        try:
            file_size_mb = path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                self.error_message = f"File too large ({file_size_mb:.1f}MB > {self.max_file_size_mb}MB)"
                return False
        except OSError as e:
            self.error_message = f"Cannot read file: {e}"
            return False

        # Try to load the image
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
    
    def scale_to_fit(self, target_width: int, target_height: int) -> Optional[pygame.Surface]:
        """Returns scaled image surface maintaining aspect ratio.
        
        Args:
            target_width: Target width in pixels
            target_height: Target height in pixels
            
        Returns:
            Scaled pygame.Surface or None if no image loaded
        """
        if not self.current_image:
            return None
        
        # Check cache
        if self.scaled_cache and self.cached_target_size == (target_width, target_height):
            return self.scaled_cache
        
        # Calculate scaled dimensions
        image_width, image_height = self.image_dimensions
        aspect_ratio = image_width / image_height
        target_aspect = target_width / target_height
        
        if aspect_ratio > target_aspect:
            # Image is wider than target
            new_width = target_width
            new_height = int(target_width / aspect_ratio)
        else:
            # Image is taller than target
            new_height = target_height
            new_width = int(target_height * aspect_ratio)
        
        # Scale the image
        scaled_surface = pygame.transform.smoothscale(
            self.current_image, 
            (new_width, new_height)
        )
        
        # Cache the result
        self.scaled_cache = scaled_surface
        self.cached_target_size = (target_width, target_height)
        
        return scaled_surface
    
    def draw(self, surface: pygame.Surface, rect: pygame.Rect):
        """Renders preview panel with image, metadata, and close button.

        Args:
            surface: pygame.Surface to draw on
            rect: pygame.Rect defining the preview panel area
        """
        # Draw background
        pygame.draw.rect(surface, COLORS["bg"], rect)
        pygame.draw.rect(surface, COLORS["border"], rect, 1)

        # Draw close button at top-right
        close_button_size = 24
        close_button_margin = 8
        close_button_rect = pygame.Rect(
            rect.right - close_button_size - close_button_margin,
            rect.top + close_button_margin,
            close_button_size,
            close_button_size
        )

        # Check if mouse is hovering over close button
        mouse_pos = pygame.mouse.get_pos()
        is_hovering = close_button_rect.collidepoint(mouse_pos)
        close_bg_color = COLORS["highlight"] if is_hovering else COLORS["sidebar"]

        pygame.draw.rect(surface, close_bg_color, close_button_rect, border_radius=4)

        # Draw X icon
        x_color = COLORS["text_main"]
        margin = 6
        pygame.draw.line(
            surface, x_color,
            (close_button_rect.left + margin, close_button_rect.top + margin),
            (close_button_rect.right - margin, close_button_rect.bottom - margin),
            2
        )
        pygame.draw.line(
            surface, x_color,
            (close_button_rect.right - margin, close_button_rect.top + margin),
            (close_button_rect.left + margin, close_button_rect.bottom - margin),
            2
        )

        # Store close button rect for click detection
        self.close_button_rect = close_button_rect

        # If there's an error, display error message
        if self.error_message:
            font = pygame.font.SysFont("Arial", 14)
            error_lines = self.error_message.split('\n')
            y_offset = rect.centery - (len(error_lines) * 20) // 2

            for line in error_lines:
                text_surf = font.render(line, True, COLORS["text_dim"])
                text_rect = text_surf.get_rect(center=(rect.centerx, y_offset))
                surface.blit(text_surf, text_rect)
                y_offset += 20
            return

        # If no image loaded, show placeholder
        if not self.current_image:
            font = pygame.font.SysFont("Arial", 14)
            text_surf = font.render("No preview available", True, COLORS["text_dim"])
            text_rect = text_surf.get_rect(center=rect.center)
            surface.blit(text_surf, text_rect)
            return

        # Calculate available space for image (leave room for button and dimensions text)
        button_height = 35
        text_height = 25
        image_area_height = rect.height - close_button_size - close_button_margin * 2 - text_height - button_height
        image_area_width = rect.width - 20  # 10px margin on each side

        # Scale and draw image
        scaled_image = self.scale_to_fit(image_area_width, image_area_height)
        if scaled_image:
            # Center the image in the available space
            image_rect = scaled_image.get_rect()
            image_rect.centerx = rect.centerx
            image_rect.top = rect.top + close_button_size + close_button_margin * 2

            surface.blit(scaled_image, image_rect)

            # Draw dimensions text below image
            if self.image_dimensions:
                font = pygame.font.SysFont("Arial", 12)
                dim_text = f"{self.image_dimensions[0]} × {self.image_dimensions[1]} px"
                text_surf = font.render(dim_text, True, COLORS["text_dim"])
                text_rect = text_surf.get_rect(
                    centerx=rect.centerx,
                    top=image_rect.bottom + 5
                )
                surface.blit(text_surf, text_rect)

            # Draw "Open in Viewer" button
            button_width = 140
            button_height = 28
            self.open_viewer_button_rect = pygame.Rect(
                rect.centerx - button_width // 2,
                rect.bottom - button_height - 8,
                button_width,
                button_height
            )

            button_hover = self.open_viewer_button_rect.collidepoint(mouse_pos)
            button_color = COLORS["accent"] if button_hover else COLORS["selected"]
            pygame.draw.rect(surface, button_color, self.open_viewer_button_rect, border_radius=4)

            font = pygame.font.SysFont("Arial", 13, bold=True)
            button_text = font.render("Open in Viewer", True, COLORS["text_main"])
            text_rect = button_text.get_rect(center=self.open_viewer_button_rect.center)
            surface.blit(button_text, text_rect)


    


class FileManager:
    def __init__(
        self,
        rect: pygame.Rect,
        initial_dir: Optional[Path] = None,
        allowed_exts: List[str] = [".png", ".jpg"],
        on_select: Callable[[Path], None] = lambda p: None,
        on_save: Optional[Callable[[Path], None]] = None,
        mode: str = "open",
        default_name: str = "",
        on_cancel: Callable[[], None] = lambda: None,
        multi_select: bool = False,
    ):
        self.rect = rect
        self.allowed_exts = allowed_exts
        self.on_select_callback = on_select
        self.on_save_callback = on_save
        self.mode = mode
        self.on_cancel_callback = on_cancel
        self.multi_select = multi_select

        self.current_path = initial_dir if initial_dir else Path.home()
        self.history: List[Path] = []
        self.items: List[FileItem] = []

        self.selected_index: int = -1
        self.selected_indices: List[int] = []
        self.scroll_y = 0
        self.scroll_speed = 30
        self.hover_index = -1
        self.double_click_timer = 0
        self.clicked_item_index = -1

        self.sidebar_width = 140
        self.header_height = 40
        self.footer_height = 50
        self.item_height = 30

        self.font_main = pygame.font.SysFont("Arial", 14)
        self.font_bold = pygame.font.SysFont("Arial", 14, bold=True)
        self.font_icon = pygame.font.SysFont("Consolas", 20)

        self.search_query = ""
        self.is_searching = False
        self.search_rect = pygame.Rect(
            self.rect.x + self.sidebar_width + 10,
            self.rect.y + self.header_height + 5,
            self.rect.width - self.sidebar_width - 20,
            25
        )
        self.search_header_height = 35
        self.is_search_focused = False
        self.save_name = default_name
        self.is_save_name_focused = False
        self.save_name_rect = pygame.Rect(0, 0, 0, 0)
        
        self.recents_path = BASE_PATH / "data" / "recents.json"
        self.recents: List[Path] = self._load_recents()
        self.view_mode = "files"  # "files" or "recents"

        # Initialize new components for resize and preview functionality
        self.resize_handler = ResizeHandler(self.rect, min_width=400, min_height=300)
        self.image_preview = ImagePreview(max_file_size_mb=50)
        self.dimension_persistence = DimensionPersistence(BASE_PATH / "data" / "filemanager_prefs.json")
        
        # Window dragging state
        self.is_dragging_window = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        
        # Load and apply saved dimensions
        saved_dims = self.dimension_persistence.load_dimensions()
        if saved_dims:
            width, height = saved_dims
            self.rect.width = width
            self.rect.height = height
            # Update resize handler's widget_rect reference
            self.resize_handler.widget_rect = self.rect

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

        if self.search_query:
            self.is_searching = True
            # 1. Search files locally (current dir only)
            self._search_local_files(self.current_path, self.search_query)
            # 2. Search directories recursively
            self._recursive_search(self.current_path, self.search_query, INTELLISENSE_DEPTH)
            
            # Use a dict to avoid duplicates (same path might be found)
            unique_items = {str(item.path): item for item in self.items}
            self.items = sorted(unique_items.values(), key=lambda x: (not x.is_dir, x.name.lower()))
            return

        self.is_searching = False
        try:
            all_entries = list(self.current_path.iterdir())

            folders = sorted(
                [p for p in all_entries if p.is_dir()], key=lambda p: p.name.lower()
            )

            files = [
                p
                for p in all_entries
                if p.is_file() and p.suffix.lower() in self.allowed_exts
            ]
            files = sorted(files, key=lambda p: p.name.lower())

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
                # Ignore hidden and system dirs
                if p.name.startswith("."):
                    continue
                
                if p.is_dir():
                    if p.name in IGNORE_DIRS:
                        continue
                        
                    # Add matching sub-directories (recursive discovery)
                    if query.lower() in p.name.lower():
                        self.items.append(FileItem(p))
                    
                    # Continue falling into subdirs
                    self._recursive_search(p, query, depth - 1)
        except (PermissionError, OSError, Exception):
            # Ignore /proc related errors and permission issues
            pass

    def _load_recents(self) -> List[Path]:
        if not self.recents_path.exists():
            return []
        try:
            with open(self.recents_path, "r") as f:
                data = json.load(f)
                return [Path(p) for p in data if Path(p).exists()]
        except:
            return []

    def _save_recents(self):
        try:
            if not self.recents_path.parent.exists():
                self.recents_path.parent.mkdir(parents=True)
            with open(self.recents_path, "w") as f:
                json.dump([str(p) for p in self.recents], f)
        except:
            pass

    def _add_to_recents(self, path: Path):
        if path in self.recents:
            self.recents.remove(path)
        self.recents.insert(0, path)
        self.recents = self.recents[:20]  # Keep last 20
        self._save_recents()

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

    def handle_event(self, event: pygame.event.Event) -> bool:
        mouse_pos = pygame.mouse.get_pos()

        lx = mouse_pos[0] - self.rect.x
        ly = mouse_pos[1] - self.rect.y

        self.search_rect.x = self.rect.x + self.sidebar_width + 10
        self.search_rect.y = self.rect.y + self.header_height + 5

        # Use dynamic file list rect that accounts for preview panel
        file_list_rect = self._get_file_list_rect()
        
        footer_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.bottom - self.footer_height,
            self.rect.width - self.sidebar_width,
            self.footer_height,
        )
        self._update_save_name_rect(footer_rect)

        # Handle ESC key to close file manager
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            # Only close if not focused on search or save name input
            if not self.is_search_focused and not self.is_save_name_focused:
                self.on_cancel_callback()
                return True
            # If focused on input, just unfocus
            if self.is_search_focused:
                self.is_search_focused = False
                return True
            if self.is_save_name_focused:
                self.is_save_name_focused = False
                return True

        # Handle window dragging
        if event.type == pygame.MOUSEMOTION:
            if self.is_dragging_window:
                self.rect.x = mouse_pos[0] - self.drag_offset_x
                self.rect.y = mouse_pos[1] - self.drag_offset_y
                return True
        
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.is_dragging_window:
                self.is_dragging_window = False
                return True

        # Handle resize interactions
        if event.type == pygame.MOUSEMOTION:
            # Check for resize handle hover and update cursor
            handle = self.resize_handler.get_handle_at_pos(mouse_pos)
            if handle:
                if handle == 'right':
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_SIZEWE)
                elif handle == 'bottom':
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_SIZENS)
                elif handle == 'corner':
                    pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_SIZENWSE)
            elif not self.resize_handler.is_dragging and not self.is_dragging_window:
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
            
            # Update drag if in progress
            if self.resize_handler.is_dragging:
                self.resize_handler.update_drag(mouse_pos)
                return True
        
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Check if starting a resize drag
            handle = self.resize_handler.get_handle_at_pos(mouse_pos)
            if handle:
                self.resize_handler.start_drag(handle, mouse_pos)
                return True
            
            # Check if starting window drag (clicking on header)
            header_rect = pygame.Rect(
                self.rect.x + self.sidebar_width,
                self.rect.y,
                self.rect.width - self.sidebar_width,
                self.header_height,
            )
            # Don't start drag if clicking on the "up" button area
            up_button_rect = pygame.Rect(self.rect.x + self.sidebar_width, self.rect.y, 40, self.header_height)
            if header_rect.collidepoint(mouse_pos) and not up_button_rect.collidepoint(mouse_pos):
                self.is_dragging_window = True
                self.drag_offset_x = mouse_pos[0] - self.rect.x
                self.drag_offset_y = mouse_pos[1] - self.rect.y
                return True
        
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            # End resize drag and persist dimensions
            if self.resize_handler.is_dragging:
                self.resize_handler.end_drag()
                self.dimension_persistence.save_dimensions(self.rect.width, self.rect.height)
                pygame.mouse.set_cursor(pygame.SYSTEM_CURSOR_ARROW)
                return True


        if event.type == pygame.MOUSEWHEEL:
            if file_list_rect.collidepoint(mouse_pos):
                max_scroll = max(
                    0, len(self.items) * self.item_height - file_list_rect.height
                )
                self.scroll_y = max(
                    0, min(self.scroll_y - (event.y * self.scroll_speed), max_scroll)
                )
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

        if event.type == pygame.KEYDOWN and self.is_save_name_focused:
            if event.key == pygame.K_BACKSPACE:
                self.save_name = self.save_name[:-1]
            elif event.key == pygame.K_ESCAPE:
                self.is_save_name_focused = False
            elif event.key == pygame.K_RETURN:
                self._attempt_save()
            elif event.unicode and event.unicode.isprintable():
                if event.unicode not in ["/", "\\"]:
                    self.save_name += event.unicode
            return True

        if event.type == pygame.KEYDOWN and self.is_search_focused:
            mods = pygame.key.get_mods()
            ctrl_held = mods & (pygame.KMOD_LCTRL | pygame.KMOD_RCTRL)
            meta_held = mods & (pygame.KMOD_LMETA | pygame.KMOD_RMETA)
            if event.key == pygame.K_BACKSPACE:
                if ctrl_held or meta_held:
                    self.search_query = ""
                else:
                    self.search_query = self.search_query[:-1]
                self.refresh_items()
            elif event.key == pygame.K_ESCAPE:
                self.is_search_focused = False
            elif event.unicode and event.unicode.isprintable():
                self.search_query += event.unicode
                self.refresh_items()
            return True

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                # Check if clicking on preview close button
                if self.image_preview.is_visible and hasattr(self.image_preview, 'close_button_rect'):
                    if self.image_preview.close_button_rect and self.image_preview.close_button_rect.collidepoint(mouse_pos):
                        self._hide_preview()
                        return True
                
                # Check if clicking on "Open in Viewer" button
                if self.image_preview.is_visible and hasattr(self.image_preview, 'open_viewer_button_rect'):
                    if self.image_preview.open_viewer_button_rect and self.image_preview.open_viewer_button_rect.collidepoint(mouse_pos):
                        self._open_image_viewer()
                        return True
                
                if lx < self.sidebar_width:
                    self._handle_sidebar_click(ly)
                    return True

                if self.search_rect.collidepoint(mouse_pos):
                    self.is_search_focused = True
                    self.is_save_name_focused = False
                    return True
                else:
                    self.is_search_focused = False
                if self.mode == "save" and self.save_name_rect.collidepoint(mouse_pos):
                    self.is_save_name_focused = True
                    return True
                else:
                    self.is_save_name_focused = False

                if ly < self.header_height:
                    if lx < self.sidebar_width + 40:
                        self.go_up()
                    return True

                if ly > self.rect.height - self.footer_height:
                    self._handle_footer_click(lx)
                    return True

                if file_list_rect.collidepoint(mouse_pos) and self.hover_index != -1:
                    idx = self.hover_index
                    item = self.items[idx]

                    current_time = pygame.time.get_ticks()

                    if (
                        self.clicked_item_index == idx
                        and (current_time - self.double_click_timer) < 500
                    ):
                        if item.is_dir:
                            self.navigate_to(item.path, record_recent=True)
                        else:
                            if self.mode == "save":
                                self.save_name = item.name
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
                                # Single click without modifiers - clear selection and select only this item
                                self.selected_indices = [idx]
                            self.selected_index = idx
                        else:
                            self.selected_index = idx
                            self.selected_indices = [idx]
                        self.clicked_item_index = idx
                        self.double_click_timer = current_time
                        if not item.is_dir and self.mode == "save":
                            self.save_name = item.name
                        
                        # Handle preview interactions - show preview for image files
                        if not item.is_dir:
                            # Check if it's an image file
                            if item.ext in ['.png', '.jpg', '.jpeg']:
                                self._show_preview(item.path)
                            else:
                                # Hide preview for non-image files
                                self._hide_preview()
                        else:
                            # Hide preview for directories
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
        
        # lx is relative to self.rect.x, but footer starts at sidebar_width
        # So we need to adjust lx to be relative to footer start
        footer_lx = lx - self.sidebar_width
        
        # Get footer rect to calculate button positions correctly
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
                    paths = []
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

    def _resolve_save_path(self) -> Optional[Path]:
        name = self.save_name.strip()
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
            # File list gets 60% of content width when preview is visible
            # But ensure minimum 40% as per requirements
            file_list_width = int(content_width * 0.6)
            # Ensure file list is at least 40% of content area
            min_file_list_width = int(content_width * 0.4)
            file_list_width = max(file_list_width, min_file_list_width)
        else:
            # Full width when preview is hidden
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
        
        # File list gets 60%, preview gets 40%
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
        # Check if file has a supported image extension
        supported_extensions = ['.png', '.jpg', '.jpeg']
        if file_path.suffix.lower() not in supported_extensions:
            return
        
        # Load the image
        self.image_preview.load_image(file_path)
    
    def _hide_preview(self):
        """Deactivates preview panel and restores full-width file list."""
        self.image_preview.clear()

    def _open_image_viewer(self):
        """Open the standalone image viewer for the current preview image."""
        if not self.image_preview.current_path:
            return

        try:
            # Get path to standalone viewer script
            viewer_script = BASE_PATH / "src" / "standalone_image_viewer.py"

            # Launch viewer as subprocess
            subprocess.Popen([
                sys.executable,
                str(viewer_script),
                str(self.image_preview.current_path)
            ])
        except Exception as e:
            print(f"Error opening image viewer: {e}")



    def draw(self, screen: pygame.Surface):
        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill(COLORS["overlay"])
        screen.blit(overlay, (0, 0))

        pygame.draw.rect(screen, COLORS["bg"], self.rect)
        pygame.draw.rect(screen, COLORS["border"], self.rect, 1)

        sidebar_rect = pygame.Rect(
            self.rect.x, self.rect.y, self.sidebar_width, self.rect.height
        )
        pygame.draw.rect(screen, COLORS["sidebar"], sidebar_rect)
        pygame.draw.line(
            screen,
            COLORS["border"],
            (sidebar_rect.right, sidebar_rect.top),
            (sidebar_rect.right, sidebar_rect.bottom),
        )

        self._draw_sidebar_items(screen, sidebar_rect)

        header_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.y,
            self.rect.width - self.sidebar_width,
            self.header_height,
        )
        pygame.draw.rect(screen, COLORS["header"], header_rect)
        pygame.draw.line(
            screen,
            COLORS["border"],
            (header_rect.left, header_rect.bottom),
            (header_rect.right, header_rect.bottom),
        )

        self._draw_header(screen, header_rect)

        # Draw Search Bar
        search_bg_rect = pygame.Rect(
            header_rect.left,
            header_rect.bottom,
            header_rect.width,
            self.search_header_height
        )
        pygame.draw.rect(screen, COLORS["bg"], search_bg_rect)
        
        self.search_rect.x = search_bg_rect.x + 10
        self.search_rect.y = search_bg_rect.y + 5
        self.search_rect.width = search_bg_rect.width - 20
        
        box_col = COLORS["selected"] if self.is_search_focused else COLORS["border"]
        pygame.draw.rect(screen, box_col, self.search_rect, border_radius=4)
        pygame.draw.rect(screen, COLORS["sidebar"], self.search_rect.inflate(-2, -2), border_radius=4)

        search_text = self.search_query
        if not search_text and not self.is_search_focused:
            search_text = "Search files..."
            search_col = COLORS["text_dim"]
        else:
            search_col = COLORS["text_main"]
            if self.is_search_focused and (pygame.time.get_ticks() // 500) % 2:
                search_text += "|"

        txt = self.font_main.render(search_text, True, search_col)
        screen.blit(txt, (self.search_rect.x + 8, self.search_rect.y + 4))

        # Use dynamic file list rect that accounts for preview panel
        file_list_rect = self._get_file_list_rect()
        self._draw_file_list(screen, file_list_rect)

        footer_rect = pygame.Rect(
            self.rect.x + self.sidebar_width,
            self.rect.bottom - self.footer_height,
            file_list_rect.width,
            self.footer_height,
        )
        self._update_save_name_rect(footer_rect)
        pygame.draw.rect(screen, COLORS["header"], footer_rect)
        pygame.draw.line(
            screen,
            COLORS["border"],
            (footer_rect.left, footer_rect.top),
            (footer_rect.right, footer_rect.top),
        )

        self._draw_footer(screen, footer_rect)

        # Draw preview panel if visible
        if self.image_preview.is_visible:
            preview_rect = self._get_preview_rect()
            self.image_preview.draw(screen, preview_rect)
        
        # Draw resize handles
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
                COLORS["selected"] if is_active else
                COLORS["highlight"]
                if btn_rect.collidepoint(mx, my)
                else COLORS["sidebar"]
            )
            pygame.draw.rect(screen, col, btn_rect, border_radius=4)

            txt = self.font_bold.render(name, True, COLORS["text_main"])
            screen.blit(txt, (rect.x + 15, y + 7))

    def _draw_header(self, screen, rect):
        up_btn = pygame.Rect(rect.x + 5, rect.y + 5, 30, 30)
        self._draw_icon_arrow_up(
            screen, up_btn.centerx, up_btn.centery, COLORS["text_main"]
        )
        parts = self.current_path.parts
        if len(parts) > 4:
            display_parts = ["..."] + list(parts[-3:])
        else:
            display_parts = list(parts)
        path_str = " / ".join(display_parts)
        txt = self.font_main.render(path_str, True, COLORS["text_dim"])
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
                pygame.draw.rect(screen, COLORS["selected"], row_rect)
            elif i == self.hover_index:
                pygame.draw.rect(screen, COLORS["highlight"], row_rect)

            icon_x = rect.x + 10
            icon_center_y = y + self.item_height // 2
            if item.is_dir:
                self._draw_icon_folder(screen, icon_x, icon_center_y - 8)
            elif item.ext in [".png", ".jpg", ".jpeg"]:
                self._draw_icon_image(screen, icon_x, icon_center_y - 8)
            else:
                self._draw_icon_file(screen, icon_x, icon_center_y - 8)

            col = (
                COLORS["text_main"] if i == self.selected_index else COLORS["text_main"]
            )
            txt = self.font_main.render(item.name, True, col)
            screen.blit(txt, (rect.x + 35, y + 7))

        screen.set_clip(clip)

        total_h = len(self.items) * self.item_height
        if total_h > rect.height:
            scroll_pct = self.scroll_y / (total_h - rect.height)
            bar_h = max(20, rect.height * (rect.height / total_h))
            bar_y = rect.y + scroll_pct * (rect.height - bar_h)

            bar_rect = pygame.Rect(rect.right - 6, bar_y, 4, bar_h)
            pygame.draw.rect(screen, COLORS["border"], bar_rect, border_radius=2)

    def _draw_footer(self, screen, rect):
        sel_txt = "No file selected"
        if self.selected_index != -1:
            sel_txt = self.items[self.selected_index].name

        txt_surf = self.font_main.render(sel_txt, True, COLORS["text_dim"])
        if self.mode == "open":
            screen.blit(txt_surf, (rect.x + 10, rect.y + 17))

        btn_w, btn_h = 80, 30
        margin = 10

        def draw_btn(x, label, accent=False):
            r = pygame.Rect(x, rect.y + 10, btn_w, btn_h)
            bg = COLORS["accent"] if accent else COLORS["highlight"]

            mx, my = pygame.mouse.get_pos()
            if r.collidepoint(mx, my):
                bg = (min(bg[0] + 20, 255), min(bg[1] + 20, 255), min(bg[2] + 20, 255))

            pygame.draw.rect(screen, bg, r, border_radius=4)
            lbl = self.font_bold.render(label, True, COLORS["text_main"])
            lbl_r = lbl.get_rect(center=r.center)
            screen.blit(lbl, lbl_r)

        cancel_x = rect.right - btn_w - margin
        open_x = cancel_x - btn_w - margin

        draw_btn(cancel_x, "Cancel")
        draw_btn(open_x, "Save" if self.mode == "save" else "Open", accent=True)

        if self.mode == "save":
            label = self.font_bold.render("File name:", True, COLORS["text_dim"])
            screen.blit(label, (rect.x + 10, rect.y + 16))

            box_col = COLORS["selected"] if self.is_save_name_focused else COLORS["border"]
            pygame.draw.rect(screen, box_col, self.save_name_rect, border_radius=4)
            pygame.draw.rect(screen, COLORS["sidebar"], self.save_name_rect.inflate(-2, -2), border_radius=4)

            display_name = self.save_name
            if self.is_save_name_focused and (pygame.time.get_ticks() // 500) % 2:
                display_name += "|"
            txt = self.font_main.render(display_name, True, COLORS["text_main"])
            screen.blit(txt, (self.save_name_rect.x + 6, self.save_name_rect.y + 6))

    def _draw_icon_folder(self, surface, x, y):
        color = COLORS["folder"]

        pygame.draw.rect(surface, color, (x, y, 8, 4))

        pygame.draw.rect(surface, color, (x, y + 4, 18, 12))

    def _draw_icon_file(self, surface, x, y):
        color = COLORS["file"]

        pygame.draw.rect(surface, color, (x + 2, y, 14, 16))

        pygame.draw.polygon(
            surface, COLORS["bg"], [(x + 16, y), (x + 16, y + 5), (x + 11, y)]
        )

    def _draw_icon_image(self, surface, x, y):
        color = COLORS["image"]
        pygame.draw.rect(surface, color, (x + 1, y + 1, 16, 14))

        pygame.draw.polygon(
            surface, COLORS["bg"], [(x + 1, y + 15), (x + 6, y + 8), (x + 10, y + 15)]
        )
        pygame.draw.polygon(
            surface, COLORS["bg"], [(x + 8, y + 15), (x + 12, y + 6), (x + 17, y + 15)]
        )

    def _draw_icon_arrow_up(self, surface, cx, cy, color):
        points = [(cx, cy - 5), (cx - 5, cy + 2), (cx + 5, cy + 2)]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.rect(surface, color, (cx - 2, cy + 2, 4, 4))
