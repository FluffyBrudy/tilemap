# tilemap-editor

`tilemap-editor` is a pygame-based map editor focused on fast iteration for 2D games.

## Installation

[tilemap-editor on PyPI](https://pypi.org/project/tilemap-editor/)
[tilemap-parser on deepwiki](https://deepwiki.com/FluffyBrudy/tilemap)

## Parser

`tilemap-parser` is a utility to parse and display maps created by this editor. You can use it to load and visualize tilemaps in your game or application.

[tilemap-parser on deepwiki](https://deepwiki.com/FluffyBrudy/tilemap-parser)
[tilemap-parser on PyPI](https://pypi.org/project/tilemap-parser/)

## Kit

`pygkit` is general-purpose Pygame CE runtime kit: UI widgets, audio management, timers, interpolation, signals and utilities.

### Quick Start

If used for the first time do run the following commands. Afterward you can simply run wherever you want.

It is required because it initialize project settings on `settings.json`

```bash
tilemap-editor init
```

```bash
tilemap-editor run
```

```python
from editor import Editor

if __name__ == "__main__":
    editor = Editor()
    editor.run()
```
