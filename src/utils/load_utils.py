import string
from typing import Sequence
from pygame.typing import IntPoint

import re


def serialize_point(point: IntPoint, sep=","):
    if not isinstance(point, Sequence):
        raise TypeError("point must be sequence")
    elif len(point) < 2:
        raise ValueError("point must have at least 2 elements")

    if sep not in string.punctuation:
        raise ValueError(f"seprators must be one of {string.punctuation}")

    return str(point[0]) + str(sep) + str(point[1])


def deserialize_point(point_str: str):
    """require <int><separator><int> format string"""
    separators = re.escape(string.punctuation)
    matched_str = re.match(rf"(\d)[{separators}](\d)$", point_str)
    if matched_str is None:
        raise ValueError("improper point string format")
    x, y = matched_str.groups()
    return int(x), int(y)
