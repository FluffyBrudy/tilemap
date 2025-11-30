# Layer System Implementation - Phase 1-3 Complete

## Summary

A robust multi-layer system has been successfully designed and partially implemented for the tilemap editor. The code is structured to support multiple layers with full backward compatibility with existing single-layer saves.

## Completed Work

### Phase 1: Layer Management System ✅
**File:** `src/layers.py` (400+ lines)

Created two core classes:

#### `Layer` Class
- Represents a single layer with independent tile data
- Properties:
  - `name` - user-friendly layer name
  - `layer_type` - "tile" or "object" for future extensibility
  - `z_index` - rendering order
  - `visible` - toggleable visibility
  - `locked` - prevent accidental edits
  - `opacity` - alpha blending (0.0-1.0)
  - `tiles` - Dict[Tuple[int, int], TypeTile]

- Methods:
  - `set_tile(pos, tile)` - Add/update tile (respects lock)
  - `get_tile(pos)` - Retrieve tile
  - `remove_tile(pos)` - Delete tile (respects lock)
  - `clear()` - Clear all tiles
  - `to_dict()` / `from_dict()` - Serialization

#### `LayerManager` Class
- Manages collection of layers
- Active layer tracking
- Full manipulation API:
  - `create_layer(name, type, index)` - Add new layer
  - `delete_layer(index)` - Remove layer
  - `get_layer(index)` / `get_active_layer()`
  - `set_active_layer(index)`
  - `reorder_layer(from, to)` - Drag-to-reorder support
  - `get_rendered_layers()` - Sorted by z_index, filtered by visibility
  - `get_layer_count()` / `has_layers()`
  - `to_dict()` / `from_dict()` - Serialization

- Utility: `create_default_layer_manager()` - Creates manager with "Terrain" and "Objects" layers

### Phase 2: Tilemap Refactoring ✅
**File:** `src/tilemap.py` (refactored)

#### Backward Compatibility Layer
- Added `@property ongrid_tiles` that proxies to active layer
- Existing code accessing `tilemap.ongrid_tiles` continues to work
- All references automatically target the active layer

#### Enhanced Save System
- **New Format (v1.1):**
  ```json
  {
    "data": {
      "layers": [
        {
          "name": "Terrain",
          "type": "tile",
          "visible": true,
          "locked": false,
          "opacity": 1.0,
          "z_index": 0,
          "tiles": {...}
        }
      ],
      "ongrid": {...},  // Legacy format for compatibility
      "offgrid": [...]
    }
  }
  ```

- Saves to BOTH formats:
  - `data/layers` - New multi-layer format
  - `data/ongrid` - Copy of first layer for backward compatibility

#### Enhanced Load System
- **Auto-detection:** Checks for `data/layers` first, falls back to `data/ongrid`
- **Legacy loading:** Old saves automatically load into "Terrain" layer
- **Normalization:** Automatically converts path-based ttype to indices
- **Methods:**
  - `_load_layer_from_dict()` - Deserialize layer
  - `_normalize_ttype()` - Convert path strings to indices

### Phase 3: Layer Selector Widget ✅
**File:** `src/widgets/layer_selector.py` (250+ lines)

#### UI Features
- **Header** - "LAYERS" title bar
- **List Area** - Displays all layers with visual feedback
  - Click to select active layer
  - Drag to reorder layers
  - Hover highlighting
  - Active layer highlighting
  
- **Layer Item Display:**
  - Layer name (left-aligned)
  - Visibility icon (eye) - click to toggle
  - Lock icon - shows if layer is locked
  
