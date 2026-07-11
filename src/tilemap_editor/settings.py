import json
import sys
from pathlib import Path
from typing import Optional


def init_settings(generate_main: bool = False) -> None:
    print("Initialize Tilemap Editor Project")

    user_input = input("Enter base path (default: .): ").strip() or "."
    base_path = Path(user_input).expanduser()

    if not base_path.is_absolute():
        base_path = base_path.resolve()

    venv_path = Path(sys.prefix).resolve()
    if venv_path in base_path.parents:
        raise RuntimeError("base_path cannot be inside virtual environment")

    settings = {
        "base_path": str(base_path.resolve()),
        "data_path": "data",
        "collision_paths": {
            "tileset": "collision",
            "character": "character_collision"
        },
        "nodes_path": "nodes",
        "theme": "dark",
        "themes_list": ["dark", "molokai", "light", "semi_light"],
        "error_handler": {
            "log_path": "errors.log",
            "max_recent_errors": 50,
            "console_output": True,
            "file_logging": True,
            "severity_levels": ["error", "warning", "info"]
        }
    }

    settings_file = Path.cwd() / "settings.json"

    if settings_file.exists():
        raise RuntimeError("settings.json already exists. Aborting.")

    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=4)

    print(f"Created settings.json at {settings_file}")

    data_dir = base_path / settings["data_path"]
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created data directory: {data_dir}")

    if generate_main:
        generate_main_file()


def generate_main_file() -> None:
    src_dir = Path.cwd() / "src"
    src_dir.mkdir(exist_ok=True)

    main_file = src_dir / "main.py"

    if main_file.exists():
        raise RuntimeError("src/main.py already exists. Aborting.")

    boilerplate = """def main():
    print("Start your game/editor here")


if __name__ == "__main__":
    main()
"""

    with open(main_file, "w") as f:
        f.write(boilerplate)

    print(f"Created {main_file}")


def update_settings(path: Optional[str] = None) -> None:
    """Update base_path in an existing settings.json to the current device path.

    If no path is given, resolves the current working directory to an absolute
    path and writes it as base_path. This makes settings.json portable when
    shared across devices — run update on each device to fix the path.

    Args:
        path: Optional explicit base_path to write (e.g. --path /home/user/project)
    """
    settings_file = Path.cwd() / "settings.json"

    if not settings_file.exists():
        raise RuntimeError(
            "settings.json not found. Run 'tilemap-editor init' first."
        )

    with open(settings_file, "r") as f:
        config = json.load(f)

    if path is not None:
        new_base = str(Path(path).expanduser().resolve())
    else:
        new_base = str(Path.cwd().resolve())

    config["base_path"] = new_base

    with open(settings_file, "w") as f:
        json.dump(config, f, indent=4)

    print(f"Updated base_path to '{new_base}' in {settings_file}")