// UI locale (interface language).
const STORAGE_KEY_LOCALE = 'oci_ui_locale';

const MESSAGES = {
    'zh-TW': {
        brandSubtitle: 'AI 編碼工具 7×24 無人值守自動化',
        statusIdle: '閒置',
        statusRunning: '執行中',
        statusConnected: '已連線',
        statusDisconnected: '未連線',
        statusRunningConfig: '執行中：{name}',
        tabConsole: '控制台',
        tabEditor: '設定編輯器',
        labelConfigFile: '設定檔',
        loading: '載入中...',
        noConfigs: '無設定檔',
        loadFailed: '載入失敗',
        selectConfig: '選擇設定檔',
        labelLoadConfig: '載入設定檔',
        labelFilename: '檔案名稱',
        editorReload: '重新載入設定',
        refreshConfigs: '重新載入設定檔列表',
        btnCreateTemplates: '建立範本',
        btnStart: '▶ 啟動',
        btnStop: '⏹ 停止',
        advancedOptions: '進階選項',
        labelWorkingDirOverride: '工作目錄覆寫（優先）',
        workingDirOverridePlaceholder: '留空則沿用 YAML 預設或啟動目錄',
        workingDirHintOverride: '啟動時將使用：{path}（控制台覆寫）',
        workingDirHintYaml: '啟動時將使用：{path}（YAML 預設）',
        workingDirHintLaunch: '啟動時將使用：程式啟動目錄（兩處皆留空）',
        labelWorkingDirYaml: '預設工作目錄（YAML）',
        workingDirYamlHint: '保存到設定檔；控制台「工作目錄覆寫」優先於此值',
        labelSession: 'Session ID',
        sessionPlaceholder: 'Session ID（留空自動生成）',
        copySession: '複製 Session ID',
        statRounds: '輪次',
        statSessions: 'Session',
        statElapsed: '耗時',
        logTitle: '即時日誌',
        logAutoscroll: '自動捲動',
        logAutoscrollOff: '捲動已停',
        logCompact: '輕量顯示',
        logCompactOff: '完整日誌',
        logCompactHint: '僅顯示最近 {n} 條重點日誌',
        logClear: '清除日誌',
        logEmpty: '選擇設定檔後點擊「啟動」，日誌會即時顯示在這裡。',
        filenamePlaceholder: '檔案名稱.yaml',
        btnAiGen: 'AI 生成',
        btnSave: '保存',
        btnReset: '清空',
        dirtyBadge: '未保存',
        sectionCli: 'CLI 工具',
        labelTool: 'CLI 工具',
        labelModel: '模型',
        labelFullAuto: 'Full Auto',
        labelSearch: 'Search',
        sectionPrompts: '循環提示詞',
        btnAddPrompt: '+ 添加提示詞',
        sectionExec: '執行設定',
        labelDelay: '延遲 (秒)',
        labelTimeout: '超時 (秒)',
        labelRetries: '重試',
        labelMaxRounds: '輪次',
        labelSwitchRounds: '切換輪次',
        labelContinueOnError: '錯誤時繼續',
        placeholderWorkingDir: '留空沿用啟動目錄',
        labelMaxTokens: 'Max Tokens',
        labelTokenThreshold: 'Token 閾值',
        sectionAdvanced: '進階設定',
        labelShowSession: '顯示 Session ID',
        labelShowToken: '顯示 Token 用量',
        labelShowTime: '顯示時間戳',
        labelSummaryPrompt: '總結提示詞',
        placeholderModel: '留空使用預設',
        placeholderRounds: '0 = 無限',
        placeholderSwitchRounds: '0 = 不切換',
        placeholderPrompt: '輸入提示詞...',
        promptLabel: '提示詞 #{n}',
        defaultSummary: '總結本輪工作（300字內）',
        tooltipFullAuto: '啟用後使用 --dangerously-bypass-approvals-and-sandbox（完全繞過安全限制，僅限隔離環境使用）',
        tooltipSearch: '允許搜尋網路（透過 -c search=true）',
        tooltipMaxTokens: '最大 Token 限制，用於判斷何時切換 Session（OpenCode/Claude 支援）',
        tooltipTokenThreshold: '達到此比例時切換 Session（0.0-1.0）。Codex 不支援 Token 統計，會改用輪次策略',
        tooltipSummary: 'Session 切換時的總結提示',
        modalTitle: 'AI 生成設定',
        modalClose: '關閉',
        aigenStep1: '步驟 1 · 生成 Prompt',
        aigenStep1Hint: '描述你的任務，複製 Prompt 到外部 AI 工具。',
        aigenTaskLabel: '任務簡述',
        aigenTaskPlaceholder: '例如：分析 2024 年最佳 React UI 框架，整理成比較表',
        aigenCopy: '複製 Prompt',
        aigenPreview: '預覽 Prompt',
        aigenStep2: '步驟 2 · 套用結果',
        aigenStep2Hint: '將 AI 回覆的 YAML 貼上並套用到編輯器。',
        aigenYamlPlaceholder: '貼上 AI 生成的 YAML（可含 ```yaml 代碼塊）',
        aigenApply: '套用到編輯器',
        processing: '處理中...',
        starting: '啟動中...',
        stopping: '停止中...',
        saving: '保存中...',
        confirmLeaveEditor: '編輯器有未保存的變更，確定要離開嗎？',
        confirmLoadOverwrite: '目前有未保存的變更，載入會覆蓋內容，確定繼續？',
        confirmReset: '確定要清空所有設定嗎？',
        promptFilename: '請輸入檔案名稱（例如 my-config.yaml）：',
        toastSelectConfig: '請先選擇設定檔',
        toastTaskStarted: '任務已啟動',
        toastStartFailed: '啟動失敗',
        toastStartRequestFailed: '啟動請求失敗',
        toastStopSent: '已送出停止請求',
        toastStopFailed: '停止失敗',
        toastConfigsRefreshed: '設定檔列表已更新',
        toastConfigsLoadFailed: '設定檔列表載入失敗',
        toastTemplatesCreated: '已建立範本：{names}',
        toastTemplatesOverwritten: '已覆蓋範本：{names}',
        toastTemplatesFailed: '建立範本失敗',
        toastSessionCopied: 'Session ID 已複製',
        toastCopyFailed: '複製失敗',
        toastNeedPrompt: '至少需要保留一個提示詞',
        toastRequiredFields: '請至少填寫一個提示詞',
        toastSaved: '設定已保存',
        toastSaveFailed: '保存失敗',
        toastSaveRequestFailed: '保存請求失敗',
        toastLoaded: '已載入 {name}',
        toastPromptCopied: 'Prompt 已複製',
        toastAiApplied: 'AI 設定已套用到編輯器',
        toastPasteYaml: '請先貼上 AI 回覆的 YAML',
        statusSaved: '已保存: {name}',
        statusSaveFailed: '保存失敗: {error}',
        statusYamlFailed: '生成 YAML 失敗',
        statusRequestFailed: '請求失敗: {error}',
        statusLoaded: '已載入: {name}',
        statusLoadFailed: '載入失敗',
        statusParseFailed: '解析失敗: {error}',
        statusCleared: '已清空',
        statusAiApplied: '已套用 AI 生成的設定，請檢查後再保存',
        aigenCopied: '已複製到剪貼簿',
        defaultPrompt: '繼續工作',
        unknownError: '未知錯誤',
        logStartSent: '🚀 啟動請求已送出...',
        logStartFailed: '❌ 啟動失敗: {error}',
        logRequestFailed: '❌ 請求失敗: {error}',
        logStopSent: '⏹ 停止請求已送出',
        aigenNoTask: '（用戶未輸入任務描述）',
    },
    en: {
        brandSubtitle: '24/7 unattended automation for AI coding CLIs',
        statusIdle: 'Idle',
        statusRunning: 'Running',
        statusConnected: 'Connected',
        statusDisconnected: 'Offline',
        statusRunningConfig: 'Running: {name}',
        tabConsole: 'Console',
        tabEditor: 'Config Editor',
        labelConfigFile: 'Config',
        loading: 'Loading...',
        noConfigs: 'No configs',
        loadFailed: 'Load failed',
        selectConfig: 'Select config',
        labelLoadConfig: 'Load config',
        labelFilename: 'Filename',
        editorReload: 'Reload config',
        refreshConfigs: 'Reload config list',
        btnCreateTemplates: 'Create templates',
        btnStart: '▶ Start',
        btnStop: '⏹ Stop',
        advancedOptions: 'Advanced',
        labelWorkingDirOverride: 'Working dir override (priority)',
        workingDirOverridePlaceholder: 'Empty = YAML default or launch directory',
        workingDirHintOverride: 'Will use: {path} (console override)',
        workingDirHintYaml: 'Will use: {path} (YAML default)',
        workingDirHintLaunch: 'Will use: launch directory (both empty)',
        labelWorkingDirYaml: 'Default working dir (YAML)',
        workingDirYamlHint: 'Saved to config; console override takes priority',
        labelSession: 'Session ID',
        sessionPlaceholder: 'Session ID (auto-generated if empty)',
        copySession: 'Copy Session ID',
        statRounds: 'Rounds',
        statSessions: 'Sessions',
        statElapsed: 'Elapsed',
        logTitle: 'Live logs',
        logAutoscroll: 'Auto-scroll',
        logAutoscrollOff: 'Scroll paused',
        logCompact: 'Compact',
        logCompactOff: 'Full logs',
        logCompactHint: 'Showing latest {n} key log lines',
        logClear: 'Clear',
        logEmpty: 'Select a config and click Start. Logs will appear here.',
        filenamePlaceholder: 'filename.yaml',
        btnAiGen: 'AI Generate',
        btnSave: 'Save',
        btnReset: 'Clear',
        dirtyBadge: 'Unsaved',
        sectionCli: 'CLI',
        labelTool: 'CLI tool',
        labelModel: 'Model',
        labelFullAuto: 'Full Auto',
        labelSearch: 'Search',
        sectionPrompts: 'Rotating prompts',
        btnAddPrompt: '+ Add prompt',
        sectionExec: 'Execution',
        labelDelay: 'Delay (s)',
        labelTimeout: 'Timeout (s)',
        labelRetries: 'Retries',
        labelMaxRounds: 'Rounds',
        labelSwitchRounds: 'Switch after',
        labelContinueOnError: 'Continue on error',
        placeholderWorkingDir: 'Empty = launch directory',
        labelMaxTokens: 'Max Tokens',
        labelTokenThreshold: 'Token threshold',
        sectionAdvanced: 'Advanced',
        labelShowSession: 'Show Session ID',
        labelShowToken: 'Show token usage',
        labelShowTime: 'Show timestamps',
        labelSummaryPrompt: 'Summary prompt',
        placeholderModel: 'Leave empty for default',
        placeholderRounds: '0 = unlimited',
        placeholderSwitchRounds: '0 = no switch',
        placeholderPrompt: 'Enter prompt...',
        promptLabel: 'Prompt #{n}',
        defaultSummary: 'Summarize this round (max 300 words)',
        tooltipFullAuto: 'Uses --dangerously-bypass-approvals-and-sandbox (isolated environments only)',
        tooltipSearch: 'Allow web search (via -c search=true)',
        tooltipMaxTokens: 'Max token limit for session switch (OpenCode/Claude)',
        tooltipTokenThreshold: 'Switch session at this ratio (0.0-1.0). Codex uses round strategy instead',
        tooltipSummary: 'Summary prompt when switching sessions',
        modalTitle: 'AI Generate Config',
        modalClose: 'Close',
        aigenStep1: 'Step 1 · Generate prompt',
        aigenStep1Hint: 'Describe your task and copy the prompt to an external AI tool.',
        aigenTaskLabel: 'Task summary',
        aigenTaskPlaceholder: 'e.g. Compare top React UI frameworks in 2024',
        aigenCopy: 'Copy prompt',
        aigenPreview: 'Preview prompt',
        aigenStep2: 'Step 2 · Apply result',
        aigenStep2Hint: 'Paste the AI YAML response and apply it to the editor.',
        aigenYamlPlaceholder: 'Paste AI-generated YAML (may include ```yaml blocks)',
        aigenApply: 'Apply to editor',
        processing: 'Processing...',
        starting: 'Starting...',
        stopping: 'Stopping...',
        saving: 'Saving...',
        confirmLeaveEditor: 'You have unsaved changes. Leave the editor?',
        confirmLoadOverwrite: 'Unsaved changes will be lost. Continue loading?',
        confirmReset: 'Clear all settings?',
        promptFilename: 'Enter filename (e.g. my-config.yaml):',
        toastSelectConfig: 'Please select a config first',
        toastTaskStarted: 'Task started',
        toastStartFailed: 'Start failed',
        toastStartRequestFailed: 'Start request failed',
        toastStopSent: 'Stop requested',
        toastStopFailed: 'Stop failed',
        toastConfigsRefreshed: 'Config list updated',
        toastConfigsLoadFailed: 'Failed to load config list',
        toastTemplatesCreated: 'Created templates: {names}',
        toastTemplatesOverwritten: 'Overwrote templates: {names}',
        toastTemplatesFailed: 'Failed to create templates',
        toastSessionCopied: 'Session ID copied',
        toastCopyFailed: 'Copy failed',
        toastNeedPrompt: 'Keep at least one prompt',
        toastRequiredFields: 'Add at least one prompt',
        toastSaved: 'Config saved',
        toastSaveFailed: 'Save failed',
        toastSaveRequestFailed: 'Save request failed',
        toastLoaded: 'Loaded {name}',
        toastPromptCopied: 'Prompt copied',
        toastAiApplied: 'AI config applied to editor',
        toastPasteYaml: 'Paste the AI YAML response first',
        statusSaved: 'Saved: {name}',
        statusSaveFailed: 'Save failed: {error}',
        statusYamlFailed: 'YAML generation failed',
        statusRequestFailed: 'Request failed: {error}',
        statusLoaded: 'Loaded: {name}',
        statusLoadFailed: 'Load failed',
        statusParseFailed: 'Parse failed: {error}',
        statusCleared: 'Cleared',
        statusAiApplied: 'AI config applied — review before saving',
        aigenCopied: 'Copied to clipboard',
        defaultPrompt: 'Continue working',
        unknownError: 'Unknown error',
        logStartSent: '🚀 Start request sent...',
        logStartFailed: '❌ Start failed: {error}',
        logRequestFailed: '❌ Request failed: {error}',
        logStopSent: '⏹ Stop request sent',
        aigenNoTask: '(No task description provided)',
    },
};

