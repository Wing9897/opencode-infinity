// ===== Utilities =====
const STORAGE_KEY_TAB = 'oci_active_tab';
const STORAGE_KEY_CONFIG = 'oci_last_config';
const STORAGE_KEY_WORKING_DIR = 'oci_working_dir';

function debounce(fn, delay) {
    let timer = null;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

function throttle(fn, limit) {
    let inThrottle = false;
    return function (...args) {
        if (!inThrottle) {
            fn.apply(this, args);
            inThrottle = true;
            setTimeout(() => { inThrottle = false; }, limit);
        }
    };
}

function formatBytes(bytes, decimal) {
    if (bytes === 0) return '0 B';
    const base = decimal ? 1000 : 1024;
    const units = decimal
        ? ['B', 'KB', 'MB', 'GB', 'TB']
        : ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
    const i = Math.floor(Math.log(bytes) / Math.log(base));
    const idx = Math.min(i, units.length - 1);
    return parseFloat((bytes / Math.pow(base, idx)).toFixed(1)) + ' ' + units[idx];
}

function slugify(text) {
    return text
        .toLowerCase()
        .trim()
        .replace(/[^\w\s-]/g, '')
        .replace(/[-\s]+/g, '-');
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

function pluralize(count, singular, plural) {
    return count === 1 ? singular : (plural || singular + 's');
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function showToast(message, type) {
    const root = document.getElementById('toast-root');
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + (type || 'info');
    toast.textContent = message;
    root.appendChild(toast);
    setTimeout(() => toast.remove(), 3200);
}

function setButtonLoading(btn, loading, loadingText) {
    if (!btn) return;
    if (loading) {
        if (!btn.dataset.originalText) btn.dataset.originalText = btn.textContent;
        btn.textContent = loadingText || t('processing');
        btn.classList.add('is-loading');
        btn.disabled = true;
        return;
    }
    if (btn.dataset.originalText) btn.textContent = btn.dataset.originalText;
    btn.classList.remove('is-loading');
}

async function apiFetch(url, options = {}) {
    const response = await fetch(url, options);
    let data = {};
    try {
        data = await response.json();
    } catch (_) {
        if (!response.ok) {
            throw new Error(response.statusText || 'Request failed');
        }
        return {};
    }
    if (!response.ok) {
        throw new Error((data && data.error) || response.statusText || 'Request failed');
    }
    return data;
}

function fillConfigSelect(selectEl, configs, emptyKey) {
    selectEl.innerHTML = '';
    if (!configs.length) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = t(emptyKey);
        selectEl.appendChild(opt);
        return;
    }
    configs.forEach((name) => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        selectEl.appendChild(opt);
    });
}

function refreshDynamicI18n() {
    document.querySelectorAll('.prompt-item').forEach((item) => {
        const id = item.id.replace('ed-prompt-', '');
        const label = item.querySelector('.prompt-label');
        const textarea = item.querySelector('textarea');
        if (label) label.textContent = t('promptLabel', { n: id });
        if (textarea) textarea.placeholder = t('placeholderPrompt');
    });
    document.querySelectorAll('button[data-i18n]').forEach((btn) => {
        if (!btn.classList.contains('is-loading')) {
            delete btn.dataset.originalText;
            btn.textContent = t(btn.dataset.i18n);
        }
    });
    const scrollBtn = document.getElementById('log-autoscroll-btn');
    if (scrollBtn) {
        scrollBtn.textContent = logAutoScroll ? t('logAutoscroll') : t('logAutoscrollOff');
    }
    updateAppStatusBadge();
}

// ===== Tab switching =====
let editorDirty = false;
let editorSuppressDirty = false;

function switchTab(tab, force) {
    if (!force && tab === 'console' && editorDirty) {
        if (!confirm(t('confirmLeaveEditor'))) return;
    }
    document.getElementById('tab-console').hidden = (tab !== 'console');
    document.getElementById('tab-editor').hidden = (tab !== 'editor');
    document.querySelectorAll('.tab-nav a').forEach(el => {
        el.classList.toggle('active', el.dataset.tab === tab);
    });
    localStorage.setItem(STORAGE_KEY_TAB, tab);
    syncTabsConfigSelection(tab);
}

function syncTabsConfigSelection(activeTab) {
    const edSelect = document.getElementById('editor-load-select');
    const filenameInput = document.getElementById('editor-filename');
    if (activeTab === 'editor') {
        const name = configSelect.value;
        if (name && edSelect && edSelect.querySelector('option[value="' + name + '"]')) {
            edSelect.value = name;
            if (filenameInput && !filenameInput.value.trim()) filenameInput.value = name;
        }
        return;
    }
    const editorName = (filenameInput && filenameInput.value.trim()) || (edSelect && edSelect.value) || '';
    if (editorName && configSelect.querySelector('option[value="' + editorName + '"]')) {
        syncConfigSelection(editorName);
        updateStartButtonState();
    }
}

// ===== Console Tab Logic =====
const logPanel = document.getElementById('log-panel');
const logEmpty = document.getElementById('log-empty');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const configSelect = document.getElementById('config-select');
const sessionInput = document.getElementById('session-id');
const workingDirInput = document.getElementById('working-dir');
const copySessionBtn = document.getElementById('copy-session-btn');
const statusRun = document.getElementById('status-run');
const statusConn = document.getElementById('status-conn');
const statusConfig = document.getElementById('status-config');
let eventSource = null;
let statusInterval = null;
let appRunning = false;
let appConnected = false;
let logAutoScroll = true;
let activeConfigName = '';
const STATUS_POLL_IDLE_MS = 8000;
const STATUS_POLL_ACTIVE_MS = 2000;

function updateAppStatusBadge() {
    statusRun.textContent = appRunning ? t('statusRunning') : t('statusIdle');
    statusRun.className = 'status-pill ' + (appRunning ? 'status-running' : 'status-idle');
    statusConn.textContent = appConnected ? t('statusConnected') : t('statusDisconnected');
    statusConn.className = 'status-pill ' + (appConnected ? 'status-connected' : 'status-disconnected');
    if (appRunning && activeConfigName) {
        statusConfig.hidden = false;
        statusConfig.textContent = activeConfigName;
        statusConfig.title = t('statusRunningConfig', { name: activeConfigName });
    } else {
        statusConfig.hidden = true;
        statusConfig.textContent = '';
    }
    copySessionBtn.disabled = !sessionInput.value.trim();
}

function syncConfigSelection(name) {
    if (!name) return;
    if (configSelect.querySelector('option[value="' + name + '"]')) configSelect.value = name;
    const edSelect = document.getElementById('editor-load-select');
    if (edSelect && edSelect.querySelector('option[value="' + name + '"]')) edSelect.value = name;
    localStorage.setItem(STORAGE_KEY_CONFIG, name);
    prefillWorkingDirFromConfig(name);
}

function prefillWorkingDirFromConfig(name) {
    if (!name || !workingDirInput) return;
    const saved = localStorage.getItem(STORAGE_KEY_WORKING_DIR);
    if (saved) {
        workingDirInput.value = saved;
        return;
    }
    apiFetch('/api/config/' + encodeURIComponent(name))
        .then((data) => {
            if (data.working_dir) workingDirInput.value = data.working_dir;
        })
        .catch(() => {});
}

function loadConfigList(selectName) {
    const preferred = selectName || localStorage.getItem(STORAGE_KEY_CONFIG) || '';
    return apiFetch('/api/configs')
        .then((data) => {
            const configs = data.configs || [];
            fillConfigSelect(configSelect, configs, 'noConfigs');
            const edSelect = document.getElementById('editor-load-select');
            if (edSelect) {
                edSelect.innerHTML = '<option value="">' + t('selectConfig') + '</option>';
                configs.forEach((c) => {
                    const opt = document.createElement('option');
                    opt.value = c;
                    opt.textContent = c;
                    edSelect.appendChild(opt);
                });
            }
            if (configs.length > 0) {
                const pick = preferred && configs.includes(preferred) ? preferred : configs[0];
                syncConfigSelection(pick);
                updateStartButtonState();
            } else {
                startBtn.disabled = true;
            }
        })
        .catch(() => {
            fillConfigSelect(configSelect, [], 'loadFailed');
            const edSelect = document.getElementById('editor-load-select');
            if (edSelect) edSelect.innerHTML = '<option value="">' + t('selectConfig') + '</option>';
            startBtn.disabled = true;
            showToast(t('toastConfigsLoadFailed'), 'error');
        });
}

function createFactoryTemplates(btn) {
    if (btn) setButtonLoading(btn, true, t('btnCreateTemplates'));
    return fetch('/api/config/create-templates', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
    })
    .then(r => r.json())
    .then(data => {
        if (btn) setButtonLoading(btn, false);
        if (!data.ok && data.errors && data.errors.length) {
            showToast(data.errors.join('; ') || t('toastTemplatesFailed'), 'error');
            return data;
        }
        const created = data.created || [];
        const skipped = data.skipped || [];
        if (created.length) showToast(t('toastTemplatesCreated', { names: created.join(', ') }), 'success');
        else if (skipped.length) showToast(t('toastTemplatesSkipped', { names: skipped.join(', ') }), 'info');
        else showToast(t('toastTemplatesNone'), 'info');
        return loadConfigList(created[0] || configSelect.value).then(() => data);
    })
    .catch(() => {
        if (btn) setButtonLoading(btn, false);
        showToast(t('toastTemplatesFailed'), 'error');
    });
}

