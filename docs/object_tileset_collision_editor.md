# Object Tileset Collision Editor

A redesigned collision shape editor for object tilesets with a clear two-phase workflow.

## Overview

This editor allows you to define rectangular regions on an object tileset (a sprite sheet with multiple objects) and then paint collision polygons for each region.

### Two-Phase Workflow

1. **DEFINE REGIONS**: Draw rectangles on the tileset to define individual objects (trees, rocks, characters, etc.)
2. **PAINT COLLISION**: Select a region, then draw collision polygons specifically for that object

## UI Layout

```
+--------------------------------------------------------------+
| [Save] [Load] | Define Regions | Paint Collision | [?]    |
+---------------+--------------------------------+-------------+
| Regions List  |   Collision Painter (Region)   |  StatusBar  |
| - Tree (✓)    |                                |             |
| - Rock (⚠)    |   [Region image, zoomed]       |  3 shapes   |
| - Player (?)|                                |  Complete   |
+---------------+--------------------------------+-------------+
|           Object Tileset (Region Selector)                   |
|   [Full image with highlighted regions]                    |
+------------------------------------------------------------+
```

## Controls

### Define Regions Mode
- **Drag on tileset**: Create a new rectangular region
- **Click region**: Select it
- **Drag selected region**: Move it
- **Drag handles**: Resize the region
- **F2**: Rename selected region
- **Delete**: Remove selected region
- **Mouse wheel**: Zoom in/out
- **Middle mouse drag**: Pan view

### Paint Collision Mode
- **Left-click**: Add polygon vertex
- **Right-click or Enter**: Complete current polygon
- **Click near first vertex**: Close polygon (snap to complete)
- **Click on polygon**: Select it
- **Click on vertex**: Select for dragging
- **Delete/Backspace**: Remove selected polygon
- **O key**: Toggle one-way collision for selected polygon
- **G key**: Toggle grid
- **S key**: Toggle snap to grid
- **R key**: Reset view

### General
- **Ctrl+S**: Save collision data
- **Ctrl+L**: Load collision data
- **? or I**: Toggle help panel
- **Escape**: Close help / Quit (when help closed)

## Status Icons

In the regions list, each region shows a status icon:

- **✓ (green)**: Region has collision shapes defined
- **⚠ (yellow)**: Region is named but has no collision yet
- **? (gray)**: Region is unnamed (auto-generated name)

## Data Format

Collision data is saved as JSON:

```json
{
  "tileset_name": "objects",
  "regions": {
    "region_abc123": {
      "region_id": "region_abc123",
      "region_rect": [0, 0, 32, 32],
      "shapes": [
        {
          "type": "polygon",
          "vertices": [[0, 0], [32, 0], [32, 32], [0, 32]],
          "one_way": false
        }
      ],
      "properties": {}
    }
  }
}
```

## Launching

From the main editor:
1. Load an object-type tileset
2. Click the collision editor button

Standalone:
```bash
python -m plugins.object_tileset_collision.standalone path/to/objects.png --data-root ./data
```

## Implementation

### Components

The editor uses several reusable UI components:

1. **RegionSelector** (`widgets/ui/region_selector.py`): Draw/select rectangular regions on an image
2. **StatusBar** (`widgets/ui/status_bar.py`): Show operation state with color-coded feedback
3. **ModeIndicator** (`widgets/ui/mode_indicator.py`): Two-phase workflow mode switching
4. **CollisionPainter** (`plugins/tileset_collision/collision_painter.py`): Polygon drawing (shared with tileset editor)

### Event Priority

To prevent overlapping UI interactions:

1. Help panel (if open) - blocks everything
2. Inline text input (if renaming) - blocks region/painting ops
3. Region definition operations
4. Region selection
5. Collision painting (only active in Paint Collision mode)

Each layer returns `True` if it handled the event, preventing lower layers from receiving it.

## Files

- `editor.py`: Main editor implementation with two-phase workflow
- `models.py`: Data models (RegionCollisionData, ObjectTilesetCollisionLibrary)
- `standalone.py`: Standalone launcher
- `widgets/ui/region_selector.py`: Reusable region selection component
- `widgets/ui/status_bar.py`: Reusable status bar component
- `widgets/ui/mode_indicator.py`: Reusable mode indicator component
