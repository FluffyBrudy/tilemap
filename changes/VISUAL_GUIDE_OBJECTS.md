## 🎨 Visual Guide - Object Tileset System

### Layer Creation Flow

```
┌─────────────────────────────────────────┐
│ BEFORE: Always created Tile Layer       │
├─────────────────────────────────────────┤
│                                         │
│  Click "+" in layers panel              │
│    ↓                                    │
│  Layer 3 (Tile Layer) ← No choice       │
│                                         │
└─────────────────────────────────────────┘

vs.

┌─────────────────────────────────────────┐
│ AFTER: Choose layer type                │
├─────────────────────────────────────────┤
│                                         │
│  Click "+" in layers panel              │
│    ↓                                    │
│  ┌──────────────────────────────────┐  │
│  │ Layer Type                       │  │
│  ├──────────────────────────────────┤  │
│  │ ◉ Tile Layer (grid-based)        │  │
│  │ ○ Object Layer (free-positioned) │  │
│  │ [OK]  [Cancel]                   │  │
│  └──────────────────────────────────┘  │
│    ↓                                    │
│  User selects "Object Layer"            │
│    ↓                                    │
│  Layer 3 (Object Layer) ← Your choice   │
│                                         │
└─────────────────────────────────────────┘
```

---

### Object Placement Flow

```
┌──────────────────────────────────────────────────────┐
│ BEFORE: Grid-aligned, multiple objects              │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Object Tileset:                                    │
│  ┌──────┬──────┐                                    │
│  │  1   │  2   │                                    │
│  ├──────┼──────┤                                    │
│  │  3   │  4   │ ← Select this 2x2 area            │
│  └──────┴──────┘                                    │
│                                                      │
│  Canvas (click at grid position):                   │
│  ┌────────────────┐                                 │
│  │    │    │    │ │                                 │
│  │────┼────┼────┼─│                                 │
│  │    │[1][2]   │ │ ← Click here (grid 3,2)        │
│  │────┼────┼────┼─│                                 │
│  │    │[3][4]   │ │ ← Creates 4 objects            │
│  └────────────────┘                                 │
│         Grid                                        │
│                                                      │
│  Result: 4 separate 32×32 objects                   │
│  ❌ Not what we want                                │
│                                                      │
└──────────────────────────────────────────────────────┘

vs.

┌──────────────────────────────────────────────────────┐
│ AFTER: Single object, exact positioning             │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Object Tileset:                                    │
│  ┌──────┬──────┐                                    │
│  │  1   │  2   │                                    │
│  ├──────┼──────┤                                    │
│  │  3   │  4   │ ← Select this 2x2 area            │
│  └──────┴──────┘                                    │
│                                                      │
│  Canvas (click anywhere):                           │
│  ┌────────────────┐                                 │
│  │                │                                 │
│  │         ◆      │ ← Click at (157, 93)            │
│  │      ┌──────┐  │ ← NO grid snapping              │
│  │      │1234  │  │                                 │
│  │      │      │  │                                 │
│  │      └──────┘  │                                 │
│  └────────────────┘                                 │
│      Any position                                   │
│                                                      │
│  Result: 1 object at (157,93) with size 64×64      │
│  ✅ Exactly what we want!                           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

### Tileset Type Difference

```
TILE TILESET                    OBJECT TILESET
┌──────┬──────┬──────┐         ┌──────┬──────┐
│      │      │      │         │      │      │
│  [0] │  [1] │  [2] │         │ NPC1 │ NPC2 │
├──────┼──────┼──────┤         ├──────┼──────┤
│      │      │      │         │      │      │
│  [3] │  [4] │  [5] │         │ Tree │Rock  │
├──────┼──────┼──────┤         └──────┴──────┘
│      │      │      │
│  [6] │  [7] │  [8] │         Grid of sprites
└──────┴──────┴──────┘         (Variable use)

Uniform grid                    Same grid format
All 32×32                       But for objects
For terrain/tiles              

Use on: Tile Layer              Use on: Object Layer
Placement: Grid cells           Placement: Exact pixels
```

---

### Multiple Layers

```
BEFORE:                         AFTER:
┌────────────────────┐         ┌────────────────────┐
│ LAYERS             │         │ LAYERS             │
├────────────────────┤         ├────────────────────┤
│ Tile Layer 1  ◉    │         │ Tile Layer 1  ◉    │
├────────────────────┤         ├────────────────────┤
│ Tile Layer 2       │         │ Object Layer 1     │
├────────────────────┤         ├────────────────────┤
│ Tile Layer 3       │         │ Object Layer 2  ◉  │
├────────────────────┤         ├────────────────────┤
│ Tile Layer 4       │         │ Tile Layer 2       │
├────────────────────┤         ├────────────────────┤
│ +    -             │         │ +    -             │
└────────────────────┘         └────────────────────┘
All tiles                       Mixed types
(Can't have                     (Can have
 all objects)                    multiple objects)
