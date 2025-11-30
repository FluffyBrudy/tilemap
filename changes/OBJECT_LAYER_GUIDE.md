# 🎯 Object Layer System - Implementation Guide

## Overview

The tilemap system now supports two distinct layer types:

1. **Tile Layers** - Grid-aligned tiles (traditional tilemap)
2. **Object Layers** - Free-placement objects (draggable, pixel-perfect)

---

## Layer Types

### Tile Layer
```
Properties:
- Tiles snap to grid (grid_x, grid_y)
- Fixed tile size per project
- Storage: Dict[Tuple[grid_x, grid_y], TypeTile]
- Behavior: Place & forget (movable only via drag-to-grid)

Example:
┌─────┬─────┬─────┐
│ [0] │ [1] │ [2] │  Grid coordinates
├─────┼─────┼─────┤
│ [3] │ [4] │ [5] │
└─────┴─────┴─────┘
```

### Object Layer
```
Properties:
- Objects placed at pixel coordinates (px_x, px_y)
- No snapping - true pixel-perfect placement
- Objects have width & height for rendering/collision
- Draggable: move after placement
- Storage: Dict[object_id, TypeObject]
- Behavior: Place, then drag to reposition freely

Example:
┌──────────────────────────┐
│  (50,20)◆           (150,30)★ │  Pixel coordinates
│                              │  No grid snapping
│    (100,80)■                 │
└──────────────────────────┘
```

---

## Data Structures

### TypeObject (New)
```python
class TypeObject(TypedDict):
    pos: Tuple[int, int]  # Pixel position (x, y)
    ttype: str            # Tileset index
    variant: int          # Which sprite in tileset
    width: int            # Object width in pixels
    height: int           # Object height in pixels
```

### Layer Class Updates
```python
class Layer:
    # Existing
    tiles: Dict[Tuple[int, int], TypeTile]  # For tile layers
    
    # New
    objects: Dict[int, TypeObject]           # For object layers
    next_object_id: int                      # Auto-increment ID
    
    # New Methods
    add_object(pos, obj) -> int              # Returns object ID
    get_object(obj_id) -> TypeObject
    remove_object(obj_id) -> bool
    move_object(obj_id, new_pos) -> bool
    get_all_objects() -> Dict[int, TypeObject]
```

---

## Placement Behavior

### When on TILE Layer

**With Tile Tileset:**
```
1. User selects tileset (tile-sized)
2. User clicks on grid
3. Full tile placed at grid position
4. Result: Grid-aligned tile
```

**With Object Tileset:**
```
1. User selects tileset (object-sized)
2. User clicks "Slice" button (new)
3. User selects 1 sprite from tileset
4. User clicks on grid
5. Selected sprite placed at grid position (as 1 tile)
6. Result: Object-sized sprite on grid
```

### When on OBJECT Layer

**With Tile Tileset:**
```
1. User selects tileset (tile-sized)
2. User clicks "Slice" button (new)
3. User selects 1 tile from tileset
4. User clicks at pixel coordinate
5. Selected tile placed at exact pixel position
6. Result: Object with dimensions from selected tile
```

**With Object Tileset:**
```
1. User selects tileset (object-sized)
2. User clicks "Slice" button (new)
3. User selects 1 object from tileset
4. User clicks at pixel coordinate
5. Selected object placed at exact pixel position
6. Result: Object with correct width/height
7. User can drag to reposition freely
```

---

## UI/UX Flow

### Tileset Selection Dialog (New)

When adding a tileset, user chooses:

```
┌──────────────────────────────┐
│ New Tileset                   │
├──────────────────────────────┤
│ File: [terrain.png]           │
│ Tile Size: 32 x 32            │
│                                │
│ Layer Type:                    │
│ [O] Tile Tileset              │
│ [ ] Object Tileset            │
│                                │
│ [OK] [Cancel]                  │
└──────────────────────────────┘
```

**Tile Tileset:**
- Contains grid of tiles
- Each position = full tile
- Used for traditional tilemap terrain

**Object Tileset:**
- Contains individual sprites
- Each position = single object
- Used for decorations, characters, items

### Slicing Dialog (New)

When on object layer or placing from different tileset type:

```
┌──────────────────────────────┐
│ Select Sprite                 │
├──────────────────────────────┤
│ [Tileset Preview]             │
│ Click on sprite to select      │
│                                │
│ Selected: Sprite 5             │
│ Size: 64 x 48 pixels           │
│                                │
│ [OK] [Cancel]                  │
└──────────────────────────────┘
```

---

## Placement Implementation

### TileGrid Changes Needed

**Current (Tile Layer):**
```python
def place_tile(self):
    # Get grid position
    grid_pos = self.get_grid_pos(mouse_pos)
    
    # Place at grid position
    tilemap.ongrid_tiles[grid_pos] = tile_data
```

