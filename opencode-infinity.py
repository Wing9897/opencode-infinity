#!/usr/bin/env python3
"""OpenCode Infinity - 單一檔案版本.

自動化 AI 編碼工具的無限循環執行器，支援 OpenCode、Claude Code、Codex、Copilot。
"""
from __future__ import annotations

# =============================================================================
# 標準庫 imports
# =============================================================================
import ctypes
import json
import logging
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import FrameType
from typing import Any, ClassVar, Optional

# =============================================================================
# 第三方 imports
# =============================================================================
import yaml

# =============================================================================
# 工具函數
# =============================================================================


def clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a numeric value to an inclusive range."""
    return max(minimum, min(value, maximum))


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to a maximum display length."""
    if len(text) <= max_length:
        return text
    if max_length <= len(suffix):
        return suffix[:max_length]
    return text[: max_length - len(suffix)] + suffix


def utc_now_iso(timespec: str = "seconds") -> str:
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat(timespec=timespec)


def normalize_newlines(text: str) -> str:
    """Normalize mixed newline styles to \\n."""
    if "\r" not in text:
        return text
    return text.replace("\r\n", "\n").replace("\r", "\n")


def safe_int(value: object, default: int, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    """Convert a value to int with range validation and safe fallback."""
    try:
        converted = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None and converted < minimum:
        return default
    if maximum is not None and converted > maximum:
        return default
    return converted


def compact_strings(items: Iterable[Optional[str]], *, strip: bool = True, drop_empty: bool = True) -> list[str]:
    """Normalize a string sequence by removing None and blanks."""
    result: list[str] = []
    for item in items:
        if item is None:
            continue
        normalized = item.strip() if strip else item
        if drop_empty and normalized == "":
            continue
        result.append(normalized)
    return result


def flatten_dict(mapping: Mapping[str, object], *, separator: str = ".", prefix: str = "") -> dict[str, object]:
    """Flatten nested dictionaries into a single-level dotted-key mapping."""
    flattened: dict[str, object] = {}
    stack: list[tuple[str, Mapping[str, object]]] = [(prefix, mapping)]
    while stack:
        current_prefix, current_mapping = stack.pop()
        for key, value in current_mapping.items():
            full_key = f"{current_prefix}{separator}{key}" if current_prefix else key
            if isinstance(value, Mapping):
                stack.append((full_key, value))
            else:
                flattened[full_key] = value
    return flattened


def diff_mapping(before: Mapping[str, object], after: Mapping[str, object], *, separator: str = ".") -> dict[str, tuple[object, object]]:
    """Return flattened key-level differences between two mappings."""
    before_flat = flatten_dict(dict(before), separator=separator)
    after_flat = flatten_dict(dict(after), separator=separator)
    return {
        key: (before_flat.get(key), after_flat.get(key))
        for key in sorted(before_flat.keys() | after_flat.keys())
        if before_flat.get(key) != after_flat.get(key)
    }


# =============================================================================
# 資料模型 (models)
# =============================================================================


@dataclass(frozen=True)
class TaskConfig:
    """Task-level configuration."""
    name: str = "通用任務"
    description: str = ""
    language: str = "繁體中文"
    output_dir: str = "output"


@dataclass(frozen=True)
class CLIConfig:
    """CLI tool configuration."""
    tool: str = "opencode"
    commands: dict[str, Any] = field(default_factory=dict)
    full_auto: bool = False
    model: Optional[str] = None
    search: bool = False
    allowed_tools: Optional[str] = None
    permission_mode: Optional[str] = None
    mcp_server: Optional[str] = None


@dataclass(frozen=True)
class OpenCodeConfig:
    """OpenCode-specific configuration."""
    model: str = "default"
    max_tokens: int = 128000
    token_threshold: float = 0.7


@dataclass(frozen=True)
class ExecutionConfig:
    """Execution parameters configuration."""
    delay: int = 1
    timeout: int = 300
    max_retries: int = 5
    auto_continue_on_error: bool = True
    max_rounds: int = 0  # 0 = unlimited (controls when to STOP)
    switch_after_rounds: int = 0  # 0 = no switch (controls when to SWITCH session)
    switch_strategy: str = "auto"  # auto, token, rounds


@dataclass(frozen=True)
class DisplayConfig:
    """Display settings configuration."""
    show_session_id: bool = True
    show_token_usage: bool = True
    show_timestamp: bool = True


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration combining all sections."""
    task: TaskConfig = field(default_factory=TaskConfig)
    cli: CLIConfig = field(default_factory=CLIConfig)
    opencode: OpenCodeConfig = field(default_factory=OpenCodeConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    prompts: list[str] = field(default_factory=lambda: ["繼續工作"])
    summary_prompt: str = "總結本輪工作（300字內）"


@dataclass
class SanitizeResult:
    """Result of input sanitization check."""
    is_safe: bool
    sanitized_text: str = ""
    rejection_reason: str = ""


@dataclass
class RetryError:
    """Record of a single retry failure."""
    attempt: int
    timestamp: str  # ISO 8601
    return_code: Optional[int] = None
    exception_type: Optional[str] = None
    message: str = ""


@dataclass
class ExecutionResult:
    """Structured result of a command execution with retry information."""
    success: bool
    return_code: int
    duration_seconds: float
    retry_count: int
    errors: list[RetryError] = field(default_factory=list)
    stdout_text: str = ""
    stderr_text: str = ""


@dataclass
class ValidationError:
    """Configuration validation error or warning."""
    field_path: str
    message: str
    severity: str = "error"  # error | warning


# Custom exception hierarchy

class OpenCodeInfinityError(Exception):
    """Base exception for all system errors."""


class ConfigError(OpenCodeInfinityError):
    """Configuration loading or validation errors."""


class CLIAdapterError(OpenCodeInfinityError):
    """CLI adapter initialization or command building errors."""


class SessionError(OpenCodeInfinityError):
    """Session management errors."""


# =============================================================================
# 輸入消毒 (sanitizer)
# =============================================================================


class InputSanitizer:
    """Validates and sanitizes user input before subprocess execution."""

    SHELL_SPECIAL_CHARS: ClassVar[str] = r';&|$`(){}<>\'"' + "\\\n"

    DANGEROUS_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r";\s*rm\b"),
        re.compile(r"&&\s*rm\b"),
        re.compile(r"\|\|\s*rm\b"),
        re.compile(r"\$\("),
        re.compile(r"`[^`]*`"),
        re.compile(r"\|\s*sh\b"),
        re.compile(r"\|\s*bash\b"),
        re.compile(r">>\s*/"),
        re.compile(r"(?<!>)>\s*/"),
    ]

    def sanitize(self, input_text: str) -> SanitizeResult:
        """Sanitize user input for safe subprocess execution."""
        for pattern in self.DANGEROUS_PATTERNS:
            match = pattern.search(input_text)
            if match:
                reason = f"Dangerous pattern detected: '{match.group()}'"
                self._emit_warning(input_text, reason)
                return SanitizeResult(
                    is_safe=False,
                    sanitized_text="",
                    rejection_reason=reason,
                )
        sanitized = self._escape_shell_chars(input_text)
        return SanitizeResult(
            is_safe=True,
            sanitized_text=sanitized,
            rejection_reason="",
        )

    def is_safe(self, input_text: str) -> bool:
        """Convenience method to check if input is safe."""
        return self.sanitize(input_text).is_safe

    def _escape_shell_chars(self, text: str) -> str:
        """Escape shell special characters with backslash."""
        result: list[str] = []
        for char in text:
            if char == "\n":
                result.append("\\n")
            elif char in self.SHELL_SPECIAL_CHARS:
                result.append(f"\\{char}")
            else:
                result.append(char)
        return "".join(result)

    def _emit_warning(self, input_text: str, reason: str) -> None:
        """Output a warning to stderr with timestamp and truncated input."""
        timestamp = utc_now_iso()
        truncated_input = truncate_text(input_text, 200, suffix="")
        warning_msg = (
            f"[{timestamp}] WARNING: Input rejected - {reason}. "
            f"Input (first 200 chars): {truncated_input!r}\n"
        )
        sys.stderr.write(warning_msg)


# =============================================================================
# 日誌設定 (logger)
# =============================================================================

_LEVEL_COLORS: dict[int, str] = {
    logging.DEBUG: "\033[36m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
}
_RESET = "\033[0m"


class ColoredConsoleFormatter(logging.Formatter):
    """Formatter that adds ANSI color codes based on log level."""

    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelno, "")
        levelname = record.levelname
        message = record.getMessage()
        timestamp = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%S")
        return f"{color}{timestamp} [{levelname}] {record.name}: {message}{_RESET}"


class JSONFormatter(logging.Formatter):
    """Formatter that outputs each log record as a JSON object on one line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, str] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logger(
    name: str,
    level: str = "INFO",
    log_file: Optional[Path] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """Configure logger with colored console + JSON file handlers."""
    effective_level_str = os.environ.get("OPENCODE_LOG_LEVEL", level).upper()
    effective_level = _resolve_level(effective_level_str)

    env_log_file = os.environ.get("OPENCODE_LOG_FILE")
    if env_log_file is not None:
        log_file = Path(env_log_file)

    logger = logging.getLogger(name)
    logger.setLevel(effective_level)
    logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(effective_level)
    console_handler.setFormatter(ColoredConsoleFormatter())
    logger.addHandler(console_handler)

    if log_file is not None:
        file_handler = _create_file_handler(
            log_file, effective_level, max_bytes, backup_count
        )
        if file_handler is not None:
            logger.addHandler(file_handler)

    return logger


def _resolve_level(level_str: str) -> int:
    """Resolve a level string to a logging level int."""
    numeric_level = logging.getLevelName(level_str)
    if isinstance(numeric_level, int):
        return numeric_level
    sys.stderr.write(
        f"WARNING: Invalid log level '{level_str}', falling back to INFO.\n"
    )
    return logging.INFO


def _create_file_handler(
    log_file: Path,
    level: int,
    max_bytes: int,
    backup_count: int,
) -> Optional[RotatingFileHandler]:
    """Create a RotatingFileHandler for JSON-lines output."""
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(level)
        handler.setFormatter(JSONFormatter())
        return handler
    except OSError as exc:
        sys.stderr.write(
            f"WARNING: Cannot open log file '{log_file}': {exc}. "
            f"File logging disabled.\n"
        )
        return None


# =============================================================================
# 設定 schema + defaults
# =============================================================================

# --- Defaults ---

TASK_DEFAULTS: dict[str, Any] = {
    "name": "通用任務",
    "description": "",
    "language": "繁體中文",
    "output_dir": "output",
}

CLI_DEFAULTS: dict[str, Any] = {
    "tool": "opencode",
    "commands": {},
    "full_auto": False,
    "model": None,
    "search": False,
    "allowed_tools": None,
    "permission_mode": None,
    "mcp_server": None,
}

OPENCODE_DEFAULTS: dict[str, Any] = {
    "model": "default",
    "max_tokens": 128000,
    "token_threshold": 0.7,
}

EXECUTION_DEFAULTS: dict[str, Any] = {
    "delay": 1,
    "timeout": 300,
    "max_retries": 5,
    "auto_continue_on_error": True,
    "max_rounds": 0,
    "switch_after_rounds": 0,
    "switch_strategy": "auto",
}

DISPLAY_DEFAULTS: dict[str, Any] = {
    "show_session_id": True,
    "show_token_usage": True,
    "show_timestamp": True,
}

PROMPTS_DEFAULT: list[str] = ["繼續工作"]
SUMMARY_PROMPT_DEFAULT: str = "總結本輪工作（300字內）"

# --- Schema ---


class FieldType(Enum):
    """Supported configuration field types."""
    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    LIST = "list"
    DICT = "dict"
    OPTIONAL_STR = "optional_str"


@dataclass(frozen=True)
class FieldSchema:
    """Schema descriptor for a single configuration field."""
    field_type: FieldType
    required: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    valid_values: Optional[tuple[str, ...]] = None
    description: str = ""


TASK_SCHEMA: dict[str, FieldSchema] = {
    "name": FieldSchema(field_type=FieldType.STR, required=False, description="Task display name"),
    "description": FieldSchema(field_type=FieldType.STR, required=False, description="Task description"),
    "language": FieldSchema(field_type=FieldType.STR, required=False, description="Output language"),
    "output_dir": FieldSchema(field_type=FieldType.STR, required=False, description="Output directory path"),
}

CLI_SCHEMA: dict[str, FieldSchema] = {
    "tool": FieldSchema(field_type=FieldType.STR, required=True, valid_values=("opencode", "claude", "codex", "copilot"), description="CLI tool to use"),
    "commands": FieldSchema(field_type=FieldType.DICT, required=False, description="Custom command overrides"),
    "full_auto": FieldSchema(field_type=FieldType.BOOL, required=False, description="Enable full-auto mode (Codex)"),
    "model": FieldSchema(field_type=FieldType.OPTIONAL_STR, required=False, description="Model name override"),
    "search": FieldSchema(field_type=FieldType.BOOL, required=False, description="Enable web search (Codex)"),
    "allowed_tools": FieldSchema(field_type=FieldType.OPTIONAL_STR, required=False, description="Allowed tools parameter (Claude)"),
    "permission_mode": FieldSchema(field_type=FieldType.OPTIONAL_STR, required=False, description="Permission mode (Claude)"),
    "mcp_server": FieldSchema(field_type=FieldType.OPTIONAL_STR, required=False, description="MCP server parameter (Copilot)"),
}

OPENCODE_SCHEMA: dict[str, FieldSchema] = {
    "model": FieldSchema(field_type=FieldType.STR, required=False, description="OpenCode model identifier"),
    "max_tokens": FieldSchema(field_type=FieldType.INT, required=False, min_value=1, description="Maximum token limit"),
    "token_threshold": FieldSchema(field_type=FieldType.FLOAT, required=False, min_value=0.0, max_value=1.0, description="Token usage threshold (0.0-1.0)"),
}

EXECUTION_SCHEMA: dict[str, FieldSchema] = {
    "delay": FieldSchema(field_type=FieldType.INT, required=False, min_value=0, description="Delay between rounds in seconds"),
    "timeout": FieldSchema(field_type=FieldType.INT, required=False, min_value=0, description="Base timeout in seconds"),
    "max_retries": FieldSchema(field_type=FieldType.INT, required=False, min_value=0, description="Maximum retry attempts"),
    "auto_continue_on_error": FieldSchema(field_type=FieldType.BOOL, required=False, description="Continue execution on error"),
    "max_rounds": FieldSchema(field_type=FieldType.INT, required=False, min_value=0, description="Maximum execution rounds (0 = unlimited)"),
    "switch_after_rounds": FieldSchema(field_type=FieldType.INT, required=False, min_value=0, description="Switch session after N rounds (0 = no switch)"),
    "switch_strategy": FieldSchema(field_type=FieldType.STR, required=False, valid_values=("auto", "token", "rounds"), description="Session switch strategy"),
}

DISPLAY_SCHEMA: dict[str, FieldSchema] = {
    "show_session_id": FieldSchema(field_type=FieldType.BOOL, required=False, description="Display session ID in output"),
    "show_token_usage": FieldSchema(field_type=FieldType.BOOL, required=False, description="Display token usage statistics"),
    "show_timestamp": FieldSchema(field_type=FieldType.BOOL, required=False, description="Display timestamps in output"),
}

PROMPTS_SCHEMA: FieldSchema = FieldSchema(field_type=FieldType.LIST, required=False, description="List of rotating prompt strings")
SUMMARY_PROMPT_SCHEMA: FieldSchema = FieldSchema(field_type=FieldType.STR, required=False, description="Summary prompt used at token threshold")

SECTION_SCHEMAS: dict[str, dict[str, FieldSchema]] = {
    "task": TASK_SCHEMA,
    "cli": CLI_SCHEMA,
    "opencode": OPENCODE_SCHEMA,
    "execution": EXECUTION_SCHEMA,
    "display": DISPLAY_SCHEMA,
}

TOP_LEVEL_FIELDS: dict[str, FieldSchema] = {
    "prompts": PROMPTS_SCHEMA,
    "summary_prompt": SUMMARY_PROMPT_SCHEMA,
}

ALL_KNOWN_SECTIONS: frozenset[str] = frozenset(
    list(SECTION_SCHEMAS.keys()) + list(TOP_LEVEL_FIELDS.keys())
)

FIELD_TYPE_MAP: dict[FieldType, tuple[type, ...]] = {
    FieldType.STR: (str,),
    FieldType.INT: (int,),
    FieldType.FLOAT: (int, float),
    FieldType.BOOL: (bool,),
    FieldType.LIST: (list,),
    FieldType.DICT: (dict,),
    FieldType.OPTIONAL_STR: (str, type(None)),
}


def _matches_field_type(value: object, field_type: FieldType) -> bool:
    """Return True when a raw value matches a schema field type exactly enough for config validation."""
    if field_type == FieldType.STR:
        return isinstance(value, str)
    if field_type == FieldType.INT:
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type == FieldType.FLOAT:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == FieldType.BOOL:
        return isinstance(value, bool)
    if field_type == FieldType.LIST:
        return isinstance(value, list)
    if field_type == FieldType.DICT:
        return isinstance(value, dict)
    if field_type == FieldType.OPTIONAL_STR:
        return value is None or isinstance(value, str)
    return False


def _load_yaml_mapping_from_text(content: str, *, source: str) -> dict[str, Any]:
    """Parse YAML text and require a mapping at the document root.

    The config loader and GUI both need the same guardrails: parse YAML once,
    accept empty documents, and reject top-level non-mapping values with a
    consistent error message.
    """
    try:
        raw = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML parse error in '{source}': {exc}") from exc

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(f"Config file must contain a YAML mapping, got {type(raw).__name__}")
    return raw


# =============================================================================
# 設定載入器 (config loader)
# =============================================================================

_config_logger = logging.getLogger("opencode_infinity.config.loader")
_SUPPORTED_CLI_TOOLS: tuple[str, ...] = ("opencode", "claude", "codex", "copilot")


class ConfigLoader:
    """Loads, validates, and hot-reloads YAML configuration."""

    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._current_config: Optional[AppConfig] = None
        self._warnings: list[str] = []
        self._last_signature: Optional[tuple[int, int]] = None

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def current_config(self) -> Optional[AppConfig]:
        return self._current_config

    def load(self) -> AppConfig:
        """Load and validate configuration from YAML file."""
        raw = self._read_yaml()
        validation_errors = self.validate(raw)
        self._raise_on_fatal_validation_errors(validation_errors)

        config = self._build_config(raw)
        self._current_config = config
        self._last_signature = self._get_file_signature()
        return config

    def reload(self) -> tuple[AppConfig, bool]:
        """Reload configuration from file."""
        previous = self._current_config
        current_signature = self._get_file_signature()

        if (
            previous is not None
            and current_signature is not None
            and current_signature == self._last_signature
        ):
            return previous, False

        try:
            raw = self._read_yaml()
            validation_errors = self.validate(raw)
            self._raise_on_fatal_validation_errors(validation_errors)
            new_config = self._build_config(raw)
        except (ConfigError, yaml.YAMLError, OSError, ValueError) as exc:
            self._warn(f"Config reload failed: {exc}")
            if previous is not None:
                return previous, False
            return AppConfig(), False

        changed = new_config != previous
        self._current_config = new_config
        self._last_signature = current_signature
        if changed:
            print("INFO: Configuration updated successfully.", file=sys.stderr)
        return new_config, changed

    def validate(self, raw: dict[str, Any]) -> list[ValidationError]:
        """Validate raw configuration dictionary against schema."""
        errors: list[ValidationError] = []

        if not isinstance(raw, dict):
            errors.append(ValidationError(
                field_path="<root>",
                message="Configuration must be a YAML mapping (dictionary)",
                severity="error",
            ))
            return errors

        unknown_top_level = raw.keys() - ALL_KNOWN_SECTIONS
        for key in unknown_top_level:
            errors.append(ValidationError(
                field_path=key,
                message=f"Unknown configuration field '{key}' (possible typo?)",
                severity="warning",
            ))

        for section_name, section_schema in SECTION_SCHEMAS.items():
            section_data = raw.get(section_name)
            if section_data is None:
                required_fields = [
                    fname for fname, fschema in section_schema.items() if fschema.required
                ]
                if required_fields:
                    for fname in required_fields:
                        errors.append(ValidationError(
                            field_path=f"{section_name}.{fname}",
                            message=f"Required field '{fname}' is missing from section '{section_name}'",
                            severity="error",
                        ))
                continue

            if not isinstance(section_data, dict):
                errors.append(ValidationError(
                    field_path=section_name,
                    message=f"Section '{section_name}' must be a mapping",
                    severity="error",
                ))
                continue

            errors.extend(self._validate_section(section_name, section_data, section_schema))

        for field_name, field_schema in TOP_LEVEL_FIELDS.items():
            value = raw.get(field_name)
            if value is not None:
                if not _matches_field_type(value, field_schema.field_type):
                    errors.append(ValidationError(
                        field_path=field_name,
                        message=f"Field '{field_name}' must be of type {field_schema.field_type.value}, got {type(value).__name__}",
                        severity="error",
                    ))

        return errors

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    def _warn(self, message: str) -> None:
        self._warnings.append(message)
        print(f"WARNING: {message}", file=sys.stderr)

    def _raise_on_fatal_validation_errors(
        self,
        validation_errors: list[ValidationError],
    ) -> None:
        fatal_errors = [error for error in validation_errors if error.severity == "error"]
        if not fatal_errors:
            return

        formatted_errors = [
            f"{error.field_path}: {error.message}"
            for error in fatal_errors
        ]
        for error_message in formatted_errors:
            _config_logger.warning("Config validation error: %s", error_message)
        raise ConfigError(
            "Configuration validation failed: " + "; ".join(formatted_errors)
        )

    def _get_file_signature(self) -> Optional[tuple[int, int]]:
        try:
            stat_result = self._config_path.stat()
        except OSError:
            return None
        return stat_result.st_mtime_ns, stat_result.st_size

    def _coerce_bounded_int(
        self, raw: dict[str, Any], field_name: str, default: int, minimum: int, warning_prefix: str,
    ) -> int:
        raw_value = raw.get(field_name, default)
        if isinstance(raw_value, bool):
            if field_name in raw:
                self._warn(
                    f"{warning_prefix} value {raw_value!r} must be an integer, using default {default}"
                )
            return default
        try:
            normalized = int(raw_value)
        except (TypeError, ValueError):
            if field_name in raw:
                self._warn(
                    f"{warning_prefix} value {raw_value!r} is not an integer, using default {default}"
                )
            return default

        if normalized < minimum:
            if field_name in raw:
                self._warn(
                    f"{warning_prefix} value {raw_value!r} is out of range (min {minimum}), using default {default}"
                )
            return default
        return normalized

    def _coerce_unit_interval_float(
        self, raw: dict[str, Any], field_name: str, default: float, warning_prefix: str,
    ) -> float:
        raw_value = raw.get(field_name, default)
        if isinstance(raw_value, bool):
            if field_name in raw:
                self._warn(
                    f"{warning_prefix} value {raw_value!r} must be a number, using default {default}"
                )
            return default
        try:
            normalized = float(raw_value)
        except (TypeError, ValueError):
            if field_name in raw:
                self._warn(
                    f"{warning_prefix} value {raw_value!r} is not a number, using default {default}"
                )
            return default
        if 0.0 <= normalized <= 1.0:
            return normalized
        self._warn(f"{warning_prefix} value {raw_value} is out of range [0.0, 1.0], using default {default}")
        return default

    def _read_yaml(self) -> dict[str, Any]:
        try:
            content = self._config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigError(f"Cannot read config file '{self._config_path}': {exc}") from exc
        raw = _load_yaml_mapping_from_text(content, source=str(self._config_path))
        return self._unwrap_named_config(raw)

    def _unwrap_named_config(self, raw: dict[str, Any]) -> dict[str, Any]:
        if len(raw) != 1:
            return raw
        key = next(iter(raw))
        value = raw[key]
        if key in ALL_KNOWN_SECTIONS:
            return raw
        if isinstance(value, dict):
            inner_keys = set(value.keys())
            known_keys = inner_keys & ALL_KNOWN_SECTIONS
            if known_keys:
                return value
        return raw

    def _validate_section(
        self, section_name: str, section_data: dict[str, Any], section_schema: dict[str, Any],
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []

        for key in section_data:
            if key not in section_schema:
                errors.append(ValidationError(
                    field_path=f"{section_name}.{key}",
                    message=f"Unknown field '{key}' in section '{section_name}' (possible typo?)",
                    severity="warning",
                ))

        for fname, fschema in section_schema.items():
            value = section_data.get(fname)
            if value is None and fschema.required:
                errors.append(ValidationError(
                    field_path=f"{section_name}.{fname}",
                    message=f"Required field '{fname}' is missing from section '{section_name}'",
                    severity="error",
                ))
                continue
            if value is None:
                continue

            if not _matches_field_type(value, fschema.field_type):
                errors.append(ValidationError(
                    field_path=f"{section_name}.{fname}",
                    message=f"Field '{fname}' must be of type {fschema.field_type.value}, got {type(value).__name__}",
                    severity="error",
                ))
                continue

            if fschema.min_value is not None and value < fschema.min_value:
                errors.append(ValidationError(
                    field_path=f"{section_name}.{fname}",
                    message=f"Field '{fname}' value {value} is below minimum {fschema.min_value}, using default",
                    severity="warning",
                ))
            if fschema.max_value is not None and value > fschema.max_value:
                errors.append(ValidationError(
                    field_path=f"{section_name}.{fname}",
                    message=f"Field '{fname}' value {value} is above maximum {fschema.max_value}, using default",
                    severity="warning",
                ))
            if fschema.valid_values is not None and value not in fschema.valid_values:
                errors.append(ValidationError(
                    field_path=f"{section_name}.{fname}",
                    message=f"Field '{fname}' value '{value}' is not one of {fschema.valid_values}",
                    severity="warning",
                ))

        return errors

    def _build_config(self, raw: dict[str, Any]) -> AppConfig:
        cli_raw = raw.get("cli", {})
        if isinstance(cli_raw, dict):
            cli_raw = dict(cli_raw)
            cli_raw["commands"] = self._normalize_cli_commands(cli_raw.get("commands", {}))

        task = self._build_task_config(raw.get("task", {}))
        cli = self._build_cli_config(cli_raw)
        opencode = self._build_opencode_config(raw.get("opencode", {}))
        execution = self._build_execution_config(raw.get("execution", {}))
        display = self._build_display_config(raw.get("display", {}))
        prompts = self._normalize_prompts(raw.get("prompts"))
        summary_prompt = self._normalize_summary_prompt(raw.get("summary_prompt"))

        return AppConfig(
            task=task, cli=cli, opencode=opencode, execution=execution,
            display=display, prompts=prompts, summary_prompt=summary_prompt,
        )

    def _normalize_cli_commands(self, raw_commands: Any) -> dict[str, Any]:
        """Normalize CLI command overrides and migrate legacy string commands."""
        if not isinstance(raw_commands, dict):
            return dict(CLI_DEFAULTS["commands"])

        commands = dict(raw_commands)
        run_session = commands.get("run_session")
        if isinstance(run_session, str):
            migrated = run_session.split()
            self._warn(
                f"Migration: cli.commands.run_session converted from string '{run_session}' to list {migrated}"
            )
            commands["run_session"] = migrated
        return commands

    def _normalize_prompts(self, raw_prompts: Any) -> list[str]:
        if not isinstance(raw_prompts, list):
            return list(PROMPTS_DEFAULT)
        string_prompts = [item for item in raw_prompts if isinstance(item, str)]
        normalized = [normalize_newlines(prompt) for prompt in compact_strings(string_prompts)]
        if normalized:
            return normalized
        return list(PROMPTS_DEFAULT)

    def _normalize_summary_prompt(self, raw_summary_prompt: Any) -> str:
        if not isinstance(raw_summary_prompt, str):
            return SUMMARY_PROMPT_DEFAULT
        return normalize_newlines(raw_summary_prompt)

    def _build_task_config(self, raw: Any) -> TaskConfig:
        if not isinstance(raw, dict):
            return TaskConfig()
        return TaskConfig(
            name=raw.get("name", TASK_DEFAULTS["name"]),
            description=raw.get("description", TASK_DEFAULTS["description"]),
            language=raw.get("language", TASK_DEFAULTS["language"]),
            output_dir=raw.get("output_dir", TASK_DEFAULTS["output_dir"]),
        )

    def _build_cli_config(self, raw: Any) -> CLIConfig:
        if not isinstance(raw, dict):
            return CLIConfig()
        tool = raw.get("tool", CLI_DEFAULTS["tool"])
        normalized_tool = tool.strip().lower() if isinstance(tool, str) else CLI_DEFAULTS["tool"]
        commands_raw = raw.get("commands", CLI_DEFAULTS["commands"])
        commands = commands_raw if isinstance(commands_raw, dict) else dict(CLI_DEFAULTS["commands"])
        return CLIConfig(
            tool=normalized_tool,
            commands=commands,
            full_auto=raw.get("full_auto", CLI_DEFAULTS["full_auto"]),
            model=raw.get("model", CLI_DEFAULTS["model"]),
            search=raw.get("search", CLI_DEFAULTS["search"]),
            allowed_tools=raw.get("allowed_tools", CLI_DEFAULTS["allowed_tools"]),
            permission_mode=raw.get("permission_mode", CLI_DEFAULTS["permission_mode"]),
            mcp_server=raw.get("mcp_server", CLI_DEFAULTS["mcp_server"]),
        )

    def _build_opencode_config(self, raw: Any) -> OpenCodeConfig:
        if not isinstance(raw, dict):
            return OpenCodeConfig()
        token_threshold = self._coerce_unit_interval_float(
            raw=raw, field_name="token_threshold",
            default=OPENCODE_DEFAULTS["token_threshold"], warning_prefix="opencode.token_threshold",
        )
        max_tokens = self._coerce_bounded_int(
            raw=raw, field_name="max_tokens",
            default=OPENCODE_DEFAULTS["max_tokens"], minimum=1, warning_prefix="opencode.max_tokens",
        )
        return OpenCodeConfig(
            model=raw.get("model", OPENCODE_DEFAULTS["model"]),
            max_tokens=max_tokens,
            token_threshold=token_threshold,
        )

    def _build_execution_config(self, raw: Any) -> ExecutionConfig:
        if not isinstance(raw, dict):
            return ExecutionConfig()
        delay = self._coerce_bounded_int(raw=raw, field_name="delay", default=EXECUTION_DEFAULTS["delay"], minimum=0, warning_prefix="execution.delay")
        timeout = self._coerce_bounded_int(raw=raw, field_name="timeout", default=EXECUTION_DEFAULTS["timeout"], minimum=0, warning_prefix="execution.timeout")
        max_retries = self._coerce_bounded_int(raw=raw, field_name="max_retries", default=EXECUTION_DEFAULTS["max_retries"], minimum=0, warning_prefix="execution.max_retries")
        max_rounds = self._coerce_bounded_int(raw=raw, field_name="max_rounds", default=EXECUTION_DEFAULTS["max_rounds"], minimum=0, warning_prefix="execution.max_rounds")
        switch_after_rounds = self._coerce_bounded_int(raw=raw, field_name="switch_after_rounds", default=EXECUTION_DEFAULTS["switch_after_rounds"], minimum=0, warning_prefix="execution.switch_after_rounds")
        return ExecutionConfig(
            delay=delay, timeout=timeout, max_retries=max_retries,
            auto_continue_on_error=raw.get("auto_continue_on_error", EXECUTION_DEFAULTS["auto_continue_on_error"]),
            max_rounds=max_rounds,
            switch_after_rounds=switch_after_rounds,
            switch_strategy=raw.get("switch_strategy", EXECUTION_DEFAULTS["switch_strategy"]),
        )

    def _build_display_config(self, raw: Any) -> DisplayConfig:
        if not isinstance(raw, dict):
            return DisplayConfig()
        return DisplayConfig(
            show_session_id=raw.get("show_session_id", DISPLAY_DEFAULTS["show_session_id"]),
            show_token_usage=raw.get("show_token_usage", DISPLAY_DEFAULTS["show_token_usage"]),
            show_timestamp=raw.get("show_timestamp", DISPLAY_DEFAULTS["show_timestamp"]),
        )


# =============================================================================
# CLI adapter base + 各實作 + factory
# =============================================================================


class CLIAdapter(ABC):
    """Base class for all CLI tool adapters."""

    @abstractmethod
    def build_run_command(self, prompt: str) -> list[str]:
        """Build command to run a new prompt (no session)."""
        ...

    @abstractmethod
    def build_session_command(self, session_id: str, prompt: str) -> list[str]:
        """Build command to continue a session with a prompt."""
        ...

    @abstractmethod
    def build_continue_command(self) -> list[str]:
        """Build command to continue the most recent session."""
        ...

    def build_export_command(self, session_id: str) -> Optional[list[str]]:
        """Build command to export session data."""
        return None

    @property
    def supports_token_stats(self) -> bool:
        """Whether this CLI tool supports token usage statistics."""
        return False

    @property
    def tool_name(self) -> str:
        """Human-readable tool name."""
        return self.__class__.__name__


class OpenCodeAdapter(CLIAdapter):
    """Adapter for the OpenCode CLI tool."""

    _MIN_PROMPT_LENGTH: int = 1
    _MAX_PROMPT_LENGTH: int = 100_000

    def __init__(self) -> None:
        if shutil.which("opencode") is None:
            raise CLIAdapterError(
                "opencode executable not found. "
                "Please ensure opencode is installed and available in PATH."
            )

    def _validate_prompt(self, prompt: str) -> None:
        length = len(prompt)
        if length < self._MIN_PROMPT_LENGTH:
            raise CLIAdapterError("Prompt must not be empty (minimum 1 character).")
        if length > self._MAX_PROMPT_LENGTH:
            raise CLIAdapterError(
                f"Prompt exceeds maximum length of {self._MAX_PROMPT_LENGTH} characters (got {length})."
            )

    def build_run_command(self, prompt: str) -> list[str]:
        self._validate_prompt(prompt)
        return ["opencode", "run", prompt]

    def build_session_command(self, session_id: str, prompt: str) -> list[str]:
        self._validate_prompt(prompt)
        return ["opencode", "run", "-s", session_id, prompt]

    def build_continue_command(self) -> list[str]:
        return ["opencode", "run", "--continue"]

    def build_export_command(self, session_id: str) -> Optional[list[str]]:
        return ["opencode", "export", session_id]

    def build_stats_command(self) -> list[str]:
        return ["opencode", "stats"]

    @property
    def supports_token_stats(self) -> bool:
        return True

    @property
    def tool_name(self) -> str:
        return "OpenCode"


_MAX_MODEL_NAME_LENGTH: int = 128


class CodexAdapter(CLIAdapter):
    """Adapter for the Codex CLI tool (v0.6x+)."""

    def __init__(self, config: CLIConfig) -> None:
        self._config = config
        if config.model is not None:
            self._validate_model(config.model)

    @staticmethod
    def _validate_model(model: str) -> None:
        if not model:
            raise CLIAdapterError("Model name must not be empty when specified.")
        if len(model) > _MAX_MODEL_NAME_LENGTH:
            raise CLIAdapterError(
                f"Model name exceeds maximum length of {_MAX_MODEL_NAME_LENGTH} characters (got {len(model)})."
            )

    def _build_global_flags(self) -> list[str]:
        flags: list[str] = []
        if self._config.full_auto:
            flags.append("--full-auto")
        if self._config.model is not None:
            flags.extend(["-m", self._config.model])
        if self._config.search:
            flags.append("--search")
        return flags

    def _build_subcommand_flags(self) -> list[str]:
        return ["--skip-git-repo-check"]

    def build_run_command(self, prompt: str) -> list[str]:
        if not prompt:
            raise CLIAdapterError("Prompt must not be empty")
        cmd: list[str] = ["codex"]
        cmd.extend(self._build_global_flags())
        cmd.append("exec")
        cmd.extend(self._build_subcommand_flags())
        return cmd

    def build_session_command(self, session_id: str, prompt: str) -> list[str]:
        if not prompt:
            raise CLIAdapterError("Prompt must not be empty")
        cmd: list[str] = ["codex"]
        cmd.extend(self._build_global_flags())
        # Codex resume behavior is currently tied to the most recent session.
        # Keep the explicit session_id parameter for interface consistency.
        cmd.extend(["exec", "resume", "--last"])
        cmd.extend(self._build_subcommand_flags())
        return cmd

    def build_continue_command(self) -> list[str]:
        cmd: list[str] = ["codex"]
        cmd.extend(self._build_global_flags())
        cmd.extend(["resume", "--last"])
        cmd.extend(self._build_subcommand_flags())
        return cmd

    def build_export_command(self, session_id: str) -> Optional[list[str]]:
        return None

    @property
    def supports_token_stats(self) -> bool:
        return False

    @property
    def tool_name(self) -> str:
        return "Codex CLI"

    @property
    def supports_stdin_pipe(self) -> bool:
        return True


class ClaudeAdapter(CLIAdapter):
    """Adapter for Claude Code CLI tool."""

    def __init__(self, config: CLIConfig) -> None:
        self._config = config

    @property
    def tool_name(self) -> str:
        return "Claude Code"

    def _build_security_params(self) -> list[str]:
        params: list[str] = []
        if self._config.allowed_tools is not None:
            params.extend(["--allowedTools", self._config.allowed_tools])
        if self._config.permission_mode is not None:
            params.extend(["--permission-mode", self._config.permission_mode])
        return params

    def build_run_command(self, prompt: str) -> list[str]:
        if not prompt:
            raise CLIAdapterError("Prompt must not be empty")
        cmd: list[str] = ["claude"]
        cmd.extend(self._build_security_params())
        cmd.extend(["-p", prompt])
        return cmd

    def build_continue_command(self) -> list[str]:
        cmd: list[str] = ["claude", "--continue"]
        cmd.extend(self._build_security_params())
        return cmd

    def build_session_command(self, session_id: str, prompt: str) -> list[str]:
        if not session_id:
            raise CLIAdapterError("Session ID must not be empty")
        if not prompt:
            raise CLIAdapterError("Prompt must not be empty")
        cmd: list[str] = ["claude", "--resume", session_id]
        cmd.extend(self._build_security_params())
        cmd.extend(["-p", prompt])
        return cmd

    def build_export_command(self, session_id: str) -> Optional[list[str]]:
        return None

    @property
    def supports_token_stats(self) -> bool:
        return False


class CopilotAdapter(CLIAdapter):
    """Adapter for the GitHub Copilot CLI tool."""

    def __init__(self, config: CLIConfig) -> None:
        self._config = config
        self._mcp_server: Optional[str] = config.mcp_server

    def _build_base_command(self) -> list[str]:
        cmd: list[str] = ["copilot"]
        cmd.append("--agent")
        cmd.append("--read-files")
        cmd.append("--write-files")
        cmd.append("--create-pr")
        if self._mcp_server:
            cmd.append("--mcp-server")
            cmd.append(self._mcp_server)
        return cmd

    def build_run_command(self, prompt: str) -> list[str]:
        if not prompt:
            raise CLIAdapterError("Prompt must not be empty")
        cmd = self._build_base_command()
        cmd.append("run")
        cmd.append(prompt)
        return cmd

    def build_session_command(self, session_id: str, prompt: str) -> list[str]:
        if not session_id:
            raise CLIAdapterError("Session ID must not be empty")
        if not prompt:
            raise CLIAdapterError("Prompt must not be empty")
        cmd = self._build_base_command()
        cmd.append("run_session")
        cmd.append("--session")
        cmd.append(session_id)
        cmd.append(prompt)
        return cmd

    def build_continue_command(self) -> list[str]:
        cmd = self._build_base_command()
        cmd.append("run_session")
        cmd.append("--last")
        return cmd

    @property
    def supports_token_stats(self) -> bool:
        return False

    @property
    def tool_name(self) -> str:
        return "Copilot"


def create_adapter(tool: str, config: CLIConfig) -> CLIAdapter:
    """Factory function to create the appropriate CLI adapter."""
    tool_lower = tool.strip().lower()
    if tool_lower == "opencode":
        return OpenCodeAdapter()
    if tool_lower == "claude":
        return ClaudeAdapter(config)
    if tool_lower == "codex":
        return CodexAdapter(config)
    if tool_lower == "copilot":
        return CopilotAdapter(config)
    supported = ", ".join(_SUPPORTED_CLI_TOOLS)
    raise ValueError(f"Unsupported CLI tool: {tool!r}. Supported tools: {supported}")


# =============================================================================
# 平台工具 (executor/platform)
# =============================================================================

IS_WINDOWS: bool = os.name == "nt"

_TERMINATE_TIMEOUT_SECONDS: int = 5

_platform_logger = logging.getLogger("opencode_infinity.executor.platform")


def terminate_process(process: subprocess.Popen[Any]) -> None:
    """Gracefully terminate a subprocess with platform-aware fallback."""
    try:
        process.terminate()
    except OSError as exc:
        _platform_logger.debug("terminate_process: terminate() raised OSError: %s", exc)
        return

    try:
        process.wait(timeout=_TERMINATE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        _platform_logger.warning(
            "terminate_process: process %d did not exit within %d seconds, sending kill signal",
            process.pid, _TERMINATE_TIMEOUT_SECONDS,
        )
        try:
            process.kill()
            process.wait()
        except OSError as exc:
            _platform_logger.debug("terminate_process: kill() raised OSError: %s", exc)


def get_creation_flags() -> int:
    """Return platform-appropriate subprocess creation flags."""
    if IS_WINDOWS:
        return 0x00000200  # CREATE_NEW_PROCESS_GROUP
    return 0


_ENABLE_VIRTUAL_TERMINAL_PROCESSING: int = 0x0004
_STD_OUTPUT_HANDLE: int = -11
_STD_ERROR_HANDLE: int = -12


def _try_enable_virtual_terminal() -> bool:
    """Attempt to enable Windows Virtual Terminal Processing for ANSI colors."""
    if not IS_WINDOWS:
        return False
    try:
        kernel32 = ctypes.windll.kernel32
        for handle_id in (_STD_OUTPUT_HANDLE, _STD_ERROR_HANDLE):
            handle = kernel32.GetStdHandle(handle_id)
            if handle == -1:
                return False
            mode = ctypes.c_ulong()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            new_mode = mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
            if not kernel32.SetConsoleMode(handle, new_mode):
                return False
        return True
    except (AttributeError, OSError, ValueError):
        return False


def init_ansi_colors() -> None:
    """Initialize ANSI color support for the current platform."""
    if not IS_WINDOWS:
        return
    if _try_enable_virtual_terminal():
        _platform_logger.debug("Windows Virtual Terminal Processing enabled successfully")
        return
    try:
        import colorama  # type: ignore[import-untyped]
        colorama.init()
        _platform_logger.debug("Windows ANSI colors initialized via colorama fallback")
    except ImportError:
        sys.stderr.write(
            "WARNING: Could not enable ANSI colors on Windows. "
            "Install colorama for color support: pip install colorama\n"
        )


# =============================================================================
# 執行器 (executor/runner)
# =============================================================================

_executor_logger = logging.getLogger("opencode_infinity.executor.runner")

_MAX_BACKOFF_SECONDS: int = 3600


class Executor:
    """Executes subprocess commands with retry, timeout, and cleanup."""

    def __init__(self, sanitizer: Optional[InputSanitizer] = None) -> None:
        self._sanitizer = sanitizer if sanitizer is not None else InputSanitizer()

    def run_with_retry(
        self,
        command: list[str],
        timeout: int,
        max_retries: int,
        prompt: Optional[str] = None,
        stdin_input: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute a command with retry logic and exponential backoff."""
        start_time = time.monotonic()
        validation_error = self._validate_invocation(command, timeout, max_retries)
        if validation_error is not None:
            return self._build_immediate_failure(start_time=start_time, exception_type="ValueError", message=validation_error)

        sanitization_failure = self._sanitize_prompt(start_time, prompt, command, "run_with_retry")
        if sanitization_failure is not None:
            return sanitization_failure

        errors: list[RetryError] = []
        temp_files: list[Path] = []
        resolved_command = self._resolve_command(command)
        stdin_bytes = stdin_input.encode("utf-8") if stdin_input else None
        last_stdout = ""
        last_stderr = ""

        try:
            for attempt in range(max_retries + 1):
                attempt_timeout = self._calculate_backoff_timeout(timeout, attempt)

                try:
                    result = self._execute_once(
                        command=resolved_command, timeout=attempt_timeout,
                        stdin_input=stdin_bytes, temp_files=temp_files,
                    )
                    last_stdout = self._decode_output(result.stdout)
                    last_stderr = self._decode_output(result.stderr)
                    if result.returncode == 0:
                        duration = time.monotonic() - start_time
                        return ExecutionResult(
                            success=True,
                            return_code=0,
                            duration_seconds=duration,
                            retry_count=attempt,
                            errors=errors,
                            stdout_text=last_stdout,
                            stderr_text=last_stderr,
                        )

                    error = RetryError(
                        attempt=attempt + 1, timestamp=utc_now_iso(),
                        return_code=result.returncode,
                        message=f"Command exited with code {result.returncode}",
                    )
                    errors.append(error)
                    _executor_logger.warning(
                        "run_with_retry: attempt %d/%d failed, return_code=%d, command=%s",
                        attempt + 1, max_retries + 1, result.returncode, command,
                    )

                except subprocess.TimeoutExpired:
                    error = RetryError(
                        attempt=attempt + 1, timestamp=utc_now_iso(),
                        exception_type="TimeoutExpired",
                        message=f"Command timed out after {attempt_timeout}s",
                    )
                    errors.append(error)
                    _executor_logger.warning(
                        "run_with_retry: attempt %d/%d timed out, timeout=%ds, command=%s",
                        attempt + 1, max_retries + 1, attempt_timeout, command,
                    )

                except OSError as exc:
                    error = RetryError(
                        attempt=attempt + 1, timestamp=utc_now_iso(),
                        exception_type=type(exc).__name__, message=str(exc),
                    )
                    errors.append(error)
                    _executor_logger.error(
                        "run_with_retry: attempt %d/%d raised %s: %s, command=%s",
                        attempt + 1, max_retries + 1, type(exc).__name__, exc, command,
                    )

                if attempt < max_retries:
                    backoff_wait = min(2 ** attempt, _MAX_BACKOFF_SECONDS)
                    time.sleep(min(backoff_wait, 10))

            duration = time.monotonic() - start_time
            final_return_code = (
                errors[-1].return_code if errors and errors[-1].return_code is not None else -1
            )
            return ExecutionResult(
                success=False,
                return_code=final_return_code,
                duration_seconds=duration,
                retry_count=max_retries,
                errors=errors,
                stdout_text=last_stdout,
                stderr_text=last_stderr,
            )

        finally:
            self._cleanup_temp_files(temp_files)

    def run_with_popen(
        self,
        command: list[str],
        timeout: int,
        stdin_input: Optional[str] = None,
        prompt: Optional[str] = None,
        capture_output: bool = False,
    ) -> ExecutionResult:
        """Execute a command using Popen for stdin pipe support.
        
        When capture_output=False (default), stdout/stderr are inherited from
        the terminal so the user sees real-time output from the subprocess.
        When capture_output=True, output is captured into ExecutionResult fields.
        """
        start_time = time.monotonic()
        validation_error = self._validate_invocation(command, timeout, 0)
        if validation_error is not None:
            return self._build_immediate_failure(start_time=start_time, exception_type="ValueError", message=validation_error)

        sanitization_failure = self._sanitize_prompt(start_time, prompt, command, "run_with_popen")
        if sanitization_failure is not None:
            return sanitization_failure

        temp_files: list[Path] = []
        stdin_bytes = stdin_input.encode("utf-8") if stdin_input else None

        try:
            process: Optional[subprocess.Popen[bytes]] = None
            try:
                resolved_command = self._resolve_command(command)
                process = subprocess.Popen(
                    resolved_command,
                    stdin=subprocess.PIPE if stdin_input else None,
                    stdout=subprocess.PIPE if capture_output else None,
                    stderr=subprocess.PIPE if capture_output else None,
                    shell=False,
                    creationflags=get_creation_flags(),
                )
                if capture_output:
                    stdout_data, stderr_data = process.communicate(input=stdin_bytes, timeout=timeout)
                else:
                    # Write stdin then wait — output goes directly to terminal
                    if stdin_bytes and process.stdin:
                        process.stdin.write(stdin_bytes)
                        process.stdin.close()
                    process.wait(timeout=timeout)
                    stdout_data, stderr_data = b"", b""
                duration = time.monotonic() - start_time
                return ExecutionResult(
                    success=process.returncode == 0,
                    return_code=process.returncode if process.returncode is not None else -1,
                    duration_seconds=duration, retry_count=0,
                    errors=(
                        [] if process.returncode == 0
                        else [RetryError(attempt=1, timestamp=utc_now_iso(), return_code=process.returncode, message=f"Command exited with code {process.returncode}")]
                    ),
                    stdout_text=self._decode_output(stdout_data),
                    stderr_text=self._decode_output(stderr_data),
                )

            except subprocess.TimeoutExpired:
                if process is not None:
                    terminate_process(process)
                duration = time.monotonic() - start_time
                return ExecutionResult(
                    success=False, return_code=-1, duration_seconds=duration, retry_count=0,
                    errors=[RetryError(attempt=1, timestamp=utc_now_iso(), exception_type="TimeoutExpired", message=f"Command timed out after {timeout}s")],
                )

            except OSError as exc:
                _executor_logger.error("run_with_popen: %s: %s, command=%s", type(exc).__name__, exc, command)
                duration = time.monotonic() - start_time
                return ExecutionResult(
                    success=False, return_code=-1, duration_seconds=duration, retry_count=0,
                    errors=[RetryError(attempt=1, timestamp=utc_now_iso(), exception_type=type(exc).__name__, message=str(exc))],
                )

        finally:
            self._cleanup_temp_files(temp_files)

    # --- Private helpers ---

    def _validate_invocation(self, command: list[str], timeout: int, max_retries: int) -> Optional[str]:
        if not command:
            return "command must not be empty"
        if timeout < 0:
            return "timeout must be non-negative"
        if max_retries < 0:
            return "max_retries must be non-negative"
        return None

    def _sanitize_prompt(self, start_time: float, prompt: Optional[str], command: list[str], operation: str) -> Optional[ExecutionResult]:
        if prompt is None:
            return None
        sanitize_result = self._sanitizer.sanitize(prompt)
        if sanitize_result.is_safe:
            return None
        _executor_logger.warning("%s: prompt rejected by sanitizer, reason=%s, command=%s", operation, sanitize_result.rejection_reason, command)
        return self._build_immediate_failure(start_time=start_time, exception_type="SanitizationError", message=sanitize_result.rejection_reason)

    def _build_immediate_failure(self, start_time: float, exception_type: str, message: str) -> ExecutionResult:
        duration = time.monotonic() - start_time
        return ExecutionResult(
            success=False, return_code=-1, duration_seconds=duration, retry_count=0,
            errors=[RetryError(attempt=0, timestamp=utc_now_iso(), exception_type=exception_type, message=message)],
        )

    @staticmethod
    def _resolve_command(command: list[str]) -> list[str]:
        if not command:
            return command
        if IS_WINDOWS:
            resolved = shutil.which(command[0])
            if resolved is not None:
                return [resolved] + command[1:]
        return command

    def _execute_once(self, command: list[str], timeout: int, stdin_input: Optional[bytes] = None, temp_files: Optional[list[Path]] = None) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            command, input=stdin_input, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=False, timeout=timeout, creationflags=get_creation_flags(),
        )

    @staticmethod
    def _decode_output(output: Optional[bytes]) -> str:
        if not output:
            return ""
        return output.decode("utf-8", errors="replace")

    def _calculate_backoff_timeout(self, base_timeout: int, attempt: int) -> int:
        backoff_timeout: int = base_timeout * (2 ** attempt)
        return min(backoff_timeout, _MAX_BACKOFF_SECONDS)

    def _cleanup_temp_files(self, temp_files: list[Path]) -> None:
        for temp_path in temp_files:
            self._safe_delete(temp_path)

    @staticmethod
    def _safe_delete(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            _executor_logger.debug("_safe_delete: failed to delete %s: %s: %s", path, type(exc).__name__, exc)


# =============================================================================
# Session 管理器
# =============================================================================

_session_logger = logging.getLogger("opencode_infinity.session.manager")

_SESSION_CREATION_TIMEOUT: int = 30
_MAX_EXPORT_MESSAGES: int = 5
_MESSAGE_CHAR_LIMIT: int = 500


class SessionManager:
    """Manages session lifecycle: creation, switching, context passing."""

    def __init__(self, adapter: CLIAdapter, executor: Executor, config: AppConfig) -> None:
        self._adapter = adapter
        self._executor = executor
        self._config = config
        self._round_count: int = 0
        self._session_increment: int = 0
        self._original_session_id: Optional[str] = None

    @property
    def round_count(self) -> int:
        return self._round_count

    def increment_round(self) -> None:
        self._round_count += 1

    def reset_rounds(self) -> None:
        self._round_count = 0

    def update_runtime(self, *, adapter: Optional[CLIAdapter] = None, config: Optional[AppConfig] = None) -> None:
        """Update runtime dependencies without discarding session state."""
        if adapter is not None:
            self._adapter = adapter
        if config is not None:
            self._config = config

    def should_switch(self, session_id: str) -> bool:
        """Determine whether a session switch is needed."""
        strategy = self._config.execution.switch_strategy
        strategy_handler = self._resolve_switch_strategy(strategy)
        return strategy_handler(session_id)

    def switch_session(self, current_session_id: str) -> str:
        """Execute the session switch workflow."""
        if self._original_session_id is None:
            self._original_session_id = current_session_id

        _session_logger.info("switch_session: initiating session switch from %s", current_session_id)

        summary_context = self._execute_summary(current_session_id)
        exported_context = self._export_context(current_session_id)
        context = self._build_context(summary_context, exported_context)
        new_session_id = self._create_new_session(current_session_id, context)

        self.reset_rounds()
        _session_logger.info("switch_session: switched from %s to %s", current_session_id, new_session_id)
        return new_session_id

    # --- Private helpers ---

    def _resolve_switch_strategy(self, strategy: str) -> Callable[[str], bool]:
        if strategy == "token":
            return self._check_token_threshold
        if strategy == "rounds":
            return lambda _session_id: self._check_rounds_threshold()
        if self._adapter.supports_token_stats:
            return self._check_token_threshold
        return lambda _session_id: self._check_rounds_threshold()

    def _check_token_threshold(self, session_id: str) -> bool:
        if not self._adapter.supports_token_stats:
            return self._check_rounds_threshold()

        stats_command: Optional[list[str]] = None
        if hasattr(self._adapter, "build_stats_command"):
            stats_command = getattr(self._adapter, "build_stats_command")()

        if stats_command is None:
            return self._check_rounds_threshold()

        result = self._executor.run_with_retry(command=stats_command, timeout=30, max_retries=1)

        if not result.success:
            _session_logger.warning("_check_token_threshold: stats query failed for session %s", session_id)
            return self._check_rounds_threshold()

        token_ratio = self._parse_token_usage(result)
        if token_ratio is None:
            return self._check_rounds_threshold()

        threshold = self._config.opencode.token_threshold
        should_switch = token_ratio >= threshold

        if should_switch:
            _session_logger.info(
                "_check_token_threshold: token usage %.1f%% exceeds threshold %.1f%%",
                token_ratio * 100, threshold * 100,
            )
        return should_switch

    def _check_rounds_threshold(self) -> bool:
        switch_after = self._config.execution.switch_after_rounds
        if switch_after <= 0:
            return False
        should_switch = self._round_count >= switch_after
        if should_switch:
            _session_logger.info(
                "_check_rounds_threshold: round count %d reached switch_after_rounds %d",
                self._round_count, switch_after,
            )
        return should_switch

    def _parse_token_usage(self, result: ExecutionResult) -> Optional[float]:
        try:
            max_tokens = self._config.opencode.max_tokens
            if max_tokens <= 0:
                return None
            estimated_tokens_per_round = 3000
            estimated_usage = self._round_count * estimated_tokens_per_round
            ratio = estimated_usage / max_tokens
            return clamp(ratio, 0.0, 1.0)
        except (ValueError, ZeroDivisionError):
            return None

    def _execute_summary(self, session_id: str) -> str:
        summary_prompt = self._config.summary_prompt
        try:
            command = self._adapter.build_session_command(session_id, summary_prompt)
            result = self._executor.run_with_retry(
                command=command, timeout=self._config.execution.timeout, max_retries=1, prompt=summary_prompt,
            )
            if result.success:
                summary_text = normalize_newlines(result.stdout_text).strip()
                if summary_text:
                    return summary_text
                _session_logger.warning(
                    "_execute_summary: empty summary output for session %s, using fallback prompt",
                    session_id,
                )
                return summary_prompt
            _session_logger.warning("_execute_summary: failed for session %s, return_code=%d", session_id, result.return_code)
            return ""
        except (OSError, SessionError) as exc:
            _session_logger.warning("_execute_summary: %s: %s, session_id=%s", type(exc).__name__, exc, session_id)
            return ""

    def _export_context(self, session_id: str) -> list[str]:
        export_command = self._adapter.build_export_command(session_id)
        if export_command is None:
            return []
        try:
            result = self._executor.run_with_retry(command=export_command, timeout=_SESSION_CREATION_TIMEOUT, max_retries=1)
            if not result.success:
                return []
            return compact_strings(normalize_newlines(result.stdout_text).splitlines())[:_MAX_EXPORT_MESSAGES]
        except (OSError, SessionError) as exc:
            _session_logger.warning("_export_context: %s: %s, session_id=%s", type(exc).__name__, exc, session_id)
            return []

    def _build_context(self, summary: str, messages: list[str]) -> str:
        context_parts: list[str] = []
        normalized_summary = normalize_newlines(summary).strip()
        normalized_messages = [normalize_newlines(message) for message in compact_strings(messages)]

        if normalized_summary:
            context_parts.append(f"Summary: {truncate_text(normalized_summary, _MESSAGE_CHAR_LIMIT, suffix='')}")

        truncated_messages = [
            truncate_text(msg, _MESSAGE_CHAR_LIMIT, suffix="")
            for msg in normalized_messages[:_MAX_EXPORT_MESSAGES]
        ]
        if truncated_messages:
            context_parts.append("Recent context:")
            context_parts.extend(truncated_messages)

        return "\n".join(context_parts)

    def _create_new_session(self, current_session_id: str, context: str) -> str:
        start_time = time.monotonic()
        try:
            new_session_prompt = self._get_new_session_prompt(context)
            command = self._adapter.build_run_command(new_session_prompt)
            result = self._executor.run_with_retry(
                command=command, timeout=_SESSION_CREATION_TIMEOUT, max_retries=1, prompt=new_session_prompt,
            )
            elapsed = time.monotonic() - start_time
            if result.success and elapsed <= _SESSION_CREATION_TIMEOUT:
                new_id = self._generate_session_id(current_session_id)
                _session_logger.info("_create_new_session: auto-created session %s in %.1fs", new_id, elapsed)
                return new_id
            return self._generate_fallback_session_id(current_session_id)
        except (OSError, SessionError) as exc:
            _session_logger.warning("_create_new_session: %s: %s, session_id=%s", type(exc).__name__, exc, current_session_id)
            return self._generate_fallback_session_id(current_session_id)

    def _get_new_session_prompt(self, context: str) -> str:
        if context:
            return context
        if self._config.prompts:
            return self._config.prompts[0]
        return self._config.summary_prompt

    def _generate_session_id(self, current_session_id: str) -> str:
        self._session_increment += 1
        base_id = self._original_session_id or current_session_id
        return f"{base_id}_{self._session_increment}"

    def _generate_fallback_session_id(self, current_session_id: str) -> str:
        self._session_increment += 1
        base_id = self._original_session_id or current_session_id
        new_id = f"{base_id}_{self._session_increment}"
        print(f"WARNING: Auto session creation failed. Using manual session ID: {new_id}", file=sys.stderr)
        _session_logger.warning("_generate_fallback_session_id: using manual ID %s", new_id)
        return new_id


# =============================================================================
# 主程式邏輯 (__main__)
# =============================================================================

_TASKS_YAML_DIR: str = "configs"

_SESSION_ID_PATTERN: re.Pattern[str] = re.compile(
    r"^(ses_.+|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)

_main_logger: logging.Logger = logging.getLogger("opencode_infinity.__main__")


def _validate_session_id(session_id: str) -> bool:
    """Validate session_id format: must be ses_* or UUID."""
    return bool(_SESSION_ID_PATTERN.match(session_id))


def _resolve_config_path(config_name: Optional[str]) -> Path:
    """Resolve the configuration file path from a config name or path."""
    if config_name is None:
        tasks_dir = Path(_TASKS_YAML_DIR)
        if tasks_dir.is_dir():
            yaml_files = sorted(
                list(tasks_dir.glob("*.yaml")) + list(tasks_dir.glob("*.yml")),
                key=lambda path: path.name,
            )
            if yaml_files:
                return yaml_files[0]
        raise ConfigError(
            f"No config file specified and no YAML files found in '{_TASKS_YAML_DIR}/'"
        )

    config_path = Path(config_name)
    if config_path.is_file():
        return config_path

    tasks_dir = Path(_TASKS_YAML_DIR)
    for candidate in (
        tasks_dir / f"{config_name}.yaml",
        tasks_dir / config_name,
        tasks_dir / f"{config_name}.yml",
    ):
        if candidate.is_file():
            return candidate

    raise ConfigError(
        f"Config file not found: '{config_name}' "
        f"(searched in current directory and '{_TASKS_YAML_DIR}/')"
    )


def _resolve_launch_arguments(args: list[str]) -> tuple[str, Optional[str]]:
    """Resolve CLI arguments into a session ID and an optional config reference."""
    if len(args) == 1:
        if _validate_session_id(args[0]):
            return args[0], None
        return f"ses_{int(time.time())}", args[0]

    if len(args) == 2:
        if _validate_session_id(args[0]):
            return args[0], args[1]
        raise ConfigError(
            "When two arguments are supplied, the first one must be a valid session ID "
            "(ses_* or UUID)."
        )

    raise ConfigError(
        "Expected one or two positional arguments: <session_id> [config_name]"
    )


def _supports_stdin_pipe(adapter: CLIAdapter) -> bool:
    """Return whether the adapter prefers stdin-based prompt delivery."""
    return bool(getattr(adapter, "supports_stdin_pipe", False))


def _format_elapsed_time(seconds: float) -> str:
    """Format elapsed time as 'X小時Y分鐘'."""
    total_minutes = int(seconds) // 60
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}小時{minutes}分鐘"


class _MainLoopState:
    """Mutable state for the main execution loop."""

    def __init__(self) -> None:
        self.running: bool = True
        self.round_count: int = 0
        self.success_count: int = 0
        self.fail_count: int = 0
        self.session_count: int = 1
        self.start_time: float = time.monotonic()
        self.current_session_id: str = ""
        self.executor: Optional[Executor] = None


_state: _MainLoopState = _MainLoopState()


def _sigint_handler(signum: int, frame: Optional[FrameType]) -> None:
    """Handle SIGINT (Ctrl+C): stop loop, display stats."""
    _state.running = False
    elapsed = time.monotonic() - _state.start_time
    elapsed_str = _format_elapsed_time(elapsed)
    total = _state.success_count + _state.fail_count
    success_rate = f"{_state.success_count}/{total}" if total > 0 else "0/0"

    print(file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    print("OpenCode Infinity - 執行統計", file=sys.stderr)
    print(f"  總執行輪次: {_state.round_count}", file=sys.stderr)
    print(f"  成功/失敗: {success_rate}", file=sys.stderr)
    print(f"  Session 數量: {_state.session_count}", file=sys.stderr)
    print(f"  總耗時: {elapsed_str}", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    sys.exit(0)


def _display_round_info(round_num: int, session_id: str, config: AppConfig, prompt: str) -> None:
    """Display round information to the terminal."""
    try:
        print(f"\n{'-' * 50}")
        print(f">> Round {round_num}")
        if config.display.show_session_id:
            print(f"  Session: {session_id}")
        if config.display.show_timestamp:
            now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            print(f"  Time: {now}")
        prompt_display = truncate_text(prompt, 80)
        print(f"  Prompt: {prompt_display}")
        print(f"{'-' * 50}")
    except UnicodeEncodeError:
        print(f"\n[Round {round_num}] Session={session_id}")


def _select_prompt(prompts: list[str], prompt_index: int) -> tuple[str, int]:
    """Return the next prompt and the updated cursor position.

    A tiny helper keeps the main loop readable and centralizes the fallback
    behavior when the config provides no prompts.
    """
    active_prompts = prompts or ["繼續工作"]
    next_index = prompt_index + 1
    return active_prompts[prompt_index % len(active_prompts)], next_index


def _build_round_command(adapter: CLIAdapter, round_num: int, session_id: str, prompt: str) -> list[str]:
    """Build the command for the current round.

    Round 1 starts a fresh run, later rounds continue the active session.
    Keeping this logic in one place avoids the CLI and GUI loops drifting apart.
    """
    if round_num == 1:
        return adapter.build_run_command(prompt)
    return adapter.build_session_command(session_id, prompt)


def _execute_prompt_round(
    *,
    executor: Executor,
    adapter: CLIAdapter,
    round_num: int,
    session_id: str,
    prompt: str,
    timeout: int,
    max_retries: int,
) -> ExecutionResult:
    """Execute one prompt round using the adapter's preferred transport."""
    command = _build_round_command(adapter, round_num, session_id, prompt)
    if _supports_stdin_pipe(adapter):
        return executor.run_with_popen(
            command=command,
            timeout=timeout,
            stdin_input=prompt,
            prompt=prompt,
        )
    return executor.run_with_retry(
        command=command,
        timeout=timeout,
        max_retries=max_retries,
        prompt=prompt,
    )


def _reload_hot_config(
    *,
    round_num: int,
    config_loader: ConfigLoader,
    config: AppConfig,
    adapter: CLIAdapter,
    session_manager: SessionManager,
    app_logger: logging.Logger,
) -> tuple[AppConfig, CLIAdapter, SessionManager]:
    """Reload config on demand and refresh runtime components if anything changed."""
    if round_num < 2:
        return config, adapter, session_manager

    try:
        new_config, changed = config_loader.reload()
    except (OSError, ValueError, ConfigError) as exc:
        app_logger.warning("Config reload failed at round %d: %s: %s", round_num, type(exc).__name__, exc)
        return config, adapter, session_manager

    if not changed:
        return config, adapter, session_manager

    previous_config = config
    updated_config = new_config
    updated_adapter, updated_session_manager = _refresh_runtime_components(
        session_manager=session_manager,
        adapter=adapter,
        previous_config=previous_config,
        new_config=updated_config,
    )
    app_logger.info(
        "Config hot-reloaded at round %d: %s",
        round_num,
        _summarize_config_changes(previous_config, updated_config),
    )
    return updated_config, updated_adapter, updated_session_manager


def _refresh_runtime_components(
    session_manager: SessionManager,
    adapter: CLIAdapter,
    previous_config: AppConfig,
    new_config: AppConfig,
) -> tuple[CLIAdapter, SessionManager]:
    """Apply hot-reloaded config while preserving session state."""
    active_adapter = adapter
    if new_config.cli.tool != previous_config.cli.tool:
        active_adapter = create_adapter(new_config.cli.tool, new_config.cli)
    session_manager.update_runtime(adapter=active_adapter, config=new_config)
    return active_adapter, session_manager


def _summarize_config_changes(
    previous_config: AppConfig,
    new_config: AppConfig,
    *,
    max_items: int = 6,
) -> str:
    """Return a compact summary of effective config field changes."""
    changes = diff_mapping(asdict(previous_config), asdict(new_config))
    if not changes:
        return "no effective field changes"

    preview = ", ".join(
        f"{field}: {truncate_text(repr(old), 40)} -> "
        f"{truncate_text(repr(new), 40)}"
        for field, (old, new) in list(changes.items())[:max_items]
    )
    remaining = len(changes) - max_items
    if remaining > 0:
        return f"{preview}, ... (+{remaining} more)"
    return preview


def main() -> None:
    """Main entry point for OpenCode Infinity.

    CLI interface: python opencode-infinity.py <session_id> [config_name]
    GUI interface: python opencode-infinity.py --gui
    """
    if "--gui" in sys.argv:
        _start_gui()
        return
    try:
        _run()
    except SystemExit:
        raise
    except KeyboardInterrupt:
        _sigint_handler(signal.SIGINT, None)
    except OpenCodeInfinityError as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        _main_logger.error("main: handled open-code error: %s: %s", type(exc).__name__, exc, exc_info=True)
        sys.exit(1)
    except Exception as exc:
        print(f"FATAL: Unhandled exception: {type(exc).__name__}: {exc}", file=sys.stderr)
        _main_logger.error("main: unhandled exception: %s: %s", type(exc).__name__, exc, exc_info=True)
        sys.exit(1)


def _run() -> None:
    """Internal main logic."""
    args = sys.argv[1:]

    if len(args) == 0 or len(args) > 2:
        print("Usage: python opencode-infinity.py <session_id> [config_name]", file=sys.stderr)
        print(
            "  session_id: Required when two arguments are supplied; a single non-session argument is treated as config_name.",
            file=sys.stderr,
        )
        print(f"  config_name: Optional config name or path (searches in '{_TASKS_YAML_DIR}/')", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  python opencode-infinity.py ses_docs codex     # 使用 codex.yaml", file=sys.stderr)
        print("  python opencode-infinity.py ses_abc123 codex   # 指定 session", file=sys.stderr)
        sys.exit(1)

    try:
        session_id, config_name = _resolve_launch_arguments(args)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    init_ansi_colors()

    app_logger = setup_logger("opencode_infinity")
    app_logger.info("OpenCode Infinity starting, session_id=%s", session_id)

    resolved_config_path: str = "<unresolved>"
    try:
        config_path = _resolve_config_path(config_name)
        resolved_config_path = str(config_path)
        config_loader = ConfigLoader(config_path)
        config = config_loader.load()
    except (ConfigError, OSError, ValueError) as exc:
        print(
            f"ERROR: Failed to load config '{resolved_config_path}': {exc}",
            file=sys.stderr,
        )
        app_logger.error(
            "_run: config load failed: %s: %s, path=%s",
            type(exc).__name__,
            exc,
            resolved_config_path,
        )
        sys.exit(1)

    app_logger.info("Config loaded: tool=%s, config_path=%s", config.cli.tool, config_path)

    try:
        adapter = create_adapter(config.cli.tool, config.cli)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        app_logger.error("_run: adapter creation failed: %s", exc)
        sys.exit(1)

    executor = Executor()
    session_manager = SessionManager(adapter, executor, config)

    _state.current_session_id = session_id
    _state.executor = executor
    _state.start_time = time.monotonic()

    signal.signal(signal.SIGINT, _sigint_handler)

    app_logger.info("Starting main loop, tool=%s", adapter.tool_name)

    prompt_index = 0

    while _state.running:
        _state.round_count += 1
        round_num = _state.round_count

        config, adapter, session_manager = _reload_hot_config(
            round_num=round_num,
            config_loader=config_loader,
            config=config,
            adapter=adapter,
            session_manager=session_manager,
            app_logger=app_logger,
        )

        if config.execution.max_rounds > 0:
            if round_num > config.execution.max_rounds:
                app_logger.info("Reached max_rounds=%d, stopping", config.execution.max_rounds)
                break

        current_prompt, prompt_index = _select_prompt(config.prompts, prompt_index)

        _display_round_info(round_num, session_id, config, current_prompt)

        session_manager.increment_round()
        if session_manager.should_switch(session_id):
            app_logger.info("Session switch triggered at round %d", round_num)
            try:
                new_session_id = session_manager.switch_session(session_id)
                session_id = new_session_id
                _state.current_session_id = session_id
                _state.session_count += 1
                app_logger.info("Switched to new session: %s", session_id)
            except (OSError, SessionError, ValueError) as exc:
                app_logger.warning("Session switch failed: %s: %s", type(exc).__name__, exc)

        use_stdin_pipe = _supports_stdin_pipe(adapter)

        if round_num == 1:
            command = adapter.build_run_command(current_prompt)
        else:
            command = adapter.build_session_command(session_id, current_prompt)

        app_logger.debug("Executing command for round %d: %s", round_num, command)

        if use_stdin_pipe:
            result = executor.run_with_popen(
                command=command, timeout=config.execution.timeout,
                stdin_input=current_prompt, prompt=current_prompt,
            )
        else:
            result = executor.run_with_retry(
                command=command, timeout=config.execution.timeout,
                max_retries=config.execution.max_retries, prompt=current_prompt,
            )

        if result.success:
            _state.success_count += 1
            app_logger.info("Round %d completed successfully (%.1fs)", round_num, result.duration_seconds)
        else:
            _state.fail_count += 1
            app_logger.warning("Round %d failed: return_code=%d, retries=%d", round_num, result.return_code, result.retry_count)
            if not config.execution.auto_continue_on_error:
                app_logger.info("auto_continue_on_error=False, stopping after failure")
                break

        if _state.running and config.execution.delay > 0:
            time.sleep(config.execution.delay)

    elapsed = time.monotonic() - _state.start_time
    elapsed_str = _format_elapsed_time(elapsed)
    total = _state.success_count + _state.fail_count
    success_rate = f"{_state.success_count}/{total}" if total > 0 else "0/0"

    print(file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    print("OpenCode Infinity - 執行完成", file=sys.stderr)
    print(f"  總執行輪次: {_state.round_count}", file=sys.stderr)
    print(f"  成功/失敗: {success_rate}", file=sys.stderr)
    print(f"  Session 數量: {_state.session_count}", file=sys.stderr)
    print(f"  總耗時: {elapsed_str}", file=sys.stderr)
    print("=" * 50, file=sys.stderr)


# =============================================================================
# Web GUI (Flask)
# =============================================================================

_gui_log_queue: queue.Queue[str] = queue.Queue(maxsize=10000)
_gui_state: dict[str, Any] = {
    "running": False,
    "round_count": 0,
    "session_count": 1,
    "start_time": 0.0,
    "config_name": "",
    "session_id": "",
    "thread": None,
    "stop_event": None,
    "process": None,
}


def _gui_log(message: str) -> None:
    """Push a log message to both the GUI queue and stderr."""
    timestamp = time.strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    try:
        _gui_log_queue.put_nowait(formatted)
    except queue.Full:
        try:
            _gui_log_queue.get_nowait()
            _gui_log_queue.put_nowait(formatted)
        except queue.Empty:
            pass
    print(formatted, file=sys.stderr)


def _gui_run_task(config_name: str, session_id: str, stop_event: threading.Event) -> None:
    """Background thread: run the execution loop with GUI logging."""
    _gui_log(f"🚀 啟動執行 - Config: {config_name}, Session: {session_id}")
    _gui_state["round_count"] = 0
    _gui_state["session_count"] = 1
    _gui_state["start_time"] = time.monotonic()

    try:
        config_path = _resolve_config_path(config_name)
        config_loader = ConfigLoader(config_path)
        config = config_loader.load()
    except (ConfigError, OSError, ValueError) as exc:
        _gui_log(f"❌ 設定載入失敗: {exc}")
        _gui_state["running"] = False
        return

    _gui_log(f"✅ 設定載入成功: tool={config.cli.tool}")

    try:
        adapter = create_adapter(config.cli.tool, config.cli)
    except (ValueError, CLIAdapterError) as exc:
        _gui_log(f"❌ CLI 適配器建立失敗: {exc}")
        _gui_state["running"] = False
        return

    executor = Executor()
    session_manager = SessionManager(adapter, executor, config)
    prompt_index = 0

    while not stop_event.is_set():
        _gui_state["round_count"] += 1
        round_num = _gui_state["round_count"]

        if config.execution.max_rounds > 0 and round_num > config.execution.max_rounds:
            _gui_log(f"🏁 已達最大輪次 {config.execution.max_rounds}，停止執行")
            break

        # Hot-reload config
        if round_num >= 2:
            try:
                new_config, changed = config_loader.reload()
                if changed:
                    previous_config = config
                    config = new_config
                    adapter, session_manager = _refresh_runtime_components(
                        session_manager=session_manager, adapter=adapter,
                        previous_config=previous_config, new_config=config,
                    )
                    _gui_log(
                        f"🔄 設定已熱重載: {_summarize_config_changes(previous_config, new_config)}"
                    )
            except (ConfigError, OSError, ValueError) as exc:
                _gui_log(f"⚠️ 設定熱重載失敗: {type(exc).__name__}: {exc}")

        current_prompt, prompt_index = _select_prompt(config.prompts, prompt_index)

        _gui_log(f"▶ Round {round_num} | Session: {session_id} | Prompt: {truncate_text(current_prompt, 60)}")

        session_manager.increment_round()
        if session_manager.should_switch(session_id):
            _gui_log("🔀 觸發 Session 切換...")
            try:
                new_session_id = session_manager.switch_session(session_id)
                session_id = new_session_id
                _gui_state["session_count"] += 1
                _gui_state["session_id"] = session_id
                _gui_log(f"✅ 切換到新 Session: {session_id}")
            except (OSError, SessionError, ValueError) as exc:
                _gui_log(f"⚠️ Session 切換失敗: {exc}")

        use_stdin_pipe = _supports_stdin_pipe(adapter)

        if round_num == 1:
            command = adapter.build_run_command(current_prompt)
        else:
            command = adapter.build_session_command(session_id, current_prompt)

        _gui_log(f"  執行命令: {' '.join(command[:3])}...")

        if use_stdin_pipe:
            result = executor.run_with_popen(
                command=command, timeout=config.execution.timeout,
                stdin_input=current_prompt, prompt=current_prompt,
            )
        else:
            result = executor.run_with_retry(
                command=command, timeout=config.execution.timeout,
                max_retries=config.execution.max_retries, prompt=current_prompt,
            )

        if result.success:
            _gui_log(f"  ✅ Round {round_num} 完成 ({result.duration_seconds:.1f}s)")
        else:
            _gui_log(f"  ❌ Round {round_num} 失敗 (code={result.return_code}, retries={result.retry_count})")
            if not config.execution.auto_continue_on_error:
                _gui_log("⛔ auto_continue_on_error=False，停止執行")
                break

        if stop_event.is_set():
            break

        if config.execution.delay > 0:
            for _ in range(config.execution.delay * 10):
                if stop_event.is_set():
                    break
                time.sleep(0.1)

    elapsed = time.monotonic() - _gui_state["start_time"]
    _gui_log(f"🏁 執行結束 - 輪次: {_gui_state['round_count']}, Session: {_gui_state['session_count']}, 耗時: {_format_elapsed_time(elapsed)}")
    _gui_state["running"] = False


def _start_gui() -> None:
    """Start the Flask web GUI server."""
    try:
        from flask import Flask, Response, jsonify, request
    except ImportError:
        print("ERROR: Flask 未安裝。請執行: pip install flask", file=sys.stderr)
        sys.exit(1)

    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False

    @app.route("/")
    def index():
        gui_path = Path(__file__).parent / "gui" / "index.html"
        if not gui_path.is_file():
            return "ERROR: gui/index.html not found", 404
        return Response(gui_path.read_text(encoding="utf-8"), mimetype="text/html")

    @app.route("/api/configs")
    def api_configs():
        configs_dir = Path(_TASKS_YAML_DIR)
        configs: list[str] = []
        if configs_dir.is_dir():
            for f in sorted(configs_dir.iterdir()):
                if f.suffix in (".yaml", ".yml"):
                    configs.append(f.name)
        return jsonify({"configs": configs})

    @app.route("/api/config/<name>")
    def api_config_content(name: str):
        configs_dir = Path(_TASKS_YAML_DIR)
        target = configs_dir / name
        if not target.is_file():
            return jsonify({"content": "檔案不存在"}), 404
        try:
            content = target.read_text(encoding="utf-8")
            return jsonify({"content": content})
        except OSError as exc:
            return jsonify({"content": f"讀取失敗: {exc}"}), 500

    @app.route("/api/start", methods=["POST"])
    def api_start():
        if _gui_state["running"]:
            return jsonify({"ok": False, "error": "已在執行中"})
        data = request.get_json(force=True, silent=True) or {}
        config_name = data.get("config", "")
        session_id = data.get("session_id", "").strip()
        if not config_name:
            return jsonify({"ok": False, "error": "未指定設定檔"})
        if not session_id:
            session_id = f"ses_{int(time.time())}"

        _gui_state["running"] = True
        _gui_state["config_name"] = config_name
        _gui_state["session_id"] = session_id
        _gui_state["round_count"] = 0
        _gui_state["session_count"] = 1

        stop_event = threading.Event()
        _gui_state["stop_event"] = stop_event

        t = threading.Thread(
            target=_gui_run_task,
            args=(config_name, session_id, stop_event),
            daemon=True,
        )
        _gui_state["thread"] = t
        t.start()

        return jsonify({"ok": True, "session_id": session_id})

    @app.route("/api/stop", methods=["POST"])
    def api_stop():
        if not _gui_state["running"]:
            return jsonify({"ok": False, "error": "目前未在執行"})
        stop_event = _gui_state.get("stop_event")
        if stop_event:
            stop_event.set()
        _gui_state["running"] = False
        _gui_log("⏹ 使用者請求停止")
        return jsonify({"ok": True})

    @app.route("/api/status")
    def api_status():
        elapsed_seconds = 0.0
        if _gui_state["start_time"] > 0 and _gui_state["running"]:
            elapsed_seconds = time.monotonic() - _gui_state["start_time"]
        minutes = int(elapsed_seconds) // 60
        seconds = int(elapsed_seconds) % 60
        elapsed_str = f"{minutes}:{seconds:02d}"
        return jsonify({
            "running": _gui_state["running"],
            "round_count": _gui_state["round_count"],
            "session_count": _gui_state["session_count"],
            "elapsed": elapsed_str,
            "config_name": _gui_state["config_name"],
            "session_id": _gui_state["session_id"],
        })

    @app.route("/api/logs")
    def api_logs():
        def generate():
            while True:
                try:
                    msg = _gui_log_queue.get(timeout=15)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        return Response(generate(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.route("/api/config/save", methods=["POST"])
    def api_config_save():
        data = request.get_json(force=True, silent=True) or {}
        filename = data.get("filename", "").strip()
        content = data.get("content", "")
        if not filename:
            return jsonify({"ok": False, "error": "未指定檔案名稱"}), 400
        # Security: reject path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            return jsonify({"ok": False, "error": "檔案名稱不合法（不允許路徑字元）"}), 400
        if not (filename.endswith(".yaml") or filename.endswith(".yml")):
            return jsonify({"ok": False, "error": "檔案名稱必須以 .yaml 或 .yml 結尾"}), 400
        # Validate it's valid YAML
        try:
            _load_yaml_mapping_from_text(content, source=f"GUI save payload: {filename}")
        except ConfigError as exc:
            return jsonify({"ok": False, "error": f"YAML 格式無效: {exc}"}), 400
        configs_dir = Path(_TASKS_YAML_DIR)
        configs_dir.mkdir(parents=True, exist_ok=True)
        target = configs_dir / filename
        try:
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return jsonify({"ok": False, "error": f"寫入失敗: {exc}"}), 500
        return jsonify({"ok": True, "path": str(target)})

    @app.route("/api/config/generate-yaml", methods=["POST"])
    def api_config_generate_yaml():
        data = request.get_json(force=True, silent=True) or {}
        try:
            yaml_str = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
            return jsonify({"yaml": yaml_str})
        except (TypeError, ValueError, yaml.YAMLError) as exc:
            return jsonify({"yaml": None, "error": str(exc)}), 500

    @app.route("/api/config/parse-yaml", methods=["POST"])
    def api_config_parse_yaml():
        data = request.get_json(force=True, silent=True) or {}
        content = data.get("content", "")
        try:
            parsed = _load_yaml_mapping_from_text(content, source="GUI parse payload")
            # If top-level has a single key wrapping the config, unwrap it
            keys = list(parsed.keys())
            if len(keys) == 1 and isinstance(parsed[keys[0]], dict):
                # Check if it looks like a named config (has nested task/cli/execution)
                inner = parsed[keys[0]]
                if any(k in inner for k in ("task", "cli", "execution", "prompts")):
                    parsed = inner
            return jsonify({"config": parsed})
        except ConfigError as exc:
            return jsonify({"error": f"YAML 解析失敗: {exc}"}), 400

    port = 8080
    print(f"🌐 OpenCode Infinity Web GUI 啟動中...", file=sys.stderr)
    print(f"   http://localhost:{port}", file=sys.stderr)

    # Open browser after a short delay
    def _open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=_open_browser, daemon=True).start()

    # Suppress Flask's default banner for cleaner output
    import logging as _logging
    _logging.getLogger("werkzeug").setLevel(_logging.WARNING)

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
