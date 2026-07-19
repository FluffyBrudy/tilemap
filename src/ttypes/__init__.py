from collections.abc import Sequence

from pygame import Vector2

from .tilemap import *

TCoor = tuple[int, int]
TOffset = tuple[int, int] | Sequence[int] | Vector2
