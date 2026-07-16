# Toolbar Refactoring Plan

## Current State

### Architecture (before refactor)

```
Toolbar (toolbar.py)           ← 164 lines, NOT refactored
  ├── Directly writes self.editor.pan_mode / select_mode / eraser_mode
  ├── Text labels on buttons (no icons for select/eraser/auto/nodes)
  ├── Manual Rect layout (no WidgetBase)
  ├── Mutual exclusion enforced with if/else chains (3x duplication)
  │
  ├── Editor (editor.py:156-161)     ← 6 mode booleans
  ├── TileGrid (tile_grid.py:417)    ← reads editor booleans directly
  ├── Editor keyboard shortcuts      ← duplicate mutual exclusion
  └── IconManager (icon_manager.py)  ← 20 fallback icons, 35 SVGs
```

### Current Toolbar Buttons (10)

| Key | Label | Has Icon? | Binds |
|-----|-------|-----------|-------|
| pan | Pan | `pan.svg` + fallback | `editor.pan_mode` |
| select | Select | **none** — renders text | `editor.select_mode` |
| eraser | Eraser | **none** — renders text | `editor.eraser_mode` |
| grid | Grid | `grid.svg` | `editor.toggle_grid()` |
| auto | Auto | **none** — renders text | `editor.toggle_auto_autotile()` |
| nodes | Nodes | **none** — renders text | `editor.show_nodes` |
| zoom_out | Zoom- | key mismatch `"zoom_out"` vs `"zoomout"` | `tile_grid.zoom_by(-0.1)` |
| zoom_in | Zoom+ | key mismatch `"zoom_in"` vs `"zoomin"` | `tile_grid.zoom_by(0.1)` |
| reset | Reset | `reset.svg` + fallback | `tile_grid.reset_view()` |
| fit | Fit | `fit.svg` + fallback | `tile_grid.fit_to_map()` |

### Problems

1. **No tool abstraction** — 6 plain booleans on Editor, no single source of truth
2. **Mutual exclusion** — copied in toolbar.py, editor.py keyboard handlers, and tile_grid.py
3. **Missing icons** — 4 buttons have no icon, 2 have key name mismatches
4. **No WidgetBase** — toolbar uses manual Rect layout, not the refactored pattern
5. **Draw duplicates logic** — `draw()` re-evaluates `is_active` with same if/elif chain as `handle_event()`
6. **Fixed 74px buttons** — doesn't adapt to icon-only mode (wastes space)
7. **No separators** — hardcoded `x += 6` gap between zoom and view tools
8. **Object tools missing** — no dedicated select/erase for objects (rect select only works for tiles)

---

## Target Design (Tiled-inspired)

```
┌──────────────────────────────────────────────────────────────────────┐
│ [pan] [select] [eraser] [fill] [ | ] [grid] [auto] [nodes] [ | ] [zoom-] [zoom+] [reset] [fit] │
└──────────────────────────────────────────────────────────────────────┘
     icon    icon     icon    icon          icon    icon    icon          icon    icon    icon   icon
```

- **Icon-only buttons** (~28×28px) with tooltips on hover — no text labels
- **Separator bars** (`|`) between logical groups
- **Theme-aware** — follows global COLORS/SHAPE via WidgetBase
- **Tooltip** on every button (already works)
- **Active state** highlighted with `COLORS.accent_active`
- **Keyboard shortcuts** shown in tooltip

### Icon Requirements

Current gap — need **placeholder SVGs** for:

| Key | Replace With | Current |
|-----|-------------|---------|
| `select` | Select cursor / rectangle icon | text "Select" |
| `eraser` | Eraser icon | text "Eraser" |
| `auto` | Auto-tile wand icon | text "Auto" |
| `nodes` | Node/graph icon | text "Nodes" |
| `zoom_in` | Fix key to `"zoomin"` | key mismatch |
| `zoom_out` | Fix key to `"zoomout"` | key mismatch |

---

## Phase 0: Entry Point — Tool Abstraction

