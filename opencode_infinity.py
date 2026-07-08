#!/usr/bin/env python3
"""OpenCode Infinity - 單一檔案版本.

自動化 AI 編碼工具的無限循環執行器，支援 OpenCode、Claude Code、Codex、Copilot。
"""

from __future__ import annotations

# =============================================================================
# 標準庫 imports
# =============================================================================
import itertools
import random
import socket
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
from collections import deque
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


_ANSI_ESCAPE_RE: re.Pattern[str] = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Remove terminal ANSI color/control sequences from CLI output."""
    return _ANSI_ESCAPE_RE.sub("", text)


def _configure_stdio_encoding() -> None:
    """Best-effort UTF-8 stdio on Windows consoles and PyInstaller builds."""
    if sys.platform != "win32":
        return
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _eprint(*args: object, **kwargs: object) -> None:
    """Print to stderr without crashing on legacy Windows code pages."""
    kwargs.setdefault("file", sys.stderr)
    file = kwargs["file"]
    text = " ".join(str(arg) for arg in args)
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        encoding = getattr(file, "encoding", None) or "utf-8"
        safe = text.encode(encoding, errors="replace").decode(
            encoding, errors="replace"
        )
        print(safe, **{k: v for k, v in kwargs.items() if k != "file"}, file=file)


def _desktop_log_path() -> Path:
    log_dir = _get_user_config_dir().parent
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "desktop.log"


def _desktop_log(message: str) -> None:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _desktop_log_path().open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _show_fatal_error(title: str, message: str) -> None:
    _desktop_log(f"FATAL {title}: {message}")
    _eprint(f"ERROR: {message}")
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        except Exception:
            pass


def _pick_listen_port(preferred: int) -> int:
    """Return a localhost TCP port that can be bound, preferring the requested one."""
    candidates = [preferred]
    for offset in range(1, 32):
        candidates.append(preferred + offset)
    for port in candidates:
        if port < 1 or port > 65535:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise ConfigError(f"No available local port found near {preferred}")


def safe_int(
    value: object,
    default: int,
    minimum: Optional[int] = None,
    maximum: Optional[int] = None,
) -> int:
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


def compact_strings(
    items: Iterable[Optional[str]], *, strip: bool = True, drop_empty: bool = True
) -> list[str]:
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


def flatten_dict(
    mapping: Mapping[str, object], *, separator: str = ".", prefix: str = ""
) -> dict[str, object]:
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


def diff_mapping(
    before: Mapping[str, object], after: Mapping[str, object], *, separator: str = "."
) -> dict[str, tuple[object, object]]:
    """Return flattened key-level differences between two mappings."""
    before_flat = flatten_dict(dict(before), separator=separator)
    after_flat = flatten_dict(dict(after), separator=separator)
    return {
        key: (before_flat.get(key), after_flat.get(key))
        for key in sorted(before_flat.keys() | after_flat.keys())
        if before_flat.get(key) != after_flat.get(key)
    }


_SLUGIFY_RE: re.Pattern[str] = re.compile(r"[^\w\s-]")
_SLUGIFY_WHITESPACE_RE: re.Pattern[str] = re.compile(r"[-\s]+")


def slugify(text: str, *, lower: bool = True, separator: str = "-") -> str:
    """Convert a string to a URL/filesystem-safe slug."""
    result = _SLUGIFY_RE.sub("", text).strip()
    result = _SLUGIFY_WHITESPACE_RE.sub(separator, result)
    return result.lower() if lower else result


def chunk_iterable(items: Iterable[object], size: int) -> list[list[object]]:
    """Split an iterable into fixed-size chunks (last chunk may be smaller)."""
    iterator = iter(items)
    chunks: list[list[object]] = []
    while True:
        chunk = list(itertools.islice(iterator, size))
        if not chunk:
            break
        chunks.append(chunk)
    return chunks


def format_bytes(n: int, *, decimal: bool = False) -> str:
    """Format a byte count as a human-readable string (e.g. 1.5 KiB)."""
    if decimal:
        units = ("B", "KB", "MB", "GB", "TB", "PB")
        divisor = 1000.0
    else:
        units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
        divisor = 1024.0
    if n < divisor:
        return f"{n} {units[0]}"
    for unit in units[1:]:
        n /= divisor
        if abs(n) < divisor:
            return f"{n:.1f} {unit}"
    return f"{n:.1f} {units[-1]}"


def merge_dicts_deep(*dicts: Mapping[str, object]) -> dict[str, object]:
    """Deep-merge multiple dictionaries (later dicts override earlier ones)."""
    result: dict[str, object] = {}
    for d in dicts:
        for key, value in d.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = merge_dicts_deep(result[key], value)
            else:
                result[key] = value
    return result


_ID_CHARS: str = "abcdefghijklmnopqrstuvwxyz0123456789"


def generate_short_id(length: int = 8) -> str:
    """Generate a short alphanumeric ID (not cryptographically secure)."""
    return "".join(random.choice(_ID_CHARS) for _ in range(length))


def ensure_dir(path: Path, *, mode: int = 0o755) -> Path:
    """Ensure a directory exists and is writable; raise on failure."""
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise OSError(f"Not a directory: {path}")
    return path


_DURATION_RE: re.Pattern[str] = re.compile(
    r"(?:(\d+)\s*d(?:ays?)?\s*)?"
    r"(?:(\d+)\s*h(?:ours?)?\s*)?"
    r"(?:(\d+)\s*m(?:in(?:utes?)?)?\s*)?"
    r"(?:(\d+)\s*s(?:ec(?:onds?)?)?\s*)?",
    re.IGNORECASE,
)


def parse_duration(text: str, *, default: int = 0) -> int:
    """Parse a human-readable duration string into seconds.

    Supported formats: "1d", "2h30m", "45s", "1d 6h", "30m".
    """
    text = text.strip()
    if not text:
        return default
    match = _DURATION_RE.fullmatch(text)
    if not match:
        return default
    days, hours, minutes, seconds = (int(v) if v else 0 for v in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


_INVALID_FILENAME_CHARS_RE: re.Pattern[str] = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(text: str, *, replacement: str = "_", max_length: int = 128) -> str:
    """Strip or replace characters that are invalid in filenames."""
    result = _INVALID_FILENAME_CHARS_RE.sub(replacement, text).strip()
    result = _SLUGIFY_WHITESPACE_RE.sub(replacement, result)
    if not result:
        result = "untitled"
    return result[:max_length].rstrip(". ")


# =============================================================================
# 資料模型 (models)
# =============================================================================


@dataclass(frozen=True)
class CLIConfig:
    """CLI tool configuration."""

    tool: str = "opencode"
    full_auto: bool = False
    model: Optional[str] = None
    search: bool = False
    allowed_tools: Optional[str] = None
    permission_mode: Optional[str] = None
    mcp_server: Optional[str] = None


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
    max_tokens: int = 128000
    token_threshold: float = 0.7
    working_dir: str = ""  # empty = inherit parent process cwd for CLI subprocesses


@dataclass(frozen=True)
class DisplayConfig:
    """Display settings configuration."""

    show_session_id: bool = True
    show_timestamp: bool = True


@dataclass(frozen=True)
class AppConfig:
    """Top-level application configuration combining all sections."""

    cli: CLIConfig = field(default_factory=CLIConfig)
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
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
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

CLI_DEFAULTS: dict[str, Any] = {
    "tool": "opencode",
    "full_auto": False,
    "model": None,
    "search": False,
    "allowed_tools": None,
    "permission_mode": None,
    "mcp_server": None,
}

EXECUTION_DEFAULTS: dict[str, Any] = {
    "delay": 1,
    "timeout": 300,
    "max_retries": 5,
    "auto_continue_on_error": True,
    "max_rounds": 0,
    "switch_after_rounds": 0,
    "switch_strategy": "auto",
    "max_tokens": 128000,
    "token_threshold": 0.7,
    "working_dir": "",
}

DISPLAY_DEFAULTS: dict[str, Any] = {
    "show_session_id": True,
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


CLI_SCHEMA: dict[str, FieldSchema] = {
    "tool": FieldSchema(
        field_type=FieldType.STR,
        required=True,
        valid_values=("opencode", "claude", "codex", "copilot"),
    ),
    "full_auto": FieldSchema(field_type=FieldType.BOOL, required=False),
    "model": FieldSchema(field_type=FieldType.OPTIONAL_STR, required=False),
    "search": FieldSchema(field_type=FieldType.BOOL, required=False),
    "allowed_tools": FieldSchema(field_type=FieldType.OPTIONAL_STR, required=False),
    "permission_mode": FieldSchema(field_type=FieldType.OPTIONAL_STR, required=False),
    "mcp_server": FieldSchema(field_type=FieldType.OPTIONAL_STR, required=False),
}

EXECUTION_SCHEMA: dict[str, FieldSchema] = {
    "delay": FieldSchema(field_type=FieldType.INT, required=False, min_value=0),
    "timeout": FieldSchema(field_type=FieldType.INT, required=False, min_value=0),
    "max_retries": FieldSchema(field_type=FieldType.INT, required=False, min_value=0),
    "auto_continue_on_error": FieldSchema(field_type=FieldType.BOOL, required=False),
    "max_rounds": FieldSchema(field_type=FieldType.INT, required=False, min_value=0),
    "switch_after_rounds": FieldSchema(
        field_type=FieldType.INT, required=False, min_value=0
    ),
    "switch_strategy": FieldSchema(
        field_type=FieldType.STR,
        required=False,
        valid_values=("auto", "token", "rounds"),
    ),
    "max_tokens": FieldSchema(field_type=FieldType.INT, required=False, min_value=1),
    "token_threshold": FieldSchema(
        field_type=FieldType.FLOAT, required=False, min_value=0.0, max_value=1.0
    ),
    "working_dir": FieldSchema(field_type=FieldType.STR, required=False),
}

DISPLAY_SCHEMA: dict[str, FieldSchema] = {
    "show_session_id": FieldSchema(field_type=FieldType.BOOL, required=False),
    "show_timestamp": FieldSchema(field_type=FieldType.BOOL, required=False),
}

PROMPTS_SCHEMA: FieldSchema = FieldSchema(field_type=FieldType.LIST, required=False)
SUMMARY_PROMPT_SCHEMA: FieldSchema = FieldSchema(
    field_type=FieldType.STR, required=False
)

SECTION_SCHEMAS: dict[str, dict[str, FieldSchema]] = {
    "cli": CLI_SCHEMA,
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
        raise ConfigError(
            f"Config file must contain a YAML mapping, got {type(raw).__name__}"
        )
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
            errors.append(
                ValidationError(
                    field_path="<root>",
                    message="Configuration must be a YAML mapping (dictionary)",
                    severity="error",
                )
            )
            return errors

        unknown_top_level = raw.keys() - ALL_KNOWN_SECTIONS
        for key in unknown_top_level:
            errors.append(
                ValidationError(
                    field_path=key,
                    message=f"Unknown configuration field '{key}' (possible typo?)",
                    severity="warning",
                )
            )

        for section_name, section_schema in SECTION_SCHEMAS.items():
            section_data = raw.get(section_name)
            if section_data is None:
                required_fields = [
                    fname
                    for fname, fschema in section_schema.items()
                    if fschema.required
                ]
                if required_fields:
                    for fname in required_fields:
                        errors.append(
                            ValidationError(
                                field_path=f"{section_name}.{fname}",
                                message=f"Required field '{fname}' is missing from section '{section_name}'",
                                severity="error",
                            )
                        )
                continue

            if not isinstance(section_data, dict):
                errors.append(
                    ValidationError(
                        field_path=section_name,
                        message=f"Section '{section_name}' must be a mapping",
                        severity="error",
                    )
                )
                continue

            errors.extend(
                self._validate_section(section_name, section_data, section_schema)
            )

        for field_name, field_schema in TOP_LEVEL_FIELDS.items():
            value = raw.get(field_name)
            if value is not None:
                if not _matches_field_type(value, field_schema.field_type):
                    errors.append(
                        ValidationError(
                            field_path=field_name,
                            message=f"Field '{field_name}' must be of type {field_schema.field_type.value}, got {type(value).__name__}",
                            severity="error",
                        )
                    )

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
        fatal_errors = [
            error for error in validation_errors if error.severity == "error"
        ]
        if not fatal_errors:
            return

        formatted_errors = [
            f"{error.field_path}: {error.message}" for error in fatal_errors
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
        self,
        raw: dict[str, Any],
        field_name: str,
        default: int,
        minimum: int,
        warning_prefix: str,
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
        self,
        raw: dict[str, Any],
        field_name: str,
        default: float,
        warning_prefix: str,
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
        self._warn(
            f"{warning_prefix} value {raw_value} is out of range [0.0, 1.0], using default {default}"
        )
        return default

    def _read_yaml(self) -> dict[str, Any]:
        try:
            content = self._config_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigError(
                f"Cannot read config file '{self._config_path}': {exc}"
            ) from exc
        raw = _load_yaml_mapping_from_text(content, source=str(self._config_path))
        return raw

    def _validate_section(
        self,
        section_name: str,
        section_data: dict[str, Any],
        section_schema: dict[str, Any],
    ) -> list[ValidationError]:
        errors: list[ValidationError] = []

        for key in section_data:
            if key not in section_schema:
                errors.append(
                    ValidationError(
                        field_path=f"{section_name}.{key}",
                        message=f"Unknown field '{key}' in section '{section_name}' (possible typo?)",
                        severity="warning",
                    )
                )

        for fname, fschema in section_schema.items():
            value = section_data.get(fname)
            if value is None and fschema.required:
                errors.append(
                    ValidationError(
                        field_path=f"{section_name}.{fname}",
                        message=f"Required field '{fname}' is missing from section '{section_name}'",
                        severity="error",
                    )
                )
                continue
            if value is None:
                continue

            if not _matches_field_type(value, fschema.field_type):
                errors.append(
                    ValidationError(
                        field_path=f"{section_name}.{fname}",
                        message=f"Field '{fname}' must be of type {fschema.field_type.value}, got {type(value).__name__}",
                        severity="error",
                    )
                )
                continue

            if fschema.min_value is not None and value < fschema.min_value:
                errors.append(
                    ValidationError(
                        field_path=f"{section_name}.{fname}",
                        message=f"Field '{fname}' value {value} is below minimum {fschema.min_value}, using default",
                        severity="warning",
                    )
                )
            if fschema.max_value is not None and value > fschema.max_value:
                errors.append(
                    ValidationError(
                        field_path=f"{section_name}.{fname}",
                        message=f"Field '{fname}' value {value} is above maximum {fschema.max_value}, using default",
                        severity="warning",
                    )
                )
            if fschema.valid_values is not None and value not in fschema.valid_values:
                errors.append(
                    ValidationError(
                        field_path=f"{section_name}.{fname}",
                        message=f"Field '{fname}' value '{value}' is not one of {fschema.valid_values}",
                        severity="warning",
                    )
                )

        return errors

    def _build_config(self, raw: dict[str, Any]) -> AppConfig:
        cli = self._build_cli_config(raw.get("cli", {}))
        execution = self._build_execution_config(raw.get("execution", {}))
        display = self._build_display_config(raw.get("display", {}))
        prompts = self._normalize_prompts(raw.get("prompts"))
        summary_prompt = self._normalize_summary_prompt(raw.get("summary_prompt"))

        return AppConfig(
            cli=cli,
            execution=execution,
            display=display,
            prompts=prompts,
            summary_prompt=summary_prompt,
        )

    def _normalize_prompts(self, raw_prompts: Any) -> list[str]:
        if not isinstance(raw_prompts, list):
            return list(PROMPTS_DEFAULT)
        string_prompts = [item for item in raw_prompts if isinstance(item, str)]
        normalized = [
            normalize_newlines(prompt) for prompt in compact_strings(string_prompts)
        ]
        if normalized:
            return normalized
        return list(PROMPTS_DEFAULT)

    def _normalize_summary_prompt(self, raw_summary_prompt: Any) -> str:
        if not isinstance(raw_summary_prompt, str):
            return SUMMARY_PROMPT_DEFAULT
        return normalize_newlines(raw_summary_prompt)

    def _build_cli_config(self, raw: Any) -> CLIConfig:
        if not isinstance(raw, dict):
            return CLIConfig()
        tool = raw.get("tool", CLI_DEFAULTS["tool"])
        normalized_tool = (
            tool.strip().lower() if isinstance(tool, str) else CLI_DEFAULTS["tool"]
        )
        return CLIConfig(
            tool=normalized_tool,
            full_auto=raw.get("full_auto", CLI_DEFAULTS["full_auto"]),
            model=raw.get("model", CLI_DEFAULTS["model"]),
            search=raw.get("search", CLI_DEFAULTS["search"]),
            allowed_tools=raw.get("allowed_tools", CLI_DEFAULTS["allowed_tools"]),
            permission_mode=raw.get("permission_mode", CLI_DEFAULTS["permission_mode"]),
            mcp_server=raw.get("mcp_server", CLI_DEFAULTS["mcp_server"]),
        )

    def _build_execution_config(self, raw: Any) -> ExecutionConfig:
        if not isinstance(raw, dict):
            return ExecutionConfig()
        delay = self._coerce_bounded_int(
            raw=raw,
            field_name="delay",
            default=EXECUTION_DEFAULTS["delay"],
            minimum=0,
            warning_prefix="execution.delay",
        )
        timeout = self._coerce_bounded_int(
            raw=raw,
            field_name="timeout",
            default=EXECUTION_DEFAULTS["timeout"],
            minimum=0,
            warning_prefix="execution.timeout",
        )
        max_retries = self._coerce_bounded_int(
            raw=raw,
            field_name="max_retries",
            default=EXECUTION_DEFAULTS["max_retries"],
            minimum=0,
            warning_prefix="execution.max_retries",
        )
        max_rounds = self._coerce_bounded_int(
            raw=raw,
            field_name="max_rounds",
            default=EXECUTION_DEFAULTS["max_rounds"],
            minimum=0,
            warning_prefix="execution.max_rounds",
        )
        switch_after_rounds = self._coerce_bounded_int(
            raw=raw,
            field_name="switch_after_rounds",
            default=EXECUTION_DEFAULTS["switch_after_rounds"],
            minimum=0,
            warning_prefix="execution.switch_after_rounds",
        )
        max_tokens = self._coerce_bounded_int(
            raw=raw,
            field_name="max_tokens",
            default=EXECUTION_DEFAULTS["max_tokens"],
            minimum=1,
            warning_prefix="execution.max_tokens",
        )
        token_threshold = self._coerce_unit_interval_float(
            raw=raw,
            field_name="token_threshold",
            default=EXECUTION_DEFAULTS["token_threshold"],
            warning_prefix="execution.token_threshold",
        )
        working_dir = raw.get("working_dir", EXECUTION_DEFAULTS["working_dir"])
        if working_dir is None:
            working_dir = ""
        elif not isinstance(working_dir, str):
            self._warn("execution.working_dir must be a string, using empty value")
            working_dir = ""
        else:
            working_dir = working_dir.strip()
        return ExecutionConfig(
            delay=delay,
            timeout=timeout,
            max_retries=max_retries,
            auto_continue_on_error=raw.get(
                "auto_continue_on_error", EXECUTION_DEFAULTS["auto_continue_on_error"]
            ),
            max_rounds=max_rounds,
            switch_after_rounds=switch_after_rounds,
            switch_strategy=raw.get(
                "switch_strategy", EXECUTION_DEFAULTS["switch_strategy"]
            ),
            max_tokens=max_tokens,
            token_threshold=token_threshold,
            working_dir=working_dir,
        )

    def _build_display_config(self, raw: Any) -> DisplayConfig:
        if not isinstance(raw, dict):
            return DisplayConfig()
        return DisplayConfig(
            show_session_id=raw.get(
                "show_session_id", DISPLAY_DEFAULTS["show_session_id"]
            ),
            show_timestamp=raw.get(
                "show_timestamp", DISPLAY_DEFAULTS["show_timestamp"]
            ),
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


_MAX_MODEL_NAME_LENGTH: int = 128


def _validate_model_name(model: str) -> None:
    if not model:
        raise CLIAdapterError("Model name must not be empty when specified.")
    if len(model) > _MAX_MODEL_NAME_LENGTH:
        raise CLIAdapterError(
            f"Model name exceeds maximum length of {_MAX_MODEL_NAME_LENGTH} characters (got {len(model)})."
        )


def _ensure_windows_user_path() -> None:
    """Merge user-level PATH entries for Windows GUI / frozen builds."""
    if sys.platform != "win32":
        return
    try:
        import winreg
    except ImportError:
        return

    path_parts: list[str] = []
    existing = os.environ.get("PATH", "")
    if existing:
        path_parts.append(existing)

    for hive, subkey in (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ):
        try:
            with winreg.OpenKey(hive, subkey) as key:
                user_path, _ = winreg.QueryValueEx(key, "Path")
                if user_path:
                    path_parts.append(user_path)
        except OSError:
            continue

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        path_parts.append(str(Path(appdata) / "npm"))

    merged: list[str] = []
    seen: set[str] = set()
    for part in path_parts:
        for segment in part.split(os.pathsep):
            normalized = segment.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(normalized)

    os.environ["PATH"] = os.pathsep.join(merged)


def _find_cli_tool(name: str) -> Optional[str]:
    """Resolve a CLI executable after ensuring Windows user PATH is loaded."""
    _ensure_windows_user_path()
    return shutil.which(name)


_opencode_auto_flag_cache: dict[str, bool] = {}


def _opencode_cli_supports_auto(executable: str) -> bool:
    """Return True when this opencode build exposes `run --auto`."""
    cached = _opencode_auto_flag_cache.get(executable)
    if cached is not None:
        return cached
    supports = False
    try:
        result = subprocess.run(
            [executable, "run", "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=get_creation_flags(),
            stdin=subprocess.DEVNULL,
        )
        help_text = (result.stdout or "") + (result.stderr or "")
        supports = "--auto" in help_text
    except (OSError, subprocess.TimeoutExpired, ValueError):
        supports = False
    _opencode_auto_flag_cache[executable] = supports
    return supports


class OpenCodeAdapter(CLIAdapter):
    """Adapter for the OpenCode CLI tool."""

    _MIN_PROMPT_LENGTH: int = 1
    _MAX_PROMPT_LENGTH: int = 100_000

    def __init__(self, config: CLIConfig) -> None:
        self._config = config
        executable = _find_cli_tool("opencode")
        if executable is None:
            raise CLIAdapterError(
                "opencode executable not found. "
                "Please ensure opencode is installed and available in PATH."
            )
        self._executable = executable
        self._supports_auto = _opencode_cli_supports_auto(executable)
        if config.model is not None:
            _validate_model_name(config.model)

    def _model_flags(self) -> list[str]:
        if self._config.model:
            return ["-m", self._config.model]
        return []

    def _stream_flags(self) -> list[str]:
        """Flags that make headless subprocess runs emit progress on stderr."""
        return ["--print-logs"]

    def _headless_flags(self) -> list[str]:
        """Flags for unattended subprocess runs (auto-approve permission prompts)."""
        if self._supports_auto:
            return ["--auto"]
        return []

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
        return [
            self._executable,
            "run",
            *self._stream_flags(),
            *self._headless_flags(),
            *self._model_flags(),
            prompt,
        ]

    def build_session_command(self, session_id: str, prompt: str) -> list[str]:
        self._validate_prompt(prompt)
        # OpenCode assigns its own session IDs on `run`. Infinity's ses_* IDs are
        # not valid; use --continue to resume the last session in this directory.
        return [
            self._executable,
            "run",
            *self._stream_flags(),
            *self._headless_flags(),
            "-c",
            *self._model_flags(),
            prompt,
        ]

    def build_export_command(self, session_id: str) -> Optional[list[str]]:
        return [self._executable, "export", session_id]

    def build_stats_command(self) -> list[str]:
        return [self._executable, "stats"]

    @property
    def supports_token_stats(self) -> bool:
        return True

    @property
    def tool_name(self) -> str:
        return "OpenCode"


class CodexAdapter(CLIAdapter):
    """Adapter for the Codex CLI tool (v0.130+, Rust rewrite).

    Since Codex CLI 0.130 the ``--full-auto`` flag no longer exists.
    The ``exec`` subcommand is already non-interactive (approval: never).
    Flags available differ between ``exec`` and ``exec resume``:
      - exec: -m, -s, --skip-git-repo-check, -c, --dangerously-bypass-approvals-and-sandbox
      - exec resume: -m, --skip-git-repo-check, -c, --dangerously-bypass-approvals-and-sandbox
    Note: --search is NOT available on exec; use -c "search=true" instead.
    """

    def __init__(self, config: CLIConfig) -> None:
        self._config = config
        if config.model is not None:
            _validate_model_name(config.model)

    def _build_exec_flags(self) -> list[str]:
        """Build flags for ``codex exec [PROMPT]``."""
        flags: list[str] = []
        if self._config.full_auto:
            # Legacy full_auto: bypass all safety
            flags.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            # Default: workspace-write sandbox (exec already defaults to approval: never)
            flags.extend(["-s", "workspace-write"])
        if self._config.model is not None:
            flags.extend(["-m", self._config.model])
        if self._config.search:
            flags.extend(["-c", "search=true"])
        flags.append("--skip-git-repo-check")
        return flags

    def _build_resume_flags(self) -> list[str]:
        """Build flags for ``codex exec resume``."""
        flags: list[str] = []
        if self._config.full_auto:
            flags.append("--dangerously-bypass-approvals-and-sandbox")
        if self._config.model is not None:
            flags.extend(["-m", self._config.model])
        flags.append("--skip-git-repo-check")
        return flags

    def build_run_command(self, prompt: str) -> list[str]:
        if not prompt:
            raise CLIAdapterError("Prompt must not be empty")
        cmd: list[str] = ["codex", "exec"]
        cmd.extend(self._build_exec_flags())
        return cmd

    def build_session_command(self, session_id: str, prompt: str) -> list[str]:
        if not prompt:
            raise CLIAdapterError("Prompt must not be empty")
        cmd: list[str] = ["codex", "exec", "resume", "--last"]
        cmd.extend(self._build_resume_flags())
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
        return OpenCodeAdapter(config)
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
            process.pid,
            _TERMINATE_TIMEOUT_SECONDS,
        )
        try:
            process.kill()
            process.wait()
        except OSError as exc:
            _platform_logger.debug("terminate_process: kill() raised OSError: %s", exc)


def get_creation_flags() -> int:
    """Return platform-appropriate subprocess creation flags."""
    if IS_WINDOWS:
        flags = 0x00000200  # CREATE_NEW_PROCESS_GROUP
        if getattr(sys, "frozen", False):
            # Windowed exe has no console; prevent child console windows.
            flags |= 0x08000000  # CREATE_NO_WINDOW
        return flags
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
        _platform_logger.debug(
            "Windows Virtual Terminal Processing enabled successfully"
        )
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

_OPENCODE_DESKTOP_ENV_KEYS: tuple[str, ...] = (
    "OPENCODE_SERVER_PASSWORD",
    "OPENCODE_SERVER_USERNAME",
    "OPENCODE_CLIENT",
)

_SUBPROCESS_STDERR_FAILURE_PATTERNS: tuple[str, ...] = (
    "session not found",
    "notfounderror",
)


def _is_opencode_command(command: list[str]) -> bool:
    if not command:
        return False
    executable = Path(command[0])
    stem = executable.stem.lower()
    return stem == "opencode"


def _subprocess_env_for_command(command: list[str]) -> dict[str, str]:
    """Build subprocess env, stripping OpenCode Desktop vars for CLI isolation."""
    env = os.environ.copy()
    if _is_opencode_command(command):
        for key in _OPENCODE_DESKTOP_ENV_KEYS:
            env.pop(key, None)
        if not _opencode_cli_supports_auto(command[0]):
            env["OPENCODE_PERMISSION"] = '{"*":"allow"}'
    return env


def _stderr_indicates_failure(stderr_text: str) -> bool:
    lower = stderr_text.lower()
    return any(pattern in lower for pattern in _SUBPROCESS_STDERR_FAILURE_PATTERNS)


def _evaluate_subprocess_success(return_code: int, stderr_text: str) -> bool:
    if return_code != 0:
        return False
    return not _stderr_indicates_failure(stderr_text)


def _subprocess_failure_message(return_code: int, stderr_text: str) -> str:
    if return_code == 0 and _stderr_indicates_failure(stderr_text):
        return "Command exited 0 but stderr indicates failure (e.g. Session not found)"
    return f"Command exited with code {return_code}"


class Executor:
    """Executes subprocess commands with retry, timeout, and cleanup."""

    def __init__(
        self,
        sanitizer: Optional[InputSanitizer] = None,
        *,
        working_dir: Optional[Path] = None,
    ) -> None:
        self._sanitizer = sanitizer if sanitizer is not None else InputSanitizer()
        self._working_dir = working_dir

    def _subprocess_cwd(self) -> Optional[str]:
        if self._working_dir is None:
            return None
        return str(self._working_dir)

    def run_with_retry(
        self,
        command: list[str],
        timeout: int,
        max_retries: int,
        prompt: Optional[str] = None,
        stdin_input: Optional[str] = None,
        on_output_line: Optional[Callable[[str], None]] = None,
    ) -> ExecutionResult:
        """Execute a command with retry logic and exponential backoff."""
        start_time = time.monotonic()
        validation_error = self._validate_invocation(command, timeout, max_retries)
        if validation_error is not None:
            return self._build_immediate_failure(
                start_time=start_time,
                exception_type="ValueError",
                message=validation_error,
            )

        sanitization_failure = self._sanitize_prompt(
            start_time, prompt, command, "run_with_retry"
        )
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
                    if on_output_line is not None:
                        return_code, last_stdout, last_stderr = (
                            self._execute_once_streaming(
                                resolved_command,
                                attempt_timeout,
                                stdin_input=stdin_bytes,
                                on_output_line=on_output_line,
                            )
                        )
                        result = subprocess.CompletedProcess(
                            args=resolved_command,
                            returncode=return_code,
                            stdout=last_stdout.encode("utf-8", errors="replace"),
                            stderr=last_stderr.encode("utf-8", errors="replace"),
                        )
                    else:
                        result = self._execute_once(
                            command=resolved_command,
                            timeout=attempt_timeout,
                            stdin_input=stdin_bytes,
                            temp_files=temp_files,
                        )
                    last_stdout = self._decode_output(result.stdout)
                    last_stderr = self._decode_output(result.stderr)
                    if _evaluate_subprocess_success(result.returncode, last_stderr):
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
                        attempt=attempt + 1,
                        timestamp=utc_now_iso(),
                        return_code=result.returncode,
                        message=_subprocess_failure_message(
                            result.returncode, last_stderr
                        ),
                    )
                    errors.append(error)
                    _executor_logger.warning(
                        "run_with_retry: attempt %d/%d failed, return_code=%d, command=%s",
                        attempt + 1,
                        max_retries + 1,
                        result.returncode,
                        command,
                    )
                    if on_output_line is not None:
                        on_output_line(
                            f"[retry] 第 {attempt + 1}/{max_retries + 1} 次嘗試失敗 "
                            f"(exit code {result.returncode})"
                        )

                except subprocess.TimeoutExpired:
                    error = RetryError(
                        attempt=attempt + 1,
                        timestamp=utc_now_iso(),
                        exception_type="TimeoutExpired",
                        message=f"Command timed out after {attempt_timeout}s",
                    )
                    errors.append(error)
                    _executor_logger.warning(
                        "run_with_retry: attempt %d/%d timed out, timeout=%ds, command=%s",
                        attempt + 1,
                        max_retries + 1,
                        attempt_timeout,
                        command,
                    )
                    if on_output_line is not None:
                        on_output_line(
                            f"[timeout] 第 {attempt + 1}/{max_retries + 1} 次嘗試逾時 "
                            f"({attempt_timeout}s 無回應)"
                        )

                except OSError as exc:
                    error = RetryError(
                        attempt=attempt + 1,
                        timestamp=utc_now_iso(),
                        exception_type=type(exc).__name__,
                        message=str(exc),
                    )
                    errors.append(error)
                    _executor_logger.error(
                        "run_with_retry: attempt %d/%d raised %s: %s, command=%s",
                        attempt + 1,
                        max_retries + 1,
                        type(exc).__name__,
                        exc,
                        command,
                    )
                    if on_output_line is not None:
                        on_output_line(
                            f"[error] 第 {attempt + 1}/{max_retries + 1} 次嘗試發生錯誤: "
                            f"{type(exc).__name__}: {exc}"
                        )

                if attempt < max_retries:
                    backoff_wait = min(min(2**attempt, _MAX_BACKOFF_SECONDS), 10)
                    if on_output_line is not None:
                        on_output_line(f"[retry] {backoff_wait}s 後重試...")
                    time.sleep(backoff_wait)

            duration = time.monotonic() - start_time
            final_return_code = (
                errors[-1].return_code
                if errors and errors[-1].return_code is not None
                else -1
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
        on_output_line: Optional[Callable[[str], None]] = None,
    ) -> ExecutionResult:
        """Execute a command using Popen for stdin pipe support.

        When capture_output=False (default), stdout/stderr are inherited from
        the terminal so the user sees real-time output from the subprocess.
        When on_output_line is set, output is streamed to the callback instead.
        When capture_output=True, output is captured into ExecutionResult fields.
        """
        start_time = time.monotonic()
        validation_error = self._validate_invocation(command, timeout, 0)
        if validation_error is not None:
            return self._build_immediate_failure(
                start_time=start_time,
                exception_type="ValueError",
                message=validation_error,
            )

        sanitization_failure = self._sanitize_prompt(
            start_time, prompt, command, "run_with_popen"
        )
        if sanitization_failure is not None:
            return sanitization_failure

        temp_files: list[Path] = []
        stdin_bytes = stdin_input.encode("utf-8") if stdin_input else None

        try:
            if on_output_line is not None:
                try:
                    return_code, stdout_text, stderr_text = (
                        self._execute_once_streaming(
                            self._resolve_command(command),
                            timeout,
                            stdin_input=stdin_bytes,
                            on_output_line=on_output_line,
                        )
                    )
                except subprocess.TimeoutExpired:
                    duration = time.monotonic() - start_time
                    return ExecutionResult(
                        success=False,
                        return_code=-1,
                        duration_seconds=duration,
                        retry_count=0,
                        errors=[
                            RetryError(
                                attempt=1,
                                timestamp=utc_now_iso(),
                                exception_type="TimeoutExpired",
                                message=f"Command timed out after {timeout}s",
                            )
                        ],
                    )
                duration = time.monotonic() - start_time
                success = _evaluate_subprocess_success(return_code, stderr_text)
                return ExecutionResult(
                    success=success,
                    return_code=return_code,
                    duration_seconds=duration,
                    retry_count=0,
                    errors=(
                        []
                        if success
                        else [
                            RetryError(
                                attempt=1,
                                timestamp=utc_now_iso(),
                                return_code=return_code,
                                message=_subprocess_failure_message(
                                    return_code, stderr_text
                                ),
                            )
                        ]
                    ),
                    stdout_text=stdout_text,
                    stderr_text=stderr_text,
                )

            process: Optional[subprocess.Popen[bytes]] = None
            try:
                resolved_command = self._resolve_command(command)
                process = subprocess.Popen(
                    resolved_command,
                    stdin=subprocess.PIPE if stdin_input else subprocess.DEVNULL,
                    stdout=subprocess.PIPE if capture_output else None,
                    stderr=subprocess.PIPE if capture_output else None,
                    shell=False,
                    cwd=self._subprocess_cwd(),
                    env=_subprocess_env_for_command(resolved_command),
                    creationflags=get_creation_flags(),
                )
                if capture_output:
                    stdout_data, stderr_data = process.communicate(
                        input=stdin_bytes, timeout=timeout
                    )
                else:
                    # Write stdin then wait — output goes directly to terminal
                    if stdin_bytes and process.stdin:
                        process.stdin.write(stdin_bytes)
                        process.stdin.close()
                    process.wait(timeout=timeout)
                    stdout_data, stderr_data = b"", b""
                duration = time.monotonic() - start_time
                stderr_text = self._decode_output(stderr_data)
                return_code = (
                    process.returncode if process.returncode is not None else -1
                )
                success = _evaluate_subprocess_success(return_code, stderr_text)
                return ExecutionResult(
                    success=success,
                    return_code=return_code,
                    duration_seconds=duration,
                    retry_count=0,
                    errors=(
                        []
                        if success
                        else [
                            RetryError(
                                attempt=1,
                                timestamp=utc_now_iso(),
                                return_code=return_code,
                                message=_subprocess_failure_message(
                                    return_code, stderr_text
                                ),
                            )
                        ]
                    ),
                    stdout_text=self._decode_output(stdout_data),
                    stderr_text=stderr_text,
                )

            except subprocess.TimeoutExpired:
                if process is not None:
                    terminate_process(process)
                duration = time.monotonic() - start_time
                return ExecutionResult(
                    success=False,
                    return_code=-1,
                    duration_seconds=duration,
                    retry_count=0,
                    errors=[
                        RetryError(
                            attempt=1,
                            timestamp=utc_now_iso(),
                            exception_type="TimeoutExpired",
                            message=f"Command timed out after {timeout}s",
                        )
                    ],
                )

            except OSError as exc:
                _executor_logger.error(
                    "run_with_popen: %s: %s, command=%s",
                    type(exc).__name__,
                    exc,
                    command,
                )
                duration = time.monotonic() - start_time
                return ExecutionResult(
                    success=False,
                    return_code=-1,
                    duration_seconds=duration,
                    retry_count=0,
                    errors=[
                        RetryError(
                            attempt=1,
                            timestamp=utc_now_iso(),
                            exception_type=type(exc).__name__,
                            message=str(exc),
                        )
                    ],
                )

        finally:
            self._cleanup_temp_files(temp_files)

    # --- Private helpers ---

    def _validate_invocation(
        self, command: list[str], timeout: int, max_retries: int
    ) -> Optional[str]:
        if not command:
            return "command must not be empty"
        if timeout < 0:
            return "timeout must be non-negative"
        if max_retries < 0:
            return "max_retries must be non-negative"
        return None

    def _sanitize_prompt(
        self,
        start_time: float,
        prompt: Optional[str],
        command: list[str],
        operation: str,
    ) -> Optional[ExecutionResult]:
        if prompt is None:
            return None
        sanitize_result = self._sanitizer.sanitize(prompt)
        if sanitize_result.is_safe:
            return None
        _executor_logger.warning(
            "%s: prompt rejected by sanitizer, reason=%s, command=%s",
            operation,
            sanitize_result.rejection_reason,
            command,
        )
        return self._build_immediate_failure(
            start_time=start_time,
            exception_type="SanitizationError",
            message=sanitize_result.rejection_reason,
        )

    def _build_immediate_failure(
        self, start_time: float, exception_type: str, message: str
    ) -> ExecutionResult:
        duration = time.monotonic() - start_time
        return ExecutionResult(
            success=False,
            return_code=-1,
            duration_seconds=duration,
            retry_count=0,
            errors=[
                RetryError(
                    attempt=0,
                    timestamp=utc_now_iso(),
                    exception_type=exception_type,
                    message=message,
                )
            ],
        )

    @staticmethod
    def _resolve_command(command: list[str]) -> list[str]:
        if not command:
            return command
        first = command[0]
        if Path(first).is_file():
            return command
        resolved = _find_cli_tool(first)
        if resolved is not None:
            return [resolved] + command[1:]
        return command

    def _execute_once(
        self,
        command: list[str],
        timeout: int,
        stdin_input: Optional[bytes] = None,
        temp_files: Optional[list[Path]] = None,
    ) -> subprocess.CompletedProcess[bytes]:
        # DEVNULL stdin prevents CLI tools from blocking on interactive input,
        # and avoids invalid inherited handles in windowed (no-console) builds.
        stdin_kwargs: dict[str, Any] = (
            {"input": stdin_input} if stdin_input else {"stdin": subprocess.DEVNULL}
        )
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=timeout,
            cwd=self._subprocess_cwd(),
            env=_subprocess_env_for_command(command),
            **stdin_kwargs,
            creationflags=get_creation_flags(),
        )

    def _execute_once_streaming(
        self,
        command: list[str],
        timeout: int,
        *,
        stdin_input: Optional[bytes] = None,
        on_output_line: Callable[[str], None],
    ) -> tuple[int, str, str]:
        """Run a command and stream stdout/stderr lines to a callback."""
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE if stdin_input else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            cwd=self._subprocess_cwd(),
            env=_subprocess_env_for_command(command),
            creationflags=get_creation_flags(),
        )
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        def _reader(pipe: Any, chunks: list[str], prefix: str = "") -> None:
            try:
                while True:
                    line = pipe.readline()
                    if not line:
                        break
                    text = (
                        self._decode_output(line)
                        if isinstance(line, (bytes, bytearray))
                        else str(line)
                    )
                    chunks.append(text)
                    stripped = text.rstrip("\r\n")
                    if stripped:
                        on_output_line(prefix + stripped)
            finally:
                pipe.close()

        readers: list[threading.Thread] = []
        if process.stdout is not None:
            thread = threading.Thread(
                target=_reader, args=(process.stdout, stdout_chunks), daemon=True
            )
            thread.start()
            readers.append(thread)
        if process.stderr is not None:
            thread = threading.Thread(
                target=_reader,
                args=(process.stderr, stderr_chunks, "[stderr] "),
                daemon=True,
            )
            thread.start()
            readers.append(thread)

        if stdin_input and process.stdin is not None:
            process.stdin.write(stdin_input)
            process.stdin.close()

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_process(process)
            raise

        for thread in readers:
            thread.join(timeout=1.0)

        return (
            process.returncode if process.returncode is not None else -1,
            "".join(stdout_chunks),
            "".join(stderr_chunks),
        )

    @staticmethod
    def _decode_output(output: Optional[bytes]) -> str:
        if not output:
            return ""
        return output.decode("utf-8", errors="replace")

    def _calculate_backoff_timeout(self, base_timeout: int, attempt: int) -> int:
        backoff_timeout: int = base_timeout * (2**attempt)
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
            _executor_logger.debug(
                "_safe_delete: failed to delete %s: %s: %s",
                path,
                type(exc).__name__,
                exc,
            )


# =============================================================================
# Session 管理器
# =============================================================================

_session_logger = logging.getLogger("opencode_infinity.session.manager")

_SESSION_CREATION_TIMEOUT: int = 30
_MAX_EXPORT_MESSAGES: int = 5
_MESSAGE_CHAR_LIMIT: int = 500


class SessionManager:
    """Manages session lifecycle: creation, switching, context passing."""

    def __init__(
        self, adapter: CLIAdapter, executor: Executor, config: AppConfig
    ) -> None:
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

    def update_runtime(
        self,
        *,
        adapter: Optional[CLIAdapter] = None,
        config: Optional[AppConfig] = None,
    ) -> None:
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

        _session_logger.info(
            "switch_session: initiating session switch from %s", current_session_id
        )

        summary_context = self._execute_summary(current_session_id)
        exported_context = self._export_context(current_session_id)
        context = self._build_context(summary_context, exported_context)
        new_session_id = self._create_new_session(current_session_id, context)

        self.reset_rounds()
        _session_logger.info(
            "switch_session: switched from %s to %s", current_session_id, new_session_id
        )
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

        result = self._executor.run_with_retry(
            command=stats_command, timeout=30, max_retries=1
        )

        if not result.success:
            _session_logger.warning(
                "_check_token_threshold: stats query failed for session %s", session_id
            )
            return self._check_rounds_threshold()

        token_ratio = self._parse_token_usage(result)
        if token_ratio is None:
            return self._check_rounds_threshold()

        threshold = self._config.execution.token_threshold
        should_switch = token_ratio >= threshold

        if should_switch:
            _session_logger.info(
                "_check_token_threshold: token usage %.1f%% exceeds threshold %.1f%%",
                token_ratio * 100,
                threshold * 100,
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
                self._round_count,
                switch_after,
            )
        return should_switch

    def _parse_token_usage(self, result: ExecutionResult) -> Optional[float]:
        try:
            max_tokens = self._config.execution.max_tokens
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
                command=command,
                timeout=self._config.execution.timeout,
                max_retries=1,
                prompt=summary_prompt,
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
            _session_logger.warning(
                "_execute_summary: failed for session %s, return_code=%d",
                session_id,
                result.return_code,
            )
            return ""
        except (OSError, ValueError) as exc:
            _session_logger.warning(
                "_execute_summary: %s: %s, session_id=%s",
                type(exc).__name__,
                exc,
                session_id,
            )
            return ""

    def _export_context(self, session_id: str) -> list[str]:
        export_command = self._adapter.build_export_command(session_id)
        if export_command is None:
            return []
        try:
            result = self._executor.run_with_retry(
                command=export_command, timeout=_SESSION_CREATION_TIMEOUT, max_retries=1
            )
            if not result.success:
                return []
            return compact_strings(normalize_newlines(result.stdout_text).splitlines())[
                :_MAX_EXPORT_MESSAGES
            ]
        except (OSError, ValueError) as exc:
            _session_logger.warning(
                "_export_context: %s: %s, session_id=%s",
                type(exc).__name__,
                exc,
                session_id,
            )
            return []

    def _build_context(self, summary: str, messages: list[str]) -> str:
        context_parts: list[str] = []
        normalized_summary = normalize_newlines(summary).strip()
        normalized_messages = [
            normalize_newlines(message) for message in compact_strings(messages)
        ]

        if normalized_summary:
            context_parts.append(
                f"Summary: {truncate_text(normalized_summary, _MESSAGE_CHAR_LIMIT, suffix='')}"
            )

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
                command=command,
                timeout=_SESSION_CREATION_TIMEOUT,
                max_retries=1,
                prompt=new_session_prompt,
            )
            elapsed = time.monotonic() - start_time
            if result.success and elapsed <= _SESSION_CREATION_TIMEOUT:
                new_id = self._generate_session_id(current_session_id)
                _session_logger.info(
                    "_create_new_session: auto-created session %s in %.1fs",
                    new_id,
                    elapsed,
                )
                return new_id
            return self._generate_fallback_session_id(current_session_id)
        except (OSError, ValueError) as exc:
            _session_logger.warning(
                "_create_new_session: %s: %s, session_id=%s",
                type(exc).__name__,
                exc,
                current_session_id,
            )
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
        print(
            f"WARNING: Auto session creation failed. Using manual session ID: {new_id}",
            file=sys.stderr,
        )
        _session_logger.warning(
            "_generate_fallback_session_id: using manual ID %s", new_id
        )
        return new_id


# =============================================================================
# 主程式邏輯 (__main__)
# =============================================================================

_CONFIG_DIR_ENV: str = "OPENCODE_INFINITY_CONFIG_DIR"
_tasks_config_dir: Optional[Path] = None
_main_logger: logging.Logger = logging.getLogger("opencode_infinity.__main__")


def _app_root() -> Path:
    """Return the application root directory (supports PyInstaller bundles)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return Path(__file__).parent


