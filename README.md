# tilemap-editor

`tilemap-editor` is a pygame-based map editor focused on fast iteration for 2D games.

## What it includes

- multi-layer tile/object map editing
- tileset and per-tile properties
- sprite animation editor (`tilemap-anim-editor`)
- JSON save/load compatible with this editor

## Install (local/dev)

```bash
pip install -e .
```

## Run editor

```bash
tilemap-editor
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
