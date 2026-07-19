from __future__ import annotations

import json
from pathlib import Path

import pygame
from pygame import Surface

from widgets.ui.region_selector import Region


def regions_sidecar_path(image_path: Path) -> Path:
    return image_path.with_suffix(".regions.json")


def export_all_regions(
    image: Surface,
    regions: list[Region],
    output_dir: Path,
    prefix: str = "region",
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for i, region in enumerate(regions):
        r = region.rect
        if r.width <= 0 or r.height <= 0:
            continue
        sub = image.subsurface(r)
        path = output_dir / f"{prefix}_{i}.png"
        pygame.image.save(sub, str(path))
        saved.append(path)
    return saved


def save_regions_json(regions: list[Region], path: Path) -> None:
    data = {"regions": [r.to_dict() for r in regions]}
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_regions_json(path: Path) -> list[Region]:
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return [Region.from_dict(r) for r in data.get("regions", [])]
