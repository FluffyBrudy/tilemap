"""
Data models for sprite animations.

Pure data — no pygame dependency. These are serializable to/from JSON
and can be used in headless tools, exporters, or game runtimes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.project_paths import to_project_path


@dataclass
class AnimationMarker:
    """Named cue on a frame index (e.g. startup / active / recovery boundaries)."""

    name: str
    frame_index: int

    def to_dict(self) -> dict:
        return {"name": self.name, "frame_index": self.frame_index}

    @staticmethod
    def from_dict(data: dict) -> AnimationMarker:
        return AnimationMarker(
            name=str(data["name"]),
            frame_index=int(data["frame_index"]),
        )


@dataclass
class AnimationFrame:
    """A single frame in an animation sequence."""

    variant_id: int  # Tile index in the spritesheet (row-major)
    duration_ms: float = 100.0  # How long this frame displays

    def to_dict(self) -> dict:
        return {"variant_id": self.variant_id, "duration_ms": self.duration_ms}

    @staticmethod
    def from_dict(data: dict) -> AnimationFrame:
        return AnimationFrame(
            variant_id=data["variant_id"],
            duration_ms=data.get("duration_ms", 100.0),
        )


@dataclass
class Animation:
    """A named animation sequence composed of frames."""

    name: str
    frames: List[AnimationFrame] = field(default_factory=list)
    loop: bool = True
    # Playback rate hint for preview + runtime (wall-clock: durations are ms per cel).
    fps: float = 60.0
    # Optional JSON-serializable key/value data (combat phases, tags, exporter hints, …).
    metadata: Dict[str, Any] = field(default_factory=dict)
    markers: List[AnimationMarker] = field(default_factory=list)

    def total_duration_ms(self) -> float:
        return sum(f.duration_ms for f in self.frames)

    def frame_count(self) -> int:
        return len(self.frames)

    def add_frame(self, variant_id: int, duration_ms: float = 100.0) -> AnimationFrame:
        frame = AnimationFrame(variant_id=variant_id, duration_ms=duration_ms)
        self.frames.append(frame)
        return frame

    def remove_frame(self, index: int) -> bool:
        if 0 <= index < len(self.frames):
            self.frames.pop(index)
            return True
        return False

    def move_frame(self, from_idx: int, to_idx: int) -> bool:
        if 0 <= from_idx < len(self.frames) and 0 <= to_idx < len(self.frames):
            frame = self.frames.pop(from_idx)
            self.frames.insert(to_idx, frame)
            return True
        return False

    def duplicate_frame(self, index: int) -> bool:
        if 0 <= index < len(self.frames):
            orig = self.frames[index]
            copy = AnimationFrame(
                variant_id=orig.variant_id, duration_ms=orig.duration_ms
            )
            self.frames.insert(index + 1, copy)
            return True
        return False

    def clamp_markers(self) -> None:
        """Keep marker indices valid after frame add/remove/reorder."""
        n = len(self.frames)
        if n == 0:
            self.markers.clear()
            return
        for m in self.markers:
            m.frame_index = max(0, min(m.frame_index, n - 1))

    def copy_as_new_name(self, new_name: str) -> Animation:
        """Deep copy of this clip under a new name (for duplicate / template)."""
        return Animation(
            name=new_name,
            frames=[
                AnimationFrame(f.variant_id, f.duration_ms) for f in self.frames
            ],
            loop=self.loop,
            fps=self.fps,
            metadata=dict(self.metadata),
            markers=[AnimationMarker(m.name, m.frame_index) for m in self.markers],
        )

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "frames": [f.to_dict() for f in self.frames],
            "loop": self.loop,
            "fps": self.fps,
        }
        if self.metadata:
            d["metadata"] = dict(self.metadata)
        if self.markers:
            d["markers"] = [m.to_dict() for m in self.markers]
        return d

    @staticmethod
    def from_dict(data: dict) -> Animation:
        raw_meta = data.get("metadata")
        if raw_meta is None:
            meta: Dict[str, Any] = {}
        elif isinstance(raw_meta, dict):
            meta = dict(raw_meta)
        else:
            meta = {}
        raw_markers = data.get("markers")
        markers: List[AnimationMarker] = []
        if isinstance(raw_markers, list):
            for item in raw_markers:
                if isinstance(item, dict) and "name" in item and "frame_index" in item:
                    markers.append(AnimationMarker.from_dict(item))
        anim = Animation(
            name=data["name"],
            frames=[AnimationFrame.from_dict(f) for f in data.get("frames", [])],
            loop=data.get("loop", True),
            fps=float(data.get("fps", 60.0)),
            metadata=meta,
            markers=markers,
        )
        anim.clamp_markers()
        return anim


@dataclass
class AnimationLibrary:
    """Collection of named animations tied to a single spritesheet."""

    animations: Dict[str, Animation] = field(default_factory=dict)
    spritesheet_path: Optional[str] = None
    tile_size: Tuple[int, int] = (32, 32)

    def add_animation(self, anim: Animation) -> None:
        self.animations[anim.name] = anim

    def remove_animation(self, name: str) -> bool:
        if name in self.animations:
            del self.animations[name]
            return True
        return False

    def rename_animation(self, old_name: str, new_name: str) -> bool:
        if old_name in self.animations and new_name not in self.animations:
            anim = self.animations.pop(old_name)
            anim.name = new_name
            self.animations[new_name] = anim
            return True
        return False

    def get_animation(self, name: str) -> Optional[Animation]:
        return self.animations.get(name)

    def animation_names(self) -> List[str]:
        return list(self.animations.keys())

    def to_dict(self, *, base_path: Optional[Path] = None) -> dict:
        spritesheet_path = self.spritesheet_path
        if spritesheet_path and base_path is not None:
            spritesheet_path = to_project_path(spritesheet_path, base_path)

        return {
            "spritesheet_path": spritesheet_path,
            "tile_size": list(self.tile_size),
            "animations": {
                name: anim.to_dict() for name, anim in self.animations.items()
            },
        }

    @staticmethod
    def from_dict(data: dict) -> AnimationLibrary:
        lib = AnimationLibrary(
            spritesheet_path=data.get("spritesheet_path"),
            tile_size=tuple(data.get("tile_size", [32, 32])),
        )
        for name, anim_data in data.get("animations", {}).items():
            lib.animations[name] = Animation.from_dict(anim_data)
        return lib

    def save(self, path: Path, *, base_path: Optional[Path] = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(base_path=base_path), f, indent=2)

    @staticmethod
    def load(path: Path) -> AnimationLibrary:
        with open(path, "r", encoding="utf-8") as f:
            return AnimationLibrary.from_dict(json.load(f))
