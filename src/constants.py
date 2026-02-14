from pathlib import Path

BASE_PATH = Path(__file__).parent.parent
THEME_PATH = BASE_PATH / "src" / "themes"

MAIN_PANEL_ID = "#main_panel"

INTELLISENSE_DEPTH = 3
IGNORE_DIRS = {".git", "__pycache__", "node_modules", "venv", ".venv", "build", "dist"}
