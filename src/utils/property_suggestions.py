from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from editor import Editor


class PropertySuggestionRegistry:
    def __init__(self):
        self._data: dict[str, list[str]] = {}

    def refresh(self, editor: "Editor"):
        values: dict[str, set[str]] = {}

        if editor.tileset_widget:
            for ts in editor.tileset_widget.tilesets:
                for k, v in ts.properties.items():
                    values.setdefault(k, set()).add(str(v))
                for tile_props in ts.tile_properties.values():
                    for k, v in tile_props.items():
                        values.setdefault(k, set()).add(str(v))

        if editor.tilemap:
            for layer in editor.tilemap.layer_manager.layers:
                for k, v in layer.properties.items():
                    values.setdefault(k, set()).add(str(v))
                for tile in layer.tiles.values():
                    if "properties" in tile:
                        for k, v in tile["properties"].items():
                            values.setdefault(k, set()).add(str(v))
                if layer.layer_type == "object":
                    for obj in layer.objects.values():
                        if "properties" in obj:
                            for k, v in obj["properties"].items():
                                values.setdefault(k, set()).add(str(v))

        if editor.node_manager:
            for node in editor.node_manager.nodes.values():
                for k, v in node.properties.items():
                    values.setdefault(k, set()).add(str(v))

        self._data = {k: sorted(v) for k, v in values.items()}

    @property
    def known_keys(self) -> list[str]:
        return sorted(self._data.keys())

    def ghost_text(self, key: str, input_text: str) -> str:
        if key not in self._data:
            return ""
        prefix = input_text.lower()
        matches = [
            v
            for v in self._data[key]
            if v.lower().startswith(prefix) and v != input_text
        ]
        if matches:
            return matches[0][len(input_text):]
        return ""

    def key_ghost(self, input_text: str) -> str:
        if not input_text:
            return ""
        prefix = input_text.lower()
        matches = [
            k for k in self._data
            if k.lower().startswith(prefix) and k != input_text
        ]
        if matches:
            return sorted(matches)[0][len(input_text):]
        return ""