def _normalize_working_dir_text(value: Any) -> str:
    if value is None or not isinstance(value, str):
        return ""
    return value.strip()


def _resolve_execution_working_dir(
    config: AppConfig,
    *,
    override: Optional[str] = None,
) -> Optional[Path]:
    """Resolve subprocess cwd from GUI override or YAML execution.working_dir."""
    raw = _normalize_working_dir_text(override)
    if not raw:
        raw = _normalize_working_dir_text(config.execution.working_dir)
    if not raw:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.is_dir():
        raise ConfigError(f"working_dir is not a directory: {path}")
    return path


def _self_tool_directory_warning(path: Path) -> Optional[str]:
    """Warn when automation may modify this tool's own source tree."""
    if getattr(sys, "frozen", False):
        return None
    if (path / "opencode_infinity.py").is_file():
        return (
            f"工作目錄含 opencode_infinity.py（{path}），"
            "AI 可能修改本工具源碼。請改用目標專案目錄。"
        )
    return None


def _get_user_config_dir() -> Path:
    """Return the cross-platform user config directory."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "OpenCodeInfinity" / "configs"


_FACTORY_SEED_CONFIGS: dict[str, str] = {
    "opencode.yaml": """# OpenCode 出廠範本 · 連載文章創作
# 每輪只寫一小段，接續前稿繼續寫，不要一輪完結全篇
cli:
  tool: opencode

