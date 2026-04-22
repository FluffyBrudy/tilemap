# tilemap-editor

> [!WARNING]
> This is mostly vibe coded as working with ui isnt so easy in pygame. Somehow it works for me. Though it took decent time as this was initially too buggy(which still is as expected). Just an experiment and keep customizing for my need.
PRs are welcome.

`tilemap-editor` is a pygame-based map editor focused on fast iteration for 2D games.
`tilemap-parser` to parse this editor. (https://pypi.org/project/tilemap-parser/)[https://pypi.org/project/tilemap-parser/]

## What it includes

- **Multi-layer tile/object map editing** with visual layer management
- **Decent enough UI** with SVG icons, consistent fonts, and modern design
- **Sprite animation editor** (`tilemap-anim-editor`) with frame-by-frame editing
- **Built-in tools**: File manager, error console, image viewer, automapper
- **Font management** with auto-selected coding fonts for clarity
- **Icon system** with 26+ SVG icons and geometric fallbacks
- **JSON save/load** compatible with this editor
- **Decent console** toggled with ctrl + ` for error/warning/logs/debugging

## Key Features

### UI Improvements
- SVG icons throughout the interface
- Bold, auto-selected coding fonts (JetBrains Mono, Fira Code, Consolas)

### Animation Editor
- Frame picker with visual thumbnails
- Playback controls (play, pause, stop, loop)
- FPS control and onion skinning
- Timeline with marker support
- Export to JSON format

### Map Editor
- Pan, zoom, reset, and fit-to-view controls
- Grid toggle with visual feedback
- Layer management with visibility controls
- Tileset browser with preview
- Autotile support for rapid level design

## Install (local/dev)

### Using Virtual Environment (Recommended)

For Linux and macOS:

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install in development mode
pip install -e .

# Deactivate when done
deactivate
```

For Windows:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate

# Install in development mode
pip install -e .

# Deactivate when done
deactivate
```

### Direct Install (Not Recommended)

```bash
pip install -e .
```

## Package installtion from pypi

```bash
pip install tilemap-editor
```
```bash
pip install tilemap-parser
```

## Run editor

```bash
# Main tilemap editor
tilemap-editor

# Standalone animation editor
tilemap-anim-editor path/to/spritesheet.png --tile-size 32x32
```

## In-game debug usage

```python
from editor import Editor

if __name__ == "__main__":
    dbg = Editor()
    dbg.run()
```

## Runtime split

This package is editor-first. Runtime parser/loading modules can be moved into a separate package later.

## Icons & Assets

The editor includes 26+ SVG icons from the Godot icon set:
- File operations: folder, file, image, save, load, duplicate
- Playback: play, pause, stop, loop
- UI controls: close, plus, warning, info, check, error
- Map tools: pan, zoom in/out, reset, fit, grid
- All icons have geometric fallbacks if SVG loading fails
