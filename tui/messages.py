"""Textual messages for cross-thread UI updates."""
from __future__ import annotations

from textual.message import Message


class LogLine(Message):
    """Append a line to the console log panel."""

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()


class StatsUpdated(Message):
    """Update running statistics in the console header."""

    def __init__(
        self,
        *,
        running: bool,
        round_count: int,
        session_count: int,
        session_id: str,
        config_name: str,
        working_dir: str,
        elapsed_seconds: float,
    ) -> None:
        self.running = running
        self.round_count = round_count
        self.session_count = session_count
        self.session_id = session_id
        self.config_name = config_name
        self.working_dir = working_dir
        self.elapsed_seconds = elapsed_seconds
        super().__init__()


class ConfigListChanged(Message):
    """Config file list was refreshed."""

    def __init__(self, configs: list[str]) -> None:
        self.configs = configs
        super().__init__()