execution:
  delay: 1
  timeout: 300
  max_retries: 5
  auto_continue_on_error: true
  max_rounds: 0
  switch_after_rounds: 0
  max_tokens: 128000
  token_threshold: 0.7
  # working_dir: "D:/my-project"  # 留空則沿用啟動目錄

display:
  show_session_id: true
  show_timestamp: true

prompts:
  - |
    在 output/articles/ 建立或打開連載草稿 draft.md（已有檔案則讀取，不要重寫）：
    - 本輪只做：確定主題、列出 4-6 個章節大綱
    - 撰寫「開篇 + 第一章」約 400-600 字
    - 文末加上 <!-- CONTINUE: 下一章節標題 --> 標記待寫段落
    - 禁止本輪寫完全文或結語
    - 寫入後確認 draft.md 非空且至少 200 字；若為空檔請在本輪內補寫
  - |
    打開 draft.md，從 <!-- CONTINUE --> 標記處接續創作：
    - 本輪只寫下一個章節，約 400-600 字
    - 語氣與前文一致，開頭 1-2 句自然銜接
    - 更新 CONTINUE 標記指向下一段
    - 禁止重寫已有段落，禁止一輪內完結全篇
  - |
    繼續擴寫 draft.md：補寫下一章節，或深化目前最薄弱的一段：
    - 可先列出已完成章節與待寫章節（各一行）
    - 本輪專注新增內容，不做全篇大改
    - 若大綱仍有 2 章以上未寫，不要寫結語
  - |
    接續創作新的一節（案例、故事或論點展開）：
    - 僅可微調前文銜接句（最多 2 句），不可整段重寫
    - 本輪約 400-600 字，保持「進行中」草稿狀態
    - 更新 CONTINUE 標記