const AIGEN_PROMPTS = {
    '繁體中文': `你是一個 AI 自動化任務配置生成器。我正在使用一個叫 "OpenCode Infinity" 的工具，它能讓 AI 編碼工具（Codex、Claude、OpenCode、Copilot）7x24 無人值守自動循環執行任務。

我需要你根據我的任務簡述，生成以下 YAML 欄位：

## 輸出格式（請嚴格按照此 YAML 格式輸出）

\`\`\`yaml
prompts:
  - "第一個循環提示詞（指示 AI 開始工作的方向）"
  - "第二個循環提示詞（指示 AI 繼續或深入）"
  - "第三個循環提示詞（指示 AI 檢查、驗證或整理）"

summary_prompt: "總結提示詞（要求 AI 在切換 session 前總結工作）"
\`\`\`

## 規則

1. **prompts**: 生成 3-5 個循環提示詞，它們會被輪流使用
2. **summary_prompt**: 要求 AI 用 300 字內總結本輪完成的工作
3. 所有內容使用「{lang}」撰寫
4. 提示詞要具體且有方向性，避免太籠統的「繼續工作」

## 我的任務簡述

{task}

---

請直接輸出 YAML 格式的結果，不需要額外解釋。`,
    English: `You are an AI task config generator. I use "OpenCode Infinity" to run Codex, Claude, OpenCode, or Copilot in unattended 24/7 loops.

Generate the following YAML fields from my task summary:

## Output format (strict YAML)

\`\`\`yaml
prompts:
  - "First rotating prompt"
  - "Second rotating prompt"
  - "Third rotating prompt"

summary_prompt: "Summary prompt before session switch"
\`\`\`

## Rules

1. **prompts**: 3-5 specific rotating prompts
2. **summary_prompt**: summarize the round in ~300 words
3. Write everything in "{lang}"
4. Avoid vague prompts like "continue working"

## My task summary

{task}

---

Output YAML only, no extra explanation.`,
};

