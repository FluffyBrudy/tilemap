import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.project_paths import to_project_path, resolve_project_path
from tilemap_editor.settings import init_settings


@pytest.fixture
def tmp_base():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def tmp_with_file(tmp_base):
    target = tmp_base / "subdir" / "file.png"
    target.parent.mkdir(parents=True)
    target.touch()
    return tmp_base, target


class TestToProjectPath:
    def test_relative_to_base(self, tmp_with_file):
        base, target = tmp_with_file
        assert to_project_path(target, base) == "subdir/file.png"

    def test_absolute_input(self, tmp_base):
        target = tmp_base / "file.png"
        target.touch()
        assert to_project_path(str(target), tmp_base) == "file.png"

    def test_outside_base_directory(self, tmp_base):
        base = tmp_base / "project"
        base.mkdir()
        outside = tmp_base / "outside" / "file.png"
        outside.parent.mkdir(parents=True)
        outside.touch()

        result = to_project_path(outside, base)
        assert ".." in result


class TestResolveProjectPath:
    def test_resolves_relative_to_base(self, tmp_base):
        target = tmp_base / "subdir" / "file.png"
        target.parent.mkdir(parents=True)
        target.touch()

        result = resolve_project_path("subdir/file.png", tmp_base, must_exist=True)
        assert result == target.resolve()

    def test_resolves_via_fallback(self, tmp_base):
        base = tmp_base / "project"
        base.mkdir()
        fallback = tmp_base / "maps"
        fallback.mkdir()
        target = fallback / "assets" / "file.png"
        target.parent.mkdir(parents=True)
        target.touch()

        stored = "assets/file.png"
        result = resolve_project_path(stored, base, fallback_roots=[fallback], must_exist=True)
        assert result == target.resolve()

    def test_returns_first_candidate_when_not_exist(self, tmp_base):
        stored = "nonexistent/file.png"
        result = resolve_project_path(stored, tmp_base)
        assert result == (tmp_base / stored).resolve()


class TestInitSettings:
    def test_creates_settings_json_and_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            orig_cwd = Path.cwd()
            os.chdir(str(tmp_path))
            try:
                with mock.patch("builtins.input", return_value=str(tmp_path)):
                    init_settings()

                settings_file = tmp_path / "settings.json"
                assert settings_file.exists()

                with open(settings_file) as f:
                    cfg = json.load(f)
                assert cfg["base_path"] == str(tmp_path)
                assert cfg["data_path"] == "data"

                data_dir = tmp_path / "data"
                assert data_dir.is_dir()
            finally:
                os.chdir(str(orig_cwd))

    def test_uses_current_dir_as_default_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            orig_cwd = Path.cwd()
            os.chdir(str(tmp_path))
            try:
                with mock.patch("builtins.input", return_value=""):
                    init_settings()

                settings_file = tmp_path / "settings.json"
                assert settings_file.exists()

                with open(settings_file) as f:
                    cfg = json.load(f)
                assert Path(cfg["base_path"]).resolve() == tmp_path
            finally:
                os.chdir(str(orig_cwd))

    def test_aborts_if_settings_already_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            (tmp_path / "settings.json").touch()
            orig_cwd = Path.cwd()
            os.chdir(str(tmp_path))
            try:
                with mock.patch("builtins.input", return_value=str(tmp_path)):
                    with pytest.raises(RuntimeError, match="already exists"):
                        init_settings()
            finally:
                os.chdir(str(orig_cwd))

    def test_creates_main_file_when_flag_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp).resolve()
            orig_cwd = Path.cwd()
            os.chdir(str(tmp_path))
            try:
                with mock.patch("builtins.input", return_value=str(tmp_path)):
                    init_settings(generate_main=True)

                src_main = tmp_path / "src" / "main.py"
                assert src_main.exists()
            finally:
                os.chdir(str(orig_cwd))
