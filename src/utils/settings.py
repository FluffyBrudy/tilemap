"""
Settings management system for tilemap editor.

Provides centralized configuration management with JSON persistence
and user-customizable settings.
"""

import json
from typing import Any, Dict
from constants import BASE_PATH


class Settings:
    """Settings manager with JSON persistence and defaults."""
    
    _instance = None
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize settings with defaults and load from file."""
        if self._initialized:
            return
            
        self.settings_file = BASE_PATH / "data" / "settings.json"
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Default settings
        self._defaults = {
            "error_handler": {
                "log_path": "data/logs/errors.log",
                "max_recent_errors": 50,
                "console_output": True,
                "file_logging": True,
                "severity_levels": ["error", "warning", "info"]
            },
            "editor": {
                "default_window_size": "1500x900",
                "default_fps": 60,
                "auto_save": False,
                "auto_save_interval": 300  # seconds
            },
            "paths": {
                "default_tileset_dir": "data/tilesets",
                "default_map_dir": "data/maps",
                "default_project_dir": "data/projects"
            }
        }
        
        self._settings: Dict[str, Any] = {}
        self.load_settings()
        self._initialized = True
    
    def load_settings(self) -> None:
        """Load settings from JSON file with fallback to defaults."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults (deep merge for nested dicts)
                    self._settings = self._deep_merge(self._defaults, loaded_settings)
            else:
                self._settings = self._defaults.copy()
                self.save_settings()  # Create initial settings file
        except Exception as e:
            # If settings file is corrupted, use defaults
            self._settings = self._defaults.copy()
            print(f"Warning: Failed to load settings, using defaults: {e}")
    
    def save_settings(self) -> None:
        """Save current settings to JSON file."""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save settings: {e}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get setting value by dot-separated key path.
        
        Args:
            key_path: Dot-separated path (e.g., "error_handler.log_path")
            default: Default value if key not found
        """
        keys = key_path.split('.')
        value = self._settings
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set setting value by dot-separated key path.
        
        Args:
            key_path: Dot-separated path (e.g., "error_handler.log_path")
            value: Value to set
        """
        keys = key_path.split('.')
        target = self._settings
        
        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        
        # Set the final value
        target[keys[-1]] = value
        self.save_settings()
    
    def get_all(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        return self._settings.copy()
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = self._defaults.copy()
        self.save_settings()
    
    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result


# Global settings instance
settings = Settings()
