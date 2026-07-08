"""Refresh visible UI strings after locale change."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Button, Checkbox, Collapsible, Input, Label, Select, Static, Tab

from tui import i18n

if TYPE_CHECKING:
    from tui.app import InfinityApp


def refresh_app_locale(app: InfinityApp) -> None:
    try:
        app._update_tab_status()
    except Exception:
        return

    for tab_id, key in (
        ("tab-console-label", "tab_console"),
        ("tab-editor-label", "tab_editor"),
    ):
        try:
            tab = app.query_one(f"#{tab_id}", Tab)
            tab.label = i18n.t(key)
        except Exception:
            pass

    from tui.screens.console import ConsolePanel
    from tui.screens.editor import EditorPanel

    app.query_one("#console-panel", ConsolePanel).refresh_locale()
    app.query_one("#editor-panel", EditorPanel).refresh_locale()
    if hasattr(app, "_refresh_bindings"):
        app._refresh_bindings()


def _set_button(button_id: str, key: str, root) -> None:
    try:
        btn = root.query_one(f"#{button_id}", Button)
        btn.label = i18n.t(key)
    except Exception:
        pass


def _set_label(label_id: str, key: str, root) -> None:
    try:
        lbl = root.query_one(f"#{label_id}", Label)
        lbl.update(i18n.t(key))
    except Exception:
        pass


def _set_static(static_id: str, key: str, root) -> None:
    try:
        st = root.query_one(f"#{static_id}", Static)
        st.update(i18n.t(key))
    except Exception:
        pass


def _set_collapsible(collapsible_id: str, key: str, root) -> None:
    try:
        col = root.query_one(f"#{collapsible_id}", Collapsible)
        col.title = i18n.t(key)
    except Exception:
        pass


def _set_checkbox(checkbox_id: str, key: str, root) -> None:
    try:
        cb = root.query_one(f"#{checkbox_id}", Checkbox)
        cb.label = i18n.t(key)
    except Exception:
        pass


def _set_input_placeholder(input_id: str, key: str, root) -> None:
    try:
        inp = root.query_one(f"#{input_id}", Input)
        inp.placeholder = i18n.t(key)
    except Exception:
        pass