summary_prompt: |
  請用繁體中文總結本輪文章進度（200字內）：
  1. 本輪寫了哪個章節、約多少字
  2. 全文目前完成度（已完成/待寫章節）
  3. 下一輪建議接寫哪一段
""",
    "codex.yaml": """# Codex 出廠範本 · 連載文章創作（可搜尋補充資料）
# 每輪只寫一小段，接續前稿繼續寫，不要一輪就寫完
cli:
  tool: codex
  search: true

execution:
  delay: 1
  timeout: 300
  max_retries: 5
  auto_continue_on_error: true
  max_rounds: 0
  switch_after_rounds: 0
  max_tokens: 128000
  token_threshold: 0.7
  # working_dir: "D:/my-project"  # 留空則沿用啟動目錄

display:
  show_session_id: true
  show_timestamp: true

prompts:
  - |
    在 output/articles/ 建立或打開研究型連載草稿 draft.md（已有則接寫）：
    - 本輪：選定主題、列出 4-6 章大綱，搜尋 2-3 個可靠來源
    - 撰寫開篇與第一章約 400-600 字，文末附「參考來源」小節
    - 加上 <!-- CONTINUE: 下一章節標題 -->
    - 一輪寫不完是正常流程，不要寫結語
    - 寫入後確認 draft.md 非空且至少 200 字；若為空檔請在本輪內補寫
  - |
    接續 draft.md：先搜尋本 chapter 需要的事實、數據或案例，再撰寫下一章約 400-600 字：
    - 從 CONTINUE 標記處接寫，不重寫前文
    - 新內容需與已寫段落邏輯連貫
    - 更新 CONTINUE 標記與參考來源
  - |
    繼續擴寫：補寫下一章，或把某個論點寫深一層：
    - 列出「已完成 / 待寫」章節各一行
    - 本輪以新增段落為主，避免全篇重構
    - 尚有 2 章以上未寫時，不要寫結語
  - |
    接續創作並補充佐證（搜尋引用、數據或對比例子）：
    - 本輪約 400-600 字，只允許微調銜接句（最多 2 句）
    - 保持草稿為連載進行中狀態
    - 更新 CONTINUE 標記

