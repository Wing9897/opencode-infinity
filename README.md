# OpenCode Infinity ⚡

讓 AI 編碼工具（Codex、Claude、OpenCode、Copilot）7x24 無人值守自動循環執行。

設好 prompt，它就自動幫你不斷叫 AI 做事 — 處理重試、超時、session 管理，你去睡覺它繼續跑。

## 安裝

```bash
pip install pyyaml flask
```

## 使用方式

### CLI 模式

```bash
# 在目標專案目錄中執行：
cd /path/to/your-project
python /path/to/opencode-infinity.py codex
python /path/to/opencode-infinity.py ses_abc123 codex
```

### GUI 模式

```bash
python opencode-infinity.py --gui
```

開啟瀏覽器 `http://localhost:8080`，提供：
- 控制台 — 選 config、啟動/停止、即時日誌、統計
- 設定編輯器 — 表單式建立/編輯 YAML

## 配置

編輯 `configs/codex.yaml` 或 `configs/opencode.yaml`：

```yaml
task:
  name: "我的任務"
  language: "繁體中文"

cli:
  tool: "codex"           # opencode / claude / codex / copilot
  model: ""               # 留空用預設，或指定如 openai/gpt-5.2-codex
  commands:
    run_session: ""       # 自訂 CLI 指令（留空用預設）

execution:
  delay: 1                # 每輪延遲（秒）
  timeout: 300            # 超時（秒）
  max_retries: 5          # 最大重試
  max_rounds: 0           # 跑多少輪停止（0 = 無限）
  switch_after_rounds: 0  # 跑多少輪切換 session（0 = 不切換）
  max_tokens: 128000      # Token 上限（用於判斷何時切換 session）
  token_threshold: 0.7    # 達到 70% 時切換（OpenCode/Claude 支援）

display:
  show_session_id: true
  show_token_usage: true
  show_timestamp: true

prompts:
  - "繼續工作"
  - "檢查並修復問題"

summary_prompt: "總結本輪工作（300字內）"
```

### 平台支援差異

| 功能 | OpenCode | Claude | Codex | Copilot |
|------|----------|--------|-------|---------|
| Token 統計 | ✅ | ✅ | ❌ | ⚠️ 有限 |
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
- Web GUI：瀏覽器操作 + 設定編輯器（表單式建立/編輯 config）
- 成功/失敗統計：Ctrl+C 時顯示

## 注意事項

⚠️ **不要在本工具目錄中執行** — 請 `cd` 到目標專案目錄再跑，否則 AI 會修改本工具的程式碼。

## 專案結構

```
opencode-infinity/
├── opencode-infinity.py    ← 主程式
├── gui/
│   └── index.html          ← Web GUI 頁面（Pico CSS）
├── configs/
│   ├── codex.yaml
│   └── opencode.yaml
├── README.md
└── .gitignore
```

## 授權

MIT
