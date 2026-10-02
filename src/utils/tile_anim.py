"""Tile clips stored in *.tanim.json files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

PathLike = str | Path

TANIM_VERSION = 1
TANIM_SUFFIX = ".tanim.json"
ANIM_CLIP_KEY = "anim_clip"
MODE_DEFAULT = "default"
MODE_RANDOM_START = "random_start_times"


@dataclass(frozen=True)
class TileClipFrame:
    sheet: str = ""
    variant: int = 0
    duration_ms: float = 100.0


@dataclass(frozen=True)
class TileAnimClip:
    name: str = ""
    frames: tuple[TileClipFrame, ...] = ()
    loop: bool = True
    mode: str = MODE_DEFAULT

    def total_duration_ms(self) -> float:
        return sum(f.duration_ms for f in self.frames)


@dataclass
class TileAnimFile:
    tileset: str = ""
    clips: list[TileAnimClip] = field(default_factory=list)

    def by_name(self, name: str) -> TileAnimClip | None:
        for clip in self.clips:
            if clip.name == name:
                return clip
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": TANIM_VERSION,
            "tileset": self.tileset,
            "clips": {
                c.name: {
                    "loop": c.loop,
                    "mode": c.mode,
                    "frames": [
                        {"sheet": f.sheet, "variant": f.variant, "duration_ms": f.duration_ms}
                        for f in c.frames
                    ],
                }
                for c in self.clips
            },
        }

    @staticmethod
    def from_dict(data: Any) -> TileAnimFile:
        if not isinstance(data, dict):
            return TileAnimFile()
        tileset = data.get("tileset", "")
        raw = data.get("clips", {})
        clips: list[TileAnimClip] = []
        if isinstance(raw, dict):
            for name, entry in raw.items():
                clip = _parse_clip(name, entry)
                if clip is None:
                    continue
                clips.append(clip)
        return TileAnimFile(
            tileset=tileset if isinstance(tileset, str) else "",
            clips=clips,
        )

    @staticmethod
    def load(path: PathLike) -> TileAnimFile:
        try:
            with open(path) as f:
                return TileAnimFile.from_dict(json.load(f))
        except (OSError, ValueError):
            return TileAnimFile()

    def save(self, path: PathLike) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)


def _is_frame(frame: Any) -> bool:
    return (
        isinstance(frame, dict)
        and isinstance(frame.get("sheet"), str)
        and bool(frame.get("sheet"))
        and isinstance(frame.get("variant"), int)
        and not isinstance(frame.get("variant"), bool)
        and frame.get("variant") >= 0
        and isinstance(frame.get("duration_ms", 100.0), (int, float))
        and not isinstance(frame.get("duration_ms", 100.0), bool)
        and frame.get("duration_ms", 100.0) > 0
        and frame.get("duration_ms", 100.0) != float("inf")
    )


def _parse_clip(name: Any, data: Any) -> TileAnimClip | None:
    if not isinstance(name, str) or not name or not isinstance(data, dict):
        return None
    raw_frames = data.get("frames")
    if not isinstance(raw_frames, list) or not raw_frames:
        return None
    frames = [
        TileClipFrame(
            sheet=f["sheet"],
            variant=f["variant"],
            duration_ms=float(f.get("duration_ms", 100.0)),
        )
        for f in raw_frames
        if _is_frame(f)
    ]
    if not frames:
        return None
    mode = data.get("mode", MODE_DEFAULT)
    if mode not in (MODE_DEFAULT, MODE_RANDOM_START):
        mode = MODE_DEFAULT
    return TileAnimClip(
        name=name,
        frames=tuple(frames),
        loop=data.get("loop", True) is True,
        mode=mode,
    )


def load_tile_anim_file(path: PathLike) -> dict[str, TileAnimClip]:
    """Load clips from file. Returns empty dict on error."""
    return {c.name: c for c in TileAnimFile.load(path).clips}


def detect_anim_schema(data: Any) -> str:
    """Return sprite, tile, or unknown."""
    if not isinstance(data, dict):
        return "unknown"
    if isinstance(data.get("animations"), dict):
        return "sprite"
    if isinstance(data.get("clips"), dict):
        return "tile"
    return "unknown"


def detect_anim_schema_file(path: PathLike) -> str:
    """Return schema for a file. Unknown if unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            return detect_anim_schema(json.load(f))
    except (OSError, ValueError):
        return "unknown"


