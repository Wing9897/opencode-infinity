const STORAGE_KEY_LOCALE = 'oci_ui_locale';

const MESSAGES = {
    'zh-TW': {
        brandSubtitle: 'AI 編碼工具 7×24 無人值守自動化',
        configHint: '設定檔請手動編輯 YAML（路徑見啟動終端或 %APPDATA%\\OpenCodeInfinity\\configs\\）。',
        statusIdle: '閒置',
        statusRunning: '執行中',
        statusConnected: '已連線',
        statusDisconnected: '未連線',
        statusRunningConfig: '執行中：{name}',
        labelConfigFile: '設定檔',
        loading: '載入中...',
        noConfigs: '無設定檔',
        loadFailed: '載入失敗',
        refreshConfigs: '重新載入設定檔列表',
        btnCreateTemplates: '建立範本',
        btnStart: '▶ 啟動',
        btnStop: '⏹ 停止',
        advancedOptions: '進階選項',
        workingDirPlaceholder: '工作目錄（留空沿用啟動目錄或 YAML 設定）',
        labelWorkingDir: '工作目錄',
        labelSession: 'Session ID',
        sessionPlaceholder: 'Session ID（留空自動生成）',
        copySession: '複製 Session ID',
        statRounds: '輪次',
        statSessions: 'Session',
        statElapsed: '耗時',
        logTitle: '即時日誌',
        logAutoscroll: '自動捲動',
        logAutoscrollOff: '捲動已停',
        logClear: '清除日誌',
        logEmpty: '選擇設定檔後點擊「啟動」，日誌會即時顯示在這裡。',
        processing: '處理中...',
        starting: '啟動中...',
        stopping: '停止中...',
        toastSelectConfig: '請先選擇設定檔',
        toastTaskStarted: '任務已啟動',
        toastStartFailed: '啟動失敗',
        toastStopSent: '已送出停止請求',
        toastStopFailed: '停止失敗',
        toastConfigsRefreshed: '設定檔列表已更新',
        toastConfigsLoadFailed: '無法載入設定檔列表',
        toastTemplatesCreated: '已建立範本：{names}',
        toastTemplatesSkipped: '範本已存在（未變更）：{names}',
        toastTemplatesNone: '所有範本已存在',
        toastTemplatesFailed: '建立範本失敗',
        toastSessionCopied: '已複製 Session ID',
        toastCopyFailed: '複製失敗',
        unknownError: '未知錯誤',
        logStartSent: '🚀 已送出啟動請求...',
        logStartFailed: '❌ 啟動失敗：{error}',
        logStopSent: '⏹ 已送出停止請求',
    },
    en: {
        brandSubtitle: '24/7 unattended AI coding automation',
        configHint: 'Edit YAML configs manually (see config dir in the terminal or %APPDATA%\\OpenCodeInfinity\\configs\\).',
        statusIdle: 'Idle',
        statusRunning: 'Running',
        statusConnected: 'Connected',
        statusDisconnected: 'Offline',
        statusRunningConfig: 'Running: {name}',
        labelConfigFile: 'Config',
        loading: 'Loading...',
        noConfigs: 'No configs',
        loadFailed: 'Load failed',
        refreshConfigs: 'Reload config list',
        btnCreateTemplates: 'Create templates',
        btnStart: '▶ Start',
        btnStop: '⏹ Stop',
        advancedOptions: 'Advanced',
        workingDirPlaceholder: 'Working directory (empty = launch dir or YAML)',
        labelWorkingDir: 'Working directory',
        labelSession: 'Session ID',
        sessionPlaceholder: 'Session ID (auto-generated if empty)',
        copySession: 'Copy Session ID',
        statRounds: 'Rounds',
        statSessions: 'Sessions',
        statElapsed: 'Elapsed',
        logTitle: 'Live logs',
        logAutoscroll: 'Auto-scroll',
        logAutoscrollOff: 'Scroll paused',
        logClear: 'Clear',
        logEmpty: 'Select a config and click Start. Logs will appear here.',
        processing: 'Processing...',
        starting: 'Starting...',
        stopping: 'Stopping...',
        toastSelectConfig: 'Please select a config first',
        toastTaskStarted: 'Task started',
        toastStartFailed: 'Start failed',
        toastStopSent: 'Stop requested',
        toastStopFailed: 'Stop failed',
        toastConfigsRefreshed: 'Config list updated',
        toastConfigsLoadFailed: 'Failed to load config list',
        toastTemplatesCreated: 'Created templates: {names}',
        toastTemplatesSkipped: 'Templates already exist (unchanged): {names}',
        toastTemplatesNone: 'All templates already exist',
        toastTemplatesFailed: 'Failed to create templates',
        toastSessionCopied: 'Session ID copied',
        toastCopyFailed: 'Copy failed',
        unknownError: 'Unknown error',
        logStartSent: '🚀 Start request sent...',
        logStartFailed: '❌ Start failed: {error}',
        logStopSent: '⏹ Stop request sent',
    },
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

function setLocale(locale) {
    if (!MESSAGES[locale]) return;
    currentLocale = locale;
    localStorage.setItem(STORAGE_KEY_LOCALE, locale);
    applyI18n();
    if (typeof refreshDynamicI18n === 'function') refreshDynamicI18n();
}

function applyI18n() {
    document.documentElement.lang = currentLocale === 'en' ? 'en' : 'zh-TW';
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
    const langSelect = document.getElementById('ui-lang-select');
    if (langSelect) langSelect.value = currentLocale;
}

document.addEventListener('DOMContentLoaded', () => {
    const langSelect = document.getElementById('ui-lang-select');
    if (langSelect) {
        langSelect.value = currentLocale;
        langSelect.addEventListener('change', () => setLocale(langSelect.value));
    }
    applyI18n();
});
