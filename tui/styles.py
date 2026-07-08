"""Shared Textual theme styles."""

APP_CSS = """
/* ── Global ── */
Screen {
    layout: vertical;
    background: $background;
}

#tab-bar-row {
    height: 3;
    background: $surface;
    border-bottom: solid $primary 40%;
    align: left middle;
}

#main-tabs {
    width: 1fr;
    height: 3;
    background: transparent;
    padding: 0;
}

#main-tabs Tab {
    color: $text-muted;
}

#main-tabs Tab.-active {
    color: $accent;
    text-style: bold;
    background: $primary 15%;
}

#tab-status {
    width: auto;
    min-width: 20;
    height: 3;
    padding: 0 2;
    color: $text-muted;
    text-style: bold;
    content-align: center middle;
}

#tab-status.running {
    color: $success;
}

#main-switcher {
    height: 1fr;
}

#console-panel {
    height: 1fr;
}

#editor-panel {
    height: 1fr;
}

TabPane {
    padding: 1 2;
}

#tab-editor {
    height: 1fr;
    align: center top;
}

#editor-panel {
    height: 1fr;
    width: 100%;
    align: center top;
}

#editor-shell {
    width: 96;
    max-width: 96;
    height: auto;
    padding: 0;
    background: transparent;
}

.density-compact #editor-shell {
    width: 88;
    max-width: 88;
}

.density-normal #editor-shell {
    width: 100;
    max-width: 100;
}

.density-comfortable #editor-shell {
    width: 110;
    max-width: 110;
}

#console-shell {
    width: auto;
    max-width: 96;
    min-width: 72;
    height: 1fr;
}

.density-compact #console-shell {
    max-width: 84;
}

/* ── Density: compact (default) ── */
.density-compact #tab-bar-row {
    height: 3;
}

.density-compact TabPane {
    padding: 0 1;
}

.density-compact .section-card {
    margin: 0 0;
    padding: 0 0 0 0;
}

.density-compact .form-grid {
    grid-gutter: 0 1;
    padding: 0;
}

.density-compact .form-row,
.density-compact .toolbar-row,
.density-compact .checkbox-row {
    padding: 0;
}

.density-compact .prompt-area {
    height: 3;
    margin: 0 0 0 0;
}

.density-compact #prompt-list {
    min-height: 3;
    padding: 0;
}

.density-compact .log-header {
    padding: 0;
}

.density-compact LogPanel {
    min-height: 6;
}

.density-compact .toolbar-row .action-btn {
    min-width: 8;
    margin: 0 0 0 0;
}

.density-compact .form-label {
    width: 14;
}

/* ── Density: normal ── */
.density-normal TabPane {
    padding: 1 2;
}

.density-normal .section-card {
    margin: 1 0;
    padding: 0 1 1 1;
}

.density-normal .prompt-area {
    height: 4;
}

/* ── Density: comfortable ── */
.density-comfortable TabPane {
    padding: 1 3;
}

.density-comfortable .section-card {
    margin: 1 0;
    padding: 0 1 1 1;
}

.density-comfortable .form-grid {
    grid-gutter: 1 2;
    padding: 1 0 0 0;
}

.density-comfortable .prompt-area {
    height: 6;
}

.density-comfortable #prompt-list {
    min-height: 8;
}

.density-comfortable LogPanel {
    min-height: 12;
}

/* ── Section cards ── */
.section-card {
    border: solid $primary 25%;
    background: $surface-darken-1;
    margin: 1 0;
    padding: 0 1 1 1;
}

.section-card CollapsibleTitle {
    background: $primary 18%;
    color: $accent;
    text-style: bold;
    padding: 0 1;
}

.section-card:focus-within {
    border: solid $accent 40%;
}

/* ── Required markers ── */
.form-label-required {
    color: $text-muted;
}

.required-hint {
    color: $warning;
    height: auto;
    padding: 0 0 0 0;
    text-style: italic;
}

.required-hint.-ok {
    color: $success;
}

/* ── Form layout ── */
.form-row {
    height: auto;
    padding: 0 0 1 0;
    align: left middle;
}

.form-label {
    width: 16;
    color: $text-muted;
    padding: 0 1 0 0;
}

.form-value {
    width: 1fr;
    min-width: 12;
}

.form-grid {
    layout: grid;
    grid-size: 2;
    grid-gutter: 1 2;
    height: auto;
    padding: 1 0 0 0;
}

.form-grid .form-label {
    width: 100%;
}

.form-grid .form-value {
    width: 100%;
}

.checkbox-row {
    height: auto;
    padding: 0 0 1 0;
}

.checkbox-row Checkbox {
    margin: 0 2 0 0;
}

/* ── Toolbar / actions ── */
.toolbar-row {
    height: auto;
    padding: 0 0 1 0;
    align: left middle;
}

.toolbar-row .action-btn {
    margin: 0 1 0 0;
    min-width: 10;
}

#btn-start {
    background: $success 25%;
    color: $text;
}

#btn-stop {
    background: $error 25%;
    color: $text;
}

#btn-save {
    background: $success 30%;
}

#btn-diagnose {
    background: $warning 20%;
}

#ed-aigen-btn {
    background: $accent 20%;
    color: $accent;
}

/* ── Logs ── */
.log-header {
    color: $accent;
    text-style: bold;
    padding: 1 0 0 0;
    height: auto;
    width: 1fr;
}

.log-toolbar {
    height: auto;
    align: left middle;
    padding: 0;
}

#btn-copy-log {
    width: auto;
    min-width: 10;
}

LogPanel {
    border: solid $primary 25%;
    background: $surface;
    height: 1fr;
    min-height: 10;
    padding: 0 1;
}

#editor-status {
    color: $warning;
    height: auto;
    padding: 0 0 1 0;
}

#config-select {
    width: 1fr;
    margin: 0 1 0 0;
}

.prompt-area {
    height: 5;
    margin: 0 0 1 0;
    border: solid $primary 30%;
}

#prompt-list {
    height: auto;
    min-height: 6;
    padding: 0 0 1 0;
}

.editor-actions {
    height: auto;
    padding: 1 0 0 0;
    align: left middle;
}

.editor-actions Button {
    margin: 0 1 0 0;
}

.prompt-row {
    height: auto;
    width: 100%;
    margin: 0 0 0 0;
    align: left middle;
}

.prompt-row TextArea {
    width: 1fr;
    height: 3;
    min-height: 3;
}

.prompt-del-btn {
    width: 4;
    min-width: 4;
    margin: 0 0 0 1;
    background: $error 20%;
    color: $error;
}
"""
