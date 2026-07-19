# tilemap-editor — Agent Context

## Overview

Pygame-ce based 2D tilemap editor. Single dependency: `pygame-ce>=2.5`.
Published on PyPI as `tilemap-editor`.

## Python Rules

- **Requires Python >= 3.11**
- **Never use system/global Python** — always use the project venv
- Venv at project root: `.venv/`
- Activate: `.venv/bin/python` (do NOT `source .venv/bin/activate` in scripts)

## Quick Start

```bash
# Initialize project settings (first use only)
.venv/bin/python -m tilemap_editor init

# Run editor
.venv/bin/python -m tilemap_editor run
.venv/bin/python -m tilemap_editor run --size 1920x1080 --fps 60

# Tests
.venv/bin/python -m pytest tests/ -v

# Lint
.venv/bin/python -m ruff check src/

# Syntax check a file
.venv/bin/python -c "import ast; ast.parse(open('src/widgets/x.py').read())"
```

## Project Structure

```
src/
  tilemap_editor/         # Package entry point
    cli.py                # CLI: init / run commands
    settings.py           # `tilemap-editor init` — creates settings.json
    __main__.py           # python -m tilemap_editor
    assets/               # Bundled icons (SVG), fonts (Noto, JetBrains Mono)
  editor.py               # Main Editor class (~1400 lines) — owns all widgets, main loop
  tilemap.py              # Tilemap data model (~766 lines) — layers, tiles, autotile rules
  nodes.py                # Node / NodeRect dataclasses
  node_manager.py         # Node CRUD, sidecar JSON persistence
  main.py                 # Empty — placeholder for user boilerplate
  widgets/
    ui/                   # Reusable UI components
      dropdown.py         # Dropdown with scroll
      slider.py           # Slider with drag
      color_field.py      # Color picker
      node_editor.py      # Node properties panel (area + particle)
      node_selector.py    # Node list sidebar
      particle_config_dialog.py  # Full particle config dialog
      property_editor.py  # Generic property editor
      tree_widget.py      # Reusable tree with drag-drop, folders, icons
      region_selector.py  # Freeform region drawing/selection on images
      button.py           # Button(WidgetBase) with icon_key, hover/press/active
      toolbar.py          # Icon-only toolbar using Button + ToolManager
      menubar.py          # Top menu bar
      status_bar.py       # Status bar with status types
      notification.py     # Notification toasts
      sidebar_container.py # Tabbed sidebar container
      dialog_base.py      # Base modal dialog
      confirm_dialog.py, layer_type_dialog.py, tileset_type_dialog.py
      draw_utils.py       # truncate_text, draw_separator, draw_panel
    particle_presets.py   # 66 particle presets (11 categories)
    particle_system.py    # Editor-side particle simulation for preview
    tile_grid.py          # Main tile canvas — rendering, selection, particle preview
    tile_selector.py      # Tileset sidebar with tree panel (left 140px)
    filemanager.py        # File navigation
    autotiler.py          # Autotile rule designer
    spritesheet_grid.py   # Spritesheet grid overlay
    ...
  plugins/
    sprite_animation/     # Animation editor (standalone + integrated)
    tileset_collision/    # Tileset collision shape editor
    character_collision/  # Character collision shape editor
    object_tileset_collision/  # Object collision editor
    sprite_editor/        # Sprite editor (editor.py, standalone.py, dialogs.py, region_export.py)
  utils/
    error_handler.py      # Error capture + logging
    font_manager.py       # Font loading/caching
    icon_manager.py       # SVG icon rendering
    history.py            # Undo/redo
    project_paths.py      # Path resolution
    serialization.py      # JSON serialization helpers
    ...
  configs/
    themes.py             # Theme color definitions
  constants.py            # BASE_PATH, app constants
  layers.py               # Layer manager
```

## Architecture

```
Editor (editor.py)
  ├── Tilemap (tilemap.py)          — map data: layers, tiles, tile_size, map_size
  ├── NodeManager (node_manager.py) — node state + sidecar JSON persistence
  ├── TileGrid (widgets/tile_grid.py) — main rendering canvas
  ├── TileSelector (widgets/tile_selector.py) — tileset sidebar with tree panel (left 140px)
  ├── LayerSelector                 — layer list
  ├── NodeSelector / NodeEditor     — node list + property panel
  ├── MenuBar, Toolbar, StatusBar   — chrome
  ├── AutotileRuleDesigner          — autotile rules
  └── Plugins (sprite_animation, collision editors, etc.)
```

