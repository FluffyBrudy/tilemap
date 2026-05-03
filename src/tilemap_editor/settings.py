import json
import sys
from pathlib import Path


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