## 🎯 Object Tileset Placement - Exact Behavior

### The Three Key Changes

#### 1. Layer Type Dialog

When you click the "+" button to add a layer:

```
BEFORE: Instantly created a tile layer
AFTER:  Dialog appears asking what type
```

Dialog:
```
┌─────────────────────────────┐
│ Layer Type                  │
├─────────────────────────────┤
│ ◉ Tile Layer (grid-based)   │
│ ○ Object Layer (free-pos)   │
│ [OK]  [Cancel]              │
└─────────────────────────────┘
```

**Result:** Can now create multiple object layers!

---

#### 2. Single Object from Selection

When you select and place from object tileset:

```
BEFORE: Selected 4-tile block (2x2)
        ↓ Placed as 4 separate objects

AFTER:  Selected 4-tile block (2x2)
        ↓ Placed as 1 single object (128x128)
```

**Example:**

If you select a 2x2 tile area from object tileset:
- Selection: 128x128 pixels (4 tiles × 32px each)
- Result: ONE object with width=128, height=128
- NOT: Four separate 32x32 objects

---

#### 3. Exact Pixel Positioning

When you click to place the object:

```
BEFORE: Click at screen position
        ↓ Convert to grid (75, 93)
        ↓ Place at pixel (2400, 2976)

AFTER:  Click at screen position
        ↓ Convert to world pixel (157, 93)
        ↓ Place at pixel (157, 93) ← EXACT position!
```

**No grid snapping!**

---

## Placement Algorithm

### Step 1: Get Mouse Position
```python
mouse_pos = pygame.mouse.get_pos()        # Screen coordinates
world_pos = self.screen_to_world(mouse_pos)  # World coordinates
```

### Step 2: Get Selection Dimensions
```python
sel_width = src_rect[2]   # e.g., 128
sel_height = src_rect[3]  # e.g., 64
```

### Step 3: Calculate Variant ID
```python
# Where in the tileset is this coming from?
start_sx = src_rect[0]  # e.g., 64 (second column)
start_sy = src_rect[1]  # e.g., 32 (second row)

variant_id = ((start_sy // 32) * cols) + (start_sx // 32)
# = (1 * 8) + 2 = 10
```

### Step 4: Create Single Object
```python
obj_data = {
    "pos": (world_pos[0], world_pos[1]),  # Exact position!
    "ttype": tileset_index,
    "tileset_type": "object",
    "variant": 10,                        # Top-left of selection
    "width": 128,                         # Full selection width
    "height": 64,                         # Full selection height
}
```

### Step 5: Add to Layer
```python
layer.add_object((world_pos[0], world_pos[1]), obj_data)
```

---

## Example Scenarios

### Scenario 1: Single Tile Selection

```
Tileset:
┌──┬──┬──┐
│  │  │● │ ← Selected (tile 2)
├──┼──┼──┤
│  │  │  │
└──┴──┴──┘

Click at pixel (300, 150)

Result:
{
    "pos": (300, 150),
    "variant": 2,
    "width": 32,   ← One tile wide
    "height": 32,  ← One tile tall
}
```

### Scenario 2: 2x2 Selection

```
Tileset:
┌──┬──┬──┐
│●1│●2│  │ ← Selected
├──┼──┼──┤
│●3│●4│  │ ← This 2x2 block
└──┴──┴──┘

Click at pixel (157, 93)

Result:
{
    "pos": (157, 93),
    "variant": 0,        ← Top-left (tile 1)
    "width": 64,         ← Two tiles wide (2 × 32)
    "height": 64,        ← Two tiles tall
}
```

### Scenario 3: Custom Sized Sprite

```
Tileset:
┌─────────────┐
│             │ ← Custom sprite (96x128)
│             │
└─────────────┘

Click at pixel (500, 200)

Result:
{
    "pos": (500, 200),
    "width": 96,         ← Exact sprite width
    "height": 128,       ← Exact sprite height
}
```

---

## Rendering

When rendering the object:

