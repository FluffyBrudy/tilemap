"""
Synchronous pygame loader for parsed tilemaps.

Builds a runtime view with optional surfaces per tileset and a stable
``get_image(tileset_index, variant)`` API suitable for drawing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pygame
from pygame import Rect, Surface

from runtime.tilemap_parse import MapParseError, ParsedTilemap, parse_tilemap_file

PathLike = Union[str, Path]


class TilemapRuntime:
    """Holds parsed map data plus loaded tileset images."""

    def __init__(
        self,
        parsed: ParsedTilemap,
        surfaces: List[Optional[Surface]],
        resolved_paths: List[Path],
        warnings: List[str],
        *,
        map_path: Optional[Path] = None,
    ) -> None:
        self.parsed = parsed
        self.surfaces = surfaces
        self.resolved_paths = resolved_paths
        self.warnings = warnings
        self.map_path = map_path
        self._tw, self._th = parsed.meta.tile_size
        self._build_path_index()
        self._normalize_tile_ttiles()

    @classmethod
    def load(
        cls,
        path: PathLike,
        *,
        extra_search_base: Optional[Path] = None,
        skip_missing_images: bool = True,
    ) -> TilemapRuntime:
        """
        Parse ``path`` and load tileset images.

        ``extra_search_base`` is tried when a relative tileset path is not found
        next to the map (same behaviour as the editor, which also tries project root).
        """
        p = Path(path)
        parsed = parse_tilemap_file(p)
        map_dir = p.parent
        surfaces: List[Optional[Surface]] = []
        resolved: List[Path] = []
        warnings: List[str] = []

        if not pygame.get_init():
            pygame.init()

        for i, ts in enumerate(parsed.tilesets):
            resolved_path = _resolve_resource_path(ts.path, map_dir, extra_search_base)
            resolved.append(resolved_path)
            if not resolved_path.is_file():
                msg = f"Tileset missing ({i}): {ts.path!r} → {resolved_path}"
                warnings.append(msg)
                surfaces.append(None)
                continue
            try:
                surf = pygame.image.load(str(resolved_path)).convert_alpha()
                surfaces.append(surf)
            except pygame.error as e:
                msg = f"Tileset load failed ({i}) {resolved_path}: {e}"
                warnings.append(msg)
                if not skip_missing_images:
                    raise MapParseError(msg) from e
                surfaces.append(None)

        inst = cls(parsed, surfaces, resolved, warnings, map_path=p)
        return inst

    def _build_path_index(self) -> None:
        self._path_to_index: Dict[str, int] = {}
        for i, pts in enumerate(self.parsed.tilesets):
            raw = pts.path.replace("\\", "/")
            rp = self.resolved_paths[i]
            self._path_to_index[raw] = i
            self._path_to_index[str(rp)] = i
            self._path_to_index[str(rp.resolve())] = i
            self._path_to_index[Path(raw).name] = i

    def _lookup_tileset_index(self, ref: str) -> int:
        ref_norm = ref.replace("\\", "/")
        if ref_norm in self._path_to_index:
            return self._path_to_index[ref_norm]
        pref = Path(ref)
        for i, rp in enumerate(self.resolved_paths):
            try:
                if rp.resolve() == pref.resolve():
                    return i
            except (OSError, ValueError):
                pass
            if rp.name == pref.name:
                return i
        return -1

    def _normalize_tile_ttiles(self) -> None:
        for layer in self.parsed.layers:
            if layer.layer_type == "object":
                continue
            for pos, tile in layer.tiles.items():
                if isinstance(tile.ttype, str):
                    idx = self._lookup_tileset_index(tile.ttype)
                    if idx < 0:
                        self.warnings.append(
                            f"Unresolved tileset ref {tile.ttype!r} at layer {layer.name!r} cell {pos}"
                        )
                    tile.ttype = idx

    def get_image(self, variant: int, ttype: int = 0) -> Optional[Surface]:
        """
        Return a **copy** of the tile subsurface for ``variant`` on tileset ``ttype``.

        Variant layout matches the editor: row-major indices with ``meta.tile_size``.
        """
        if ttype < 0 or ttype >= len(self.surfaces):
            return None
        surf = self.surfaces[ttype]
        if surf is None:
            return None
        return _variant_subsurface_copy(surf, variant, (self._tw, self._th))

    def get_tile_image(self, tile: Union[int, Tuple[int, int], object]) -> Optional[Surface]:
        """
        Convenience: if ``tile`` is an int, treat it as ``variant`` on tileset 0.
        If it is a mapping-like or object with ``ttype`` and ``variant``, use those.
        """
        if isinstance(tile, int):
            return self.get_image(tile, 0)
        ttype = getattr(tile, "ttype", None)
        variant = getattr(tile, "variant", None)
        if ttype is None and isinstance(tile, dict):
            ttype = tile.get("ttype")
            variant = tile.get("variant")
        if ttype is None or variant is None:
            return None
        return self.get_image(int(variant), int(ttype))


def _variant_subsurface_copy(surf: Surface, variant: int, tile_size: Tuple[int, int]) -> Optional[Surface]:
    tw, th = tile_size
    if tw <= 0 or th <= 0:
        return None
    cols = max(1, surf.get_width() // tw)
    col = variant % cols
    row = variant // cols
    src = Rect(col * tw, row * th, tw, th)
    if not surf.get_rect().contains(src):
        return None
    return surf.subsurface(src).copy()


def _resolve_resource_path(
    path_str: str,
    map_dir: Path,
    extra_search_base: Optional[Path],
) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    cand = (map_dir / p).resolve()
    if cand.is_file():
        return cand
    if extra_search_base is not None:
        cand2 = (Path(extra_search_base) / path_str).resolve()
        if cand2.is_file():
            return cand2
    return cand


def load_tilemap_runtime(
    path: PathLike,
    *,
    extra_search_base: Optional[Path] = None,
    skip_missing_images: bool = True,
) -> TilemapRuntime:
    """Alias for :meth:`TilemapRuntime.load`."""
    return TilemapRuntime.load(path, extra_search_base=extra_search_base, skip_missing_images=skip_missing_images)
