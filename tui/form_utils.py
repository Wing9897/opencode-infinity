"""Form helpers."""
from __future__ import annotations

from textual.widgets import Input, Select, TextArea

from tui import i18n


def req_label(key: str) -> str:
    """Label text with a red required asterisk."""
    return f"{i18n.t(key)} [red]*[/]"


def req_title(key: str) -> str:
    """Section title with a required asterisk."""
    return f"{i18n.t(key)} *"


def select_empty(widget: Select) -> bool:
    value = widget.value
    return not isinstance(value, str) or not value.strip()


def text_area_empty(widget: TextArea) -> bool:
    return not widget.text.strip()
