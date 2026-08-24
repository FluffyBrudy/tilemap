"""Tests for sandbox mode: CLI pre-flight validation, node sidecar fallback,
data_root redirect, and Save-As asset copy/export semantics."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class FakeNotifications:
    def __init__(self):
        self.messages = []

    def notify(self, text, color=None, duration=3.0):
        self.messages.append(("notify", text))

    def error(self, text, detail=""):
        self.messages.append(("error", text))

    def success(self, text, detail=""):
        self.messages.append(("success", text))


class FakeConfirmDialog:
    def __init__(self):
        self.calls = []

    def show(self, title, message, on_confirm, on_cancel):
        self.calls.append((title, message, on_confirm, on_cancel))


class FakeSurface:
    def __init__(self, w=16, h=16):
        self._w = w
        self._h = h

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h


class FakeTileset:
    def __init__(self, path: Path, name: str | None = None, tileset_type: str = "tile"):
        self.path = path
        self.name = name or path.name
        self.surface = FakeSurface()
        self.tileset_type = tileset_type
        self.properties = {}
        self.tile_properties = {}
        self.animation = None
        self.uid = path.name


class FakeTilesetWidget:
    def __init__(self, tilesets):
        self.tilesets = tilesets


class FakeTileGrid:
    zoom_level = 1.0
    scroll_x = 0
    scroll_y = 0


def make_editor(sandbox: Path, project_root: Path):
    from editor import Editor
    from node_manager import NodeManager
    from tilemap import Tilemap

    editor = Editor.__new__(Editor)
    editor.base_path = project_root
    editor.data_root = sandbox
    editor._project_data_root = project_root
    editor._sandbox_root = sandbox
    editor.is_sandbox = True
    editor.config = {"nodes_path": "nodes"}
    editor.tile_grid_widget = FakeTileGrid()
    editor.autotiler = None
    editor.regex_automap_designer = None
    editor.notifications = FakeNotifications()
    editor.confirm_dialog = FakeConfirmDialog()
    editor.tilemap = Tilemap(editor)
    editor.tilemap.init_size((16, 16), (10, 10))
    editor.tileset_widget = None
    editor.node_manager = NodeManager(editor)
    return editor


class TestCliValidation:
    def test_missing_sandbox_dir_exits(self, tmp_path, capsys):
        from tilemap_editor.cli import validate_sandbox

        missing = tmp_path / "nope"
        with pytest.raises(SystemExit) as exc:
            validate_sandbox(missing)
        assert exc.value.code == 1
        assert "Sandbox directory not found" in capsys.readouterr().out

    def test_missing_map_json_exits(self, tmp_path, capsys):
        from tilemap_editor.cli import validate_sandbox

        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        with pytest.raises(SystemExit) as exc:
            validate_sandbox(sandbox)
        assert exc.value.code == 1
        assert "Sandbox map not found" in capsys.readouterr().out

    def test_missing_tileset_file_exits(self, tmp_path, capsys):
        from tilemap_editor.cli import validate_sandbox

        sandbox = tmp_path / "sandbox"
        (sandbox / "assets").mkdir(parents=True)
        (sandbox / "assets" / "terrain.png").write_bytes(b"x")
        payload = {
            "meta": {"tile_size": "16;16", "map_size": "10;10", "version": "1.1"},
            "resources": {
                "tilesets": [
                    {"path": "assets/terrain.png", "type": "tile", "tile_count": 16, "firstgid": 0},
                    {"path": "assets/missing.png", "type": "tile", "tile_count": 4, "firstgid": 16},
                ]
            },
            "data": {"ongrid": {}, "layers": []},
        }
        (sandbox / "map.json").write_text(json.dumps(payload))
        with pytest.raises(SystemExit) as exc:
            validate_sandbox(sandbox)
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "assets/missing.png" in out
        assert "assets/terrain.png" not in out

    def test_invalid_map_json_exits(self, tmp_path, capsys):
        from tilemap_editor.cli import validate_sandbox

        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        (sandbox / "map.json").write_text("{not json")
        with pytest.raises(SystemExit) as exc:
            validate_sandbox(sandbox)
        assert exc.value.code == 1
        assert "Failed to read sandbox map" in capsys.readouterr().out

    def test_valid_sandbox_returns_map_path(self, tmp_path):
        from tilemap_editor.cli import validate_sandbox

        sandbox = tmp_path / "sandbox"
        (sandbox / "assets").mkdir(parents=True)
        (sandbox / "assets" / "terrain.png").write_bytes(b"x")
        payload = {
            "meta": {"tile_size": "16;16", "map_size": "10;10", "version": "1.1"},
            "resources": {"tilesets": [{"path": "assets/terrain.png", "type": "tile"}]},
            "data": {"ongrid": {}, "layers": []},
        }
        (sandbox / "map.json").write_text(json.dumps(payload))
        result = validate_sandbox(sandbox)
        assert result == sandbox / "map.json"


class TestNodeSidecarFallback:
    def make_manager(self, sandbox, map_dir):
        from node_manager import NodeManager
        from tilemap import Tilemap

        class _Editor:
            data_root = sandbox
            config = {"nodes_path": "nodes"}

        editor = _Editor()
        editor.tilemap = Tilemap(editor)
        editor.tilemap.init_size((16, 16), (10, 10))
        manager = NodeManager(editor)
        manager.add_node(manager.create_default_node("Objects"))
        manager.save(map_dir / "level.json")
        manager.nodes.clear()
        return manager, map_dir / "level.json"

    def write_map_adjacent_sidecar(self, map_dir, node_id="n1"):
        data = {
            "version": 2,
            "groups": ["G"],
            "nodes": [
                {
                    "node_id": node_id,
                    "name": "Player Spawn",
                    "node_type": "area",
                    "area": {"x": 48, "y": 224, "w": 16, "h": 16},
                    "layer_name": "Objects",
                    "properties": {"type": "player_spawn"},
                    "group": "G",
                }
            ],
        }
        (map_dir / "level.nodes.json").write_text(json.dumps(data))

    def test_map_adjacent_sidecar_found_when_nodes_dir_empty(self, tmp_path):
        manager, map_path = self.make_manager(tmp_path, tmp_path)
        (tmp_path / "nodes" / "level.nodes.json").unlink()
        self.write_map_adjacent_sidecar(tmp_path)
        manager.load(map_path)
        assert "n1" in manager.nodes
        assert manager.groups == ["G"]

    def test_nodes_dir_sidecar_wins_when_both_exist(self, tmp_path):
        sandbox = tmp_path / "sandbox"
        (sandbox / "nodes").mkdir(parents=True)
        manager, map_path = self.make_manager(sandbox, sandbox)
        self.write_map_adjacent_sidecar(sandbox, node_id="adjacent")
        manager.load(map_path)
        assert len(manager.nodes) == 1
        assert "adjacent" not in manager.nodes

    def test_no_sidecar_anywhere_loads_empty(self, tmp_path):
        from node_manager import NodeManager
        from tilemap import Tilemap

        class _Editor:
            data_root = tmp_path
            config = {"nodes_path": "nodes"}

        editor = _Editor()
        editor.tilemap = Tilemap(editor)
        editor.tilemap.init_size((16, 16), (10, 10))
        manager = NodeManager(editor)
        manager.load(tmp_path / "lonely.json")
        assert manager.nodes == {}


class TestSandboxSaveAs:
    def _setup(self, tmp_path, conflict=False):
        sandbox = tmp_path / "sandbox"
        project = tmp_path / "project"
        (sandbox / "assets").mkdir(parents=True)
        (sandbox / "assets" / "terrain.png").write_bytes(b"terrain")
        (sandbox / "assets" / "objects.png").write_bytes(b"objects")
        ts1 = FakeTileset(sandbox / "assets" / "terrain.png")
        ts2 = FakeTileset(sandbox / "assets" / "objects.png", tileset_type="object")
        editor = make_editor(sandbox, project)
        editor.tileset_widget = FakeTilesetWidget([ts1, ts2])
        target_dir = project / "maps"
        target_dir.mkdir(parents=True)
        if conflict:
            (target_dir / "assets").mkdir()
            (target_dir / "assets" / "terrain.png").write_bytes(b"old")
        return editor, target_dir / "export.json"

    def test_save_as_copies_assets_and_rewrites_paths(self, tmp_path):
        editor, target = self._setup(tmp_path)
        editor.on_map_save_selected(target)

        assert (target.parent / "assets" / "terrain.png").read_bytes() == b"terrain"
        assert (target.parent / "assets" / "objects.png").read_bytes() == b"objects"
        assert editor.tileset_widget.tilesets[0].path == target.parent / "assets" / "terrain.png"
        assert editor.tileset_widget.tilesets[1].path == target.parent / "assets" / "objects.png"
        assert editor.is_sandbox is False
        assert editor.data_root == editor._project_data_root
        assert editor.node_manager._nodes_dir == editor._project_data_root / "nodes"

        saved = json.loads(target.read_text())
        paths = [t["path"] for t in saved["resources"]["tilesets"]]
        assert paths == ["assets/terrain.png", "assets/objects.png"]
        assert all(".." not in p for p in paths)

    def test_save_as_conflict_shows_confirm_then_exports(self, tmp_path):
        editor, target = self._setup(tmp_path, conflict=True)
        editor.on_map_save_selected(target)

        assert editor.confirm_dialog.calls
        title, message, on_confirm, _ = editor.confirm_dialog.calls[0]
        assert title == "Overwrite Assets?"
        assert "terrain.png" in message

        assert not target.exists()
        on_confirm()
        assert target.exists()
        assert (target.parent / "assets" / "terrain.png").read_bytes() == b"terrain"
        assert editor.is_sandbox is False

    def test_save_as_no_conflict_skips_confirm(self, tmp_path):
        editor, target = self._setup(tmp_path)
        editor.on_map_save_selected(target)
        assert editor.confirm_dialog.calls == []

    def test_external_tileset_not_repointed(self, tmp_path):
        editor, target = self._setup(tmp_path)
        external = tmp_path / "external.png"
        external.write_bytes(b"e")
        ts = FakeTileset(external, name="external.png")
        editor.tileset_widget.tilesets.append(ts)
        editor.on_map_save_selected(target)
        assert editor.tileset_widget.tilesets[2].path == external

    def test_non_sandbox_save_unchanged(self, tmp_path):
        editor, target = self._setup(tmp_path)
        editor.is_sandbox = False
        editor._sandbox_root = None
        editor.on_map_save_selected(target)
        assert target.exists()
        assert editor.is_sandbox is False


class TestAutotileRuleNeighborsTolerance:
    def test_bitmask_neighbors_converted_to_deltas(self):
        from widgets.autotiler import AutotileRule

        rule = AutotileRule.from_dict(
            {"name": "full_solid", "neighbors": [1, 1, 1, 1, 1, 1, 1, 1], "variant_ids": [15], "tileset_index": 0}
        )
        assert rule.neighbors == {
            (-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1),
        }

    def test_bitmask_single_column_maps_to_north_south(self):
        from widgets.autotiler import AutotileRule

        rule = AutotileRule.from_dict(
            {"name": "single_column", "neighbors": [0, 1, 0, 0, 0, 0, 1, 0], "variant_ids": [10], "tileset_index": 0}
        )
        assert rule.neighbors == {(0, -1), (0, 1)}

    def test_pair_neighbors_unchanged(self):
        from widgets.autotiler import AutotileRule

        rule = AutotileRule.from_dict(
            {"name": "r", "neighbors": [[-1, 0], [1, 0]], "variant_ids": [3], "tileset_index": 0}
        )
        assert rule.neighbors == {(-1, 0), (1, 0)}

    def test_empty_neighbors_loads(self):
        from widgets.autotiler import AutotileRule

        rule = AutotileRule.from_dict({"name": "r", "neighbors": [], "variant_ids": [0], "tileset_index": 0})
        assert rule.neighbors == set()

    def test_bad_bitmask_length_raises(self):
        from widgets.autotiler import AutotileRule

        with pytest.raises(ValueError):
            AutotileRule.from_dict({"name": "r", "neighbors": [1, 1, 1], "variant_ids": [0]})


class TestDisplayLoadPath:
    def test_relative_path_inside_cwd(self, tmp_path, monkeypatch):
        from editor import _display_load_path

        monkeypatch.chdir(tmp_path)
        assert _display_load_path(Path("sandbox/map.json")) == Path("sandbox/map.json")

    def test_absolute_path_inside_cwd(self, tmp_path, monkeypatch):
        from editor import _display_load_path

        monkeypatch.chdir(tmp_path)
        assert _display_load_path(tmp_path / "sandbox" / "map.json") == Path("sandbox/map.json")

    def test_path_outside_cwd_returns_raw(self, tmp_path, monkeypatch):
        from editor import _display_load_path

        (tmp_path / "other").mkdir()
        monkeypatch.chdir(tmp_path / "other")
        outside = tmp_path / "sandbox" / "map.json"
        assert _display_load_path(outside) == outside

    def test_regression_relative_path_does_not_raise(self, monkeypatch):
        """The reported crash: relative 'sandbox/map.json' vs absolute cwd."""
        from editor import _display_load_path

        monkeypatch.chdir(Path(__file__).parent.parent)
        assert _display_load_path(Path("sandbox/map.json")) == Path("sandbox/map.json")


class TestNodeSidecarBelongsGuard:
    def _manager(self, data_root: Path, nodes_rel: str = "nodes"):
        from node_manager import NodeManager
        from tilemap import Tilemap

        class _Editor:
            config = {"nodes_path": nodes_rel}

        editor = _Editor()
        editor.data_root = data_root
        editor.tilemap = Tilemap(editor)
        editor.tilemap.init_size((16, 16), (10, 10))
        return NodeManager(editor)

    EMPTY = '{"version": 2, "groups": [], "nodes": []}'

    def test_diverged_active_sidecar_relocates_write_to_canonical(self, tmp_path):
        """Loaded a legacy map-adjacent sidecar, but canonical lives in the
        central nodes dir -> writes go to canonical (relocation accepted);
        the legacy file is left byte-identical."""
        maps_dir = tmp_path / "maps"
        maps_dir.mkdir(parents=True)
        manager = self._manager(tmp_path)
        loaded = maps_dir / "level.json"
        adjacent = maps_dir / "level.nodes.json"
        adjacent.write_text(self.EMPTY)
        manager.load(loaded)
        assert manager._active_sidecar == adjacent

        manager.add_node(manager.create_default_node("Objects"))
        manager.save(loaded)

        canonical = tmp_path / "nodes" / "level.nodes.json"
        assert canonical.is_file(), "canonical must receive the write"
        assert adjacent.read_text() == self.EMPTY, "diverged sidecar stays frozen"

    def test_matching_active_sidecar_is_kept(self, tmp_path):
        maps_dir = tmp_path / "maps"
        maps_dir.mkdir(parents=True)
        # nodes dir == map dir: canonical and adjacent coincide
        manager = self._manager(maps_dir, nodes_rel=".")
        loaded = maps_dir / "level.json"
        adjacent = maps_dir / "level.nodes.json"
        adjacent.write_text(self.EMPTY)
        manager.load(loaded)

        manager.add_node(manager.create_default_node("Objects"))
        manager.save(loaded)

        data = json.loads(adjacent.read_text())
        assert len(data["nodes"]) == 1

    def test_export_reset_sends_writes_to_canonical_not_sandbox(self, tmp_path):
        sandbox_dir = tmp_path / "sandbox"
        sandbox_dir.mkdir(parents=True)
        sandbox_map = sandbox_dir / "level.json"
        sandbox_map.write_text("{}")
        stale = sandbox_dir / "level.nodes.json"
        stale.write_text(self.EMPTY)

        project = tmp_path / "project"
        manager = self._manager(sandbox_dir)
        manager.editor.data_root = sandbox_dir
        manager.load(sandbox_map)
        manager.add_node(manager.create_default_node("Objects"))

        # what the export flow does before save_map(): point data_root back
        # at the project, then clear the sandbox sidecar pointer
        manager.editor.data_root = project
        manager.reset_nodes_dir()
        target = tmp_path / "export" / "level.json"
        target.parent.mkdir(parents=True)
        manager.save(target)

        canonical = project / "nodes" / "level.nodes.json"
        assert canonical.is_file(), "canonical receives the exported nodes"
        assert stale.read_text() == self.EMPTY, "sandbox copy stays frozen"
        assert not (target.parent / "level.nodes.json").exists()

    def test_no_active_uses_canonical_fallback(self, tmp_path):
        manager = self._manager(tmp_path)
        manager.add_node(manager.create_default_node("Objects"))
        target = tmp_path / "maps" / "other.json"
        target.parent.mkdir(parents=True)
        manager.save(target)
        assert (tmp_path / "nodes" / "other.nodes.json").is_file()
