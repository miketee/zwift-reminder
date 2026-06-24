"""
common.py

Shared helpers for loading config and resolving the Zwift log path.
Imported by watcher.py (and anything else that needs config or paths).
"""

import json
import os
from pathlib import Path

# config.json sits in the project root, one level above src/
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

DEFAULTS = {
    "checklist": [
        "Water bottle",
        "Towel",
        "Fan on",
        "Correct frame & wheels for this race",
    ],
    "reminder_threshold_seconds": 30,
    "popup_auto_close_seconds": 10,
    "log_path": "",
}


def load_config() -> dict:
    """
    Loads config.json from the project root. Missing keys fall back to
    DEFAULTS, so a partial or empty config.json is always safe.
    """
    config = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        config.update(user_config)
    except FileNotFoundError:
        pass  # No config.json — all defaults, which is fine
    except json.JSONDecodeError as e:
        # Bad JSON is worth surfacing; caller's log() will catch this
        raise ValueError(f"config.json is not valid JSON: {e}") from e
    return config


def get_zwift_log_path(config: dict) -> Path:
    """
    Returns the path to Zwift's Log.txt.

    Priority:
      1. config["log_path"] if non-empty (user override for non-standard installs)
      2. %LOCALAPPDATA%\\Zwift\\Logs\\Log.txt  (confirmed default as of 2026)
    """
    override = (config.get("log_path") or "").strip()
    if override:
        return Path(override)

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        raise EnvironmentError(
            "%LOCALAPPDATA% is not set. Cannot locate Zwift's Log.txt. "
            "Set 'log_path' in config.json to the full path of your Log.txt."
        )

    return Path(local_app_data) / "Zwift" / "Logs" / "Log.txt"