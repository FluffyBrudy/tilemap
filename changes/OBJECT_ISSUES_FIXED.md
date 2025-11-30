## ✅ Object Tileset Issues Fixed

### Issues Addressed

1. **Multiple Object Layers** ✅
2. **Object Tiles Placed as Single Entity** ✅
3. **Free Positioning (No Grid Snapping)** ✅

---

## What Changed

### Issue 1: Multiple Object Layers Not Possible

**Problem:** The UI only created "Tile" layers by default.

**Solution:** Added `LayerTypeDialog` to let users choose layer type when creating new layers.

```python
# Before: Always created tile layer
layer_manager.create_layer("Layer 1")

# After: Show dialog
layer_type_dialog.show(on_confirm, on_cancel)
# User selects "Object Layer"
layer_manager.create_layer("Layer 1", layer_type="object")
```

**New Files:**
- `src/widgets/ui/layer_type_dialog.py` - Dialog for selecting tile vs object layer

**Modified:**
- `src/editor.py` - Integrated layer type dialog
- `src/widgets/layer_selector.py` - Uses dialog when adding layers

---

### Issue 2: Object Tiles Placed in Bulk, Not Sliced

**Problem:** When selecting multiple tiles from an object tileset, the code was placing each tile individually as separate objects.

```python
# Before: Loop through each tile in selection
for y_off in range(sel_h_tiles):
    for x_off in range(sel_w_tiles):
        # Place separate object for each tile
        active_layer.add_object(...)  # ← Called multiple times
```

**Solution:** Place the ENTIRE selection as a single object with the selection's dimensions.

```python
# After: One object from entire selection
sel_width = src_rect[2]   # Selection width in pixels
sel_height = src_rect[3]  # Selection height in pixels

obj_data = {
    "pos": (pixel_x, pixel_y),
    "width": sel_width,   # ← Use full selection size
    "height": sel_height,
    ...
}
active_layer.add_object((pixel_x, pixel_y), obj_data)
```

**Modified:**
- `src/widgets/tile_grid.py` - Rewrote `_place_object_free()` method

---

### Issue 3: Objects Not Sitting Freely (Still Grid-Snapped)

**Problem:** Objects were being placed at grid positions, not exact pixel coordinates.

```python
# Before: Using hover_cell (grid-based)
if self.hover_cell is None:
    return
pixel_x = world_pos[0] + (x_off * tile_w)  # ← Still grid-aligned
```

**Solution:** Use exact mouse position in world coordinates, no grid snapping.

```python
# After: Direct mouse position
mouse_pos = pygame.mouse.get_pos()
world_pos = self.screen_to_world(mouse_pos)  # ← Exact pixel position

obj_data = {
    "pos": (world_pos[0], world_pos[1]),  # ← Use exact position
    ...
}
```

**Modified:**
- `src/widgets/tile_grid.py` - Completely rewrote `_place_object_free()`

---

## Complete `_place_object_free()` - New Implementation

```python
def _place_object_free(self, active_layer, tileset_index, tileset_data, 
                       src_rect, tile_w, tile_h, sheet_cols):
    """Place objects at exact pixel position (free placement).
    
    For object tilesets, place the ENTIRE selection as a single entity
    at the exact mouse position, NOT sliced into individual tiles.
    """
    mouse_pos = pygame.mouse.get_pos()
    world_pos = self.screen_to_world(mouse_pos)

    # Get the selected area dimensions
    sel_width = src_rect[2]   # Width of selection in pixels
    sel_height = src_rect[3]  # Height of selection in pixels
    
    # Start position in tileset
    start_sx = src_rect[0]    # Pixel X in tileset
    start_sy = src_rect[1]    # Pixel Y in tileset

    # Create a SINGLE object from the entire selection
    variant_id = ((start_sy // tile_h) * sheet_cols) + (start_sx // tile_w)

    obj_data = {
        "pos": (world_pos[0], world_pos[1]),  # EXACT pixel position
        "ttype": int(tileset_index),
        "tileset_type": "object",
        "variant": variant_id,
        "width": sel_width,    # Selection size, not tile size
        "height": sel_height,
    }

    active_layer.add_object((world_pos[0], world_pos[1]), obj_data)
```

