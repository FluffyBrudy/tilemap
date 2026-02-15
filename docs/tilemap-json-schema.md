# Tilemap JSON Schema (summary)

This describes the JSON structure produced by the tilemap save logic and what each field refers to.
Tags:
- **[public]**: safe for external tools to read/emit
- **[internal]**: editor/runtime state (UI or transient)
- **[mixed]**: used by both external tools and the editor

## Root
- `meta`: object **[mixed]** (map settings + view state)
- `resources`: object **[public]** (tilesets used by the map)
- `project_state`: object **[mixed]** (autotile rules/groups)
- `data`: object **[public]** (layers + tiles/objects)

## meta
- `tile_size`: `"w;h"` string **[public]** — tile pixel size
- `map_size`: `"w;h"` string **[public]** — current map bounds in tiles
- `initial_map_size`: `"w;h"` string **[mixed]** — size from map setup
- `zoom_level`: number **[internal]** — editor view zoom
- `scroll`: `"x;y"` string **[internal]** — editor view scroll
- `version`: string (e.g., `"1.1"`) **[public]** — format version

## resources
- `tilesets`: array of tileset objects **[public]**
  - `path`: string **[public]** — path to tileset image
  - `type`: string **[public]** — tileset kind (e.g., `"tile"` or `"object"`)
  - `properties`: object (optional) **[public]** — tileset-level metadata
  - `tile_properties`: object (optional) **[public]** — per-variant metadata, keyed by variant id as string

## project_state
- `rules`: array of rule objects **[mixed]** (flat list; backward compatibility)
  - `name`: string **[mixed]** — display name
  - `neighbors`: array of `[x, y]` pairs **[public]** — neighbor offsets that must exist
  - `tileset_path`: string **[mixed]** — absolute/relative tileset path (fallback if index missing)
  - `tileset_index`: number or null **[mixed]** — index into `resources.tilesets`
  - `variant_ids`: array of numbers **[public]** — tile variant ids used by rule
  - `group_id`: string (optional) **[mixed]** — group name/id
- `groups`: array of group objects (optional) **[mixed]**
  - `name`: string **[mixed]**
  - `rules`: array of rule objects (same as above)

## data
- `layers`: array of layer objects **[public]**
  - `name`: string **[public]** — display name
  - `type`: string (`"tile"` or `"object"`) **[public]**
  - `visible`: boolean **[mixed]** — editor toggle
  - `locked`: boolean **[mixed]** — editor lock
  - `opacity`: number **[mixed]** — layer opacity in editor
  - `z_index`: number **[public]** — draw order
  - `tiles`: object keyed by `"x;y"` strings **[public]**
    - tile:
      - `pos`: `"x;y"` string **[public]** — grid position
      - `ttype`: number (or string in some saves) **[public]** — tileset index (or path fallback)
      - `variant`: number **[public]** — tile variant id within tileset
      - `properties`: object (optional) **[public]** — per-tile metadata
  - `objects`: object keyed by id string (only for `type: "object"`) **[public]**
    - object:
      - `area`: `{x, y, w, h}` (numbers) **[public]** — pixel bounds
      - `ttype`: number **[public]** — tileset index
      - `tileset_type`: string **[public]** — tileset kind for objects
      - `variant`: number **[public]** — variant id
      - `properties`: object (optional) **[public]**
  - `next_object_id`: number (optional) **[internal]** — editor id counter
  - `properties`: object (optional) **[public]** — per-layer metadata

## Usage notes (examples)
- **Tile image reference**: a tile is identified by `ttype` + `variant`.
  - `ttype` points to the tileset by index in `resources.tilesets`.
  - `variant` is the tile’s index inside that tileset image.
- **Object image reference**: an object uses the same `ttype` + `variant` pairing plus `tileset_type` to distinguish object tilesets.
- **Autotile (automap)**: rules in `project_state` are primarily for the editor’s autotile features.
  - You can read rules externally, but prefer applying autotile in the editor rather than in custom runtime code.
