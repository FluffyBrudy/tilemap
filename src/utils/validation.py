from pathlib import Path
from typing import Any


def is_png_image(path: Path | str | Any, raise_error=False):
    if not isinstance(path, (str, Path)) and raise_error:
        raise ValueError("path must be string or pathlib.Path instance")
    image_path: "Path" = path  # type: ignore
    if isinstance(path, str):
        image_path = Path(path)
    if not image_path.exists():
        raise FileNotFoundError("given image not found")
    return image_path.suffix.lower() == ".png"
