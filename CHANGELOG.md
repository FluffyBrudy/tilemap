# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 2025-04-23

### Added
- **Tileset Collision Plugin**: Godot-like polygon collision editor
  - `CollisionPainter`: Interactive polygon drawing with edge-constrain mode
  - `TilesetCollisionEditor`: Full editor with tile selector and painted tiles list
  - `TilesetCollisionLibrary`: Persistent collision data management
  - Edge-draw mode (`E` key + `Shift`) for precise slope/stair creation
  - Help panel (`H` key) with all controls documented
  - One-way collision support for platforms
  - Zoom, pan, and grid controls
- **Character Collision Plugin**: Shape-based character collision editor
  - Rectangle, Circle, and Capsule shape support
  - Protocol-based design for easy integration

### Changed
- Updated pyproject.toml version to 2.0.1
- Improved editor.py and tile_selector.py integration

## [2.0.0] - 2025-04-22

### Major Changes
- **NEW**: SVG icon system with 26+ professional icons
- **NEW**: Dynamic icon loading - icons auto-load by button name
- **NEW**: Geometric icon fallbacks for all UI elements
- **NEW**: Centralized font manager with bold weights for clarity
- **NEW**: Professional UI with consistent styling

### Features
- **Icon Manager**: Native pygame-ce SVG support with caching
- **Animation Editor**: SVG icons for Dup, Marker, JSON, and playback controls
- **Main Toolbar**: SVG icons for pan, zoom, reset, fit, grid
- **Console**: Severity icons (error, warning, info) with visual indicators
- **File Manager**: SVG folder, file, and image icons
- **Font System**: Auto-selects JetBrains Mono, Fira Code, or Consolas
- **Fallback System**: Geometric drawing primitives when SVG fails

### Assets
- Added 26 SVG icons from Godot icon set
- Included fonts directory in distribution
- Updated MANIFEST.in to include all assets

### Build
- Enabled include-package-data in pyproject.toml
- No external dependencies (uses native pygame-ce SVG)
- Clean distribution without cairosvg or other heavy deps

### Technical
- Replaced all Unicode characters with SVG icons
- Improved font clarity with bold weights
- Added comprehensive icon caching
- Maintained backward compatibility

## [1.1.3] - 2024-XX-XX

### Bug Fixes
- Fixed animation editor rename functionality
- Corrected file manager ESC key behavior
- Improved error console rendering

## [1.1.2] - 2024-XX-XX

### Features
- Added spritesheet support
- Improved file handling

## [1.1.1] - 2024-XX-XX

### Bug Fixes
- Patch release for stability improvements

## [1.1.0] - 2024-XX-XX

### Features
- Initial release with basic tilemap editing
- Sprite animation editor
- JSON save/load support
