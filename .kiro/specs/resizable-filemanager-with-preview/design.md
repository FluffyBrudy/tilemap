# Design Document: Resizable FileManager with Preview

## Overview

This design enhances the existing FileManager widget in the Python-based tilemap editor to support dynamic resizing and PNG image preview capabilities. The FileManager is a modal dialog widget built with pygame that allows users to browse directories and select files.

The enhancement adds three major capabilities:
1. **Resizable widget** - Users can drag handles to adjust the FileManager dimensions, with constraints to maintain usability
2. **Image preview panel** - When users click on image files (.png, .jpg, .jpeg), a preview panel displays the image content
3. **State persistence** - The FileManager remembers user-preferred dimensions across application sessions

The design maintains the existing FileManager architecture while adding new components for resize handling, image loading/rendering, and layout management for the preview panel.

## Architecture

### Component Structure

The FileManager widget follows a single-class design pattern consistent with other widgets in the application. The enhancement extends this pattern with new subsystems:

```
FileManager
├── Core State (existing)
│   ├── File navigation
│   ├── Selection management
│   └── Search functionality
├── Resize System (new)
│   ├── Resize handle detection
│   ├── Drag state management
│   └── Dimension constraints
├── Preview System (new)
│   ├── Image loading
│   ├── Image caching
│   ├── Preview rendering
│   └── Error handling
└── Persistence System (new)
    ├── Dimension storage
    └── Dimension restoration
```

### Layout Architecture

The FileManager uses a fixed layout structure that will be enhanced to support dynamic sizing:

**Current Layout:**
```
┌─────────────────────────────────────┐
│ Sidebar │ Header                    │
│         ├───────────────────────────┤
│         │ Search Bar                │
│         ├───────────────────────────┤
│         │ File List                 │
│         │                           │
│         ├───────────────────────────┤
│         │ Footer (buttons)          │
└─────────────────────────────────────┘
```

**Enhanced Layout (with preview):**
```
┌─────────────────────────────────────────────┐
│ Sidebar │ Header                            │
│         ├───────────────────────────────────┤
│         │ Search Bar                        │
│         ├──────────────────┬────────────────┤
│         │ File List        │ Preview Panel  │
│         │                  │ [Image]        │
│         │                  │ [Dimensions]   │
│         │                  │ [Close Button] │
│         ├──────────────────┴────────────────┤
│         │ Footer (buttons)                  │
└─────────────────────────────────────────────┘
```

### Resize Handle Placement

The resize handles will be positioned at:
- **Right edge** - Primary resize handle for width adjustment
- **Bottom edge** - Secondary resize handle for height adjustment  
- **Bottom-right corner** - Diagonal resize handle for simultaneous width/height adjustment

This placement follows standard UI conventions and provides intuitive resize interactions.

### Event Flow

**Resize Event Flow:**
1. User hovers over resize handle → Cursor changes to resize indicator
2. User clicks and drags → Widget dimensions update in real-time
3. Dimensions are constrained to minimum values (400x300)
4. On mouse release → New dimensions are persisted to disk

**Preview Event Flow:**
1. User clicks on image file in list → Preview system activates
2. Image file is loaded asynchronously (if > 1MB) or synchronously (if < 1MB)
3. Image is scaled to fit preview panel while maintaining aspect ratio
4. Preview panel is rendered with image, dimensions text, and close button
5. File list layout adjusts to accommodate preview panel (60/40 split)

## Components and Interfaces

### ResizeHandler Component

**Responsibilities:**
- Detect mouse hover over resize handles
- Manage drag state during resize operations
- Apply dimension constraints
- Update widget rect in real-time

**Interface:**
```python
class ResizeHandler:
    def __init__(self, widget_rect: pygame.Rect, min_width: int, min_height: int):
        self.widget_rect = widget_rect
        self.min_width = min_width
        self.min_height = min_height
        self.is_dragging = False
        self.drag_handle = None  # 'right', 'bottom', 'corner'
        self.drag_start_pos = None
        self.drag_start_rect = None
    
    def get_handle_at_pos(self, pos: Tuple[int, int]) -> Optional[str]:
        """Returns handle type if pos is over a resize handle, else None"""
        pass
    
    def start_drag(self, handle: str, pos: Tuple[int, int]):
        """Initiates resize drag operation"""
        pass
    
    def update_drag(self, pos: Tuple[int, int]) -> pygame.Rect:
        """Updates widget rect during drag, returns new rect"""
        pass
    
    def end_drag(self):
        """Completes resize drag operation"""
        pass
    
    def draw_handles(self, surface: pygame.Surface):
        """Renders resize handles on the widget"""
        pass
```

**Handle Detection:**
- Right edge: 5-pixel wide vertical strip along right edge
- Bottom edge: 5-pixel tall horizontal strip along bottom edge
- Corner: 10x10 pixel square at bottom-right corner

### ImagePreview Component

**Responsibilities:**
- Load image files from disk
- Scale images to fit preview panel
- Render preview with metadata
- Handle loading errors gracefully

