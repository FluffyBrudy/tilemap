import sys
from pathlib import Path

# Handle PyInstaller bundled execution
# When frozen (built with PyInstaller), sys._MEIPASS contains the temp directory
# where bundled files are extracted. Otherwise, use the normal project structure.
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # Running as compiled executable
    BASE_PATH = Path(sys._MEIPASS)
else:
    # Running as script
    BASE_PATH = Path(__file__).parent.parent
THEME_PATH = BASE_PATH / "src" / "themes"

MAIN_PANEL_ID = "#main_panel"

INTELLISENSE_DEPTH = 3
IGNORE_DIRS = {".git", "__pycache__", "node_modules", "venv", ".venv", "build", "dist"}
MAX_LOG_FILES = 20