function updateStartButtonState() {
    if (appRunning) return;
    startBtn.disabled = !configSelect.value;
}

function hideLogEmpty() {
    if (logEmpty) logEmpty.hidden = true;
}

const LOG_FLUSH_BATCH_SIZE = 40;
let logPending = [];
let logFlushScheduled = false;

function buildLogLine(msg) {
    const div = document.createElement('div');
    let cls = '';
    if (msg.includes('\u2705') || msg.includes('完成') || msg.includes('complete')) cls = ' log-success';
    else if (msg.includes('\u274c') || msg.includes('失敗') || msg.includes('failed')) cls = ' log-error';
    else if (msg.includes('\u26a0') || msg.includes('WARNING')) cls = ' log-warning';
    else if (msg.includes('  | +')) cls = ' log-diff-add';
    else if (msg.includes('  | -')) cls = ' log-diff-del';
    else if (msg.includes('  | ')) cls = ' log-cli';
    div.className = cls;
    div.textContent = msg;
    return div;
}

function flushLogPending() {
    logFlushScheduled = false;
    if (logPending.length === 0) return;
    hideLogEmpty();
    const fragment = document.createDocumentFragment();
    const batch = logPending.splice(0, LOG_FLUSH_BATCH_SIZE);
    batch.forEach((msg) => fragment.appendChild(buildLogLine(msg)));
    logPanel.appendChild(fragment);
    if (logAutoScroll) logPanel.scrollTop = logPanel.scrollHeight;
    while (logPanel.children.length > 501) {
        const first = logPanel.firstElementChild;
        if (first && first.id !== 'log-empty') first.remove();
    }
    if (logPending.length > 0) scheduleLogFlush();
}