The Editor is the central orchestrator. Widgets communicate through the Editor reference (`self.editor`). There is no event bus or signal system — widgets pull state from `self.editor` directly.

## Data Persistence

Editor saves state as sidecar `.json` files alongside each map:

| Sidecar                        | Directory    | Contents                              |
| ------------------------------ | ------------ | ------------------------------------- |
| `<map>.nodes.json`             | `nodes/`     | Nodes (area, particle_emitter, group) |
| `<tileset>.collision.json`     | `collision/` | Tileset collision shapes              |
| `<spritesheet>.collision.json` | `collision/` | Character collision shapes            |
| `settings.json`                | root         | Project settings (paths, etc.)        |

Nodes are saved via `NodeManager.save()` — writes `nodes/<map_stem>.nodes.json` with `{"nodes": [...], "groups": [...]}`.

## Node System

Three node types defined in `widgets/ui/node_selector.py`:

| Type               | Label            | Color  |
| ------------------ | ---------------- | ------ |
| `area`             | Area Zone        | Green  |
| `group`            | Group / Folder   | Yellow |
| `particle_emitter` | Particle Emitter | Pink   |

`Node` dataclass (`nodes.py`):

```python
@dataclass
class Node:
    node_id: str          # UUID
    name: str
    node_type: str        # "area" | "group" | "particle_emitter"
    area: NodeRect        # x, y, w, h on the map
    layer_name: str
    properties: dict      # Type-specific config (particle params, tags, etc.)
    group: Optional[str]  # Group/folder membership
```

`node.properties` is a raw dict — no schema validation at editor level. For `particle_emitter` nodes, it holds the full particle system config (emission shape, colors, sizes, etc.).

## Particle System (Editor Preview)

- Presets: `widgets/particle_presets.py` — 66 presets across 11 categories
- Config dialog: `widgets/ui/particle_config_dialog.py` — full parameter editing with Dropdown, Slider, ColorField widgets
- Preview: `widgets/particle_system.py` — particle simulation + `tile_grid.py::reset_particle_preview()`
- Config lives in `node.properties` (NOT a separate `.particles.json` file)
- Editor particle code is independent of any external package

## UI Patterns

**Every widget follows:**

- `draw(screen)` — render to screen surface
- `handle_event(event)` — process pygame events, return `True` if consumed
- `resize(x, y, w, h)` — set position/size (called by parent)

**Scroll handling** — two paths for backward compatibility:

```python
# Legacy (button 4/5 events)
if event.button == 4:  # scroll up
if event.button == 5:  # scroll down

# Modern (MOUSEWHEEL event)
if event.type == pygame.MOUSEWHEEL:
    # event.y > 0 = scroll up, event.y < 0 = scroll down
```

**Modal dialogs** — set `self.active = True/False`, block interactions behind them.

## Linting & Code Style

- Ruff config: `ruff.toml` — `line-length = 88`, rules `E722`, `E701`, `F821`, `F841`
- snake_case for methods and variables
- `__slots__` on performance-critical classes (particle, hot UI components)
- Relative imports within the package: `from widgets.ui.x import Y`
- No `# type: ignore` unless justified and documented

## Testing

- pytest, 209+ tests in `tests/`
- Some tests require `pygame.display.init()` / `set_mode((1, 1))` (autouse fixture)
- Run: `.venv/bin/python -m pytest tests/ -v`
- Run single file: `.venv/bin/python -m pytest tests/test_x.py -v`

---

## Refactor Progress (Sessions 1–4 — WidgetBase, Theme, Toolbar, Plugin Refactor, Collision Editors)

### Done

