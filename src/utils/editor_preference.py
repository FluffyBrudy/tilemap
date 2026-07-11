"""
Editor preferences loader.

Loads settings from settings.json in current working directory.
No defaults, no auto-creation - settings.json is the single source of truth.
"""

import json
from pathlib import Path
from typing import Dict, Any


def load_settings() -> Dict[str, Any]:
    """
    Load settings.json from current working directory.

    Returns:
        Dictionary containing full settings configuration.

    Raises:
        RuntimeError: If settings.json is not found in cwd.
    """
    settings_file = Path.cwd() / "settings.json"

    if not settings_file.exists():
        raise RuntimeError("settings.json not found. Run 'tilemap-editor init' first.")

    with open(settings_file, "r", encoding="utf-8") as f:
        return json.load(f)


__all__ = ["load_settings"]
