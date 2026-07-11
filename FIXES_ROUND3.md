# Code Review Fixes - Round 3

All issues addressed with minimal changes, validated with no diagnostics errors.

## Fixed Issues

### 1. ⏭️ Theme persistence - SKIPPED
Per user request, not implementing yet.

### 2. ✅ editor.py - _effective_selector_w (lines 583-605, 1302-1323, 1362)
Store clamped selector width as `_effective_selector_w` and reuse it consistently:
- Layout calculation uses remaining available width
- Sidebar sizing uses effective width
- Resize handle rendering uses effective width
- Event hit-testing uses effective width
- Prevents tile-grid rect from exceeding window
- Keeps divider consistently aligned

### 3. ✅ input.py - Clipping intersection (lines 155-160)
Intersect `content_rect` with existing clip before applying:
- Preserves caller's narrower viewport
- Prevents drawing outside parent container
- Retains existing restoration logic

### 4. ✅ tile_grid.py - Pixel offset reset for tiles (line 1059)
Reset `_selection_pixel_offset` to (0,0) after tile layer move:
- Prevents offsets from prior object moves from persisting
- Tile selections always aligned to grid
- Object selections retain pixel precision
- Preserves existing behavior for other layer types

## Summary

All changes minimal, focused, and validated:
- No diagnostics errors
- No redundant comments
- Proper behavior preservation
- Clean separation of concerns