def tanim_to_library_dict(
    tanim: TileAnimFile | dict[str, Any],
    *,
    spritesheet: str | None = None,
    tile_size: tuple[int, int] = (32, 32),
) -> dict[str, Any]:
    """Convert tile clips to sprite library dict. Per-frame sheets are dropped."""
    file = tanim if isinstance(tanim, TileAnimFile) else TileAnimFile.from_dict(tanim)
    sheet = spritesheet if spritesheet is not None else file.tileset
    tw, th = tile_size
    try:
        tw, th = int(tw), int(th)
    except (TypeError, ValueError):
        tw, th = (32, 32)
    if tw < 1 or th < 1:
        tw, th = (32, 32)
    return {
        "spritesheet_path": sheet,
        "tile_size": [tw, th],
        "grid_offset": [0, 0],
        "animations": {
            clip.name: {
                "name": clip.name,
                "frames": [
                    {"variant_id": f.variant, "duration_ms": f.duration_ms} for f in clip.frames
                ],
                "loop": clip.loop,
                "fps": 60.0,
            }
            for clip in file.clips
        },
    }


ANIMATIONS_DIR_NAME = "animations"


def animations_dir(data_root: PathLike | None) -> Path | None:
    """Return data/animations dir, or None."""
    if data_root is None:
        return None
    return Path(data_root) / ANIMATIONS_DIR_NAME


def resolve_tanim_for_tileset(tileset_path: PathLike, data_root: PathLike | None) -> Path | None:
    """Return data/animations/<stem>.tanim.json path."""
    base = animations_dir(data_root)
    if base is None:
        return None
    return base / (Path(tileset_path).stem + TANIM_SUFFIX)


def resolve_clip_sheet(paths: list[str], sheet_ref: str) -> int | None:
    """Find sheet index by exact path, then file name, then stem."""

    def norm(p: str) -> str:
        return str(PurePosixPath(p.replace("\\", "/")))

    ref = norm(sheet_ref or "")
    if not ref:
        return None
    for i, p in enumerate(paths):
        if norm(p or "") == ref:
            return i
    ref_name = PurePosixPath(ref).name
    hits = [i for i, p in enumerate(paths) if PurePosixPath(norm(p or "")).name == ref_name]
    if len(hits) == 1:
        return hits[0]
    ref_stem = PurePosixPath(ref).stem
    hits = [i for i, p in enumerate(paths) if PurePosixPath(norm(p or "")).stem == ref_stem]
    if len(hits) == 1:
        return hits[0]
    return None


def _frame_index_at(clip: TileAnimClip, time_ms: float, phase: int = 0) -> int:
    n = len(clip.frames)
    total = clip.total_duration_ms()
    if n == 0 or total <= 0:
        return 0
    phase = phase % n
    if not clip.loop and time_ms >= total:
        return (phase + n - 1) % n
    t = time_ms % total if clip.loop else time_ms
    acc = 0.0
    for i in range(n):
        idx = (phase + i) % n
        acc += clip.frames[idx].duration_ms
        if t < acc:
            return idx
    return (phase + n - 1) % n


def clip_frame_at(clip: TileAnimClip, time_ms: float, phase: int = 0) -> TileClipFrame | None:
    if not clip.frames:
        return None
    return clip.frames[_frame_index_at(clip, time_ms, phase)]


def clip_phase_for_cell(x: int, y: int, ttype: int, n: int) -> int:
    """Return start offset for a cell so synced tiles look varied."""
    if n <= 0:
        return 0
    return ((x * 73856093) ^ (y * 19349663) ^ (ttype * 83492791)) % n