```

---

### Coordinate System

```
GRID-BASED (Tile Layer):
┌────┬────┬────┬────┐
│(0,0)(1,0)(2,0)(3,0)│
├────┼────┼────┼────┤
│(0,1)(1,1)(2,1)(3,1)│
├────┼────┼────┼────┤
│(0,2)(1,2)(2,2)(3,2)│
└────┴────┴────┴────┘
 Only 16 possible positions

PIXEL-BASED (Object Layer):
┌─────────────────────┐
│ (157,93)      ◆     │
│ (300,200)  ★        │
│ (45,320)   ▲        │
│            (123,50)▲│
└─────────────────────┘
 Infinite possible positions
```

---

### Object Data Comparison

```
TILE (on tile layer):
{
    "pos": (5, 3),              ← Grid coordinates
    "ttype": "0",               ← String
    "variant": 5,
}

vs.

OBJECT (on object layer):
{
    "pos": (157, 93),           ← Pixel coordinates
    "ttype": 2,                 ← Integer
    "tileset_type": "object",   ← NEW: type tracking
    "variant": 10,
    "width": 128,               ← NEW: full size
    "height": 64,               ← NEW: full size
}
```

---

### Selection Size Impact

```
SELECT 1 TILE:                 SELECT 2×2 TILES:
┌────┐                         ┌────┬────┐
│    │ ← 32×32                 │    │    │
│    │                         ├────┼────┤
└────┘                         │    │    │
                               └────┴────┘
Object: 32×32                  Object: 64×64

SELECT CUSTOM AREA:            SELECT CUSTOM AREA:
┌──────┐                       ┌──────────────┐
│      │ ← 64×48               │              │ ← 96×128
│      │                       │              │
└──────┘                       │              │
                               └──────────────┘
Object: 64×48                  Object: 96×128

Size = Selection size (not tile size)
```

---

### Rendering Pipeline

```
Object Layer Data:
┌──────────────────────────────────────────┐
│ {                                        │
│   "pos": (157, 93),                      │
│   "ttype": 2,                            │
│   "variant": 10,                         │
│   "width": 128,                          │
│   "height": 64                           │
│ }                                        │
└──────────────────────────────────────────┘
             ↓
    Get tileset from index
             ↓
    Get sprite from variant
    (at position: 10 % cols, 10 // cols)
             ↓
    Draw sprite at pixel position
    (157 - scroll_x, 93 - scroll_y)
             ↓
    Use object's width/height
    (not tile size)
             ↓
┌──────────────────────────────────────────┐
│ Canvas showing rendered object           │
│ at exact pixel position                  │
└──────────────────────────────────────────┘
```

---

### Workflow Comparison

```
OLD WORKFLOW:          NEW WORKFLOW:
1. Add tileset  ───┬─→ 1. Add tileset  ───┬─→
                   │    Tile only         │    Choose type
2. Create layer  ──┴─→ 2. Create layer  ──┴─→
   Always tile           Choose type

3. Place objects     3. Place objects
   Grid snapped         Free positioning
   Multiple objects     Single object
   32×32 only          Any size

RESULT:              RESULT:
- Limited           - Flexible
- Grid-aligned      - Pixel-perfect
- 4 objects         - 1 object
```

---

### Click Position Effect

```
Tile Layer:                    Object Layer (with object tileset):
┌──────────────┐              ┌──────────────┐
│  │  │  │     │              │              │
│──┼──┼──┼─────│              │    Click at  │
│  │▲ │  │ ←──┤ Click         │   (157,93)   │
│──┼──┼──┼─────│ at grid       │      ↓       │
│  │  │  │     │ (5,3)         │    ◆ Here   │
└──────────────┘              └──────────────┘

→ Tile placed at               → Object placed at
  grid position (5,3)            EXACT pixel (157,93)
  Which is pixel (160,96)        NOT at grid!
  (5 × 32, 3 × 32)
```

---

### Dialog Hierarchy

```
┌────────────────────────────────────┐
│ Editor                             │
├────────────────────────────────────┤
│                                    │
│  Dialogs (appear in order):        │
│  1. Save Input ─────────────┐      │
│  2. TilesetTypeDialog ─────┼──┐   │
│  3. LayerTypeDialog ───────┼──┼─┐ │
│     (All modal)            │  │ │ │
│                            │  │ │ │
│  When tileset dialog shown:│  │ │ │
│  └─────────────────────────┘  │ │ │
│     [Choose Tileset Type]      │ │ │
│                                │ │ │
│  When layer dialog shown:      │ │ │
│                 ┌──────────────┘ │ │
│                 [Choose Layer Type]│ │
│                                    │
│  Only one dialog visible at time   │
│                                    │
└────────────────────────────────────┘
```

---

### Summary Icons

```
✅ Multiple object layers
   Can create tile AND object layers in same project

✅ Single entity placement
   One selection = one object (not sliced up)

✅ Free positioning
   Click at (157,93) → object at (157,93)
   No grid snapping!

✅ Real coordinates
   Store actual pixel positions
   Not converted to grid indices

✅ Tiled-like behavior
   Works exactly like industry-standard editor
```

