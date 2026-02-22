# Standalone Animation Editor

Independent tool for creating sprite animations. Can be launched from tilemap editor or run standalone.

## Usage

### From Tilemap Editor
Tools > Animation Editor

### Standalone
```bash
python3 src/standalone_animation_editor.py [animation_file.json]
```

## Controls

- `SPACE` - Play/Pause animation preview
- `Ctrl+O` - Open animation file
- `Ctrl+S` - Save animation file
- `Ctrl+I` - Import image/spritesheet
- `ESC` - Exit

## Features

- Import single images or spritesheets
- Frame-based animation with custom timing
- Preview with play/pause
- Save/load animation definitions as JSON
- Independent of tilemap (can be used for any project)

## Animation File Format

```json
{
  "name": "my_animation",
  "loop": true,
  "default_duration": 200,
  "frames": [
    {
      "image": "frame_0.png",
      "duration_ms": 200,
      "crop": {"x": 0, "y": 0, "w": 32, "h": 32}
    }
  ]
}
```

## TODO

- Integrate file manager for image import
- Spritesheet auto-splitting
- Frame timeline editor
- Onion skinning
- Export options
