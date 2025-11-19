from typing import TYPE_CHECKING, Optional, cast, override
from pygame import Event, Rect
from pygame_gui import UI_FORM_SUBMITTED
from pygame_gui.elements import UIForm, UILabel, UIPanel

from widgets.shared_widgets import alert


if TYPE_CHECKING:
    from editor import Editor
    from pygame_gui.core.gui_type_hints import RectLike


class MapSetup(UIPanel):
    _editor_instance: "Editor" = None  # type: ignore

    def __init__(
        self,
        editor: "Editor",
        relative_rect: "RectLike",
        starting_height: int = 1,
        visible: int = 1,
    ):
        super().__init__(
            relative_rect=relative_rect,
            manager=editor.manager,
            starting_height=starting_height,
            visible=visible,
            anchors={"center": "center"},
        )
        questionnaire = {
            "Map Size": {"width": "integer", "height": "integer"},
            "Tile Size": {"width": "integer", "height": "integer"},
        }
        self.widgets = {
            "label": UILabel(
                manager=editor.manager,
                container=self,
                relative_rect=(0, 0, self.relative_rect.width, 50),
                text="Choose tile size and map size",
                anchors={"centerx": "centerx", "top": "top"},
            ),
            "form": UIForm(
                relative_rect=Rect(
                    0,
                    0,
                    int(self.relative_rect.width * 0.8),
                    int(self.relative_rect.height * 0.8),
                ),
                questionnaire=questionnaire,
                manager=editor.manager,
                container=self,
                anchors={"center": "center"},
            ),
        }

        if cast(Optional["Editor"], MapSetup._editor_instance) is None:
            MapSetup._editor_instance = editor

    def update(self, time_delta: float):
        return super().update(time_delta)

    @override
    def process_event(self, event: Event):
        if event.type == UI_FORM_SUBMITTED and event.ui_element == self.widgets["form"]:
            editor = MapSetup._editor_instance
            map_size = tuple(event.form_values["Map Size"].values())
            tile_size = tuple(event.form_values["Tile Size"].values())
            editor.tilemap.init_size(tile_size, map_size)

            map_value_error = map_size[0] < 1 or map_size[1] < 1
            tile_value_error = tile_size[0] < 1 or tile_size[1] < 1
            if map_value_error:
                alert("map width and height must be non zero and positive")
            elif tile_value_error:
                alert("map width and height must be non zero and positive")
            return True
        return False
