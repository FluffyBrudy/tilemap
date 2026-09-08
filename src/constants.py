import sys
from pathlib import Path

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_PATH = Path(sys._MEIPASS)
else:
    BASE_PATH = Path(__file__).parent.parent
THEME_PATH = BASE_PATH / "src" / "themes"

MAIN_PANEL_ID = "#main_panel"

INTELLISENSE_DEPTH = 3
IGNORE_DIRS = {".git", "__pycache__", "node_modules", "venv", ".venv", "build", "dist"}
MAX_LOG_FILES = 20

SPRITESHEET_THRESHOLD_WIDTH = 800
SPRITESHEET_THRESHOLD_HEIGHT = 600