summary_prompt: |
  請用繁體中文總結本輪文章進度（200字內）：
  1. 本輪新增哪一章、用了哪些資料來源
  2. 全文完成度與待寫章節
  3. 下一輪建議接寫方向
""",
    "article-en.yaml": """# Factory template · serial article writing (English)
# Write a little each round; continue the draft — do not finish in one round
cli:
  tool: codex
  search: true

execution:
  delay: 1
  timeout: 300
  max_retries: 5
  auto_continue_on_error: true
  max_rounds: 0
  switch_after_rounds: 0
  max_tokens: 128000
  token_threshold: 0.7
  # working_dir: "D:/my-project"  # empty = launch directory

display:
  show_session_id: true
  show_timestamp: true

prompts:
  - |
    Create or open a serial draft at output/articles/draft.md (read existing file; do not rewrite):
    - This round only: pick a topic and outline 4-6 chapters
    - Write the opening plus chapter 1 (~400-600 words)
    - End with <!-- CONTINUE: next chapter title -->
    - Do not finish the full article or write a conclusion this round
    - After writing, verify draft.md is non-empty (at least 200 words); rewrite in-round if empty
  - |
    Continue draft.md from the <!-- CONTINUE --> marker:
    - Write only the next chapter (~400-600 words)
    - Match tone and add 1-2 bridging sentences
    - Update the CONTINUE marker
    - Do not rewrite prior sections or finish the whole piece in one round
  - |
    Keep expanding draft.md — add the next chapter or deepen the weakest section:
    - List completed vs pending chapters (one line each)
    - Focus on new content, not a full rewrite
    - If 2+ chapters remain, do not write a conclusion
  - |
    Continue with a new section (case study, story, or argument):
    - You may tweak at most 2 bridging sentences; no full rewrites
    - ~400-600 words; keep the draft in progress
    - Update the CONTINUE marker

summary_prompt: |
  Summarize this round's article progress in English (max 200 words):
  1. Which chapter was added and approximate word count
  2. Overall completion (done vs pending chapters)
  3. Suggested focus for the next round
""",
}


def _create_factory_templates(target_dir: Path) -> dict[str, list[str]]:
    """Create or overwrite built-in factory templates."""
    target_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    overwritten: list[str] = []
    errors: list[str] = []
    for filename, content in _FACTORY_SEED_CONFIGS.items():
        target = target_dir / filename
        existed = target.is_file()
        try:
            target.write_text(content, encoding="utf-8")
            if existed:
                overwritten.append(filename)
                _main_logger.info("Overwrote factory template: %s", target)
            else:
                created.append(filename)
                _main_logger.info("Created factory template: %s", target)
        except OSError as exc:
            errors.append(f"{filename}: {exc}")
    return {"created": created, "overwritten": overwritten, "errors": errors}


def init_config_dir(override: Optional[str] = None) -> Path:
    """Initialize and return the active config directory."""
    global _tasks_config_dir
    _ensure_windows_user_path()
    if override:
        resolved = Path(override).expanduser()
    elif os.environ.get(_CONFIG_DIR_ENV, "").strip():
        resolved = Path(os.environ[_CONFIG_DIR_ENV]).expanduser()
    else:
        resolved = _get_user_config_dir()
    resolved.mkdir(parents=True, exist_ok=True)
    _tasks_config_dir = resolved
    return resolved


def get_tasks_config_dir() -> Path:
    """Return the active config directory, creating it when needed."""
    if _tasks_config_dir is None:
        return init_config_dir()
    return _tasks_config_dir


_SESSION_ID_PATTERN: re.Pattern[str] = re.compile(
    r"^(ses_.+|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)


def _validate_config_filename(filename: str) -> None:
    """Reject path traversal and non-YAML config filenames."""
    name = filename.strip()
    if not name:
        raise ConfigError("未指定檔案名稱")
    if ".." in name or "/" in name or "\\" in name:
        raise ConfigError("檔案名稱不合法（不允許路徑字元）")
    if not (name.endswith(".yaml") or name.endswith(".yml")):
        raise ConfigError("檔案名稱必須以 .yaml 或 .yml 結尾")


def _config_file_path(filename: str) -> Path:
    _validate_config_filename(filename)
    return get_tasks_config_dir() / filename.strip()


def _validate_session_id(session_id: str) -> bool:
    """Validate session_id format: must be ses_* or UUID."""
    return bool(_SESSION_ID_PATTERN.match(session_id))


def _resolve_config_path(config_name: Optional[str]) -> Path:
    """Resolve the configuration file path from a config name or path."""
    tasks_dir = get_tasks_config_dir()
    if config_name is None:
        if tasks_dir.is_dir():
            yaml_files = sorted(
                list(tasks_dir.glob("*.yaml")) + list(tasks_dir.glob("*.yml")),
                key=lambda path: path.name,
            )
            if yaml_files:
                return yaml_files[0]
        raise ConfigError(
            f"No config file specified and no YAML files found in '{tasks_dir}/'"
        )

    config_path = Path(config_name)
    if config_path.is_file():
        return config_path

    for candidate in (
        tasks_dir / f"{config_name}.yaml",
        tasks_dir / config_name,
        tasks_dir / f"{config_name}.yml",
    ):
        if candidate.is_file():
            return candidate

    raise ConfigError(
        f"Config file not found: '{config_name}' "
        f"(searched in '{tasks_dir}/' and direct paths)"
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


def _display_round_info(
    round_num: int, session_id: str, config: AppConfig, prompt: str
) -> None:
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


def _build_round_command(
    adapter: CLIAdapter, round_num: int, session_id: str, prompt: str
) -> list[str]:
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
    on_output_line: Optional[Callable[[str], None]] = None,
) -> ExecutionResult:
    """Execute one prompt round using the adapter's preferred transport."""
    command = _build_round_command(adapter, round_num, session_id, prompt)
    if _supports_stdin_pipe(adapter):
        return executor.run_with_popen(
            command=command,
            timeout=timeout,
            stdin_input=prompt,
            prompt=prompt,
            on_output_line=on_output_line,
        )
    return executor.run_with_retry(
        command=command,
        timeout=timeout,
        max_retries=max_retries,
        prompt=prompt,
        on_output_line=on_output_line,
    )


