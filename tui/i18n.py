"""UI translations (ported from gui/i18n.js)."""
from __future__ import annotations

from typing import Any

from tui import state as ui_state

MESSAGES: dict[str, dict[str, str]] = {
    "zh-TW": {
        "app_title": "OpenCode Infinity",
        "brand_subtitle": "AI 編碼工具 7×24 無人值守自動化",
        "tab_console": "控制台",
        "tab_editor": "設定編輯器",
        "status_idle": "閒置",
        "status_running": "執行中",
        "label_config": "設定檔",
        "no_configs": "無設定檔",
        "btn_templates": "建立範本",
        "btn_refresh": "重新載入",
        "btn_diagnose": "診斷",
        "btn_start": "啟動",
        "btn_stop": "停止",
        "btn_save": "保存",
        "btn_reset": "清空",
        "btn_load": "載入",
        "btn_aigen": "AI 生成",
        "btn_add_prompt": "+ 提示詞",
        "advanced": "進階選項",
        "label_working_dir": "工作目錄覆寫",
        "label_session": "Session ID",
        "stat_rounds": "輪次",
        "stat_sessions": "Session",
        "stat_elapsed": "耗時",
        "log_title": "即時日誌",
        "log_empty": "選擇設定檔後點擊「啟動」，日誌會顯示在這裡。",
        "section_cli": "CLI 工具",
        "section_exec": "執行設定",
        "section_display": "顯示設定",
        "section_prompts": "循環提示詞",
        "label_tool": "CLI 工具",
        "label_model": "模型",
        "label_filename": "檔案名稱",
        "label_summary": "總結提示詞",
        "default_summary": "總結本輪工作（300字內）",
        "switch_auto": "自動",
        "switch_token": "Token 閾值",
        "switch_rounds": "輪次",
        "toast_saved": "設定已保存",
        "toast_loaded": "已載入 {name}",
        "toast_select_config": "請先選擇設定檔",
        "toast_started": "任務已啟動",
        "toast_stopped": "已送出停止請求",
        "toast_templates": "範本：{names}",
        "confirm_reset": "確定要清空所有設定嗎？",
        "aigen_title": "AI 生成設定",
        "aigen_task": "任務簡述",
        "aigen_apply": "套用到編輯器",
        "aigen_no_task": "（用戶未輸入任務描述）",
        "locale_zh": "中文",
        "locale_en": "English",
    },
    "en": {
        "app_title": "OpenCode Infinity",
        "brand_subtitle": "24/7 unattended automation for AI coding CLIs",
        "tab_console": "Console",
        "tab_editor": "Config Editor",
        "status_idle": "Idle",
        "status_running": "Running",
        "label_config": "Config",
        "no_configs": "No configs",
        "btn_templates": "Create templates",
        "btn_refresh": "Reload",
        "btn_diagnose": "Diagnose",
        "btn_start": "Start",
        "btn_stop": "Stop",
        "btn_save": "Save",
        "btn_reset": "Reset",
        "btn_load": "Load",
        "btn_aigen": "AI Generate",
        "btn_add_prompt": "+ Prompt",
        "advanced": "Advanced",
        "label_working_dir": "Working dir override",
        "label_session": "Session ID",
        "stat_rounds": "Rounds",
        "stat_sessions": "Sessions",
        "stat_elapsed": "Elapsed",
        "log_title": "Live logs",
        "log_empty": "Select a config and press Start to stream logs here.",
        "section_cli": "CLI",
        "section_exec": "Execution",
        "section_display": "Display",
        "section_prompts": "Prompts",
        "label_tool": "CLI tool",
        "label_model": "Model",
        "label_filename": "Filename",
        "label_summary": "Summary prompt",
        "default_summary": "Summarize this round (max 300 words)",
        "switch_auto": "Auto",
        "switch_token": "Token threshold",
        "switch_rounds": "Rounds",
        "toast_saved": "Config saved",
        "toast_loaded": "Loaded {name}",
        "toast_select_config": "Select a config first",
        "toast_started": "Task started",
        "toast_stopped": "Stop requested",
        "toast_templates": "Templates: {names}",
        "confirm_reset": "Clear all editor fields?",
        "aigen_title": "AI config generator",
        "aigen_task": "Task summary",
        "aigen_apply": "Apply to editor",
        "aigen_no_task": "(No task description provided)",
        "locale_zh": "中文",
        "locale_en": "English",
    },
}

AIGEN_PROMPTS: dict[str, str] = {
    "繁體中文": """你是一個 AI 自動化任務配置生成器。我正在使用一個叫 "OpenCode Infinity" 的工具，它能讓 AI 編碼工具（Codex、Claude、OpenCode、Copilot）7x24 無人值守自動循環執行任務。

我需要你根據我的任務簡述，生成以下 YAML 欄位：

## 輸出格式（請嚴格按照此 YAML 格式輸出）

```yaml
prompts:
  - "第一個循環提示詞（指示 AI 開始工作的方向）"
  - "第二個循環提示詞（指示 AI 繼續或深入）"
  - "第三個循環提示詞（指示 AI 檢查、驗證或整理）"

summary_prompt: "總結提示詞（要求 AI 在切換 session 前總結工作）"
```

## 規則

1. **prompts**: 生成 3-5 個循環提示詞，它們會被輪流使用
2. **summary_prompt**: 要求 AI 用 300 字內總結本輪完成的工作
3. 所有內容使用「{lang}」撰寫
4. 提示詞要具體且有方向性，避免太籠統的「繼續工作」

## 我的任務簡述

{task}

---

請直接輸出 YAML 格式的結果，不需要額外解釋。""",
    "English": """You are an AI task config generator. I use "OpenCode Infinity" to run Codex, Claude, OpenCode, or Copilot in unattended 24/7 loops.

Generate the following YAML fields from my task summary:

## Output format (strict YAML)

```yaml
prompts:
  - "First rotating prompt"
  - "Second rotating prompt"
  - "Third rotating prompt"

summary_prompt: "Summary prompt before session switch"
```

## Rules

1. **prompts**: 3-5 specific rotating prompts
2. **summary_prompt**: summarize the round in ~300 words
3. Write everything in "{lang}"
4. Avoid vague prompts like "continue working"

## My task summary

{task}

---

Output YAML only, no extra explanation.""",
}

_locale: str = ui_state.get_locale()


def get_locale() -> str:
    return _locale


def set_locale(locale: str) -> None:
    global _locale
    if locale not in MESSAGES:
        return
    _locale = locale
    ui_state.set_locale(locale)


def t(key: str, **params: Any) -> str:
    table = MESSAGES.get(_locale, MESSAGES["zh-TW"])
    text = table.get(key, MESSAGES["zh-TW"].get(key, key))
    for name, value in params.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def build_aigen_prompt(task_input: str, output_lang: str) -> str:
    template = AIGEN_PROMPTS.get(output_lang, AIGEN_PROMPTS["English"])
    task = task_input.strip() or t("aigen_no_task")
    return template.replace("{lang}", output_lang).replace("{task}", task)


def extract_yaml_from_text(text: str) -> str:
    raw = text.strip()
    if "```" in raw:
        lines = raw.splitlines()
        in_block = False
        collected: list[str] = []
        for line in lines:
            if line.strip().startswith("```"):
                if in_block:
                    break
                in_block = True
                continue
            if in_block:
                collected.append(line)
        if collected:
            return "\n".join(collected).strip()
    return raw
