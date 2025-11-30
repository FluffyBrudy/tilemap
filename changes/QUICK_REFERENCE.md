# 🚀 Quick Reference - Object Tilesets

## Create Object Layer

1. Click **`+`** button in layer panel
2. Select **`Object Layer`** → **`OK`**
3. New object layer created ✓

Can create multiple!

---

## Add Object Tileset

1. Click **`Add Tileset`** button
2. Select image file
3. Select **`Object Tileset`** → **`OK`**
4. Tileset added ✓

---

## Place Objects

1. Select object layer
2. Select object tileset
3. Select sprite area from tileset
4. Click canvas at desired position
5. Object placed at EXACT position ✓

**No grid snapping!**

---

## Key Differences

| Action | Tile Layer | Object Layer |
|--------|-----------|--------------|
| **Create** | Auto created | Choose "Object Layer" |
| **Tileset** | Grid-aligned | Free-positioned |
| **Placement** | Snaps to grid | Exact pixels |
| **Multiple** | Yes | Yes |
| **Position** | (grid_x, grid_y) | (pixel_x, pixel_y) |

---

## Object Data Structure

```python
{
    "pos": (157, 93),        # Exact pixel position
    "ttype": 2,              # Tileset index
    "tileset_type": "object",# Type of tileset
    "variant": 10,           # Sprite in tileset
    "width": 128,            # Object width (px)
    "height": 64             # Object height (px)
}
```

---

## Quick Tips

✅ **Selection size = object size**
  - Select 1 tile → 32×32 object
  - Select 2×2 → 64×64 object
  - Select custom → that size

✅ **Position precision**
  - Click at (157, 93) → placed at (157, 93)
  - Not aligned to grid

✅ **Multiple objects**
  - Can overlap freely
  - Each has own position/size
  - Right-click to remove

✅ **Multiple layers**
  - Mix of tile and object layers
  - Each layer independent

---

## Troubleshooting

**Objects not appearing?**
- Verify active layer is "Object Layer"
- Verify tileset is "Object Tileset"
- Check layer visibility

**Object wrong size?**
- Selection size becomes object size
- Select different area for different size

**Object snapped to grid?**
- Make sure using "Object Tileset"
- Not "Tile Tileset"

**Can't create object layer?**
- Click "+" button
- Select "Object Layer" in dialog
- Click OK

---

## Files Modified

- `src/editor.py` - Dialog integration
- `src/widgets/tile_grid.py` - Placement logic
- `src/widgets/layer_selector.py` - Layer creation
- `src/widgets/ui/layer_type_dialog.py` - NEW dialog
- `src/widgets/ui/tileset_type_dialog.py` - Tileset selection
- `src/widgets/tile_selector.py` - Tileset loading
- `src/ttypes/tilemap.py` - Data structures

---

## Test It

```python
# In your map setup:
1. Create → Object Layer
2. Add → Object Tileset (select image, choose "Object")
3. Click canvas at (100, 50)
4. Object appears at (100, 50) ✓

# Try these positions:
- (0, 0)
- (157, 93)
- (999, 456)
- (1, 1)

All work! No grid constraint!
```

---

## Comparison: Before vs After

**Before:**
```
Layer 1 (Tile)
Layer 2 (Tile)
Layer 3 (Tile)
```
❌ All same type

**After:**
```
Layer 1 (Tile)
Layer 2 (Object)
Layer 3 (Object)
```
✅ Mix and match!

---

## Architecture

```
TileGrid
├── place_tile()
    ├── Layer type: tile?  ──→ _place_tile_grid()
    └── Layer type: object?
        ├── Tileset type: tile?  ──→ _place_tile_grid()
        └── Tileset type: object? ──→ _place_object_free()
```

---

## Next Steps

✨ Future features (not yet implemented):
- [ ] Drag to reposition objects
- [ ] Multi-select objects
- [ ] Copy/paste objects
- [ ] Object properties panel

But foundation is ready!

---

## Status: ✅ Complete

✅ Multiple object layers
✅ Single object placement
✅ Free pixel positioning
✅ Real coordinate storage
✅ Backward compatible

**Ready for game development!**

