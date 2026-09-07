"""Alias (pattern brush) library — sidecar model, no UI.

One ``*.alias.json`` file per tileset under ``data/aliases/``::

    {"version": 1, "tileset": "tiles/stone.png", "aliases": [
        {"name": "WallEnd", "w": 3, "h": 2,
         "cells": [[dx, dy, variant], ...]}]}

Aliases are tile-only: a (tileset identity, local pattern) pair. No
objects, no layer references. Malformed entries are skipped on load so
one bad leaf cannot break the palette; valid data round-trips exactly.
Saves are atomic (tmp + replace).
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ALIAS_VERSION = 1
ALIAS_SUFFIX = ".alias.json"


@dataclass
class AliasPattern:
    """A named multi-cell tile pattern within one tileset."""

    name: str
    w: int
    h: int
    cells: list[tuple[int, int, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "w": self.w,
            "h": self.h,
            "cells": [[dx, dy, v] for dx, dy, v in self.cells],
        }

    @staticmethod
    def from_dict(data: Any) -> AliasPattern | None:
        """Parse one alias; return None when malformed."""
        if not isinstance(data, dict):
            return None
        name = data.get("name")
        w, h = data.get("w"), data.get("h")
        if (not isinstance(name, str) or not name
                or not isinstance(w, int) or not isinstance(h, int)
                or w <= 0 or h <= 0):
            return None
        raw_cells = data.get("cells")
        if not isinstance(raw_cells, list):
            return None
        cells: list[tuple[int, int, int]] = []
        seen: set[tuple[int, int]] = set()
        for entry in raw_cells:
            if (not isinstance(entry, (list, tuple)) or len(entry) != 3):
                continue
            dx, dy, variant = entry
            if (not isinstance(dx, int) or not isinstance(dy, int)
                    or not isinstance(variant, int)):
                continue
            if not (0 <= dx < w and 0 <= dy < h and variant >= 0):
                continue
            if (dx, dy) in seen:
                continue
            seen.add((dx, dy))
            cells.append((dx, dy, variant))
        if not cells:
            return None
        return AliasPattern(name=name, w=w, h=h, cells=cells)


@dataclass
class AliasFile:
    """All aliases authored against a single tileset."""

    tileset: str = ""
    aliases: list[AliasPattern] = field(default_factory=list)

    def by_name(self, name: str) -> AliasPattern | None:
        for alias in self.aliases:
            if alias.name == name:
                return alias
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": ALIAS_VERSION,
            "tileset": self.tileset,
            "aliases": [a.to_dict() for a in self.aliases],
        }

    @staticmethod
    def from_dict(data: Any) -> AliasFile:
        if not isinstance(data, dict):
            return AliasFile()
        tileset = data.get("tileset", "")
        raw = data.get("aliases", [])
        aliases: list[AliasPattern] = []
        seen: set[str] = set()
        if isinstance(raw, list):
            for entry in raw:
                alias = AliasPattern.from_dict(entry)
                if alias is None or alias.name in seen:
                    continue
                seen.add(alias.name)
                aliases.append(alias)
        return AliasFile(
            tileset=tileset if isinstance(tileset, str) else "",
            aliases=aliases,
        )

    @staticmethod
    def load(path: str | Path) -> AliasFile:
        try:
            with open(path) as f:
                return AliasFile.from_dict(json.load(f))
        except (OSError, ValueError):
            return AliasFile()

    def save(self, path: str | Path) -> None:
        """Atomic write (tmp + replace) so a crash never half-writes."""
        path = Path(path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def alias_path_for(aliases_dir: str | Path, stem: str) -> Path:
    return Path(aliases_dir) / f"{stem}{ALIAS_SUFFIX}"


class AliasScope:
    """Aggregates one scope (several alias files) with mtime tracking.

    The editor palette polls :meth:`changed` to reload files the
    standalone composer saved — no IPC needed.
    """

    def __init__(self, aliases_dir: str | Path, stems: list[str]):
        self.aliases_dir = Path(aliases_dir)
        self.stems = list(stems)
        self.files: dict[str, AliasFile] = {}
        self._mtimes: dict[str, float] = {}
        self.refresh(force=True)

    def refresh(self, force: bool = False) -> bool:
        """(Re)load files whose mtime moved. Returns True if anything changed."""
        changed = False
        for stem in self.stems:
            path = alias_path_for(self.aliases_dir, stem)
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = -1.0
            if force or mtime != self._mtimes.get(stem):
                self._mtimes[stem] = mtime
                self.files[stem] = AliasFile.load(path)
                changed = True
        return changed

    def changed(self) -> bool:
        """True if any scoped file appeared, vanished, or was rewritten."""
        for stem in self.stems:
            path = alias_path_for(self.aliases_dir, stem)
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = -1.0
            if mtime != self._mtimes.get(stem):
                return True
        return False

    def all_aliases(self) -> list[tuple[str, str, AliasPattern]]:
        """(stem, tileset, pattern) triples across the scope, in scope order."""
        out = []
        for stem in self.stems:
            af = self.files.get(stem)
            if af is None:
                continue
            for alias in af.aliases:
                out.append((stem, af.tileset, alias))
        return out