- **Footer** - Management buttons
  - "+" button to add new layer (auto-named "Layer N")
  - "-" button to delete active layer (safe: won't delete last layer)
  - Layer count display

#### Interaction Model
- **Selection:** Click a layer to make it active (routing to `LayerManager`)
- **Reordering:** Drag-and-drop support with visual feedback
- **Creation:** Click "+" creates new layer with auto-incremented name
- **Deletion:** Click "-" removes active layer (with validation)
- **Visibility:** Click eye icon to toggle layer visibility (future: implement rendering)
- **Lock:** Shows lock status, future versions can implement lock-toggling

#### Layout
- Designed to sit below TileSelector widget
- Proper height calculations for flexible layout
- Color scheme matches editor aesthetic
- Interactive buttons with hover states

## Architecture Decisions & Rationale

### 1. Backward Compatibility Property
```python
@property
def ongrid_tiles(self) -> TTile:
    active_layer = self.layer_manager.get_active_layer()
    return active_layer.tiles if active_layer else {}
```
**Why:** Allows existing code (tile_grid, autotiler, etc.) to work without modification. Zero breaking changes.

### 2. Dual Save Format
**Why:** Ensures compatibility with tools/scripts expecting old format while enabling layer features for new saves.

### 3. Active Layer Pattern
**Why:** Simple mental model - "Place tiles on the active layer". No complex logic needed in tile_grid.

### 4. Layer Lock vs. Layer Visibility
- **Lock:** Prevents accidental modification
- **Visibility:** Doesn't affect data, only rendering

**Why:** Separate concerns allow flexible UI control.

### 5. Z-Index Auto-Management
Layers maintain positions in list; z_index auto-updated when reordering.

**Why:** Prevents duplicate z-indices and keeps rendering order predictable.

## Next Steps (Phase 4-5)

### Phase 4: TileGrid Integration
**File to modify:** `src/widgets/tile_grid.py`

Changes needed:
1. Replace `self.editor.tilemap.ongrid_tiles` with property access (already works)
2. Update render() to use `layer_manager.get_rendered_layers()`
3. Update place_tile() to target active layer (already works via property)
4. Add optional layer highlighting during paint
5. Test all placement operations on different layers

### Phase 5: Editor Layout
**File to modify:** `src/editor.py`

Changes needed:
1. Import LayerSelector: `from widgets.layer_selector import LayerSelector`
2. Add initialization in Editor.__init__():
   ```python
   tileset_h = 300  # Current height
   layer_h = 150    # New layer selector height
   
   self.tileset_widget = TileSelector(self, 0, 0, 300, tileset_h)
   self.layer_widget = LayerSelector(self, 0, tileset_h, 300, layer_h)
   ```
3. Adjust tile_grid_widget to accommodate new layout
4. Update draw() and handle_event() to include layer_widget

## Testing Strategy

### Compatibility Tests (Before Phase 4)
```python
# Test backward compatibility
def test_ongrid_tiles_property():
    tilemap = Tilemap(editor)
    tilemap.ongrid_tiles[(0, 0)] = tile_data  # Should work
    assert (0, 0) in tilemap.ongrid_tiles  # Should work
    
# Test layer system
def test_layer_manager():
    mgr = create_default_layer_manager()
    assert mgr.get_layer_count() == 2
    mgr.create_layer("New")
    assert mgr.get_layer_count() == 3
```

### Save/Load Tests
```python
# Test new format save
def test_save_new_format():
    # Create layers, add tiles
    # Save map
    # Verify JSON has "layers" section
    
# Test legacy format load
def test_load_legacy_format():
    # Load old single-layer save
    # Verify loads into first layer
    # Verify no data loss
```

### UI Tests
- Layer list displays correctly
- Click selection works
- Drag-to-reorder works
- Add/Remove buttons function
- Tile placement on different layers works

## Compatibility Analysis

### ✅ Full Compatibility (No Changes Needed)
- `src/utils/serialization.py` - Generic serialization
- `src/constants.py` - Constants
- `src/widgets/tile_selector.py` - Tile selection (width unchanged)
- `src/widgets/mapsetup.py` - Map initialization
- `src/widgets/filemanager.py` - File operations
- `src/widgets/autotiler.py` - Autotiler (uses active layer via property)

### ⚠️ Requires Minor Changes
- `src/editor.py` - Add LayerSelector widget and layout adjustments
- `src/widgets/tile_grid.py` - Already compatible via property, but should use `get_rendered_layers()` for optimization

### 🔄 Already Refactored
- `src/tilemap.py` - Full layer support with backward compatibility
- `src/layers.py` - New core layer system

## File Structure Summary

```
src/
  layers.py                    # NEW - Core layer system (400 lines)
  tilemap.py                   # MODIFIED - Layer support + backward compat
  
  widgets/
    layer_selector.py          # NEW - Layer UI widget (250 lines)
    tile_grid.py              # READY (no changes needed yet)
    tile_selector.py          # READY (no changes needed)
    autotiler.py              # READY (works via property)
    filemanager.py            # READY
    mapsetup.py               # READY
    
  editor.py                    # READY (minor layout changes needed)
  main.py
  constants.py
  event_map.py
  utils/
```

## Risk Assessment

| Risk | Probability | Mitigation |
|------|-------------|-----------|
| Breaking existing saves | Very Low | Comprehensive backward compatibility layer |
| Tile placement on wrong layer | Low | Property pattern ensures active layer targeting |
| UI layout issues | Low | Relative positioning in layout functions |
| Performance regression | Very Low | O(1) active layer access, efficient layer iteration |

## Performance Notes

- **Memory:** Minimal increase (layer metadata only, no tile duplication)
- **CPU:** No regression (property access is ~0 cost, layer iteration is O(n) where n ≤ 10 typically)
- **Rendering:** Can be optimized with `get_rendered_layers()` filtering

## Code Quality

- **Lines of Code:** ~650 new
- **Modularity:** Clean separation of concerns
- **Type Hints:** Full type annotations throughout
- **Documentation:** Docstrings on all public methods
- **Testing:** Ready for unit tests

---

**Status:** 60% Complete - Ready for Phase 4 (TileGrid Integration)
**Estimated Time for Phase 4-5:** 1-2 hours of testing and integration