function scheduleLogFlush() {
    if (logFlushScheduled) return;
    logFlushScheduled = true;
    requestAnimationFrame(flushLogPending);
}

function addLog(msg) {
    logPending.push(msg);
    scheduleLogFlush();
}

function connectSSE() {
    if (eventSource) eventSource.close();
    eventSource = new EventSource('/api/logs');
    eventSource.onopen = () => {
        appConnected = true;
        updateAppStatusBadge();
        // Server replays recent history on (re)connect; reset panel to avoid duplicates.
        [...logPanel.children].forEach(child => {
            if (child.id !== 'log-empty') child.remove();
        });
        if (logEmpty) logEmpty.hidden = false;
    };
    eventSource.onmessage = (e) => {
        if (e.data && e.data !== ':keepalive') addLog(e.data);
    };
    eventSource.onerror = () => {
        appConnected = false;
        updateAppStatusBadge();
        eventSource.close();
        setTimeout(connectSSE, 3000);
    };
}

function scheduleStatusPoll() {
    if (statusInterval) clearInterval(statusInterval);
    if (document.hidden) return;
    const ms = appRunning ? STATUS_POLL_ACTIVE_MS : STATUS_POLL_IDLE_MS;
    statusInterval = setInterval(updateStatus, ms);
}

let elapsedTicker = null;
let elapsedStartMs = 0;

