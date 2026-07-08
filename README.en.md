# OpenCode Infinity ⚡

Run AI coding tools (Codex, Claude, OpenCode, Copilot) in a 7×24 unattended automation loop.

Set your prompts once — the tool keeps calling the AI for you, handling retries, timeouts, and session management while you sleep.

**Languages:** [中文](README.md) · English

## Installation

```bash
pip install -r requirements.txt
```

Requires **Python 3.10+** and a Unicode-capable terminal (Windows Terminal / PowerShell 7 recommended).

## Usage

### Textual TUI (single interface)

```bash
cd /path/to/your-project
python /path/to/opencode_infinity.py
```

Launches a terminal UI with:

- **Console** — config picker, start/stop, working-dir override, live logs, stats, diagnose
- **Config editor** — visual YAML editor, AI prompt generator, save configs
- **Shortcuts** — `Ctrl+S` save editor, `Ctrl+Q` quit (stop the task first if running)

Optional flag:

```bash
python opencode_infinity.py --config-dir ./configs
```

### Desktop exe (Release)

Windows users can download `OpenCode-Infinity.exe` and double-click to open the TUI in a console window (no Python required).

On every **push to `main`**, GitHub Actions will:

1. Run smoke tests
2. Build `OpenCode-Infinity.exe`
3. **Auto-bump the patch version** on the existing tag (e.g. `v1.0.0` → `v1.0.1`)
4. Create a GitHub Release and upload the exe

Local build:

```bash
pip install -r requirements-desktop.txt
pyinstaller desktop/opencode_infinity.spec --noconfirm
```

## Configuration

Config files live in the user directory by default (shared by source and desktop exe):

| Platform | Path |
|----------|------|
| Windows | `%APPDATA%\OpenCodeInfinity\configs\` |
| macOS | `~/Library/Application Support/OpenCodeInfinity/configs/` |
| Linux | `~/.config/OpenCodeInfinity/configs/` |

Configs are **not** created automatically on first launch. In the TUI, click **Create templates** to generate or **overwrite** these built-in seeds:

| File | Description |
|------|-------------|
| `opencode.yaml` | Chinese serial article writing (OpenCode) |
| `codex.yaml` | Chinese serial article writing (Codex + web search) |
| `article-en.yaml` | English serial article writing (Codex + web search) |

Seeds are designed to **write a little each round**, continuing `output/articles/draft.md` — not finishing the full article in one pass.

Override the config directory with environment variables or CLI flags:

```bash
set OPENCODE_INFINITY_CONFIG_DIR=D:\my-configs
python opencode_infinity.py --config-dir ./configs codex
```

### Config structure

```yaml
cli:
  tool: "codex"           # opencode / claude / codex / copilot
  model: ""               # empty = default, or e.g. openai/gpt-5.2-codex
  search: true            # Codex only: allow web search

execution:
  delay: 1                # delay between rounds (seconds)
  timeout: 300            # timeout (seconds)
  max_retries: 5          # max retries
  max_rounds: 0           # stop after N rounds (0 = unlimited)
  switch_after_rounds: 0  # switch session after N rounds (0 = never)
  max_tokens: 128000      # token cap (used for session switching)
  token_threshold: 0.7    # switch at 70% (OpenCode/Claude)
  working_dir: ""         # default working directory (empty = cwd at launch)

display:
  show_session_id: true
  show_timestamp: true

prompts:
  - "First rotating prompt"
  - "Second rotating prompt"

summary_prompt: "Summary prompt before session switch"
```

> The unused `task` section (name, description, language, output dir, etc.) has been removed. Legacy configs still load with warnings.

### Working directory priority

| Priority | Source | Notes |
|----------|--------|-------|
| 1 | Console **working dir override** | One-shot override; not saved to YAML |
| 2 | YAML `execution.working_dir` | Default in the config file |
| 3 | Launch directory | Used when both above are empty |

The console shows which path will be used at start time.

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
- Textual TUI: console + config editor + AI prompt generation

## Important

⚠️ **Do not run inside this tool’s repo** — `cd` into your target project first, or the AI may modify this tool’s source. Set `execution.working_dir` in the editor, or use the console **working dir override** under Advanced options.

**Is `output/articles/draft.md` empty?** If the folder and file were created, write permissions are fine — this is usually not an exe permission issue. The AI often creates the file before filling it; let the loop continue and check the **📁 working directory** line in the logs matches your project path.

## Project layout

```
opencode-infinity/
├── opencode_infinity.py    ← core logic + TUI entry
├── tui/                    ← Textual UI
│   ├── app.py
│   ├── services.py
│   ├── runtime.py
│   └── screens/
├── desktop/
│   ├── launcher.py         ← exe entry
│   └── opencode_infinity.spec
├── configs/
│   └── test-opencode.yaml
├── tests/
│   ├── test_smoke.py
│   └── test_tui.py
├── requirements.txt
├── requirements-desktop.txt
└── .github/workflows/
    └── build-desktop.yml
```

## Development / testing

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## License

MIT
