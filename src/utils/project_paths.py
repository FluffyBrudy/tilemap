from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional


def _as_base_path(base_path: Path) -> Path:
    return Path(base_path).expanduser().resolve()


def to_project_path(path: str | Path, base_path: Path) -> str:
    """Serialize a filesystem path as a project-relative POSIX path."""
    raw_path = Path(path).expanduser()
    base = _as_base_path(base_path)

    if raw_path.is_absolute():
        abs_path = raw_path.resolve()
    else:
        abs_path = (base / raw_path).resolve()

    try:
        relative = abs_path.relative_to(base)
    except ValueError:
        relative = Path(os.path.relpath(abs_path, base))

    return relative.as_posix()


def resolve_project_path(
    path: str | Path,
    base_path: Path,
    *,
    fallback_roots: Optional[Iterable[Path]] = None,
    must_exist: bool = False,
) -> Path:
    """Resolve a project JSON path against base_path, with legacy fallbacks."""
    raw_path = Path(path).expanduser()

    if raw_path.is_absolute():
        return raw_path.resolve()

    base = _as_base_path(base_path)
    candidates = [(base / raw_path).resolve()]

    for root in fallback_roots or ():
        candidate = (Path(root).expanduser() / raw_path).resolve()
        if candidate not in candidates:
            candidates.append(candidate)

    if must_exist:
        for candidate in candidates:
            if candidate.exists():
                return candidate

    return candidates[0]
