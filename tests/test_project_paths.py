import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.project_paths import to_project_path, resolve_project_path


class TestToProjectPath:
    def test_relative_to_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "subdir" / "file.png"
            target.parent.mkdir(parents=True)
            target.touch()

            result = to_project_path(target, base)
            assert result == "subdir/file.png"

    def test_absolute_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "file.png"
            target.touch()

            result = to_project_path(str(target), base)
            assert result == "file.png"

    def test_outside_base_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "project"
            base.mkdir()
            outside = Path(tmp) / "outside" / "file.png"
            outside.parent.mkdir(parents=True)
            outside.touch()

            result = to_project_path(outside, base)
            assert ".." in result


class TestResolveProjectPath:
    def test_resolves_relative_to_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "subdir" / "file.png"
            target.parent.mkdir(parents=True)
            target.touch()

            stored = "subdir/file.png"
            result = resolve_project_path(stored, base, must_exist=True)
            assert result == target.resolve()

    def test_resolves_via_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "project"
            base.mkdir()
            fallback = Path(tmp) / "maps"
            fallback.mkdir()
            target = fallback / "assets" / "file.png"
            target.parent.mkdir(parents=True)
            target.touch()

            stored = "assets/file.png"
            result = resolve_project_path(stored, base, fallback_roots=[fallback], must_exist=True)
            assert result == target.resolve()

    def test_returns_first_candidate_when_not_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            stored = "nonexistent/file.png"
            result = resolve_project_path(stored, base)
            assert result == (base / stored).resolve()
