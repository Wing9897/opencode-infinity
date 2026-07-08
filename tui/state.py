"""Persist UI preferences (replaces browser localStorage)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import opencode_infinity as core


def _state_path() -> Path:
    return core._get_user_config_dir() / "ui-state.json"


def load_state() -> dict[str, Any]:
    path = _state_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(data: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_locale() -> str:
    return str(load_state().get("locale", "en"))


def set_locale(locale: str) -> None:
    data = load_state()
    data["locale"] = locale
    save_state(data)


def get_selected_config() -> str:
    return str(load_state().get("selected_config", ""))


def set_selected_config(name: str) -> None:
    data = load_state()
    data["selected_config"] = name
    save_state(data)


def get_working_dir_override(config_name: str) -> str:
    overrides = load_state().get("working_dir_overrides", {})
    if isinstance(overrides, dict):
        return str(overrides.get(config_name, ""))
    return ""


def set_working_dir_override(config_name: str, value: str) -> None:
    data = load_state()
    overrides = data.get("working_dir_overrides")
    if not isinstance(overrides, dict):
        overrides = {}
    if value:
        overrides[config_name] = value
    else:
        overrides.pop(config_name, None)
    data["working_dir_overrides"] = overrides
    save_state(data)


def get_log_compact() -> bool:
    return bool(load_state().get("log_compact", False))


def set_log_compact(compact: bool) -> None:
    data = load_state()
    data["log_compact"] = compact
    save_state(data)


UI_DENSITIES = ("compact", "normal", "comfortable")


def get_ui_density() -> str:
    value = str(load_state().get("ui_density", "compact"))
    return value if value in UI_DENSITIES else "compact"


def set_ui_density(density: str) -> None:
    if density not in UI_DENSITIES:
        return
    data = load_state()
    data["ui_density"] = density
    save_state(data)
