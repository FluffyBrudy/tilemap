import re
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ttypes.tilemap import TypeObject


def serialize_point(point: Sequence, sep=";"):
    if not isinstance(point, Sequence):
        raise TypeError("point must be sequence")
    if len(point) < 2:
        raise ValueError("point must have at least 2 elements")

    def format_val(v):
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v

    return f"{format_val(point[0])}{sep}{format_val(point[1])}"


def deserialize_point(point_str: str):
    point_str = point_str.strip()
    matched_str = re.fullmatch(r"(-?\d+(?:\.\d+)?)[;, ](-?\d+(?:\.\d+)?)", point_str)

    if matched_str is None:
        raise ValueError(f"Improper point string format: {point_str}")

    x, y = matched_str.groups()

    def parse_val(v):
        f = float(v)
        return int(f) if f.is_integer() else f

    return parse_val(x), parse_val(y)


def copy_object(obj: "TypeObject") -> "TypeObject":
    """Create a deep copy of a TypeObject, copying the area dict as well."""
    from ttypes.tilemap import TypeArea, TypeObject

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

    import copy

    if "properties" in obj:
        obj_copy["properties"] = copy.deepcopy(obj["properties"])
    if "animation" in obj:
        obj_copy["animation"] = copy.deepcopy(obj["animation"])

    return obj_copy


def serialize_object(obj: "TypeObject") -> "TypeObject":
    """Prepare a TypeObject for JSON serialization (copy the object structure)."""
    return copy_object(obj)