function formatElapsedSeconds(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return minutes + ':' + String(seconds).padStart(2, '0');
}

function startElapsedTicker() {
    if (elapsedTicker) return;
    elapsedStartMs = Date.now();
    elapsedTicker = setInterval(() => {
        if (!appRunning) return;
        const seconds = Math.floor((Date.now() - elapsedStartMs) / 1000);
        document.getElementById('stat-elapsed').textContent = formatElapsedSeconds(seconds);
    }, 1000);
}

function stopElapsedTicker() {
    if (elapsedTicker) clearInterval(elapsedTicker);
    elapsedTicker = null;
}

function updateStatus() {
    apiFetch('/api/status').then((data) => {
        document.getElementById('stat-rounds').textContent = data.round_count || 0;
        document.getElementById('stat-sessions').textContent = data.session_count || 0;
        // Keep client-side ticker authoritative while running to avoid UI freezes
        // when status polling stalls under heavy log traffic.
        if (!elapsedTicker) {
            document.getElementById('stat-elapsed').textContent = data.elapsed || '0:00';
        }
        const wasRunning = appRunning;
        appRunning = !!data.running;
        activeConfigName = data.running ? (data.config_name || '') : '';
        if (data.session_id) sessionInput.value = data.session_id;
        updateAppStatusBadge();

        document.querySelectorAll('.stat-card').forEach((card) => card.classList.remove('is-active'));
        if (data.running) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
            document.getElementById('stat-card-rounds')?.classList.add('is-active');
        } else {
            stopBtn.disabled = true;
            updateStartButtonState();
        }
        if (wasRunning !== appRunning) {
            scheduleStatusPoll();
            if (appRunning) startElapsedTicker();
            else stopElapsedTicker();
        }
        if (!appRunning) {
            document.getElementById('stat-elapsed').textContent = data.elapsed || '0:00';
        }
    }).catch(() => {
        appConnected = false;
        updateAppStatusBadge();
    });
}

startBtn.addEventListener('click', () => {
    const config = configSelect.value;
    if (!config) {
        showToast(t('toastSelectConfig'), 'error');
        return;
    }
    const sid = sessionInput.value.trim();
    const workingDir = workingDirInput ? workingDirInput.value.trim() : '';
    if (workingDir) localStorage.setItem(STORAGE_KEY_WORKING_DIR, workingDir);
    else localStorage.removeItem(STORAGE_KEY_WORKING_DIR);
    setButtonLoading(startBtn, true, t('starting'));
    apiFetch('/api/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({config: config, session_id: sid, working_dir: workingDir})
    })
    .then((data) => {
        setButtonLoading(startBtn, false);
        addLog(t('logStartSent'));
        sessionInput.value = data.session_id || '';
        activeConfigName = config;
        syncConfigSelection(config);
        startBtn.disabled = true;
        stopBtn.disabled = false;
        appRunning = true;
        startElapsedTicker();
        scheduleStatusPoll();
        updateAppStatusBadge();
        showToast(t('toastTaskStarted'), 'success');
    })
    .catch((e) => {
        setButtonLoading(startBtn, false);
        updateStartButtonState();
        addLog(t('logStartFailed', { error: e.message || t('unknownError') }));
        showToast(e.message || t('toastStartFailed'), 'error');
    });
});

stopBtn.addEventListener('click', () => {
    setButtonLoading(stopBtn, true, t('stopping'));
    apiFetch('/api/stop', { method: 'POST' })
    .then(() => {
        setButtonLoading(stopBtn, false);
        addLog(t('logStopSent'));
        showToast(t('toastStopSent'), 'info');
    })
    .catch((e) => {
        setButtonLoading(stopBtn, false);
        addLog('\u26a0\ufe0f ' + (e.message || t('toastStopFailed')));
        showToast(e.message || t('toastStopFailed'), 'error');
    });
});

configSelect.addEventListener('change', () => {
    syncConfigSelection(configSelect.value);
    updateStartButtonState();
});

document.getElementById('refresh-configs-btn').addEventListener('click', () => {
    loadConfigList(configSelect.value).then(() => showToast(t('toastConfigsRefreshed'), 'info'));
});

