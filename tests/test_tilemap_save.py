"""
Tests for Tilemap.save_map.

Catches regressions like referencing undefined variables in the
save path (e.g., `base_path` instead of `map_dir` when serializing
autotile rules).
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestSaveMapAutotileRules:
    """save_map must handle autotile rules without NameError"""

    @pytest.fixture
    def fake_autotiler(self):
        class FakeRule:
            def __init__(self, name: str):
                self.name = name
                self.tileset_path = ""
                self.tileset_index = None
                self.variant_ids = []
                self.group_id = name

            def to_dict(self):
                return {
                    "name": self.name,
                    "neighbors": [],
                    "tileset_path": self.tileset_path,
                    "tileset_index": self.tileset_index,
                    "variant_ids": self.variant_ids,
                    "group_id": self.group_id,
                }

        class FakeGroup:
            def __init__(self, name: str, rules):
                self.name = name
                self.rules = rules

        class FakeAutotiler:
            groups = [FakeGroup("Test", [FakeRule("rule_a"), FakeRule("rule_b")])]

            @property
            def rules(self):
                all_rules = []
                for g in self.groups:
                    all_rules.extend(g.rules)
                return all_rules

        return FakeAutotiler()

    @pytest.fixture
    def editor(self, fake_autotiler):
        class FakeTilesetWidget:
            tilesets = []

        class FakeTileGrid:
            zoom_level = 1.0
            scroll_x = 0
            scroll_y = 0

        class FakeEditor:
            tileset_widget = FakeTilesetWidget()
            tile_grid_widget = FakeTileGrid()
            autotiler = fake_autotiler
            base_path = None
            data_root = None
            regex_automap_designer = None

        return FakeEditor()

    def test_save_map_with_autotile_rules_succeeds(self, editor):
        """save_map must not raise when autotiler is configured with rules"""
        from tilemap import Tilemap

        tm = Tilemap(editor)
        tm.init_size((16, 16), (10, 10))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            tm.save_map(path)
            with open(path) as f:
                data = json.load(f)

        assert "project_state" in data
        assert "rules" in data["project_state"]
        assert "groups" in data["project_state"]

    def test_save_map_autotile_rules_serialized_correctly(self, editor):
        """saved autotile rules should appear in project_state.rules"""
        from tilemap import Tilemap

        tm = Tilemap(editor)
        tm.init_size((16, 16), (10, 10))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            tm.save_map(path)
            with open(path) as f:
                data = json.load(f)

        rule_names = [r["name"] for r in data["project_state"]["rules"]]
        assert "rule_a" in rule_names
        assert "rule_b" in rule_names

    def test_save_map_autotile_groups_serialized_correctly(self, editor):
        """saved autotile groups should appear in project_state.groups"""
        from tilemap import Tilemap

        tm = Tilemap(editor)
        tm.init_size((16, 16), (10, 10))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            tm.save_map(path)
            with open(path) as f:
                data = json.load(f)

        group_names = [g["name"] for g in data["project_state"]["groups"]]
        assert "Test" in group_names

    def test_save_map_without_autotiler_still_works(self):
        """Regression: save_map must work when autotiler is absent"""
        from tilemap import Tilemap

        class FakeTilesetWidget:
            tilesets = []

        class FakeTileGrid:
            zoom_level = 1.0
            scroll_x = 0
            scroll_y = 0

        class FakeEditor:
            tileset_widget = FakeTilesetWidget()
            tile_grid_widget = FakeTileGrid()
            autotiler = None
            base_path = None
            data_root = None
            regex_automap_designer = None

        tm = Tilemap(FakeEditor())
        tm.init_size((16, 16), (10, 10))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            tm.save_map(path)
