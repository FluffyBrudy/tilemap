# Character Collision Editor

Visual editor for defining collision shapes for character sprites.

## Features

- **3 Shape Types**: Rectangle, Circle, and Capsule
- **Visual Editing**: Interactive handles for adjusting shape properties
- **Grid & Snap**: Optional grid overlay with snap-to-grid
- **Zoom & Pan**: Mouse wheel to zoom, middle-mouse to pan
- **Save/Load**: JSON format for collision data

## Usage

### From Main Editor

1. Open the main tilemap editor
2. Go to **Tools → Character Collision Editor**
3. Select a character sprite image
4. The editor opens in a new window

### Standalone

```bash
# Basic usage
python -m plugins.character_collision.standalone path/to/character.png

# With character name
python -m plugins.character_collision.standalone path/to/character.png --name "Player"

# Load existing collision data
python -m plugins.character_collision.standalone path/to/character.png --load collision.json

# Custom window size
python -m plugins.character_collision.standalone path/to/character.png --window-size 1200x900
```

## Controls

### Shape Selection
- Click shape type buttons (Rectangle, Circle, Capsule) to switch

### Rectangle Shape
- Drag corner handles to resize
- Drag to reposition

### Circle Shape
- Drag center handle to move
- Drag radius handle to resize

### Capsule Shape
- Drag top/bottom handles to adjust height
- Drag radius handle to adjust width

### View Controls
- **Mouse Wheel**: Zoom in/out
- **Middle Mouse**: Pan view
- **G**: Toggle grid
- **R**: Reset view

### File Operations
- **Ctrl+S**: Save collision data
- **Ctrl+L**: Load collision data
- **Escape**: Close editor

## Data Format

Collision data is saved as JSON:

```json
{
  "name": "Player",
  "shape": {
    "type": "rectangle",
    "width": 16.0,
    "height": 24.0,
    "offset": [0.0, 0.0]
  },
  "properties": {}
}
```

### Shape Types

**Rectangle**:
```json
{
  "type": "rectangle",
  "width": 16.0,
  "height": 24.0,
  "offset": [0.0, 0.0]
}
```

**Circle**:
```json
{
  "type": "circle",
  "radius": 12.0,
  "offset": [16.0, 16.0]
}
```

**Capsule**:
```json
{
  "type": "capsule",
  "radius": 8.0,
  "height": 16.0,
  "offset": [16.0, 8.0]
}
```

## Integration

The editor uses the same architecture as the tileset collision editor:

- **Standalone subprocess**: Runs independently from main editor
- **Centralized managers**: Uses FontManager, IconManager, ErrorHandler
- **Protocol-based**: Loose coupling via duck-typed protocols

## File Naming Convention

Collision data files are saved with `.collision.json` extension:
- `player.png` → `player.collision.json`
- `enemy.png` → `enemy.collision.json`

The editor automatically looks for and loads existing collision data when opening a sprite.

## Notes

Polygon shapes are intentionally omitted for character collision to keep the collision detection simple and performant. For complex character shapes, use a capsule which provides good approximation for most humanoid characters.
