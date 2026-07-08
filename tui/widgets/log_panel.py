"""Reusable TUI widgets."""
from __future__ import annotations

from textual.widgets import RichLog, Static


class StatsBar(Static):
    """Display rounds, sessions, and elapsed time."""


class LogPanel(RichLog):
    """Scrollable execution log with plain-text copy support."""

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=False, markup=False, wrap=True, **kwargs)
        self._plain_lines: list[str] = []

    def append_line(self, text: str, *, plain: str | None = None) -> None:
        line = plain if plain is not None else text
        self._plain_lines.append(line)
        self.write(line)

    def plain_text(self) -> str:
        return "\n".join(self._plain_lines)

    def clear_log(self) -> None:
        self._plain_lines.clear()
        self.clear()
