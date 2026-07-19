from collections.abc import Callable
from typing import TYPE_CHECKING

from pygame import QUIT, Event

if TYPE_CHECKING:
    from editor import Editor


class EventMap:
    def __init__(self, editor: "Editor") -> None:
        self.editor = editor

        self.event_map: dict[tuple[int, int | None], Callable[[Event], None]] = {
            (QUIT, None): lambda _: self.quit()
        }

    def get_event(self, event_key: tuple[int, int | None]):
        return self.event_map.get(event_key, None)

    def quit(self):
        self.editor.running = False
