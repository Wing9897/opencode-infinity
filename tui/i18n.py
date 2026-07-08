"""UI translations for the Textual TUI."""
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
        "label_config_file": "設定檔",
        "prompt_select_config": "請選擇設定檔",
        "option_new_config": "＋ 新建設定檔…",
        "btn_new_config": "新建",
        "btn_reload_list": "重新載入",
        "btn_cancel": "取消",
        "btn_create": "建立",
        "new_config_title": "新建設定檔",
        "new_config_hint": "輸入新檔名（儲存時寫入）",
        "new_config_empty": "請輸入檔案名稱",
        "label_layout": "版面",
        "label_language": "語言",
        "no_configs": "無設定檔",
        "btn_templates": "建立範本",
        "btn_refresh": "重新載入",
        "btn_diagnose": "診斷",
        "btn_start": "啟動",
        "btn_stop": "停止",
        "btn_copy_log": "複製日誌",
        "btn_save": "保存",
        "btn_reset": "清空",
        "btn_load": "載入",
        "btn_aigen": "AI 產生設定",
        "btn_add_prompt": "＋ 新增提示詞",
        "advanced": "進階選項",
        "label_working_dir": "工作目錄覆寫",
        "label_session": "工作階段 ID",
        "stat_rounds": "輪次",
        "stat_sessions": "工作階段",
        "stat_session": "工作階段",
        "stat_elapsed": "耗時",
        "log_title": "即時日誌",
        "log_empty": "選擇設定檔後點擊「啟動」，日誌會顯示在這裡。",
        "section_cli": "命令列工具",
        "section_exec": "執行設定",
        "section_exec_basic": "基本執行設定",
        "section_exec_advanced": "進階執行設定",
        "section_codex_opts": "Codex 選項",
        "section_display": "顯示設定",
        "section_prompts": "循環提示詞",
        "label_tool": "命令列工具",
        "label_model": "模型",
        "label_filename": "檔案名稱",
        "label_summary": "總結提示詞",
        "label_full_auto": "全自動",
        "label_search": "網路搜尋",
        "label_continue_on_error": "錯誤時繼續",
        "label_show_session": "顯示工作階段 ID",
        "label_show_token": "顯示權杖用量",
        "label_show_time": "顯示時間戳記",
        "field_delay": "延遲（秒）",
        "field_timeout": "逾時（秒）",
        "field_retries": "重試次數",
        "field_max_rounds": "最大輪次",
        "field_switch_rounds": "切換輪次",
        "field_strategy": "切換策略",
        "field_max_tokens": "最大權杖數",
        "field_token_threshold": "權杖閾值",
        "field_working_dir": "工作目錄",
        "placeholder_model": "留空使用預設模型",
        "placeholder_working_dir": "留空使用設定檔或目前目錄",
        "placeholder_session": "留空自動產生",
        "badge_required": "必填",
        "hint_pick_config": "▶ 請先選擇設定檔才能啟動",
        "hint_pick_config_ok": "✓ 已選擇設定檔",
        "hint_select_config": "▶ 請先選擇要編輯的設定檔",
        "hint_select_config_ok": "✓ 已選擇設定檔",
        "toast_locale_switched": "語言已切換",
        "toast_locale_switched_to": "已切換為 {lang}",
        "toast_editor_cleared": "編輯器已清空",
        "toast_configs_reloaded": "設定檔列表已更新",
        "toast_new_config": "新建：{name}",
        "toast_aigen_applied": "AI 設定已套用",
        "toast_prompt_min": "至少保留一則提示詞",
        "aigen_step1": "步驟 1：輸入任務簡述，複製下方預覽給外部 AI",
        "aigen_step2": "步驟 2：將 AI 回覆的 YAML 貼到下方",
        "aigen_preview_label": "複製給 AI 的提示詞預覽",
        "aigen_paste_yaml": "貼上 AI 回覆的 YAML",
        "aigen_yaml_placeholder": "貼上提示詞與總結提示詞的 YAML…",
        "aigen_paste_notify": "請先貼上 AI 回覆的 YAML 內容",
        "aigen_lang_zh": "繁體中文",
        "aigen_lang_en": "英文",
        "hint_prompt": "▶ 至少填寫一則循環提示詞",
        "hint_prompt_ok": "✓ 提示詞已填寫",
        "density_compact": "緊湊",
        "density_normal": "標準",
        "density_comfortable": "寬鬆",
        "toast_density": "版面：{density}",
        "default_summary": "總結本輪工作（300字內）",
        "switch_auto": "自動",
        "switch_token": "權杖閾值",
        "switch_rounds": "依輪次",
        "toast_saved": "設定已保存",
        "toast_loaded": "已載入 {name}",
        "toast_select_config": "請先選擇設定檔",
        "toast_started": "任務已啟動",
        "toast_stopped": "已送出停止請求",
        "toast_log_copied": "日誌已複製到剪貼簿",
        "toast_log_copy_empty": "沒有可複製的日誌",
        "toast_templates": "範本：{names}",
        "confirm_reset": "確定要清空所有設定嗎？",
        "aigen_title": "AI 產生設定",
        "aigen_task": "任務簡述",
        "aigen_apply": "套用到編輯器",
        "aigen_no_task": "（用戶未輸入任務描述）",
        "locale_zh": "中文",
        "locale_en": "英文",
        "toast_quit_running": "請先停止任務再結束程式",
        "toast_saved_path": "已儲存：{path}",
        "templates_none": "（無）",
        "diag_title": "環境診斷",
        "diag_infinity": "Infinity",
        "diag_opencode": "OpenCode",
        "diag_headless": "無頭模式",
        "diag_config_dir": "設定目錄",
        "diag_cwd": "工作目錄",
        "diag_no_issues": "未發現問題",
        "binding_save": "儲存",
        "binding_lang": "語言",
        "binding_copy_log": "複製日誌",
        "binding_quit": "結束",
        "binding_larger": "放大",
        "binding_smaller": "縮小",
        "log_config_load_failed": "設定載入失敗：{error}",
        "log_cli_adapter_failed": "CLI 適配器失敗：{error}",
        "log_session_switch_failed": "工作階段切換失敗：{message}",
        "log_max_rounds": "已達最大輪次（{max_rounds}）",
        "log_aborted": "已中止：{reason}",
        "log_stopped": "已停止",
        "log_error": "錯誤：{type}：{message}",
        "err_already_running": "已在執行中",
    },
    "en": {
        "app_title": "OpenCode Infinity",
        "brand_subtitle": "24/7 unattended automation for AI coding CLIs",
        "tab_console": "Console",
        "tab_editor": "Config Editor",
        "status_idle": "Idle",
        "status_running": "Running",
        "label_config": "Config",
        "label_config_file": "Config file",
        "prompt_select_config": "Select a config",
        "option_new_config": "+ New config…",
        "btn_new_config": "New",
        "btn_reload_list": "Reload list",
        "btn_cancel": "Cancel",
        "btn_create": "Create",
        "new_config_title": "New config file",
        "new_config_hint": "Enter a filename (saved on Save)",
        "new_config_empty": "Enter a filename",
        "label_layout": "Layout",
        "label_language": "Language",
        "no_configs": "No configs",
        "btn_templates": "Create templates",
        "btn_refresh": "Reload",
        "btn_diagnose": "Diagnose",
        "btn_start": "Start",
        "btn_stop": "Stop",
        "btn_copy_log": "Copy log",
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
        "stat_session": "Session",
        "stat_elapsed": "Elapsed",
        "log_title": "Live logs",
        "log_empty": "Select a config and press Start to stream logs here.",
        "section_cli": "CLI",
        "section_exec": "Execution",
        "section_exec_basic": "Basic execution",
        "section_exec_advanced": "Advanced execution",
        "section_codex_opts": "Codex options",
        "section_display": "Display",
        "section_prompts": "Prompts",
        "label_tool": "CLI tool",
        "label_model": "Model",
        "label_filename": "Filename",
        "label_summary": "Summary prompt",
        "label_full_auto": "Full Auto",
        "label_search": "Search",
        "label_continue_on_error": "Continue on error",
        "label_show_session": "Show session ID",
        "label_show_token": "Show token usage",
        "label_show_time": "Show timestamp",
        "field_delay": "Delay (s)",
        "field_timeout": "Timeout (s)",
        "field_retries": "Retries",
        "field_max_rounds": "Max rounds",
        "field_switch_rounds": "Switch after rounds",
        "field_strategy": "Switch strategy",
        "field_max_tokens": "Max tokens",
        "field_token_threshold": "Token threshold",
        "field_working_dir": "Working directory",
        "placeholder_model": "Leave empty for default model",
        "placeholder_working_dir": "Leave empty for config or cwd",
        "placeholder_session": "Leave empty to auto-generate",
        "badge_required": "Required",
        "hint_pick_config": "▶ Select a config before starting",
        "hint_pick_config_ok": "✓ Config selected",
        "hint_select_config": "▶ Select a config to edit",
        "hint_select_config_ok": "✓ Config selected",
        "toast_locale_switched": "Language switched",
        "toast_locale_switched_to": "Switched to {lang}",
        "toast_editor_cleared": "Editor cleared",
        "toast_configs_reloaded": "Config list reloaded",
        "toast_new_config": "New: {name}",
        "toast_aigen_applied": "AI config applied",
        "toast_prompt_min": "Keep at least one prompt",
        "aigen_step1": "Step 1: Enter task summary, copy preview below to external AI",
        "aigen_step2": "Step 2: Paste AI YAML response below",
        "aigen_preview_label": "Prompt preview for AI",
        "aigen_paste_yaml": "Paste AI YAML response",
        "aigen_yaml_placeholder": "Paste prompts / summary_prompt YAML…",
        "aigen_lang_zh": "Traditional Chinese",
        "aigen_lang_en": "English",
        "aigen_paste_notify": "Paste the AI YAML response first",
        "hint_prompt": "▶ Enter at least one loop prompt",
        "hint_prompt_ok": "✓ Prompt filled",
        "density_compact": "Compact",
        "density_normal": "Normal",
        "density_comfortable": "Comfortable",
        "toast_density": "Layout: {density}",
        "default_summary": "Summarize this round (max 300 words)",
        "switch_auto": "Auto",
        "switch_token": "Token threshold",
        "switch_rounds": "Rounds",
        "toast_saved": "Config saved",
        "toast_loaded": "Loaded {name}",
        "toast_select_config": "Select a config first",
        "toast_started": "Task started",
        "toast_stopped": "Stop requested",
        "toast_log_copied": "Log copied to clipboard",
        "toast_log_copy_empty": "Nothing to copy",
        "toast_templates": "Templates: {names}",
        "confirm_reset": "Clear all editor fields?",
        "aigen_title": "AI config generator",
        "aigen_task": "Task summary",
        "aigen_apply": "Apply to editor",
        "aigen_no_task": "(No task description provided)",
        "locale_zh": "Chinese",
        "locale_en": "English",
        "toast_quit_running": "Stop the task before quitting",
        "toast_saved_path": "Saved: {path}",
        "templates_none": "(none)",
        "diag_title": "Environment diagnostics",
        "diag_infinity": "Infinity",
        "diag_opencode": "OpenCode",
        "diag_headless": "Headless",
        "diag_config_dir": "Config dir",
        "diag_cwd": "Working dir",
        "diag_no_issues": "No issues found",
        "binding_save": "Save",
        "binding_lang": "Lang",
        "binding_copy_log": "Copy log",
        "binding_quit": "Quit",
        "binding_larger": "Larger",
        "binding_smaller": "Smaller",
        "log_config_load_failed": "Config load failed: {error}",
        "log_cli_adapter_failed": "CLI adapter failed: {error}",
        "log_session_switch_failed": "Session switch failed: {message}",
        "log_max_rounds": "Reached max rounds ({max_rounds})",
        "log_aborted": "Aborted: {reason}",
        "log_stopped": "Stopped",
        "log_error": "Error: {type}: {message}",
        "err_already_running": "Already running",
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
    table = MESSAGES.get(_locale, MESSAGES["en"])
    text = table.get(key, MESSAGES["en"].get(key, key))
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
