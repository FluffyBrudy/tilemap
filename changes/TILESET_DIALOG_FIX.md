# Tileset Type Dialog Fix

## Issue
When loading a map file via Ctrl+O, the editor was incorrectly showing the "Is this an object or tile tileset?" dialog for each tileset in the map. This dialog should **ONLY** appear when the user manually selects tileset images (.png files) from the file manager.

## Root Cause
The `load_map()` method was calling `on_file_selected()` for each tileset path in the saved map file. The `on_file_selected()` method was designed for manual user selections and always triggered the tileset_type_dialog.

```python
# BEFORE (Wrong)
for path_str in payload["resources"]["tilesets"]:
    p = Path(path_str)
    if not p.is_absolute():
        p = BASE_PATH / p
    self.editor.tileset_widget.on_file_selected(p)  # Shows dialog!
```

## Solution
Separated the code paths for **manual tileset addition** (needs dialog) and **map-based tileset loading** (already knows type).

### 1. Updated Save Format
Modified `src/tilemap.py` to save both tileset path AND type in map files:

```python
# BEFORE
save_data["resources"]["tilesets"].append(str(rel))

# AFTER
save_data["resources"]["tilesets"].append({
    "path": path_str,
    "type": ts.tileset_type
})
```

### 2. Created Silent Loading Method
Added `load_tileset_from_path()` method in `src/widgets/tile_selector.py`:

```python
def load_tileset_from_path(self, path: Path, tileset_type: str):
    """Load tileset from path without showing dialog (used when loading maps)."""
    if path.exists():
        try:
            surf = pygame.image.load(path).convert_alpha()
            if is_image_multipleof(surf.get_size(), self.editor.tilemap.tile_size):
                # Create and add tileset directly without dialog
                tileset_data = TilesetData(path.name, path, surf, tileset_type=tileset_type)
                self.tilesets.append(tileset_data)
                self.active_idx = len(self.tilesets) - 1
                self.tileset_map[self.active_idx] = tileset_data
```

### 3. Updated Load Logic
Modified `load_map()` in `src/tilemap.py` to use the new method:

```python
for ts_entry in payload["resources"]["tilesets"]:
    # Handle both old format (string) and new format (dict with path and type)
    if isinstance(ts_entry, str):
        # Legacy format: just a path string, default to "tile" type
        path_str = ts_entry
        tileset_type = "tile"
    else:
        # New format: dict with path and type
        path_str = ts_entry.get("path", "")
        tileset_type = ts_entry.get("type", "tile")
    
    p = Path(path_str)
    if not p.is_absolute():
        p = BASE_PATH / p
    
    # Load tileset silently without showing dialog
    self.editor.tileset_widget.load_tileset_from_path(p, tileset_type)
```

## Behavior Changes

| Scenario | Before | After |
|----------|--------|-------|
| Ctrl+O to load map | Shows dialog for each tileset | No dialog, silent load |
| Manual tileset add via File Manager | Shows dialog | Shows dialog ✓ |
| Reopen existing map | Shows dialog | No dialog ✓ |

## Backward Compatibility
The solution handles both old (string) and new (dict with type) tileset formats:
- Old maps saved with just paths will default to "tile" type
- New maps will save both path and type, allowing exact restoration

## Files Modified
1. `src/tilemap.py`
   - Updated save_data to include tileset type
   - Updated load_map() to use new silent loading method
   - Added backward compatibility for old format

2. `src/widgets/tile_selector.py`
   - Added new `load_tileset_from_path()` method
   - Kept `on_file_selected()` unchanged for manual user additions
