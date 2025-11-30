## 🐛 Bug Fixes - Object Layer Placement Issues

### Problems Found and Fixed

#### Problem 1: Early Return Blocking Object Placement
**Issue:** `place_tile()` had `if not self.hover_cell: return` at the very beginning
- Checked for grid hover BEFORE determining if object layer
- Object layers with free positioning don't have hover_cell
- Result: Objects couldn't be placed freely at all

**Fix:** Moved hover_cell check AFTER layer type detection
```python
# Before:
def place_tile(self):
    if not self.hover_cell:  # ← BLOCKS object placement!
        return
    ...

# After:
def place_tile(self):
    # Get layer and check type first
    ...
    if (active_layer.layer_type == "object" 
        and tileset_data.tileset_type == "object"):
        self._place_object_free(...)  # ← Works now!
    else:
        if not self.hover_cell:  # ← Only needed for grid placement
            return
        self._place_tile_grid(...)
```

**Impact:** Objects on object layers can now be placed anywhere!

---

#### Problem 2: Rendering Objects with Wrong Dimensions
**Issue:** Render method calculated sheet_cols using object width instead of tile width
```python
# Wrong:
sheet_cols = sheet_w // obj_w  # ← obj_w could be 64, 128, etc!
src_x = (variant_id % sheet_cols) * obj_w
src_y = (variant_id // sheet_cols) * obj_h
```

This meant:
- If object is 64×64 and sheet is 256 wide: sheet_cols = 4
- If object is 128×128 and sheet is 256 wide: sheet_cols = 2
- Wrong variant calculation!

**Fix:** Use tile_w and tile_h (32×32) for sheet layout, but use obj_w and obj_h for rendering size
```python
# Correct:
sheet_cols = sheet_w // tile_w  # ← Use actual tile size (32)
src_x = (variant_id % sheet_cols) * tile_w
src_y = (variant_id // sheet_cols) * tile_h
src_rect = Rect(src_x, src_y, obj_w, obj_h)  # ← Draw full object size
```

**Impact:** Objects render from correct tileset position!

---

### Changed Files

**`src/widgets/tile_grid.py`**

#### Change 1: place_tile()
```python
# BEFORE: Early return blocks everything
if not self.hover_cell:
    return

# AFTER: Conditionally check hover_cell
if (active_layer.layer_type == "object" 
    and tileset_data.tileset_type == "object"):
    self._place_object_free(...)
else:
    if not self.hover_cell:
        return
    self._place_tile_grid(...)
```

#### Change 2: render() object rendering
```python
# BEFORE: Wrong sheet_cols calculation
sheet_cols = sheet_w // obj_w
src_x = (variant_id % sheet_cols) * obj_w
src_y = (variant_id // sheet_cols) * obj_h

# AFTER: Correct calculation
sheet_cols = sheet_w // tile_w
src_x = (variant_id % sheet_cols) * tile_w
src_y = (variant_id // sheet_cols) * tile_h
src_rect = Rect(src_x, src_y, obj_w, obj_h)
```

---

## Now It Works!

✅ **Object layers with object tilesets:**
1. Click "+" → Select "Object Layer"
2. Click "Add" → Select image → "Object Tileset"
3. Click canvas at ANY position
4. Object placed at EXACT pixel position
5. NO grid snapping!
6. Single object from selection!

---

## Test Workflow

```
1. Create object layer
   ✓ Dialog shows
   ✓ Select "Object Layer"

2. Add object tileset
   ✓ Dialog shows
   ✓ Select "Object Tileset"

3. Place object
   ✓ Can click anywhere on canvas
   ✓ Object appears at exact position
   ✓ NOT grid-aligned
   ✓ Correct size rendered
```

---

## Root Causes

1. **Architecture issue:** Layer type checking came too late
   - Solution: Reorder logic to check layer type first

2. **Rendering logic error:** Confused object size with tile size
   - Solution: Use tile_w/tile_h for sheet layout, obj_w/obj_h for drawing

---

## Status

✅ Fixed and tested
✅ All errors cleared
✅ Ready for use

Objects now work correctly on object layers!

