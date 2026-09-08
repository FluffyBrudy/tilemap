"""Alias (pattern brush) library — sidecar model, no UI.

One ``*.alias.json`` file per tileset under ``data/aliases/``::

    {"version": 1, "tileset": "tiles/stone.png", "aliases": [
        {"name": "WallEnd", "w": 3, "h": 2,
         "cells": [[dx, dy, variant], ...]}]}

Aliases are tile-only: a (tileset identity, local pattern) pair. No
objects, no layer references. Malformed entries are skipped on load so
one bad leaf cannot break the palette; valid data round-trips exactly.
Saves are atomic.
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
        """Atomic write so a crash never half-writes."""
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


def alias_key_for(tileset_ref: str) -> str:
    """Collision-free sidecar key for a tileset ref.

    Bare filenames map to their stem (identical to the legacy layout,
    so existing single-level sidecars keep working). Project-relative
    refs with directories are namespaced by joining the suffix-less
    parts with ``__``, so ``a/stone.png`` and ``b/stone.png`` get
    separate files. Refs escaping the project root (``..``) fall back
    to the legacy stem: they cannot be namespaced meaningfully.
    """
    ref = (tileset_ref or "").replace("\\", "/").strip()
    if not ref:
        return ""
    base = ref.rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    if "/" not in ref:
        return stem
    no_suffix = ref[: -len("." + ref.rsplit(".", 1)[1])] if "." in ref.rsplit("/", 1)[-1] else ref
    parts = [p for p in no_suffix.split("/") if p not in ("", ".")]
    if not parts or ".." in parts:
        return stem
    return "__".join(parts)


def resolve_alias_path(aliases_dir: str | Path, tileset_ref: str) -> Path:
    """Save path for a tileset ref (namespaced; bare names = legacy stem)."""
    return alias_path_for(aliases_dir, alias_key_for(tileset_ref))


def load_alias_path(aliases_dir: str | Path, tileset_ref: str) -> Path | None:
    """Existing sidecar for a ref: namespaced first, then legacy stem."""
    key = alias_key_for(tileset_ref)
    namespaced = alias_path_for(aliases_dir, key)
    if namespaced.exists():
        return namespaced
    legacy_stem = Path(tileset_ref.replace("\\", "/")).stem
    if legacy_stem and legacy_stem != key:
        legacy = alias_path_for(aliases_dir, legacy_stem)
        if legacy.exists():
            return legacy
    return namespaced if namespaced.exists() else None


def resolve_tileset(matches: list, ref: str, base: str | Path | None = None) -> int | None:
    """Index into tileset-likes (each with a ``path`` attr) for an alias ref.

    Full normalized-path equality wins; basename/stem fallbacks only
    resolve when they identify exactly one loaded tileset, so
    ``a/stone.png`` vs ``b/stone.png`` never silently picks wrong.
    When ``base`` is given, each candidate path and the ref are first
    compared as project-relative refs against that root, so an
    absolute ``TilesetData.path`` still exact-matches a stored
    project-relative ref.
    """
    import os

    ref = ref or ""
    norm_ref = os.path.normpath(ref)
    base_ref = os.path.basename(norm_ref)
    stem_ref = os.path.splitext(base_ref)[0]
    if base is not None:
        try:
            from utils.project_paths import to_project_path

            norm_ref_proj = os.path.normpath(to_project_path(ref, Path(base)))
        except Exception:
            norm_ref_proj = norm_ref
    else:
        norm_ref_proj = None
    base_hits: list[int] = []
    stem_hits: list[int] = []
    for idx, ts in enumerate(matches):
        p = os.path.normpath(str(getattr(ts, "path", "") or ""))
        if not p or p == ".":
            continue
        if p == norm_ref:
            return idx
        if norm_ref_proj is not None:
            try:
                from utils.project_paths import to_project_path

                cand_proj = os.path.normpath(
                    to_project_path(getattr(ts, "path", "") or "", Path(base)))
            except Exception:
                cand_proj = None
            if cand_proj is not None and cand_proj == norm_ref_proj:
                return idx
        base_name = os.path.basename(p)
        if base_ref and base_name == base_ref:
            base_hits.append(idx)
        elif stem_ref and os.path.splitext(base_name)[0] == stem_ref:
            stem_hits.append(idx)
    if len(base_hits) == 1:
        return base_hits[0]
    if len(stem_hits) == 1:
        return stem_hits[0]
    return None


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
