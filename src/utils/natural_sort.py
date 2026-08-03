"""Natural (human-friendly) sorting keys for file/asset names.

`natural_key("frame_2.png") < natural_key("frame_11.png")` — digit runs
compare numerically while plain lexicographic sort would place 11 before 2.
"""

from __future__ import annotations

import re
from typing import Any

_DIGITS = re.compile(r"(\d+)")


def natural_key(name: str) -> tuple[tuple[int, int] | tuple[int, str], ...]:
    """Sort key for a filename: digit runs compare numerically, text case-insensitive.

    Each part is tagged with a type so int/str parts never compare against
    each other (which would raise TypeError in Python 3), e.g. "a1b" vs "aab".
    """
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in _DIGITS.split(name)
    )


def sorted_natural(names: list[Any], *, key=None) -> list[Any]:
    """Sorted copy of `names` using natural order (optionally via `key` extractor)."""
    return sorted(names, key=lambda n: natural_key(key(n) if key else str(n)))
