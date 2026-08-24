"""Pure operations for keeping tileset identity stable across mutations.

Tiles and objects reference tilesets by *positional index* (``ttype``).
Any mutation that changes that order -- removal, skipped loads on
missing files -- must remap indices or every painted tile silently
re-points at the wrong sheet.  These helpers centralize counting,
remapping, bounds validation, rule fixing and placeholder creation so
widget code (``remove_tileset``), the save path (gid integrity guard)
and the load path (missing-file placeholders) share one implementation.

Everything here is deliberately side-effect-light and unit-testable
without a running editor.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:  # pragma: no cover
    from widgets.autotiler import AutotileRule
    from widgets.tile_selector import TilesetData


# ---------------------------------------------------------------------------
# record iteration
# ---------------------------------------------------------------------------

def _iter_layers(layer_manager: Any) -> Iterable[Any]:
    """Yield every layer of a LayerManager-like object."""
    for layer in getattr(layer_manager, "layers", []) or []:
        yield layer


def iter_ttype_records(layer_manager: Any) -> Iterable[dict]:
    """Yield every paintable record (tile dict or object dict).

    Both shapes carry a ``"ttype"`` key.  Missing/None ttypes and
    non-dict records are skipped defensively so callers never crash on
    half-built layers.
    """
    for layer in _iter_layers(layer_manager):
        tiles = getattr(layer, "tiles", None)
        if isinstance(tiles, dict):
            for rec in tiles.values():
                if isinstance(rec, dict):
                    yield rec
        objects = getattr(layer, "objects", None)
        if isinstance(objects, dict):
            for rec in objects.values():
                if isinstance(rec, dict):
                    yield rec


# ---------------------------------------------------------------------------
# reference counting / remapping
# ---------------------------------------------------------------------------

def count_ttype_refs(layer_manager: Any, index: int) -> int:
    """Number of painted tiles/objects referencing tileset *index*."""
    return sum(
        1
        for rec in iter_ttype_records(layer_manager)
        if rec.get("ttype") == index
    )


def remap_after_removal(layer_manager: Any, removed_index: int) -> int:
    """Shift every ``ttype > removed_index`` down by one, in place.

    Records pointing AT ``removed_index`` are left untouched -- callers
    must guarantee none exist (see :func:`count_ttype_refs`) or accept
    orphaned records.  Returns the number of records remapped.
    """
    changed = 0
    for rec in iter_ttype_records(layer_manager):
        t = rec.get("ttype")
        if isinstance(t, int) and t > removed_index:
            rec["ttype"] = t - 1
            changed += 1
    return changed


def validate_ttype_bounds(
    layer_manager: Any,
    tileset_count: int,
) -> list[str]:
    """Return human-readable errors for records whose ttype is out of range.

    Used by the save path as a hard gate: writing gids derived from a
    shorter/shifted tileset list would silently corrupt the map.
    """
    problems: list[str] = []
    if tileset_count <= 0:
        return problems
    for layer in _iter_layers(layer_manager):
        name = getattr(layer, "name", "?")
        tiles = getattr(layer, "tiles", None)
        if isinstance(tiles, dict):
            for loc, rec in tiles.items():
                if not isinstance(rec, dict):
                    continue
                t = rec.get("ttype")
                if isinstance(t, int) and not 0 <= t < tileset_count:
                    problems.append(
                        f"layer '{name}' tile {loc}: ttype {t} outside 0..{tileset_count - 1}"
                    )
        objects = getattr(layer, "objects", None)
        if isinstance(objects, dict):
            for oid, rec in objects.items():
                if not isinstance(rec, dict):
                    continue
                t = rec.get("ttype")
                if isinstance(t, int) and not 0 <= t < tileset_count:
                    problems.append(
                        f"layer '{name}' object #{oid}: ttype {t} outside 0..{tileset_count - 1}"
                    )
    return problems


# ---------------------------------------------------------------------------
# autotile rules
# ---------------------------------------------------------------------------

def _iter_rules(autotiler: Any) -> Iterable["AutotileRule"]:
    for group in getattr(autotiler, "groups", []) or []:
        yield from getattr(group, "rules", []) or []
    yield from getattr(autotiler, "rules", []) or []


def _resolve_rule_index(rule_path: str, tilesets: list) -> int | None:
    """Re-resolve an autotile rule's tileset index from its stored path."""
    if not rule_path:
        return None
    try:
        want = Path(rule_path)
    except (TypeError, ValueError):
        return None
    for i, ts in enumerate(tilesets):
        ts_path = getattr(ts, "path", None)
        if ts_path is None:
            continue
        try:
            if Path(ts_path) == want or Path(ts_path).name == want.name:
                return i
        except (TypeError, ValueError):
            continue
    return None


def remap_rule_indexes(autotiler: Any, removed_index: int, tilesets: list) -> int:
    """Fix autotile rules after removing the tileset at *removed_index*.

    Rules living above the removed slot shift down; rules pointing at
    the removed slot fall back to their persisted ``tileset_path``
    (source of truth) or None when unresolvable.  Returns fix count.
    """
    fixed = 0
    for rule in _iter_rules(autotiler):
        idx = getattr(rule, "tileset_index", None)
        if not isinstance(idx, int):
            continue
        if idx > removed_index:
            rule.tileset_index = idx - 1
            fixed += 1
        elif idx == removed_index:
            rule.tileset_index = _resolve_rule_index(
                getattr(rule, "tileset_path", ""), tilesets
            )
            fixed += 1
    return fixed


# ---------------------------------------------------------------------------
# placeholder for missing tileset files (load-time index preservation)
# ---------------------------------------------------------------------------

PLACEHOLDER_SUFFIX = " (missing)"


def make_placeholder_tileset(
    missing_path_str: str,
    tile_size: tuple[int, int],
    tileset_type: str = "tile",
) -> "TilesetData":
    """Build a magenta stand-in preserving the resource slot of a missing file.

    The surface is exactly one tile so downstream variant math stays in
    bounds; the name carries a ``(missing)`` marker and ``path`` keeps
    the original location so a later save round-trips the entry.
    """
    from widgets.tile_selector import TilesetData  # local: avoid import cycle

    tw = max(1, int(tile_size[0]))
    th = max(1, int(tile_size[1]))

    import pygame

    surf = pygame.Surface((tw, th), pygame.SRCALPHA)
    surf.fill((255, 0, 255, 255))

    p = Path(missing_path_str)
    ts = TilesetData(p.name + PLACEHOLDER_SUFFIX, p, surf, tileset_type=tileset_type)
    ts.properties = {"placeholder": True}
    return ts


def is_placeholder(ts: Any) -> bool:
    return bool(getattr(ts, "properties", None) or {}).get("placeholder", False)