This is the **first branch**. Minimal, self-contained, no visual changes — just decouples the toolbar from raw editor booleans.

### Step 0a: Create `ToolKind` enum and `ToolManager`

**New file:** `src/widgets/ui/tool_kind.py`

```python
from enum import Enum
from typing import Optional


class ToolKind(Enum):
    PAINT = "paint"         # default — no toolbar button
    SELECT = "select"
    ERASER = "eraser"
    PAN = "pan"


class ToolManager:
    """Central tool state. Single source of truth for active tool."""

    def __init__(self):
        self._active: Optional[ToolKind] = None
        self._prev: Optional[ToolKind] = None

    @property
    def active(self) -> Optional[ToolKind]:
        return self._active

    def activate(self, tool: ToolKind) -> None:
        self._prev = self._active if self._active != tool else self._prev
        self._active = tool

    def toggle(self, tool: ToolKind) -> None:
        if self._active == tool:
            self._active = self._prev or None
        else:
            self._prev = self._active
            self._active = tool

    def deactivate(self) -> None:
        self._prev = self._active
        self._active = None

    def is_active(self, tool: ToolKind) -> bool:
        return self._active == tool
```

### Step 0b: Replace editor booleans with ToolManager

In `editor.py`:
- Replace `self.pan_mode`, `self.select_mode`, `self.eraser_mode` with `self.tool_manager = ToolManager()`
- Keep `self.autotile_mode`, `self.show_nodes`, `self.node_editing_mode` as separate booleans (they aren't tools in the same sense)

Keyboard shortcuts (Ctrl+Space pan toggle) and tile_grid booleans all redirect through `self.tool_manager`.

### Step 0c: Refactor Toolbar to use ToolManager via callbacks

- Each tool button gets an `on_click` lambda: `lambda: editor.tool_manager.toggle(ToolKind.PAN)`
- `draw()` queries `editor.tool_manager.is_active(ToolKind.PAN)` for active state
- Adds placeholder procedural fallback icons for missing tool icons (select, eraser) in `icon_manager.py`
- Fixes key name mismatch: `"zoom_in"` → `"zoomin"`, `"zoom_out"` → `"zoomout"`

### Step 0d: Refactor TileGrid to use ToolManager

In `tile_grid.py`:
- `self.editor.select_mode` → `self.editor.tool_manager.is_active(ToolKind.SELECT)`
- `self.editor.eraser_mode` → `self.editor.tool_manager.is_active(ToolKind.ERASER)`
- `self.editor.pan_mode` → `self.editor.tool_manager.is_active(ToolKind.PAN)`

### Files Touched (Phase 0)

| File | Change |
|------|--------|
| NEW `src/widgets/ui/tool_kind.py` | ~40 lines — ToolKind enum + ToolManager |
| `src/editor.py` | Replace 3 booleans with `self.tool_manager`, update keyboard shortcuts |
| `src/widgets/ui/toolbar.py` | Use `editor.tool_manager.toggle()` via on_click, query for draw state |
| `src/widgets/tile_grid.py` | `self.editor.select_mode` → `tool_manager.is_active(ToolKind.SELECT)` |
| `src/utils/icon_manager.py` | Add fallback icons for `"select"`, `"eraser"`, `"auto"`, `"nodes"`; fix key aliases |
| (watch for) `src/plugins/*.py` | Any file reading `editor.pan_mode` etc — search needed |

### Risk: Search for all `editor.pan_mode` / `editor.select_mode` / `editor.eraser_mode` references

Must update every consumer. Candidates:
- `editor.py` — tool toggles + keyboard shortcuts
- `tile_grid.py` — event dispatch
- `toolbar.py` — button click + draw
- `menubar.py` — menu actions
- Any `plugin/*.py` — check

---

## Phase 1: Visual Refactor

After the tool abstraction is stable, refactor the toolbar appearance:

### Step 1a: Convert to WidgetBase + Button composition

- `Toolbar(WidgetBase)` — the container
- Each tool button is a `Button(WidgetBase)` instance, not a `Rect` + text
- Icon rendered via `icon_manager.get_icon(key, 20, color)` at 20px instead of 16px
- No text labels (icon-only), tooltip on hover

### Step 1b: Icon-only compact layout

- Button size: 28×28px with 2px padding
- Separator: thin vertical line (2px wide, 16px tall) between groups
- Groups: (pan, select, eraser, fill) | (grid, auto, nodes) | (zoom-, zoom+, reset, fit)

### Step 1c: Tiled-style toolbar features

- **Permanent tooltip** on hover showing name + shortcut
- **Active indicator** — filled background on active tool
- **Toggle state** — grid/auto/nodes show as toggle buttons
- **Disabled state** — future tools can show disabled

### Files Touched (Phase 1)

| File | Change |
|------|--------|
| `src/widgets/ui/toolbar.py` | Full rewrite: WidgetBase, Button children, icon-only layout |
| `src/widgets/ui/button.py` | May need `set_active(is_active)` style method or icon-only variant |

---

## Phase 2: Separator + Object Tools

After the basic toolbar looks right, add object-aware tools:

### Step 2a: Object-aware Select

- New `ObjectSelectTool` class (or behavior in TileGrid)
- Click on object → select it, begin drag-to-move
- Follows node pattern (`_handle_show_node_event`) and character collision editor pattern
- No rect selection for objects (for now)

### Step 2b: Object-aware Eraser

- Eraser on object layers uses tile-size rect (fix for 1×1 pixel bug)
- Match the pattern from the node eraser behavior

### Step 2c: Separator bar SVG icon

- Add `separator.svg` (thin vertical line, to be provided by user)
- Or draw programmatically in toolbar.draw()

---

## Phase 3: Theme + CLI Polish

### Step 3a: Custom theme loading

- Load `.json` theme files from a well-known path (e.g., `~/.config/tilemap-editor/themes/`)
- CLI `--theme <path>` argument to load a custom theme file at startup
- `settings.json` `"theme"` field can be a name (built-in) or path

### Step 3b: Toolbar theme colors

- Ensure toolbar-specific colors use `COLORS.*` everywhere (already works via dynamic proxy)
- Add `COLORS.toolbar_bg`, `COLORS.toolbar_button` if needed for customization

---

## Branch Strategy

```
main
├── refactor/tool-abstraction      ← Phase 0 (entry point — minimal, safe)
├── refactor/toolbar-ui            ← Phase 1 (visual refactor — WidgetBase + icons)
├── refactor/separator-object-tools ← Phase 2 (object selection + eraser)
├── feat/theme-cli                 ← Phase 3 (CLI theme arg)
└── ... (each tool can branch further if needed)
```

Each branch is self-contained, minimal, and builds on the previous one.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `editor.pan_mode` used in plugins | Search with `rg "editor\.(pan_mode\|select_mode\|eraser_mode)"` before Phase 0 |
| Toolbar position/y changes affect other widgets | Keep toolbar at y=30, height=35 unchanged until Phase 1 |
| Missing icons break layout | Add fallback procedural icons in Phase 0 Step 0c before refactoring layout |
| ToolManager doesn't cover all editor booleans | Keep `autotile_mode`, `show_nodes`, `node_editing_mode` as booleans — not all are "tools" |
| The clipboard/menubar also use toolbar-like buttons | Don't refactor those in Phase 0 — only the main toolbar |

---

## Verification

After each phase:
```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m ruff check src/
.venv/bin/python -c "import ast; ast.parse(open('src/widgets/ui/toolbar.py').read())"
```

Launch editor and manually test:
1. All 10 toolbar buttons toggle correctly
2. Mutual exclusion works (pan disables select disables eraser)
3. Grid, auto, nodes toggle independently
4. Zoom in/out/reset/fit work
5. Tooltips appear on hover
6. Resize window → toolbar re-layouts
7. Theme switch propagates to toolbar colors