- **WidgetBase** (`widget_base.py`) — base class with box model (padding, border, `content_rect`), `draw_base()` using `COLORS`/`SHAPE` from theme
- **MapSetup** — WidgetBase, Button, InputBox, SPACING; fixed OR text overlap between Create/Open buttons
- **InputBox** (`input.py`) — `InputBox(WidgetBase)`, `BaseTextInput`, `DigitInput`/`TextInput`; hardcoded colors→COLORS
- **Label** (`label.py`) — `Label(WidgetBase)` with alignment
- **Button** (`button.py`) — `Button(WidgetBase)` with hover/press/disabled, accent, `on_click`
- **DialogBase** + 3 dialogs (`confirm_dialog.py`, `layer_type_dialog.py`, `tileset_type_dialog.py`) — show/hide/center/draw helpers/handle_event_base
- **Theme** (`theme.py`) — COLORS (dynamic proxy), SHAPE, FONTS, SPACING; applied from `settings.json`
- **FileManager** — COLORS→theme COLORS, SysFont→FONTS, `InlineTextInput`→`InputBox`
- **TileSelector** — WidgetBase, `draw_base()` replaces `draw_background()`, FONTS, removed bottom buttons (→SidebarContainer)
- **SidebarContainer** (`widgets/ui/sidebar_container.py`) — tabbed container with toolbar; holds TileSelector + LayerSelector as tabs
- **Editor sidebar** — single `self.sidebar` widget; tabs replace tileset_h/layer_h split; vertical resize drag with SYSTEM_CURSOR_SIZEWE
- **draw_utils.py** — `truncate_text()`, `draw_separator()`
- **PropertyEditor** — SysFont→FONTS, hardcoded colors→COLORS, manual buttons→Button widgets, truncation + hover tooltip for long values (removed font-shrinking)
- **LayerSelector** — Button widgets replace manual rect buttons, `FONTS.get_*` replaces `font_manager.get_font(...)`, all color aliases removed in favor of `COLORS.*`, unused imports removed
- **MapProperties** — COLOR\_ constants→`COLORS.*`, `pygame.font.SysFont`→`FONTS.*`, `Rect` buttons→`Button` widgets, hardcoded colors→`COLORS.*`/`SHAPE.*`, manual draw→`Button.draw()`
- **ToolManager/ToolKind** (`tool_manager.py`) — central tool state replacing 6 editor booleans; mutual exclusion enforced in one place
- **Toolbar** — icon-only compact layout (28px), separator bars between groups, tooltips, `ToolManager` callbacks
- **Object-aware Select** — node hit detection, priority: selection move → node → rubber-band
- **Object-aware Eraser** — tile-size rect, unified step=1 adjustment, pixel-precise overlay
- **DragTracker** (`drag_tracker.py`) — float-precision world-coordinate delta computation (10 tests)
- **Bugfixes — Node resize** — 8 handle cases use `rs`-corrected absolute-position math (opposite-edge `* rs`, width delta `/ rs`)
- **Bugfixes — Object selection** — `_draw_selection_rect` uses `eff_w` for move offset; `_begin_move`/`delete_selection` use `eff_w` for hit-test (fixes move speed and multi-object selection at rs≠1)
- **Custom theme loading** — `UIColorSet.from_dict()` parses JSON; `ThemeManager.resolve_theme()` tries built-in → registered → file path; `ThemeManager.set_theme()` returns success bool
- **CLI `--theme`** — argument on `run` subcommand, accepts name or path to `.json` file; overrides `settings.json` `"theme"` field
- **TreeWidget** (`tree_widget.py`) — reusable tree widget with `TreeNode` dataclass, expand/collapse, multi-select, drag-drop, keyboard nav, scrollbar; integrated into TileSelector as 140px left panel replacing tab bar
- **TileSelector tree integration** — virtual folders (`+ Folder` button), `_sync_tree()` walks folder hierarchy, tileset/object icons via SVG, drag-drop folder reparenting with `while node in self.roots` dedup and `set_data` ID sanitization
- **Icons** — `folder.svg`, `tileset.svg`, `miniobj.svg`, `fold_down_arrow.svg`, `unfold_right_arrow.svg` in assets; icon_manager tints SVGs via `BLEND_RGBA_MULT` for theme compliance
- **Bugfixes — Sprite editor** — fixed missing `if ctrl:` block around keyboard shortcuts, incomplete `_detect_tile_size` return, bare `try` without `except` in `_on_add_sheets`, missing `SpritesheetGrid` import, missing `"""` on module docstring
- **Bugfixes — Standalone** — missing `try:` before `from .editor import SpriteEditor`, wrong indentation on `load_regions_for_image()`, broken `pygame.display.set_mode` call

### Session 4 — Plugin Refactor, Collision Editors, New Widgets

