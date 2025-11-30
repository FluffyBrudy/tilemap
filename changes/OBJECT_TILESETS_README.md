# 🎯 Object Tilesets Implementation - Complete Reference

## Quick Start

### What You Can Do Now

1. **Create object layers** with free-positioned objects (not grid-snapped)
2. **Designate tilesets** as either "tile" (grid-based) or "object" (free-positioned)
3. **Place objects** at exact pixel coordinates, just like Tiled editor
4. **Store real coordinates** instead of grid coordinates for objects

---

## The Implementation

### 1. Data Types

#### TypeObject - What's stored in memory
```python
class TypeObject(TypedDict, total=True):
    pos: Tuple[int, int]      # Pixel coords (x, y) - NO grid snapping
    ttype: int                # Tileset index
    tileset_type: str         # "tile" or "object" - which tileset type
    variant: int              # Sprite index in tileset
    width: int                # Object width (pixels)
    height: int               # Object height (pixels)
```

#### TilesetData - Tileset metadata
```python
class TilesetData:
    name: str                 # Filename
    path: Path                # File path
    surface: pygame.Surface   # Image data
    tileset_type: str         # "tile" or "object"
    offset: List[int]         # Pan offset in selector UI
```

---

### 2. Dialog Flow

When adding a tileset:
```
User clicks "Add Tileset"
    ↓
File manager opens
    ↓
User selects image
    ↓
NEW: Tileset Type Dialog appears
    ┌─────────────────────┐
    │ Tile Tileset        │
    │ ◉ Tile Tileset      │ 
    │ ○ Object Tileset    │
    │ [OK] [Cancel]       │
    └─────────────────────┘
    ↓
User selects type
    ↓
Tileset added with tileset_type="tile" or "object"
```

---

### 3. Placement Logic

#### When you click on canvas:

**Scenario 1: Tile Layer + Tile Tileset**
```
→ Use _place_tile_grid()
→ Place at grid position (5, 3)
→ Store as TypeTile in layer.tiles[(5,3)]
```

**Scenario 2: Object Layer + Tile Tileset**
```
→ Use _place_tile_grid() 
→ Click at grid (5, 3) = pixel (160, 96)
→ Create TypeObject at pixel (160, 96)
→ Object has tileset_type="tile"
```

**Scenario 3: Object Layer + Object Tileset** ⭐ **NEW**
```
→ Use _place_object_free()
→ Click at pixel (157, 93)
→ Create TypeObject at EXACT pixel (157, 93)
→ NO GRID SNAPPING
→ Object has tileset_type="object"
```

---

### 4. Rendering

```python
# Get active layer
active_layer = tilemap.layer_manager.get_active_layer()

if active_layer.layer_type == "tile":
    # Render grid-aligned tiles
    for x, y in grid_positions:
        tile = active_layer.get_tile((x, y))
        render_at_grid(tile, x, y)

elif active_layer.layer_type == "object":
    # Render free-positioned objects
    for obj_id, obj in active_layer.get_all_objects().items():
        px, py = obj["pos"]  # ← PIXEL coordinates!
        render_at_pixel(obj, px, py)
```

---

## How to Use

### Step 1: Create Map with Object Layer

```python
# In your code or through UI:
tilemap.layer_manager.create_layer("Objects", layer_type="object")
```

### Step 2: Add Object Tileset

```
1. Click "Add Tileset"
2. Select image file (e.g., enemies.png)
3. Dialog: Select "Object Tileset"
4. Click OK
```

### Step 3: Place Objects

```
1. Select "Objects" layer
2. Select object tileset
3. Click at pixel position (x, y)
4. Object placed at EXACT position - no grid snapping!
5. Right-click to remove
```

### Result

Objects are stored as:
```json
{
  "pos": [157, 93],
  "ttype": 2,
  "tileset_type": "object",
  "variant": 5,
  "width": 32,
  "height": 48
}
```

**Key:** `pos` is EXACT pixel position, not grid-aligned!

---

## File Changes Summary

### New Files
- `src/widgets/ui/tileset_type_dialog.py` - Dialog for selecting tileset type

### Modified Files

**src/ttypes/tilemap.py**
- Added `tileset_type: str` to TypeObject
- Changed `ttype` from `str` to `int` for TypeObject
- Updated TypeObjectSerialized

**src/widgets/tile_selector.py**
- Added `tileset_type` parameter to TilesetData
- Modified tileset loading to show dialog
- Added `_on_tileset_type_selected()` callback

