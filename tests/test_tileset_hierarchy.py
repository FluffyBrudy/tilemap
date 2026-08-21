"""Tileset folder hierarchy persistence + tree rename/delete tests.

Covers:
- tileset_hierarchy store: roundtrip, corrupt/missing fallbacks, sanitization
- TileSelector: placement from hierarchy file, restart survival
- Folder ops: add (auto-rename), F2 rename flow, delete promotes children
- TreeWidget inline rename widget behavior
- LayerSelector rename charset regression (underscores/spaces allowed)
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import json
import sys
from pathlib import Path

import pygame
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.context_dispatch import PropertyContextDispatcher  # noqa: E402
from utils.tileset_hierarchy import (  # noqa: E402
    FolderEntry,
    ItemEntry,
    TilesetHierarchy,
    hierarchy_path,
    load_hierarchy,
    save_hierarchy,
)
from widgets.layer_selector import LayerSelector  # noqa: E402
from widgets.tile_selector import TileSelector, TilesetData  # noqa: E402
from widgets.ui.tree_widget import TreeWidget  # noqa: E402


@pytest.fixture(autouse=True)
def init_pygame():
    pygame.init()
    pygame.display.set_mode((1, 1))
    yield
    pygame.quit()


@pytest.fixture
def data_root(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    return root


def write_hierarchy(root: Path, payload) -> None:
    hierarchy_path(root).write_text(json.dumps(payload), encoding="utf-8")


def read_hierarchy(root: Path) -> dict:
    return json.loads(hierarchy_path(root).read_text(encoding="utf-8"))


def make_surface(w=32, h=32):
    surf = pygame.Surface((w, h))
    surf.fill((120, 120, 160))
    return surf


class FakeTilemap:
    tile_size = (32, 32)


class FakeEditor:
    def __init__(self, data_root=None):
        self.tilemap = FakeTilemap()
        self.context_dispatch = PropertyContextDispatcher()
        self.data_root = data_root


def make_selector(data_root) -> TileSelector:
    return TileSelector(FakeEditor(data_root=data_root), x=0, y=0, w=400, h=600)


def add_tileset(sel: TileSelector, name: str, path: Path) -> str:
    ts = TilesetData(name=name, path=path, surface=make_surface(), tileset_type="tile")
    sel.tilesets.append(ts)
    sel.tileset_map[len(sel.tilesets) - 1] = ts
    sel._sync_tree()
    return ts.uid


def key_event(key, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


# -- store ------------------------------------------------------------------


class TestStore:
    def test_missing_returns_none(self, data_root):
        assert load_hierarchy(data_root) is None

    def test_roundtrip(self, data_root):
        hier = TilesetHierarchy(
            folders=[FolderEntry(id="f_1", name="Terrain")],
            items=[ItemEntry(path="grass.png", folder="f_1")],
        )
        assert save_hierarchy(data_root, hier) is True
        loaded = load_hierarchy(data_root)
        assert loaded is not None
        assert [f.id for f in loaded.folders] == ["f_1"]
        assert loaded.items[0].path == "grass.png"
        assert loaded.items[0].folder == "f_1"

    def test_corrupt_returns_none(self, data_root):
        hierarchy_path(data_root).write_text("{not json!!", encoding="utf-8")
        assert load_hierarchy(data_root) is None

    def test_wrong_version_returns_none(self, data_root):
        write_hierarchy(data_root, {"version": 99, "folders": [], "items": []})
        assert load_hierarchy(data_root) is None

    def test_non_object_root_returns_none(self, data_root):
        hierarchy_path(data_root).write_text("[1, 2]", encoding="utf-8")
        assert load_hierarchy(data_root) is None

    def test_duplicate_folder_ids_deduped(self, data_root):
        write_hierarchy(
            data_root,
            {
                "version": 1,
                "folders": [
                    {"id": "f_1", "name": "A"},
                    {"id": "f_1", "name": "B"},
                ],
                "items": [],
            },
        )
        loaded = load_hierarchy(data_root)
        assert len(loaded.folders) == 1
        assert loaded.folders[0].name == "A"

    def test_unknown_parent_cleared(self, data_root):
        write_hierarchy(
            data_root,
            {
                "version": 1,
                "folders": [{"id": "f_1", "name": "A", "parent": "ghost"}],
                "items": [],
            },
        )
        loaded = load_hierarchy(data_root)
        assert loaded.folders[0].parent is None

    def test_parent_cycle_broken(self, data_root):
        write_hierarchy(
            data_root,
            {
                "version": 1,
                "folders": [
                    {"id": "a", "name": "A", "parent": "b"},
                    {"id": "b", "name": "B", "parent": "a"},
                ],
                "items": [],
            },
        )
        loaded = load_hierarchy(data_root)
        # invariant: every parent chain terminates (no cycles survive)
        for f in loaded.folders:
            seen = {f.id}
            cur = f.parent
            while cur is not None:
                assert cur not in seen
                seen.add(cur)
                entry = loaded.folder_by_id(cur)
                assert entry is not None
                cur = entry.parent

    def test_duplicate_item_paths_deduped(self, data_root):
        write_hierarchy(
            data_root,
            {
                "version": 1,
                "folders": [],
                "items": [
                    {"path": "x.png", "folder": None},
                    {"path": "x.png", "folder": "f_1"},
                ],
            },
        )
        loaded = load_hierarchy(data_root)
        assert len(loaded.items) == 1
        assert loaded.items[0].folder is None

    def test_next_folder_id(self):
        hier = TilesetHierarchy(folders=[FolderEntry(id="f_3", name="x")])
        assert hier.next_folder_id() == "f_4"
        assert TilesetHierarchy().next_folder_id() == "f_1"


# -- selector placement ------------------------------------------------------


class TestSelectorPlacement:
    def test_tileset_placed_into_folder_from_file(self, data_root):
        write_hierarchy(
            data_root,
            {
                "version": 1,
                "folders": [{"id": "f_1", "name": "Terrain"}],
                "items": [{"path": "grass.png", "folder": "f_1"}],
            },
        )
        sel = make_selector(data_root)
        uid = add_tileset(sel, "grass", data_root / "grass.png")
        node = sel._tree.find_node(uid)
        assert node.parent is not None and node.parent.id == "f_1"

    def test_unmatched_tileset_at_root(self, data_root):
        write_hierarchy(
            data_root,
            {
                "version": 1,
                "folders": [{"id": "f_1", "name": "Terrain"}],
                "items": [{"path": "grass.png", "folder": "f_1"}],
            },
        )
        sel = make_selector(data_root)
        uid = add_tileset(sel, "stone", data_root / "stone.png")
        node = sel._tree.find_node(uid)
        assert node.parent is None

    def test_streaming_syncs_keep_placing(self, data_root):
        write_hierarchy(
            data_root,
            {
                "version": 1,
                "folders": [{"id": "f_1", "name": "Terrain"}],
                "items": [
                    {"path": "a.png", "folder": "f_1"},
                    {"path": "b.png", "folder": "f_1"},
                ],
            },
        )
        sel = make_selector(data_root)
        uid_a = add_tileset(sel, "a", data_root / "a.png")
        uid_b = add_tileset(sel, "b", data_root / "b.png")
        folder = sel._tree.find_node("f_1")
        assert [c.id for c in folder.children] == [uid_a, uid_b]

    def test_restart_preserves_folders(self, data_root):
        sel1 = make_selector(data_root)
        add_tileset(sel1, "a", data_root / "a.png")
        uid_b = add_tileset(sel1, "b", data_root / "b.png")
        sel1._add_folder()
        fid = next(n.id for n in sel1._tree.roots if n.is_folder)
        sel1._tree.cancel_rename()
        node_b = sel1._tree.find_node(uid_b)
        while node_b in sel1._tree.roots:
            sel1._tree.roots.remove(node_b)
        sel1._tree.find_node(fid).add_child(node_b)
        sel1._save_hierarchy()

        sel2 = make_selector(data_root)
        add_tileset(sel2, "a", data_root / "a.png")
        add_tileset(sel2, "b", data_root / "b.png")
        folder = sel2._tree.find_node(fid)
        assert folder is not None and folder.label.startswith("Folder")
        assert [c.label for c in folder.children] == ["b"]


# -- folder operations --------------------------------------------------------


class TestFolderOps:
    def test_add_folder_saves_and_starts_rename(self, data_root):
        sel = make_selector(data_root)
        add_tileset(sel, "a", data_root / "a.png")
        sel._add_folder()
        fid = next(n.id for n in sel._tree.roots if n.is_folder)
        assert sel._tree._rename_id == fid
        saved = read_hierarchy(data_root)
        assert saved["folders"][0]["id"] == fid

    def test_f2_rename_flow_persists(self, data_root):
        sel = make_selector(data_root)
        add_tileset(sel, "a", data_root / "a.png")
        sel._add_folder()
        fid = next(n.id for n in sel._tree.roots if n.is_folder)
        sel._tree.cancel_rename()
        sel._tree.selected_ids = {fid}

        assert sel.handle_event(key_event(pygame.K_F2)) is True
        for ch in "Terrain":
            key = getattr(pygame, f"K_{ch}", pygame.K_UNKNOWN)
            sel.handle_event(key_event(key, ch))
        sel.handle_event(key_event(pygame.K_RETURN))

        assert sel._tree.find_node(fid).label == "Terrain"
        assert read_hierarchy(data_root)["folders"][0]["name"] == "Terrain"

    def test_rename_allows_spaces_and_underscores(self, data_root):
        sel = make_selector(data_root)
        sel._add_folder()
        fid = next(n.id for n in sel._tree.roots if n.is_folder)
        sel._tree.cancel_rename()
        sel._tree.selected_ids = {fid}
        sel.handle_event(key_event(pygame.K_F2))
        for ch in "my_tiles ":
            sel.handle_event(key_event(pygame.K_UNKNOWN, ch))
        sel.handle_event(key_event(pygame.K_RETURN))
        assert sel._tree.find_node(fid).label == "my_tiles"

    def test_delete_promotes_children_to_root(self, data_root):
        sel = make_selector(data_root)
        uid = add_tileset(sel, "a", data_root / "a.png")
        sel._add_folder()
        fid = next(n.id for n in sel._tree.roots if n.is_folder)
        sel._tree.cancel_rename()
        node = sel._tree.find_node(uid)
        while node in sel._tree.roots:
            sel._tree.roots.remove(node)
        sel._tree.find_node(fid).add_child(node)

        sel.handle_event(key_event(pygame.K_DELETE))

        promoted = sel._tree.find_node(uid)
        assert promoted.parent is None and promoted in sel._tree.roots
        assert sel._tree.find_node(fid) is None
        saved = read_hierarchy(data_root)
        assert saved["folders"] == []
        assert saved["items"] == [{"path": "a.png", "folder": None}]

    def test_delete_key_ignores_tileset_selection(self, data_root):
        sel = make_selector(data_root)
        uid = add_tileset(sel, "a", data_root / "a.png")
        sel._add_folder()
        sel._tree.cancel_rename()
        sel._tree.selected_ids = {uid}
        sel.handle_event(key_event(pygame.K_DELETE))
        assert sel._tree.find_node(uid) is not None


# -- tree widget rename -------------------------------------------------------


class TestTreeRenameWidget:
    def _tree_with_folder(self):
        tree = TreeWidget(pygame.Rect(0, 0, 140, 400))

        class N:
            pass

        tree.set_data([])
        return tree

    def test_begin_rename_unknown_id(self):
        tree = self._tree_with_folder()
        assert tree.begin_rename("nope") is False

    def test_commit_updates_label_and_callback(self):
        tree = self._tree_with_folder()
        committed = []
        tree.on_rename_committed = lambda nid, label: committed.append((nid, label))
        from widgets.ui.tree_widget import TreeNode

        tree.set_data([TreeNode(id="f_1", label="Old", is_folder=True)])
        assert tree.begin_rename("f_1") is True
        tree._rename_input.insert_text("New")
        tree.handle_event(key_event(pygame.K_RETURN))
        assert tree.find_node("f_1").label == "New"
        assert committed == [("f_1", "New")]

    def test_empty_label_keeps_old(self):
        tree = self._tree_with_folder()
        from widgets.ui.tree_widget import TreeNode

        tree.set_data([TreeNode(id="f_1", label="Old", is_folder=True)])
        tree.begin_rename("f_1")
        tree._rename_input.text = ""
        tree.handle_event(key_event(pygame.K_RETURN))
        assert tree.find_node("f_1").label == "Old"

    def test_escape_cancels(self):
        tree = self._tree_with_folder()
        from widgets.ui.tree_widget import TreeNode

        tree.set_data([TreeNode(id="f_1", label="Old", is_folder=True)])
        tree.begin_rename("f_1")
        tree._rename_input.insert_text("Changed")
        tree.handle_event(key_event(pygame.K_ESCAPE))
        assert tree.find_node("f_1").label == "Old"
        assert tree._rename_id is None


# -- layer selector rename charset regression ---------------------------------


class TestLayerRenameCharset:
    class FakeLayer:
        def __init__(self, name):
            self.name = name
            self.opacity = 1.0
            self.y_sort = False

    class FakeLayerManager:
        def __init__(self, layers):
            self.layers = layers
            self.active_layer_idx = 0

        def get_layer(self, idx):
            if 0 <= idx < len(self.layers):
                return self.layers[idx]
            return None

    class FakeTM:
        def __init__(self, lm):
            self.layer_manager = lm

    class FakeEd:
        def __init__(self, lm):
            self.tilemap = TestLayerRenameCharset.FakeTM(lm)
            self.context_dispatch = PropertyContextDispatcher()

    def test_underscore_and_space_accepted(self):
        lm = self.FakeLayerManager([self.FakeLayer("base")])
        ls = LayerSelector(self.FakeEd(lm), 0, 0, 200, 400)
        ls._start_rename(0)
        for ch in "my_layer 2":
            ls.handle_event(key_event(pygame.K_UNKNOWN, ch))
        ls.handle_event(key_event(pygame.K_RETURN))
        assert lm.layers[0].name == "my_layer 2"

    def test_escape_cancels(self):
        lm = self.FakeLayerManager([self.FakeLayer("base")])
        ls = LayerSelector(self.FakeEd(lm), 0, 0, 200, 400)
        ls._start_rename(0)
        ls.handle_event(key_event(pygame.K_UNKNOWN, "x"))
        ls.handle_event(key_event(pygame.K_ESCAPE))
        assert lm.layers[0].name == "base"

    def test_empty_name_rejected(self):
        lm = self.FakeLayerManager([self.FakeLayer("base")])
        ls = LayerSelector(self.FakeEd(lm), 0, 0, 200, 400)
        ls._start_rename(0)
        ls.rename_input.text = ""
        ls.handle_event(key_event(pygame.K_RETURN))
        assert lm.layers[0].name == "base"
