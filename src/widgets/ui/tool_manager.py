from enum import Enum
from typing import Optional


class ToolKind(Enum):
    PAINT = "paint"
    SELECT = "select"
    ERASER = "eraser"
    PAN = "pan"


class ToolManager:
    """Central tool state. Single source of truth for active tool.

    Manages mutually exclusive tools (pan, select, eraser) with
    automatic previous-tool save/restore.
    """

    def __init__(self):
        self._active: Optional[ToolKind] = None
        self._prev: Optional[ToolKind] = None

    @property
    def active(self) -> Optional[ToolKind]:
        return self._active

    def activate(self, tool: ToolKind) -> None:
        self._prev = self._active
        self._active = tool

    def deactivate(self) -> None:
        self._prev = self._active
        self._active = None

    def toggle(self, tool: ToolKind) -> None:
        if self._active == tool:
            self._active = self._prev
            self._prev = None
        else:
            self._prev = self._active
            self._active = tool

    def is_active(self, tool: ToolKind) -> bool:
        return self._active == tool

    def restore_previous(self) -> Optional[ToolKind]:
        prev = self._prev
        self._active = prev
        self._prev = None
        return prev
