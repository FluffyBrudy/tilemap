# Tilemap Editor Requirements

## Core Design Rules

### R1: Deterministic Project-Based Configuration
- **base_path** = project root (directory containing `settings.json`)
- **data_path** = `base_path / "data"` (always derived, never stored)
- All project-specific paths are relative to base_path
- No assumptions about current working directory

### R2: Single Source of Truth
- `settings.json` is the ONLY configuration file
- Created ONLY via `tilemap_editor init`
- No auto-creation of settings.json by individual modules
- No reading settings.json by internal modules (except Editor)

### R3: Explicit Path Passing
- Paths are opaque strings/values passed through call chain
- Modules receive paths as parameters, not from config
- No module introspects settings.json for paths

### R4: BASE_PATH for Package Assets Only
- `BASE_PATH` (the package root) is for:
  - Package assets (icons, default tiles, etc.)
  - Internal defaults only
- Never used for project-specific data
- Project data goes in user's project directory (base_path)

### R5: Standalone Tools are CLI Tools
- Receive all paths as CLI arguments
- No dependencies on Editor or settings.json
- Use BASE_PATH for default values only

### R6: No Internal Module Reads settings.json
- Only Editor reads settings.json
- Internal modules (plugins, utilities) receive paths via:
  - Constructor/injection from Editor
  - CLI arguments for standalone tools
- ErrorHandler gets log_root from Editor (not from settings)

### R7: Log Directory Structure
- Log root = `base_path / "logs"`
- Error log = `log_root / "errors.log"` (not "logs/errors.log")
- StandaloneErrorConsole receives `--log-file` path directly

### R8: Collision Paths
- Stored in settings.json as `collision_paths` dict for future extensibility
- Editor resolves actual paths at runtime
- Individual collision editors use resolved paths via `_data_root`

### R9: Generated Data Paths
- Generated project JSON stores file references relative to `base_path`
- Runtime/editor code may resolve those references to absolute `Path` objects in memory
- Absolute paths are accepted only for legacy input, not emitted in new generated data

## Implementation Requirements

### settings.json Structure
```json
{
  "base_path": "<absolute_path_to_project_root>",
  "data_path": "data",
  "collision_paths": {
    "tileset": "collision",
    "character": "character_collision"
  },
  "error_handler": {
    "enabled": true,
    "log_path": "errors.log"
  }
}
```

### Editor Responsibilities
1. Load and validate settings.json on startup
2. Resolve data_root = base_path / "data"
3. Pass --data-root to all standalone editors
4. Pass --log-file to StandaloneErrorConsole

### Standalone Tool Arguments
- `--data-root`: Path to data directory (for save/load)
- `--log-file`: Path to error log (for error console only)

### Data Root Usage in Editors
```python
# In editor __init__ or from_path:
self._data_root: Path = None

# When saving/loading:
def _get_data_dir(self) -> Path:
    if self._data_root:
        return self._data_root
    return BASE_PATH / "data"  # Fallback for standalone
```

### ErrorHandler Dependency Injection
- Editor loads settings, extracts error_handler config
- Editor calls `error_handler.configure(log_root=base_path / "logs")`
- StandaloneErrorConsole receives `--log-file` (not --data-root)

## Affected Files

### Core
- `src/editor.py` - Loads settings, passes --data-root to standalones
- `src/utils/error_handler.py` - Uses injected log_root
- `src/standalone_error_console.py` - Accepts --log-file

### Plugins
- `src/plugins/tileset_collision/editor.py` - Uses _data_root for save/load
- `src/plugins/tileset_collision/standalone.py` - Accepts --data-root
- `src/plugins/character_collision/editor.py` - Uses _data_root for save/load
- `src/plugins/character_collision/standalone.py` - Accepts --data-root
- `src/plugins/sprite_animation/editor.py` - Uses _data_root for file manager
- `src/plugins/sprite_animation/standalone.py` - Accepts --data-root

### Settings
- `src/tilemap_editor/settings.py` - init_settings generates settings.json
- `src/utils/editor_preference.py` - load_settings for Editor use

## Testing Checklist
- [ ] `tilemap_editor init` creates settings.json with correct paths
- [ ] Editor loads settings and passes --data-root to standalones
- [ ] Standalone editors save/load to data_root/collision_type/
- [ ] Error console writes to base_path/logs/errors.log
- [ ] No module imports settings.json directly except Editor
- [ ] Standalone tools work without settings.json (use BASE_PATH defaults)