**New (Layer-aware):**
```python
def place_tile(self):
    active_layer = tilemap.layer_manager.get_active_layer()
    
    if active_layer.layer_type == "tile":
        # Tile layer: snap to grid
        grid_pos = self.get_grid_pos(mouse_pos)
        active_layer.set_tile(grid_pos, tile_data)
    
    elif active_layer.layer_type == "object":
        # Object layer: free pixel placement
        pixel_pos = self.screen_to_world(mouse_pos)
        obj_id = active_layer.add_object(pixel_pos, object_data)
```

---

## Dragging Objects

### Object Layer Dragging (New)

```python
def handle_event(self, event):
    # Object selection/dragging
    if layer.layer_type == "object":
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Check if clicking on object
            obj_id = self._get_object_at_pos(pos)
            if obj_id is not None:
                self.selected_object_id = obj_id
                self.dragging_object = True
        
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging_object:
                new_pos = self.screen_to_world(mouse_pos)
                active_layer.move_object(self.selected_object_id, new_pos)
        
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging_object = False
```

### Collision Detection (New)

```python
def _get_object_at_pos(self, pixel_pos: Tuple[int, int]) -> Optional[int]:
    """Check if mouse is on any object, return object ID."""
    for obj_id, obj in active_layer.objects.items():
        obj_x, obj_y = obj["pos"]
        obj_w, obj_h = obj["width"], obj["height"]
        
        # Check if pixel_pos is within object bounds
        if (obj_x <= pixel_pos[0] < obj_x + obj_w and
            obj_y <= pixel_pos[1] < obj_y + obj_h):
            return obj_id
    
    return None
```

---

## Serialization

### Save Format (v1.1+)

```json
{
  "meta": {"tile_size": "32;32", "map_size": "30;20", "version": "1.1"},
  "data": {
    "layers": [
      {
        "name": "Terrain",
        "type": "tile",
        "tiles": {
          "0;0": {"pos": "(0,0)", "ttype": "0", "variant": 5},
          "1;0": {"pos": "(1,0)", "ttype": "0", "variant": 6}
        },
        "objects": {},
        "next_object_id": 1
      },
      {
        "name": "Decorations",
        "type": "object",
        "tiles": {},
        "objects": {
          "1": {"pos": "(50,20)", "ttype": "1", "variant": 3, "width": 64, "height": 48},
          "2": {"pos": "(150,30)", "ttype": "1", "variant": 5, "width": 64, "height": 48}
        },
        "next_object_id": 3
      }
    ]
  }
}
```

---

## Implementation Phases

### Phase 1: Foundation (DONE)
- [x] Extended TypeTile to TypeObject
- [x] Added object storage to Layer class
- [x] Implemented object CRUD operations
- [x] Updated serialization (to_dict/from_dict)

### Phase 2: TileGrid Integration (TODO)
- [ ] Layer type awareness in TileGrid
- [ ] Tile layer placement (grid snapping)
- [ ] Object layer placement (free pixels)
- [ ] Object selection/dragging
- [ ] Collision detection for objects

### Phase 3: UI Dialogs (TODO)
- [ ] Tileset type selection dialog
- [ ] Sprite slicing dialog
- [ ] Object property editor (width/height)

### Phase 4: Rendering (TODO)
- [ ] Render objects with proper bounds
- [ ] Visual selection indicator
- [ ] Drag preview
- [ ] Layer sorting (by z_index)

### Phase 5: Advanced (TODO)
- [ ] Object copy/paste
- [ ] Object grouping
- [ ] Object naming
- [ ] Object collision shapes
- [ ] Export per-layer

---

## Code Example: Adding Objects

```python
from layers import Layer
from ttypes.tilemap import TypeObject

# Create object layer
obj_layer = Layer("Decorations", "object")

# Add an object
obj_data = TypeObject(
    pos=(50, 20),
    ttype="1",  # Tileset index
    variant=5,  # Which sprite
    width=64,
    height=48
)
obj_id = obj_layer.add_object((50, 20), obj_data)

# Move object
obj_layer.move_object(obj_id, (100, 30))

# Get object
obj = obj_layer.get_object(obj_id)
print(f"Object at {obj['pos']}, size {obj['width']}x{obj['height']}")

# Remove object
obj_layer.remove_object(obj_id)

# Save & load
layer_dict = obj_layer.to_dict()
obj_layer2 = Layer.from_dict(layer_dict)
```

---

## Next Steps

1. **Phase 2 (TileGrid)**: Implement layer-aware placement
2. **Phase 3 (Dialogs)**: Create tileset type selection UI
3. **Phase 4 (Rendering)**: Render objects on tile layers
4. **Phase 5 (Polish)**: Add advanced features

---

## Questions?

Key concepts:
- **Tile Layer**: Grid-aligned, fixed positioning, traditional tilemap
- **Object Layer**: Pixel-perfect, draggable, free placement
- **Slicing**: Converting from full tileset to single sprite selection
- **Object ID**: Unique identifier for each object (auto-increment)

All object layer functionality is transparent to existing code - backward compatible! ✅

