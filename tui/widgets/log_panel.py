"""Reusable TUI widgets."""
from __future__ import annotations

from textual.widgets import RichLog, Static


class StatsBar(Static):
    """Display rounds, sessions, and elapsed time."""

    DEFAULT_CSS = """
    StatsBar {
        height: 3;
        padding: 0 1;
        background: $surface;
    }
    """


class LogPanel(RichLog):
    """Scrollable execution log."""

    DEFAULT_CSS = """
    LogPanel {
        border: solid $primary;
        height: 1fr;
        min-height: 12;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=True, markup=True, wrap=True, **kwargs)

    def append_line(self, text: str) -> None:
        self.write(text)

    def clear_log(self) -> None:
        self.clear()
