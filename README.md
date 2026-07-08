# OpenCode Infinity ⚡

**語言：** [中文](README.md) · [English](README.en.md)

讓 AI 編碼工具（Codex、Claude、OpenCode、Copilot）7×24 無人值守自動循環執行。

設好 prompt，它就自動幫你不斷叫 AI 做事 — 處理重試、超時、session 管理，你去睡覺它繼續跑。

## 安裝

```bash
pip install -r requirements.txt
```

需要 **Python 3.10+** 與可顯示 Unicode 的終端機（Windows Terminal / PowerShell 7 建議）。

## 使用方式

### Textual TUI（唯一介面）

```bash
cd /path/to/your-project
python /path/to/opencode_infinity.py
```

啟動後進入終端機介面，提供：

- **控制台** — 選設定檔、啟動/停止、工作目錄覆寫、即時日誌、統計、環境診斷
- **設定編輯器** — 圖形化編輯 YAML、AI 生成提示詞、保存設定檔
- **快捷鍵** — `Ctrl+S` 保存編輯器、`Ctrl+Q` 退出（執行中需先停止）

可選參數：

```bash
python opencode_infinity.py --config-dir ./configs
```

### 桌面 exe（Release）

Windows 使用者下載 `OpenCode-Infinity.exe`，雙擊後在終端視窗中開啟 TUI（無需安裝 Python）。

每次 **push 到 `main`**，GitHub Actions 會自動：

1. 跑 smoke tests
2. build `OpenCode-Infinity.exe`
3. 依現有 tag **自動 bump patch 版本**（例如 `v1.0.0` → `v1.0.1`）
4. 建立 GitHub Release 並上傳 exe

本機手動 build：

```bash
pip install -r requirements-desktop.txt
pyinstaller desktop/opencode_infinity.spec --noconfirm
```

## 配置

設定檔預設存放在使用者目錄（源碼版與 exe 共用）：

| 平台 | 路徑 |
|------|------|
| Windows | `%APPDATA%\OpenCodeInfinity\configs\` |
| macOS | `~/Library/Application Support/OpenCodeInfinity/configs/` |
| Linux | `~/.config/OpenCodeInfinity/configs/` |

首次啟動不會自動建立設定檔。請在 GUI 點 **「建立範本」**，會建立或**覆蓋**以下內建種子：

| 檔案 | 說明 |
|------|------|
| `opencode.yaml` | 中文連載文章（OpenCode） |
| `codex.yaml` | 中文連載文章（Codex + 網路搜尋） |
| `article-en.yaml` | 英文連載文章（Codex + 網路搜尋） |

種子設計為**每輪只寫一小段**，接續 `output/articles/draft.md` 繼續創作，而非一輪寫完全文。

也可用環境變數或參數覆寫設定目錄：

```bash
set OPENCODE_INFINITY_CONFIG_DIR=D:\my-configs
python opencode_infinity.py --config-dir ./configs
```

### 設定檔結構

```yaml
cli:
  tool: "codex"           # opencode / claude / codex / copilot
  model: ""               # 留空用預設，或指定如 openai/gpt-5.2-codex
  search: true            # Codex 專用：允許網路搜尋

execution:
  delay: 1                # 每輪延遲（秒）
  timeout: 300            # 超時（秒）
  max_retries: 5          # 最大重試
  max_rounds: 0           # 跑多少輪停止（0 = 無限）
  switch_after_rounds: 0  # 跑多少輪切換 session（0 = 不切換）
  max_tokens: 128000      # Token 上限（用於判斷何時切換 session）
  token_threshold: 0.7    # 達到 70% 時切換（OpenCode/Claude 支援）
  working_dir: ""         # 預設工作目錄（留空 = 啟動時 cwd）

display:
  show_session_id: true
  show_timestamp: true

prompts:
  - "第一個循環提示詞"
  - "第二個循環提示詞"

summary_prompt: "Session 切換前的總結提示詞"
```

> 已移除未使用的 `task` 區塊（名稱、描述、語言、輸出目錄等）。舊設定檔仍可載入，僅會顯示警告。

### 工作目錄優先順序

| 優先級 | 來源 | 說明 |
|--------|------|------|
| 1 | 控制台「工作目錄覆寫」 | 單次啟動臨時覆寫，不寫入 YAML |
| 2 | YAML `execution.working_dir` | 設定檔預設值 |
| 3 | 程式啟動目錄 | 兩處皆留空時使用 |

控制台會即時顯示啟動時將使用的路徑。

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
- Textual TUI：控制台 + 設定編輯器 + AI 生成提示詞

## 注意事項

⚠️ **不要在本工具目錄中執行** — 請 `cd` 到目標專案目錄再跑，否則 AI 會修改本工具的程式碼。可在編輯器設定 `execution.working_dir`，或在控制台「進階選項」臨時覆寫工作目錄。

**`output/articles/draft.md` 是空檔？** 若能建立資料夾與 `.md` 檔，代表寫入權限正常，不是 exe 權限問題。常見原因是本輪 AI 只建了檔案尚未寫入內容 — 讓循環繼續跑下一輪，並在日誌確認「📁 工作目錄」路徑是否為你預期的專案位置。

## 專案結構

```
opencode-infinity/
├── opencode_infinity.py    ← 核心邏輯 + TUI 入口
├── tui/                    ← Textual 介面
│   ├── app.py
│   ├── services.py
│   ├── runtime.py
│   └── screens/
├── desktop/
│   ├── launcher.py         ← exe 入口
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

## 開發 / 測試

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

## 授權

MIT