def _interruptible_sleep(seconds: float, should_stop: Callable[[], bool]) -> None:
    """Sleep in short slices so stop requests can interrupt promptly."""
    if seconds <= 0:
        return
    slices = max(1, int(seconds * 10))
    for _ in range(slices):
        if should_stop():
            return
        time.sleep(seconds / slices)


def _reload_hot_config(
    *,
    round_num: int,
    config_loader: ConfigLoader,
    config: AppConfig,
    adapter: CLIAdapter,
    session_manager: SessionManager,
    app_logger: logging.Logger,
    on_reloaded: Optional[Callable[[str], None]] = None,
    on_reload_failed: Optional[Callable[[str], None]] = None,
) -> tuple[AppConfig, CLIAdapter, SessionManager]:
    """Reload config on demand and refresh runtime components if anything changed."""
    if round_num < 2:
        return config, adapter, session_manager

    try:
        new_config, changed = config_loader.reload()
    except (OSError, ValueError, ConfigError) as exc:
        message = (
            f"Config reload failed at round {round_num}: {type(exc).__name__}: {exc}"
        )
        app_logger.warning(message)
        if on_reload_failed is not None:
            on_reload_failed(f"⚠️ 設定熱重載失敗: {type(exc).__name__}: {exc}")
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
    summary = _summarize_config_changes(previous_config, updated_config)
    app_logger.info("Config hot-reloaded at round %d: %s", round_num, summary)
    if on_reloaded is not None:
        on_reloaded(summary)
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
        f"{field}: {truncate_text(repr(old), 40)} -> {truncate_text(repr(new), 40)}"
        for field, (old, new) in list(changes.items())[:max_items]
    )
    remaining = len(changes) - max_items
    if remaining > 0:
        return f"{preview}, ... (+{remaining} more)"
    return preview


@dataclass
class _ExecutionLoopStats:
    """Mutable counters collected while running the shared execution loop."""

    round_count: int = 0
    success_count: int = 0
    fail_count: int = 0
    session_count: int = 1
    session_id: str = ""


@dataclass
class _ExecutionLoopHooks:
    """Callbacks that let CLI and GUI reuse the same execution loop."""

    should_stop: Callable[[], bool]
    on_round_begin: Callable[[int, str, AppConfig, str], None]
    on_round_success: Callable[[int, ExecutionResult], None]
    on_round_failure: Callable[[int, ExecutionResult], None]
    on_session_switched: Callable[[str], None]
    on_session_switch_failed: Callable[[str], None]
    on_max_rounds_reached: Callable[[int], None]
    on_reloaded: Optional[Callable[[str], None]] = None
    on_reload_failed: Optional[Callable[[str], None]] = None
    on_command_preview: Optional[Callable[[list[str]], None]] = None
    on_cli_output: Optional[Callable[[str], None]] = None
    on_iteration_end: Optional[Callable[[_ExecutionLoopStats], None]] = None
    on_session_switch_attempt: Optional[Callable[[], None]] = None
    on_abort: Optional[Callable[[str], None]] = None
    interruptible_delay: bool = False


def _run_execution_loop(
    *,
    config_loader: ConfigLoader,
    config: AppConfig,
    adapter: CLIAdapter,
    executor: Executor,
    session_manager: SessionManager,
    session_id: str,
    app_logger: logging.Logger,
    hooks: _ExecutionLoopHooks,
) -> tuple[_ExecutionLoopStats, AppConfig, CLIAdapter, SessionManager]:
    """Run the shared prompt execution loop for CLI and GUI modes."""
    stats = _ExecutionLoopStats(session_id=session_id)
    prompt_index = 0
    active_config = config
    active_adapter = adapter
    active_session_manager = session_manager
    active_session_id = session_id

    while not hooks.should_stop():
        stats.round_count += 1
        round_num = stats.round_count

        active_config, active_adapter, active_session_manager = _reload_hot_config(
            round_num=round_num,
            config_loader=config_loader,
            config=active_config,
            adapter=active_adapter,
            session_manager=active_session_manager,
            app_logger=app_logger,
            on_reloaded=hooks.on_reloaded,
            on_reload_failed=hooks.on_reload_failed,
        )

        if (
            active_config.execution.max_rounds > 0
            and round_num > active_config.execution.max_rounds
        ):
            hooks.on_max_rounds_reached(active_config.execution.max_rounds)
            break

        current_prompt, prompt_index = _select_prompt(
            active_config.prompts, prompt_index
        )
        hooks.on_round_begin(
            round_num, active_session_id, active_config, current_prompt
        )

        active_session_manager.increment_round()
        if active_session_manager.should_switch(active_session_id):
            if hooks.on_session_switch_attempt is not None:
                hooks.on_session_switch_attempt()
            try:
                active_session_id = active_session_manager.switch_session(
                    active_session_id
                )
                stats.session_count += 1
                stats.session_id = active_session_id
                hooks.on_session_switched(active_session_id)
            except (OSError, ValueError) as exc:
                hooks.on_session_switch_failed(f"{type(exc).__name__}: {exc}")

        if hooks.on_command_preview is not None:
            hooks.on_command_preview(
                _build_round_command(
                    active_adapter, round_num, active_session_id, current_prompt
                )
            )

        result = _execute_prompt_round(
            executor=executor,
            adapter=active_adapter,
            round_num=round_num,
            session_id=active_session_id,
            prompt=current_prompt,
            timeout=active_config.execution.timeout,
            max_retries=active_config.execution.max_retries,
            on_output_line=hooks.on_cli_output,
        )

        if result.success:
            stats.success_count += 1
            hooks.on_round_success(round_num, result)
        else:
            stats.fail_count += 1
            hooks.on_round_failure(round_num, result)
            if not active_config.execution.auto_continue_on_error:
                if hooks.on_abort is not None:
                    hooks.on_abort("auto_continue_on_error=False")
                break

        if hooks.on_iteration_end is not None:
            hooks.on_iteration_end(stats)

        if hooks.should_stop():
            break

        if active_config.execution.delay > 0:
            if hooks.interruptible_delay:
                _interruptible_sleep(active_config.execution.delay, hooks.should_stop)
            else:
                time.sleep(active_config.execution.delay)

    stats.session_id = active_session_id
    return stats, active_config, active_adapter, active_session_manager


@dataclass
class _LaunchOptions:
    """Parsed optional CLI/GUI launch flags."""

    config_dir: Optional[str] = None
    port: int = 8080
    open_browser: bool = True
    port_explicit: bool = False


DEFAULT_DESKTOP_PORT = 19090


def _parse_launch_options(argv: list[str]) -> tuple[list[str], _LaunchOptions]:
    """Extract optional flags and return the remaining positional arguments."""
    options = _LaunchOptions()
    positional: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--config-dir":
            if index + 1 >= len(argv):
                raise ConfigError("--config-dir requires a path argument")
            options.config_dir = argv[index + 1]
            index += 2
            continue
        if arg.startswith("--config-dir="):
            options.config_dir = arg.split("=", 1)[1]
            index += 1
            continue
        if arg == "--port":
            if index + 1 >= len(argv):
                raise ConfigError("--port requires a number argument")
            options.port = safe_int(
                argv[index + 1], default=8080, minimum=1, maximum=65535
            )
            options.port_explicit = True
            index += 2
            continue
        if arg.startswith("--port="):
            options.port = safe_int(
                arg.split("=", 1)[1], default=8080, minimum=1, maximum=65535
            )
            options.port_explicit = True
            index += 1
            continue
        if arg == "--no-browser":
            options.open_browser = False
            index += 1
            continue
        if arg.startswith("-"):
            raise ConfigError(f"Unknown option: {arg}")
        positional.append(arg)
        index += 1
    return positional, options


