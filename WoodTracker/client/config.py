import json
import os
from pathlib import Path

APP_NAME = "WoodTracker"

def get_appdata_dir():
    base = Path(os.environ.get("APPDATA", Path.home()))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

CONFIG_FILE = get_appdata_dir() / "config.json"

def load_config():
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

def save_config(cfg: dict):
    CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2),
        encoding="utf-8",
    )

def get_sheet_id():
    return load_config().get("sheet_id")

def set_sheet_id(sheet_id: str):
    cfg = load_config()
    cfg["sheet_id"] = sheet_id
    save_config(cfg)

def get_wow_addon_dir():
    return load_config().get("wow_addon_dir")

def set_wow_addon_dir(path: str):
    cfg = load_config()
    cfg["wow_addon_dir"] = path
    save_config(cfg)

