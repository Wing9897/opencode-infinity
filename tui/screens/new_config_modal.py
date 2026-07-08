"""Modal to name a new config file."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from tui import i18n


class NewConfigModal(ModalScreen[str | None]):
    """Ask for a new YAML filename."""

    DEFAULT_CSS = """
    NewConfigModal {
        align: center middle;
    }
    #new-config-dialog {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #new-config-name {
        margin: 1 0;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="new-config-dialog"):
            yield Label(i18n.t("new_config_title"), classes="form-label-required")
            yield Static(i18n.t("new_config_hint"), classes="required-hint")
            yield Input(
                id="new-config-name",
                placeholder="opencode.yaml",
            )
            with Horizontal(classes="editor-actions"):
                yield Button(i18n.t("btn_cancel"), id="new-config-cancel")
                yield Button(
                    i18n.t("btn_create"),
                    id="new-config-create",
                    variant="primary",
                )

    def on_mount(self) -> None:
        self.query_one("#new-config-name", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def refresh_locale(self) -> None:
        self.query_one("#new-config-name", Input).placeholder = "opencode.yaml"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "new-config-cancel":
            self.dismiss(None)
            return
        if event.button.id == "new-config-create":
            name = self.query_one("#new-config-name", Input).value.strip()
            if not name:
                self.notify(i18n.t("new_config_empty"), severity="error")
                return
            if not name.endswith((".yaml", ".yml")):
                name += ".yaml"
            self.dismiss(name)

    def refresh_locale(self) -> None:
        self.query_one("#new-config-name", Input).placeholder = "opencode.yaml"
