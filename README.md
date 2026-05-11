# tilemap-editor

`tilemap-editor` is a pygame-based map editor focused on fast iteration for 2D games.

## Installation

[tilemap-editor on PyPI](https://pypi.org/project/tilemap-editor/)

## Parser

`tilemap-parser` is a utility to parse and display maps created by this editor. You can use it to load and visualize tilemaps in your game or application.

[tilemap-parser on Vercel](https://tilemap-parser.vercel.app/)

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

