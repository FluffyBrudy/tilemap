import string
import re
from typing import Sequence
from pygame.typing import IntPoint


def serialize_point(point: IntPoint, sep=";"):
    if not isinstance(point, Sequence):
        raise TypeError("point must be sequence")
    elif len(point) < 2:
        raise ValueError("point must have at least 2 elements")
    return f"{point[0]}{sep}{point[1]}"


def deserialize_point(point_str: str):
    separators = re.escape(string.punctuation)
    matched_str = re.search(rf"(\d+)[{separators}](\d+)$", point_str)

    if matched_str is None:
        raise ValueError(f"Improper point string format: {point_str}")

    x, y = matched_str.groups()
    return int(x), int(y)