def main() -> None:
    """Main entry point for OpenCode Infinity.

    CLI: python opencode_infinity.py <session_id> [config_name]
    GUI: python opencode_infinity.py --gui
    """
    _configure_stdio_encoding()
    global _main_logger
    _main_logger = setup_logger("opencode_infinity.__main__")
    raw_args = sys.argv[1:]

    if "--gui" in raw_args:
        gui_args = [arg for arg in raw_args if arg != "--gui"]
        try:
            positional, options = _parse_launch_options(gui_args)
            if positional:
                raise ConfigError(
                    f"Unexpected arguments for --gui: {' '.join(positional)}"
                )
            init_config_dir(options.config_dir)
            _start_gui(port=options.port, open_browser=options.open_browser)
        except ConfigError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    try:
        positional, options = _parse_launch_options(raw_args)
        init_config_dir(options.config_dir)
        _run(positional)
    except SystemExit:
        raise
    except KeyboardInterrupt:
        _sigint_handler(signal.SIGINT, None)
    except OpenCodeInfinityError as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        _main_logger.error(
            "main: handled open-code error: %s: %s",
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        sys.exit(1)
    except Exception as exc:
        print(
            f"FATAL: Unhandled exception: {type(exc).__name__}: {exc}", file=sys.stderr
        )
        _main_logger.error(
            "main: unhandled exception: %s: %s", type(exc).__name__, exc, exc_info=True
        )
        sys.exit(1)


def _run(args: Optional[list[str]] = None) -> None:
    """Internal main logic."""
    if args is None:
        args = sys.argv[1:]

    if len(args) == 0 or len(args) > 2:
        config_dir = get_tasks_config_dir()
        print(
            "Usage: python opencode_infinity.py <session_id> [config_name]",
            file=sys.stderr,
        )
        print(
            "  session_id: Required when two arguments are supplied; a single non-session argument is treated as config_name.",
            file=sys.stderr,
        )
        print(
            f"  config_name: Optional config name or path (searches in '{config_dir}/')",
            file=sys.stderr,
        )
        print("\nOptions:", file=sys.stderr)
        print("  --config-dir PATH   Override config directory", file=sys.stderr)
        print("  --gui               Start browser-based web GUI", file=sys.stderr)
        print("  --port PORT         GUI server port (default: 8080)", file=sys.stderr)
        print(
            "  --no-browser        Do not auto-open browser in --gui mode",
            file=sys.stderr,
        )
        print("\nExamples:", file=sys.stderr)
        print(
            "  python opencode_infinity.py ses_docs codex     # 使用 codex.yaml",
            file=sys.stderr,
        )
        print(
            "  python opencode_infinity.py ses_abc123 codex   # 指定 session",
            file=sys.stderr,
        )
        print("  python opencode_infinity.py --gui", file=sys.stderr)
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

    app_logger.info(
        "Config loaded: tool=%s, config_path=%s", config.cli.tool, config_path
    )

    try:
        adapter = create_adapter(config.cli.tool, config.cli)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        app_logger.error("_run: adapter creation failed: %s", exc)
        sys.exit(1)

    try:
        working_dir = _resolve_execution_working_dir(config)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        app_logger.error("_run: invalid working_dir: %s", exc)
        sys.exit(1)

    tool_warning = _self_tool_directory_warning(working_dir) if working_dir else None
    if tool_warning:
        print(f"WARNING: {tool_warning}", file=sys.stderr)
        app_logger.warning(tool_warning)
    if working_dir:
        app_logger.info("CLI working directory: %s", working_dir)

    executor = Executor(working_dir=working_dir)
    session_manager = SessionManager(adapter, executor, config)

    _state.current_session_id = session_id
    _state.executor = executor
    _state.start_time = time.monotonic()

    signal.signal(signal.SIGINT, _sigint_handler)

    app_logger.info("Starting main loop, tool=%s", adapter.tool_name)

    def _sync_cli_state(loop_stats: _ExecutionLoopStats) -> None:
        _state.round_count = loop_stats.round_count
        _state.success_count = loop_stats.success_count
        _state.fail_count = loop_stats.fail_count
        _state.session_count = loop_stats.session_count
        _state.current_session_id = loop_stats.session_id

    def _on_session_switched(new_session_id: str) -> None:
        nonlocal session_id
        session_id = new_session_id
        _state.current_session_id = new_session_id
        app_logger.info("Switched to new session: %s", new_session_id)

    hooks = _ExecutionLoopHooks(
        should_stop=lambda: not _state.running,
        on_round_begin=_display_round_info,
        on_round_success=lambda round_num, result: app_logger.info(
            "Round %d completed successfully (%.1fs)",
            round_num,
            result.duration_seconds,
        ),
        on_round_failure=lambda round_num, result: app_logger.warning(
            "Round %d failed: return_code=%d, retries=%d",
            round_num,
            result.return_code,
            result.retry_count,
        ),
        on_session_switched=_on_session_switched,
        on_session_switch_failed=lambda message: app_logger.warning(
            "Session switch failed: %s", message
        ),
        on_max_rounds_reached=lambda max_rounds: app_logger.info(
            "Reached max_rounds=%d, stopping", max_rounds
        ),
        on_abort=lambda reason: app_logger.info("%s, stopping after failure", reason),
        on_iteration_end=_sync_cli_state,
    )

    stats, _, _, _ = _run_execution_loop(
        config_loader=config_loader,
        config=config,
        adapter=adapter,
        executor=executor,
        session_manager=session_manager,
        session_id=session_id,
        app_logger=app_logger,
        hooks=hooks,
    )
    _sync_cli_state(stats)
    session_id = stats.session_id

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

_GUI_LOG_HISTORY_LIMIT: int = 500
_gui_log_lock = threading.Lock()
_gui_log_history: deque[str] = deque(maxlen=_GUI_LOG_HISTORY_LIMIT)
_gui_log_subscribers: set[queue.Queue[str]] = set()
_gui_state_lock = threading.Lock()
_gui_state: dict[str, Any] = {
    "running": False,
    "round_count": 0,
    "session_count": 1,
    "start_time": 0.0,
    "config_name": "",
    "session_id": "",
    "working_dir": "",
    "thread": None,
    "stop_event": None,
}


def _gui_log_subscribe() -> queue.Queue[str]:
    """Register an SSE client queue, pre-filled with recent history."""
    client_queue: queue.Queue[str] = queue.Queue(maxsize=_GUI_LOG_HISTORY_LIMIT * 2)
    with _gui_log_lock:
        for line in _gui_log_history:
            try:
                client_queue.put_nowait(line)
            except queue.Full:
                break
        _gui_log_subscribers.add(client_queue)
    return client_queue


def _gui_log_unsubscribe(client_queue: queue.Queue[str]) -> None:
    with _gui_log_lock:
        _gui_log_subscribers.discard(client_queue)


def _gui_log(message: str) -> None:
    """Broadcast a log line to all SSE clients, stderr, and the desktop log."""
    timestamp = time.strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    with _gui_log_lock:
        _gui_log_history.append(formatted)
        subscribers = list(_gui_log_subscribers)
    for client_queue in subscribers:
        try:
            client_queue.put_nowait(formatted)
        except queue.Full:
            try:
                client_queue.get_nowait()
                client_queue.put_nowait(formatted)
            except queue.Empty:
                pass
    if getattr(sys, "frozen", False):
        # Windowed PyInstaller builds have no console; stderr writes can block forever.
        _desktop_log(formatted)
    else:
        _eprint(formatted)


def _gui_log_article_draft_status(working_dir: Optional[Path]) -> None:
    """Log draft.md size after a round to help diagnose empty output files."""
    base = working_dir if working_dir is not None else Path.cwd()
    draft = base / "output" / "articles" / "draft.md"
    if not draft.is_file():
        return
    try:
        size = draft.stat().st_size
    except OSError as exc:
        _gui_log(f"  ⚠️ 無法讀取 draft.md: {exc}")
        return
    if size == 0:
        _gui_log(
            "  ⚠️ draft.md 已建立但為空檔。"
            "這通常不是 exe 權限問題（能建檔代表目錄可寫），"
            "而是本輪 AI 尚未寫入內容；請確認工作目錄正確並讓下一輪繼續。"
        )
        _gui_log(f"  📁 檔案位置: {draft.resolve()}")
        return
    _gui_log(f"  📝 draft.md 目前 {size} bytes — {draft.resolve()}")


def _gui_run_task(
    config_name: str,
    session_id: str,
    stop_event: threading.Event,
    working_dir_override: Optional[str] = None,
) -> None:
    """Background thread: run the execution loop with GUI logging."""
    _gui_log(f"🚀 啟動執行 - Config: {config_name}, Session: {session_id}")
    with _gui_state_lock:
        _gui_state["round_count"] = 0
        _gui_state["session_count"] = 1
        _gui_state["start_time"] = time.monotonic()

    try:
        try:
            _ensure_windows_user_path()
            config_path = _resolve_config_path(config_name)
            _gui_log(f"📄 讀取設定: {config_path}")
            config_loader = ConfigLoader(config_path)
            config = config_loader.load()
        except (ConfigError, OSError, ValueError) as exc:
            _gui_log(f"❌ 設定載入失敗: {exc}")
            return

        _gui_log(f"✅ 設定載入成功: tool={config.cli.tool}")

        try:
            working_dir = _resolve_execution_working_dir(
                config, override=working_dir_override
            )
        except ConfigError as exc:
            _gui_log(f"❌ 工作目錄無效: {exc}")
            return

        tool_warning = (
            _self_tool_directory_warning(working_dir) if working_dir else None
        )
        if tool_warning:
            _gui_log(f"⚠️ {tool_warning}")
        if working_dir:
            _gui_log(f"📁 工作目錄: {working_dir}")
        else:
            _gui_log(f"📁 工作目錄: {Path.cwd()}（沿用啟動目錄）")

        try:
            adapter = create_adapter(config.cli.tool, config.cli)
        except (ValueError, CLIAdapterError) as exc:
            _gui_log(f"❌ CLI 適配器建立失敗: {exc}")
            if sys.platform == "win32":
                _gui_log(
                    "💡 提示：請確認已安裝 opencode（npm i -g opencode-ai），"
                    "並重新啟動桌面版以載入 PATH。"
                )
            return

        if isinstance(adapter, OpenCodeAdapter):
            _gui_log(f"🔧 OpenCode: {adapter._executable}")

        executor = Executor(working_dir=working_dir)
        session_manager = SessionManager(adapter, executor, config)
        loop_logger = logging.getLogger("opencode_infinity.gui_loop")

        def _sync_gui_state(loop_stats: _ExecutionLoopStats) -> None:
            with _gui_state_lock:
                _gui_state["round_count"] = loop_stats.round_count
                _gui_state["session_count"] = loop_stats.session_count
                _gui_state["session_id"] = loop_stats.session_id

        def _on_gui_round_begin(
            round_num: int,
            active_session_id: str,
            active_config: AppConfig,
            current_prompt: str,
        ) -> None:
            with _gui_state_lock:
                _gui_state["round_count"] = round_num
                _gui_state["session_id"] = active_session_id
            _gui_log(
                f"▶ Round {round_num} | Session: {active_session_id} | "
                f"Prompt: {truncate_text(current_prompt, 60)}"
            )
            _gui_log("  ⏳ 正在呼叫 AI CLI（首次回應可能需要數分鐘，請稍候）…")

        cli_log_state = {"window_start": 0.0, "count": 0, "suppressed": 0}

        def _on_gui_cli_output(line: str) -> None:
            clean = _strip_ansi(line)
            if clean.startswith("[stderr] "):
                clean = clean[9:]
            clean = clean.strip()
            if not clean:
                return
            lower = clean.lower()
            if (
                "service=" in lower
                and "info" in lower
                and not any(token in lower for token in ("error", "warn", "fail", "timeout"))
            ):
                now = time.monotonic()
                if now - cli_log_state["window_start"] > 1.0:
                    if cli_log_state["suppressed"]:
                        _gui_log(
                            f"  | ... opencode 內部日誌 (+{cli_log_state['suppressed']} 行已摺疊)"
                        )
                    cli_log_state["window_start"] = now
                    cli_log_state["count"] = 0
                    cli_log_state["suppressed"] = 0
                if cli_log_state["count"] >= 4:
                    cli_log_state["suppressed"] += 1
                    return
                cli_log_state["count"] += 1
            _gui_log(f"  | {truncate_text(clean, 1200)}")

        def _on_gui_round_success(round_num: int, result: ExecutionResult) -> None:
            _gui_log(f"  ✅ Round {round_num} 完成 ({result.duration_seconds:.1f}s)")
            _gui_log_article_draft_status(working_dir)

        hooks = _ExecutionLoopHooks(
            should_stop=stop_event.is_set,
            on_round_begin=_on_gui_round_begin,
            on_round_success=_on_gui_round_success,
            on_round_failure=lambda round_num, result: _gui_log(
                f"  ❌ Round {round_num} 失敗 (code={result.return_code}, retries={result.retry_count})"
            ),
            on_session_switched=lambda new_session_id: _gui_log(
                f"✅ 切換到新 Session: {new_session_id}"
            ),
            on_session_switch_attempt=lambda: _gui_log("🔀 觸發 Session 切換..."),
            on_session_switch_failed=lambda message: _gui_log(
                f"⚠️ Session 切換失敗: {message}"
            ),
            on_max_rounds_reached=lambda max_rounds: _gui_log(
                f"🏁 已達最大輪次 {max_rounds}，停止執行"
            ),
            on_abort=lambda reason: _gui_log(f"⛔ {reason}，停止執行"),
            on_reloaded=lambda summary: _gui_log(f"🔄 設定已熱重載: {summary}"),
            on_reload_failed=_gui_log,
            on_command_preview=lambda command: _gui_log(
                f"  執行命令: {' '.join(command[:3])}..."
            ),
            on_cli_output=_on_gui_cli_output,
            on_iteration_end=_sync_gui_state,
            interruptible_delay=True,
        )

        stats, _, _, _ = _run_execution_loop(
            config_loader=config_loader,
            config=config,
            adapter=adapter,
            executor=executor,
            session_manager=session_manager,
            session_id=session_id,
            app_logger=loop_logger,
            hooks=hooks,
        )
        _sync_gui_state(stats)

        with _gui_state_lock:
            elapsed = time.monotonic() - _gui_state["start_time"]
            round_count = _gui_state["round_count"]
            session_count = _gui_state["session_count"]
        _gui_log(
            f"🏁 執行結束 - 輪次: {round_count}, Session: {session_count}, "
            f"耗時: {_format_elapsed_time(elapsed)}"
        )
    except Exception as exc:
        _gui_log(f"❌ 執行異常: {type(exc).__name__}: {exc}")
        _desktop_log(f"gui_run_task error: {type(exc).__name__}: {exc}")
    finally:
        with _gui_state_lock:
            _gui_state["running"] = False


def _gui_asset_mimetype(filename: str) -> str:
    if filename.endswith(".css"):
        return "text/css"
    if filename.endswith(".js"):
        return "application/javascript"
    return "application/octet-stream"


def _register_gui_static_routes(app: Any, Response: Any) -> None:
    @app.route("/")
    def index():
        gui_path = _app_root() / "gui" / "index.html"
        if not gui_path.is_file():
            return "ERROR: gui/index.html not found", 404
        return Response(gui_path.read_text(encoding="utf-8"), mimetype="text/html")

    @app.route("/gui/<path:filename>")
    def gui_assets(filename: str):
        if ".." in filename or filename.startswith("/"):
            return "Invalid path", 400
        asset_path = _app_root() / "gui" / filename
        if not asset_path.is_file():
            return "Asset not found", 404
        return Response(asset_path.read_bytes(), mimetype=_gui_asset_mimetype(filename))


def _register_config_api_routes(app: Any, jsonify: Any, request: Any) -> None:
    @app.route("/api/configs")
    def api_configs():
        configs_dir = get_tasks_config_dir()
        if not configs_dir.is_dir():
            return jsonify({"configs": []})
        configs = sorted(
            f.name for f in configs_dir.iterdir() if f.suffix in (".yaml", ".yml")
        )
        return jsonify({"configs": configs})

    @app.route("/api/config/create-templates", methods=["POST"])
    def api_config_create_templates():
        result = _create_factory_templates(get_tasks_config_dir())
        return jsonify({"ok": not result["errors"], **result})

    @app.route("/api/config/<name>")
    def api_config_content(name: str):
        try:
            target = _config_file_path(name)
        except ConfigError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        if not target.is_file():
            return jsonify({"ok": False, "error": "檔案不存在"}), 404
        try:
            content = target.read_text(encoding="utf-8")
            working_dir = ""
            try:
                config = ConfigLoader(target).load()
                working_dir = config.execution.working_dir
            except (ConfigError, OSError, ValueError):
                pass
            return jsonify({"content": content, "working_dir": working_dir})
        except OSError as exc:
            return jsonify({"ok": False, "error": f"讀取失敗: {exc}"}), 500

    @app.route("/api/config/save", methods=["POST"])
    def api_config_save():
        data = request.get_json(force=True, silent=True) or {}
        filename = data.get("filename", "").strip()
        content = data.get("content", "")
        try:
            target = _config_file_path(filename)
        except ConfigError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        try:
            _load_yaml_mapping_from_text(
                content, source=f"GUI save payload: {filename}"
            )
        except ConfigError as exc:
            return jsonify({"ok": False, "error": f"YAML 格式無效: {exc}"}), 400
        configs_dir = get_tasks_config_dir()
        configs_dir.mkdir(parents=True, exist_ok=True)
        try:
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return jsonify({"ok": False, "error": f"寫入失敗: {exc}"}), 500
        return jsonify({"ok": True, "path": str(target)})

    @app.route("/api/config/generate-yaml", methods=["POST"])
    def api_config_generate_yaml():
        data = request.get_json(force=True, silent=True) or {}
        try:
            yaml_str = yaml.dump(
                data, default_flow_style=False, allow_unicode=True, sort_keys=False
            )
            return jsonify({"yaml": yaml_str})
        except (TypeError, ValueError, yaml.YAMLError) as exc:
            return jsonify({"yaml": None, "error": str(exc)}), 500

    @app.route("/api/config/parse-yaml", methods=["POST"])
    def api_config_parse_yaml():
        data = request.get_json(force=True, silent=True) or {}
        content = data.get("content", "")
        try:
            parsed = _load_yaml_mapping_from_text(content, source="GUI parse payload")
            keys = list(parsed.keys())
            if len(keys) == 1 and isinstance(parsed[keys[0]], dict):
                inner = parsed[keys[0]]
                if any(k in inner for k in ("cli", "execution", "prompts")):
                    parsed = inner
            return jsonify({"config": parsed})
        except ConfigError as exc:
            return jsonify({"error": f"YAML 解析失敗: {exc}"}), 400


def _register_runtime_api_routes(
    app: Any, jsonify: Any, request: Any, Response: Any
) -> None:
    @app.route("/api/start", methods=["POST"])
    def api_start():
        with _gui_state_lock:
            if _gui_state["running"]:
                return jsonify({"ok": False, "error": "已在執行中"}), 409
        data = request.get_json(force=True, silent=True) or {}
        config_name = data.get("config", "")
        session_id = data.get("session_id", "").strip()
        working_dir_override = _normalize_working_dir_text(data.get("working_dir"))
        if not config_name:
            return jsonify({"ok": False, "error": "未指定設定檔"}), 400
        if session_id and not _validate_session_id(session_id):
            return jsonify({"ok": False, "error": "session_id 格式不正確"}), 400
        try:
            config_path = _resolve_config_path(config_name)
        except ConfigError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        if not config_path.is_file():
            return jsonify({"ok": False, "error": f"找不到設定檔: {config_name}"}), 404
        try:
            config = ConfigLoader(config_path).load()
            resolved_working_dir = _resolve_execution_working_dir(
                config, override=working_dir_override or None
            )
        except (ConfigError, OSError, ValueError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        if not session_id:
            session_id = f"ses_{int(time.time())}"

        stop_event = threading.Event()
        with _gui_state_lock:
            if _gui_state["running"]:
                return jsonify({"ok": False, "error": "已在執行中"}), 409
            _gui_state["running"] = True
            _gui_state["config_name"] = config_name
            _gui_state["session_id"] = session_id
            _gui_state["working_dir"] = (
                str(resolved_working_dir) if resolved_working_dir else ""
            )
            _gui_state["round_count"] = 0
            _gui_state["session_count"] = 1
            _gui_state["start_time"] = time.monotonic()
            _gui_state["stop_event"] = stop_event

        t = threading.Thread(
            target=_gui_run_task,
            args=(config_name, session_id, stop_event, working_dir_override or None),
            daemon=True,
        )
        with _gui_state_lock:
            _gui_state["thread"] = t
        t.start()

        return jsonify({"ok": True, "session_id": session_id})

    @app.route("/api/stop", methods=["POST"])
    def api_stop():
        with _gui_state_lock:
            if not _gui_state["running"]:
                return jsonify({"ok": False, "error": "目前未在執行"}), 409
            stop_event = _gui_state.get("stop_event")
        if stop_event:
            stop_event.set()
        _gui_log("⏹ 使用者請求停止")
        return jsonify({"ok": True})

    @app.route("/api/status")
    def api_status():
        with _gui_state_lock:
            running = _gui_state["running"]
            start_time = _gui_state["start_time"]
            elapsed_seconds = (
                time.monotonic() - start_time if start_time > 0 and running else 0.0
            )
            payload = {
                "running": running,
                "round_count": _gui_state["round_count"],
                "session_count": _gui_state["session_count"],
                "config_name": _gui_state["config_name"],
                "session_id": _gui_state["session_id"],
                "working_dir": _gui_state.get("working_dir", ""),
            }
        minutes = int(elapsed_seconds) // 60
        seconds = int(elapsed_seconds) % 60
        payload["elapsed"] = f"{minutes}:{seconds:02d}"
        return jsonify(payload)

    @app.route("/api/logs")
    def api_logs():
        client_queue = _gui_log_subscribe()

        def generate():
            try:
                while True:
                    try:
                        msg = client_queue.get(timeout=15)
                        yield f"data: {msg}\n\n"
                    except queue.Empty:
                        yield ": keepalive\n\n"
            finally:
                _gui_log_unsubscribe(client_queue)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )


def _create_flask_app():
    """Create and configure the Flask application for the web GUI."""
    try:
        from flask import Flask, Response, jsonify, request
    except ImportError as exc:
        raise ConfigError("Flask 未安裝。請執行: pip install flask") from exc

    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False
    _register_gui_static_routes(app, Response)
    _register_config_api_routes(app, jsonify, request)
    _register_runtime_api_routes(app, jsonify, request, Response)
    return app


def _start_flask_background(port: int, *, host: str = "127.0.0.1") -> Any:
    """Start Flask in a background thread and return the werkzeug server."""
    from werkzeug.serving import make_server

    app = _create_flask_app()
    server = make_server(host, port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _wait_for_gui_server(port: int, *, timeout_seconds: float = 10.0) -> None:
    """Wait until the local GUI server accepts connections."""
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + timeout_seconds
    url = f"http://127.0.0.1:{port}/"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.1)
    raise ConfigError(
        f"GUI server did not start on port {port} within {timeout_seconds:.0f}s"
    )


def _suppress_werkzeug_logs() -> None:
    import logging as _logging

    _logging.getLogger("werkzeug").setLevel(_logging.WARNING)


def _start_gui(*, port: int = 8080, open_browser: bool = True) -> None:
    """Start the Flask web GUI server in the foreground."""
    try:
        app = _create_flask_app()
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    preferred_port = port
    try:
        port = _pick_listen_port(port)
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    config_dir = get_tasks_config_dir()
    _eprint("🌐 OpenCode Infinity Web GUI 啟動中...")
    _eprint(f"   http://127.0.0.1:{port}")
    if port != preferred_port:
        _eprint(f"   (Port {preferred_port} unavailable, using {port} instead)")
    _eprint(f"   Config dir: {config_dir}")

    if open_browser:

        def _open_browser():
            time.sleep(1.5)
            webbrowser.open(f"http://127.0.0.1:{port}")

        threading.Thread(target=_open_browser, daemon=True).start()

    _suppress_werkzeug_logs()
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


def _start_desktop(*, port: int = DEFAULT_DESKTOP_PORT) -> None:
    """Start the pywebview desktop GUI."""
    server = None
    try:
        import webview
    except ImportError:
        _show_fatal_error(
            "OpenCode Infinity", "pywebview 未安裝。請執行: pip install pywebview"
        )
        sys.exit(1)

    try:
        gui_index = _app_root() / "gui" / "index.html"
        if not gui_index.is_file():
            raise ConfigError(f"找不到 GUI 資源: {gui_index}")

        _create_flask_app()
        config_dir = get_tasks_config_dir()
        port = _pick_listen_port(port)
        timeout = 30.0 if getattr(sys, "frozen", False) else 10.0

        _desktop_log(
            f"Starting desktop GUI on http://127.0.0.1:{port} (config: {config_dir})"
        )
        _eprint("OpenCode Infinity Desktop GUI starting...")
        _eprint(f"   http://127.0.0.1:{port}")
        _eprint(f"   Config dir: {config_dir}")

        _suppress_werkzeug_logs()
        server = _start_flask_background(port)
        _wait_for_gui_server(port, timeout_seconds=timeout)

        webview.create_window(
            "OpenCode Infinity",
            f"http://127.0.0.1:{port}",
            width=1280,
            height=860,
            min_size=(960, 640),
        )
        start_kwargs: dict[str, Any] = {}
        if sys.platform == "win32":
            start_kwargs["gui"] = "edgechromium"
        webview.start(**start_kwargs)
    except Exception as exc:
        _show_fatal_error(
            "OpenCode Infinity - 啟動失敗",
            f"{exc}\n\n詳細日誌: {_desktop_log_path()}",
        )
        raise SystemExit(1) from exc
    finally:
        if server is not None:
            server.shutdown()


if __name__ == "__main__":
    main()
