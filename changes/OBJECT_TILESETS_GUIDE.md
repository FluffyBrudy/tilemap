## 🎯 Object Tilesets vs Tile Tilesets - Visual Guide

### The Problem You Had

**Before:** All tilesets were grid-aligned, even if you wanted free-positioned objects.

```
Tile Tileset (grid-based)
┌─────┬─────┬─────┐
│ [0] │ [1] │ [2] │  All snapped to grid
├─────┼─────┼─────┤
│ [3] │ [4] │ [5] │
└─────┴─────┴─────┘

Object on Object Layer
┌──────────────────┐
│  (100,150) ◆     │  But placed at grid positions only
│                  │  NOT at exact pixel coordinates
└──────────────────┘
```

---

### The Solution: Tileset Types

Now you can designate **what type each tileset is:**

```
┌─────────────────────────────────────────┐
│ TILE TILESET                            │
├─────────────────────────────────────────┤
│ ┌─────┬─────┬─────┐                     │
│ │ [0] │ [1] │ [2] │  Multiple sprites   │
│ ├─────┼─────┼─────┤  in a grid          │
│ │ [3] │ [4] │ [5] │  All same size      │
│ └─────┴─────┴─────┘                     │
│                                         │
│ Use for: Tile layers, terrain, etc.    │
│ Placement: Grid-aligned (32, 64)       │
└─────────────────────────────────────────┘

vs.

┌─────────────────────────────────────────┐
│ OBJECT TILESET                          │
├─────────────────────────────────────────┤
│  ◆     ★     ■     ▲     ●              │
│  NPC1  Tree  Rock  Sign  Plant          │
│                                         │
│ Use for: Objects on object layers       │
│ Placement: ANY pixel position (52, 143) │
│ FREE positioning - NO grid snap!        │
└─────────────────────────────────────────┘
```

---

## Layer Type vs Tileset Type

These are DIFFERENT things:

### LAYER TYPE (how data is stored)
```
Tile Layer
├─ Stores: Dict[grid_pos, tile]
├─ Keys: (0,0), (1,0), (2,0), etc.
└─ Rendering: Grid-aligned

Object Layer
├─ Stores: Dict[object_id, object]
├─ Object pos: (pixel_x, pixel_y) - ANY coordinates
└─ Rendering: Exact pixel position
```

### TILESET TYPE (what the tileset is for)
```
Tile Tileset
├─ Format: Image grid of same-sized sprites
├─ Used on: Tile layers primarily
├─ Grid size: 32x32, 16x16, etc.
└─ Example: terrain.png with 8x8 tiles

Object Tileset
├─ Format: Image grid (for now, same as tile)
├─ Used on: Object layers
├─ Each sprite: Can have different meaning
└─ Example: enemies.png or decorations.png
```

---

## Placement Examples

### Example 1: Tile Layer + Tile Tileset (EXISTING)
```python
# User clicks at grid position (5, 3)
# System places tile grid-aligned

Result:
┌──────────────────────────────────────┐
│ ┌──────┐                              │
│ │ Grid │                              │
│ ├──────┼──────┬──────┐                │
│ │ Tile │ Tile │ Tile │  ← Row 3      │
│ ├──────┼──────┼──────┤                │
│ │ Tile │[TILE]│ Tile │  ← Grid (5,3) │
│ └──────┴──────┴──────┘                │
│     Column 5                           │
└──────────────────────────────────────┘
```

### Example 2: Object Layer + Tile Tileset (NEW)
```python
# User places a tile on object layer
# System creates object with tile dimensions

obj_data = {
    "pos": (160, 96),        # Grid (5,3) * 32 = pixel position
    "ttype": 0,              # Tileset index
    "tileset_type": "tile",  # ← Came from tile tileset
    "variant": 5,
    "width": 32,
    "height": 32
}

# Result: Object with 32x32 size at grid position
```

### Example 3: Object Layer + Object Tileset (NEW! ✨)
```python
# User clicks at ANY pixel position like (157, 93)
# System places object at EXACT position - no grid snap!

obj_data = {
    "pos": (157, 93),        # ← EXACT pixel position
    "ttype": 2,              # Tileset index
    "tileset_type": "object",# ← Came from object tileset
    "variant": 7,
    "width": 32,
    "height": 48
}

# Result: Object at EXACT coordinates, pixel-perfect

┌──────────────────────────────┐
│                              │
│       ◆ ← (157, 93)          │
│       Not snapped to grid!    │
│                              │
└──────────────────────────────┘
```

---

## How to Use It

### Step 1: Create Object Tileset

```
1. Click "Add Tileset" button
2. Select your object image (e.g., enemies.png)
3. Choose type:
   
   ┌────────────────────────────┐
   │ Tileset Type               │
   │ [ ] Tile Tileset           │
   │ [X] Object Tileset         │ ← Select this
   └────────────────────────────┘
   
4. Click OK
```

### Step 2: Create Object Layer

```
1. Right-click layer list
2. "New Layer" → "Object Layer"
3. Layer added
```

### Step 3: Place Objects

```
1. Select the object layer
2. Select object tileset
3. Click on canvas AT EXACT POSITION YOU WANT
   - No grid snapping!
   - Click at pixel (157, 93) → object at (157, 93)
4. Right-click to remove
```

---

## Key Differences From Before

### Before (Weird)
```
Object Layer
├─ Objects always placed at grid position
├─ Even if you wanted pixel-perfect positioning
├─ No distinction between tile and object tilesets
└─ Limited for game object placement
```

### After (Like Tiled)
```
Object Layer
├─ Objects placed at ANY pixel position
├─ Pixel-perfect - click at (x,y), object at (x,y)
├─ Clear distinction: tile vs object tilesets
└─ Perfect for game objects, NPCs, decorations
```

---

## Data Structure

### Object Data (stored in layer.objects dict)

```python
{
    "pos": (157, 93),         # Pixel coordinates (not grid!)
    "ttype": 2,               # Which tileset (index)
    "tileset_type": "object", # Was it tile or object tileset?
    "variant": 7,             # Which sprite in tileset
    "width": 32,              # Sprite width in pixels
    "height": 48              # Sprite height in pixels
}
```

### When Saved to JSON

```json
{
    "objects": {
        "1": {
            "pos": "157;93",
            "ttype": 2,
            "tileset_type": "object",
            "variant": 7,
            "width": 32,
            "height": 48
        }
    }
}
```

---

## Advantages

✅ **Free positioning** - Place objects exactly where you want  
✅ **No grid snapping** - More control for game objects  
✅ **Tiled-like** - Works like industry-standard editor  
✅ **Metadata tracking** - Know which tileset type each object used  
✅ **Backward compatible** - Old tile layers still work  
✅ **Flexible** - Can use tile tilesets on object layers too  

---

## Future Enhancements

- [ ] Drag to reposition objects
- [ ] Multi-select objects
- [ ] Snap-to-grid toggle (optional)
- [ ] Object properties (rotation, scale, etc.)
- [ ] Collision shapes
- [ ] Layers panel shows tile/object icons