let currentLocale = localStorage.getItem(STORAGE_KEY_LOCALE) ||
    (navigator.language && navigator.language.toLowerCase().startsWith('zh') ? 'zh-TW' : 'en');

function t(key, params) {
    const table = MESSAGES[currentLocale] || MESSAGES['zh-TW'];
    let text = table[key] || MESSAGES['zh-TW'][key] || key;
    if (params) {
        Object.keys(params).forEach((k) => {
            text = text.split('{' + k + '}').join(String(params[k]));
        });
    }
    return text;
}

function getLocale() {
    return currentLocale;
}

function setLocale(locale) {
    if (!MESSAGES[locale]) return;
    currentLocale = locale;
    localStorage.setItem(STORAGE_KEY_LOCALE, locale);
    applyI18n();
    if (typeof refreshDynamicI18n === 'function') refreshDynamicI18n();
    else if (typeof updateAppStatusBadge === 'function') updateAppStatusBadge();
}

function applyI18n() {
    document.documentElement.lang = currentLocale === 'en' ? 'en' : 'zh-TW';
    document.title = currentLocale === 'en'
        ? 'OpenCode Infinity - Web GUI'
        : 'OpenCode Infinity - Web GUI';

    document.querySelectorAll('[data-i18n]').forEach((el) => {
        const key = el.dataset.i18n;
        const attr = el.dataset.i18nAttr;
        if (attr) el.setAttribute(attr, t(key));
        else el.textContent = t(key);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
        el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    document.querySelectorAll('[data-i18n-title]').forEach((el) => {
        el.title = t(el.dataset.i18nTitle);
    });
    document.querySelectorAll('[data-i18n-tooltip]').forEach((el) => {
        const tip = el.querySelector('.tooltip');
        if (tip) tip.textContent = t(el.dataset.i18nTooltip);
    });

    const langSelect = document.getElementById('ui-lang-select');
    if (langSelect) langSelect.value = currentLocale;
}

function buildAigenPrompt(taskInput, outputLang) {
    const template = AIGEN_PROMPTS[outputLang] || AIGEN_PROMPTS.English;
    const task = taskInput || t('aigenNoTask');
    return template.split('{lang}').join(outputLang).split('{task}').join(task);
}

document.addEventListener('DOMContentLoaded', () => {
    const langSelect = document.getElementById('ui-lang-select');
    if (langSelect) {
        langSelect.value = currentLocale;
        langSelect.addEventListener('change', () => setLocale(langSelect.value));
    }
    applyI18n();
});