document.querySelectorAll('.js-create-templates-btn').forEach((btn) => {
    btn.addEventListener('click', () => createFactoryTemplates(btn));
});

document.getElementById('log-clear-btn').addEventListener('click', () => {
    [...logPanel.children].forEach(child => {
        if (child.id !== 'log-empty') child.remove();
    });
    if (logEmpty) logEmpty.hidden = false;
});

document.getElementById('log-autoscroll-btn').addEventListener('click', (e) => {
    logAutoScroll = !logAutoScroll;
    e.currentTarget.classList.toggle('active', logAutoScroll);
    e.currentTarget.textContent = logAutoScroll ? t('logAutoscroll') : t('logAutoscrollOff');
});

copySessionBtn.addEventListener('click', () => {
    const value = sessionInput.value.trim();
    if (!value) return;
    navigator.clipboard.writeText(value)
        .then(() => showToast(t('toastSessionCopied'), 'success'))
        .catch(() => showToast(t('toastCopyFailed'), 'error'));
});

sessionInput.addEventListener('input', updateAppStatusBadge);

if (workingDirInput) {
    const savedWorkingDir = localStorage.getItem(STORAGE_KEY_WORKING_DIR);
    if (savedWorkingDir) workingDirInput.value = savedWorkingDir;
    workingDirInput.addEventListener('change', () => {
        const value = workingDirInput.value.trim();
        if (value) localStorage.setItem(STORAGE_KEY_WORKING_DIR, value);
        else localStorage.removeItem(STORAGE_KEY_WORKING_DIR);
    });
}

// ===== Editor Tab Logic =====
let edPromptCounter = 0;
const editorDirtyBadge = document.getElementById('editor-dirty-badge');
const editorStatusBar = document.getElementById('editor-status');
const editorStatusText = document.getElementById('editor-status-text');

function markEditorDirty() {
    if (editorSuppressDirty) return;
    editorDirty = true;
    editorDirtyBadge.hidden = false;
}

function clearEditorDirty() {
    editorDirty = false;
    editorDirtyBadge.hidden = true;
}

function editorUpdateCli() {
    const tool = document.getElementById('ed-cli-tool').value;
    document.getElementById('ed-codex-options').hidden = (tool !== 'codex');
}

function editorAddPrompt(content) {
    edPromptCounter++;
    const container = document.getElementById('ed-prompts-container');
    const div = document.createElement('div');
    div.className = 'prompt-item';
    div.id = 'ed-prompt-' + edPromptCounter;
    div.innerHTML = '<div class="prompt-label">' + t('promptLabel', { n: edPromptCounter }) + '</div>' +
        '<textarea class="ed-prompt-textarea" placeholder="' + t('placeholderPrompt') + '">' + (content || '') + '</textarea>' +
        '<button type="button" class="prompt-remove" onclick="editorRemovePrompt(' + edPromptCounter + ')">\u00d7</button>';
    container.appendChild(div);
    div.querySelector('textarea').addEventListener('input', markEditorDirty);
}

function editorRemovePrompt(id) {
    const el = document.getElementById('ed-prompt-' + id);
    if (!el) return;
    const container = document.getElementById('ed-prompts-container');
    if (container.children.length <= 1) {
        showToast(t('toastNeedPrompt'), 'error');
        return;
    }
    el.remove();
    markEditorDirty();
}

function editorGetPrompts() {
    const areas = document.querySelectorAll('.ed-prompt-textarea');
    const prompts = [];
    areas.forEach(ta => { const v = ta.value.trim(); if (v) prompts.push(v); });
    return prompts.length > 0 ? prompts : [t('defaultPrompt')];
}

function editorValidate() {
    const taskName = document.getElementById('ed-task-name');
    let hasPrompt = false;
    document.querySelectorAll('.ed-prompt-textarea').forEach(ta => {
        if (ta.value.trim()) hasPrompt = true;
    });
    let valid = true;
    taskName.classList.remove('field-invalid');
    if (!taskName.value.trim()) {
        taskName.classList.add('field-invalid');
        valid = false;
    }
    if (!hasPrompt) valid = false;
    if (!valid) showToast(t('toastRequiredFields'), 'error');
    return valid;
}

