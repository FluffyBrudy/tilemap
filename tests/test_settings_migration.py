"""Settings migration: old settings.json files gain current defaults."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_missing_themes_list_gets_builtin(monkeypatch, tmp_path):
    from editor import _load_project_config
    from tilemap_editor.settings import BUILTIN_THEMES

    assert "monokai" in BUILTIN_THEMES
    (tmp_path / "settings.json").write_text(json.dumps({
        "base_path": str(tmp_path),
        "data_path": "data",
        "error_handler": {},
    }))
    (tmp_path / "data").mkdir()
    monkeypatch.chdir(tmp_path)
    _, _, config = _load_project_config()
    assert config["themes_list"] == list(BUILTIN_THEMES)
    assert "monokai" in config["themes_list"]
    # written back for next launch
    disk = json.loads((tmp_path / "settings.json").read_text())
    assert disk["themes_list"] == list(BUILTIN_THEMES)
