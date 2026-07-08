"""Reusable TUI widgets."""
from __future__ import annotations

from textual.widgets import RichLog


class LogPanel(RichLog):
    """Scrollable execution log with plain-text copy support."""

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=False, markup=False, wrap=True, **kwargs)
        self._plain_lines: list[str] = []
        self._placeholder_only = False

    def show_placeholder(self, text: str) -> None:
        """Show a single placeholder line (replaced on first real log line)."""
        self._plain_lines.clear()
        self.clear()
        self._plain_lines.append(text)
        self.write(text)
        self._placeholder_only = True

    def refresh_placeholder(self, text: str) -> None:
        """Update placeholder text after locale change."""
        if self._placeholder_only:
            self.show_placeholder(text)

    def append_line(self, text: str, *, plain: str | None = None) -> None:
        if self._placeholder_only:
            self._plain_lines.clear()
            self.clear()
            self._placeholder_only = False
        line = plain if plain is not None else text
        self._plain_lines.append(line)
        self.write(line)

    def plain_text(self) -> str:
        return "\n".join(self._plain_lines)

    def clear_log(self) -> None:
        self._plain_lines.clear()
        self.clear()
        self._placeholder_only = False