function editorGenerateConfig() {
    const config = {};
    const taskName = document.getElementById('ed-task-name').value.trim();
    const taskDesc = document.getElementById('ed-task-desc').value.trim();
    const taskLang = document.getElementById('ed-task-lang').value;
    const taskOutput = document.getElementById('ed-task-output').value.trim() || 'output';
    config.task = { name: taskName || t('defaultTaskName'), language: taskLang, output_dir: taskOutput };
    if (taskDesc) config.task.description = taskDesc;
    const cliTool = document.getElementById('ed-cli-tool').value;
    config.cli = { tool: cliTool };
    const cliModel = document.getElementById('ed-cli-model').value.trim();
    if (cliModel) config.cli.model = cliModel;
    const cliCommand = document.getElementById('ed-cli-command').value.trim();
    if (cliCommand) config.cli.commands = { run_session: cliCommand };
    if (cliTool === 'codex') {
        config.cli.full_auto = document.getElementById('ed-cli-fullauto').checked;
        config.cli.search = document.getElementById('ed-cli-search').checked;
    }
    config.execution = {
        delay: parseInt(document.getElementById('ed-exec-delay').value) || 1,
        timeout: parseInt(document.getElementById('ed-exec-timeout').value) || 300,
        max_retries: parseInt(document.getElementById('ed-exec-retries').value) || 5,
        max_rounds: parseInt(document.getElementById('ed-exec-rounds').value) || 0,
        switch_after_rounds: parseInt(document.getElementById('ed-exec-switch-rounds').value) || 0,
        max_tokens: parseInt(document.getElementById('ed-max-tokens').value) || 128000,
        token_threshold: parseFloat(document.getElementById('ed-token-threshold').value) || 0.7,
        auto_continue_on_error: document.getElementById('ed-exec-continue').checked
    };
    const workingDir = document.getElementById('ed-exec-working-dir').value.trim();
    if (workingDir) config.execution.working_dir = workingDir;
    config.display = {
        show_session_id: document.getElementById('ed-disp-session').checked,
        show_token_usage: document.getElementById('ed-disp-token').checked,
        show_timestamp: document.getElementById('ed-disp-time').checked
    };
    config.prompts = editorGetPrompts();
    config.summary_prompt = document.getElementById('ed-summary-prompt').value.trim() || t('defaultSummary');
    return config;
}

function editorSave() {
    if (!editorValidate()) return;
    let filename = document.getElementById('editor-filename').value.trim();
    if (!filename) {
        filename = prompt(t('promptFilename'));
        if (!filename) return;
    }
    if (!filename.endsWith('.yaml') && !filename.endsWith('.yml')) filename += '.yaml';
    const config = editorGenerateConfig();
    const saveBtn = document.getElementById('editor-save-btn');
    setButtonLoading(saveBtn, true, t('saving'));
    fetch('/api/config/generate-yaml', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(config)
    }).then(r => r.json()).then(data => {
        if (!data.yaml) {
            setButtonLoading(saveBtn, false);
            editorSetStatus(t('statusYamlFailed'), true);
            return;
        }
        return fetch('/api/config/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({filename: filename, content: data.yaml})
        });
    }).then(r => { if (r) return r.json(); }).then(data => {
        setButtonLoading(saveBtn, false);
        if (data && data.ok) {
            editorSetStatus(t('statusSaved', { name: filename }), false);
            document.getElementById('editor-filename').value = filename;
            clearEditorDirty();
            loadConfigList(filename);
            showToast(t('toastSaved'), 'success');
        } else if (data) {
            editorSetStatus(t('statusSaveFailed', { error: data.error || t('unknownError') }), true);
            showToast(data.error || t('toastSaveFailed'), 'error');
        }
    }).catch(e => {
        setButtonLoading(saveBtn, false);
        editorSetStatus(t('statusRequestFailed', { error: e.message }), true);
        showToast(t('toastSaveRequestFailed'), 'error');
    });
}

