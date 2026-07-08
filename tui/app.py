"""OpenCode Infinity Textual application."""
from __future__ import annotations

import sys
import threading

import opencode_infinity as core
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from tui import i18n, state as ui_state
from tui.locale_refresh import refresh_app_locale
from tui.styles import APP_CSS
from tui.messages import LogLine, StatsUpdated
from tui.runtime import RunController, stats_message_from_snapshot
from tui.screens.console import ConsolePanel
from tui.screens.editor import EditorPanel


class InfinityApp(App):
    """Unified Textual UI for OpenCode Infinity."""

    TITLE = "OpenCode Infinity"
    CSS = APP_CSS

    BINDINGS = [
        Binding("ctrl+s", "save_editor", "Save", show=True, key_display="ctrl+s"),
        Binding("ctrl+l", "toggle_locale", "Lang", show=True, key_display="ctrl+l"),
        Binding("ctrl+shift+c", "copy_log", "Copy log", show=True, key_display="ctrl+shift+c"),
        Binding("ctrl+q", "quit", "Quit", show=True, key_display="ctrl+q"),
        Binding("ctrl+equal", "density_up", "Larger", show=True, key_display="ctrl+="),
        Binding("ctrl+minus", "density_down", "Smaller", show=True, key_display="ctrl+-"),
    ]

    def _refresh_bindings(self) -> None:
        self.BINDINGS = [
            Binding(
                "ctrl+s",
                "save_editor",
                i18n.t("binding_save"),
                show=True,
                key_display="ctrl+s",
            ),
            Binding(
                "ctrl+l",
                "toggle_locale",
                i18n.t("binding_lang"),
                show=True,
                key_display="ctrl+l",
            ),
            Binding(
                "ctrl+shift+c",
                "copy_log",
                i18n.t("binding_copy_log"),
                show=True,
                key_display="ctrl+shift+c",
            ),
            Binding(
                "ctrl+q",
                "quit",
                i18n.t("binding_quit"),
                show=True,
                key_display="ctrl+q",
            ),
            Binding(
                "ctrl+equal",
                "density_up",
                i18n.t("binding_larger"),
                show=True,
                key_display="ctrl+=",
            ),
            Binding(
                "ctrl+minus",
                "density_down",
                i18n.t("binding_smaller"),
                show=True,
                key_display="ctrl+-",
            ),
        ]
        self.refresh_bindings()

    def __init__(self) -> None:
        super().__init__()
        self._locale_changing = False
        self.controller = RunController(
            on_log=self._emit_log,
            on_stats=self._emit_stats,
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="top-bar"):
            yield Static(
                f"∞ {i18n.t('brand_subtitle')}",
                id="brand-mark",
            )
            yield Static("", id="density-indicator")
            yield Static("", id="round-indicator")
            yield Static("", id="locale-indicator")
        with TabbedContent():
            with TabPane(i18n.t("tab_console"), id="tab-console"):
                yield ConsolePanel(self.controller, id="console-panel")
            with TabPane(i18n.t("tab_editor"), id="tab-editor"):
                yield EditorPanel(id="editor-panel")
        yield Footer()

    def on_mount(self) -> None:
        locale = ui_state.get_locale()
        if locale in ("zh-TW", "en"):
            i18n.set_locale(locale)
        self._apply_density()
        self._update_locale_indicator()
        self._update_round_indicator()
        self._refresh_bindings()
        self.set_interval(1.0, self._tick_stats)

    def _locale_display(self, locale: str) -> str:
        return i18n.t("locale_zh") if locale == "zh-TW" else i18n.t("locale_en")

    def _update_locale_indicator(self) -> None:
        locale = i18n.get_locale()
        indicator = self.query_one("#locale-indicator", Static)
        indicator.update(
            f"[dim]{i18n.t('label_language')}[/] {self._locale_display(locale)}"
        )

    def _update_round_indicator(
        self,
        *,
        running: bool | None = None,
        round_count: int | None = None,
    ) -> None:
        snap = self.controller.snapshot()
        if running is None:
            running = snap["running"]
        if round_count is None:
            round_count = snap["round_count"]
        indicator = self.query_one("#round-indicator", Static)
        indicator.update(f"{i18n.t('stat_rounds')}: {round_count}")
        if running:
            indicator.add_class("running")
        else:
            indicator.remove_class("running")

    def action_toggle_locale(self) -> None:
        current = i18n.get_locale()
        new_locale = "en" if current == "zh-TW" else "zh-TW"
        if self._locale_changing:
            return
        self._locale_changing = True
        try:
            i18n.set_locale(new_locale)
            if not self.is_mounted:
                return
            refresh_app_locale(self)
            self._update_locale_indicator()
            self._update_round_indicator()
            self._refresh_bindings()
            self.notify(
                i18n.t(
                    "toast_locale_switched_to",
                    lang=self._locale_display(new_locale),
                )
            )
        finally:
            self._locale_changing = False

    def _density_label(self, density: str) -> str:
        return i18n.t(f"density_{density}")

    def _apply_density(self) -> None:
        density = ui_state.get_ui_density()
        screen = self.screen
        for name in ui_state.UI_DENSITIES:
            screen.remove_class(f"density-{name}")
        screen.add_class(f"density-{density}")
        indicator = self.query_one("#density-indicator", Static)
        indicator.update(
            f"[dim]{i18n.t('label_layout')}[/] {self._density_label(density)}"
        )

    def action_density_up(self) -> None:
        order = ui_state.UI_DENSITIES
        current = ui_state.get_ui_density()
        index = min(order.index(current) + 1, len(order) - 1)
        ui_state.set_ui_density(order[index])
        self._apply_density()
        self.notify(i18n.t("toast_density", density=self._density_label(order[index])))

    def action_density_down(self) -> None:
        order = ui_state.UI_DENSITIES
        current = ui_state.get_ui_density()
        index = max(order.index(current) - 1, 0)
        ui_state.set_ui_density(order[index])
        self._apply_density()
        self.notify(i18n.t("toast_density", density=self._density_label(order[index])))

    def _dispatch_to_ui(self, callback, *args, **kwargs) -> None:
        """Run a UI callback from the worker thread or directly on the app thread."""
        if threading.current_thread() is threading.main_thread():
            callback(*args, **kwargs)
        else:
            self.call_from_thread(callback, *args, **kwargs)

    def _emit_log(self, text: str, source: str = "cli") -> None:
        self._dispatch_to_ui(self.post_message, LogLine(text, source=source))

    def _emit_stats(self) -> None:
        self._dispatch_to_ui(self._post_stats)

    def _post_stats(self) -> None:
        self.post_message(stats_message_from_snapshot(self.controller.snapshot()))

    def _tick_stats(self) -> None:
        if self.controller.snapshot()["running"]:
            self._post_stats()

    def on_log_line(self, message: LogLine) -> None:
        console = self.query_one("#console-panel", ConsolePanel)
        console.on_log_line(message)

    def on_stats_updated(self, message: StatsUpdated) -> None:
        self._update_round_indicator(
            running=message.running,
            round_count=message.round_count,
        )
        console = self.query_one("#console-panel", ConsolePanel)
        console.on_stats_updated(message)

    def refresh_all_configs(self, select_name: str = "") -> None:
        console = self.query_one("#console-panel", ConsolePanel)
        console.refresh_configs()
        if select_name:
            console._select_config(select_name)
        editor = self.query_one("#editor-panel", EditorPanel)
        editor._reload_config_list()

    def action_copy_log(self) -> None:
        console = self.query_one("#console-panel", ConsolePanel)
        console.copy_log()

    def action_save_editor(self) -> None:
        editor = self.query_one("#editor-panel", EditorPanel)
        editor._save_config()

    def action_quit(self) -> None:
        if self.controller.snapshot()["running"]:
            self.notify(i18n.t("toast_quit_running"), severity="warning")
            return
        self.exit()


def run_app() -> None:
    """Launch the Textual TUI."""
    core._configure_stdio_encoding()
    for issue in core._runtime_self_check():
        core._eprint(f"Self-check warning: {issue}")
    InfinityApp().run()


if __name__ == "__main__":
    run_app()
