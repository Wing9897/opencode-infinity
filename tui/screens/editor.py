"""Config editor tab widget."""
from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Collapsible, Input, Label, Select, Static, TextArea

from tui import i18n, services
from tui.form_utils import req_label, req_title, select_empty, text_area_empty
from tui.locale_refresh import (
    _set_button,
    _set_checkbox,
    _set_collapsible,
    _set_input_placeholder,
    _set_label,
    _set_static,
)
from tui.screens.aigen_modal import AigenModal
from tui.screens.new_config_modal import NewConfigModal
from tui.services import ServiceError

NEW_CONFIG_VALUE = "__new__"


class EditorPanel(VerticalScroll):
    """YAML config editor form."""

    DEFAULT_CSS = """
    EditorPanel {
        height: 1fr;
        width: 100%;
        align: center top;
    }
    #editor-shell {
        width: 96;
        max-width: 96;
        height: auto;
        padding: 0 1;
    }
    .compact-toolbar {
        width: 100%;
    }
    .compact-toolbar .form-label {
        width: auto;
        min-width: 8;
    }
    #ed-config-select {
        width: 1fr;
        min-width: 24;
        margin: 0 1 0 0;
    }
    #editor-shell .form-grid {
        grid-size: 2;
        grid-gutter: 0 2;
    }
    #editor-shell .prompt-area {
        height: 3;
        min-height: 3;
    }
    #ed-summary-prompt {
        height: 3;
        min-height: 3;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._prompt_ids: list[str] = []
        self._prompt_counter = 0
        self._dirty = False
        self._pending_names: list[str] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="editor-shell"):
            with Horizontal(classes="toolbar-row compact-toolbar"):
                yield Static(
                    req_label("label_config_file"),
                    id="ed-config-label",
                    classes="form-label form-label-required",
                )
                yield Select(
                    [],
                    id="ed-config-select",
                    prompt=i18n.t("prompt_select_config"),
                )
                yield Button(
                    i18n.t("btn_new_config"), id="ed-new-btn", classes="action-btn"
                )
                yield Button(
                    i18n.t("btn_reload_list"), id="ed-reload-btn", classes="action-btn"
                )
            yield Static(
                i18n.t("hint_select_config"),
                id="editor-config-hint",
                classes="required-hint",
            )
            yield Static("", id="editor-status")

            with Collapsible(
                title=req_title("section_cli"),
                collapsed=False,
                classes="section-card",
                id="section-cli",
            ):
                with Grid(classes="form-grid"):
                    yield Static(
                        req_label("label_tool"),
                        id="lbl-cli-tool",
                        classes="form-label form-label-required",
                    )
                    yield Select(
                        [
                            ("OpenCode", "opencode"),
                            ("Codex", "codex"),
                            ("Claude (experimental)", "claude"),
                            ("Copilot (experimental)", "copilot"),
                        ],
                        id="ed-cli-tool",
                        value="opencode",
                        classes="form-value",
                    )
                    yield Label(
                        i18n.t("label_model"),
                        id="lbl-cli-model",
                        classes="form-label",
                    )
                    yield Input(
                        id="ed-cli-model",
                        classes="form-value",
                        placeholder=i18n.t("placeholder_model"),
                    )
                with Collapsible(
                    title=i18n.t("section_codex_opts"),
                    collapsed=True,
                    id="section-codex",
                ):
                    with Horizontal(classes="checkbox-row"):
                        yield Checkbox(
                            i18n.t("label_full_auto"), id="ed-cli-fullauto"
                        )
                        yield Checkbox(i18n.t("label_search"), id="ed-cli-search")

            with Collapsible(
                title=req_title("section_prompts"),
                collapsed=False,
                classes="section-card",
                id="section-prompts",
            ):
                yield Static(
                    i18n.t("hint_prompt"),
                    id="editor-prompt-hint",
                    classes="required-hint",
                )
                yield Vertical(id="prompt-list")
                yield Button(i18n.t("btn_add_prompt"), id="ed-add-prompt")
                yield Label(
                    i18n.t("label_summary"),
                    id="lbl-summary",
                    classes="form-label",
                )
                yield TextArea(id="ed-summary-prompt", classes="prompt-area")

            with Collapsible(
                title=i18n.t("section_exec_basic"),
                collapsed=False,
                classes="section-card",
                id="section-exec-basic",
            ):
                with Grid(classes="form-grid"):
                    yield Label(
                        i18n.t("field_delay"),
                        id="lbl-delay",
                        classes="form-label",
                    )
                    yield Input(id="ed-exec-delay", value="1", classes="form-value")
                    yield Label(
                        i18n.t("field_timeout"),
                        id="lbl-timeout",
                        classes="form-label",
                    )
                    yield Input(
                        id="ed-exec-timeout", value="300", classes="form-value"
                    )
                    yield Label(
                        i18n.t("field_retries"),
                        id="lbl-retries",
                        classes="form-label",
                    )
                    yield Input(
                        id="ed-exec-retries", value="5", classes="form-value"
                    )
                    yield Label(
                        i18n.t("field_max_rounds"),
                        id="lbl-rounds",
                        classes="form-label",
                    )
                    yield Input(
                        id="ed-exec-rounds", value="0", classes="form-value"
                    )
                with Horizontal(classes="checkbox-row"):
                    yield Checkbox(
                        i18n.t("label_continue_on_error"),
                        id="ed-exec-continue",
                        value=True,
                    )

            with Collapsible(
                title=i18n.t("section_exec_advanced"),
                collapsed=True,
                classes="section-card",
                id="section-exec-advanced",
            ):
                with Grid(classes="form-grid"):
                    yield Label(
                        i18n.t("field_switch_rounds"),
                        id="lbl-switch-rounds",
                        classes="form-label",
                    )
                    yield Input(
                        id="ed-exec-switch-rounds",
                        value="0",
                        classes="form-value",
                    )
                    yield Label(
                        i18n.t("field_strategy"),
                        id="lbl-strategy",
                        classes="form-label",
                    )
                    yield Select(
                        [
                            (i18n.t("switch_auto"), "auto"),
                            (i18n.t("switch_token"), "token"),
                            (i18n.t("switch_rounds"), "rounds"),
                        ],
                        id="ed-exec-switch-strategy",
                        value="auto",
                        classes="form-value",
                    )
                    yield Label(
                        i18n.t("field_max_tokens"),
                        id="lbl-max-tokens",
                        classes="form-label",
                    )
                    yield Input(
                        id="ed-max-tokens", value="128000", classes="form-value"
                    )
                    yield Label(
                        i18n.t("field_token_threshold"),
                        id="lbl-token-threshold",
                        classes="form-label",
                    )
                    yield Input(
                        id="ed-token-threshold", value="0.7", classes="form-value"
                    )
                    yield Label(
                        i18n.t("field_working_dir"),
                        id="lbl-working-dir",
                        classes="form-label",
                    )
                    yield Input(id="ed-exec-working-dir", classes="form-value")

            with Collapsible(
                title=i18n.t("section_display"),
                collapsed=True,
                classes="section-card",
                id="section-display",
            ):
                with Horizontal(classes="checkbox-row"):
                    yield Checkbox(
                        i18n.t("label_show_session"),
                        id="ed-disp-session",
                        value=True,
                    )
                    yield Checkbox(
                        i18n.t("label_show_token"),
                        id="ed-disp-token",
                        value=True,
                    )
                    yield Checkbox(
                        i18n.t("label_show_time"),
                        id="ed-disp-time",
                        value=True,
                    )

            with Horizontal(classes="editor-actions"):
                yield Button(i18n.t("btn_aigen"), id="ed-aigen-btn")
                yield Button(i18n.t("btn_save"), id="ed-save-btn", variant="primary")
                yield Button(i18n.t("btn_reset"), id="ed-reset-btn", variant="warning")

    def on_mount(self) -> None:
        self._reload_config_list()
        self._add_prompt("")
        summary = self.query_one("#ed-summary-prompt", TextArea)
        summary.load_text(i18n.t("default_summary"))
        self._refresh_required_hints()

    def refresh_locale(self) -> None:
        self.query_one("#ed-config-label", Static).update(req_label("label_config_file"))
        _set_static("editor-config-hint", "hint_select_config", self)
        _set_static("editor-prompt-hint", "hint_prompt", self)
        _set_button("ed-new-btn", "btn_new_config", self)
        _set_button("ed-reload-btn", "btn_reload_list", self)
        _set_button("ed-add-prompt", "btn_add_prompt", self)
        _set_button("ed-aigen-btn", "btn_aigen", self)
        _set_button("ed-save-btn", "btn_save", self)
        _set_button("ed-reset-btn", "btn_reset", self)
        self.query_one("#section-cli", Collapsible).title = req_title("section_cli")
        _set_collapsible("section-codex", "section_codex_opts", self)
        _set_collapsible("section-exec-basic", "section_exec_basic", self)
        _set_collapsible("section-exec-advanced", "section_exec_advanced", self)
        _set_collapsible("section-display", "section_display", self)
        self.query_one("#section-prompts", Collapsible).title = req_title("section_prompts")
        self.query_one("#lbl-cli-tool", Static).update(req_label("label_tool"))
        _set_label("lbl-cli-model", "label_model", self)
        _set_label("lbl-delay", "field_delay", self)
        _set_label("lbl-timeout", "field_timeout", self)
        _set_label("lbl-retries", "field_retries", self)
        _set_label("lbl-rounds", "field_max_rounds", self)
        _set_label("lbl-switch-rounds", "field_switch_rounds", self)
        _set_label("lbl-strategy", "field_strategy", self)
        _set_label("lbl-max-tokens", "field_max_tokens", self)
        _set_label("lbl-token-threshold", "field_token_threshold", self)
        _set_label("lbl-working-dir", "field_working_dir", self)
        _set_label("lbl-summary", "label_summary", self)
        _set_checkbox("ed-cli-fullauto", "label_full_auto", self)
        _set_checkbox("ed-cli-search", "label_search", self)
        _set_checkbox("ed-exec-continue", "label_continue_on_error", self)
        _set_checkbox("ed-disp-session", "label_show_session", self)
        _set_checkbox("ed-disp-token", "label_show_token", self)
        _set_checkbox("ed-disp-time", "label_show_time", self)
        _set_input_placeholder("ed-cli-model", "placeholder_model", self)
        strategy = self.query_one("#ed-exec-switch-strategy", Select)
        current = strategy.value
        strategy.set_options(
            [
                (i18n.t("switch_auto"), "auto"),
                (i18n.t("switch_token"), "token"),
                (i18n.t("switch_rounds"), "rounds"),
            ]
        )
        if isinstance(current, str):
            if current != strategy.value:
                strategy.value = current
        select = self.query_one("#ed-config-select", Select)
        select.prompt = i18n.t("prompt_select_config")
        self._reload_config_list()
        self._refresh_required_hints()

    def _selected_config_name(self) -> str:
        value = self.query_one("#ed-config-select", Select).value
        if not isinstance(value, str):
            return ""
        if value in ("", NEW_CONFIG_VALUE):
            return ""
        return value

    def _first_prompt_area(self) -> TextArea | None:
        if not self._prompt_ids:
            return None
        return self.query_one(f"#{self._prompt_ids[0]}", TextArea)

    def _refresh_required_hints(self) -> None:
        select = self.query_one("#ed-config-select", Select)
        config_hint = self.query_one("#editor-config-hint", Static)
        config_missing = select_empty(select) or select.value == NEW_CONFIG_VALUE
        if config_missing:
            config_hint.update(i18n.t("hint_select_config"))
            config_hint.remove_class("-ok")
        else:
            config_hint.update(i18n.t("hint_select_config_ok"))
            config_hint.add_class("-ok")

        prompt_hint = self.query_one("#editor-prompt-hint", Static)
        first_prompt = self._first_prompt_area()
        prompt_missing = first_prompt is None or text_area_empty(first_prompt)
        if prompt_missing:
            prompt_hint.update(i18n.t("hint_prompt"))
            prompt_hint.remove_class("-ok")
        else:
            prompt_hint.update(i18n.t("hint_prompt_ok"))
            prompt_hint.add_class("-ok")

    def _reload_config_list(self) -> None:
        configs = list(services.list_configs())
        for name in self._pending_names:
            if name not in configs:
                configs.append(name)
        configs.sort()
        options = [(name, name) for name in configs]
        options.append((i18n.t("option_new_config"), NEW_CONFIG_VALUE))
        select = self.query_one("#ed-config-select", Select)
        current = select.value
        select.set_options(options or [(i18n.t("no_configs"), "")])
        if isinstance(current, str) and current:
            if current == NEW_CONFIG_VALUE or any(
                value == current for _, value in options
            ):
                if select.value != current:
                    select.value = current

    def _add_prompt(self, content: str = "") -> None:
        self._prompt_counter += 1
        prompt_id = f"prompt-{self._prompt_counter}"
        self._prompt_ids.append(prompt_id)
        container = self.query_one("#prompt-list", Vertical)
        row = Horizontal(classes="prompt-row", id=f"row-{prompt_id}")
        area = TextArea(content, id=prompt_id, classes="prompt-area")
        delete_btn = Button(
            "×",
            id=f"del-{prompt_id}",
            classes="prompt-del-btn",
            variant="error",
        )
        container.mount(row)
        row.mount(area)
        row.mount(delete_btn)
        self.call_after_refresh(self._refresh_required_hints)

    def _remove_prompt(self, prompt_id: str) -> None:
        if prompt_id not in self._prompt_ids or len(self._prompt_ids) <= 1:
            self.notify(i18n.t("toast_prompt_min"), severity="warning")
            return
        self._prompt_ids.remove(prompt_id)
        self.query_one(f"#row-{prompt_id}", Horizontal).remove()
        self._dirty = True
        self._refresh_required_hints()

    def _collect_config(self) -> dict[str, Any]:
        tool = self.query_one("#ed-cli-tool", Select).value
        if not isinstance(tool, str):
            tool = "opencode"
        config: dict[str, Any] = {"cli": {"tool": tool}}
        model = self.query_one("#ed-cli-model", Input).value.strip()
        if model:
            config["cli"]["model"] = model
        if tool == "codex":
            config["cli"]["full_auto"] = self.query_one(
                "#ed-cli-fullauto", Checkbox
            ).value
            config["cli"]["search"] = self.query_one("#ed-cli-search", Checkbox).value
        execution: dict[str, Any] = {
            "delay": int(self.query_one("#ed-exec-delay", Input).value or 1),
            "timeout": int(self.query_one("#ed-exec-timeout", Input).value or 300),
            "max_retries": int(self.query_one("#ed-exec-retries", Input).value or 5),
            "max_rounds": int(self.query_one("#ed-exec-rounds", Input).value or 0),
            "switch_after_rounds": int(
                self.query_one("#ed-exec-switch-rounds", Input).value or 0
            ),
            "switch_strategy": self.query_one(
                "#ed-exec-switch-strategy", Select
            ).value
            or "auto",
            "max_tokens": int(self.query_one("#ed-max-tokens", Input).value or 128000),
            "token_threshold": float(
                self.query_one("#ed-token-threshold", Input).value or 0.7
            ),
            "auto_continue_on_error": self.query_one(
                "#ed-exec-continue", Checkbox
            ).value,
        }
        working_dir = self.query_one("#ed-exec-working-dir", Input).value.strip()
        if working_dir:
            execution["working_dir"] = working_dir
        config["execution"] = execution
        config["display"] = {
            "show_session_id": self.query_one("#ed-disp-session", Checkbox).value,
            "show_token_usage": self.query_one("#ed-disp-token", Checkbox).value,
            "show_timestamp": self.query_one("#ed-disp-time", Checkbox).value,
        }
        prompts: list[str] = []
        for prompt_id in self._prompt_ids:
            text = self.query_one(f"#{prompt_id}", TextArea).text.strip()
            if text:
                prompts.append(text)
        config["prompts"] = prompts or [""]
        config["summary_prompt"] = (
            self.query_one("#ed-summary-prompt", TextArea).text.strip()
            or i18n.t("default_summary")
        )
        return config

    def _fill_form(self, cfg: dict[str, Any]) -> None:
        cli = cfg.get("cli") or {}
        exec_cfg = cfg.get("execution") or {}
        disp = cfg.get("display") or {}
        self.query_one("#ed-cli-tool", Select).value = cli.get("tool", "opencode")
        self.query_one("#ed-cli-model", Input).value = cli.get("model", "") or ""
        self.query_one("#ed-cli-fullauto", Checkbox).value = bool(
            cli.get("full_auto")
        )
        self.query_one("#ed-cli-search", Checkbox).value = bool(cli.get("search"))
        self.query_one("#ed-exec-delay", Input).value = str(exec_cfg.get("delay", 1))
        self.query_one("#ed-exec-timeout", Input).value = str(
            exec_cfg.get("timeout", 300)
        )
        self.query_one("#ed-exec-retries", Input).value = str(
            exec_cfg.get("max_retries", 5)
        )
        self.query_one("#ed-exec-rounds", Input).value = str(
            exec_cfg.get("max_rounds", 0)
        )
        self.query_one("#ed-exec-switch-rounds").value = str(
            exec_cfg.get("switch_after_rounds", 0)
        )
        self.query_one("#ed-exec-switch-strategy", Select).value = exec_cfg.get(
            "switch_strategy", "auto"
        )
        self.query_one("#ed-max-tokens", Input).value = str(
            exec_cfg.get("max_tokens", 128000)
        )
        self.query_one("#ed-token-threshold", Input).value = str(
            exec_cfg.get("token_threshold", 0.7)
        )
        self.query_one("#ed-exec-continue", Checkbox).value = exec_cfg.get(
            "auto_continue_on_error", True
        )
        self.query_one("#ed-exec-working-dir", Input).value = exec_cfg.get(
            "working_dir", ""
        ) or ""
        self.query_one("#ed-disp-session", Checkbox).value = disp.get(
            "show_session_id", True
        )
        self.query_one("#ed-disp-token", Checkbox).value = disp.get(
            "show_token_usage", True
        )
        self.query_one("#ed-disp-time", Checkbox).value = disp.get(
            "show_timestamp", True
        )
        container = self.query_one("#prompt-list", Vertical)
        container.remove_children()
        self._prompt_ids.clear()
        prompts = cfg.get("prompts") or [""]
        for prompt in prompts:
            self._add_prompt(prompt if isinstance(prompt, str) else "")
        summary = cfg.get("summary_prompt") or i18n.t("default_summary")
        self.query_one("#ed-summary-prompt", TextArea).load_text(summary)
        self._dirty = False
        self.query_one("#editor-status", Static).update("")
        self._refresh_required_hints()

    def on_select_changed(self, event: Select.Changed) -> None:
        if getattr(self.app, "_locale_changing", False):
            return
        if event.select.id != "ed-config-select":
            return
        value = event.value
        if not isinstance(value, str):
            return
        if value == NEW_CONFIG_VALUE:
            self.app.push_screen(NewConfigModal(), self._on_new_config_named)
            return
        if value:
            self._load_config_by_name(value)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id in self._prompt_ids:
            self._refresh_required_hints()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid.startswith("del-"):
            self._remove_prompt(bid.removeprefix("del-"))
            return
        if bid == "ed-add-prompt":
            self._add_prompt("")
            self._dirty = True
        elif bid == "ed-save-btn":
            self._save_config()
        elif bid == "ed-reset-btn":
            self._fill_form({})
            self.query_one("#ed-config-select", Select).value = ""
            self._dirty = False
            self.notify(i18n.t("toast_editor_cleared"))
        elif bid == "ed-reload-btn":
            self._reload_config_list()
            self.notify(i18n.t("toast_configs_reloaded"))
        elif bid == "ed-new-btn":
            self.app.push_screen(NewConfigModal(), self._on_new_config_named)
        elif bid == "ed-aigen-btn":
            self.app.push_screen(AigenModal(), self._apply_aigen)

    def _on_new_config_named(self, name: str | None) -> None:
        if not name:
            if self.query_one("#ed-config-select", Select).value == NEW_CONFIG_VALUE:
                self.query_one("#ed-config-select", Select).value = ""
            return
        if name not in self._pending_names:
            self._pending_names.append(name)
        self._reload_config_list()
        self.query_one("#ed-config-select", Select).value = name
        self._fill_form({})
        self._dirty = True
        self.notify(i18n.t("toast_new_config", name=name))

    def _load_config_by_name(self, name: str) -> None:
        try:
            payload = services.read_config(name)
            parsed = services.parse_yaml(payload["content"])
        except ServiceError as exc:
            self.query_one("#editor-status", Static).update(str(exc))
            return
        self._fill_form(parsed)
        self.query_one("#ed-config-select", Select).value = name
        self.notify(i18n.t("toast_loaded", name=name))

    def _save_config(self) -> None:
        filename = self._selected_config_name()
        if not filename:
            self._refresh_required_hints()
            self.notify(i18n.t("hint_select_config"), severity="error")
            return
        config = self._collect_config()
        if not any(p.strip() for p in config.get("prompts", [])):
            self._refresh_required_hints()
            self.notify(i18n.t("hint_prompt"), severity="error")
            return
        try:
            yaml_text = services.generate_yaml(config)
            path = services.save_config(filename, yaml_text)
        except ServiceError as exc:
            self.query_one("#editor-status", Static).update(str(exc))
            self.notify(str(exc), severity="error")
            return
        if filename in self._pending_names:
            self._pending_names.remove(filename)
        self._dirty = False
        self.query_one("#editor-status", Static).update(
            i18n.t("toast_saved_path", path=path)
        )
        self.notify(i18n.t("toast_saved"))
        self._reload_config_list()
        self.query_one("#ed-config-select", Select).value = filename
        app = self.app
        if hasattr(app, "refresh_all_configs"):
            app.refresh_all_configs(filename)

    def _apply_aigen(self, result: dict[str, str] | None) -> None:
        if not result:
            return
        try:
            parsed = services.parse_yaml(result["yaml"])
        except ServiceError as exc:
            self.notify(str(exc), severity="error")
            return
        merged = self._collect_config()
        if "prompts" in parsed:
            merged["prompts"] = parsed["prompts"]
        if "summary_prompt" in parsed:
            merged["summary_prompt"] = parsed["summary_prompt"]
        self._fill_form(merged)
        self._dirty = True
        self.notify(i18n.t("toast_aigen_applied"))