---

## How to Use Now

### 1. Create Object Layer

```
1. Click "+" button in layer panel
2. Dialog appears:
   ○ Tile Layer
   ◉ Object Layer
3. Select "Object Layer" → [OK]
4. New object layer created
```

You can now create **multiple object layers**!

### 2. Add Object Tileset

```
1. Click "Add Tileset"
2. Select image
3. Dialog: Choose "Object Tileset"
4. Click OK
```

### 3. Place Objects Freely

```
1. Select object layer
2. Select object tileset
3. Click/drag to select object sprite
4. Click anywhere on canvas
   → Object placed at EXACT mouse position
   → NO grid snapping
   → Entire selection becomes single object
```

---

## Data Structure

### Single Object from Selection

```python
{
    "pos": (157, 93),         # Exact pixel position
    "ttype": 2,               # Tileset index
    "tileset_type": "object", # Type of tileset
    "variant": 5,             # Top-left tile in selection
    "width": 128,             # Selection width (not tile size!)
    "height": 64,             # Selection height
}
```

### Key Points

- **pos**: EXACT pixel coordinates - NOT grid-aligned
- **width/height**: Full selection dimensions, not individual tile size
- **variant**: Points to top-left tile of selection (for rendering)

---

## Rendering

Objects render at exact pixel position using their full dimensions:

```python
obj_x, obj_y = obj["pos"]
dest_x = obj_x - self.scroll_x + self.rect.x
dest_y = obj_y - self.scroll_y + self.rect.y

src_rect = Rect(start_sx, start_sy, obj["width"], obj["height"])
surface.blit(tileset_surface, (dest_x, dest_y), area=src_rect)
```

---

## Comparison: Before vs After

### Before

❌ Only one layer type per layer (tile or object)
❌ Objects placed in grid loops
❌ Objects snapped to grid
❌ Multiple tiles became multiple objects
❌ No distinction between "create tile layer" vs "create object layer"

### After

✅ Can create multiple object layers
✅ Objects placed as single units
✅ Objects at exact pixel positions
✅ Selection becomes one object
✅ Dialog to choose layer type when creating

---

## Workflow Diagram

```
Click "Add Layer"
    ↓
LayerTypeDialog appears
    ┌─────────────────┐
    │ Tile Layer      │
    │ Object Layer ◉  │
    └─────────────────┘
    ↓
User selects "Object Layer"
    ↓
layer_manager.create_layer("Layer", layer_type="object")
    ↓
New object layer ready
    ↓
User clicks on object tileset
    ↓
User clicks canvas at (157, 93)
    ↓
_place_object_free() called
    ↓
Object placed at EXACT (157, 93)
    ↓
Object created with:
- pos: (157, 93)
- width: selection_width
- height: selection_height
```

---

## Testing

- [ ] Create new project
- [ ] Add first object layer (select "Object Layer")
- [ ] Add second object layer (select "Object Layer")
- [ ] Verify multiple layers exist in layer panel
- [ ] Add object tileset
- [ ] Select 2x2 area from object tileset (128x128 pixels)
- [ ] Click at pixel position (157, 93)
- [ ] Verify object appears at exact position
- [ ] Verify object has 128x128 size (not 32x32)
- [ ] Verify no grid snapping

---

## Files Changed

### New Files
- `src/widgets/ui/layer_type_dialog.py` - Layer type selection dialog

### Modified Files
- `src/editor.py` - Integrated layer type dialog
- `src/widgets/tile_grid.py` - Fixed `_place_object_free()` method
- `src/widgets/layer_selector.py` - Uses dialog for layer creation

---

## Summary

✅ **Multiple object layers** - Dialog lets you choose layer type
✅ **Single entity placement** - Entire selection = one object
✅ **Free positioning** - Uses exact mouse pixel coords, no snapping

Objects now work **exactly like Tiled editor**!

