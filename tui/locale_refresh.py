"""Refresh visible UI strings after locale change."""
from __future__ import annotations

from typing import TYPE_CHECKING

from textual.widgets import Button, Checkbox, Collapsible, Input, Label, Select, Static
from textual.widgets._tabbed_content import ContentTab

from tui import i18n, state as ui_state

if TYPE_CHECKING:
    from tui.app import InfinityApp


def refresh_app_locale(app: InfinityApp) -> None:
    try:
        app.query_one("#brand-mark", Static).update(
            f"∞ {i18n.t('brand_subtitle')}"
        )
        density = app.query_one("#density-indicator", Static)
        density.update(
            f"[dim]{i18n.t('label_layout')}[/] "
            f"{i18n.t(f'density_{ui_state.get_ui_density()}')}"
        )
        locale = i18n.get_locale()
        app.query_one("#locale-indicator", Static).update(
            f"[dim]{i18n.t('label_language')}[/] "
            f"{i18n.t('locale_zh') if locale == 'zh-TW' else i18n.t('locale_en')}"
        )
        app._update_round_indicator()
    except Exception:
        return

    for pane_id, key in (
        ("tab-console", "tab_console"),
        ("tab-editor", "tab_editor"),
    ):
        try:
            tab = app.query_one(f"#{ContentTab.add_prefix(pane_id)}")
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
