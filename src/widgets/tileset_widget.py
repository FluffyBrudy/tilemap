from typing import TYPE_CHECKING
from pathlib import Path
from filemanager import openfilemanager
import pygame
from pygame_gui import UI_BUTTON_PRESSED
from pygame_gui.core import ObjectID
from pygame_gui.core.gui_type_hints import RectLike
from pygame_gui.elements import (
    UIButton,
    UIImage,
    UIPanel,
    UIScrollingContainer,
    UITabContainer,
    UIWindow,
)

from widgets.shared_widgets import alert

if TYPE_CHECKING:
    from editor import Editor


class TilesetContainer(UIWindow):
    _editor_instance: "Editor" = None  # type: ignore

    def __init__(
        self,
        editor: "Editor",
        rect: RectLike,
        window_display_title: str = "tileset",
        visible: int = 1,
    ):
        if not TilesetContainer._editor_instance:
            TilesetContainer._editor_instance = editor
        editor = TilesetContainer._editor_instance
        super().__init__(
            manager=editor.manager,
            rect=rect,
            resizable=True,
            draggable=True,
            visible=visible,
            window_display_title=window_display_title,
        )

        container = self.get_container()
        container_width, container_height = container.get_size()

        tileset_tab_container = int(container_height * 0.5)
        toolbar_height = int(container_height * 0.03)

        self.tileset_tabs_container = UITabContainer(
            manager=editor.manager,
            relative_rect=(0, 0, container_width, tileset_tab_container),
            anchors={"left": "left", "right": "right", "top": "top", "bottom": "top"},
            visible=visible,
            container=self.get_container(),
        )

        self.bottom_toolbar = UIPanel(
            manager=editor.manager,
            relative_rect=(0, -toolbar_height, container_width, toolbar_height),
            container=self.get_container(),
            object_id=ObjectID(object_id="#tileset_btm_toolbar"),
            anchors={
                "left": "left",
                "right": "right",
                "top": "bottom",
                "bottom": "bottom",
            },
        )
        button_width = 60
        self.add_button = UIButton(
            relative_rect=(-button_width, 0, button_width, int(toolbar_height * 0.9)),
            text="+",
            container=self.bottom_toolbar,
            anchors={"right": "right", "top": "top"},
            tool_tip_text="add tileset",
        )
        self.remove_button = UIButton(
            relative_rect=(-button_width, 0, button_width, int(toolbar_height * 0.9)),
            text="-",
            container=self.bottom_toolbar,
            anchors={"right": "right", "top": "top", "right_target": self.add_button},
            tool_tip_text="remove tileset",
        )

    def add_tileset(self, path: Path | str):
        if not isinstance(path, Path):
            path = Path(path)
        if not path.exists():
            alert("tileset doesnt exists")
            return
        filename = path.stem + path.suffix

        surface = pygame.image.load(path).convert_alpha()
        container = self.tileset_tabs_container
        tab_id = container.add_tab(filename, f"tab_{filename}")
        tab_container = container.get_tab_container(tab_id)
        UIImage(
            relative_rect=(0, 0, *surface.size),
            image_surface=surface,
            manager=TilesetContainer._editor_instance.manager,
            container=tab_container,
            object_id=ObjectID(object_id="#tileset_image"),
        )

    def process_event(self, event: pygame.event.Event) -> bool:
        consumed = super().process_event(event)

        if event.type == UI_BUTTON_PRESSED:
            if event.ui_element == self.add_button:
                filepath = openfilemanager()
                self.add_tileset(filepath)
                consumed = True
            elif event.ui_element == self.remove_button:
                consumed = True

        return consumed
