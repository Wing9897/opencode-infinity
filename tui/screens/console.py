"""Console tab widget."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Button, Collapsible, Input, Label, Select, Static

from tui import i18n, services, state as ui_state
from tui.form_utils import select_empty
from tui.locale_refresh import (
    _set_button,
    _set_collapsible,
    _set_input_placeholder,
    _set_label,
    _set_static,
)
from tui.messages import ConfigListChanged, LogLine, StatsUpdated
from tui.runtime import RunController, stats_message_from_snapshot
from tui.services import ServiceError
from tui.widgets.log_panel import LogPanel, StatsBar


class ConsolePanel(Vertical):
    """Main control surface: config, start/stop, logs."""

    DEFAULT_CSS = """
    ConsolePanel {
        align: center top;
        height: 1fr;
    }
    """

    def __init__(self, controller: RunController, **kwargs) -> None:
        super().__init__(**kwargs)
        self.controller = controller
        self._configs: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="console-shell"):
            with Horizontal(classes="toolbar-row", id="console-controls"):
                yield Select(
                    [],
                    id="config-select",
                    prompt=i18n.t("prompt_select_config"),
                )
                yield Button(
                    i18n.t("btn_templates"), id="btn-templates", classes="action-btn"
                )
                yield Button(
                    i18n.t("btn_refresh"), id="btn-refresh", classes="action-btn"
                )
                yield Button(
                    i18n.t("btn_diagnose"), id="btn-diagnose", classes="action-btn"
                )
                yield Button(i18n.t("btn_start"), id="btn-start", classes="action-btn")
                yield Button(
                    i18n.t("btn_stop"), id="btn-stop", classes="action-btn", disabled=True
                )
            yield Static(
                i18n.t("hint_pick_config"),
                id="console-required-hint",
                classes="required-hint",
            )
            yield StatsBar(id="stats-bar")
            with Collapsible(
                title=i18n.t("advanced"),
                collapsed=True,
                classes="section-card",
                id="section-advanced",
            ):
                with Grid(classes="form-grid"):
                    yield Label(
                        i18n.t("label_working_dir"),
                        id="lbl-working-dir",
                        classes="form-label",
                    )
                    yield Input(
                        placeholder=i18n.t("placeholder_working_dir"),
                        id="working-dir",
                        classes="form-value",
                    )
                    yield Label(
                        i18n.t("label_session"),
                        id="lbl-session",
                        classes="form-label",
                    )
                    yield Input(
                        placeholder=i18n.t("placeholder_session"),
                        id="session-id",
                        classes="form-value",
                    )
            with Horizontal(classes="log-toolbar", id="log-toolbar"):
                yield Static(i18n.t("log_title"), id="log-header", classes="log-header")
                yield Button(
                    i18n.t("btn_copy_log"),
                    id="btn-copy-log",
                    classes="action-btn",
                )
            yield LogPanel(id="log-panel")

    def refresh_locale(self) -> None:
        select = self.query_one("#config-select", Select)
        select.prompt = i18n.t("prompt_select_config")
        _set_static("console-required-hint", "hint_pick_config", self)
        _set_static("log-header", "log_title", self)
        _set_button("btn-templates", "btn_templates", self)
        _set_button("btn-refresh", "btn_refresh", self)
        _set_button("btn-diagnose", "btn_diagnose", self)
        _set_button("btn-start", "btn_start", self)
        _set_button("btn-stop", "btn_stop", self)
        _set_button("btn-copy-log", "btn_copy_log", self)
        _set_collapsible("section-advanced", "advanced", self)
        _set_label("lbl-working-dir", "label_working_dir", self)
        _set_label("lbl-session", "label_session", self)
        _set_input_placeholder("working-dir", "placeholder_working_dir", self)
        _set_input_placeholder("session-id", "placeholder_session", self)
        self._reload_config_options()
        self._refresh_required_hints()
        self._update_stats_display()

    def _reload_config_options(self) -> None:
        """Refresh config dropdown labels without re-triggering selection logic."""
        select = self.query_one("#config-select", Select)
        current = select.value
        options = [(name, name) for name in self._configs] or [
            (i18n.t("no_configs"), "")
        ]
        select.set_options(options)
        if isinstance(current, str) and current and select.value != current:
            select.value = current

    def on_mount(self) -> None:
        self.refresh_configs()
        saved = ui_state.get_selected_config()
        if saved:
            self._select_config(saved)
        self._update_stats_display()
        self._refresh_required_hints()
        self.query_one("#log-panel", LogPanel).append_line(i18n.t("log_empty"))

    def _refresh_required_hints(self) -> None:
        select = self.query_one("#config-select", Select)
        hint = self.query_one("#console-required-hint", Static)
        missing = select_empty(select)
        if missing:
            hint.update(i18n.t("hint_pick_config"))
            hint.remove_class("-ok")
        else:
            hint.update(i18n.t("hint_pick_config_ok"))
            hint.add_class("-ok")

    def refresh_configs(self) -> None:
        self._configs = services.list_configs()
        select = self.query_one("#config-select", Select)
        options = [(name, name) for name in self._configs] or [
            (i18n.t("no_configs"), "")
        ]
        select.set_options(options)
        if self._configs:
            saved = ui_state.get_selected_config()
            if saved in self._configs:
                select.value = saved
            else:
                select.value = self._configs[0]
            self._on_config_changed()
        self._refresh_required_hints()

    def _select_config(self, name: str) -> None:
        if name in self._configs:
            self.query_one("#config-select", Select).value = name
            self._on_config_changed()

    def _on_config_changed(self) -> None:
        select = self.query_one("#config-select", Select)
        name = select.value
        if not isinstance(name, str) or not name:
            return
        ui_state.set_selected_config(name)
        override = ui_state.get_working_dir_override(name)
        self.query_one("#working-dir", Input).value = override

    def on_select_changed(self, event: Select.Changed) -> None:
        if getattr(self.app, "_locale_changing", False):
            return
        if event.select.id == "config-select":
            self._on_config_changed()
            self._refresh_required_hints()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "working-dir":
            select = self.query_one("#config-select", Select)
            name = select.value
            if isinstance(name, str) and name:
                ui_state.set_working_dir_override(name, event.value.strip())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "btn-refresh":
            self.refresh_configs()
            self.notify(i18n.t("toast_configs_reloaded"))
        elif button_id == "btn-templates":
            self._create_templates()
        elif button_id == "btn-diagnose":
            self._run_diagnose()
        elif button_id == "btn-start":
            self._start_run()
        elif button_id == "btn-stop":
            self.controller.stop()
            self.notify(i18n.t("toast_stopped"))
        elif button_id == "btn-copy-log":
            self.copy_log()

    def copy_log(self) -> None:
        panel = self.query_one("#log-panel", LogPanel)
        text = panel.plain_text().strip()
        if not text:
            self.notify(i18n.t("toast_log_copy_empty"), severity="warning")
            return
        self.app.copy_to_clipboard(text)
        self.notify(i18n.t("toast_log_copied"))

    def _create_templates(self) -> None:
        result = services.create_templates()
        created = result.get("created", [])
        overwritten = result.get("overwritten", [])
        names = ", ".join(created + overwritten) or i18n.t("templates_none")
        self.notify(i18n.t("toast_templates", names=names))
        self.refresh_configs()

    def _run_diagnose(self) -> None:
        report = services.get_diagnose()
        log = self.query_one("#log-panel", LogPanel)
        log.append_line(
            f"--- {i18n.t('diag_title')} ---",
        )
        build = report.get("build") or {}
        if build:
            log.append_line(
                f"  {i18n.t('diag_infinity')}: {build.get('mode')} {build.get('version')}"
            )
        opencode = report.get("opencode")
        if opencode:
            log.append_line(
                f"  {i18n.t('diag_opencode')}: {opencode.get('version')} "
                f"@ {opencode.get('path')}"
            )
            log.append_line(
                f"  {i18n.t('diag_headless')}: {opencode.get('headless_mode')}"
            )
        if report.get("config_dir"):
            log.append_line(f"  {i18n.t('diag_config_dir')}: {report['config_dir']}")
        if report.get("working_dir"):
            log.append_line(f"  {i18n.t('diag_cwd')}: {report['working_dir']}")
        issues = report.get("issues") or []
        if issues:
            for issue in issues:
                log.append_line(f"  ! {issue}")
        else:
            log.append_line(f"  {i18n.t('diag_no_issues')}")

    def _start_run(self) -> None:
        select = self.query_one("#config-select", Select)
        config_name = select.value
        if not isinstance(config_name, str) or not config_name:
            self._refresh_required_hints()
            self.notify(i18n.t("toast_select_config"))
            return
        session_id = self.query_one("#session-id", Input).value.strip()
        working_dir = self.query_one("#working-dir", Input).value.strip()
        try:
            session_id, resolved = services.prepare_start(
                config_name, session_id, working_dir
            )
        except ServiceError as exc:
            self.notify(str(exc), severity="error")
            return
        self.query_one("#session-id", Input).value = session_id
        try:
            self.controller.start(
                config_name,
                session_id,
                working_dir_override=working_dir or None,
            )
        except RuntimeError as exc:
            self.notify(str(exc), severity="error")
            return
        self.query_one("#btn-start", Button).disabled = True
        self.query_one("#btn-stop", Button).disabled = False
        self.notify(i18n.t("toast_started"))

    def on_log_line(self, message: LogLine) -> None:
        panel = self.query_one("#log-panel", LogPanel)
        panel.append_line(message.text)

    def on_stats_updated(self, message: StatsUpdated) -> None:
        self._update_stats_display(message)

    def _update_stats_display(self, message: StatsUpdated | None = None) -> None:
        if message is None:
            message = stats_message_from_snapshot(self.controller.snapshot())
        minutes = int(message.elapsed_seconds) // 60
        seconds = int(message.elapsed_seconds) % 60
        elapsed = f"{minutes}:{seconds:02d}"
        stats = self.query_one("#stats-bar", StatsBar)
        if message.running:
            stats.add_class("running")
            status = i18n.t("status_running")
        else:
            stats.remove_class("running")
            status = i18n.t("status_idle")
        config = message.config_name or "-"
        stats.update(
            f"{status}  |  {i18n.t('stat_elapsed')}: {elapsed}  |  {config}"
        )
        self.query_one("#btn-start", Button).disabled = message.running
        self.query_one("#btn-stop", Button).disabled = not message.running

    def on_config_list_changed(self, message: ConfigListChanged) -> None:
        self._configs = message.configs
        select = self.query_one("#config-select", Select)
        options = [(name, name) for name in self._configs] or [
            (i18n.t("no_configs"), "")
        ]
        select.set_options(options)
