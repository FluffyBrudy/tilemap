from typing import Sequence
from pygame import Vector2
from pygame_gui.core.interfaces import IUIElementInterface
from .tilemap import *
from .theme import *

TCoor = Tuple[int, int]
TOffset = Tuple[int, int] | Sequence[int] | Vector2
UIAnchor = Dict[str, str | IUIElementInterface]
