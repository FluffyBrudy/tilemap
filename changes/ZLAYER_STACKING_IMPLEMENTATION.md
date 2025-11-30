# Z-Index Layer Stacking Implementation

## Overview
Implemented visual layer stacking based on z-index with independent visibility toggle. Layers now display with proper depth ordering without fully blocking lower layers, and visibility can be controlled via the eye icon without changing the active layer selection.

## Key Changes

### 1. **Rendering Logic (tile_grid.py)**
   - **Changed from**: Single active layer rendering
   - **Changed to**: Multi-layer rendering based on z-index order
   
   **Details**:
   - Modified `render()` method to iterate through ALL visible layers sorted by z-index
   - Uses `tilemap.layer_manager.get_rendered_layers()` which returns layers sorted by z-index and filtered by visibility
   - Each layer is rendered in order, creating proper stacking effect
   - Added opacity support: layers with opacity < 1.0 are rendered to a temporary surface with alpha blending
   - Lower z-index layers appear behind, higher z-index layers appear in front

   ```python
   rendered_layers = tilemap.layer_manager.get_rendered_layers()
   for layer in rendered_layers:
       # Render each layer, creating stacking effect
   ```

### 2. **Layer Visibility Toggle (layer_selector.py)**
   - **Added**: Eye icon click handler to toggle layer visibility
   - **Effect**: Clicking the eye icon toggles `layer.visible` WITHOUT changing active layer
   - **Selection remains**: Clicking elsewhere on the layer still selects it as active
   
   **Implementation**:
   - Added `_get_eye_icon_rect()` method to detect clicks on eye icon
   - Added `_get_lock_icon_rect()` method to detect clicks on lock icon
   - Updated `handle_event()` to check for icon clicks before regular selection
   - Eye icon toggles visibility independently

### 3. **Improved Icon Visuals (layer_selector.py)**

   **Eye Icon**:
   - **Visible (on)**: Green circle with highlight dot (👁️)
     - Color: (100, 200, 100)
     - Shows layer is visible
   - **Hidden (off)**: Gray X symbol (⊘)
     - Color: (100, 100, 100)
     - Shows layer is hidden

   **Lock Icon**:
   - **Locked**: Red/orange filled square
     - Color: (200, 100, 100)
     - Layer cannot be edited
   - **Unlocked**: Gray empty square
     - Color: (100, 100, 100)
     - Layer can be edited

## User Interaction

### Clicking on a Layer Item
1. **Click anywhere on layer (except icons)**: 
   - Layer becomes active (selected)
   - Can now place/edit tiles on this layer
   - Other layers remain visible if they are visible

2. **Click eye icon (🔍)**: 
   - Toggles visibility on/off
   - Does NOT change active layer
   - Hidden layers don't render but can still be edited if selected

3. **Click lock icon (🔒)**: 
   - Toggles lock/unlock
   - Locked layers cannot be edited
   - Locked layers are still visible

### Visual Result
- Multiple layers visible simultaneously
- Proper depth ordering (lower layers behind, upper layers in front)
- Can see through semi-transparent layers (opacity < 1.0)
- Can toggle visibility without losing your active layer selection

## Technical Details

### Z-Index System
- Z-index = layer position in the layers list (0 = bottom, n = top)
- Automatically updated when layers are reordered
- Used by `get_rendered_layers()` to sort layers for rendering

### Visibility System
- Each layer has a `visible` boolean property
- `get_rendered_layers()` filters out invisible layers
- Toggled by clicking the eye icon

### Opacity System
- Each layer has an `opacity` float (0.0 to 1.0)
- Rendered with alpha blending when < 1.0
- Temporary surface used to preserve layer transparency

## Benefits

✅ **Better Composition**: See how layers interact visually before hiding them
✅ **Non-Destructive Visibility**: Toggle visibility without affecting layer selection
✅ **Proper Depth**: Layers stack correctly by z-index
✅ **Visual Feedback**: Icons clearly show layer status
✅ **Flexible**: Can still edit any layer regardless of visibility (except if locked)

## Testing Checklist

- [ ] Create multiple layers with tiles
- [ ] Click eye icon to hide/show layers
- [ ] Verify active layer selection works independently of visibility
- [ ] Drag layers to reorder and verify stacking changes
- [ ] Set layer opacity and verify transparency
- [ ] Lock/unlock layers and verify edit behavior
