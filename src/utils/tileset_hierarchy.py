"""Persistence for virtual tileset folders in the tileset selector tree.

Stored as ``<data_root>/tileset_hierarchy.json`` — a user-visible,
user-editable file next to ``recents.json``. The hierarchy is metadata
only: tilesets themselves are never moved or touched.

Missing or corrupt file means "no hierarchy": callers fall back to the
plain linear list. Items are keyed by project-relative POSIX paths
(``TilesetData.uid`` values reset every launch and must not be used).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from utils.error_handler import error_handler
from utils.project_paths import to_project_path

HIERARCHY_FILENAME = "tileset_hierarchy.json"
VERSION = 1


@dataclass
class FolderEntry:
    id: str
    name: str
    parent: str | None = None


@dataclass
class ItemEntry:
    path: str  # project-relative POSIX path of the tileset image
    folder: str | None = None


@dataclass
class TilesetHierarchy:
    folders: list[FolderEntry] = field(default_factory=list)
    items: list[ItemEntry] = field(default_factory=list)

    def folder_by_id(self, folder_id: str | None) -> FolderEntry | None:
        if folder_id is None:
            return None
        return next((f for f in self.folders if f.id == folder_id), None)

    def item_by_path(self, path: str) -> ItemEntry | None:
        return next((i for i in self.items if i.path == path), None)

    def placement_map(self) -> dict[str, str]:
        """path -> folder_id for items assigned to a known folder."""
        known = {f.id for f in self.folders}
        return {
            i.path: i.folder for i in self.items if i.folder and i.folder in known
        }

    def next_folder_id(self) -> str:
        nums = []
        for f in self.folders:
            suffix = f.id.split("_", 1)[1] if f.id.startswith("f_") else ""
            if suffix.isdigit():
                nums.append(int(suffix))
        return f"f_{max(nums, default=0) + 1}"


def hierarchy_path(data_root: Path) -> Path:
    return Path(data_root) / HIERARCHY_FILENAME


def sanitize(hierarchy: TilesetHierarchy) -> TilesetHierarchy:
    """Drop duplicate ids, unknown parents and parent cycles."""
    seen: set[str] = set()
    folders: list[FolderEntry] = []
    for f in hierarchy.folders:
        if not f.id or f.id in seen:
            continue
        seen.add(f.id)
        folders.append(f)
    by_id = {f.id: f for f in folders}

    for f in folders:
        visited = {f.id}
        cur = f.parent
        while cur is not None:
            if cur not in by_id or cur in visited:
                f.parent = None
                break
            visited.add(cur)
            cur = by_id[cur].parent

    hierarchy.folders = folders
    # drop empty paths, dedupe items by path (keep first occurrence)
    seen_paths: set[str] = set()
    deduped: list[ItemEntry] = []
    for i in hierarchy.items:
        if not i.path or i.path in seen_paths:
            continue
        if i.folder is not None and i.folder not in by_id:
            i.folder = None
        seen_paths.add(i.path)
        deduped.append(i)
    hierarchy.items = deduped
    return hierarchy


def load_hierarchy(data_root: Path) -> TilesetHierarchy | None:
    """Load the hierarchy file; None when absent/corrupt/incompatible."""
    path = hierarchy_path(data_root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("root is not an object")
        if data.get("version") != VERSION:
            raise ValueError(f"unsupported version: {data.get('version')!r}")

        folders = []
        for f in data.get("folders") or []:
            parent = f.get("parent")
            folders.append(
                FolderEntry(
                    id=str(f["id"]),
                    name=str(f.get("name", "")),
                    parent=str(parent) if parent else None,
                )
            )
        items = []
        for i in data.get("items") or []:
            folder = i.get("folder")
            items.append(
                ItemEntry(
                    path=str(i["path"]),
                    folder=str(folder) if folder else None,
                )
            )
        return sanitize(TilesetHierarchy(folders=folders, items=items))
    except Exception as e:
        error_handler.capture_info(
            f"tileset_hierarchy.json unusable, using linear view: {e}",
            context="tileset_hierarchy_load",
        )
        return None


def save_hierarchy(data_root: Path, hierarchy: TilesetHierarchy) -> bool:
    """Atomically write the hierarchy file. Returns False on failure."""
    path = hierarchy_path(data_root)
    payload = {
        "version": VERSION,
        "folders": [
            {"id": f.id, "name": f.name, "parent": f.parent} for f in hierarchy.folders
        ],
        "items": [{"path": i.path, "folder": i.folder} for i in hierarchy.items],
    }
    tmp = path.with_suffix(".json.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception as e:
        error_handler.capture(e, context="tileset_hierarchy_save")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def relative_path(path: Path, data_root: Path) -> str:
    return to_project_path(path, data_root)
