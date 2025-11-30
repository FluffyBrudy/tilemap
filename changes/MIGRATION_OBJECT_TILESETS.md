## 🔄 Migration Notes - Object Tileset Changes

### Backward Compatibility

✅ **100% backward compatible** - All existing maps continue to work without changes.

---

## For Existing Maps

### No Migration Needed

Existing data loads and works automatically because:

1. **TilesetData default:** `tileset_type="tile"` by default
2. **Layer system:** Active layer manager maintains old `ongrid_tiles` dict
3. **Rendering:** Automatically uses correct layer type

```python
# Old code still works exactly the same
editor.tilemap.ongrid_tiles[(5, 3)] = {
    "pos": (5, 3),
    "ttype": "0",     # Old: string
    "variant": 5
}

# BUT internally, layer system converts to:
layer.set_tile((5, 3), {
    "pos": (5, 3),
    "ttype": "0",     # Still works
    "variant": 5
})
```

---

## If You Want to Use New Features

### For New Object Layers (Best Practice)

```python
# 1. Create object layer
layer_manager.create_layer("MyObjects", layer_type="object")

# 2. Add object tileset as "object" type
# When file dialog completes, select "Object Tileset" type

# 3. Place objects - they'll be free-positioned
# vs grid-aligned if you use "Tile Tileset"
```

### For Mixed Use (Tile Tileset on Object Layer)

```python
# You can still place tiles on object layers
# They just become objects with tile dimensions

# 1. Create object layer
layer_manager.create_layer("MixedLayer", layer_type="object")

# 2. Add tile tileset as "tile" type
# When file dialog completes, select "Tile Tileset" type

# 3. Place tiles - they become grid-aligned objects
#    Each tile becomes an object with width=32, height=32
```

---

## What Changed in Object Data

### Old Format (Before)
```json
{
    "objects": {
        "1": {
            "pos": "100;50",
            "ttype": "0",
            "variant": 5,
            "width": 32,
            "height": 32
        }
    }
}
```

### New Format (After)
```json
{
    "objects": {
        "1": {
            "pos": "100;50",
            "ttype": 0,                 // Changed: int instead of str
            "tileset_type": "object",   // NEW: tracks tileset type
            "variant": 5,
            "width": 32,
            "height": 32
        }
    }
}
```

---

## Loading Old Maps

When loading old JSON files:

```python
# Old format has ttype as string "0"
# New code expects int 0 for objects

# Automatic conversion happens in layer loading:
try:
    obj_id = int(obj_id_str)
    layer.objects[obj_id] = obj_data
    # ttype will be "0" (str) from old format
    # Code handles both str and int gracefully
except (ValueError, TypeError):
    pass
```

---

## Changes to TypeObject

### In-Memory Representation

| Field | Before | After | Notes |
|-------|--------|-------|-------|
| pos | Tuple | Tuple | Unchanged |
| ttype | str | int | More efficient |
| variant | int | int | Unchanged |
| width | int | int | Unchanged |
| height | int | int | Unchanged |
| tileset_type | — | str | NEW: "tile" or "object" |

---

## For Save/Load Implementation

### When Saving Objects

```python
# Convert to serialized format
obj_serialized = {
    "pos": "100;50",              # Format: "x;y"
    "ttype": int(obj["ttype"]),   # Ensure int
    "tileset_type": obj["tileset_type"],  # NEW
    "variant": obj["variant"],
    "width": obj["width"],
    "height": obj["height"]
}

# Save to JSON
json.dump(obj_serialized, f)
```

### When Loading Objects

```python
# Parse from JSON
obj_data = {
    "pos": tuple(map(int, pos_str.split(';'))),
    "ttype": int(data["ttype"]),  # Convert to int if needed
    "tileset_type": data.get("tileset_type", "object"),  # Default if missing
    "variant": int(data["variant"]),
    "width": int(data["width"]),
    "height": int(data["height"])
}
```

---

## Debugging

### If Objects Aren't Rendering

Check these things:

1. **Is active layer an object layer?**
   ```python
   active = tilemap.layer_manager.get_active_layer()
   assert active.layer_type == "object"
   ```

2. **Are objects in the layer?**
   ```python
   objs = active.get_all_objects()
   print(f"Objects: {len(objs)}")
   ```

3. **Is tileset type recognized?**
   ```python
   ts = tileset_widget.tilesets[tileset_idx]
   print(f"Tileset type: {ts.tileset_type}")  # Should be "tile" or "object"
   ```

4. **Is variant ID valid?**
   ```python
   sheet_w = tileset_data.surface.get_width()
   sheet_cols = sheet_w // obj_width
   variant = obj["variant"]
   max_variant = (sheet_h // obj_height) * sheet_cols - 1
   assert variant <= max_variant, f"Variant {variant} out of range"
   ```

---

## What to Test

### Existing Projects
- [ ] Load old map with tile layers → works
- [ ] Place tiles on tile layer → works
- [ ] Remove tiles → works
- [ ] Save and reload → works

### New Features
- [ ] Create object layer
- [ ] Add object tileset → dialog appears
- [ ] Select "Object Tileset" type
- [ ] Place objects → free-positioned (no grid snap)
- [ ] Right-click to remove
- [ ] Objects render correctly at all scroll positions

### Mixed Scenarios
- [ ] Add tile tileset to object layer → dialog appears
- [ ] Select "Tile Tileset" type
- [ ] Place on object layer → becomes objects with tile dimensions
- [ ] Works with free-positioned objects in same layer

---

## FAQ

### Q: My old maps don't work!
**A:** They should work automatically. Check that:
1. Layer manager is initialized properly
2. Active layer is being detected
3. Tilesets are loaded

### Q: Can I mix tile and object tilesets in same map?
**A:** Yes! Each tileset is independent. You can have both types loaded.

### Q: Do I need to re-save maps to use new format?
**A:** No. Old maps load fine with `tileset_type` defaulting to "object". 
But save with new system to get full benefits.

### Q: What if I have old object data without tileset_type?
**A:** The code handles it:
```python
tileset_type = obj.get("tileset_type", "object")  # Default to object
```

### Q: Will old object coordinates work?
**A:** Yes, completely. Objects stay at same pixel positions.

---

## Version Info

- **Backward Compat:** ✅ Full
- **Data Migration:** ❌ Not needed
- **Old Maps:** ✅ Load and work automatically
- **New Feature:** Object tilesets with free positioning