function editorLoad() {
    const sel = document.getElementById('editor-load-select').value;
    if (!sel) return;
    if (editorDirty && !confirm(t('confirmLoadOverwrite'))) {
        document.getElementById('editor-load-select').value = document.getElementById('editor-filename').value || '';
        return;
    }
    apiFetch('/api/config/' + encodeURIComponent(sel))
        .then((data) => apiFetch('/api/config/parse-yaml', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({content: data.content})
        }))
        .then((parsed) => {
            if (parsed.error) {
                editorSetStatus(t('statusParseFailed', { error: parsed.error }), true);
                return;
            }
            editorFillForm(parsed.config);
            document.getElementById('editor-filename').value = sel;
            syncConfigSelection(sel);
            if (parsed.config.execution && parsed.config.execution.working_dir && workingDirInput) {
                workingDirInput.value = parsed.config.execution.working_dir;
            }
            editorSetStatus(t('statusLoaded', { name: sel }), false);
            showToast(t('toastLoaded', { name: sel }), 'info');
        })
        .catch((e) => editorSetStatus(t('statusLoadFailed') + ': ' + e.message, true));
}

function editorFillForm(cfg) {
    editorSuppressDirty = true;
    const task = cfg.task || {};
    const cli = cfg.cli || {};
    const exec = cfg.execution || {};
    const disp = cfg.display || {};
    document.getElementById('ed-task-name').value = task.name || '';
    document.getElementById('ed-task-desc').value = task.description || '';
    document.getElementById('ed-task-lang').value = task.language || '繁體中文';
    document.getElementById('ed-task-output').value = task.output_dir || 'output';
    document.getElementById('ed-cli-tool').value = cli.tool || 'opencode';
    document.getElementById('ed-cli-model').value = cli.model || '';
    document.getElementById('ed-cli-fullauto').checked = cli.full_auto === true;
    document.getElementById('ed-cli-search').checked = cli.search === true;
    document.getElementById('ed-cli-command').value = (cli.commands && cli.commands.run_session) || '';
    editorUpdateCli();
    document.getElementById('ed-exec-delay').value = exec.delay != null ? exec.delay : 1;
    document.getElementById('ed-exec-timeout').value = exec.timeout != null ? exec.timeout : 300;
    document.getElementById('ed-exec-retries').value = exec.max_retries != null ? exec.max_retries : 5;
    document.getElementById('ed-exec-rounds').value = exec.max_rounds != null ? exec.max_rounds : 0;
    document.getElementById('ed-exec-switch-rounds').value = exec.switch_after_rounds != null ? exec.switch_after_rounds : 0;
    document.getElementById('ed-max-tokens').value = exec.max_tokens != null ? exec.max_tokens : 128000;
    document.getElementById('ed-token-threshold').value = exec.token_threshold != null ? exec.token_threshold : 0.7;
    document.getElementById('ed-exec-continue').checked = exec.auto_continue_on_error !== false;
    document.getElementById('ed-exec-working-dir').value = exec.working_dir || '';
    document.getElementById('ed-disp-session').checked = disp.show_session_id !== false;
    document.getElementById('ed-disp-token').checked = disp.show_token_usage !== false;
    document.getElementById('ed-disp-time').checked = disp.show_timestamp !== false;
    document.getElementById('ed-prompts-container').innerHTML = '';
    edPromptCounter = 0;
    const prompts = cfg.prompts || [''];
    prompts.forEach(p => editorAddPrompt(typeof p === 'string' ? p : ''));
    document.getElementById('ed-summary-prompt').value = cfg.summary_prompt || t('defaultSummary');
    document.getElementById('ed-task-name').classList.remove('field-invalid');
    editorSuppressDirty = false;
    clearEditorDirty();
}

function editorReset() {
    if (!confirm(t('confirmReset'))) return;
    editorFillForm({});
    document.getElementById('editor-filename').value = '';
    editorSetStatus(t('statusCleared'), false);
}

function editorSetStatus(msg, isError) {
    editorStatusBar.hidden = !msg;
    editorStatusText.textContent = msg || '';
    editorStatusText.style.color = isError ? 'var(--danger)' : 'var(--success)';
}

document.getElementById('ed-add-prompt-btn').addEventListener('click', () => {
    editorAddPrompt('');
    markEditorDirty();
});
document.getElementById('editor-save-btn').addEventListener('click', editorSave);
document.getElementById('editor-reset-btn').addEventListener('click', editorReset);
document.getElementById('editor-reload-btn').addEventListener('click', () => {
    const sel = document.getElementById('editor-load-select').value;
    if (!sel) {
        showToast(t('toastSelectConfig'), 'error');
        return;
    }
    editorLoad();
});

