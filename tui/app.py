"""OpenCode Infinity Textual application."""
from __future__ import annotations

import sys
import time

import opencode_infinity as core
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Select, TabbedContent, TabPane

from tui import i18n, state as ui_state
from tui.messages import LogLine, StatsUpdated
from tui.runtime import RunController
from tui.screens.console import ConsolePanel
from tui.screens.editor import EditorPanel


class InfinityApp(App):
    """Unified Textual UI for OpenCode Infinity."""

    TITLE = "OpenCode Infinity"
    CSS = """
    Screen {
        layout: vertical;
    }
    TabbedContent {
        height: 1fr;
    }
    TabPane {
        padding: 1 2;
    }
    #locale-select {
        dock: right;
        width: 14;
        margin: 0 2 0 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save_editor", "Save", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.controller = RunController(
            on_log=self._emit_log,
            on_stats=self._emit_stats,
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Select(
            [(i18n.t("locale_zh"), "zh-TW"), (i18n.t("locale_en"), "en")],
            id="locale-select",
            value=i18n.get_locale(),
        )
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
            self.query_one("#locale-select", Select).value = locale
        self.set_interval(1.0, self._tick_stats)

    def _emit_log(self, text: str) -> None:
        self.call_from_thread(self.post_message, LogLine(text))

    def _emit_stats(self) -> None:
        self.call_from_thread(self._post_stats)

    def _post_stats(self) -> None:
        snap = self.controller.snapshot()
        elapsed = (
            time.monotonic() - snap["start_time"]
            if snap["start_time"] > 0 and snap["running"]
            else 0.0
        )
        self.post_message(
            StatsUpdated(
                running=snap["running"],
                round_count=snap["round_count"],
                session_count=snap["session_count"],
                session_id=snap["session_id"],
                config_name=snap["config_name"],
                working_dir=snap["working_dir"],
                elapsed_seconds=elapsed,
            )
        )

    def _tick_stats(self) -> None:
        if self.controller.snapshot()["running"]:
            self._post_stats()

    def on_log_line(self, message: LogLine) -> None:
        console = self.query_one("#console-panel", ConsolePanel)
        console.on_log_line(message)

    def on_stats_updated(self, message: StatsUpdated) -> None:
        console = self.query_one("#console-panel", ConsolePanel)
        console.on_stats_updated(message)

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "locale-select" and isinstance(event.value, str):
            i18n.set_locale(event.value)
            self.notify(f"Locale: {event.value}")

    def refresh_all_configs(self, select_name: str = "") -> None:
        console = self.query_one("#console-panel", ConsolePanel)
        console.refresh_configs()
        if select_name:
            console._select_config(select_name)
        editor = self.query_one("#editor-panel", EditorPanel)
        editor._reload_config_list()

    def action_save_editor(self) -> None:
        editor = self.query_one("#editor-panel", EditorPanel)
        editor._save_config()

    def action_quit(self) -> None:
        if self.controller.snapshot()["running"]:
            self.notify("Stop the task before quitting.", severity="warning")
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
