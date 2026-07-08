"""AI config generator modal."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select, TextArea

from tui import i18n


class AigenModal(ModalScreen[dict[str, str] | None]):
    """Modal to build an external AI prompt and optionally apply YAML."""

    DEFAULT_CSS = """
    AigenModal {
        align: center middle;
    }
    #aigen-dialog {
        width: 80%;
        max-width: 90;
        height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #aigen-preview {
        height: 1fr;
        min-height: 10;
    }
    #aigen-yaml {
        height: 12;
        display: none;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="aigen-dialog"):
            yield Label(i18n.t("aigen_title"))
            yield Label(i18n.t("aigen_task"))
            yield TextArea(id="aigen-task")
            yield Select(
                [(i18n.t("locale_zh"), "繁體中文"), (i18n.t("locale_en"), "English")],
                id="aigen-lang",
                value="繁體中文",
            )
            yield TextArea(id="aigen-preview", read_only=True)
            yield TextArea(id="aigen-yaml", placeholder="Paste AI YAML here")
            yield Button(i18n.t("aigen_apply"), id="aigen-apply", variant="primary")
            yield Button("Close", id="aigen-close")

    def on_mount(self) -> None:
        self._refresh_preview()

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
        if event.button.id == "aigen-close":
            self.dismiss(None)
            return
        if event.button.id == "aigen-apply":
            raw = self.query_one("#aigen-yaml", TextArea).text.strip()
            if not raw:
                yaml_area = self.query_one("#aigen-yaml", TextArea)
                yaml_area.display = True
                self.notify("Paste AI YAML into the text area below, then press Apply again.")
                return
            self.dismiss({"yaml": i18n.extract_yaml_from_text(raw)})
