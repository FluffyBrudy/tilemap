# Changelog

<!-- towncrier release notes start -->
# tilemap_editor 4.3.8 (2026-08-04)

## Features

- Sprite editor: two-row grouped toolbar, natural filename sorting on multi-sheet loads, and a Stack V/H toggle for vertical or horizontal sheet stacking. 
- Rewrote the sprite editor around a command stack with single-canvas undo memory: shared clipboard with relative-tile pasting that survives scale/grid changes, drag-move and rubber-band selection that can expand the canvas, object-selection undo restore, and a pure camera with cursor-anchored zoom. (sprite-editor-v2)

## Bug Fixes

- Fixed sprite editor undo history corruption from shared region references, viewport cache staleness after region edits, coordinate errors after loading new sheets, index lookup failures with negative-origin canvases, and canvas expansion failures for negative cell coordinates
- Fixed sprite editor paste landing in wrong cells after a scale or grid-size change (clipboard now stores relative tile offsets), paste/cut double-clipboard split-brain, paste preview lacking pixel ghost, and moves/pastes past the canvas edge now expanding the canvas. (sprite-editor-paste-fixes)
- Fixed sprite editor theming and camera gestures: the canvas, header bar, grid lines, and overlays now use theme colors/fonts instead of hardcoded dark values (canvas no longer stays black on light themes), the canvas header no longer covers the sheet's top rows, and mouse wheel zoom/pan work again with the same 30px/1.12x behavior as the old editor. (sprite-editor-theme-wheel)


## [4.3.7] - 2026-07-30

### Bug Fixes

- Replaced buggy auto-resize system with explicit offset + size model for widget positioning

## [4.3.6] - 2026-07-26

### Features

- Added tileset properties completion
- Updated README with credits and Python version info

### Bug Fixes

- Fixed UX bugs and node prescale problem

## [4.3.4] - 2026-07-24

### Features

- Added y-sort option for tile rendering order

### Changed

- Restructured codebase with enhanced UI components and preference persistence
- Improved shape editor UX with theme integration and viewport centering

## [4.3.1] - 2026-07-17

### Bug Fixes

- Fixed create folder blocker in file manager
- Adjusted input field inner size

## [4.3.0] - 2026-07-16

### Changed

- Refactored toolbar and tool system with ToolManager/ToolKind central state
- Replaced editor boolean flags with centralized ToolManager mutual exclusion
- CLI `--theme` support

### Added

- Icon-only compact toolbar (28px) with separator bars and tooltips

### Bug Fixes

- Fixed node and object render_scale bugs (selection rect, move offset, hit-test)

## [4.2.0] - 2026-07-15

### Features

- Separated autotile group from layer tile data
- Added global ID system for tiles
- Re-added autotile early-out optimization
- Added auto-detect group from variant

## [4.1.0] - 2026-07-13

### Features

- Added .tmx file open/save support with TMX-to-dict converter

### Bug Fixes

- Fixed alignment of tmx converter with parser fixes (mask, props, gid count)

### Misc

- Formatted code and applied unsafe fixes with ruff

## [4.0.0] - 2026-07-11

### Changed

- Refactored widget theme system with dynamic COLORS proxy, SHAPE, FONTS, SPACING
- Applied theme from settings.json with custom theme loading support
- Added theme-aware WidgetBase with box model (padding, border, content_rect)

### Added

- CLI `--theme` argument accepting name or path to .json file

### Bug Fixes

- Fixed tile grid issues and serialization
- Improved node ui/ux with ctrl/cmd+shift+n toggle for node manager
- Improved particle rendering
- Temporarily disabled autotile propagation on collision paint

## [3.3.8] - 2026-07-01

### Bug Fixes

- Replaced smoothscale with scale for broader compatibility
- Fixed fallback to scale when smoothscale fails on non-32bit surfaces
- Replaced unicode characters with SVG icons for frame nav and onion skin

## [3.3.4] - 2026-06-17

### Features

- Enhanced sprite editor with cut/copy/paste functionality
- Added checkbox widget for UI controls

### Documentation

- Added documentation for tilemap-editor (setup, project structure, architecture, usage)

## [3.3.3] - 2026-06-10

### Features

- Added particle system with 66 presets across 11 categories
- Added particle system editor integration with config dialog
- Added particle preview in TileGrid

### Bug Fixes

- Fixed propagation of negative grid offsets
- Fixed zero animation frame_stride guard
- Fixed preset dropdown refresh on node switch
- Fixed particle preview reset on config save

### Misc

- Added 'synchronize' type to PR agent workflow triggers

## [3.2.10] - 2026-06-07

### Bug Fixes

- Fixed tab click offset ignoring scroll_x

### Added

- Hover-only arrow buttons for tab navigation

## [3.2.9] - 2026-06-07

### Bug Fixes

- Fixed stride normalization — removed % stride normalization, auto-compute stride
- Fixed dialog UI overlap

## [3.2.8] - 2026-06-07

### Features

- Added node system with NodeManager, NodeSelector, NodeEditor, and TileGrid overlay
- Added lenient tileset loading with warn dialog instead of reject on size mismatch

### Bug Fixes

- Fixed layer rename text not visible during editing
- Fixed object layer position offset from render_scale
- Fixed capsule move icon and animation preview grid_offset
- Fixed layer rename Cmd+Backspace interaction

## [3.2.4] - 2026-06-04

### Features

- Added copy/paste collision shapes with toast feedback and painted tiles focus mode
- Added sprite editor integration with flip ghosting fix, tileset zoom, autotiler import fix
- Added auto-expand spritesheet canvas on paste overflow
- Added editable name field in character collision editor
- Added renaming support in character collision
- Added animation library loading and tool state management
- Added auto-propagation of collision shapes to auto-tile variant groups on save

### Bug Fixes

- Fixed animation rename shortcuts, path resolution, file input overflow, and dual-focus metadata fields
- Fixed sprite editor multi-row paste flattening and missing tile-size arg
- Fixed dynamic grid span
- Fixed L shortcut conflict with name input

### Misc

- Added unit tests

## [3.1.6] - 2026-05-21

### Bug Fixes

- Fixed NameError in save_map
- Fixed asymmetry in load path resolution
- Fixed path resolution in init

### Added

- Added render_scale to map properties with dialog UI and TileGrid support
- Added auto-creation of data directory on init

## [3.1.0] - 2026-05-18

### Features

- Added Godot-inspired physics layer (radio) + mask (checkbox) bit selector (16 layers)
- Added collision layer sidebar overlay with toggle/close/dim
- Added object tileset collision editor with region support
- Added reusable text input system with cursor, selection, and shortcuts
- Added project initialization, asset management, and data structure improvements
- Added theme support
- Added collision mask support
- Implemented event priority system and modal overlays in autotiler

### Changed

- Improved file manager path handling and directory initialization
- Improved tileset collision help panel and macOS HiDPI support
