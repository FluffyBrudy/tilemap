import string
import re
from typing import Sequence, TYPE_CHECKING
from pygame.typing import IntPoint

if TYPE_CHECKING:
    from ttypes.tilemap import TypeObject, TypeArea


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


def copy_object(obj: "TypeObject") -> "TypeObject":
    """Create a deep copy of a TypeObject, copying the area dict as well."""
    from ttypes.tilemap import TypeObject, TypeArea

    area_copy: TypeArea = {
        "x": obj["area"]["x"],
        "y": obj["area"]["y"],
        "w": obj["area"]["w"],
        "h": obj["area"]["h"],
    }

    obj_copy: TypeObject = {
        "area": area_copy,
        "ttype": obj["ttype"],
        "tileset_type": obj["tileset_type"],
        "variant": obj["variant"],
    }

    return obj_copy


def serialize_object(obj: "TypeObject") -> "TypeObject":
    """Prepare a TypeObject for JSON serialization (copy the object structure)."""
    return copy_object(obj)
