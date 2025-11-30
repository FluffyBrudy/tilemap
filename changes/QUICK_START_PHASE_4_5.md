# Quick Start Guide: Finishing Phase 4-5

## Phase 4: TileGrid Integration (Ready to Go)

### Current Status
✅ Backward compatibility property works - no changes strictly necessary
⚠️ Optimization and explicit layer awareness recommended

### Minimal Changes (Optional but Recommended)

**File:** `src/widgets/tile_grid.py`

#### Update the render() method (around line 245):
```python
# Current - works but doesn't use layers
tileset_map = self.editor.tileset_widget.tileset_map

# Recommended - future-proof
# For now, single-layer rendering is fine via property
# In future, could render multiple visible layers:
"""
rendered_layers = self.editor.tilemap.layer_manager.get_rendered_layers()
for layer in rendered_layers:
    # Render tiles from layer
    for loc in layer.tiles:
        # ... existing rendering logic
"""
```

**Current code is already compatible** - The `@property ongrid_tiles` automatically uses active layer.

### Testing (Quick)
```python
# Test 1: Place tile on Layer 1
editor.tilemap.layer_manager.set_active_layer(0)
tile_grid.place_tile()  # Should place on Layer 1

# Test 2: Switch to Layer 2 and verify tiles are different
editor.tilemap.layer_manager.set_active_layer(1)
# Layer 2 should be empty

# Test 3: Switch back to Layer 1
editor.tilemap.layer_manager.set_active_layer(0)
# Previously placed tile should still be there
```

**Status:** ✅ No changes needed, fully backward compatible

---

## Phase 5: Editor Layout (Simple Integration)

### File: `src/editor.py`

#### Step 1: Add import (line ~12)
```python
from widgets.layer_selector import LayerSelector
```

#### Step 2: Modify __init__ method (around line 35)
Replace:
```python
self.selector_w = 300
self.map_setup_widget: Optional[MapSetup] = None
self.tileset_widget: Optional[TileSelector] = None
self.tile_grid_widget: Optional[TileGrid] = None
```

With:
```python
self.selector_w = 300
self.tileset_h = 300
self.layer_h = 150
self.map_setup_widget: Optional[MapSetup] = None
self.tileset_widget: Optional[TileSelector] = None
self.layer_widget: Optional[LayerSelector] = None
self.tile_grid_widget: Optional[TileGrid] = None
```

#### Step 3: Initialize LayerSelector in __init__
Add after tileset_widget initialization (search for "self.tileset_widget = TileSelector..."):
```python
# Layer selector widget below tileset
self.layer_widget = LayerSelector(
    self,
    self.width - self.selector_w,           # x: right side
    self.tileset_h,                         # y: below tileset
    self.selector_w,                        # width: same as tileset
    self.layer_h                            # height: 150px
)
```

#### Step 4: Update TileGrid creation
Find where `self.tile_grid_widget` is created and adjust height:
```python
# OLD (if it exists):
# self.tile_grid_widget = TileGrid(self, Rect(...))

# NEW:
grid_rect = Rect(
    0, 0,
    self.width - self.selector_w,  # Leave room for layer selector
    self.height - (self.tileset_h + self.layer_h)  # Account for both widgets
)
self.tile_grid_widget = TileGrid(self, grid_rect)
```

#### Step 5: Update draw() method
Find the draw method (around line 150+) and add layer_widget rendering:
```python
# After drawing tileset_widget
if self.tileset_widget:
    self.tileset_widget.draw(self.screen)

# ADD THIS:
if self.layer_widget:
    self.layer_widget.draw(self.screen)
```

#### Step 6: Update handle_event() method
Find where events are passed to widgets and add layer_widget:
```python
# After tileset_widget.handle_event()
if self.tileset_widget and self.tileset_widget.handle_event(event):
    return

# ADD THIS:
if self.layer_widget and self.layer_widget.handle_event(event):
    return
```

---

## Validation Checklist

After making Phase 5 changes, verify:

- [ ] Editor starts without errors
- [ ] Layer selector appears below tileset selector
- [ ] Clicking "+" adds a new layer
- [ ] Clicking "-" removes the selected layer
- [ ] Clicking a layer in the list makes it active (should update tile_grid context)
- [ ] Layer count updates after add/remove
- [ ] Tile placement works (places on active layer)
- [ ] Switching layers and checking tiles confirms data is separate
- [ ] File save/load preserves layer structure
- [ ] Old save files load correctly (creates "Terrain" layer)

---

## Troubleshooting

### Layer selector doesn't appear
- Check import in editor.py: `from widgets.layer_selector import LayerSelector`
- Verify `self.layer_widget.draw(self.screen)` is in draw() method
- Check y-coordinate calculation: `y = self.tileset_h` should position it below tileset

### Tiles don't appear after switching layers
- Verify `layer_widget.handle_event()` is called
- Check that `LayerManager.set_active_layer()` is being called
- Verify TileGrid uses `self.editor.tilemap.ongrid_tiles` (which proxies to active layer)

### Tiles disappear after reordering layers
- This is expected! Reordering changes z_index, not layer position
- To move tiles between layers: implement copy/cut/paste (future feature)

### Save/Load issues
- Verify `tilemap.py` save_map() and load_map() methods were updated
- Check that layers are populated correctly with `_load_layer_from_dict()`

---

## Next Advanced Features (Optional)

After Phase 5 is working, consider:

1. **Visibility Toggle**
   - Make eye icon clickable: `layer.visible = not layer.visible`
   - Update `TileGrid.render()` to use `get_rendered_layers()`

2. **Lock Toggle**
   - Make lock icon clickable: `layer.locked = not layer.locked`
   - Already respected in Layer.set_tile()

3. **Layer Rename**
   - Right-click context menu
   - Text input dialog for new name

4. **Layer Opacity**
   - Slider in UI
   - Apply in rendering with `pygame.Surface.set_alpha()`

5. **Merge Layers**
   - Context menu option
   - Copy all tiles to target layer, delete source

6. **Duplicate Layer**
   - Copy all tiles and create new layer with "_copy" suffix

---

## Time Estimates

- **Phase 4 Testing:** 15 minutes (no code changes needed)
- **Phase 5 Implementation:** 20 minutes
- **Phase 5 Testing:** 15 minutes
- **Total:** ~1 hour to completion

---

**You're almost there!** The hard architecture work is done. Phase 5 is just wiring it all together. 🎉

