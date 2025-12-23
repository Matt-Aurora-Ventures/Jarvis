import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "lifeos" / "config"
BASE_CONFIG = CONFIG_DIR / "lifeos.config.json"
LOCAL_CONFIG = CONFIG_DIR / "lifeos.config.local.json"


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
        return {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> Dict[str, Any]:
    base = _load_json(BASE_CONFIG)
    local = _load_json(LOCAL_CONFIG)
    if local:
        return _deep_merge(base, local)
    return base


def resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        return (ROOT / path).resolve()
    return path
