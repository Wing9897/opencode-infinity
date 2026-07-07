# OpenCode Infinity ⚡

Run AI coding tools (Codex, Claude, OpenCode, Copilot) in a 7×24 unattended automation loop.

Set your prompts once — the tool keeps calling the AI for you, handling retries, timeouts, and session management while you sleep.

**Languages:** [中文](README.md) · English

## Installation

### From source (CLI + browser GUI)

```bash
pip install pyyaml flask
```

### Desktop (pywebview)

```bash
pip install pyyaml flask pywebview
```

## Usage

### CLI mode

```bash
# Run from your target project directory:
cd /path/to/your-project
python /path/to/opencode_infinity.py codex
python /path/to/opencode_infinity.py ses_abc123 codex
```

### Browser GUI mode

```bash
python opencode_infinity.py --gui
python opencode_infinity.py --gui --no-browser --port 9000
```

Open `http://127.0.0.1:8080` in your browser:

- **Console** — pick a config, start/stop, working directory, live logs, stats
- **Configs** — click **Create templates**, then **edit YAML manually** (no in-browser editor)
- **UI language** — switch 中文 / English in the top-right corner

### Desktop exe (Release)

Windows users can download `OpenCode-Infinity-GUI.exe` (embedded window, no Python required).

For source development, use `--gui` (browser); you do not need pywebview.

On every **push to `main`**, GitHub Actions will:

1. Run smoke tests
2. Build `OpenCode-Infinity-GUI.exe`
3. **Auto-bump the patch version** on the existing tag (e.g. `v1.0.0` → `v1.0.1`)
4. Create a GitHub Release and upload the exe

You can also trigger manually via **Actions → Build and Release → Run workflow**.

Local build:

```bash
pip install pyinstaller flask pyyaml pywebview
pyinstaller desktop/opencode_infinity.spec --noconfirm
```

## Configuration

Config files live in the user directory by default (shared by CLI, browser GUI, and desktop):

| Platform | Path |
|----------|------|
| Windows | `%APPDATA%\OpenCodeInfinity\configs\` |
| macOS | `~/Library/Application Support/OpenCodeInfinity/configs/` |
| Linux | `~/.config/OpenCodeInfinity/configs/` |

Configs are **not** created automatically on first launch. In the Web GUI, click **Create templates** to generate `codex.yaml` and `opencode.yaml` from built-in templates (only missing files; existing configs are not overwritten).

Override with environment variables or CLI flags:

```bash
set OPENCODE_INFINITY_CONFIG_DIR=D:\my-configs
python opencode_infinity.py --config-dir ./configs codex
```

Example config:

```yaml
task:
  name: "My task"
  language: "English"

cli:
  tool: "codex"           # opencode / claude / codex / copilot
  model: ""               # empty = default, or e.g. openai/gpt-5.2-codex

execution:
  delay: 1                # delay between rounds (seconds)
  timeout: 300            # timeout (seconds)
  max_retries: 5          # max retries
  max_rounds: 0           # stop after N rounds (0 = unlimited)
  switch_after_rounds: 0  # switch session after N rounds (0 = never)
  max_tokens: 128000      # token cap (used for session switching)
  token_threshold: 0.7    # switch at 70% (OpenCode/Claude)
  working_dir: ""         # CLI working directory (empty = cwd at launch; GUI can override)

display:
  show_session_id: true
  show_timestamp: true

prompts:
  - "Continue working"
  - "Check and fix issues"

summary_prompt: "Summarize this round (within 300 words)"
```

### Platform feature matrix

| Feature | OpenCode | Claude | Codex | Copilot |
|---------|----------|--------|-------|---------|
| Token stats | ✅ | ❌ | ❌ | ⚠️ limited |
| Session switching | ✅ | ✅ | ✅ | ✅ |
| Sandbox control | — | — | ✅ | — |
| Web search | — | — | ✅ | — |

> Codex CLI 0.130+ removed `--full-auto`; use `-s workspace-write` (default) or `--dangerously-bypass-approvals-and-sandbox`.
> When Codex/Copilot lack token stats, the tool falls back to round-based switching (`switch_after_rounds`).

## Features

- Multi-CLI support: OpenCode, Claude, Codex, Copilot
- Prompt rotation: cycle through multiple prompts
- Smart retries: exponential backoff on timeout (5m → 10m → 20m → 40m → 60m)
- Session management: switch by token threshold or round count
- Hot reload: edit YAML while running; changes apply on the next round
- Input sanitization: guards against command injection
- Live output: Codex reasoning streams to the terminal
- Web GUI: start/stop and log monitoring (edit YAML for settings)
- Success/failure stats on Ctrl+C

## Important

⚠️ **Do not run inside this tool’s repo** — `cd` into your target project first, or the AI may modify this tool’s source. The source GUI lets you set a **working directory** under Advanced options, or set `execution.working_dir` in YAML.

## Project layout

```
opencode-infinity/
├── opencode_infinity.py    ← main entry (CLI / --gui)
├── desktop/
│   ├── launcher.py         ← exe entry (embedded window)
│   └── opencode_infinity.spec
├── gui/
│   ├── index.html          ← Web GUI (console)
│   ├── styles.css
│   ├── app.js
│   └── i18n.js
├── configs/
│   └── test-opencode.yaml  ← local OpenCode smoke test (built-in templates via GUI)
├── tests/
│   └── test_smoke.py
├── requirements.txt
├── requirements-desktop.txt
├── .github/workflows/
│   ├── ci.yml              ← tests on PR / push
│   └── build-desktop.yml   ← build + release on push to main
├── README.md
├── README.en.md
└── .gitignore
```

## Development / testing

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v

# Local OpenCode smoke test (use an empty dir to avoid editing this repo)
python opencode_infinity.py --config-dir ./configs test-opencode
```

## License

MIT