**Interface:**
```python
class ImagePreview:
    def __init__(self, max_file_size_mb: int = 50):
        self.current_image = None  # pygame.Surface
        self.current_path = None  # Path
        self.image_dimensions = None  # Tuple[int, int]
        self.error_message = None  # Optional[str]
        self.max_file_size_mb = max_file_size_mb
        self.is_visible = False
    
    def load_image(self, path: Path) -> bool:
        """Loads image from path, returns success status"""
        pass
    
    def clear(self):
        """Clears current preview"""
        pass
    
    def scale_to_fit(self, target_width: int, target_height: int) -> pygame.Surface:
        """Returns scaled image surface maintaining aspect ratio"""
        pass
    
    def draw(self, surface: pygame.Surface, rect: pygame.Rect):
        """Renders preview panel with image, metadata, and close button"""
        pass
```

**Image Loading Strategy:**
- Check file size before loading
- If > 50MB, display "file too large" message without loading
- Use pygame.image.load() for supported formats
- Catch and handle pygame.error for corrupted files
- Cache loaded image to avoid reloading on panel resize

### DimensionPersistence Component

**Responsibilities:**
- Save widget dimensions to disk
- Load widget dimensions on initialization
- Handle missing or corrupted preference files

**Interface:**
```python
class DimensionPersistence:
    def __init__(self, pref_file: Path):
        self.pref_file = pref_file
    
    def save_dimensions(self, width: int, height: int):
        """Persists dimensions to JSON file"""
        pass
    
    def load_dimensions(self) -> Optional[Tuple[int, int]]:
        """Loads dimensions from JSON file, returns None if not found"""
        pass
```

**Storage Format:**
```json
{
  "filemanager_width": 600,
  "filemanager_height": 400
}
```

**Storage Location:**
- File: `{BASE_PATH}/data/filemanager_prefs.json`
- Same directory as existing recents.json file

### FileManager Integration

The FileManager class will be enhanced with:

**New Attributes:**
```python
self.resize_handler = ResizeHandler(self.rect, min_width=400, min_height=300)
self.image_preview = ImagePreview(max_file_size_mb=50)
self.dimension_persistence = DimensionPersistence(BASE_PATH / "data" / "filemanager_prefs.json")
self.preview_visible = False
```

**Modified Methods:**
- `__init__()` - Initialize new components, load saved dimensions
- `handle_event()` - Add resize handle detection and drag handling
- `draw()` - Render resize handles and preview panel
- `_draw_file_list()` - Adjust layout when preview is visible

**New Methods:**
```python
def _handle_resize_event(self, event: pygame.event.Event) -> bool:
    """Processes resize-related events"""
    pass

def _show_preview(self, file_path: Path):
    """Activates preview panel for given image file"""
    pass

def _hide_preview(self):
    """Deactivates preview panel"""
    pass

def _get_file_list_rect(self) -> pygame.Rect:
    """Returns rect for file list, accounting for preview panel"""
    pass

def _get_preview_rect(self) -> pygame.Rect:
    """Returns rect for preview panel"""
    pass
```

## Data Models

### ResizeState

Tracks the current state of resize operations:

```python
@dataclass
class ResizeState:
    is_dragging: bool
    handle_type: Optional[str]  # 'right', 'bottom', 'corner', None
    drag_start_pos: Optional[Tuple[int, int]]
    drag_start_rect: Optional[pygame.Rect]
```

### PreviewState

Tracks the current state of the preview panel:

```python
@dataclass
class PreviewState:
    is_visible: bool
    image_surface: Optional[pygame.Surface]
    image_path: Optional[Path]
    original_dimensions: Optional[Tuple[int, int]]
    error_message: Optional[str]
    close_button_rect: Optional[pygame.Rect]
```

### DimensionPreferences

Persisted user preferences for widget dimensions:

```python
@dataclass
class DimensionPreferences:
    width: int
    height: int
    
    def to_dict(self) -> dict:
        return {"filemanager_width": self.width, "filemanager_height": self.height}
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DimensionPreferences':
        return cls(
            width=data.get("filemanager_width", 600),
            height=data.get("filemanager_height", 400)
        )
```

### Layout Calculations

The layout system uses these calculations to position elements:

**File List Width (when preview visible):**
```python
content_width = self.rect.width - self.sidebar_width
file_list_width = max(int(content_width * 0.4), 200)  # Minimum 200px
preview_width = content_width - file_list_width
```

**Preview Panel Position:**
```python
preview_x = self.rect.x + self.sidebar_width + file_list_width
preview_y = self.rect.y + self.header_height + self.search_header_height
preview_width = content_width - file_list_width
preview_height = self.rect.height - self.header_height - self.footer_height - self.search_header_height
```

**Image Scaling:**
```python
def calculate_scaled_dimensions(
    image_width: int, 
    image_height: int, 
    target_width: int, 
    target_height: int
) -> Tuple[int, int]:
    """Returns scaled dimensions maintaining aspect ratio"""
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
    
    return (new_width, new_height)
```

