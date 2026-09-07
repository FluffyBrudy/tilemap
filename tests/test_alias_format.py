"""Tests for the alias sidecar format (tile-only pattern brushes)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aliases import AliasFile, AliasPattern, AliasScope, alias_path_for


def test_round_trip(tmp_path):
    af = AliasFile(tileset="tiles/stone.png", aliases=[
        AliasPattern(name="WallEnd", w=3, h=2,
                     cells=[(0, 0, 5), (1, 0, 6), (2, 1, 7)]),
    ])
    p = tmp_path / "stone.alias.json"
    af.save(p)
    back = AliasFile.load(p)
    assert back.tileset == "tiles/stone.png"
    assert [(a.name, a.w, a.h, a.cells) for a in back.aliases] == [
        ("WallEnd", 3, 2, [(0, 0, 5), (1, 0, 6), (2, 1, 7)])]


def test_malformed_entries_skipped():
    af = AliasFile.from_dict({
        "version": 1,
        "tileset": "tiles/stone.png",
        "aliases": [
            {"name": "Good", "w": 2, "h": 2, "cells": [[0, 0, 1]]},
            {"name": "Good", "w": 2, "h": 2, "cells": [[1, 1, 2]]},  # dup name
            {"name": "", "w": 2, "h": 2, "cells": [[0, 0, 1]]},
            {"name": "NoCells", "w": 2, "h": 2},
            {"name": "BadDim", "w": 0, "h": 2, "cells": [[0, 0, 1]]},
            {"name": "Oob", "w": 1, "h": 1,
             "cells": [[5, 5, 1], [0, 0, 2], [0, 0, 3]]},  # oob + dup cell
            {"name": "Neg", "w": 2, "h": 2, "cells": [[0, 0, -1]]},
            42, "x", None,
        ],
    })
    assert [(a.name, a.cells) for a in af.aliases] == [
        ("Good", [(0, 0, 1)]), ("Oob", [(0, 0, 2)])]


def test_load_missing_or_corrupt_gives_empty(tmp_path):
    assert AliasFile.load(tmp_path / "nope.alias.json").aliases == []
    bad = tmp_path / "bad.alias.json"
    bad.write_text("{not json")
    assert AliasFile.load(bad).aliases == []
    assert AliasFile.from_dict(None).aliases == []
    assert AliasFile.from_dict({"aliases": "nope"}).aliases == []


def test_scope_aggregates_in_order_and_tracks_mtime(tmp_path):
    (tmp_path / "stone.alias.json").write_text(json.dumps({
        "version": 1, "tileset": "s.png",
        "aliases": [{"name": "A", "w": 1, "h": 1, "cells": [[0, 0, 0]]}]}))
    (tmp_path / "grass.alias.json").write_text(json.dumps({
        "version": 1, "tileset": "g.png",
        "aliases": [{"name": "B", "w": 1, "h": 1, "cells": [[0, 0, 1]]}]}))
    scope = AliasScope(tmp_path, ["stone", "grass", "missing"])
    assert [(s, a.name) for s, _, a in scope.all_aliases()] == [
        ("stone", "A"), ("grass", "B")]
    assert scope.changed() is False
    assert scope.refresh() is False
    (tmp_path / "grass.alias.json").write_text(json.dumps({
        "version": 1, "tileset": "g.png",
        "aliases": [{"name": "C", "w": 1, "h": 1, "cells": [[0, 0, 9]]}]}))
    assert scope.changed() is True
    assert scope.refresh() is True
    assert [a.name for _, _, a in scope.all_aliases()] == ["A", "C"]
    assert alias_path_for(tmp_path, "stone").name == "stone.alias.json"
