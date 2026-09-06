# Tileset Collision Editor

Godot-style polygon collision editor for tileset tiles.

## Features

- **Godot-like Workflow**: Select tiles from bottom panel, paint collision in middle, see painted tiles in side panel
- **Multi-Select**: Select multiple tiles and paint collision on all at once (Ctrl+click)
- **Persistent Collision**: Collision persists when switching tiles (like Godot)
- **Resizable Panels**: Drag handle to resize tileset selector
- **Zoom & Pan**: Mouse wheel to zoom, Space+Mouse or Middle-mouse to pan
- **One-Way Collision**: Toggle one-way platforms (press O)
- **Visual Feedback**: Blue for normal collision, red for one-way, orange for selected

## Layout

```
+----------------------------------------------------+
| Toolbar: [Save] [Load] [Clear Current]            |
+---------------+------------------------------------+
| Painted Tiles |     Collision Painter              |
| (side list)   |     (polygon drawing area)         |
|               |                                    |
+---------------+------------------------------------+
|          Tileset Selector (resizable)             |
|          (scrollable, zoomable, click to select)  |
+----------------------------------------------------+
```

## Usage

### From Main Editor

1. Load a tileset in the main editor
2. Click the "C" button in the tile selector bottom bar
3. The collision editor opens in a new window

Or:

1. Go to **Tools → Tileset Collision Editor** (if no tileset loaded, shows notification)

### Standalone

```bash
# Basic usage
python -m plugins.tileset_collision.standalone path/to/tileset.png

# With tile size
python -m plugins.tileset_collision.standalone path/to/tileset.png --tile-size 16x16

# Load existing collision data
python -m plugins.tileset_collision.standalone path/to/tileset.png --load collision.json

# Custom window size
python -m plugins.tileset_collision.standalone path/to/tileset.png --window-size 1400x900
```

## Workflow (Godot-style)

1. **Select Tiles**: Click tiles in the bottom tileset selector
   - Single-select: Click a tile
   - Multi-select: Ctrl+click multiple tiles
   - Pan: Space+Left mouse or Middle mouse
   - Zoom: Mouse wheel
   - Recenter: Press H

2. **Paint Collision**: Draw polygons in the middle collision painter
   - Click to add vertices
   - Right-click or Enter to complete polygon
   - Collision is applied to ALL selected tiles

3. **View Painted Tiles**: Side panel shows only tiles with collision
   - Click a painted tile to select and edit it
   - Shows shape count for each tile

4. **Edit Collision**: Select painted tiles to modify their collision
   - Drag vertices to adjust shape
   - Press O to toggle one-way collision
   - Delete/Backspace to remove selected polygon
   - Shift+Delete to clear all collision from selected tiles

## Controls

### Bottom Panel (Tileset Selector)

- **Left-click**: Select tile (Ctrl+click for multi-select)
- **Space+Left mouse** or **Middle mouse**: Pan view
- **Mouse wheel**: Zoom in/out
- **H**: Recenter view
- **Drag resize handle**: Resize panel height

### Middle Panel (Collision Painter)

- **Left-click**: Add vertex to polygon
- **Right-click** or **Enter**: Complete polygon
- **Escape**: Cancel current polygon
- **Click polygon**: Select polygon
- **Drag vertex**: Move vertex
- **Drag inside polygon**: Move the whole shape (Esc restores)
- **Delete/Backspace**: Remove selected polygon
- **Shift+Delete**: Clear collision for selected tiles
- **O**: Toggle one-way collision (selected polygon)
- **G**: Toggle grid
- **S**: Toggle snap to grid
- **R**: Reset view
- **Middle mouse**: Pan view
- **Mouse wheel**: Zoom

### Side Panel (Painted Tiles)

- **Click**: Select painted tile
- **Mouse wheel**: Scroll list
- Shows only tiles with collision data

### File Operations

- **Ctrl+S**: Save collision data
- **Ctrl+L**: Load collision data
- **Escape**: Close editor

## Visual Feedback

### Polygon Colors

- **Blue**: Normal collision (blocks from all directions)
- **Red**: One-way collision (blocks from top only)
- **Orange**: Selected polygon
- **Green**: First vertex of current polygon

### Tileset Selector

- **Blue border**: Selected tile(s)
- **Small dot in corner**: Tile has collision data

## Data Format

Collision data is saved as JSON with `.collision.json` extension:

```json
{
  "tileset_name": "terrain",
  "tile_size": [32, 32],
  "tiles": {
    "0": {
      "tile_id": 0,
      "shapes": [
        {
          "vertices": [[0, 16], [32, 16], [32, 32], [0, 32]],
          "one_way": false
        }
      ]
    },
    "5": {
      "tile_id": 5,
      "shapes": [
        {
          "vertices": [[0, 0], [32, 0], [32, 8], [0, 8]],
          "one_way": true
        }
      ]
    }
  }
}
```

See `COLLISION_DATA_FORMAT.md` for complete specification and runtime parsing examples.

## File Naming Convention

Collision data files are saved next to the tileset image:

- `terrain.png` → `terrain.collision.json`
- `dungeon.png` → `dungeon.collision.json`

The editor automatically looks for and loads existing collision data when opening a tileset.

## Tips

### Efficient Workflow

1. **Multi-select similar tiles**: Select all platform tiles at once, draw collision once
2. **Use one-way for platforms**: Press O to make jump-through platforms
3. **Snap to grid**: Press S to enable grid snapping for precise alignment
4. **Zoom in for detail**: Use mouse wheel to zoom in for precise vertex placement
5. **Recenter often**: Press H to recenter view when lost

### Common Patterns

**Solid Block**:
```
Draw rectangle covering entire tile
```

**Platform (one-way)**:
```
Draw thin rectangle at top of tile
Press O to make it one-way
```

**Slope**:
```
Draw triangle following the slope angle
Mirror it to the other side with the Flip X / Flip Y checkboxes
(previewed in the painter; stored per tile as flip_x/flip_y)
```

**Complex Terrain**:
```
Draw polygon following the terrain contour
Use multiple polygons for holes/gaps
```

## Integration

The editor uses the same architecture as other plugins:

- **Standalone subprocess**: Runs independently from main editor
- **Centralized managers**: Uses FontManager, IconManager, ErrorHandler
- **Protocol-based**: Loose coupling via duck-typed protocols
- **Auto-save**: Collision data saved automatically when switching tiles

## Architecture

See `ARCHITECTURE.md` for detailed technical documentation.

## One-Way Collision

One-way collision is useful for:
- Jump-through platforms
- Ladders
- Moving platforms
- Slopes you can walk up but fall through

When `one_way` is true:
- Collision blocks objects moving downward (landing on top)
- Objects can pass through from below, left, and right

Visual indicator: Red polygons are one-way, blue are solid.

## Performance Notes

For runtime parsing:
- Cache collision data, don't reload every frame
- Use spatial partitioning (quadtree/grid) for large tilemaps
- Only check collision for visible/nearby tiles
- Use bounding boxes for broad-phase collision detection

See `COLLISION_DATA_FORMAT.md` for optimization strategies.