**src/editor.py**
- Imported TilesetTypeDialog
- Added tileset_type_dialog instance
- Integrated dialog into event handling and rendering

**src/widgets/tile_grid.py**
- Refactored `place_tile()` to support both paths
- Added `_place_tile_grid()` for grid placement
- Added `_place_object_free()` for free placement
- Updated `remove_tile()` to handle objects
- Updated `render()` to render both tile and object layers

---

## Key Features

✅ **Free Positioning** - Objects at exact pixel coords (e.g., 157, 93)  
✅ **No Grid Snapping** - Complete pixel-perfect control  
✅ **Tileset Type Tracking** - Know which type each object uses  
✅ **Backward Compatible** - All existing maps work unchanged  
✅ **Tiled-Like** - Works like industry-standard editor  
✅ **Flexible** - Can use tile tilesets on object layers too  

---

## Data Flow

```
User adds tileset
    ↓
Dialog asks: Tile or Object?
    ↓
Tileset created with tileset_type
    ↓
User selects layer + tileset
    ↓
User clicks canvas
    ↓
Check: Is layer object? Is tileset object?
    ↓
YES → Free placement (_place_object_free)
    ↓
NO  → Grid placement (_place_tile_grid)
    ↓
Object/Tile stored with metadata
    ↓
Render layer using correct method
```

---

## Important Notes

### Position Storage

**Tile Layer:**
```python
tiles = {
    (5, 3): {           # ← Grid coordinates as KEY
        "pos": (5, 3),
        "ttype": "0",
        "variant": 5
    }
}
```

**Object Layer:**
```python
objects = {
    1: {                # ← Object ID as key
        "pos": (157, 93),   # ← PIXEL coordinates in value
        "ttype": 2,
        "tileset_type": "object",
        "variant": 5,
        "width": 32,
        "height": 32
    }
}
```

### Key Difference

Objects store **exact pixel positions**, not grid-aligned!

---

## Testing Checklist

- [ ] Create new project
- [ ] Create object layer
- [ ] Add object tileset (select "Object Tileset" type)
- [ ] Click at various pixel positions
- [ ] Verify objects placed at exact positions
- [ ] Verify no grid snapping
- [ ] Right-click to remove objects
- [ ] Scroll canvas, objects render correctly
- [ ] Load old map, still works
- [ ] Place tile tileset on object layer, works

---

## Future Enhancements

These are NOT implemented yet, but the foundation supports them:

- [ ] Drag objects to reposition (pixel-perfect)
- [ ] Multi-select objects
- [ ] Copy/paste objects
- [ ] Object properties panel
- [ ] Rotation/scale per object
- [ ] Snap-to-grid toggle
- [ ] Collision shape definition
- [ ] Z-ordering per object

---

## Troubleshooting

### Objects not appearing?
1. Check active layer is object layer: `layer.layer_type == "object"`
2. Check objects exist: `layer.get_all_objects()`
3. Check tileset loaded: `tileset_widget.tilesets`
4. Check variant ID is valid

### Objects snapped to grid?
1. Confirm you selected "Object Tileset" type when adding tileset
2. Check `tileset_data.tileset_type == "object"`
3. Verify `_place_object_free()` is being called

### Dialog not appearing?
1. Check editor has `tileset_type_dialog` instance
2. Check event handler includes dialog
3. Check draw method includes dialog

---

## API Reference

### Layer Methods

```python
layer = tilemap.layer_manager.get_active_layer()

# Tile operations
layer.set_tile((x, y), tile_data)
tile = layer.get_tile((x, y))
layer.remove_tile((x, y))
layer.get_all_tiles()

# Object operations
obj_id = layer.add_object((px, py), obj_data)
obj = layer.get_object(obj_id)
layer.remove_object(obj_id)
layer.get_all_objects()
layer.move_object(obj_id, (new_px, new_py))
```

### TileGrid Methods

```python
# Get selected brush/tileset
tileset_idx, tileset_data, rect = self.get_selected_brush()

# Check tileset type
if tileset_data.tileset_type == "object":
    # Free positioning
else:
    # Grid alignment
```

---

## Conclusion

You now have **Tiled-like object placement** in your editor!

Objects on object layers can be placed at **any pixel position**, not just grid-aligned. The system automatically distinguishes between tile and object tilesets, so you know what kind of placement to expect.

**Perfect for:** Game objects, NPCs, decorations, props, items, etc.

