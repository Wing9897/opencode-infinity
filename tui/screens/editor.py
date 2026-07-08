"""Config editor tab widget."""
from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label, Select, Static, TextArea

from tui import i18n, services
from tui.screens.aigen_modal import AigenModal
from tui.services import ServiceError


class EditorPanel(VerticalScroll):
    """YAML config editor form."""

    DEFAULT_CSS = """
    EditorPanel {
        height: 1fr;
    }
    .field-row {
        height: auto;
        padding: 0 0 1 0;
    }
    .field-label {
        width: 20;
    }
    .field-input {
        width: 1fr;
    }
    #prompt-list {
        height: auto;
        min-height: 8;
    }
    .prompt-area {
        height: 6;
        margin-bottom: 1;
    }
    #editor-status {
        color: $warning;
        height: auto;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._prompt_ids: list[str] = []
        self._prompt_counter = 0
        self._dirty = False

    def compose(self) -> ComposeResult:
        with Horizontal(classes="field-row"):
            yield Label(i18n.t("label_filename"), classes="field-label")
            yield Input(id="ed-filename", classes="field-input", placeholder="opencode.yaml")
            yield Select([], id="ed-load-select", prompt=i18n.t("btn_load"))
            yield Button(i18n.t("btn_load"), id="ed-load-btn")
        yield Static("", id="editor-status")
        yield Label(i18n.t("section_cli"))
        with Horizontal(classes="field-row"):
            yield Label(i18n.t("label_tool"), classes="field-label")
            yield Select(
                [
                    ("OpenCode", "opencode"),
                    ("Codex", "codex"),
                    ("Claude (experimental)", "claude"),
                    ("Copilot (experimental)", "copilot"),
                ],
                id="ed-cli-tool",
                value="opencode",
            )
        with Horizontal(classes="field-row"):
            yield Label(i18n.t("label_model"), classes="field-label")
            yield Input(id="ed-cli-model", classes="field-input")
        with Horizontal(classes="field-row"):
            yield Checkbox("Full Auto", id="ed-cli-fullauto")
            yield Checkbox("Search", id="ed-cli-search")
        yield Label(i18n.t("section_exec"))
        with Horizontal(classes="field-row"):
            yield Label("delay", classes="field-label")
            yield Input(id="ed-exec-delay", value="1", classes="field-input")
            yield Label("timeout", classes="field-label")
            yield Input(id="ed-exec-timeout", value="300", classes="field-input")
        with Horizontal(classes="field-row"):
            yield Label("retries", classes="field-label")
            yield Input(id="ed-exec-retries", value="5", classes="field-input")
            yield Label("max_rounds", classes="field-label")
            yield Input(id="ed-exec-rounds", value="0", classes="field-input")
        with Horizontal(classes="field-row"):
            yield Label("switch_rounds", classes="field-label")
            yield Input(id="ed-exec-switch-rounds", value="0", classes="field-input")
            yield Label("strategy", classes="field-label")
            yield Select(
                [
                    (i18n.t("switch_auto"), "auto"),
                    (i18n.t("switch_token"), "token"),
                    (i18n.t("switch_rounds"), "rounds"),
                ],
                id="ed-exec-switch-strategy",
                value="auto",
            )
        with Horizontal(classes="field-row"):
            yield Label("max_tokens", classes="field-label")
            yield Input(id="ed-max-tokens", value="128000", classes="field-input")
            yield Label("token_threshold", classes="field-label")
            yield Input(id="ed-token-threshold", value="0.7", classes="field-input")
        with Horizontal(classes="field-row"):
            yield Label("working_dir", classes="field-label")
            yield Input(id="ed-exec-working-dir", classes="field-input")
            yield Checkbox("Continue on error", id="ed-exec-continue", value=True)
        yield Label(i18n.t("section_display"))
        with Horizontal(classes="field-row"):
            yield Checkbox("show_session_id", id="ed-disp-session", value=True)
            yield Checkbox("show_token_usage", id="ed-disp-token", value=True)
            yield Checkbox("show_timestamp", id="ed-disp-time", value=True)
        yield Label(i18n.t("section_prompts"))
        yield Vertical(id="prompt-list")
        yield Button(i18n.t("btn_add_prompt"), id="ed-add-prompt")
        yield Label(i18n.t("label_summary"))
        yield TextArea(id="ed-summary-prompt", classes="prompt-area")
        with Horizontal(classes="field-row"):
            yield Button(i18n.t("btn_aigen"), id="ed-aigen-btn")
            yield Button(i18n.t("btn_save"), id="ed-save-btn", variant="primary")
            yield Button(i18n.t("btn_reset"), id="ed-reset-btn", variant="warning")

    def on_mount(self) -> None:
        self._reload_config_list()
        self._add_prompt("")
        summary = self.query_one("#ed-summary-prompt", TextArea)
        summary.load_text(i18n.t("default_summary"))

    def _reload_config_list(self) -> None:
        configs = services.list_configs()
        select = self.query_one("#ed-load-select", Select)
        select.set_options([(c, c) for c in configs] or [("—", "")])

    def _add_prompt(self, content: str = "") -> None:
        self._prompt_counter += 1
        prompt_id = f"prompt-{self._prompt_counter}"
        self._prompt_ids.append(prompt_id)
        container = self.query_one("#prompt-list", Vertical)
        area = TextArea(content, id=prompt_id, classes="prompt-area")
        container.mount(area)

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
        self.query_one("#ed-exec-switch-rounds", Input).value = str(
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "ed-add-prompt":
            self._add_prompt("")
            self._dirty = True
        elif bid == "ed-save-btn":
            self._save_config()
        elif bid == "ed-reset-btn":
            self._fill_form({})
            self.query_one("#ed-filename", Input).value = ""
            self.notify("Editor cleared")
        elif bid == "ed-load-btn":
            self._load_config()
        elif bid == "ed-aigen-btn":
            self.app.push_screen(AigenModal(), self._apply_aigen)

    def _load_config(self) -> None:
        name = self.query_one("#ed-load-select", Select).value
        if not isinstance(name, str) or not name:
            return
        try:
            payload = services.read_config(name)
            parsed = services.parse_yaml(payload["content"])
        except ServiceError as exc:
            self.query_one("#editor-status", Static).update(str(exc))
            return
        self._fill_form(parsed)
        self.query_one("#ed-filename", Input).value = name
        self.notify(i18n.t("toast_loaded", name=name))

    def _save_config(self) -> None:
        filename = self.query_one("#ed-filename", Input).value.strip()
        if not filename:
            self.notify("Enter a filename", severity="error")
            return
        if not filename.endswith((".yaml", ".yml")):
            filename += ".yaml"
        config = self._collect_config()
        if not any(p.strip() for p in config.get("prompts", [])):
            self.notify("At least one prompt is required", severity="error")
            return
        try:
            yaml_text = services.generate_yaml(config)
            path = services.save_config(filename, yaml_text)
        except ServiceError as exc:
            self.query_one("#editor-status", Static).update(str(exc))
            self.notify(str(exc), severity="error")
            return
        self._dirty = False
        self.query_one("#editor-status", Static).update(f"Saved: {path}")
        self.notify(i18n.t("toast_saved"))
        self._reload_config_list()
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
        self.notify("AI config applied")
