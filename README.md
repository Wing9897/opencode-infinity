# OpenCode Infinity ⚡

**語言：** [中文](README.md) · [English](README.en.md)

讓 AI 編碼工具（Codex、Claude、OpenCode、Copilot）7x24 無人值守自動循環執行。

設好 prompt，它就自動幫你不斷叫 AI 做事 — 處理重試、超時、session 管理，你去睡覺它繼續跑。

## 安裝

### 源碼版（CLI + 瀏覽器 GUI）

```bash
pip install pyyaml flask
```

### 桌面版（pywebview）

```bash
pip install pyyaml flask pywebview
```

## 使用方式

### CLI 模式

```bash
# 在目標專案目錄中執行：
cd /path/to/your-project
python /path/to/opencode_infinity.py codex
python /path/to/opencode_infinity.py ses_abc123 codex
```

### 瀏覽器 GUI 模式

```bash
python opencode_infinity.py --gui
python opencode_infinity.py --gui --no-browser --port 9000
```

開啟瀏覽器 `http://127.0.0.1:8080`，提供：
- 控制台 — 選 config、啟動/停止、工作目錄、即時日誌、統計
- 設定檔 — 點「建立範本」後，**手動編輯 YAML**（不在網頁內建編輯器）
- 介面語言 — 右上角可切換中文 / English

### 桌面 exe（Release）

Windows 使用者下載 `OpenCode-Infinity-GUI.exe` 即可（內嵌視窗，無需 Python）。

源碼開發請用 `--gui`（瀏覽器），不必裝 pywebview。

每次 **push 到 `main`**，GitHub Actions 會自動：

1. 跑 smoke tests
2. build `OpenCode-Infinity-GUI.exe`
3. 依現有 tag **自動 bump patch 版本**（例如 `v1.0.0` → `v1.0.1`）
4. 建立 GitHub Release 並上傳 exe

也可在 **Actions → Build and Release → Run workflow** 手動觸發。

本機手動 build：

```bash
pip install pyinstaller flask pyyaml pywebview
pyinstaller desktop/opencode_infinity.spec --noconfirm
```

## 配置

設定檔預設存放在使用者目錄（CLI / 瀏覽器 GUI / 桌面版共用）：

| 平台 | 路徑 |
|------|------|
| Windows | `%APPDATA%\OpenCodeInfinity\configs\` |
| macOS | `~/Library/Application Support/OpenCodeInfinity/configs/` |
| Linux | `~/.config/OpenCodeInfinity/configs/` |

首次啟動不會自動建立設定檔。請在 Web GUI 點 **「建立範本」**，才會從內建範本建立 `codex.yaml`、`opencode.yaml`（僅建立缺少的檔案，不會覆蓋既有設定）。

也可用環境變數或參數覆寫：

```bash
set OPENCODE_INFINITY_CONFIG_DIR=D:\my-configs
python opencode_infinity.py --config-dir ./configs codex
```

編輯設定檔範例：

```yaml
task:
  name: "我的任務"
  language: "繁體中文"

cli:
  tool: "codex"           # opencode / claude / codex / copilot
  model: ""               # 留空用預設，或指定如 openai/gpt-5.2-codex

execution:
  delay: 1                # 每輪延遲（秒）
  timeout: 300            # 超時（秒）
  max_retries: 5          # 最大重試
  max_rounds: 0           # 跑多少輪停止（0 = 無限）
  switch_after_rounds: 0  # 跑多少輪切換 session（0 = 不切換）
  max_tokens: 128000      # Token 上限（用於判斷何時切換 session）
  token_threshold: 0.7    # 達到 70% 時切換（OpenCode/Claude 支援）
  working_dir: ""         # CLI 工作目錄（留空 = 啟動時 cwd；GUI 可覆寫）

display:
  show_session_id: true
  show_timestamp: true

prompts:
  - "繼續工作"
  - "檢查並修復問題"

summary_prompt: "總結本輪工作（300字內）"
```

### 平台支援差異

| 功能 | OpenCode | Claude | Codex | Copilot |
|------|----------|--------|-------|---------|
| Token 統計 | ✅ | ❌ | ❌ | ⚠️ 有限 |
| Session 切換 | ✅ | ✅ | ✅ | ✅ |
| Sandbox 控制 | — | — | ✅ | — |
| Web Search | — | — | ✅ | — |

> Codex CLI 0.130+ 已移除 `--full-auto`，改用 `-s workspace-write`（預設）或 `--dangerously-bypass-approvals-and-sandbox`。
> Codex/Copilot 不支援 Token 統計時，自動改用輪次策略（`switch_after_rounds`）。

## 功能

- 多 CLI 支援：OpenCode、Claude、Codex、Copilot
- 提示詞輪轉：多個 prompt 循環使用
- 智能重試：指數退避超時（5分→10分→20分→40分→60分）
- Session 管理：Token 閾值或輪次策略自動切換
- 熱重載：運行中修改 YAML，下一輪自動套用
- 輸入消毒：防止命令注入
- 即時輸出：Codex 的思考過程直接顯示在終端
- Web GUI：啟動/停止、日誌監看（設定請編輯 YAML）
- 成功/失敗統計：Ctrl+C 時顯示

## 注意事項

⚠️ **不要在本工具目錄中執行** — 請 `cd` 到目標專案目錄再跑，否則 AI 會修改本工具的程式碼。源碼版 GUI 可在「進階選項」設定 **工作目錄**，或於 YAML 設定 `execution.working_dir`。

## 專案結構

```
opencode-infinity/
├── opencode_infinity.py    ← 主程式（CLI / --gui）
├── desktop/
│   ├── launcher.py         ← exe 入口（內嵌視窗）
│   └── opencode_infinity.spec
├── gui/
│   ├── index.html          ← Web GUI（控制台）
│   ├── styles.css
│   ├── app.js
│   └── i18n.js
├── configs/
│   └── test-opencode.yaml  ← 本機 OpenCode 實測用（內建範本由程式碼提供，經 GUI 建立）
├── tests/
│   └── test_smoke.py
├── requirements.txt
├── requirements-desktop.txt
├── .github/workflows/
│   ├── ci.yml              ← PR / push 時跑測試
│   └── build-desktop.yml   ← push main 時 build + release
├── README.md
├── README.en.md
└── .gitignore
```

## 開發 / 測試

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v

# 本機 OpenCode 實測（在空目錄執行，避免改動本工具程式碼）
python opencode_infinity.py --config-dir ./configs test-opencode
```

## 授權

MIT