const editorScroll = document.querySelector('.editor-form-scroll');
if (editorScroll) {
    editorScroll.addEventListener('input', (e) => {
        if (e.target.matches('input, textarea, select')) markEditorDirty();
    });
    editorScroll.addEventListener('change', (e) => {
        if (e.target.matches('input[type="checkbox"], select')) markEditorDirty();
    });
}

// ===== AI Generate Modal Logic =====
function aigenOpen() {
    const modal = document.getElementById('aigen-modal');
    const editorLang = document.getElementById('ed-task-lang').value;
    if (editorLang) document.getElementById('aigen-lang').value = editorLang;
    aigenUpdatePreview();
    modal.classList.add('open');
    document.getElementById('aigen-task-input').focus();
}

function aigenClose() {
    document.getElementById('aigen-modal').classList.remove('open');
    document.getElementById('aigen-status').textContent = '';
}

function aigenCloseOnBackdrop(event) {
    if (event.target.id === 'aigen-modal') aigenClose();
}

function aigenExtractYaml(text) {
    const fenced = text.match(/```(?:yaml|yml)?\s*([\s\S]*?)```/i);
    return (fenced ? fenced[1] : text).trim();
}

function aigenApplyYaml() {
    const raw = document.getElementById('aigen-yaml-input').value.trim();
    if (!raw) {
        aigenSetStatus(t('toastPasteYaml'), true);
        return;
    }
    const content = aigenExtractYaml(raw);
    fetch('/api/config/parse-yaml', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({content: content})
    }).then(r => r.json()).then(parsed => {
        if (parsed.error) {
            aigenSetStatus(t('statusParseFailed', { error: parsed.error }), true);
            return;
        }
        editorFillForm(parsed.config);
        markEditorDirty();
        aigenClose();
        switchTab('editor', true);
        editorSetStatus(t('statusAiApplied'), false);
        showToast(t('toastAiApplied'), 'success');
    }).catch(e => aigenSetStatus(t('statusRequestFailed', { error: e.message }), true));
}

function aigenSetStatus(msg, isError) {
    const status = document.getElementById('aigen-status');
    status.textContent = msg;
    status.style.color = isError ? 'var(--danger)' : 'var(--success)';
}

function aigenBuildPrompt() {
    const taskInput = document.getElementById('aigen-task-input').value.trim();
    const lang = document.getElementById('aigen-lang').value;
    return buildAigenPrompt(taskInput, lang);
}

function aigenUpdatePreview() {
    document.getElementById('aigen-preview').textContent = aigenBuildPrompt();
}

function aigenCopy() {
    const text = aigenBuildPrompt();
    navigator.clipboard.writeText(text).then(() => {
        aigenSetStatus(t('aigenCopied'), false);
        showToast(t('toastPromptCopied'), 'success');
        setTimeout(() => { document.getElementById('aigen-status').textContent = ''; }, 2500);
    }).catch(() => {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        aigenSetStatus(t('aigenCopied'), false);
        showToast(t('toastPromptCopied'), 'success');
    });
}

document.getElementById('editor-aigen-btn').addEventListener('click', aigenOpen);
document.getElementById('aigen-copy-btn').addEventListener('click', aigenCopy);
document.getElementById('aigen-apply-btn').addEventListener('click', aigenApplyYaml);
document.getElementById('aigen-task-input').addEventListener('input', aigenUpdatePreview);
document.getElementById('aigen-lang').addEventListener('change', aigenUpdatePreview);

document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') aigenClose();
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        if (!document.getElementById('tab-editor').hidden) {
            event.preventDefault();
            editorSave();
        }
    }
});

// Init
updateAppStatusBadge();
connectSSE();
scheduleStatusPoll();
updateStatus();
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = null;
    } else {
        updateStatus();
        scheduleStatusPoll();
    }
});
loadConfigList().then(() => {
    const savedTab = localStorage.getItem(STORAGE_KEY_TAB);
    if (savedTab === 'editor') switchTab('editor', true);
});
editorAddPrompt('');