```python
# Get object data
obj_x, obj_y = obj["pos"]           # e.g., (157, 93)
obj_w = obj["width"]                # e.g., 128
obj_h = obj["height"]               # e.g., 64
variant = obj["variant"]            # e.g., 10

# Calculate screen position
screen_x = obj_x - scroll_x + rect.x
screen_y = obj_y - scroll_y + rect.y

# Calculate tileset source position
sheet_cols = tileset_width // tile_size
src_x = (variant % sheet_cols) * 32
src_y = (variant // sheet_cols) * 32

# Draw
src_rect = Rect(src_x, src_y, obj_w, obj_h)
surface.blit(tileset_surface, (screen_x, screen_y), area=src_rect)
```

---

## Key Point: Width and Height

### OLD (Wrong)
```python
# Always 32x32 (tile size)
"width": 32,
"height": 32,
```

### NEW (Correct)
```python
# Size of selection/sprite
"width": sel_width,   # Could be 64, 96, 128, etc.
"height": sel_height,
```

This means:
- 1 tile selected → 32x32 object
- 2x2 tiles selected → 64x64 object
- 3x4 tiles selected → 96x128 object

---

## Position Precision

Objects are stored with **exact pixel precision**:

```python
# Before: Grid-aligned only
(0, 0), (32, 0), (64, 0), (96, 0)  ← Limited positions

# After: Any pixel coordinate
(0, 0), (1, 0), (157, 93), (999, 234)  ← Full precision
```

---

## Collision with Selection

When you select from a tileset that's not aligned to grid:

```
Tileset (image can be any size):
Width: 256 pixels (8 tiles × 32px)
Height: 192 pixels (6 tiles × 32px)

Click at (100, 75) and drag to (164, 139)

Selection rectangle:
- Width: 164 - 100 = 64
- Height: 139 - 75 = 64

Object created with:
- width: 64  ← Exact selection size
- height: 64
```

---

## FAQ

### Q: Why is my object 128x128 instead of 32x32?
**A:** You selected a 4-tile block (2x2), so it's 128x128. Select a single tile for 32x32.

### Q: Can I place objects at (157, 93)?
**A:** Yes! Any pixel position is supported now.

### Q: Why is my object not at the exact position I clicked?
**A:** The position is relative to world space (accounting for scroll). Zoom in to verify exact position.

### Q: Can I place overlapping objects?
**A:** Yes! Objects don't snap to grid, so they can overlap freely.

### Q: How do I move an object after placing?
**A:** Future feature: drag to reposition (not yet implemented).

---

## Testing Workflow

```
1. Create object layer
   ✓ Confirm dialog appears
   ✓ Confirm you can select "Object Layer"
   ✓ Confirm layer created with type="object"

2. Add object tileset
   ✓ Confirm dialog appears
   ✓ Confirm you can select "Object Tileset"
   ✓ Confirm tileset added with tileset_type="object"

3. Select 2x2 area (128x128 pixels)
   ✓ Confirm selection rectangle is 128x128

4. Click at (157, 93)
   ✓ Object appears at (157, 93)
   ✓ Object is NOT on a grid cell
   ✓ Object size is 128x128 (not 32x32)

5. Verify single object created
   ✓ Right-click to delete
   ✓ Only one object removed (not four)
```

---

## Technical Details

### Object Data Structure

```python
TypeObject = {
    "pos": Tuple[int, int],       # (x, y) pixel coords
    "ttype": int,                 # Tileset index
    "tileset_type": str,          # "tile" or "object"
    "variant": int,               # Sprite index in tileset
    "width": int,                 # Object width in pixels
    "height": int,                # Object height in pixels
}
```

### Storage
```python
# In layer.objects dict
layer.objects[object_id] = obj_data

# Example:
layer.objects[1] = {
    "pos": (157, 93),
    "ttype": 2,
    "tileset_type": "object",
    "variant": 10,
    "width": 128,
    "height": 64
}
```

### Serialization (JSON)
```json
{
    "objects": {
        "1": {
            "pos": "157;93",
            "ttype": 2,
            "tileset_type": "object",
            "variant": 10,
            "width": 128,
            "height": 64
        }
    }
}
```

---

## Summary

Your object tileset system now works **exactly like Tiled**:

✅ Create multiple object layers
✅ Place selections as single objects
✅ Free pixel-perfect positioning
✅ No grid snapping
✅ Store real coordinates

Perfect for game objects, NPCs, decorations, and anything that needs precise positioning!