def generate_strip_clips(
    *,
    sheet: str,
    base_variants: list[int],
    frame_stride: int,
    frame_count: int,
    name_for: Any = None,
    duration_ms: float = 100.0,
    loop: bool = True,
    mode: str = MODE_DEFAULT,
) -> dict[str, TileAnimClip]:
    """Build one clip per base variant from a uniform strip."""
    clips: dict[str, TileAnimClip] = {}
    for vid in base_variants:
        name = name_for(vid) if callable(name_for) else f"clip_{vid}"
        frames = tuple(
            TileClipFrame(sheet=sheet, variant=vid + k * frame_stride, duration_ms=duration_ms)
            for k in range(max(0, frame_count))
        )
        if not frames:
            continue
        clips[name] = TileAnimClip(name=name, frames=frames, loop=loop, mode=mode)
    return clips


def sprite_library_to_tanim(
    lib: dict[str, Any],
    *,
    sheet: str,
    duration_default_ms: float = 100.0,
    mode: str | None = None,
    sheets: dict[str, list[str]] | None = None,
    clip_modes: dict[str, str] | None = None,
) -> TileAnimFile:
    """Convert sprite anim dict to tile file. Skips bad entries."""
    anims = lib.get("animations", {}) if isinstance(lib, dict) else {}
    clips: list[TileAnimClip] = []
    if isinstance(anims, dict):
        for name, entry in anims.items():
            if not isinstance(name, str) or not name or not isinstance(entry, dict):
                continue
            raw_frames = entry.get("frames", [])
            if not isinstance(raw_frames, list) or not raw_frames:
                continue
            frames: list[TileClipFrame] = []
            for f in raw_frames:
                if not isinstance(f, dict):
                    continue
                vid = f.get("variant_id", f.get("variant"))
                if isinstance(vid, bool) or not isinstance(vid, int) or vid < 0:
                    continue
                dur = f.get("duration_ms", duration_default_ms)
                if isinstance(dur, bool) or not isinstance(dur, (int, float)) or dur <= 0:
                    dur = duration_default_ms
                frames.append(TileClipFrame(sheet=sheet, variant=vid, duration_ms=float(dur)))
            if not frames:
                continue
            clip_mode = mode if mode in (MODE_DEFAULT, MODE_RANDOM_START) else None
            if clip_mode is None and clip_modes:
                stored = clip_modes.get(name)
                if stored in (MODE_DEFAULT, MODE_RANDOM_START):
                    clip_mode = stored
            if clip_mode is None:
                clip_mode = entry.get("mode", MODE_DEFAULT)
                if clip_mode not in (MODE_DEFAULT, MODE_RANDOM_START):
                    clip_mode = MODE_DEFAULT
            stored_sheets = sheets.get(name) if sheets else None
            if stored_sheets is not None and len(stored_sheets) == len(frames):
                frames = [
                    TileClipFrame(sheet=s, variant=f.variant, duration_ms=f.duration_ms)
                    for f, s in zip(frames, stored_sheets, strict=True)
                    if isinstance(s, str) and s
                ]
                if not frames:
                    continue
            clips.append(
                TileAnimClip(
                    name=name if isinstance(entry.get("name", name), str) else name,
                    frames=tuple(frames),
                    loop=entry.get("loop", True) is True,
                    mode=clip_mode,
                )
            )
    tileset = lib.get("spritesheet_path", sheet) if isinstance(lib, dict) else sheet
    if not isinstance(tileset, str) or not tileset:
        tileset = sheet
    return TileAnimFile(tileset=tileset, clips=clips)


class TileAnimCache:
    """Cache tile clips by file path and mod time."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, dict[str, TileAnimClip]]] = {}

    def get_clips(
        self, tileset_path: PathLike, data_root: PathLike | None = None
    ) -> tuple[Path | None, dict[str, TileAnimClip]]:
        tanim = resolve_tanim_for_tileset(tileset_path, data_root)
        if tanim is None:
            return None, {}
        key = str(tanim)
        try:
            mtime = tanim.stat().st_mtime if tanim.is_file() else -1.0
        except OSError:
            mtime = -1.0
        cached = self._data.get(key)
        if cached is not None and cached[0] == mtime:
            return tanim, cached[1]
        clips = load_tile_anim_file(tanim) if mtime >= 0 else {}
        self._data[key] = (mtime, clips)
        return tanim, clips

    def invalidate(self, tanim: PathLike | None = None) -> None:
        if tanim is None:
            self._data.clear()
        else:
            self._data.pop(str(Path(tanim)), None)
