"""AI config generator modal."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select, Static, TextArea

from tui import i18n


class AigenModal(ModalScreen[dict[str, str] | None]):
    """Modal to build an external AI prompt and optionally apply YAML."""

    DEFAULT_CSS = """
    AigenModal {
        align: center middle;
    }
    #aigen-dialog {
        width: 85%;
        max-width: 100;
        height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #aigen-preview {
        height: 1fr;
        min-height: 8;
    }
    #aigen-yaml {
        height: 8;
        border: solid $warning 40%;
    }
    .aigen-actions {
        height: auto;
        padding: 1 0 0 0;
        align: right middle;
    }
    .aigen-actions Button {
        margin: 0 0 0 1;
        min-width: 12;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", i18n.t("btn_cancel"), show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="aigen-dialog"):
            yield Label(i18n.t("aigen_title"), id="aigen-title")
            yield Static(i18n.t("aigen_step1"), id="aigen-step1", classes="required-hint")
            yield Label(i18n.t("aigen_task"), id="aigen-task-label")
            yield TextArea(id="aigen-task")
            yield Select(
                [
                    (i18n.t("aigen_lang_zh"), "繁體中文"),
                    (i18n.t("aigen_lang_en"), "English"),
                ],
                id="aigen-lang",
                value="English",
            )
            yield Label(i18n.t("aigen_preview_label"), id="aigen-preview-label")
            yield TextArea(id="aigen-preview", read_only=True)
            yield Static(i18n.t("aigen_step2"), id="aigen-step2", classes="required-hint")
            yield Label(i18n.t("aigen_paste_yaml"), id="aigen-yaml-label")
            yield TextArea(
                id="aigen-yaml",
                placeholder=i18n.t("aigen_yaml_placeholder"),
            )
            with Horizontal(classes="aigen-actions"):
                yield Button(i18n.t("btn_cancel"), id="aigen-cancel")
                yield Button(i18n.t("aigen_apply"), id="aigen-apply", variant="primary")

    def on_mount(self) -> None:
        lang = self.query_one("#aigen-lang", Select)
        lang.value = "繁體中文" if i18n.get_locale() == "zh-TW" else "English"
        self._refresh_preview()
        self.query_one("#aigen-task", TextArea).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "aigen-task":
            self._refresh_preview()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "aigen-lang":
            self._refresh_preview()

    def _refresh_preview(self) -> None:
        task = self.query_one("#aigen-task", TextArea).text
        lang = self.query_one("#aigen-lang", Select).value
        if not isinstance(lang, str):
            lang = "繁體中文"
        preview = i18n.build_aigen_prompt(task, lang)
        self.query_one("#aigen-preview", TextArea).load_text(preview)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "aigen-cancel":
            self.dismiss(None)
            return
        if event.button.id == "aigen-apply":
            raw = self.query_one("#aigen-yaml", TextArea).text.strip()
            if not raw:
                self.notify(i18n.t("aigen_paste_notify"), severity="warning")
                self.query_one("#aigen-yaml", TextArea).focus()
                return
            self.dismiss({"yaml": i18n.extract_yaml_from_text(raw)})

    def refresh_locale(self) -> None:
        self.query_one("#aigen-title", Label).update(i18n.t("aigen_title"))
        self.query_one("#aigen-step1", Static).update(i18n.t("aigen_step1"))
        self.query_one("#aigen-task-label", Label).update(i18n.t("aigen_task"))
        self.query_one("#aigen-preview-label", Label).update(i18n.t("aigen_preview_label"))
        self.query_one("#aigen-step2", Static).update(i18n.t("aigen_step2"))
        self.query_one("#aigen-yaml-label", Label).update(i18n.t("aigen_paste_yaml"))
        self.query_one("#aigen-yaml", TextArea).placeholder = i18n.t(
            "aigen_yaml_placeholder"
        )
        self.query_one("#aigen-cancel", Button).label = i18n.t("btn_cancel")
        self.query_one("#aigen-apply", Button).label = i18n.t("aigen_apply")
        lang = self.query_one("#aigen-lang", Select)
        current = lang.value
        lang.set_options(
            [
                (i18n.t("aigen_lang_zh"), "繁體中文"),
                (i18n.t("aigen_lang_en"), "English"),
            ]
        )
        if isinstance(current, str):
            lang.value = current
        self._refresh_preview()
