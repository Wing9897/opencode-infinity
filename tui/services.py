"""Service layer: direct Python calls replacing Flask /api routes."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

import yaml

import opencode_infinity as core

from tui import i18n


class ServiceError(Exception):
    """User-facing service error."""


def list_configs() -> list[str]:
    configs_dir = core.get_tasks_config_dir()
    if not configs_dir.is_dir():
        return []
    return sorted(
        f.name for f in configs_dir.iterdir() if f.suffix in (".yaml", ".yml")
    )


def create_templates() -> dict[str, Any]:
    return core._create_factory_templates(core.get_tasks_config_dir())


def read_config(name: str) -> dict[str, Any]:
    try:
        target = core._config_file_path(name)
    except core.ConfigError as exc:
        raise ServiceError(str(exc)) from exc
    if not target.is_file():
        raise ServiceError(i18n.t("err_file_not_found"))
    try:
        content = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise ServiceError(i18n.t("err_read_failed", error=exc)) from exc
    working_dir = ""
    try:
        config = core.ConfigLoader(target).load()
        working_dir = config.execution.working_dir
    except (core.ConfigError, OSError, ValueError):
        pass
    return {"content": content, "working_dir": working_dir, "path": str(target)}


def save_config(filename: str, content: str) -> str:
    try:
        target = core._config_file_path(filename)
    except core.ConfigError as exc:
        raise ServiceError(str(exc)) from exc
    try:
        core._load_yaml_mapping_from_text(
            content, source=f"TUI save payload: {filename}"
        )
    except core.ConfigError as exc:
        raise ServiceError(i18n.t("err_yaml_invalid", error=exc)) from exc
    configs_dir = core.get_tasks_config_dir()
    configs_dir.mkdir(parents=True, exist_ok=True)
    try:
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ServiceError(i18n.t("err_write_failed", error=exc)) from exc
    return str(target)


def generate_yaml(config: dict[str, Any]) -> str:
    try:
        return yaml.dump(
            config, default_flow_style=False, allow_unicode=True, sort_keys=False
        )
    except (TypeError, ValueError, yaml.YAMLError) as exc:
        raise ServiceError(str(exc)) from exc


def parse_yaml(content: str) -> dict[str, Any]:
    try:
        parsed = core._load_yaml_mapping_from_text(content, source="TUI parse payload")
    except core.ConfigError as exc:
        raise ServiceError(i18n.t("err_yaml_parse_failed", error=exc)) from exc
    keys = list(parsed.keys())
    if len(keys) == 1 and isinstance(parsed[keys[0]], dict):
        inner = parsed[keys[0]]
        if any(k in inner for k in ("cli", "execution", "prompts")):
            parsed = inner
    return parsed


def get_diagnose() -> dict[str, Any]:
    return core._build_diagnose_report()


def get_status_payload(
    *,
    running: bool,
    round_count: int,
    session_count: int,
    config_name: str,
    session_id: str,
    working_dir: str,
    start_time: float,
) -> dict[str, Any]:
    build_info = core._app_build_info()
    elapsed_seconds = (
        time.monotonic() - start_time if start_time > 0 and running else 0.0
    )
    minutes = int(elapsed_seconds) // 60
    seconds = int(elapsed_seconds) % 60
    return {
        "running": running,
        "round_count": round_count,
        "session_count": session_count,
        "config_name": config_name,
        "session_id": session_id,
        "working_dir": working_dir,
        "app_version": build_info["version"],
        "build_mode": build_info["mode"],
        "self_check": core._runtime_self_check(),
        "elapsed": f"{minutes}:{seconds:02d}",
        "elapsed_seconds": elapsed_seconds,
    }


def prepare_start(
    config_name: str,
    session_id: str,
    working_dir_override: str,
) -> tuple[str, Optional[Path]]:
    if not config_name:
        raise ServiceError(i18n.t("err_no_config"))
    session_id = session_id.strip()
    working_dir_override = core._normalize_working_dir_text(working_dir_override)
    if session_id and not core._validate_session_id(session_id):
        raise ServiceError(i18n.t("err_session_id_invalid"))
    try:
        config_path = core._resolve_config_path(config_name)
    except core.ConfigError as exc:
        raise ServiceError(str(exc)) from exc
    if not config_path.is_file():
        raise ServiceError(i18n.t("err_config_not_found", name=config_name))
    try:
        config = core.ConfigLoader(config_path).load()
        resolved_working_dir = core._resolve_execution_working_dir(
            config, override=working_dir_override or None
        )
    except (core.ConfigError, OSError, ValueError) as exc:
        raise ServiceError(str(exc)) from exc
    if not session_id:
        session_id = f"ses_{int(time.time())}"
    return session_id, resolved_working_dir
