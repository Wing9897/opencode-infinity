"""Console tab widget."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Collapsible, Input, Label, Select, Static

from tui import i18n, services, state as ui_state
from tui.messages import ConfigListChanged, LogLine, StatsUpdated
from tui.runtime import RunController
from tui.services import ServiceError
from tui.widgets.log_panel import LogPanel, StatsBar


class ConsolePanel(Vertical):
    """Main control surface: config, start/stop, logs."""

    DEFAULT_CSS = """
    ConsolePanel {
        height: 1fr;
    }
    #console-controls {
        height: auto;
        padding: 0 0 1 0;
    }
    #config-select {
        width: 1fr;
    }
    .action-btn {
        min-width: 12;
    }
    #advanced-grid {
        height: auto;
        padding: 1 0;
    }
    """

    def __init__(self, controller: RunController, **kwargs) -> None:
        super().__init__(**kwargs)
        self.controller = controller
        self._configs: list[str] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="console-controls"):
            yield Select([], id="config-select", prompt=i18n.t("label_config"))
            yield Button(i18n.t("btn_templates"), id="btn-templates", classes="action-btn")
            yield Button(i18n.t("btn_refresh"), id="btn-refresh", classes="action-btn")
            yield Button(i18n.t("btn_diagnose"), id="btn-diagnose", classes="action-btn")
            yield Button(i18n.t("btn_start"), id="btn-start", variant="success", classes="action-btn")
            yield Button(i18n.t("btn_stop"), id="btn-stop", variant="error", classes="action-btn", disabled=True)
        yield StatsBar(id="stats-bar")
        with Collapsible(title=i18n.t("advanced"), collapsed=True):
            with Vertical(id="advanced-grid"):
                yield Label(i18n.t("label_working_dir"))
                yield Input(placeholder="留空沿用 YAML / 啟動目錄", id="working-dir")
                yield Label(i18n.t("label_session"))
                yield Input(placeholder="ses_...（留空自動生成）", id="session-id")
        yield Label(i18n.t("log_title"))
        yield LogPanel(id="log-panel")

    def on_mount(self) -> None:
        self.refresh_configs()
        saved = ui_state.get_selected_config()
        if saved:
            self._select_config(saved)
        self._update_stats_display()
        self.query_one("#log-panel", LogPanel).write(i18n.t("log_empty"))

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
        if event.select.id == "config-select":
            self._on_config_changed()

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
            self.notify("Configs refreshed")
        elif button_id == "btn-templates":
            self._create_templates()
        elif button_id == "btn-diagnose":
            self._run_diagnose()
        elif button_id == "btn-start":
            self._start_run()
        elif button_id == "btn-stop":
            self.controller.stop()
            self.notify(i18n.t("toast_stopped"))

    def _create_templates(self) -> None:
        result = services.create_templates()
        created = result.get("created", [])
        overwritten = result.get("overwritten", [])
        names = ", ".join(created + overwritten) or "none"
        self.notify(i18n.t("toast_templates", names=names))
        self.refresh_configs()

    def _run_diagnose(self) -> None:
        report = services.get_diagnose()
        log = self.query_one("#log-panel", LogPanel)
        log.write("🔍 環境診斷")
        build = report.get("build") or {}
        if build:
            log.write(f"  Infinity: {build.get('mode')} {build.get('version')}")
        opencode = report.get("opencode")
        if opencode:
            log.write(
                f"  OpenCode: {opencode.get('version')} @ {opencode.get('path')}"
            )
            log.write(f"  Headless: {opencode.get('headless_mode')}")
        if report.get("config_dir"):
            log.write(f"  Config: {report['config_dir']}")
        if report.get("working_dir"):
            log.write(f"  CWD: {report['working_dir']}")
        issues = report.get("issues") or []
        if issues:
            for issue in issues:
                log.write(f"  ⚠️ {issue}")
        else:
            log.write("  ✅ 未發現問題")

    def _start_run(self) -> None:
        select = self.query_one("#config-select", Select)
        config_name = select.value
        if not isinstance(config_name, str) or not config_name:
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
        self.query_one("#log-panel", LogPanel).append_line(message.text)

    def on_stats_updated(self, message: StatsUpdated) -> None:
        self._update_stats_display(message)

    def _update_stats_display(self, message: StatsUpdated | None = None) -> None:
        if message is None:
            snap = self.controller.snapshot()
            message = StatsUpdated(
                running=snap["running"],
                round_count=snap["round_count"],
                session_count=snap["session_count"],
                session_id=snap["session_id"],
                config_name=snap["config_name"],
                working_dir=snap["working_dir"],
                elapsed_seconds=(
                    __import__("time").monotonic() - snap["start_time"]
                    if snap["start_time"] > 0 and snap["running"]
                    else 0.0
                ),
            )
        minutes = int(message.elapsed_seconds) // 60
        seconds = int(message.elapsed_seconds) % 60
        elapsed = f"{minutes}:{seconds:02d}"
        status = i18n.t("status_running") if message.running else i18n.t("status_idle")
        config = message.config_name or "-"
        self.query_one("#stats-bar", StatsBar).update(
            f"{status} | {config} | "
            f"{i18n.t('stat_rounds')}: {message.round_count} | "
            f"{i18n.t('stat_sessions')}: {message.session_count} | "
            f"{i18n.t('stat_elapsed')}: {elapsed} | "
            f"Session: {message.session_id or '-'}"
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
