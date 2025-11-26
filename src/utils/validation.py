from pathlib import Path
from typing import Any

from pygame.typing import IntPoint


def is_png_image(path: Path | str | Any):
    if not isinstance(path, (str, Path)):
        raise ValueError("path must be string or pathlib.Path instance")
    image_path: "Path" = path  # type: ignore
    if isinstance(path, str):
        image_path = Path(path)
    if not image_path.exists():
        raise FileNotFoundError("given image not found")
    return image_path.suffix.lower() == ".png"


def is_image_multipleof(size: "IntPoint", check_size: "IntPoint"):
    ow, oh, cw, ch = (*size, *check_size)
    return ow >= cw and oh >= ch and (ow % cw == 0) and (oh % ch == 0)
