# layers.move_object() TypeObject Area Fix

## Issue
The `move_object()` method in `src/layers.py` was attempting to set `self.objects[obj_id]["pos"]`, but `TypeObject` no longer has a `pos` field after the refactoring to use area-based placement.

**TypeObject structure changed from:**
```python
TypeObject(
    pos: Tuple[int, int],      # OLD
    width: int,                 # OLD
    height: int,                # OLD
    ...
)
```

**To:**
```python
TypeObject(
    area: TypeArea {            # NEW
        x: int,
        y: int,
        w: int,
        h: int
    },
    ...
)
```

## Root Cause
When `TypeObject` was refactored to use area-based placement instead of scattered `pos`/`width`/`height` fields, the `move_object()` method in `layers.py` was not updated to match. Additionally, the test helper function `create_test_object()` in `test_layers.py` was still using the old structure.

## Solution

### 1. Fixed move_object() in src/layers.py
Changed from setting the old `pos` field to updating area coordinates:

```python
# BEFORE (Wrong)
def move_object(self, obj_id: int, new_pos: Tuple[int, int]) -> bool:
    """Move an object to a new position. Returns True if successful."""
    if not self.locked and obj_id in self.objects:
        self.objects[obj_id]["pos"] = new_pos  # ❌ pos doesn't exist
        return True
    return False

# AFTER (Correct)
def move_object(self, obj_id: int, new_pos: Tuple[int, int]) -> bool:
    """Move an object to a new position. Returns True if successful."""
    if not self.locked and obj_id in self.objects:
        # Update the area position (area.x, area.y)
        self.objects[obj_id]["area"]["x"] = new_pos[0]
        self.objects[obj_id]["area"]["y"] = new_pos[1]
        return True
    return False
```

### 2. Fixed create_test_object() in test_layers.py
Updated the test helper to create TypeObject with proper area structure:

```python
# BEFORE (Wrong)
def create_test_object(
    pos: Tuple[int, int] = (50, 20),
    ttype: str = "1",           # ❌ was string, should be int
    variant: int = 3,
    width: int = 64,
    height: int = 48,
) -> TypeObject:
    """Create a test object."""
    return TypeObject(pos=pos, ttype=ttype, variant=variant, width=width, height=height)

# AFTER (Correct)
def create_test_object(
    pos: Tuple[int, int] = (50, 20),
    ttype: int = 1,             # ✓ now int (tileset index)
    variant: int = 3,
    width: int = 64,
    height: int = 48,
) -> TypeObject:
    """Create a test object with area-based structure."""
    return TypeObject(
        area={"x": pos[0], "y": pos[1], "w": width, "h": height},
        ttype=ttype,
        tileset_type="tile",
        variant=variant
    )
```

### 3. Updated test assertions in test_layers.py
Changed `test_move_object()` assertions to use area coordinates:

```python
# BEFORE (Wrong)
assert layer.get_object(obj_id)["pos"] == (50, 20)    # ❌ pos doesn't exist

# AFTER (Correct)
assert layer.get_object(obj_id)["area"]["x"] == 50
assert layer.get_object(obj_id)["area"]["y"] == 20
```

Also fixed calls to `create_test_object()` with string tileset types:
```python
# BEFORE (Wrong)
obj1 = create_test_object((50, 20), "1", 3, 64, 48)   # ❌ "1" should be int 1

# AFTER (Correct)
obj1 = create_test_object((50, 20), 1, 3, 64, 48)     # ✓ int 1 for tileset index
```

## Test Results
**Before:** Type errors and test failures related to missing `pos` field
**After:** `test_move_object` passes ✓

Test output:
```
✓ Move object works
```

## Files Modified
1. **src/layers.py**
   - Updated `move_object()` to use `area["x"]` and `area["y"]` instead of `pos`

2. **test_layers.py**
   - Updated `create_test_object()` to create proper area-based TypeObject
   - Fixed `ttype` parameter from string to int (tileset index)
   - Updated `test_move_object()` assertions to check area coordinates
   - Fixed test data calls to use int for tileset indices

## Consistency
This fix ensures consistency across the codebase where objects are now uniformly represented with area-based placement:
- Object placement in UI (tile_grid.py) ✓
- Object serialization (serialization.py) ✓
- Object layer storage (layers.py) ✓
- Object movement (layers.move_object()) ✓
- Type definitions (ttypes/tilemap.py) ✓
