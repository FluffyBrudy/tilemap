# Layer System Architecture

## Current Architecture Analysis
- **Single Layer**: Currently uses `tilemap.ongrid_tiles` dict only
- **Data Structure**: `Dict[Tuple[int, int], TypeTile]` - position to tile mapping
- **Rendering**: `TileGrid.render()` directly accesses `tilemap.ongrid_tiles`
- **Tile Placement**: `TileGrid.place_tile()` directly modifies `tilemap.ongrid_tiles`
- **Persistence**: Saved/loaded from `data/ongrid` section in JSON

## Proposed Multi-Layer Architecture

### 1. Layer System (New File: `src/layers.py`)
```
Layer:
  - name: str (e.g., "Terrain", "Objects")
  - layer_type: "tile" | "object"  (for future extensibility)
  - tiles: Dict[Tuple[int, int], TypeTile]
  - visible: bool
  - locked: bool
  - opacity: float (0.0-1.0)
  - z_index: int (for rendering order)

LayerManager:
  - layers: List[Layer]
  - active_layer_idx: int
  - methods: create_layer, delete_layer, get_active_layer, reorder_layers, etc.
```

### 2. Widget Changes

#### LayerSelector Widget (New: `src/widgets/layer_selector.py`)
- Position: Below tileset_selector
- Features:
  - List of layers with visual indicators (eye icon for visibility, lock icon)
  - Click to select active layer
  - Drag to reorder (z-index)
  - Right-click context menu: rename, delete, duplicate, lock/unlock
  - Add/remove layer buttons

#### TileSelector Widget Changes
- Reduce height by Y pixels (to make room for LayerSelector)
- Keep scrolling behavior intact

### 3. Core Module Changes

#### `tilemap.py` Refactoring
- Replace `self.ongrid_tiles` with `self.layer_manager`
- Add backward compatibility layer for loading old saves
- New properties:
  - `get_active_layer()` → returns current layer
  - `get_layer(idx)` → access specific layer
  - Save/load layer structure to `data/layers` section

#### `tile_grid.py` Refactoring
- Change `self.editor.tilemap.ongrid_tiles` to `self.editor.tilemap.get_active_layer().tiles`
- Add optional layer highlighting during paint
- Update deletion to remove from active layer only

#### `editor.py` Layout Adjustment
- Keep TileSelector at current width (300px)
- Add LayerSelector below with same width
- Adjust tile_grid_widget height to accommodate new widget

### 4. Backward Compatibility

#### Old Format Detection
- If save file has `data/ongrid`, create default layer named "Default"
- If save file has `data/layers`, load into layer system

#### File Format Evolution
```json
{
  "data": {
    "ongrid": {...},  // Legacy: auto-converts to layers
    "layers": [       // New format
      {
        "name": "Terrain",
        "type": "tile",
        "visible": true,
        "locked": false,
        "z_index": 0,
        "tiles": {...}
      },
      {
        "name": "Objects",
        "type": "tile",
        "visible": true,
        "locked": false,
        "z_index": 1,
        "tiles": {...}
      }
    ]
  }
}
```

## Risk Analysis & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Breaking existing saves | High | Full backward compatibility layer |
| Breaking tile placement | High | Extensive testing of place_tile/remove_tile |
| Breaking autotiler | Medium | Update layer hints to work with active layer |
| Performance regression | Medium | Keep efficient layer lookup (O(1) active layer) |
| UI layout issues | Medium | Careful height calculations |

## Implementation Order

1. **Phase 1: Foundation** (src/layers.py)
   - Create Layer and LayerManager classes
   - Write unit tests

2. **Phase 2: Core Integration** (tilemap.py)
   - Refactor Tilemap to use LayerManager
   - Add backward compatibility loading
   - Update save format

3. **Phase 3: UI Integration** (layer_selector.py + editor.py)
   - Create LayerSelector widget
   - Adjust editor layout
   - Connect to LayerManager

4. **Phase 4: Dependent Systems** (tile_grid.py, autotiler.py)
   - Update TileGrid for layer awareness
   - Test tile placement on different layers
   - Verify autotiler still works

5. **Phase 5: Testing & Polish**
   - Full integration tests
   - Save/load verification
   - UI/UX improvements

## Files to Create/Modify

### New Files
- `src/layers.py` - Core layer system
- `src/widgets/layer_selector.py` - Layer UI widget

### Modified Files
- `src/tilemap.py` - Use LayerManager
- `src/editor.py` - Add LayerSelector widget
- `src/widgets/tile_grid.py` - Work with active layer
- `src/widgets/autotiler.py` - Layer-aware hints (optional)
- `src/ttypes/tilemap.py` - Add layer types

### No Changes Needed
- `src/constants.py`
- `src/utils/*`
- `src/widgets/tile_selector.py` (width stays same)
- `src/widgets/mapsetup.py`
- `src/widgets/filemanager.py`

