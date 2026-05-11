"""
Strict parsing and pygame loading for ``.anim.json`` libraries (game runtime).

``AnimationLibrary`` JSON does not store grid offset; use
:class:`SpriteAnimRuntime` with offset (0, 0) or :class:`SpriteAnimationEditor.get_image`
when offsets are authored in the editor UI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pygame
from pygame import Rect, Surface

from .models import Animation, AnimationFrame, AnimationLibrary, AnimationMarker

PathLike = Union[str, Path]


class AnimationParseError(ValueError):
    """Invalid animation JSON."""


def _req_dict(v: Any, ctx: str) -> Dict[str, Any]:
    if not isinstance(v, dict):
        raise AnimationParseError(f"{ctx}: expected object")
    return v


def _req_list(v: Any, ctx: str) -> List[Any]:
    if not isinstance(v, list):
        raise AnimationParseError(f"{ctx}: expected array")
    return v


def _req_str(v: Any, ctx: str) -> str:
    if not isinstance(v, str):
        raise AnimationParseError(f"{ctx}: expected string")
    return v


def _coerce_int(v: Any, ctx: str) -> int:
    if isinstance(v, bool):
        raise AnimationParseError(f"{ctx}: expected int")
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        try:
            return int(v, 10)
        except ValueError as e:
            raise AnimationParseError(f"{ctx}: expected int") from e
    raise AnimationParseError(f"{ctx}: expected int")


def _coerce_float(v: Any, ctx: str) -> float:
    if isinstance(v, bool):
        raise AnimationParseError(f"{ctx}: expected number")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError as e:
            raise AnimationParseError(f"{ctx}: expected number") from e
    raise AnimationParseError(f"{ctx}: expected number")


def _parse_marker(d: Dict[str, Any], ctx: str) -> AnimationMarker:
    return AnimationMarker(
        name=_req_str(d.get("name"), f"{ctx}.name"),
        frame_index=_coerce_int(d.get("frame_index"), f"{ctx}.frame_index"),
    )


def _parse_frame(d: Dict[str, Any], ctx: str) -> AnimationFrame:
    return AnimationFrame(
        variant_id=_coerce_int(d.get("variant_id"), f"{ctx}.variant_id"),
        duration_ms=_coerce_float(d.get("duration_ms", 100.0), f"{ctx}.duration_ms"),
    )


def _parse_animation(name: str, d: Dict[str, Any], ctx: str) -> Animation:
    frames_raw = _req_list(d.get("frames", []), f"{ctx}.frames")
    frames = [
        _parse_frame(_req_dict(x, f"{ctx}.frames[{i}]"), f"{ctx}.frames[{i}]")
        for i, x in enumerate(frames_raw)
    ]
    meta_raw = d.get("metadata")
    if meta_raw is None:
        metadata: Dict[str, Any] = {}
    elif isinstance(meta_raw, dict):
        metadata = dict(meta_raw)
    else:
        raise AnimationParseError(f"{ctx}.metadata: expected object or null")

    markers_raw = d.get("markers")
    markers: List[AnimationMarker] = []
    if markers_raw is not None:
        ml = _req_list(markers_raw, f"{ctx}.markers")
        for i, m in enumerate(ml):
            markers.append(_parse_marker(_req_dict(m, f"{ctx}.markers[{i}]"), f"{ctx}.markers[{i}]"))

    anim = Animation(
        name=_req_str(d.get("name", name), f"{ctx}.name"),
        frames=frames,
        loop=bool(d.get("loop", True)),
        fps=_coerce_float(d.get("fps", 60.0), f"{ctx}.fps"),
        metadata=metadata,
        markers=markers,
    )
    anim.clamp_markers()
    return anim


def parse_animation_library_dict(data: Dict[str, Any]) -> AnimationLibrary:
    """Validate and build an :class:`AnimationLibrary` (raises :exc:`AnimationParseError`)."""
    root = _req_dict(data, "root")
    sp = root.get("spritesheet_path")
    spritesheet_path = _req_str(sp, "spritesheet_path") if sp is not None else None

    ts = root.get("tile_size", [32, 32])
    ts_list = _req_list(ts, "tile_size")
    if len(ts_list) != 2:
        raise AnimationParseError("tile_size: expected [w, h]")
    tw = _coerce_int(ts_list[0], "tile_size[0]")
    th = _coerce_int(ts_list[1], "tile_size[1]")
    if tw < 1 or th < 1:
        raise AnimationParseError("tile_size: width and height must be >= 1")

    anims_raw = _req_dict(root.get("animations", {}), "animations")
    animations: Dict[str, Animation] = {}
    for key, val in anims_raw.items():
        if not isinstance(key, str):
            key = str(key)
        animations[key] = _parse_animation(key, _req_dict(val, f"animations[{key!r}]"), f"animations[{key!r}]")

    return AnimationLibrary(
        animations=animations,
        spritesheet_path=spritesheet_path,
        tile_size=(tw, th),
    )


def parse_animation_library_json(text: str) -> AnimationLibrary:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        raise AnimationParseError(f"Invalid JSON: {e}") from e
    return parse_animation_library_dict(_req_dict(payload, "root"))


def parse_animation_library_file(path: PathLike) -> AnimationLibrary:
    p = Path(path)
    if not p.is_file():
        raise AnimationParseError(f"Not a file: {p}")
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        raise AnimationParseError(f"Cannot read {p}: {e}") from e
    return parse_animation_library_json(text)


@dataclass
class SpriteAnimRuntime:
    """Spritesheet + parsed library + ``get_image(variant_id)`` for games."""

    library: AnimationLibrary
    surface: Surface
    warnings: List[str]
    json_path: Optional[Path] = None
    grid_offset_x: int = 0
    grid_offset_y: int = 0

    @classmethod
    def load(
        cls,
        json_path: PathLike,
        *,
        spritesheet_path: Optional[PathLike] = None,
        extra_search_base: Optional[Path] = None,
    ) -> SpriteAnimRuntime:
        p = Path(json_path)
        library = parse_animation_library_file(p)
        warnings: List[str] = []

        if not pygame.get_init():
            pygame.init()

        sheet_ref = spritesheet_path
        if sheet_ref is None and library.spritesheet_path:
            sheet_ref = library.spritesheet_path
        if sheet_ref is None:
            raise AnimationParseError("No spritesheet_path in JSON and none passed to load()")

        img_path = Path(sheet_ref)
        if not img_path.is_absolute():
            candidates = [(p.parent / img_path).resolve()]
            if extra_search_base is not None:
                candidates.append((Path(extra_search_base) / sheet_ref).resolve())
            candidates.extend((parent / img_path).resolve() for parent in p.parents)

            img_path = candidates[0]
            for candidate in candidates:
                if candidate.is_file():
                    img_path = candidate
                    break

        if not img_path.is_file():
            raise AnimationParseError(f"Spritesheet not found: {sheet_ref!r} (tried {img_path})")

        try:
            surface = pygame.image.load(str(img_path)).convert_alpha()
        except pygame.error as e:
            raise AnimationParseError(f"Failed to load image {img_path}: {e}") from e

        return cls(library=library, surface=surface, warnings=warnings, json_path=p)

    def get_image(self, variant: int) -> Optional[Surface]:
        """Extract cel ``variant`` using tile size and optional grid offset (default 0,0)."""
        tw, th = int(self.library.tile_size[0]), int(self.library.tile_size[1])
        if tw < 1 or th < 1:
            return None
        ox, oy = self.grid_offset_x, self.grid_offset_y
        avail_w = self.surface.get_width() - ox
        avail_h = self.surface.get_height() - oy
        if avail_w < tw or avail_h < th:
            return None
        cols = max(1, avail_w // tw)
        col = variant % cols
        row = variant // cols
        src = Rect(ox + col * tw, oy + row * th, tw, th)
        if not self.surface.get_rect().contains(src):
            return None
        return self.surface.subsurface(src).copy()
