# tilemap-editor

`tilemap-editor` is a pygame-based map editor focused on fast iteration for 2D games.

# tilemap-editor

`tilemap-editor` is a Pygame-based map editor focused on fast iteration for 2D games.

> **Credits:** The initial version of this project was based on DaFluffyPotato's platformer tutorial which is about 6-hours. If you want to understand the foundation this project started from, I highly recommend watching his video: https://www.youtube.com/watch?v=2gABYM5M0ww. While the editor has since evolved with many additional features and improvements, the original map format has been preserved for compatibility.

Several features and design ideas were also inspired by the Godot Engine, including the animation workflow, polygon collision editing, and character collision (Sprite2D-style) editing.


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

> [!WARNING]
> The current release requires **Python 3.11+**. The documentation incorrectly lists Python 3.10 support due to an accidental dependency on `typing.NotRequired`. This will be fixed in a future update.