- **Scrollbar** (`scrollbar.py`) — reusable scrollbar with drag, track-click, mouse wheel; used by TreeWidget
- **Checkbox** (`checkbox.py`) — toggleable checkbox with label, hover/disabled states, `on_changed` callback
- **Tooltip** (`tooltip.py`) — `TooltipManager` with soft-rect background, auto-clamping to screen edges
- **FilenameInput** (`fileinput.py`) — modal filename input with autocomplete suggestions from data/ tree
- **ModeIndicator** (`mode_indicator.py`) — mode switcher with `Mode` dataclass, `can_enter`/`on_enter` callbacks
- **CollisionLayerMaskWidget** (`collision_layer_mask.py`) — Godot-inspired physics layer (radio) + mask (checkbox) bit selector, 16 layers
- **CollisionLayerSidebar** (`collision_layer_sidebar.py`) — slide-in overlay sidebar wrapping mask widget with toggle/close/dim
- **Character Collision plugin** (`plugins/character_collision/`) — shape editor for character collision polygons (editor, standalone, models, protocols)
- **Object Tileset Collision plugin** (`plugins/object_tileset_collision/`) — shape editor for object tileset collision (editor, standalone, models, protocols)
- **Sprite Animation refactor** — major timeline/frame-picker/preview cleanup, `clipboard_util`, `runtime_load`, `validation` modules
- **Sprite Editor refactor** — dialogs.py (+197 lines), region_export.py (+49 lines), editor.py significantly restructured
- **Tileset Collision refactor** — collision_painter, editor, models cleaned up
- **FileManager refactor** — 294 lines changed, folder creation blocker fix, input field sizing
- **TileGrid refactor** — node resize cleanup (`_node_drag_start` removal, explicit `int()` casts)
- **TileSelector refactor** — tree panel integration, folder hierarchy sync, icon-only tree
- **ttypes package** (`src/ttypes/`) — typed tilemap model definitions
- **New utils** — `icons_cache.py`, `editor_preference.py`, `log_capture.py`, `standalone.py`, `validation.py`
- **14 new test files** — collision layer mask/sidebar, editor pan mode, render scale, tile grid selection, tile selector pick, toolbar tools, autotile layers, GID collision, serialization regression, sprite animation grid, project paths, tilemap save
- **Bugfix — Folder blocker** — fixed filemanager folder creation blocking input
- **Bugfix — Input field inner size** — adjusted fileinput inner sizing

### Next

- (none)

### Relevant Files

- `src/widgets/widget_base.py`, `input.py`, `mapsetup.py`, `tile_selector.py`, `layer_selector.py`
- `src/widgets/ui/button.py`, `checkbox.py`, `collision_layer_mask.py`, `collision_layer_sidebar.py`
- `src/widgets/ui/sidebar_container.py`, `widget_base.py`, `label.py`, `dialog_base.py`, `theme.py`, `draw_utils.py`
- `src/widgets/ui/property_editor.py`, `tree_widget.py`, `scrollbar.py`, `tooltip.py`, `fileinput.py`, `mode_indicator.py`
- `src/widgets/ui/region_selector.py`
- `src/widgets/ui/confirm_dialog.py`, `layer_type_dialog.py`, `tileset_type_dialog.py`
- `src/widgets/ui/toolbar.py`, `tool_manager.py`, `drag_tracker.py`
- `src/widgets/tile_grid.py`, `tile_selector.py`, `filemanager.py`, `spritesheet_grid.py`, `autotiler.py`
- `src/tilemap_editor/cli.py`
- `src/tilemap_editor/assets/icons/` — SVG icons
- `src/editor.py`
- `src/plugins/sprite_editor/editor.py`, `standalone.py`, `dialogs.py`, `region_export.py`
- `src/plugins/sprite_animation/` — full plugin directory
- `src/plugins/tileset_collision/` — full plugin directory
- `src/plugins/character_collision/` — full plugin directory
- `src/plugins/object_tileset_collision/` — full plugin directory
- `src/ttypes/` — typed tilemap model definitions
- `src/utils/icons_cache.py`, `editor_preference.py`, `log_capture.py`, `standalone.py`, `validation.py`
- `tests/test_collision_layer_mask.py`, `test_collision_layer_sidebar.py`, `test_editor_pan_mode.py`
- `tests/test_render_scale.py`, `test_tile_grid_selection.py`, `test_tile_selector_pick.py`
- `tests/test_toolbar_tools.py`, `test_layers_autotile.py`, `test_gid_collision.py`
- `tests/test_serialization_regression.py`, `test_sprite_animation_editor_grid.py`
- `tests/test_project_paths.py`, `test_tilemap_save.py`
