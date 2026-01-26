# 🚀 OpenCode Infinity

<div align="center">

**通用 OpenCode CLI 自動化框架**  
智能 Token 管理 · 自動 Session 切換 · 24/7 無人值守運行

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![OpenCode CLI](https://img.shields.io/badge/OpenCode-CLI-green.svg)](https://github.com/opencode-cli)

</div>

---

## ✨ 核心特性

- 🤖 **智能 Token 管理** - 自動監控使用量，達到閾值自動切換 session
- 🔄 **無縫上下文傳遞** - 新 session 自動繼承工作內容，保持連貫性
- ⚙️ **YAML 配置驅動** - 靈活配置，支持多任務並行
- 🎨 **豐富視覺反饋** - 彩色輸出、Token 進度、實時狀態
- 🛡️ **健壯容錯設計** - 指數退避重試，執行失敗不中斷
- 📊 **詳細統計報告** - 輪次、Session 數、執行時間、Token 使用
- 🔧 **靈活參數覆蓋** - 命令行參數動態調整配置

## 📦 安裝

### 前置需求

| 需求           | 版本   | 說明   |
| ------------ | ---- | ---- |
| Python       | 3.7+ | 執行環境 |
| OpenCode CLI | 最新版  | 核心依賴 |
| PyYAML       | 任意版  | 配置解析 |

### 快速安裝

```bash
# 1. 克隆專案
git clone https://github.com/your-username/opencode-infinity.git
cd opencode-infinity

# 2. 安裝依賴
pip install pyyaml

# 3. 賦予執行權限（可選）
chmod +x opencode-infinity.py

# 4. 驗證安裝
python3 opencode-infinity.py --help
```

## 🚀 快速開始

### 方式一：一鍵啟動（推薦）

使用預設配置快速開始醫療知識庫生成：

```bash
# 啟動任務（使用預設 medical-kb 配置）
python3 opencode-infinity.py medical-kb

# 查看 session ID（會自動創建）
opencode session list
```

### 方式二：指定 Session ID

如果你已有 session，可以直接使用：

```bash
# 使用現有 session
python3 opencode-infinity.py ses_abc123xyz

# 或指定配置名稱
python3 opencode-infinity.py ses_abc123xyz --config code-generation
```

### 方式三：選擇其他任務

我們提供了多種任務配置供選擇：

```bash
# API 開發
python3 opencode-infinity.py api-development

# 技術文檔生成
python3 opencode-infinity.py documentation

# 自動化測試
python3 opencode-infinity.py testing

# 數據處理
python3 opencode-infinity.py data-processing

# 前端組件開發
python3 opencode-infinity.py frontend-components
```

### 方式四：自定義配置

```bash
# 1. 複製範例配置
cp tasks_yaml/medical-kb.yaml tasks_yaml/my-task.yaml

# 2. 編輯配置（使用你喜歡的編輯器）
vim tasks_yaml/my-task.yaml

# 3. 啟動任務
python3 opencode-infinity.py my-task
```

### 方式五：動態參數覆蓋

無需修改配置文件，臨時調整參數：

```bash
# 調整 Token 閾值和延遲
python3 opencode-infinity.py medical-kb --threshold 0.8 --delay 2

# 使用不同的 AI 模型
python3 opencode-infinity.py medical-kb --model openai/gpt-5.2-codex
```

### 停止運行

按 `Ctrl+C` 優雅退出，自動顯示統計信息：

- 總執行輪次
- Session 切換次數
- 累計運行時間
- Token 使用情況

## 📖 配置說明

### 完整配置示例

```yaml
# 任務基本信息
task:
  name: "任務名稱"
  description: "任務描述"
  language: "繁體中文"

# OpenCode 配置
opencode:
  model: "openai/gpt-5.2-codex"
  max_tokens: 128000
  token_threshold: 0.7  # 0.0-1.0，達到此比例時切換

# 執行配置
execution:
  delay: 1  # 每輪延遲（秒）
  auto_continue_on_error: true  # 失敗是否繼續
  max_retries: 3  # Session 切換失敗最大重試次數

# 提示詞（按順序輪轉）
prompts:
  - "提示詞 1..."
  - "提示詞 2..."
  - "提示詞 3..."

# 總結提示詞（達到閾值時使用）
summary_prompt: |
  請總結本輪工作...

# 上下文傳遞
context:
  export_last_messages: 5    # 導出最後 N 條消息
  max_context_chars: 500     # 單條最大字符數
  use_last_snippets: 3       # 使用最後 N 個片段

# 顯示配置
display:
  show_session_id: true
  show_token_usage: true
  show_timestamp: true
  color_per_session: true
```

### 命令行參數

```bash
python3 opencode-infinity.py <session_id> [options]

必需參數:
  session_id              OpenCode session ID (ses_xxx)

可選參數:
  -c, --config FILE       配置文件路徑（YAML）
  -m, --model MODEL       覆蓋 model 設置
  -t, --threshold NUM     覆蓋 token threshold (0.0-1.0)
  --delay SECONDS         覆蓋每輪延遲（秒）
  -h, --help              顯示幫助信息
```

## 📁 項目結構

```
opencode-infinity/
├── opencode-infinity.py          # 🎯 主程序
├── tasks_yaml/                   # 📋 任務配置目錄
│   ├── medical-kb.yaml           #    醫療知識庫（預設）
│   ├── code-generation.yaml      #    代碼生成
│   ├── api-development.yaml      #    API 開發
│   ├── documentation.yaml        #    技術文檔
│   ├── testing.yaml              #    自動化測試
│   ├── data-processing.yaml      #    數據處理
│   └── frontend-components.yaml  #    前端組件
├── hardcode_test/                # 🧪 測試檔案
├── yaml-editor.html              # 🛠️ YAML 編輯器
└── README.md                     # 📖 本文檔

💡 使用方式：
   python3 opencode-infinity.py <config-name>
   配置名稱不需要加 .yaml 後綴
```

## 📚 使用案例

### 案例 1：醫療知識庫生成

**場景**：自動建立涵蓋各種症狀的家居處理指引文檔

```bash
# 啟動任務（自動創建新 session）
python3 opencode-infinity.py medical-kb

# 或使用現有 session
python3 opencode-infinity.py ses_abc123 --config medical-kb
```

**效果**：

- ✅ 持續生成症狀處理文檔
- ✅ 達到 70% Token 自動切換 session
- ✅ 新 session 自動繼承上下文
- ✅ 所有文件保存到「症狀/」目錄

---

### 案例 2：API 後端開發

**場景**：快速生成完整的 RESTful API 服務

```bash
python3 opencode-infinity.py api-development
```

**生成內容**：

- 用戶管理 CRUD 端點
- JWT 身份驗證
- 數據驗證中間件
- OpenAPI 文檔
- 單元測試

---

### 案例 3：前端組件庫

**場景**：構建可重用的 React/Vue 組件

```bash
python3 opencode-infinity.py frontend-components --threshold 0.8
```

**生成內容**：

- 表單組件（Input, Select, Checkbox）
- 數據展示組件（Table, Card）
- TypeScript 類型定義
- Storybook 示例
- 單元測試

---

### 案例 4：技術文檔撰寫

**場景**：自動生成項目文檔

```bash
python3 opencode-infinity.py documentation --delay 2
```

**生成內容**：

- 快速開始指南
- API 使用教程
- 最佳實踐文檔
- 常見問題解答
- 架構設計文檔

---

### 案例 5：多任務並行執行

**場景**：同時執行多個不同任務

```bash
# Terminal 1 - API 開發
python3 opencode-infinity.py api-development

# Terminal 2 - 前端組件
python3 opencode-infinity.py frontend-components

# Terminal 3 - 測試生成
python3 opencode-infinity.py testing
```

**優勢**：

- 🚀 並行加速開發
- 🎯 每個任務獨立 session
- 📊 分別監控進度

## 🔧 進階技巧

### 1. 調整 Token 閾值策略

根據任務類型選擇合適的閾值：

```bash
# 文檔類任務 - 較低閾值（更頻繁切換）
python3 opencode-infinity.py documentation --threshold 0.6

# 代碼類任務 - 較高閾值（保持上下文）
python3 opencode-infinity.py api-development --threshold 0.8

# 默認值
# --threshold 0.7
```

### 2. 控制執行速度

```bash
# 快速執行（減少延遲）
python3 opencode-infinity.py medical-kb --delay 0.5

# 穩定執行（適度延遲）
python3 opencode-infinity.py medical-kb --delay 2

# 謹慎執行（避免 API 限流）
python3 opencode-infinity.py medical-kb --delay 5
```

### 3. 使用不同 AI 模型

```bash
# GPT-5.2 Codex（代碼任務推薦）
python3 opencode-infinity.py code-generation \
  --model openai/gpt-5.2-codex

# Claude Sonnet（通用任務）
python3 opencode-infinity.py documentation \
  --model anthropic/claude-sonnet-3.5

# 查看可用模型
opencode models list
```

### 4. 組合參數使用

```bash
# 全參數組合
python3 opencode-infinity.py api-development \
  --model openai/gpt-5.2-codex \
  --threshold 0.75 \
  --delay 1.5
```

### 5. 監控和調試

```bash
# 查看所有 sessions
opencode session list

# 查看特定 session 內容
opencode session view ses_abc123

# 查看 session token 使用量
opencode session stats ses_abc123
```

## 📊 輸出示例

```
══════════════════════════════════════════════════════════════════════
[腳本] OpenCode Infinity 啟動
任務: 醫療知識庫 | Model: openai/gpt-5.2-codex
Token 閾值: 70% | 語言: 繁體中文
══════════════════════════════════════════════════════════════════════

══════════════════════════════════════════════════════════════════════
[腳本] 第 1 輪 | Session 1-1 | 17:30:45
Session ID: ses_abc123
標題: 家居症狀知識庫工作
Token: 45,000/128,000 (35.2%)
══════════════════════════════════════════════════════════════════════

[腳本] 執行提示詞 #1

（AI 工作輸出...）

✓ 本輪完成
```

## ❓ 常見問題

<details>
<summary><b>Q: 如何停止運行？</b></summary>

**A:** 按 `Ctrl+C` 即可優雅退出，程序會顯示完整統計信息：

- 總執行輪次
- Session 切換次數
- 運行時間
- Token 使用情況

</details>

<details>
<summary><b>Q: Session 切換失敗怎麼辦？</b></summary>

**A:** 程序內建指數退避重試機制：

1. 自動重試最多 5 次（可在配置中調整 `execution.max_retries`）
2. 每次重試延遲加倍：5秒 → 10秒 → 20秒 → 40秒 → 60秒
3. 如仍失敗，程序會優雅退出並顯示錯誤信息

</details>

<details>
<summary><b>Q: 能否使用不同的 AI 模型？</b></summary>

**A:** 當然可以！三種方式：

1. **命令行參數**：`--model openai/gpt-5.2-codex`
2. **配置文件**：修改 `opencode.model` 欄位
3. **查看可用模型**：`opencode models list`

推薦模型：

- 代碼任務：`openai/gpt-5.2-codex`
- 文檔任務：`anthropic/claude-sonnet-3.5`
- 通用任務：`openai/gpt-4-turbo`

</details>

<details>
<summary><b>Q: 如何查看已生成的內容？</b></summary>

**A:** 使用 OpenCode CLI 命令：

```bash
# 列出所有 sessions
opencode session list

# 查看特定 session 內容
opencode session view ses_abc123

# 導出 session 內容
opencode export ses_abc123 > output.json
```

或直接查看輸出目錄（配置中的 `task.output_dir`）。

</details>

<details>
<summary><b>Q: Token 使用量如何計算？</b></summary>

**A:** 計算方式：

- **累計 Output Tokens** / **模型最大 Tokens** = 使用比例
- 達到 `token_threshold`（如 0.7 = 70%）時自動切換
- 只計算 AI 輸出的 tokens，不包括輸入

查看實時使用量：程序運行時會顯示當前進度。

</details>

<details>
<summary><b>Q: 如何創建自定義任務配置？</b></summary>

**A:** 三步驟：

1. **複製範例**：
   
   ```bash
   cp tasks_yaml/medical-kb.yaml tasks_yaml/my-task.yaml
   ```

2. **編輯配置**：
   
   - 修改 `task.name` 和 `task.description`
   - 調整 `prompts` 提示詞
   - 設定 `output_dir` 輸出目錄

3. **啟動任務**：
   
   ```bash
   python3 opencode-infinity.py my-task
   ```

</details>

<details>
<summary><b>Q: 程序會消耗很多 API 額度嗎？</b></summary>

**A:** 可控制消耗速度：

- 調整 `--delay` 參數（延遲秒數）
- 設定 `--threshold` 閾值（提前切換）
- 使用經濟型模型（如 `gpt-3.5-turbo`）
- 暫停：`Ctrl+Z`，恢復：`fg`

建議：測試階段使用 `--delay 3` 或更高。

</details>

<details>
<summary><b>Q: 支援其他語言嗎？</b></summary>

**A:** 完全支援！在配置文件中修改：

```yaml
task:
  language: "English"  # 或 "简体中文", "日本語" 等
```

程序會用該語言與 AI 溝通並生成內容。

</details>

## 🛠️ 配置範例庫

我們提供了多種開箱即用的任務配置：

| 配置檔案                       | 任務類型   | 適用場景           | 推薦閾值 |
| -------------------------- | ------ | -------------- | ---- |
| `medical-kb.yaml`          | 醫療知識庫  | 內容生成、文檔編寫      | 0.7  |
| `code-generation.yaml`     | 代碼生成   | Python 工具函數庫   | 0.7  |
| `api-development.yaml`     | API 開發 | RESTful API 後端 | 0.75 |
| `documentation.yaml`       | 技術文檔   | 教程、指南、FAQ      | 0.65 |
| `testing.yaml`             | 自動化測試  | 單元測試、集成測試      | 0.7  |
| `data-processing.yaml`     | 數據處理   | ETL、數據分析       | 0.7  |
| `frontend-components.yaml` | 前端組件   | React/Vue 組件庫  | 0.75 |

每個配置都包含：

- ✅ 精心設計的提示詞
- ✅ 合理的參數設定
- ✅ 詳細的註解說明
- ✅ 最佳實踐建議

## 🤝 貢獻

歡迎各種形式的貢獻！

### 如何貢獻

1. 🍴 **Fork 本專案**
2. 🌿 **創建特性分支**  
   
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. 💬 **提交更改**  
   
   ```bash
   git commit -m '✨ Add: amazing feature'
   ```
4. 📤 **推送到分支**  
   
   ```bash
   git push origin feature/amazing-feature
   ```
5. 🎉 **開啟 Pull Request**

### 貢獻方向

- 🐛 報告 Bug
- 💡 提出新功能建議
- 📝 改進文檔
- 🎨 優化配置範例
- 🌐 添加多語言支援

## 📄 開源協議

本專案採用 [MIT License](LICENSE)

- ✅ 商業使用
- ✅ 修改
- ✅ 分發
- ✅ 私人使用

## 🙏 致謝

- [OpenCode CLI](https://github.com/opencode-cli) - 強大的 AI CLI 工具
- 所有貢獻者和使用者的反饋與支持

## 📬 聯繫與支持

## ⭐ Star History

如果這個專案對你有幫助，歡迎給個 Star ⭐

---

<div align="center">

**OpenCode Infinity** - 讓 AI 24/7 為你工作 🚀

Made with ❤️ by wing9897

[文檔](README.md) · [範例](tasks_yaml/) · [問題回報](https://github.com/wing9897/opencode-infinity/issues)

</div>
